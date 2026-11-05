"""Primary AI workspace accessibility/layout for all existing locales, no model."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_SCALE_FACTOR','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from studio.i18n import LANGUAGES
from studio.window import Window
from studio.theme import STYLE
from check_desktop import idle

app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
for file in ('segoeui.ttf','seguisb.ttf','segoeuib.ttf','seguisym.ttf','Nirmala.ttc','msyh.ttc','msjh.ttc','YuGothR.ttc','malgun.ttf'):
    p=Path(os.environ['WINDIR'])/'Fonts'/file
    if p.is_file():QFontDatabase.addApplicationFont(str(p))
sample=Path(__file__).resolve().parents[1]/'studio/assets/jacket.png'
for code in LANGUAGES:
    with TemporaryDirectory(dir=Path.cwd()) as folder:
        config=QSettings(str(Path(folder)/'ui.ini'),QSettings.IniFormat);config.setValue('language',code)
        w=Window(config);w.resize(940,610);w.show();app.processEvents()
        try:
            w.add_paths([sample]);idle(w)
            w.set_ai_reference(sample);idle(w)
            scroll=w.ai_stack.widget(0)
            assert scroll.widget().width()<=scroll.viewport().width(),(code,'horizontal clipping')
            for widget in (w.ai_mode,w.ai_reference_btn,w.ai_clear_reference,w.ai_apply,w.ai_variant):
                scroll.ensureWidgetVisible(widget);app.processEvents()
                assert widget.visibleRegion().contains(widget.rect().center()),(code,widget.text() if hasattr(widget,'text') else 'mode')
            w.ai_mode.setCurrentIndex(w.ai_mode.findData('color'))
            assert not w.current().settings.reference and not w.ai_ref_image.isVisible()
            w.assign_color();assert w.canvas.tool=='paint'
            w.ai_manual.setChecked(False);assert w.canvas.tool=='view'
            assert not w.set_color_btn.isVisible()
            w.ai_advanced_toggle.setChecked(True);app.processEvents()
            assert scroll.widget().width()<=scroll.viewport().width(),(code,'advanced clipping')
        finally:
            idle(w);w.close();app.processEvents()
    print('PASS primary UI',code,flush=True)
