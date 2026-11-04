from .i18n import tr
from copy import deepcopy

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from .chapter import atomic_file, cache_path, compose, export_chapter, make_version, source_hash, stamp
from .engine import open_page


class Batch(QThread):
    stage = Signal(str, str)
    ready = Signal(str)
    saved = Signal(str, object)
    prepared = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, engine, pages, project, preview_only=False):
        super().__init__()
        self.engine, self.pages, self.project = engine, deepcopy(pages), project
        self.preview_only = preview_only

    def run(self):
        for p in self.pages:
            if self.isInterruptionRequested():
                break
            try:
                p.inspect_source()
                image = open_page(p.path)
                if not p.checksum:
                    p.checksum = source_hash(p.path)
                cache = cache_path(self.project, p.prediction_key())
                try:
                    with Image.open(cache) as color:
                        rgb = np.array(color.convert("RGB"))
                except (OSError, ValueError):
                    if p.original_base:
                        pred = Image.new("RGB",(1,1),"white")
                    else:
                        self.stage.emit(p.uid, tr("Загрузка модели"))
                        self.engine.prepare(p.settings)
                        self.ready.emit(self.engine.device_name)
                        self.stage.emit(p.uid, tr("Раскраска"))
                        pred = self.engine.predict(image, p.settings, [s for s in p.strokes if s.kind == "hint"])
                    rgb = np.asarray(pred)
                    atomic_file(cache, lambda path: pred.save(path, format="PNG"))
                self.stage.emit(p.uid, tr("Сохранение"))
                if stamp(p.path) != p.source_stamp:
                    raise OSError(tr("Исходный файл изменился во время обработки. Повторите страницу."))
                if self.preview_only:
                    self.prepared.emit(p.uid,(p.source_stamp,p.checksum))
                    continue
                version = make_version(p, self.project, image, rgb)
                self.saved.emit(p.uid, (p.source_stamp, p.checksum, version))
            except Exception as error:
                msg = str(error)
                if "out of memory" in msg.lower():
                    msg = tr("Недостаточно памяти. Уменьшите размер обработки в настройках.")
                self.failed.emit(p.uid, msg)


class Preview(QThread):
    rendered = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, serial, original, path, mode, intensity, strokes):
        super().__init__()
        self.serial, self.args = serial, (original, path, mode, intensity, tuple(strokes))

    def run(self):
        image, path, mode, intensity, strokes = self.args
        try:
            if path is None:
                prediction = np.full((1,1,3),255,np.uint8)
            else:
                with Image.open(path) as pred:
                    prediction = np.asarray(pred.convert("RGB"))
            result = compose(image, prediction, mode, intensity, strokes)
            self.rendered.emit(self.serial, result)
        except Exception as error:
            self.failed.emit(self.serial, str(error))


class Export(QThread):
    progress = Signal(int)
    published = Signal(object)
    failed = Signal(str)

    def __init__(self, folder, sources):
        super().__init__()
        self.folder, self.sources = folder, sources

    def run(self):
        try:
            self.published.emit(export_chapter(self.folder, self.sources, self.progress.emit))
        except Exception as error:
            self.failed.emit(str(error))
