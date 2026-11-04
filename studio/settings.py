from .i18n import tr
from pathlib import Path
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout)
from .engine import Settings, missing_weights
from .i18n import LANGUAGES


class SettingsDialog(QDialog):
    def __init__(self, current, parent):
        super().__init__(parent)
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
        self.device = QComboBox()
        for key, label in (("auto", tr("Авто · CUDA или CPU")), ("cuda", tr("Видеокарта NVIDIA")), ("cpu", tr("Процессор"))):
            self.device.addItem(label, key)
        self.device.setCurrentIndex(max(0, self.device.findData(current.device)))
        form.addRow(tr("Устройство"), self.device)
        self.size = QComboBox()
        for n in (384, 576, 768, 1024):
            self.size.addItem(tr("{0} пикс.", n), n)
        self.size.setCurrentIndex(max(0, self.size.findData(current.size)))
        form.addRow(tr("Размер для модели"), self.size)
        self.denoise = QCheckBox(tr("Убирать шум перед раскраской"))
        self.denoise.setChecked(current.denoise)
        form.addRow("", self.denoise)
        self.sigma = QSpinBox()
        self.sigma.setRange(1, 75)
        self.sigma.setValue(current.sigma)
        self.sigma.setEnabled(current.denoise)
        self.denoise.toggled.connect(self.sigma.setEnabled)
        form.addRow(tr("Сила шумоподавления"), self.sigma)
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
        caption = tr("Скачать веса со страницы автора")
        link = QLabel(f'<a style="color:#c8afff" href="https://github.com/qweasdd/manga-colorization-v2#automatic-colorization">{caption}</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        self.path.textChanged.connect(self.check)
        self.denoise.toggled.connect(self.check)
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
        return Settings(self.device.currentData(), self.size.currentData(), self.denoise.isChecked(),
                        self.sigma.value(), Path(self.path.text()).expanduser().resolve())

    def check(self):
        missing = missing_weights(self.values())
        self.note.setText(tr("Добавьте в выбранную папку ") + ", ".join(missing) if missing
                          else tr("Веса найдены. Готовые PNG сохраняются в разрешении оригинала."))
