import json
from pathlib import Path
import subprocess
import shutil
from uuid import uuid4

from PIL import Image
from PySide6.QtCore import QLockFile, QPointF, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QColorDialog, QDialog, QDialogButtonBox, QFileDialog, QInputDialog,
                               QLabel, QListWidgetItem, QMainWindow, QMessageBox, QVBoxLayout)

from . import layout
from .chapter import (Page, atomic_file, cache_path, make_version, read_settings, settings_dict,
                      source_hash, stamp, version_path, write_manifest)
from .engine import EXTENSIONS, ROOT, Engine, Settings, missing_weights, open_page, page_order
from .job import Batch, Export, Preview
from .settings import SettingsDialog
from .dialogs import choose_color, text_input
from .i18n import configure, tr, language_code


def pixmap(image):
    data = image.tobytes()
    return QPixmap.fromImage(QImage(data, image.width, image.height, image.width * 3, QImage.Format_RGB888).copy())


class Window(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        self.config = config if config is not None else QSettings(str(ROOT / ".studio-1.2.ini"), QSettings.IniFormat)
        if config is None and not self.config.allKeys():
            old = QSettings(str(ROOT / ".studio.ini"), QSettings.IniFormat)
            for key in old.allKeys():
                self.config.setValue(key,old.value(key))
        configure(self.config.value("language","auto"))
        self.restart_language = False
        self.setWindowTitle(tr("Манга-студия 1.2"))
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("mark.svg"))))
        self.setAcceptDrops(True)
        self.resize(1270, 800)
        self.setMinimumSize(940, 610)
        self.settings = Settings(self.config.value("device", "auto"), self.config.value("size",576,type=int),
                                 self.config.value("denoise",True,type=bool), self.config.value("sigma",25,type=int),
                                 Path(self.config.value("models",str(ROOT / ".models"))))
        self.home = Path(self.config.fileName()).parent / ".chapters"
        self.pages = {}
        self.items = {}
        self.active = self.project = self.lock = None
        self.folder = self.last_export = None
        self.export_files = {}
        self.chapter_name = ""
        self.palette_colors = {}
        self.active_swatch = ""
        self.custom_order = False
        self.loading = self.closing = False
        self.worker = self.preview_job = None
        self.serial = 0
        self.engine = Engine()
        self.original = None
        self.processing = None
        self.save_timer = QTimer(self, singleShot=True, interval=350)
        self.save_timer.timeout.connect(self.persist)
        self.preview_timer = QTimer(self, singleShot=True, interval=35)
        self.preview_timer.timeout.connect(self.start_preview)
        self.thumb_queue = []
        self.thumbs = QTimer(self, interval=15)
        self.thumbs.timeout.connect(self.load_thumbnails)
        layout.build(self)
        self.canvas.color = QColor(self.config.value("brush_color","#287fe8"))
        self.diameter.setValue(self.config.value("brush_diameter",18,type=int))
        self.tabs.currentChanged.connect(self.change_tool)
        self.sync_controls()
        self.refresh()
        if missing_weights(self.settings):
            self.status.setText(tr("Для раскраски укажите папку весов в настройках."))

    def ordered(self):
        return [self.pages[self.list.item(i).data(Qt.UserRole)] for i in range(self.list.count())]

    def current(self):
        return self.pages.get(self.active)

    def remember_view(self):
        p = self.current()
        if p and not self.canvas.original.isNull():
            r = self.canvas.page_rect()
            p.view = {"zoom": self.canvas.zoom, "scale": self.canvas.native_scale, "x": self.canvas.pan.x()/r.width(),
                      "y": self.canvas.pan.y()/r.height(), "split": self.canvas.split,
                      "view": self.view.currentData(), "guides": self.guides.isChecked()}

    def schedule_save(self):
        if self.project and not self.loading:
            self.save_timer.start()

    def persist(self):
        self.save_timer.stop()
        if self.project is None or self.loading:
            return True
        self.remember_view()
        doc = {"format": "manga-studio/1.2", "pages":[p.serialize() for p in self.ordered()],
               "active":self.active, "folder":str(self.folder), "name":self.chapter_name, "palette":self.palette_colors,
               "order_custom":self.custom_order, "settings":settings_dict(self.settings),
               "last_export":str(self.last_export) if self.last_export else None, "export_files":self.export_files}
        try:
            write_manifest(self.project,doc)
        except OSError as error:
            self.status.setText(tr("Автосохранение не удалось: {0}", error))
            return False
        return True

    def acquire(self, path):
        path.parent.mkdir(parents=True,exist_ok=True)
        lock = QLockFile(str(path) + ".lock")
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise OSError(tr("Этот проект уже открыт в другом окне."))
        return lock

    def begin(self, source):
        path = self.home / uuid4().hex / "chapter.json"
        self.lock = self.acquire(path)
        self.project = path
        self.folder = source.parent / tr("Раскраска")
        self.chapter_name = source.parent.name
        self.config.setValue("last_project",str(path))
        self.config.sync()

    def clear_chapter(self):
        if self.worker or not self.persist():
            return False
        self.loading = True
        self.serial += 1
        self.preview_timer.stop()
        self.active = self.project = self.folder = self.last_export = self.original = None
        self.export_files = {}
        self.pages.clear()
        self.items.clear()
        self.list.clear()
        self.thumb_queue.clear()
        self.palette_colors = {}
        self.chapter_name = ""
        self.custom_order = False
        if self.lock:
            self.lock.unlock()
            self.lock = None
        self.loading = False
        self.select_page()
        return True

    def new_project(self):
        if self.clear_chapter():
            self.status.setText(tr("Откройте папку для новой главы."))

    def choose_project(self):
        path,_ = QFileDialog.getOpenFileName(self,tr("Открыть проект"),str(self.home),tr("Проект главы (chapter.json)"))
        if path:
            self.load_project(Path(path))

    def resume(self):
        name = self.config.value("last_project","")
        if name and Path(name).is_file():
            self.load_project(Path(name))
        else:
            self.status.setText(tr("Сохранённый проект не найден. Выберите проект в меню."))

    def load_project(self, path):
        if path == self.project or self.worker:
            return
        lock = None
        try:
            lock = self.acquire(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["format"] not in ("manga-studio/1.1","manga-studio/1.2"):
                raise ValueError(tr("Неподдерживаемый формат проекта."))
            pages = [Page.load(d) for d in data["pages"]]
            settings = read_settings(data["settings"])
            folder = Path(data["folder"])
            if data["format"]=="manga-studio/1.1":
                target = self.home / uuid4().hex / "chapter.json"
                new_lock = self.acquire(target)
                try:
                    for sub in ("colors","versions"):
                        if (path.parent/sub).is_dir():
                            shutil.copytree(path.parent/sub,target.parent/sub)
                    write_manifest(target,{**data,"format":"manga-studio/1.2"})
                except Exception:
                    new_lock.unlock()
                    raise
                lock.unlock()
                lock,path = new_lock,target
            if not self.clear_chapter():
                lock.unlock()
                return
        except (KeyError, ValueError, OSError, TypeError) as error:
            if lock:
                lock.unlock()
            QMessageBox.warning(self,tr("Проект не открыт"),str(error))
            return
        self.loading = True
        self.project,self.lock,self.folder,self.settings = path,lock,folder,settings
        self.chapter_name = data.get("name",folder.parent.name)
        self.palette_colors = data.get("palette",{})
        self.custom_order = data.get("order_custom",False)
        self.last_export = Path(data["last_export"]) if data.get("last_export") else None
        self.export_files = data.get("export_files",{})
        for p in pages:
            self.insert_page(p,self.list.count())
        if pages:
            self.list.setCurrentItem(self.items.get(data.get("active"),self.list.item(0)))
        self.config.setValue("last_project",str(path))
        self.config.sync()
        self.loading = False
        self.select_page()
        self.status.setText(tr("Глава восстановлена."))

    def insert_page(self, page, index):
        item = QListWidgetItem()
        item.setData(Qt.UserRole,page.uid)
        item.setSizeHint(QSize(1,58))
        self.pages[page.uid], self.items[page.uid] = page,item
        self.list.insertItem(index,item)
        self.thumb_queue.append(page.uid)
        self.thumbs.start()

    def load_thumbnails(self):
        from PySide6.QtGui import QImageReader
        for uid in self.thumb_queue[:4]:
            if uid not in self.pages:
                continue
            reader = QImageReader(str(self.pages[uid].path))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(35,49,Qt.KeepAspectRatio))
                image = reader.read()
                if not image.isNull():
                    self.items[uid].setIcon(QIcon(QPixmap.fromImage(image)))
        del self.thumb_queue[:4]
        if not self.thumb_queue:
            self.thumbs.stop()

    def add_paths(self, paths):
        if self.worker:
            return
        seen = {p.path for p in self.pages.values()}
        try:
            for supplied in map(Path, paths):
                entries = supplied.iterdir() if supplied.is_dir() else [supplied]
                incoming = sorted({p.resolve() for p in entries if p.suffix.lower() in EXTENSIONS and p.is_file()}-seen,
                                  key=lambda p:(page_order(p),str(p)))
                if incoming and not self.project:
                    self.begin(incoming[0])
                for path in incoming:
                    seen.add(path)
                    self.insert_page(Page(path,self.settings,source_stamp=stamp(path)),self.list.count())
            if not self.custom_order:
                self.loading = True
                selected = self.active
                self.list.blockSignals(True)
                ordered = sorted(self.pages.values(),key=lambda p:(page_order(p.path),str(p.path)))
                for i,p in enumerate(ordered):
                    old = self.list.row(self.items[p.uid])
                    if old != i:
                        self.list.insertItem(i,self.list.takeItem(old))
                if ordered:
                    self.list.setCurrentItem(self.items[selected or ordered[0].uid])
                self.list.blockSignals(False)
                self.loading = False
        except OSError as error:
            self.status.setText(str(error))
        if self.pages and self.list.currentRow()<0:
            self.list.setCurrentRow(0)
        if self.list.currentItem() and self.list.currentItem().data(Qt.UserRole) != self.active:
            self.select_page()
        self.refresh()
        self.schedule_save()

    def open_files(self):
        if self.worker:
            return
        paths,_ = QFileDialog.getOpenFileNames(self,tr("Добавить страницы"),self.config.value("last_import",""),
                                              tr("Страницы (*.png *.jpg *.jpeg)"))
        if paths:
            self.config.setValue("last_import",str(Path(paths[0]).parent))
            self.add_paths(paths)

    def open_folder(self):
        if self.worker:
            return
        path = QFileDialog.getExistingDirectory(self,tr("Добавить главу"),self.config.value("last_import",""))
        if path:
            self.config.setValue("last_import",path)
            self.add_paths([path])

    def dragEnterEvent(self,event):
        if not self.worker and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self,event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()

    def move_page(self,delta):
        i = self.list.currentRow()
        if not self.worker and 0 <= i+delta < self.list.count():
            self.list.blockSignals(True)
            item = self.list.takeItem(i)
            self.list.insertItem(i+delta,item)
            self.list.setCurrentItem(item)
            self.list.blockSignals(False)
            self.custom_order = True
            self.refresh()
            self.schedule_save()

    def navigate(self,delta):
        self.list.setCurrentRow(max(0,min(self.list.count()-1,self.list.currentRow()+delta)))

    def remove_page(self):
        p = self.current()
        if p and not self.worker:
            self.active = None
            del self.pages[p.uid], self.items[p.uid]
            self.list.takeItem(self.list.currentRow())
            self.select_page()
            self.schedule_save()

    def example(self):
        src = Path(__file__).with_name("assets") / "jacket.png"
        try:
            if self.pages:
                return
            self.add_paths([src])
            p = self.current()
            if not p:
                raise FileNotFoundError(src)
            # The bundled example was generated at the baseline settings.
            p.settings = Settings(models=self.settings.models)
            p.checksum = source_hash(p.path)
            self.folder = self.home.parent / "exports" / "Demo"
            with Image.open(src.with_name("jacket-color.png")) as image:
                import numpy as np
                pred = image.convert("RGB")
                atomic_file(cache_path(self.project,p.prediction_key()),lambda path:pred.save(path,format="PNG"))
                p.versions.append(make_version(p,self.project,self.original,np.asarray(pred)))
            p.selected = 0
            self.select_page()
            self.persist()
            self.status.setText(tr("Пример готов. Сравните два режима цвета или откройте вкладку «Правка»."))
        except OSError as error:
            self.status.setText(str(error))

    def select_page(self,*args):
        if self.loading:
            return
        self.remember_view()
        item = self.list.currentItem()
        self.active = item.data(Qt.UserRole) if item else None
        p = self.current()
        self.original = None
        self.serial += 1
        self.preview_timer.stop()
        original,result = QPixmap(),QPixmap()
        self.canvas.error = ""
        if p:
            try:
                p.inspect_source()
                self.original = open_page(p.path)
                original = pixmap(self.original)
                v = p.version()
                if v and version_path(self.project,v).is_file():
                    with Image.open(version_path(self.project,v)) as saved:
                        result = pixmap(saved.convert("RGB"))
            except (OSError,ValueError) as error:
                p.error = str(error) if p.path.is_file() else tr("Исходник перемещён. Нажмите «Найти исходники».")
                self.canvas.error = p.error
        self.loading = True
        self.canvas.load_page(original,result,p.strokes if p else [])
        self.canvas.before = QPixmap()
        if p and p.trial:
            path = self.project.parent/"trials"/(p.uid+".png")
            if path.is_file():
                self.canvas.before = QPixmap(str(path))
        view = p.view if p else {}
        self.canvas.zoom = view.get("zoom",1)
        self.canvas.native_scale = view.get("scale")
        rect = self.canvas.page_rect()
        self.canvas.pan = QPointF(view.get("x",0)*rect.width(),view.get("y",0)*rect.height())
        self.canvas.split = view.get("split",0.5)
        view_mode = view.get("view","compare")
        if view_mode == "previous" and not (p and p.trial):
            view_mode = "result"
        self.view.setCurrentIndex(max(0,self.view.findData(view_mode)))
        self.guides.setChecked(view.get("guides",True))
        self.canvas.view,self.canvas.guides = self.view.currentData(),self.guides.isChecked()
        self.canvas.report_scale()
        self.loading = False
        self.sync_controls()
        if p and self.original is not None and not self.is_saved(p):
            self.request_preview()
        self.refresh()
        self.schedule_save()

    def is_saved(self,p):
        v = p.version()
        return bool(not p.trial and v and p.source_stamp and v["signature"] == p.signature() and version_path(self.project,v).is_file())

    def has_color(self,p):
        return bool(self.project and cache_path(self.project,p.prediction_key()).is_file())

    def state(self,p):
        if self.processing == p.uid:
            return tr("◉  Обработка")
        if p.error:
            return tr("⚠  Ошибка")
        if p.trial:
            return tr("Проба цвета")
        if self.is_saved(p):
            return tr("✓  Сохранено")
        if self.has_color(p):
            return tr("●  Есть правки")
        return tr("↻  Нужен пересчёт") if p.version() or p.strokes else tr("○  В очереди")

    def sync_controls(self):
        p = self.current()
        self.loading = True
        self.mode.setCurrentIndex(self.mode.findData(p.mode if p else "tint"))
        self.strength.setValue(p.intensity if p else 100)
        self.strength_label.setText(tr("Интенсивность · {0}%", self.strength.value()))
        self.versions.clear()
        if p:
            for i,v in enumerate(p.versions,1):
                title = v.get("name") or tr("Версия {0}", i)
                self.versions.addItem(f"{title} · {v['intensity']}%")
            self.versions.setCurrentIndex(p.selected)
        self.palette_box.clear()
        for name,value in self.palette_colors.items():
            square = QPixmap(16,16)
            square.fill(QColor(value))
            item = QListWidgetItem(QIcon(square),name)
            item.setData(Qt.UserRole,value)
            self.palette_box.addItem(item)
            if value == self.canvas.color.name() and (name==self.active_swatch or not self.active_swatch):
                self.palette_box.setCurrentItem(item)
        self.hex_box.setText(self.canvas.color.name().upper())
        chip = QPixmap(18,18)
        chip.fill(self.canvas.color)
        self.swatch.setText(tr("Выбрать цвет"))
        self.swatch.setIcon(QIcon(chip))
        self.set_color_btn.setIcon(QIcon(chip))
        self.loading = False

    def refresh(self):
        p = self.current()
        free = self.worker is None
        editable = bool(p and self.original is not None and free)
        pages = self.ordered()
        self.count.setText(tr("Страницы · {0}", len(pages)))
        self.stack.setCurrentIndex(int(p is not None))
        self.title.setText(p.path.name if p else tr("Мастерская"))
        for i,page in enumerate(pages,1):
            item = self.items[page.uid]
            item.setText(f"{i:02d}  {page.path.name}\n{self.state(page)}")
            item.setToolTip(page.error or str(page.path))
        pending = sum(bool(not page.trial and (page.error or not self.is_saved(page))) for page in pages)
        self.run_btn.setText(tr("Обработать очередь · {0}", pending))
        self.run_btn.setEnabled(free and pending>0)
        self.one_btn.setText(tr("Сохранить версию") if p and self.has_color(p) else tr("Раскрасить страницу"))
        self.one_btn.setEnabled(bool(free and p and (p.error or not self.is_saved(p))))
        trial = bool(p and p.trial)
        self.discard_btn.setVisible(trial)
        self.discard_btn.setEnabled(free)
        if trial:
            if self.has_color(p) or p.original_base:
                self.one_btn.setText(tr("Принять версию"))
                self.one_btn.setEnabled(free and self.preview_job is None and not self.preview_timer.isActive())
            else:
                accepted = p.version() or {}
                old_hints = [s for s in accepted.get("strokes",[]) if s["kind"]=="hint"]
                hints = [s for s in p.strokes if s.kind=="hint"]
                n = max(1,len(hints)-len(old_hints))
                self.one_btn.setText(tr("Применить подсказки · {0}", n))
        self.set_color_btn.setEnabled(editable)
        self.color_note.setText(tr("Отметьте область на странице.") if self.canvas.tool!="view" else tr("Выберите оттенок и отметьте место."))
        self.hex_box.setEnabled(editable)
        self.view.model().item(3).setEnabled(bool(p and p.trial))
        self.export_btn.setEnabled(bool(free and pages))
        self.stop_btn.setVisible(isinstance(self.worker,Batch))
        self.progress.setVisible(not free)
        self.continue_btn.setVisible(Path(self.config.value("last_project","") or "__missing__").is_file())
        self.state_label.setText(self.state(p) if p else tr("Выберите страницу"))
        problem = p.error if p else ""
        if p and p.version() and not p.original_base and not self.has_color(p) and not self.is_saved(p) and not problem:
            problem = tr("На холсте предыдущий цвет. Пересчитайте страницу, чтобы применить подсказки и параметры модели.")
        self.issue.setText(problem)
        self.issue.setVisible(bool(problem))
        self.destination.setText(f"{self.chapter_name}\n{self.folder}" if self.folder else tr("Выберите главу"))
        for b in (self.files,self.folder_btn,self.project_menu,self.settings_btn):
            b.setEnabled(free)
        for b in (self.mode,self.strength,self.all_btn,self.tool,self.diameter,self.swatch,self.palette_add):
            b.setEnabled(editable)
        self.versions.setEnabled(bool(free and p and p.versions and not trial))
        self.palette_box.setEnabled(editable and bool(self.palette_colors))
        self.undo_btn.setEnabled(editable and bool(p.strokes))
        self.redo_btn.setEnabled(editable and bool(p.redo))
        self.remove_btn.setEnabled(bool(free and p))
        self.up.setEnabled(free and self.list.currentRow()>0)
        self.down.setEnabled(free and 0<=self.list.currentRow()<len(pages)-1)
        self.dest_btn.setEnabled(bool(free and self.project))
        self.reveal.setEnabled(bool(p and p.version()))
        self.open_result.setEnabled(bool(self.last_export and self.last_export.is_dir()))
        self.retry.setEnabled(bool(free and any(page.error for page in pages)))
        self.relink_btn.setEnabled(bool(free and self.project))
        self.view.setEnabled(bool(p and not self.canvas.result.isNull()))
        self.guides.setEnabled(self.view.isEnabled() and self.view.currentData() in ("compare","previous"))
        for b in (self.fit_btn,self.minus,self.plus,self.percent):
            b.setEnabled(self.original is not None)

    def change_view(self,*args):
        if self.loading:
            return
        self.canvas.view,self.canvas.guides = self.view.currentData(),self.guides.isChecked()
        if self.canvas.view in ("compare","previous") and self.tool.currentData()!="view":
            self.tool.setCurrentIndex(self.tool.findData("view"))
        self.canvas.update()
        self.refresh()
        self.schedule_save()

    def fit(self):
        self.canvas.fit()
        self.schedule_save()

    def request_preview(self):
        self.serial += 1
        self.preview_timer.start()

    def start_preview(self):
        p = self.current()
        if self.preview_job or not p or self.original is None or self.closing:
            return
        key = p.prediction_key()
        if not self.has_color(p) and not p.original_base:
            if not p.version():
                return
            key = p.version()["prediction"]
        cache = cache_path(self.project,key)
        if p.original_base and not cache.is_file():
            cache = None
        elif not cache.is_file():
            return
        job = Preview(self.serial,self.original,cache,p.mode,p.intensity,p.strokes)
        self.preview_job = job
        job.rendered.connect(self.accept_preview)
        job.failed.connect(self.preview_failed)
        job.finished.connect(self.finish_preview)
        job.start()

    def accept_preview(self,serial,image):
        if serial == self.serial and not self.closing:
            self.canvas.result = pixmap(image)
            self.canvas.update()
            self.refresh()

    def preview_failed(self,serial,message):
        if serial == self.serial:
            self.status.setText(tr("Предпросмотр недоступен: {0}", message))

    def finish_preview(self):
        job = self.preview_job
        self.preview_job = None
        if job:
            job.deleteLater()
            if job.serial != self.serial and not self.closing:
                self.preview_timer.start()
        if self.closing and not self.worker:
            self.close()
        else:
            self.refresh()

    def changed(self,preview=True):
        if preview:
            self.request_preview()
        self.refresh()
        self.schedule_save()

    def color_changed(self,*args):
        p = self.current()
        if self.loading or self.worker or not p:
            return
        p.mode,p.intensity = self.mode.currentData(),self.strength.value()
        self.strength_label.setText(tr("Интенсивность · {0}%", p.intensity))
        self.changed()

    def apply_all(self):
        current = self.current()
        if current and not self.worker:
            for p in self.pages.values():
                p.mode,p.intensity = current.mode,current.intensity
            self.changed()
            self.status.setText(tr("Режим и интенсивность применены ко всей главе."))

    def choose_version(self,i):
        p = self.current()
        if p and 0<=i<len(p.versions):
            p.selected = i
            p.apply_options(p.versions[i])
            self.select_page()

    def change_tool(self,*args):
        self.canvas.tool = self.tool.currentData() if self.tabs.currentIndex()==1 and not self.worker else "view"
        self.canvas.setCursor(Qt.CrossCursor if self.canvas.tool!="view" else Qt.OpenHandCursor)
        self.canvas.current = []
        self.canvas.sample_source = self.sample_from.currentData()
        if self.canvas.tool != "view":
            view = self.canvas.sample_source if self.canvas.tool=="pick" else "result"
            self.view.setCurrentIndex(self.view.findData(view))
        self.canvas.update()

    def brush_size(self,value):
        self.canvas.diameter = value
        self.config.setValue("brush_diameter",value)
        self.canvas.update()

    def pick_color(self,color):
        self.sample_color(color)
        if self.tool.currentData() not in ("hint","paint","lasso"):
            self.tool.setCurrentIndex(self.tool.findData("hint"))

    def sample_color(self,color):
        self.canvas.color = color
        if self.palette_colors.get(self.active_swatch) != color.name():
            self.active_swatch = next((n for n,c in self.palette_colors.items() if c==color.name()),"")
        self.config.setValue("brush_color",color.name())
        self.sync_controls()
        self.refresh()

    def assign_color(self):
        self.right.show()
        self.tabs.setCurrentIndex(1)
        if self.tool.currentData() not in ("hint","paint","lasso"):
            self.tool.setCurrentIndex(self.tool.findData("hint"))
        self.hex_box.setFocus()
        self.hex_box.selectAll()
        self.refresh()

    def select_swatch(self,code):
        self.pick_color(QColor(code))

    def hex_changed(self):
        value = "#"+self.hex_box.text().strip().lstrip("#")
        if len(value)==7 and QColor(value).isValid():
            if value.lower()!=self.canvas.color.name():
                self.select_swatch(value)
        else:
            self.hex_box.setText(self.canvas.color.name().upper())
            self.status.setText(tr("Введите шесть шестнадцатеричных цифр."))

    def toggle_marks(self,enabled):
        self.canvas.show_marks = enabled
        self.canvas.update()

    def custom_color(self):
        color = choose_color(self,self.canvas.color)
        if color.isValid():
            self.pick_color(color)

    def name_color(self):
        name,ok = text_input(self,tr("Палитра главы"),tr("Название оттенка"))
        if ok and name.strip():
            self.palette_colors[name.strip()] = self.canvas.color.name()
            self.active_swatch = name.strip()
            self.sync_controls()
            self.palette_box.setCurrentRow(list(self.palette_colors).index(name.strip()))
            self.changed(False)

    def use_palette(self,i):
        if i >= 0:
            item = self.palette_box.item(i)
            name,value = item.text(),item.data(Qt.UserRole)
            self.active_swatch = name
            self.pick_color(QColor(value))
            self.palette_box.setCurrentRow(list(self.palette_colors).index(name))

    def rename_color(self):
        item = self.palette_box.currentItem()
        if item and not self.worker:
            old = item.text()
            new,ok = text_input(self,tr("Переименовать"),tr("Название оттенка"),text=old)
            if ok and new.strip() and new.strip() not in self.palette_colors:
                self.palette_colors[new.strip()] = self.palette_colors.pop(old)
                self.active_swatch = new.strip()
                self.sync_controls()
                self.schedule_save()

    def delete_color(self):
        item = self.palette_box.currentItem()
        if item and not self.worker:
            self.palette_colors.pop(item.text(),None)
            self.sync_controls()
            self.schedule_save()

    def begin_trial(self,p):
        if p.trial:
            return
        before = self.canvas.result if not self.canvas.result.isNull() else self.canvas.original
        self.canvas.before = before.copy()
        path = self.project.parent/"trials"/(p.uid+".png")
        atomic_file(path,lambda dest:Image.fromqpixmap(before).save(dest,format="PNG"))
        p.trial = {"options":p.options(),"selected":p.selected,"name":p.version_name}

    def discard_trial(self):
        p=self.current()
        if p and p.trial and not self.worker:
            p.apply_options(p.trial["options"])
            p.selected,p.version_name = p.trial["selected"],p.trial["name"]
            p.trial = None
            p.error = ""
            self.marks.setChecked(False)
            self.view.setCurrentIndex(self.view.findData("result"))
            self.select_page()
            self.persist()

    def add_stroke(self,s):
        p = self.current()
        if p and not self.worker:
            self.begin_trial(p)
            if s.kind == "hint":
                p.original_base = False
                self.marks.setChecked(True)
            elif not p.version() and not self.has_color(p) and not any(stroke.kind=="hint" for stroke in p.strokes):
                p.original_base = True
            name = self.active_swatch if self.palette_colors.get(self.active_swatch)==self.canvas.color.name() else self.canvas.color.name()
            if s.kind=="hint":
                n = sum(stroke.kind=="hint" for stroke in p.strokes)+1
                p.version_name = f"{name} · AI ×{n}"
            else:
                p.version_name = name
            p.strokes.append(s)
            p.redo.clear()
            self.canvas.update()
            self.changed(s.kind!="hint")
            if s.kind!="hint":
                self.status.setText(tr("Проба готова. Сравните и примите или отмените."))

    def undo(self):
        p = self.current()
        if p and p.strokes and not self.worker:
            self.begin_trial(p)
            p.redo.append(p.strokes.pop())
            self.canvas.update()
            self.changed()

    def redo(self):
        p = self.current()
        if p and p.redo and not self.worker:
            self.begin_trial(p)
            p.strokes.append(p.redo.pop())
            self.canvas.update()
            self.changed()

    def edit_settings(self):
        initial = self.current().settings if self.current() else self.settings
        dialog = SettingsDialog(initial,self)
        if dialog.exec():
            language = dialog.language.currentData()
            previous = self.config.value("language","auto")
            self.config.setValue("language",language)
            new_settings = dialog.values()
            if new_settings != initial:
                self.settings = new_settings
                for k,val in settings_dict(self.settings).items():
                    self.config.setValue(k,val)
                for p in self.pages.values():
                    p.settings = self.settings
            self.config.sync()
            self.changed()
            if language != previous:
                self.restart_language = True
                self.close()
        dialog.deleteLater()

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("О программе и авторах"))
        lay = QVBoxLayout(dialog)
        for role, who in ((tr("Направление проекта"),"d3l3tanttao"),
                          (tr("Разработка приложения, интерфейса и тестов"),"OpenAI Codex"),
                          (tr("Движок раскраски"),"qweasdd / manga-colorization-v2"),
                          (tr("Шумоподавление"),"Matias Tassano / FFDNet")):
            lay.addWidget(layout.label(role+" · "+who))
        lay.addWidget(layout.label(tr("Полный список компонентов см. в CREDITS.md.")))
        lay.addWidget(layout.button(tr("Закрыть"),dialog.accept))
        dialog.exec()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self,tr("Папка назначения"),str(self.folder or ROOT))
        if path:
            self.folder = Path(path)
            self.changed(False)

    def show_file(self):
        p = self.current()
        if p and p.version():
            path = version_path(self.project,p.version())
            exported = self.export_files.get(p.uid)
            if self.last_export and exported and exported["version"] == p.version()["id"]:
                final = self.last_export / f"{int(exported['number']):04d}.png"
                if final.is_file():
                    path = final
            if path.is_file():
                subprocess.Popen(f'explorer.exe /select,"{path}"')
            else:
                self.status.setText(tr("Файл версии перемещён. Сохраните страницу заново."))

    def open_export(self):
        if self.last_export:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_export)))

    def relink_dialog(self):
        folder = QFileDialog.getExistingDirectory(self,tr("Новое расположение исходников"))
        if folder:
            try:
                self.relink(Path(folder))
            except OSError as error:
                self.status.setText(tr("Не удалось прочитать исходники: {0}", error))

    def relink(self,folder):
        missing = [p for p in self.pages.values() if not p.path.is_file()]
        by_name = {}
        for path in folder.rglob("*"):
            if path.suffix.lower() in EXTENSIONS and path.is_file():
                by_name.setdefault(path.name.casefold(),[]).append(path)
        used = {p.path for p in self.pages.values() if p.path.is_file()}
        count = 0
        for p in missing:
            candidates = by_name.get(p.path.name.casefold(),[])
            candidates = [candidate for candidate in candidates if candidate not in used]
            if p.checksum:
                candidates = [candidate for candidate in candidates if source_hash(candidate) == p.checksum]
            if len(candidates)==1:
                p.path = candidates[0]
                used.add(p.path)
                p.source_stamp = stamp(p.path)
                p.error = ""
                self.thumb_queue.append(p.uid)
                count += 1
        self.thumbs.start()
        self.select_page()
        self.status.setText(tr("Найдено исходников: {0} из {1}.", count, len(missing)))
        self.persist()

    def start_pending(self):
        self.start([p for p in self.ordered() if not p.trial and (p.error or not self.is_saved(p))])

    def retry_errors(self):
        self.start([p for p in self.ordered() if p.error and not p.trial])

    def start_selected(self):
        if self.current():
            p = self.current()
            prepare = p.trial and not p.original_base and not self.has_color(p)
            self.start([p],bool(prepare))

    def start(self,pages,preview_only=False):
        if self.worker or not pages:
            return
        if any(not p.original_base and not self.has_color(p) and missing_weights(p.settings) for p in pages):
            self.edit_settings()
            if any(not p.original_base and not self.has_color(p) and missing_weights(p.settings) for p in pages):
                return
        self.worker = Batch(self.engine,pages,self.project,preview_only)
        self.done = self.errors = 0
        self.stopping = False
        self.worker.stage.connect(self.on_stage)
        self.worker.ready.connect(self.device.setText)
        self.worker.saved.connect(self.on_saved)
        self.worker.prepared.connect(self.on_prepared)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.finish_work)
        self.progress.setRange(0,len(pages))
        self.progress.setValue(0)
        self.stop_btn.setEnabled(True)
        self.change_tool()
        self.refresh()
        self.worker.start()

    def on_stage(self,uid,stage):
        self.processing = uid
        self.status.setText(tr("{0} · {1} · {2} из {3}", stage, self.pages[uid].path.name, self.done + self.errors + 1, len(self.worker.pages)))
        self.refresh()

    def on_saved(self,uid,payload):
        p = self.pages[uid]
        p.source_stamp,p.checksum,version = payload
        p.trial = None
        p.versions.append(version)
        p.selected = len(p.versions)-1
        p.error = ""
        self.done += 1
        self.processing = None
        self.progress.setValue(self.done+self.errors)
        if uid == self.active:
            self.select_page()
        self.persist()

    def on_prepared(self,uid,payload):
        p = self.pages[uid]
        p.source_stamp,p.checksum = payload
        p.error = ""
        self.done += 1
        self.processing = None
        if uid == self.active:
            self.marks.setChecked(False)
            self.tool.setCurrentIndex(self.tool.findData("view"))
            self.view.setCurrentIndex(self.view.findData("previous"))
            self.request_preview()
        self.persist()

    def on_failed(self,uid,message):
        self.pages[uid].error = message
        self.errors += 1
        self.processing = None
        self.progress.setValue(self.done+self.errors)
        self.refresh()
        self.persist()

    def finish_work(self):
        job = self.worker
        self.worker = self.processing = None
        if isinstance(job,Batch):
            prefix = tr("Очередь остановлена. ") if self.stopping else ""
            self.status.setText(tr("{0}Сохранено: {1}. Ошибок: {2}.", prefix, self.done, self.errors))
            if job.preview_only and not self.errors:
                self.status.setText(tr("Проба готова. Сравните и примите или отмените."))
        job.deleteLater()
        self.change_tool()
        self.refresh()
        if self.closing and not self.preview_job:
            self.close()

    def stop(self):
        if isinstance(self.worker,Batch):
            self.worker.requestInterruption()
            self.stop_btn.setEnabled(False)
            self.stopping = True
            self.status.setText(tr("Остановка после текущей страницы…"))

    def review_export(self):
        pages = self.ordered()
        for p in pages:
            p.inspect_source()
        unfinished = [p for p in pages if p.error or not self.is_saved(p)]
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Экспорт главы"))
        lay = QVBoxLayout(dialog)
        lay.addWidget(layout.label(tr("Готово {0} из {1}", len(pages) - len(unfinished), len(pages)),"title"))
        lay.addWidget(layout.label(tr("Папка назначения\n{0}\n\nPNG будут пронумерованы по списку страниц.", self.folder)))
        box = QDialogButtonBox()
        primary = box.addButton(tr("Перейти к незавершённой") if unfinished else tr("Экспортировать PNG"),QDialogButtonBox.AcceptRole)
        primary.setObjectName("primary")
        box.addButton(tr("Отмена"),QDialogButtonBox.RejectRole)
        box.accepted.connect(dialog.accept)
        box.rejected.connect(dialog.reject)
        lay.addWidget(box)
        approved = dialog.exec()
        dialog.deleteLater()
        if not approved:
            return
        if unfinished:
            self.list.setCurrentItem(self.items[unfinished[0].uid])
            self.refresh()
            self.status.setText(tr("Обработайте оставшиеся страницы и повторите экспорт."))
        else:
            self.worker = Export(self.folder,[version_path(self.project,p.version()) for p in pages])
            self.progress.setRange(0,len(pages))
            self.progress.setValue(0)
            self.worker.progress.connect(self.progress.setValue)
            self.worker.published.connect(self.exported)
            self.worker.failed.connect(lambda message:self.status.setText(tr("Ошибка экспорта: ")+message))
            self.worker.finished.connect(self.finish_work)
            self.status.setText(tr("Сохранение финальных PNG…"))
            self.change_tool()
            self.refresh()
            self.worker.start()

    def exported(self,folder):
        self.last_export = folder
        self.export_files = {p.uid: {"version": p.version()["id"], "number": i}
                             for i,p in enumerate(self.ordered(),1)}
        self.status.setText(tr("Экспортировано PNG: {0} · {1}", len(self.pages), folder))
        self.tabs.setCurrentIndex(2)
        self.persist()

    def closeEvent(self,event):
        if self.worker or self.preview_job:
            self.closing = True
            self.preview_timer.stop()
            self.stop()
            event.ignore()
        elif self.persist():
            if self.lock:
                self.lock.unlock()
                self.lock = None
            event.accept()
        else:
            self.closing = False
            event.ignore()
            QMessageBox.warning(self,tr("Проект не сохранён"),self.status.text())
