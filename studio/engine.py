from .i18n import tr
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(os.environ.get("MANGA_STUDIO_HOME", Path(__file__).resolve().parents[1])).resolve()
EXTENSIONS = {".jpg", ".jpeg", ".png"}
MODES = {"tint": "Цвет по оригиналу", "luma": "Яркость оригинала", "balanced": "Цвет и свет", "generated": "Результат ИИ"}


@dataclass(frozen=True)
class Settings:
    device: str = "auto"
    size: int = 576
    denoise: bool = True
    sigma: int = 25
    models: Path = ROOT / ".models"
    pipeline: str = "adaptive"
    quality: str = "standard"
    renderer: str = "flux"
    generation: str = "color"
    reference: str = ""
    reference_hash: str = ""
    anchor: str = ""
    anchor_hash: str = ""
    seed: int = 20261105
    precision: str = "auto"
    freedom: float = 1.0
    pixels: int = 1048576
    notes: str = ""
    protect_text: bool = True
    chapter_colors: bool = True
    fidelity: str = "strict"
    reference_role: str = "style"
    correction: str = ""
    base: str = ""
    base_hash: str = ""
    palette_notes: str = ""
    protect_paper: bool = True


def generation_settings(settings):
    """Upgrade only a new processing request; never rewrite a historical version."""
    models = settings.models if settings.models.is_dir() else ROOT/".models"
    return replace(settings, renderer="flux", device="cuda", models=models)


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


def missing_weights(settings):
    files = ["flux2-klein-4b/PROVENANCE.json", "flux2-klein-4b/model_index.json",
             "flux2-klein-4b/transformer/diffusion_pytorch_model.safetensors",
             "flux2-klein-4b/vae/diffusion_pytorch_model.safetensors"]
    encoder = settings.models / "flux2-klein-4b/text_encoder"
    missing = [name for name in files if not (settings.models/name).is_file()]
    if not list(encoder.glob("*.safetensors")):
        missing.append("flux2-klein-4b/text_encoder")
    if settings.protect_text and not (settings.models/"ocr/craft_mlt_25k.pth").is_file():
        missing.append("ocr/craft_mlt_25k.pth")
    if settings.correction in ("face","hands") and not (settings.models/"florence2-base/model.safetensors").is_file():
        missing.append("florence2-base/model.safetensors")
    return missing


class Engine:
    """Only FLUX can process new images. Historical RGB caches need no model."""
    def __init__(self):
        self.device_name = ""
        self.cancelled = lambda: False
        self.notify = lambda event: None
        self.ai = None
        self.last_report = {}

    def prepare(self, settings):
        from .ai_client import AIClient
        if self.ai is None:
            self.ai = AIClient(ROOT)
        self.device_name = "FLUX · CUDA"

    def predict(self, image, settings, strokes=()):
        result = self.ai.generate(image, generation_settings(settings), self.cancelled, self.notify)
        self.last_report = self.ai.last_report
        return result

    def release_ai(self):
        if self.ai:
            self.ai.close()
