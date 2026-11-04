"""Chapter state, immutable working versions and publication of a complete export."""
from .i18n import tr
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image

from .color import transfer
from .engine import Settings, Stroke


def settings_dict(settings):
    return {**asdict(settings), "models": str(settings.models)}


def read_settings(values):
    return Settings(**{**values, "models": Path(values["models"])})


def stamp(path):
    try:
        info = path.stat()
        return [info.st_size, info.st_mtime_ns]
    except OSError:
        return []


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_hash(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_file(path, write):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        write(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_manifest(path, document):
    payload = json.dumps(document, ensure_ascii=False, indent=1)
    atomic_file(path, lambda p: p.write_text(payload, encoding="utf-8"))


def strokes_from(values):
    return [Stroke(tuple(s["color"]), s["width"], tuple(tuple(p) for p in s["points"]), s["kind"]) for s in values]


@dataclass
class Page:
    path: Path
    settings: Settings
    uid: str = field(default_factory=lambda: uuid4().hex)
    mode: str = "tint"
    intensity: int = 100
    strokes: list = field(default_factory=list)
    redo: list = field(default_factory=list)
    versions: list = field(default_factory=list)
    selected: int = -1
    view: dict = field(default_factory=dict)
    error: str = ""
    source_stamp: list = field(default_factory=list)
    checksum: str = ""
    trial: dict | None = None
    original_base: bool = False
    version_name: str = ""

    def inspect_source(self):
        current = stamp(self.path)
        if current and current != self.source_stamp:
            self.checksum = ""
        self.source_stamp = current

    def options(self):
        options = {"mode": self.mode, "intensity": self.intensity, "strokes": [asdict(s) for s in self.strokes],
                   "settings": settings_dict(self.settings)}
        if self.original_base:
            options["original_base"] = True
        return options

    def prediction_key(self):
        hints = [asdict(s) for s in self.strokes if s.kind == "hint"]
        inputs = [self.uid, self.checksum or self.source_stamp, settings_dict(self.settings), hints]
        return digest(inputs + ["paper"] if self.original_base else inputs)

    def signature(self):
        return digest([self.checksum or self.source_stamp, self.options()])

    def version(self):
        return self.versions[self.selected] if 0 <= self.selected < len(self.versions) else None

    def apply_options(self, data):
        self.mode, self.intensity = data["mode"], data["intensity"]
        self.settings = read_settings(data["settings"])
        self.original_base = data.get("original_base", False)
        self.strokes = strokes_from(data["strokes"])
        self.redo = []

    def serialize(self):
        return {**self.options(), "uid": self.uid, "path": str(self.path), "versions": self.versions,
                "selected": self.selected, "view": self.view, "error": self.error, "stamp": self.source_stamp,
                "checksum": self.checksum, "trial": self.trial, "version_name": self.version_name}

    @classmethod
    def load(cls, data):
        p = cls(Path(data["path"]), read_settings(data["settings"]), uid=data["uid"])
        if not re.fullmatch(r"[a-f0-9]{32}", p.uid):
            raise ValueError(tr("Недопустимый идентификатор страницы"))
        p.apply_options(data)
        p.versions, p.selected = data["versions"], data["selected"]
        for version in p.versions:
            if not re.fullmatch(r"[a-f0-9]{32}", version["id"]) or not re.fullmatch(r"[a-f0-9]{64}", version["prediction"]):
                raise ValueError(tr("Недопустимый идентификатор версии"))
        p.view, p.error = data["view"], data.get("error", "")
        p.source_stamp, p.checksum = data["stamp"], data.get("checksum", "")
        p.trial, p.version_name = data.get("trial"), data.get("version_name", "")
        p.inspect_source()
        return p


def compose(original, prediction, mode, intensity, strokes):
    gray = np.asarray(original.convert("L"))
    rgb = transfer(gray, prediction, mode, intensity)
    # Work on the selection's bounding box, keeping every pixel outside it unchanged.
    height, width = gray.shape
    for s in strokes:
        if s.kind not in ("paint", "lasso"):
            continue
        pts = np.int32([(round(x*(width-1)), round(y*(height-1))) for x,y in s.points])
        diameter = max(1, round(width*s.width))
        pad = diameter + 1
        left, top = np.maximum(0, pts.min(axis=0)-pad)
        right, bottom = np.minimum((width,height), pts.max(axis=0)+pad+1)
        if right <= left or bottom <= top:
            continue
        region = np.s_[top:bottom,left:right]
        mask = np.zeros(gray[region].shape,np.uint8)
        pts -= (left,top)
        if s.kind == "lasso":
            if len(pts) < 3:
                continue
            cv2.fillPoly(mask,[pts],255)
        else:
            cv2.circle(mask,tuple(pts[0]),diameter//2,255,-1)
            cv2.polylines(mask,[pts],False,255,diameter)
        swatch = np.uint8([[s.color]])
        tinted = transfer(gray[region],swatch,mode,intensity)
        np.copyto(rgb[region],tinted,where=(mask!=0)[:,:,None])
    local = [s for s in strokes if s.kind in ("restore", "erase")]
    if local:
        height, width = gray.shape
        mask = np.zeros_like(gray)
        for stroke in local:
            pts = np.int32([(round(x * (width-1)), round(y * (height-1))) for x, y in stroke.points])
            diameter = max(1, round(width * stroke.width))
            value = 255 if stroke.kind == "restore" else 0
            cv2.circle(mask, tuple(pts[0]), diameter // 2, value, -1)
            if len(pts) > 1:
                cv2.polylines(mask, [pts], False, value, diameter)
        np.copyto(rgb, np.asarray(original), where=(mask != 0)[:, :, None])
    return Image.fromarray(rgb)


def cache_path(project, key):
    return project.parent / "colors" / (key + ".png")


def version_path(project, version):
    return project.parent / "versions" / (version["id"] + ".png")


def make_version(page, project, original, prediction):
    output = compose(original, prediction, page.mode, page.intensity, page.strokes)
    version = {**page.options(), "signature": page.signature(), "prediction": page.prediction_key(),
               "id": uuid4().hex, "name": page.version_name}
    atomic_file(version_path(project, version), lambda path: output.save(path, format="PNG"))
    return version


def export_chapter(folder, pages, notify):
    """Publish only complete numbered chapters. Prior exports keep their names."""
    folder.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=".export-", dir=folder))
    try:
        for i, source in enumerate(pages, 1):
            shutil.copyfile(source, pending / f"{i:04d}.png")
            notify(i)
        number = 1
        while True:
            destination = folder / f"Export {number:03d}"
            if not destination.exists():
                try:
                    pending.rename(destination)
                    return destination
                except OSError:
                    if not destination.exists():
                        raise
            number += 1
    finally:
        if pending.exists():
            shutil.rmtree(pending)
