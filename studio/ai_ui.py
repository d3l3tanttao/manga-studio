"""Primary source/reference workflow; manual tools remain a separate workspace."""
from dataclasses import replace
from pathlib import Path
import secrets

from PySide6.QtCore import Qt, QTextBoundaryFinder
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox, QLabel, QPlainTextEdit,
                               QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import layout
from .chapter import atomic_file, source_hash, version_path
from .engine import open_page, generation_settings
from .i18n import tr


def wrap_caption(widget,width):
    words = widget.text().split()
    separator = " "
    if len(words)==1 and any("\u3040"<=c<="\u9fff" for c in widget.text()):
        words,separator = list(widget.text()),""
    # Long translations may contain a single word wider than the panel.
    expanded = []
    for word in words:
        finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, word)
        start, chunk = 0, ""
        while (end := finder.toNextBoundary()) >= 0:
            part = word[start:end]
            if chunk and widget.fontMetrics().horizontalAdvance(chunk+part)>width:
                expanded.append(chunk)
                chunk = ""
            chunk += part
            start = end
        expanded.append(chunk)
    words = expanded
    lines = [""]
    for word in words:
        candidate = (lines[-1]+separator+word).strip()
        if lines[-1] and widget.fontMetrics().horizontalAdvance(candidate)>width:
            lines.append(word)
        else:
            lines[-1] = candidate
    widget.setText("\n".join(lines))


