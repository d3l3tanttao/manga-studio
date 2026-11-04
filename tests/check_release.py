"""Offline release checks. No model, source checkout or network is required."""
import argparse
import json
import os
from pathlib import Path
import shutil
from string import Formatter
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ.setdefault("QT_SCALE_FACTOR","1.5")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QColor,QFontDatabase,QTextLayout,QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog
from check_desktop import idle,menu_ok,pixels
from studio.chapter import cache_path,version_path
from studio.i18n import LANGUAGES,CATALOGS,resolve,tr
from studio.window import Window
from studio.settings import SettingsDialog
from studio.theme import STYLE


def fields(msg):
    return sorted(f for _,f,_,_ in Formatter().parse(msg) if f is not None)


def screen_point(w,x,y):
    r=w.canvas.page_rect()
    return QPoint(round(r.x()+r.width()*x),round(r.y()+r.height()*y))


def page_pixels(w):
    return pixels(w.canvas.result)


def check_language(app,root,code,artifacts,deep):
    conf=QSettings(str(root/"settings.ini"),QSettings.IniFormat)
    conf.setValue("language",code)
    w=Window(conf)
    try:
        w.setStyleSheet(STYLE)
        w.resize(940,610);w.show();app.processEvents()
        assert w.set_color_btn.text()==tr("Задать цвет")
        assert (w.layoutDirection()==Qt.RightToLeft)==(code in ("ar","fa","ur"))
        assert w.demo_btn.isVisible() and w.demo_btn.text()==tr("Попробовать на примере")
        for k in (w.demo_btn,w.welcome_open):
            assert k.visibleRegion().contains(k.rect().center())
        w.demo_btn.click();idle(w)
        assert w.original.size==(640,800) and w.engine.model is None
        for widget in (w.set_color_btn,w.export_btn,w.one_btn):
            assert w.rect().contains(widget.mapTo(w,widget.rect().center()))
        w.set_color_btn.click()
        assert w.canvas.tool=="hint" and w.hex_box.isVisibleTo(w)
        settings=SettingsDialog(w.settings,w)
        assert settings.language.findData(code)>=0 and settings.language.count()==26
        settings.deleteLater()
        if not deep:
            return
        w.resize(1260,840);app.processEvents()
        old=page_pixels(w); p=w.current()
        w.hex_box.setText("#287FE8"); w.hex_box.editingFinished.emit()
        assert w.canvas.color.name()=="#287fe8"
        with patch("studio.window.text_input",return_value=("Jacket blue",True)):
            w.palette_add.click()
        w.select_swatch("#df4057")
        with patch("studio.window.text_input",return_value=("Red",True)):
            w.palette_add.click()
        w.use_palette(0)
        assert w.palette_box.currentItem().text()=="Jacket blue" and w.canvas.color.name()=="#287fe8"
        with patch("studio.window.text_input",return_value=("Coat blue",True)):
            w.rename_color()
        assert w.active_swatch=="Coat blue"
        w.tool.setCurrentIndex(w.tool.findData("paint"));w.diameter.setValue(28)
        w.setFocus();QTest.keyClick(w,Qt.Key_BracketRight);assert w.canvas.diameter==29
        QTest.keyClick(w,Qt.Key_BracketLeft);assert w.canvas.diameter==28
        a,b=screen_point(w,.31,.66),screen_point(w,.33,.70)
        QTest.mousePress(w.canvas,Qt.LeftButton,pos=a)
        QTest.mouseRelease(w.canvas,Qt.LeftButton,pos=b)
        idle(w)
        assert len(p.strokes[-1].points)==2 and p.trial and len(p.versions)==1
        color=page_pixels(w)
        outside=np.ones(old.shape[:2],bool);outside[505:582,175:235]=False
        assert np.array_equal(old[outside],color[outside]) and not np.array_equal(old,color)
        w.discard_btn.click();idle(w)
        assert len(p.versions)==1 and not p.trial and np.array_equal(page_pixels(w),old)
        w.tool.setCurrentIndex(w.tool.findData("lasso"))
        poly=[screen_point(w,x,y) for x,y in ((.27,.65),(.36,.67),(.35,.77),(.24,.76))]
        QTest.mousePress(w.canvas,Qt.LeftButton,pos=poly[0])
        for pt in poly[1:]:QTest.mouseMove(w.canvas,pt)
        QTest.mouseRelease(w.canvas,Qt.LeftButton,pos=poly[0]);idle(w)
        probe=page_pixels(w); outside[:]=True;outside[509:625,144:242]=False
        assert np.array_equal(probe[outside],old[outside]) and not np.array_equal(probe,old)
        w.view.setCurrentIndex(w.view.findData("previous"))
        assert w.canvas.tool=="view" and np.array_equal(pixels(w.canvas.before),old)
        w.one_btn.click();idle(w)
        assert p.trial is None and len(p.versions)==2 and w.engine.model is None
        assert np.array_equal(np.asarray(Image.open(version_path(w.project,p.version()))),probe)
        menu_ok(w,w.review_export)
        assert np.array_equal(np.asarray(Image.open(w.last_export/"0001.png")),probe)
        if artifacts:
            artifacts.mkdir(parents=True,exist_ok=True)
            w.tabs.setCurrentIndex(1);w.view.setCurrentIndex(w.view.findData("result"));app.processEvents()
            w.grab().save(str(artifacts/f"{code}.png"))
        # Alt samples without changing the active brush. Out-of-page motion ends the stroke.
        w.tool.setCurrentIndex(w.tool.findData("paint"));w.sample_from.setCurrentIndex(1)
        mid=screen_point(w,.33,.7)
        QTest.mouseClick(w.canvas,Qt.LeftButton,Qt.AltModifier,pos=mid)
        assert w.canvas.tool=="paint" and len(set(w.canvas.color.getRgb()[:3]))==1
        r=w.canvas.page_rect(); y=round(r.center().y())
        QTest.mousePress(w.canvas,Qt.LeftButton,pos=QPoint(round(r.right())-3,y))
        QTest.mouseMove(w.canvas,QPoint(round(r.right())+12,y))
        QTest.mouseMove(w.canvas,QPoint(round(r.right())+15,y+35))
        QTest.mouseRelease(w.canvas,Qt.LeftButton,pos=QPoint(round(r.right())+15,y+35))
        assert len(p.strokes[-1].points)==2 and abs(p.strokes[-1].points[-1][0]-1)<1e-9
        idle(w);w.discard_btn.click();idle(w)
        # A true 1.1-shaped manifest with legacy version dictionaries and PNG assets.
        # A separately opened 1.1 project is migrated without modifying its manifest.
        if code=="en":
            legacy=root/"legacy";legacy.mkdir()
            w.persist()
            doc=json.loads(w.project.read_text(encoding="utf8"))
            doc["format"]="manga-studio/1.1"
            for row in doc["pages"]:
                for key in ("trial","version_name"):row.pop(key,None)
                row["versions"]=row["versions"][:1];row["selected"]=0
                row.update({k:row["versions"][0][k] for k in ("mode","intensity","strokes","settings")})
                row["versions"][0].pop("name",None)
            saved=(json.dumps(doc,ensure_ascii=False)).encode("utf8")
            (legacy/"chapter.json").write_bytes(saved)
            for part in ("colors","versions"):shutil.copytree(w.project.parent/part,legacy/part)
            w.load_project(legacy/"chapter.json");idle(w)
            assert w.project!=legacy/"chapter.json" and (legacy/"chapter.json").read_bytes()==saved
            assert w.is_saved(w.current()) and len(w.current().versions)==1
    finally:
        idle(w);w.close();app.processEvents()


