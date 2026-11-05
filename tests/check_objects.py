"""Quality and desktop regression tests for object editing, with optional real SAM."""
import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from time import sleep

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image,ImageDraw
from PySide6.QtCore import QSettings,Qt,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication,QMessageBox
from studio.chapter import Page,compose,version_path
from studio.engine import Settings,Stroke,ROOT
from studio.materials import MaterialLayer,compose_layers,material_color,audit,image_digest
from studio.regions import pack,unpack,refine_mask,background_mask,scene_regions,repair_pinholes
from studio.segmentation import Segmenter
from studio.theme import STYLE
from studio.window import Window
from check_desktop import idle,pixels


def fixture(width=640,height=800):
    image=Image.new('RGB',(width,height),'white');d=ImageDraw.Draw(image)
    d.rectangle((20,20,width-20,height-20),outline='black',width=4)
    d.ellipse((180,65,430,300),fill=(230,230,230),outline='black',width=4)
    d.polygon(((200,300),(400,300),(500,620),(135,620)),fill=(190,190,190),outline='black',width=4)
    d.rectangle((290,250,320,650),fill='black')
    d.line((220,320,240,600),fill=(100,100,100),width=3)
    return image


def core_checks():
    image=fixture();gray=np.array(image.convert('L'))
    mask=np.zeros(gray.shape,np.uint8);mask[320:600,180:480]=255;mask[319,180:480]=100
    layer=MaterialLayer(pack(mask),'Coat',(40,127,232))
    red=np.full((*gray.shape,3),(200,40,40),np.uint8)
    green=np.full((*gray.shape,3),(40,200,40),np.uint8)
    a=compose_layers(image,red,[layer]);b=compose_layers(image,green,[layer])
    assert np.array_equal(a[mask==0],red[mask==0])
    assert np.array_equal(a[mask>0],b[mask>0]),'Previous hue survived in the object or its edge'
    assert np.array_equal(unpack(layer.mask,image.size),mask)
    lockmask=np.zeros_like(mask);lockmask[:,280:330]=255
    locked=MaterialLayer(pack(lockmask),'Hair',locked=True,frozen=pack(red))
    protected=compose_layers(image,green,[layer,locked])
    assert np.array_equal(protected[lockmask>0],red[lockmask>0])
    assert all(item['pixels']==0 for item in audit(image,protected,[layer,locked]) if item['kind'] in ('protected','material'))
    layer.color=(200,50,80)
    changed=compose_layers(image,green,[layer,locked])
    assert np.array_equal(changed[lockmask>0],red[lockmask>0])
    black=np.zeros((40,40),np.uint8);black[0:5]=255
    assert np.all(material_color(black,(40,127,232))[10:]==0)
    lifted=material_color(black,(40,127,232),dark_lift=.5)
    assert lifted[20,20].max()>0
    thin=np.full((40,40),255,np.uint8);thin[:,20]=0
    assert np.all(material_color(thin,(40,127,232),dark_lift=.5)[:,20]==0)
    for swatch in ((40,127,232),(241,198,170),(255,255,255),(0,0,0)):
        mapped=material_color(np.full((2,2),255,np.uint8),swatch)
        assert np.max(np.abs(mapped.astype(int)-np.array(swatch)))<=1,(swatch,mapped[0,0])
    try:unpack(layer.mask,(10,10));raise AssertionError('Accepted wrong mask dimensions')
    except ValueError:pass
    flat=np.full((80,80),255,np.uint8);holed=flat.copy();holed[30:33,30:33]=0
    assert np.all(repair_pinholes(flat,holed)==255)
    assert repair_pinholes(flat,holed,[(31/79,31/79,False)])[31,31]==0
    edged=flat.copy();cv2.rectangle(edged,(29,29),(33,33),0,1)
    assert repair_pinholes(edged,holed)[31,31]==0
    bg=background_mask(gray)
    assert bg[0,0]==255 and bg[400,400]==0
    p=Page(Path('sample.png'),Settings());p.layers=[layer,locked]
    restored=Page.load(p.serialize())
    assert restored.options()==p.options()
    # Repeated edits are evaluated from the same source and retain all scan pixels outside the mask.
    layer.color=(40,127,232)
    again=compose_layers(image,red,[layer])
    assert np.array_equal(again,a)
    for i in range(12):
        varied=np.roll(mask,i*3,axis=1)
        refined=refine_mask(gray,varied)
        assert refined.shape==gray.shape and refined.dtype==np.uint8
    layer.source_digest=image_digest(image)
    modified=image.copy();modified.putpixel((0,0),(0,0,0))
    try:compose_layers(modified,red,[layer]);raise AssertionError('Accepted a mask for a changed original')
    except ValueError:pass
    print('PASS native masks, old-hue removal including soft edges, exact locks, black fills, serialization',flush=True)


