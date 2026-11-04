"""Exercise the 1.1 chapter workflow with real weights. --artifacts saves the audited export."""
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
        if not (w.worker or w.preview_job or w.preview_timer.isActive()):
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


def main(artifacts):
    app=QApplication([])
    for name in ("segoeui.ttf","segoeuib.ttf","seguisb.ttf","seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"])/"Fonts"/name))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    sample=Path(__file__).resolve().parents[1]/"studio"/"assets"/"jacket.png"
    with TemporaryDirectory(dir=ROOT) as temp:
        root=Path(temp)
        group=root/"Глава"; group.mkdir()
        extra=root/"Дополнение"; extra.mkdir()
        path16=group/"02.png"
        gray=np.array(Image.open(sample).convert("L"))
        gray[0,:256]=np.arange(256,dtype=np.uint8)
        Image.fromarray(gray.astype(np.uint16)*257).save(path16)
        assert np.array_equal(np.asarray(open_page(path16).convert("L")),gray)
        Image.open(sample).convert("RGB").transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(group/"10.jpg")
        broken=group/"08.jpg"
        broken.write_bytes(b"broken")
        conf=QSettings(str(root/"settings.ini"),QSettings.IniFormat)
        conf.setValue("language","ru")
        w=Window(conf); w.show(); app.processEvents()
        w.demo_btn.click(); idle(w)
        assert w.is_saved(w.current()) and w.engine.model is None
        w.new_project()
        with patch.object(QFileDialog,"getExistingDirectory",return_value=str(group)):
            w.welcome_open.click()
        assert conf.value("last_import")==str(group)
        assert [p.path.stem for p in w.ordered()]==["02","08","10"]
        folder=w.folder
        with patch.object(w.engine,"predict",wraps=w.engine.predict) as inference:
            stages=[]
            w.run_btn.click()
            w.worker.stage.connect(lambda uid,stage:stages.append(stage))
            idle(w)
            assert w.done==2 and w.errors==1 and inference.call_count==2
            assert set(stages)>={"Раскраска","Сохранение"}
            import torch
            assert w.engine.model.device == ("cuda" if torch.cuda.is_available() else "cpu")
            w.list.setCurrentRow(1); app.processEvents()
            assert w.issue.isVisible() and "изображение" in w.issue.text()
            Image.open(sample).convert("RGB").save(broken)
            w.retry.click(); idle(w)
            assert w.done==1 and w.errors==0 and inference.call_count==3
            assert not w.current().error
            missing=extra/"01.jpg"; shutil.copyfile(broken,missing)
            w.add_paths([missing])
            assert w.folder==folder and [p.path.stem for p in w.ordered()]==["01","02","08","10"]
            assert w.run_btn.text().endswith("1")
            menu_ok(w,w.review_export)
            assert w.current().path==missing and not w.last_export
            w.run_btn.click(); idle(w)
            assert inference.call_count==4
            menu_ok(w,w.review_export)
            first=w.last_export
            assert len(list(first.glob("*.png")))==4
            with patch("studio.window.subprocess.Popen") as explorer:
                w.show_file()
                assert str(first/"0001.png") in explorer.call_args.args[0]
            with patch.object(QFileDialog,"getOpenFileNames",return_value=([], "")) as dialog:
                w.open_files()
                assert dialog.call_args.args[2]==str(group)
            print(f"PASS 16-bit import, example, {w.device.text()}, insertion, retry, export preflight",flush=True)

            w.list.setCurrentRow(1); idle(w)
            p=w.current()
            w.percent.click()
            assert abs(w.canvas.page_rect().width()*w.canvas.devicePixelRatioF()/gray.shape[1]-1)<0.001
            center=w.canvas.rect().center()
            QTest.mousePress(w.canvas,Qt.MiddleButton,pos=center)
            QTest.mouseMove(w.canvas,center+QPoint(11,15))
            QTest.mouseRelease(w.canvas,Qt.MiddleButton,pos=center+QPoint(11,15))
            w.guides.click()
            camera=(w.canvas.zoom,w.canvas.pan.x(),w.canvas.pan.y())
            w.mode.setCurrentIndex(w.mode.findData("luma"))
            w.strength.setValue(61); idle(w)
            image=pixels(w.canvas.result)
            assert np.array_equal(np.asarray(Image.fromarray(image).convert("L")),gray)
            assert all(page.mode=="tint" for page in w.pages.values() if page.uid!=p.uid)
            assert camera==(w.canvas.zoom,w.canvas.pan.x(),w.canvas.pan.y())
            w.strength.setValue(0); idle(w)
            assert np.array_equal(pixels(w.canvas.result),np.asarray(open_page(path16)))
            w.strength.setValue(84); w.mode.setCurrentIndex(w.mode.findData("tint")); idle(w)
            w.set_color_btn.click()
            w.tool.setCurrentIndex(w.tool.findData("pick"))
            QTest.mouseClick(w.canvas,Qt.LeftButton,pos=center)
            assert w.canvas.tool=="hint"
            with patch("studio.window.text_input",return_value=("Аки · волосы",True)):
                w.palette_add.click()
            w.tool.setCurrentIndex(w.tool.findData("restore")); w.diameter.setValue(37)
            rect=w.canvas.page_rect()
            x,y=w.canvas.normalized(center)
            ix,iy=round(x*(gray.shape[1]-1)),round(y*(gray.shape[0]-1))
            before=pixels(w.canvas.result)
            QTest.mouseClick(w.canvas,Qt.LeftButton,pos=center); idle(w)
            after=pixels(w.canvas.result)
            assert np.array_equal(after[iy-4:iy+5,ix-4:ix+5],np.asarray(open_page(path16))[iy-4:iy+5,ix-4:ix+5])
            assert not np.array_equal(after,before)
            w.undo_btn.click(); idle(w); assert np.array_equal(pixels(w.canvas.result),before)
            w.redo_btn.click(); idle(w); assert np.array_equal(pixels(w.canvas.result),after)
            w.tool.setCurrentIndex(w.tool.findData("erase"))
            QTest.mouseClick(w.canvas,Qt.LeftButton,pos=center); idle(w)
            assert np.array_equal(pixels(w.canvas.result),before)
            w.undo_btn.click(); idle(w)
            w.one_btn.click(); idle(w)
            assert inference.call_count==4 and len(p.versions)==2
            w.use_palette(0); QTest.mouseClick(w.canvas,Qt.LeftButton,pos=center+QPoint(40,0))
            assert p.trial and w.one_btn.text().startswith("Применить подсказки")
            w.one_btn.click(); idle(w)
            assert p.trial and len(p.versions)==2
            assert not w.marks.isChecked() and w.view.currentData()=="previous"
            suggested=pixels(w.canvas.result)
            assert not np.array_equal(suggested,after)
            w.one_btn.click(); idle(w)
            assert inference.call_count==5 and len(p.versions)==3
            assert np.array_equal(suggested,np.asarray(Image.open(version_path(w.project,p.version()))))
            w.choose_version(1); idle(w)
            assert p.selected==1 and np.array_equal(pixels(w.canvas.result),after)
            w.apply_all(); assert all(page.intensity==84 for page in w.pages.values())
            w.run_btn.click(); idle(w)
            assert inference.call_count==5
            print("PASS cached previews, independent per-page controls, color picker, palette, brushes, undo/redo, versions, physical 1:1",flush=True)

        # Save the exact viewport, chosen version, edits and order across a full restart.
        uid=p.uid
        w.move_page(1)
        order=[page.uid for page in w.ordered()]
        assert order[2]==uid
        w.persist()
        w.close(); app.processEvents()
        w=Window(conf); w.show(); app.processEvents(); w.continue_btn.click(); idle(w)
        assert w.active==uid and [page.uid for page in w.ordered()]==order
        assert w.current().selected==1 and w.current().strokes[-1].kind=="restore"
        assert w.palette_colors.get("Аки · волосы") and w.folder==folder
        assert not w.guides.isChecked() and w.canvas.zoom==camera[0]
        assert abs(w.canvas.pan.x()-camera[1])<.05 and abs(w.canvas.pan.y()-camera[2])<.05, (camera,w.canvas.pan,w.current().view)
        assert w.is_saved(w.current())
        w.resize(940,610); app.processEvents()
        for b in (w.one_btn,w.run_btn,w.export_btn):
            assert w.rect().contains(b.mapTo(w,b.rect().center()))
        w.left_btn.click(); assert w.left.isHidden()
        w.left_btn.click(); w.right_btn.click(); assert w.right.isHidden()
        w.right_btn.click()
        w.left.setFocus()
        QTest.keyClick(w,Qt.Key_PageDown)
        assert w.list.currentRow()==3
        QTest.keyClick(w,Qt.Key_PageUp)
        assert w.list.currentRow()==2
        assert w.current().path==path16
        w.resize(1270,800); app.processEvents()
        with TemporaryDirectory(dir=root) as moved:
            # Move only files created by this test.
            moved=Path(moved)
            for source in (path16,broken,group/"10.jpg"):
                source.rename(moved/source.name)
                os.utime(moved/source.name,None)
            w.relink(moved)
            assert all(page.path.exists() for page in w.pages.values())
            assert w.current().strokes and w.is_saved(w.current())
            menu_ok(w,w.review_export)
            final=w.last_export
            assert final!=first and first.is_dir()
            for i,page in enumerate(w.ordered(),1):
                assert (final/f"{i:04d}.png").read_bytes()==version_path(w.project,page.version()).read_bytes()
            assert sorted(p.name for p in final.iterdir())==[f"{i:04d}.png" for i in range(1,5)]
            if artifacts:
                artifacts.mkdir(parents=True,exist_ok=True)
                shutil.copytree(final,artifacts/"chapter",dirs_exist_ok=True)
                w.list.setCurrentRow(0); w.tabs.setCurrentIndex(0); w.fit(); idle(w)
                assert w.grab().save(str(artifacts/"studio.png"))
            print("PASS project restart, view/order/version recovery, relink, versioned final export, compact layout",flush=True)
            def cpu():
                dialog=w.findChild(SettingsDialog)
                dialog.device.setCurrentIndex(dialog.device.findData("cpu"))
                dialog.size.setCurrentIndex(dialog.size.findData(384))
                dialog.denoise.setChecked(False)
                dialog.accept()
            QTimer.singleShot(0,cpu); w.settings_btn.click()
            w.run_btn.click()
            w.worker.stage.connect(lambda uid,phase:w.stop() if phase=="Раскраска" else None)
            idle(w)
            assert w.done==1 and w.errors==0 and w.device.text()=="CPU"
            w.run_btn.click(); idle(w)
            assert w.done==3 and w.errors==0
            w.close()
            print("PASS CPU, queue stop and resume. RELEASE 1.2 OK",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--artifacts",type=Path)
    main(parser.parse_args().artifacts)
