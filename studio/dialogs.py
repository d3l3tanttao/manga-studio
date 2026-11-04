from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QSlider, QVBoxLayout)
from .i18n import tr


def text_input(parent,title,prompt,text=""):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(prompt)
    dialog.setTextValue(text)
    dialog.setOkButtonText(tr("Сохранить"))
    dialog.setCancelButtonText(tr("Отмена"))
    ok = dialog.exec()
    value = dialog.textValue()
    dialog.deleteLater()
    return value,bool(ok)


def choose_color(parent, initial):
    dialog = QDialog(parent)
    dialog.setWindowTitle(tr("Выбрать цвет"))
    dialog.setMinimumWidth(330)
    outer = QVBoxLayout(dialog)
    chip = QLabel()
    chip.setFixedHeight(48)
    outer.addWidget(chip)
    form = QFormLayout()
    outer.addLayout(form)
    sliders = []
    field = QLineEdit(initial.name().upper())
    field.setMaxLength(7)
    form.addRow("HEX",field)
    for name,value in zip((tr("Красный"),tr("Зелёный"),tr("Синий")),initial.getRgb()[:3]):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0,255)
        slider.setValue(value)
        form.addRow(name,slider)
        sliders.append(slider)
    buttons = QDialogButtonBox()
    submit = buttons.addButton(tr("Выбрать"),QDialogButtonBox.AcceptRole)
    buttons.addButton(tr("Отмена"),QDialogButtonBox.RejectRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    outer.addWidget(buttons)

    def sync_sliders(text):
        code = "#"+text.lstrip("#")
        valid = len(code)==7 and QColor(code).isValid()
        submit.setEnabled(valid)
        if valid:
            color = QColor(code)
            chip.setStyleSheet(f"background:{color.name()};border-radius:6px;")
            for slider,value in zip(sliders,color.getRgb()):
                slider.blockSignals(True)
                slider.setValue(value)
                slider.blockSignals(False)
    def sync_field():
        field.setText(QColor(*(s.value() for s in sliders)).name().upper())
    field.textChanged.connect(sync_sliders)
    for slider in sliders:
        slider.valueChanged.connect(sync_field)
    sync_sliders(field.text())
    ok = dialog.exec()
    color = QColor(*(s.value() for s in sliders)) if ok else QColor()
    dialog.deleteLater()
    return color