class AIWorkspace:
    def build_ai(self):
        self.ai_syncing = False
        self.right.setMinimumWidth(300)
        parent_layout = self.right.layout()
        index = parent_layout.indexOf(self.tabs)
        parent_layout.removeWidget(self.tabs)
        self.ai_stack = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        pane = QVBoxLayout(content)
        pane.setContentsMargins(4,5,4,5)
        self.ai_source = layout.label(tr("Добавьте исходник"), "title")
        self.ai_source.setWordWrap(False)
        self.ai_source.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        pane.addWidget(self.ai_source)
        self.ai_mode = QComboBox()
        for title, code in (("Автоматическая раскраска", "color"), ("Раскраска по референсу", "reference"),
                            ("Перерисовка", "redraw")):
            self.ai_mode.addItem(tr(title), code)
        self.ai_mode.currentIndexChanged.connect(self.ai_changed)
        pane.addWidget(self.ai_mode)
        self.ai_ref_image = QLabel()
        self.ai_ref_image.setAlignment(Qt.AlignCenter)
        self.ai_ref_image.setFixedHeight(110)
        pane.addWidget(self.ai_ref_image)
        self.ai_reference_label = layout.label(tr("Референс необязателен"))
        pane.addWidget(self.ai_reference_label)
        self.ai_reference_btn = layout.button(tr("Добавить референс"), self.choose_ai_reference)
        self.ai_clear_reference = layout.button("×", self.clear_ai_reference, tip=tr("Убрать"))
        self.ai_clear_reference.setAccessibleName(tr("Убрать"))
        self.ai_clear_reference.setFixedWidth(32)
        layout.row(pane, self.ai_reference_btn, self.ai_clear_reference)
        self.ai_role = QComboBox()
        for title, code in (("Манера", "style"), ("Палитра", "palette"), ("Свет", "light"), ("Всё", "all")):
            self.ai_role.addItem(tr(title), code)
        self.ai_role_label = layout.label(tr("Из референса"))
        pane.addWidget(self.ai_role_label)
        pane.addWidget(self.ai_role)
        self.ai_role.currentIndexChanged.connect(self.ai_changed)
        self.ai_fidelity_label = layout.label(tr("Сохранение рисунка"))
        pane.addWidget(self.ai_fidelity_label)
        self.ai_fidelity = QComboBox()
        for title, code in (("Строго", "strict"), ("Сбалансированно", "balanced"), ("Свободно", "creative")):
            self.ai_fidelity.addItem(tr(title), code)
        pane.addWidget(self.ai_fidelity)
        self.ai_fidelity.currentIndexChanged.connect(self.ai_changed)
        self.ai_freedom_label = layout.label(tr("Свобода перерисовки"))
        pane.addWidget(self.ai_freedom_label)
        self.ai_freedom = QSlider(Qt.Horizontal)
        self.ai_freedom.setRange(20,100)
        self.ai_freedom.setValue(100)
        self.ai_freedom.valueChanged.connect(self.ai_changed)
        pane.addWidget(self.ai_freedom)
        self.ai_link = QCheckBox(tr("Единая палитра главы"))

        self.ai_link.setChecked(True)
        self.ai_link.toggled.connect(self.ai_changed)
        pane.addWidget(self.ai_link)
        self.ai_text = QCheckBox(tr("Сохранять текст"))
        self.ai_text.setChecked(True)
        self.ai_text.toggled.connect(self.ai_changed)
        pane.addWidget(self.ai_text)
        self.ai_apply = layout.button(tr("Применить ко всей главе"), self.ai_apply_chapter)
        pane.addWidget(self.ai_apply)
        self.ai_variant = layout.button(tr("Другой вариант"), self.ai_another)
        pane.addWidget(self.ai_variant)
        pane.addWidget(layout.label(tr("Исправления без кисти"), "section"))
        self.ai_correction = QComboBox()
        for title, code in (("Исправить кожу", "skin"), ("Вернуть лицо", "face"), ("Исправить руки", "hands"), ("Границы одежды", "clothes")):
            self.ai_correction.addItem(tr(title), code)
        pane.addWidget(self.ai_correction)
        self.ai_fix = layout.button(tr("Применить"), self.ai_correct)
        pane.addWidget(self.ai_fix)
        self.ai_anchor_label = layout.label("")
        pane.addWidget(self.ai_anchor_label)
        self.ai_remove_anchor = layout.button(tr("Убрать опору"), self.ai_clear_anchor)
        pane.addWidget(self.ai_remove_anchor)
        pane.addWidget(layout.label(tr("РАБОЧИЕ ВЕРСИИ"), "section"))
        # Keep the existing history controller and move its widget into the primary flow.
        pane.addWidget(self.versions)
        self.ai_report = layout.label("")
        pane.addWidget(self.ai_report)
        self.ai_advanced_toggle = QCheckBox(tr("Дополнительные настройки"))
        pane.addWidget(self.ai_advanced_toggle)
        self.ai_advanced = QGroupBox()
        advanced = QVBoxLayout(self.ai_advanced)
        advanced.addWidget(layout.label("FLUX.2 klein 4B"))
        self.ai_paper = QCheckBox(tr("Сохранять белый фон"))
        self.ai_paper.setChecked(True)
        self.ai_paper.toggled.connect(self.ai_changed)
        advanced.addWidget(self.ai_paper)
        self.ai_palette = QPlainTextEdit()
        self.ai_palette.setPlaceholderText(tr("Цвета персонажей"))
        self.ai_palette.setMaximumHeight(70)
        self.ai_palette.setMinimumWidth(0)
        self.ai_palette.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        self.ai_palette.textChanged.connect(self.ai_changed)
        advanced.addWidget(self.ai_palette)
        self.ai_precision = QComboBox()
        for title, code in (("Память: автоматически", "auto"), ("Полное качество", "bf16"), ("Экономия памяти", "nf4")):
            self.ai_precision.addItem(tr(title),code)
        advanced.addWidget(self.ai_precision)
        self.ai_seed = QSpinBox()
        self.ai_seed.setRange(0,2147483647)
        self.ai_seed.setValue(20261105)
        advanced.addWidget(layout.label(tr("Вариант")))
        self.ai_seed.setAccessibleName(tr("Вариант"))
        advanced.addWidget(self.ai_seed)
        self.ai_notes = QPlainTextEdit()
        self.ai_notes.setPlaceholderText(tr("Пожелания к результату (необязательно)"))
        self.ai_notes.setMaximumHeight(70)
        advanced.addWidget(self.ai_notes)
        self.ai_use_anchor = layout.button(tr("Сделать опорой главы"), self.ai_anchor)
        # Allow translated action labels to wrap inside the compact side panel.
        for button,width in ((self.ai_use_anchor,170),(self.ai_apply,200),(self.ai_variant,200),
                             (self.ai_reference_btn,150),(self.ai_remove_anchor,200),(self.ai_fix,200)):
            wrap_caption(button,width)
        advanced.addWidget(self.ai_use_anchor)
        self.ai_advanced.setVisible(False)
        for combo in (self.ai_mode,self.ai_precision,self.ai_role,self.ai_fidelity,self.ai_correction):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.ai_advanced_toggle.toggled.connect(self.ai_advanced.setVisible)
        for combo in (self.ai_precision,):
            combo.currentIndexChanged.connect(self.ai_changed)
        self.ai_seed.valueChanged.connect(self.ai_changed)
        self.ai_notes.textChanged.connect(self.ai_changed)
        self.ai_advanced.setMinimumWidth(0)
        pane.addWidget(self.ai_advanced)
        pane.addStretch()
        self.ai_stack.addWidget(scroll)
        self.ai_stack.addWidget(self.tabs)
        parent_layout.insertWidget(index, self.ai_stack, 1)
        self.ai_manual = QCheckBox(tr("Ручные инструменты"))
        for checkbox in (self.ai_manual,self.ai_link,self.ai_text,self.ai_advanced_toggle,self.ai_paper):
            wrap_caption(checkbox,190)
        self.ai_manual.toggled.connect(self.ai_manual_changed)
        parent_layout.insertWidget(index+1,self.ai_manual)
        self.set_color_btn.hide()
        self.sync_ai()

    def ai_manual_changed(self, checked):
        self.ai_stack.setCurrentIndex(int(checked))
        self.set_color_btn.setVisible(checked)
        self.change_tool()
        self.refresh()

    def sync_ai(self):
        if not hasattr(self,"ai_mode"):
            return
        self.ai_syncing = True
        p = self.current()
        s = p.settings if p else self.settings
        self.ai_source.setText(tr("Оригинал") if p else tr("Добавьте исходник"))
        self.ai_source.setToolTip(p.path.name if p else "")
        self.ai_mode.setCurrentIndex(max(0,self.ai_mode.findData(s.generation)))
        self.ai_fidelity.setCurrentIndex(max(0,self.ai_fidelity.findData(s.fidelity)))
        self.ai_role.setCurrentIndex(max(0,self.ai_role.findData(s.reference_role)))
        self.ai_palette.setPlainText(s.palette_notes)
        self.ai_paper.setChecked(s.protect_paper)
        self.ai_anchor_label.setText(tr("Опора главы: {0}", "✓") if s.anchor else "")
        self.ai_remove_anchor.setVisible(bool(s.anchor))
        self.ai_precision.setCurrentIndex(max(0,self.ai_precision.findData(s.precision)))
        self.ai_freedom.setValue(round(s.freedom*100))
        self.ai_seed.setValue(s.seed)
        self.ai_link.setChecked(s.chapter_colors)
        self.ai_text.setChecked(s.protect_text)
        self.ai_notes.setPlainText(s.notes)
        self.ai_ref_image.clear()
        self.refresh_ai_reference(s)
        redraw = s.generation == "redraw"
        self.ai_fidelity.setVisible(not redraw)
        self.ai_fidelity_label.setVisible(not redraw)
        self.ai_freedom.setVisible(redraw)
        self.ai_freedom_label.setVisible(redraw)
        report = (p.version() or {}).get("render_report",{}) if p else {}
        text = ""
        if report:
            text = tr("Обработка: {0} с", round(report.get("seconds_total",0),1))
            if report.get("warnings"):
                text += "\n" + tr("Проверьте отличия контуров и мелкие детали.")
            if report.get("protected_text_regions",0):
                text += "\n" + tr("Защищено текстовых областей: {0}",report["protected_text_regions"])
        self.ai_report.setText(text)
        self.ai_syncing = False

    def refresh_ai_reference(self,s):
        self.ai_ref_image.clear()
        if s.reference and Path(s.reference).is_file():
            self.ai_ref_image.setPixmap(QPixmap(s.reference).scaled(180,110,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            self.ai_reference_label.setText(tr("Референс добавлен"))
        else:
            self.ai_reference_label.setText(tr("Референс необязателен") if s.generation != "reference" else tr("Добавьте референс"))
        self.ai_ref_image.setVisible(bool(s.reference))
        self.ai_clear_reference.setVisible(bool(s.reference))
        self.ai_role.setVisible(bool(s.reference))
        self.ai_role_label.setVisible(bool(s.reference))

    def ai_changed(self, *_):
        if self.loading or self.ai_syncing or self.worker:
            return
        p = self.current()
        s = p.settings if p else self.settings
        mode = self.ai_mode.currentData()
        reference = s.reference if mode != "color" else ""
        new = replace(generation_settings(s), generation=mode, reference=reference,
                      reference_hash=s.reference_hash if reference else "", precision=self.ai_precision.currentData(),
                      seed=self.ai_seed.value(), freedom=self.ai_freedom.value()/100,
                      chapter_colors=self.ai_link.isChecked(), protect_text=self.ai_text.isChecked(),
                      notes=self.ai_notes.toPlainText()[:500], fidelity=self.ai_fidelity.currentData(),
                      reference_role=self.ai_role.currentData(), protect_paper=self.ai_paper.isChecked(),
                      palette_notes=self.ai_palette.toPlainText()[:400], correction="", base="", base_hash="")
        if p:
            p.settings = new
            p.mode = "generated"
            p.error = ""
        self.settings = new
        self.ai_fidelity.setVisible(mode!="redraw")
        self.ai_fidelity_label.setVisible(mode!="redraw")
        self.ai_freedom.setVisible(mode=="redraw")
        self.ai_freedom_label.setVisible(mode=="redraw")
        self.refresh_ai_reference(new)
        if new.renderer != "legacy" and self.tool.currentData()=="hint":
            self.tool.setCurrentIndex(self.tool.findData("view"))
        self.schedule_save()
        self.refresh()

    def choose_ai_reference(self):
        p = self.current()
        if not p or not self.project or self.worker:
            return
        name, _ = QFileDialog.getOpenFileName(self, tr("Добавить референс"), "", "Images (*.png *.jpg *.jpeg)")
        if name:
            self.set_ai_reference(Path(name))

    def set_ai_reference(self, path):
        p = self.current()
        if not p or not self.project:
            return
        original = open_page(path)
        target = self.project.parent / "references" / (source_hash(path)+".png")
        if not target.exists():
            atomic_file(target, lambda temp:original.save(temp,format="PNG"))
        p.settings = replace(generation_settings(p.settings), correction="", base="", base_hash="", reference=str(target), reference_hash=source_hash(target),
                             generation="redraw" if p.settings.generation=="redraw" else "reference")
        self.settings = p.settings
        self.sync_ai()
        self.schedule_save()
        self.refresh()

    def clear_ai_reference(self):
        p = self.current()
        if p:
            p.settings = replace(generation_settings(p.settings), correction="", base="", base_hash="", reference="", reference_hash="",
                generation="color" if p.settings.generation=="reference" else p.settings.generation)
            self.settings = p.settings
            self.sync_ai(); self.schedule_save(); self.refresh()

    def ai_apply_chapter(self):
        p = self.current()
        if not p or self.worker:
            return
        self.settings = replace(generation_settings(p.settings),correction="",base="",base_hash="")
        for page in self.ordered():
            page.settings = self.settings
            page.mode = "generated"
            page.error = ""
        self.schedule_save(); self.refresh()

    def ai_another(self):
        if self.current() and not self.worker:
            self.ai_seed.setValue(secrets.randbelow(2147483647))
            self.start_selected()

    def ai_anchor(self):
        p = self.current()
        if not p or not p.version() or self.worker:
            return
        source = version_path(self.project,p.version())
        target = self.project.parent/"references"/(source_hash(source)+"-anchor.png")
        atomic_file(target,lambda temp:temp.write_bytes(source.read_bytes()))
        for page in self.ordered():
            if page.uid != p.uid:
                page.settings = replace(page.settings,anchor=str(target),anchor_hash=source_hash(target),chapter_colors=True)
        self.sync_ai(); self.schedule_save(); self.refresh()

    def ai_clear_anchor(self):
        for page in self.ordered():
            page.settings = replace(page.settings,anchor="",anchor_hash="")
        self.sync_ai(); self.schedule_save(); self.refresh()

    def ai_correct(self):
        p = self.current()
        if not p or not p.version() or self.worker or p.trial:
            return
        original = version_path(self.project,p.version())
        target = self.project.parent/"references"/(source_hash(original)+"-edit.png")
        if not target.exists():
            atomic_file(target, lambda temp:temp.write_bytes(original.read_bytes()))
        # Each operation starts from the selected immutable version, never a temporary preview.
        p.settings = replace(generation_settings(p.settings), base=str(target), base_hash=source_hash(target),
                             correction=self.ai_correction.currentData())
        p.mode = "generated"
        self.start([p])

    def refresh_ai(self, editable):
        if not hasattr(self,"ai_mode"):
            return
        for w in (self.ai_mode,self.ai_reference_btn,self.ai_clear_reference,self.ai_link,self.ai_text,
                  self.ai_precision,self.ai_seed,self.ai_notes,self.ai_freedom,self.ai_apply,self.ai_variant,
                  self.ai_role,self.ai_fidelity,self.ai_palette,self.ai_paper,self.ai_remove_anchor,self.ai_correction):
            w.setEnabled(editable)
        p = self.current()
        self.ai_use_anchor.setEnabled(bool(editable and p and p.version()))
        self.ai_variant.setEnabled(bool(editable and p))
        self.ai_fix.setEnabled(bool(editable and p and p.version() and not p.trial))
        self.mode.setEnabled(False)
