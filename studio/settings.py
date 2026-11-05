from .i18n import tr
from pathlib import Path
from dataclasses import replace
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout)
from .engine import Settings, missing_weights
from .i18n import LANGUAGES


class SettingsDialog(QDialog):
    def __init__(self, current, parent):
        super().__init__(parent)
        self.current = current
        self.setWindowTitle(tr("Настройки обработки"))
        self.setMinimumWidth(530)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        title = QLabel(tr("Настройки модели для главы"))
        title.setObjectName("title")
        layout.addWidget(title)
        form = QFormLayout()
        form.setVerticalSpacing(12)
        layout.addLayout(form)
        self.language = QComboBox()
        self.language.addItem(tr("Автоматически"),"auto")
        for code,name in LANGUAGES.items():
            self.language.addItem(name,code)
        self.language.setCurrentIndex(max(0,self.language.findData(parent.config.value("language","auto"))))
        form.addRow(tr("Язык интерфейса"),self.language)
        form.addRow(tr("Устройство"), QLabel("FLUX · NVIDIA CUDA"))
        self.size = QComboBox()
        for label, pixels in (("0.5 MP",524288),("1 MP",1048576),("1.5 MP",1572864)):
            self.size.addItem(label,pixels)
        self.size.setCurrentIndex(max(0,self.size.findData(current.pixels)))
        form.addRow(tr("Размер для модели"),self.size)
        row = QHBoxLayout()
        self.path = QLineEdit(str(current.models))
        browse = QPushButton(tr("Выбрать"))
        browse.clicked.connect(self.browse)
        row.addWidget(self.path)
        row.addWidget(browse)
        form.addRow(tr("Папка весов"), row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName("muted")
        layout.addWidget(self.note)
        link = QLabel('<a style="color:#c8afff" href="https://huggingface.co/black-forest-labs/FLUX.2-klein-4B">FLUX.2 klein 4B · Black Forest Labs</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        self.path.textChanged.connect(self.check)
        self.buttons = QDialogButtonBox()
        self.buttons.addButton(tr("Сохранить"), QDialogButtonBox.AcceptRole)
        self.buttons.addButton(tr("Отмена"), QDialogButtonBox.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.check()

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, tr("Папка с весами"), self.path.text())
        if path:
            self.path.setText(path)

    def values(self):
        return replace(self.current, renderer="flux", device="cuda", pixels=self.size.currentData(),
                       models=Path(self.path.text()).expanduser().resolve())

    def check(self):
        missing = missing_weights(self.values())
        self.note.setText(tr("Добавьте в выбранную папку ") + ", ".join(missing) if missing
                          else tr("Веса найдены. Готовые PNG сохраняются в разрешении оригинала."))