def main(artifacts):
    app=QApplication([])
    app.setStyle("Fusion");app.setStyleSheet(STYLE)
    fonts=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
    for file in ("segoeui.ttf","seguisb.ttf","segoeuib.ttf","seguisym.ttf","Nirmala.ttc","msyh.ttc","msjh.ttc","YuGothR.ttc","malgun.ttf"):
        if (fonts/file).is_file():QFontDatabase.addApplicationFont(str(fonts/file))
    ru=json.loads((CATALOGS/"ru.json").read_text(encoding="utf8"))
    assert len(LANGUAGES)==25 and resolve("zh-HK")=="zh-Hant" and resolve("pt_PT")=="pt-BR"
    assert set(p.stem for p in CATALOGS.glob("*.json"))==set(LANGUAGES)
    for code in LANGUAGES:
        catalog=json.loads((CATALOGS/(code+".json")).read_text(encoding="utf8"))
        assert set(catalog)==set(ru)
        for k,v in catalog.items():
            assert v.strip() and fields(k)==fields(v),(code,k,v)
            assert '\ufffd' not in v
            if not app.platformName()=="offscreen" or (fonts/"Nirmala.ttc").is_file():
                layout=QTextLayout(v,QFont("Segoe UI",10))
                layout.beginLayout();line=layout.createLine();line.setLineWidth(10000);layout.endLayout()
                assert all(0 not in run.glyphIndexes() for run in layout.glyphRuns()),(code,k,v)
        with TemporaryDirectory(dir=Path.cwd()) as d:
            check_language(app,Path(d),code,artifacts,code in ("ru","en","de","ar","zh-Hans"))
        print("PASS",code,len(catalog),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--artifacts",type=Path)
    main(parser.parse_args().artifacts)
