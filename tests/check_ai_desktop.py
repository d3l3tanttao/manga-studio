"""Real GPU + Qt integration: chapter, references, versions, cancel, export, reopen."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_SCALE_FACTOR','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from studio.chapter import source_hash,version_path
from studio.engine import ROOT
from studio.theme import STYLE
from studio.window import Window
from check_desktop import idle,menu_ok

def main(destination,source,reference,chapter):
    app=QApplication([])
    app.setStyle('Fusion');app.setStyleSheet(STYLE)
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','seguisym.ttf'):
        QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
    root=destination/uuid4().hex
    root.mkdir(parents=True)
    inputs=root/'inputs';inputs.mkdir()
    # These are a mixed regression chapter, not a continuous story/identity dataset.
    for i,path in enumerate(chapter,1):shutil.copyfile(path,inputs/f'{i:02d}{path.suffix}')
    snapshots={p:source_hash(p) for p in inputs.iterdir()}
    config=QSettings(str(root/'settings.ini'),QSettings.IniFormat)
    config.setValue('language','ru')
    w=Window(config);w.resize(1360,900);w.show();app.processEvents()
    summary={'project_root':str(root),'checks':[]}
    def check(name):
        summary['checks'].append(name);print('PASS',name,flush=True)
    try:
        w.add_paths(list(inputs.iterdir()));idle(w)
        assert w.ai_mode.currentData()=='color' and not w.ai_manual.isChecked()
        assert w.canvas.tool=='view' and all(not p.settings.reference for p in w.ordered())
        w.run_btn.click();idle(w)
        assert w.done==3 and w.errors==0,[(p.path.name,p.error) for p in w.ordered()]
        for p in w.ordered():
            assert w.is_saved(p) and Image.open(version_path(w.project,p.version())).size==Image.open(p.path).size
            assert p.version()['render_report']['protected_text_changed_pixels']==0
            assert not p.strokes
        assert any(p.settings.anchor for p in w.ordered()[1:])
        check('three-page chapter without reference or brush, palette anchor, native dimensions, text protection')
        w.grab().save(str(root/'chapter.png'))
        menu_ok(w,w.review_export)
        assert len(list(w.last_export.glob('*.png')))==3
        check('chapter export')
        w.add_paths([source]);idle(w)
        w.list.setCurrentRow(w.list.count()-1);idle(w)
        page=w.current()
        w.set_ai_reference(reference);idle(w)
        assert page.settings.generation=='reference' and w.ai_ref_image.isVisible()
        w.start_selected();idle(w)
        assert not page.error and len(page.versions)==1,page.error
        assert page.version()['render_report']['reference_sha256']==source_hash(Path(page.settings.reference))
        first=source_hash(version_path(w.project,page.version()))
        w.grab().save(str(root/'reference.png'))
        check('reference copied into project and used by local worker')
        # Real redraw, no brush, no opaque post-blend: freedom is in latent denoising.
        w.ai_mode.setCurrentIndex(w.ai_mode.findData('redraw'))
        w.ai_freedom.setValue(100)
        w.start_selected();idle(w)
        assert len(page.versions)==2 and page.version()['render_report']['freedom']==1.,page.error
        assert first!=source_hash(version_path(w.project,page.version()))
        w.grab().save(str(root/'redraw.png'))
        check('redraw differs from coloring and retains both versions')
        w.choose_version(0);idle(w)
        assert source_hash(version_path(w.project,page.version()))==first
        check('history restores exact prior PNG')
        # Cancel only our own subprocess tree after a real denoising step.
        w.ai_seed.setValue(w.ai_seed.value()+1)
        w.start_selected()
        worker=w.worker
        cancelled=[]
        def stop_on_step(uid,stage):
            if '/' in stage and not cancelled:
                cancelled.append(True);w.stop()
        worker.stage.connect(stop_on_step)
        idle(w)
        assert cancelled and len(page.versions)==2 and not page.error
        assert w.engine.ai is None or w.engine.ai.process is None
        check('cancel mid-generation leaves versions intact and stops worker tree')
        w.ai_variant.click();idle(w)
        assert len(page.versions)==3 and not page.error,page.error
        check('new variant starts successfully after cancellation')
        # Semantic commands operate on a saved image without a brush or user mask.
        w.ai_correction.setCurrentIndex(w.ai_correction.findData('skin'))
        w.ai_fix.click();idle(w)
        assert len(page.versions)==4 and not page.error,page.error
        assert page.version()['render_report']['correction']=='skin'
        assert not page.strokes and page.settings.base
        w.ai_correction.setCurrentIndex(w.ai_correction.findData('face'))
        w.ai_fix.click();idle(w)
        assert len(page.versions)==5 and not page.error,page.error
        assert page.version()['render_report']['context_passes']
        w.grab().save(str(root/'correction.png'))
        check('skin and automatically located face correction create separate versions without brush masks')
        # Copying the whole project keeps imported references and version signatures usable.
        w.persist();project=w.project
        manifest=json.loads(project.read_text('utf8'))
        row=next(row for row in manifest['pages'] if row['uid']==page.uid)
        assert not Path(row['settings']['reference']).is_absolute()
        moved=root/'moved-project'
        shutil.copytree(project.parent,moved,ignore=shutil.ignore_patterns('*.lock'))
        w.load_project(moved/'chapter.json');idle(w)
        page=w.current()
        assert Path(page.settings.reference).is_relative_to(moved.resolve())
        assert Path(page.settings.reference).is_file() and w.is_saved(page)
        assert len(page.versions)==5 and Path(page.settings.base).is_relative_to(moved.resolve())
        check('copied project reopens with portable references and immutable versions')
        for path,digest in snapshots.items():assert source_hash(path)==digest
        check('original files unchanged')
        summary['reports']=[p.version().get('render_report',{}) for p in w.ordered()]
        summary['export']=str(w.last_export)
        (root/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
        print('ARTIFACTS',root,flush=True)
    finally:
        if w.worker:w.stop()
        idle(w);w.close();app.processEvents()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--chapter',type=Path,nargs=3,required=True)
    a=p.parse_args();main(a.output.resolve(),a.source.resolve(),a.reference.resolve(),[f.resolve() for f in a.chapter])
