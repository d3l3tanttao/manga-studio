"""Offline UI catalogs. Internal tool IDs and chapter data are language independent."""
import json
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator, Qt
from PySide6.QtWidgets import QApplication


LANGUAGES = {
    "ar":"العربية", "bn":"বাংলা", "de":"Deutsch", "en":"English", "es":"Español", "fa":"فارسی",
    "fr":"Français", "ha":"Hausa", "hi":"हिन्दी", "id":"Bahasa Indonesia", "it":"Italiano",
    "ja":"日本語", "ko":"한국어", "mr":"मराठी", "pa":"ਪੰਜਾਬੀ", "pt-BR":"Português (Brasil)",
    "ru":"Русский", "sw":"Kiswahili", "ta":"தமிழ்", "te":"తెలుగు", "tr":"Türkçe",
    "ur":"اردو", "vi":"Tiếng Việt", "zh-Hans":"简体中文", "zh-Hant":"繁體中文",
}
CATALOGS = Path(__file__).with_name("locales")
_code = "ru"
_strings = {}
_qt = None


def resolve(tag):
    tag = tag.replace("_","-").lower()
    if tag.startswith("zh"):
        return "zh-Hant" if any(s in tag for s in ("hant","tw","hk","mo")) else "zh-Hans"
    if tag.startswith("pt"):
        return "pt-BR"
    return next((key for key in LANGUAGES if key == tag.split("-")[0]),"en")


def configure(setting):
    global _code, _strings, _qt
    _code = resolve(QLocale.system().bcp47Name() if setting=="auto" else setting)
    _strings = json.loads((CATALOGS / (_code+".json")).read_text(encoding="utf-8"))
    app = QApplication.instance()
    if app:
        if _qt is not None:
            app.removeTranslator(_qt)
        locale = QLocale(_code)
        QLocale.setDefault(locale)
        app.setLayoutDirection(Qt.RightToLeft if _code in ("ar","fa","ur") else Qt.LeftToRight)
        _qt = QTranslator(app)
        if _qt.load(locale,"qtbase","_",QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(_qt)


def language_code():
    return _code


def tr(source, *args):
    text = _strings.get(source,source)
    return text.format(*args) if args else text