def desktop_checks(app,artifacts):
    with TemporaryDirectory(dir=ROOT) as temporary:
        root=Path(temporary);source=root/'page.png';fixture().save(source)
        config=QSettings(str(root/'settings.ini'),QSettings.IniFormat);config.setValue('language','ru')
        w=Window(config);w.show();w.add_paths([source]);idle(w)
        try:
            w.set_color_btn.click();assert w.tabs.currentIndex()==w.object_tab and w.canvas.tool=='object'
            w.new_object()
            w.handle_region_stroke(Stroke((40,127,232),.01,((.28,.40),(.74,.40),(.74,.75),(.28,.75)),'region_lasso'))
            w.object_name.setText('Jacket');w.object_hex.setText('#287FE8');w.apply_object();idle(w)
            p=w.current();assert p.trial and p.original_base and len(p.layers)==1
            assert w.canvas.object_overlay.isNull() and not w.canvas.object_points
            before=pixels(w.canvas.original);colored=pixels(w.canvas.result)
            mask=unpack(p.layers[0].mask,w.original.size)
            assert np.array_equal(colored[mask==0],before[mask==0])
            w.undo();idle(w);assert not p.layers and np.array_equal(pixels(w.canvas.result),before)
            w.redo();idle(w);assert len(p.layers)==1 and np.array_equal(pixels(w.canvas.result),colored)
            w.select_object(0);w.lock_object();idle(w);assert p.layers[0].locked
            w.start_selected();idle(w);assert w.is_saved(p)
            assert np.array_equal(np.asarray(Image.open(version_path(w.project,p.version()))),pixels(w.canvas.result))
            path=w.project;snapshot=p.options();w.persist();w.close()
            w=Window(config);w.show();w.load_project(path);idle(w)
            assert w.current().options()==snapshot and w.is_saved(w.current())
            w.open_objects();w.select_object(0);w.lock_object();idle(w)
            w.object_hex.setText('#C94477');w.apply_object();idle(w)
            assert w.current().layers[0].color==(201,68,119)
            w.discard_trial();idle(w)
            assert w.current().layers[0].locked and w.current().layers[0].color==(40,127,232)
            # 1.2 chapters are copied; their manifest stays byte-for-byte unchanged.
            old=root/'legacy'/'chapter.json';old.parent.mkdir()
            data=json.loads(path.read_text(encoding='utf-8'));data['format']='manga-studio/1.2'
            data['pages'][0].pop('layers',None)
            old.write_text(json.dumps(data),encoding='utf-8');bytes_before=old.read_bytes()
            w.load_project(old);idle(w)
            assert w.project!=old and old.read_bytes()==bytes_before
            if artifacts:
                artifacts.mkdir(parents=True,exist_ok=True)
                w.new_object();w.handle_region_stroke(Stroke((40,127,232),.01,((.28,.40),(.74,.40),(.74,.75),(.28,.75)),'region_lasso'))
                w.object_name.setText('Jacket');w.apply_object();idle(w)
                w.grab().save(str(artifacts/'workspace-objects.png'))
        finally:
            idle(w);w.close();app.processEvents()
    print('PASS object workflow, undo/redo, lock, accept/discard, reload, legacy migration',flush=True)


