"""Qt test helpers and the FLUX compatibility check entry point."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ.setdefault("QT_SCALE_FACTOR","1.5")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog
from studio.chapter import version_path
from studio.engine import ROOT, open_page
from studio.settings import SettingsDialog
from studio.theme import STYLE
from studio.window import Window


def idle(w):
    end = monotonic()+240
    while True:
        QApplication.processEvents()
        if not (w.worker or w.preview_job or w.selection_job or w.preview_timer.isActive()):
            return
        if monotonic()>end:
            raise TimeoutError(w.status.text())
        sleep(.012)


def menu_ok(window, method):
    QTimer.singleShot(0,lambda: QApplication.activeModalWidget().accept())
    method()
    idle(window)


def pixels(pix):
    return np.array(Image.fromqpixmap(pix).convert("RGB"))


if __name__ == "__main__":
    import check_flux_contract
