from .i18n import tr
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(os.environ.get("MANGA_STUDIO_HOME", Path(__file__).resolve().parents[1])).resolve()
EXTENSIONS = {".jpg", ".jpeg", ".png"}
MODES = {"tint": "Цвет по оригиналу", "luma": "Яркость оригинала"}


@dataclass(frozen=True)
class Settings:
    device: str = "auto"
    size: int = 576
    denoise: bool = True
    sigma: int = 25
    models: Path = ROOT / ".models"


@dataclass(frozen=True)
class Stroke:
    color: tuple
    width: float  # Fraction of scan width.
    points: tuple  # Coordinates normalized to the unpadded page.
    kind: str = "hint"


def page_order(path):
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", path.name)]


def open_page(path):
    try:
        source = Image.open(path)
    except UnidentifiedImageError as error:
        raise ValueError(tr("Не удалось прочитать изображение. Проверьте формат и целостность файла.")) from error
    with source as src:
        if src.format not in ("JPEG", "PNG"):
            raise ValueError(tr("Поддерживаются только JPEG и PNG."))
        im = ImageOps.exif_transpose(src)
        if im.mode.startswith("I;16") or im.mode == "I":
            samples = np.asarray(im).astype(np.uint32)
            gray = ((samples.clip(0, 65535) + 128) // 257).astype(np.uint8)
            if isinstance(im.info.get("transparency"), int):
                gray[samples == im.info["transparency"]] = 255
            return Image.fromarray(gray).convert("RGB")
        if "A" in im.getbands() or "transparency" in im.info:
            rgba = im.convert("RGBA")
            white = Image.new("RGB", rgba.size, "white")
            white.paste(rgba, mask=rgba.getchannel("A"))
            return white
        return im.convert("RGB")


def weight_files(settings):
    denoiser = settings.models / "denoising" / "models" / "net_rgb.pth"
    if not denoiser.is_file():
        denoiser = settings.models / "net_rgb.pth"
    return settings.models / "generator.zip", denoiser


def missing_weights(settings):
    gen, den = weight_files(settings)
    return [p.name for p in ([gen, den] if settings.denoise else [gen]) if not p.is_file()]


def apply_strokes(model, strokes):
    if not strokes:
        return
    height, width = model.current_image.shape[-2:]
    pad_h, pad_w = model.current_pad
    page_w, page_h = width - pad_w, height - pad_h
    colors = np.zeros((height, width, 3), np.uint8)
    mask = np.zeros((height, width), np.uint8)
    for stroke in strokes:
        points = [(round(x * (page_w - 1)), round(y * (page_h - 1))) for x, y in stroke.points]
        diameter = max(1, round(stroke.width * page_w))
        for array, value in ((colors, stroke.color), (mask, 1)):
            roi = array[:page_h, :page_w]
            cv2.circle(roi, points[0], diameter // 2, value, -1)
            if len(points) > 1:
                cv2.polylines(roi, [np.int32(points)], False, value, diameter)
    model.update_hint(colors, mask)


class Engine:
    """One cached model, owned by one background job at a time."""
    def __init__(self):
        self.key = None
        self.model = None
        self.device_name = ""

    def prepare(self, settings):
        import torch
        upstream = ROOT / ".upstream"
        if not (upstream / "colorizator.py").is_file():
            raise RuntimeError(tr("Отсутствует код модели в папке .upstream. См. README.md."))
        if str(upstream) not in sys.path:
            sys.path.insert(0, str(upstream))
        from colorizator import MangaColorizator
        from networks.models import Colorizer
        from denoising.denoiser import FFDNetDenoiser

        absent = missing_weights(settings)
        if absent:
            raise FileNotFoundError(tr("Укажите папку весов в настройках. Не найдены ") + ", ".join(absent))
        device = settings.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(tr("CUDA недоступна. Выберите «Процессор» в настройках."))
        gen, den = weight_files(settings)
        key = (device, gen, den if settings.denoise else None)
        if key == self.key:
            return
        self.model = self.key = None

        # Keep upstream inference and hint handling. Resolve checkpoints explicitly.
        class LocalColorizer(MangaColorizator):
            def __init__(self):
                self.device = device
                self.colorizer = Colorizer()
                state = torch.load(gen, map_location="cpu", weights_only=True)
                self.colorizer.generator.load_state_dict(state)
                self.colorizer.to(device).eval()
                self.denoiser = FFDNetDenoiser(device, _weights_dir=str(den.parent)) if settings.denoise else None

        self.model = LocalColorizer()
        self.key = key
        self.device_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"

    def predict(self, image, settings, strokes):
        import torch
        gray = image.convert("L")
        with torch.inference_mode():
            # Give the network a consistent grayscale scan for RGB, palette and gray files.
            self.model.set_image(np.asarray(gray.convert("RGB")), settings.size, settings.denoise, settings.sigma)
            apply_strokes(self.model, strokes)
            predicted = self.model.colorize()
        if not np.isfinite(predicted).all():
            raise ValueError(tr("Модель вернула недопустимые значения цвета."))
        return Image.fromarray(np.rint(predicted.clip(0, 1) * 255).astype(np.uint8))