def interaction_checks(app):
    with TemporaryDirectory(dir=ROOT) as temporary:
        root=Path(temporary);sources=[root/'one.png',root/'two.png']
        for path in sources:fixture().save(path)
        config=QSettings(str(root/'settings.ini'),QSettings.IniFormat);config.setValue('language','en')
        w=Window(config);w.show();w.add_paths(sources);idle(w)
        try:
            for page in w.ordered():
                w.list.setCurrentItem(w.items[page.uid]);idle(w);w.new_object()
                w.handle_region_stroke(Stroke((0,0,0),.01,((.28,.4),(.74,.4),(.74,.75),(.28,.75)),'region_lasso'))
                w.handle_region_stroke(Stroke((0,0,0),.04,((.4,.5),),'region_remove'))
                manually_added=w.selection_add.copy();manually_removed=w.selection_remove.copy()
                w.selection_candidates=[np.zeros_like(w.selection_mask)]
                w.choose_candidate(0)
                assert np.all(w.selection_mask[(manually_added>0)&(manually_removed==0)]==255)
                assert np.all(w.selection_mask[manually_removed>0]==0)
                w.undo_selection();assert not np.any(w.selection_remove)
                w.undo_selection(True);assert np.any(w.selection_remove)
                w.object_name.setText('Coat');w.material_name.setText('Coat');w.character_name.setText('Hero')
                w.apply_object();idle(w);w.start_selected();idle(w)
                assert w.is_saved(page)
            w.select_object(0);w.object_hex.setText('#A85577')
            def confirm():
                dialog=QApplication.activeModalWidget()
                assert isinstance(dialog,QMessageBox)
                next(button for button in dialog.buttons() if dialog.buttonRole(button)==QMessageBox.AcceptRole).click()
            QTimer.singleShot(50,confirm);w.apply_linked();idle(w)
            assert w.done==2 and w.errors==0
            for page in w.ordered():
                assert page.layers[0].color==(168,85,119) and w.is_saved(page) and len(page.versions)==2
                with Image.open(version_path(w.project,page.version())) as rendered:
                    assert rendered.size==fixture().size
            w.select_object(0)
            assert w.selection_add is not None and np.any(w.selection_remove)
            assert not w.selection_history and not w.selection_candidates
            # References use a deliberately bounded swatch, without altering target artwork.
            reference=root/'reference.png';Image.new('RGB',(100,100),(31,95,142)).save(reference)
            from studio.reference import ReferenceDialog
            dialog=ReferenceDialog(reference,w)
            dialog.selected(Stroke((0,0,0),.01,((.1,.1),(.9,.1),(.9,.9),(.1,.9)),'lasso'))
            assert dialog.color.getRgb()[:3]==(31,95,142) and dialog.accept_button.isEnabled()
            dialog.close()
            # Cancel a selection before it can publish a stale mask.
            def waiting(image,points,box,device,backend,cancelled):
                for _ in range(200):
                    if cancelled():return [],[],{}
                    sleep(.002)
                return [],[],{}
            w.selection_points=[(.4,.6,True)]
            with patch.object(w.segmenter,'predict',side_effect=waiting):
                w.run_selection();app.processEvents()
                assert w.stop_btn.isVisible()
                w.stop_btn.click();idle(w)
            assert w.selection_mask is None and w.selection_job is None
            assert len(w.current().layers)==1 and w.is_saved(w.current())
        finally:
            idle(w);w.close();app.processEvents()
    print('PASS persistent manual boundaries, selection history, linked chapter palette, reference sample',flush=True)


def sam_checks(artifacts):
    import time,torch
    segmenter=Segmenter();image=fixture()
    start=time.perf_counter()
    masks,scores,info=segmenter.predict(image,[(.38,.55,True),(.50,.22,False)],device='cuda')
    first=time.perf_counter()-start
    assert masks and any(m[440,243]>127 for m in masks)
    start=time.perf_counter()
    masks,_,_=segmenter.predict(image,[(.38,.55,True),(.50,.22,False),(.64,.60,True)],device='cuda')
    warm=time.perf_counter()-start
    assert masks and all(m.shape==(800,640) for m in masks)
    report={'first_seconds':first,'warm_seconds':warm,'peak_mib':torch.cuda.max_memory_allocated()/2**20,'backend':info}
    if artifacts:
        artifacts.mkdir(parents=True,exist_ok=True)
        (artifacts/'selection-metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        Image.fromarray(masks[0]).save(artifacts/'selection-mask.png')
    print('PASS real SAM 2.1',json.dumps(report),flush=True)
    if Segmenter.available('large'):
        start=time.perf_counter()
        masks,_,info=segmenter.predict(image,[(.38,.55,True),(.50,.22,False),(.64,.60,True)],device='cuda',backend='sam2-large')
        assert masks and masks[0][440,243]>127 and masks[0][176,320]<128
        print('PASS real SAM 2.1 Large',round(time.perf_counter()-start,3),info,flush=True)
        masks,_,info=segmenter.predict(image,[(.38,.55,True),(.50,.22,False),(.64,.60,True)],device='cuda',backend='sam2-large-parts')
        assert masks and masks[0][440,243]>127 and masks[0][480,409]>127 and masks[0][176,320]<128
        assert info['engine']=='sam2.1-large-parts'
        print('PASS independent-part SAM inference',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sam',action='store_true');parser.add_argument('--artifacts',type=Path)
    args=parser.parse_args()
    app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','seguisym.ttf'):
        QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
    core_checks();desktop_checks(app,args.artifacts);interaction_checks(app)
    if args.sam:sam_checks(args.artifacts)
