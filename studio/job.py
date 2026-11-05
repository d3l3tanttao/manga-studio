from .i18n import tr
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from .chapter import atomic_file, cache_path, cached_prediction, compose, export_chapter, make_version, source_hash, stamp
from .engine import open_page, generation_settings


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
        try:
            self.process_pages()
        finally:
            self.engine.release_ai()

    def process_pages(self):
        chapter_anchor = next((Path(p.settings.anchor) for p in self.pages
                               if p.settings.chapter_colors and p.settings.anchor),None)
        for p in self.pages:
            if self.isInterruptionRequested():
                break
            try:
                if not self.preview_only and not p.trial:
                    p.settings = generation_settings(p.settings)
                    p.mode = "generated"
                    p.original_base = False
                    p.intensity = 100
                    p.strokes, p.layers, p.regions = [], [], []
                p.inspect_source()
                image = open_page(p.path)
                if not p.checksum:
                    p.checksum = source_hash(p.path)
                if p.settings.renderer != "legacy":
                    if chapter_anchor and p.settings.chapter_colors:
                        p.settings = replace(p.settings, anchor=str(chapter_anchor), anchor_hash=source_hash(chapter_anchor))
                    for field in ("reference", "anchor", "base"):
                        path = getattr(p.settings,field)
                        if path:
                            if not Path(path).is_file():
                                raise FileNotFoundError(tr("Не найден референс: {0}", path))
                            p.settings = replace(p.settings, **{field+"_hash":source_hash(Path(path))})
                    p.mode = "generated"
                cache = cached_prediction(self.project, p)
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
                        self.engine.cancelled=self.isInterruptionRequested
                        def progress(event):
                            stage = event.get("stage")
                            text = tr("Раскраска")
                            if stage in ("model", "text"):
                                text = tr("Загрузка модели")
                            elif stage == "step":
                                text += f" {event['step']}/{event['total']}"
                            elif stage == "text_detection":
                                text = tr("Защита текста")
                            self.stage.emit(p.uid, text)
                        self.engine.notify = progress
                        pred = self.engine.predict(image, p.settings, [s for s in p.strokes if s.kind == "hint"])
                        if p.settings.renderer != "legacy" and self.isInterruptionRequested():
                            raise InterruptedError()
                    rgb = np.asarray(pred)
                    atomic_file(cache, lambda path: pred.save(path, format="PNG"))
                    if p.settings.renderer != "legacy":
                        atomic_file(cache.with_suffix(".json"), lambda path:path.write_text(
                            json.dumps(self.engine.last_report,ensure_ascii=False,indent=2),encoding="utf-8"))
                self.stage.emit(p.uid, tr("Сохранение"))
                if stamp(p.path) != p.source_stamp:
                    raise OSError(tr("Исходный файл изменился во время обработки. Повторите страницу."))
                if self.preview_only:
                    self.prepared.emit(p.uid,(p.source_stamp,p.checksum))
                    continue
                version = make_version(p, self.project, image, rgb)
                version["prediction"] = cache.stem
                if p.settings.renderer != "legacy":
                    report_path = cache.with_suffix(".json")
                    if report_path.is_file():
                        version["render_report"] = json.loads(report_path.read_text(encoding="utf-8"))
                    if p.settings.chapter_colors and not chapter_anchor and not p.settings.correction:
                        report = version.get("render_report", {})
                        if not report.get("warnings") and report.get("source_edge_coverage", 0) >= .92:
                            chapter_anchor = cache
                self.saved.emit(p.uid, (p.source_stamp, p.checksum, version))
            except InterruptedError:
                break
            except Exception as error:
                msg = str(error)
                if "out of memory" in msg.lower():
                    msg = tr("Недостаточно памяти. Уменьшите размер обработки в настройках.")
                self.failed.emit(p.uid, msg)


class Preview(QThread):
    rendered = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, serial, original, path, mode, intensity, strokes, layers=(), original_base=False):
        super().__init__()
        self.serial, self.args = serial, (original, path, mode, intensity, tuple(strokes), deepcopy(layers), original_base)

    def run(self):
        image, path, mode, intensity, strokes, layers, original_base = self.args
        try:
            if path is None:
                prediction = np.full((1,1,3),255,np.uint8)
            else:
                with Image.open(path) as pred:
                    prediction = np.asarray(pred.convert("RGB"))
            result = compose(image, prediction, mode, intensity, strokes, layers, original_base)
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
