"""Capture only the original bundled demo artwork for public documentation."""
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from PySide6.QtCore import QSettings,QPoint,Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from studio.window import Window
from studio.theme import STYLE
from studio.engine import ROOT
from check_desktop import idle


app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','seguisym.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
repo=Path(__file__).resolve().parents[1]
for code in ('ru','en'):
    destination=ROOT/'results'/'2.0'/'capture'/code;destination.mkdir(parents=True,exist_ok=True)
    config=QSettings(str(destination/'settings.ini'),QSettings.IniFormat);config.setValue('language',code)
    w=Window(config);w.resize(1350,880);w.show();w.example();idle(w)
    w.open_objects();w.new_object()
    # The public example is also usable without models. Capture its contour workflow.
    w.object_backend.setCurrentIndex(w.object_backend.findData('contour'))
    for x,y,positive in ((.275,.65,True),(.236,.75,True),(.39,.625,True),(.70,.625,True),
                         (.766,.75,True),(.609,.5625,True),(.347,.70,True),(.664,.6875,True),
                         (.34,.756,True),(.50,.35,False),(.50,.67,False),(.87,.65,False)):
        rect=w.canvas.page_rect()
        point=QPoint(round(rect.x()+x*rect.width()),round(rect.y()+y*rect.height()))
        QTest.mouseClick(w.canvas,Qt.LeftButton if positive else Qt.RightButton,pos=point)
        idle(w)
    assert w.selection_mask is not None,w.object_state.text()
    w.object_name.setText('Куртка' if code=='ru' else 'Jacket');w.object_hex.setText('#287FE8')
    w.apply_object();idle(w)
    assert w.current().layers and w.current().trial
    assert w.object_apply.visibleRegion().contains(w.object_apply.rect().center())
    assert w.object_hex.visibleRegion().contains(w.object_hex.rect().center())
    w.grab().save(str(repo/'docs'/f'workspace-{code}.png'))
    w.close();app.processEvents()
    print('PASS native object clicks and screenshot',code,flush=True)
