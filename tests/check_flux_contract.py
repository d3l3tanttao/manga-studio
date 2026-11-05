"""Compatibility and process routing without loading a neural model."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from studio.chapter import Page,settings_dict,read_settings,version_path,source_hash,asset_paths
from studio.engine import Settings
from studio.job import Batch
from studio.window import Window
from check_desktop import idle


class Probe:
    def __init__(self): self.calls=[];self.last_report={'backend':'flux'};self.device_name='probe'
    def prepare(self,settings): assert settings.renderer=='flux'
    def predict(self,image,settings,strokes):
        self.calls.append(settings)
        assert not strokes
        return Image.new('RGB',image.size,(120,150,180))
    def release_ai(self): pass


app=QApplication([])
with TemporaryDirectory(dir=Path.cwd()) as tmp:
    root=Path(tmp)
    w=Window(QSettings(str(root/'app.ini'),QSettings.IniFormat))
    try:
        w.show();app.processEvents();w.example();idle(w)
        assert w.current().version(),w.status.text()
        page=w.current(); original_version=deepcopy(page.version())
        original_file=version_path(w.project,page.version()); original_hash=source_hash(original_file)
        assert page.settings.renderer=='legacy' and w.is_saved(page)
        # Old settings reserialize byte-for-byte with the same fields.
        options=settings_dict(page.settings)
        assert settings_dict(read_settings(options))==options
        probe=Probe();batch=Batch(probe,[page],w.project)
        saved=[];failed=[];batch.saved.connect(lambda *v:saved.append(v));batch.failed.connect(lambda *v:failed.append(v))
        batch.run()
        assert not failed and len(probe.calls)==1 and len(saved)==1,(failed,len(saved))
        assert page.version()==original_version and source_hash(original_file)==original_hash
        version=saved[0][1][2]
        assert version['settings']['renderer']=='flux' and version['mode']=='generated'
        assert version['id']!=original_version['id']
        assert Image.open(version_path(w.project,version)).size==(640,800)
        # Reference/base assets remain portable and hash-based keys do not depend on directories.
        target=w.project.parent/'references'/'base.png';target.parent.mkdir(exist_ok=True)
        Image.new('RGB',(30,30)).save(target)
        settings=replace(Settings(),base=str(target),base_hash=source_hash(target),correction='skin')
        page.settings=settings;key=page.prediction_key()
        page.settings=replace(settings,base=str(root/'moved/base.png'))
        assert page.prediction_key()==key
        encoded=asset_paths({'settings':settings_dict(settings)},w.project.parent,relative=True)
        assert encoded['settings']['base']=='references/base.png'
        # Finished images are still viewable when the external original has moved.
        page.apply_options(original_version);page.path=root/'missing.png';page.error='';w.select_page();idle(w)
        assert not w.canvas.result.isNull()
        w.close();app.processEvents()
    finally:
        w.close();app.processEvents()
print('PASS legacy history unchanged, FLUX-only reprocessing, portable edit assets, missing-source viewing')
