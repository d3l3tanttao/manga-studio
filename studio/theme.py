STYLE = """
QWidget { color: #eeedf4; background: #191c25; font: 10pt 'Segoe UI'; }
QMainWindow, QWidget#root { background: #171a22; }
QFrame#header, QFrame#foot { background: #1c1e28; }
QFrame#rail { background: #1e212b; border: 1px solid #343744; border-radius: 12px; }
QWidget#transparent, QFrame#rail QLabel, QFrame#header QLabel, QFrame#foot QLabel { background: transparent; }
QLabel#brand { font-size: 17pt; font-weight: 700; }
QLabel#title { font-size: 14pt; font-weight: 650; }
QLabel#section { color: #c3b0ec; font-size: 9pt; font-weight: 700; }
QLabel#muted { color: #b1b3c3; font-size: 9pt; }
QLabel#badge { background: #373044; color: #dec6ff; font-size: 9pt; border-radius: 8px; padding: 4px 9px; }
QPushButton, QComboBox, QSpinBox, QLineEdit { background: #2b2e3a; border: 1px solid #444755;
    border-radius: 7px; padding: 6px 10px; min-height: 18px; }
QPushButton:hover, QComboBox:hover { background: #373947; border-color: #85729d; }
QPushButton:checked { background: #433752; color: #ead7ff; border-color: #9e7bc3; }
QPushButton:disabled, QComboBox:disabled { background: #262932; color: #7c7f8e; border-color: #353743; }
QPushButton#primary { background: #c5a4ed; color: #241c2d; border: 0; font-weight: 700; padding: 10px; }
QPushButton#primary:hover { background: #d5b6fa; }
QPushButton#primary:disabled { background: #53485f; color: #b6a9c5; }
QPushButton#quiet { background: transparent; border-color: transparent; color: #babcca; }
QPushButton#quiet:hover { background: #30323f; }
QPushButton:focus, QComboBox:focus, QListWidget:focus { border: 1px solid #ba98dc; }
QListWidget { background: #191c25; border: 1px solid #323541; border-radius: 8px; padding: 4px; outline: 0; }
QListWidget::item { border-radius: 5px; padding: 5px 3px; }
QListWidget::item:selected { background: #3c334a; color: white; }
QComboBox QAbstractItemView { background: #2a2c38; color: white; selection-background-color: #4d3e60; }
QToolTip { background: #323441; color: white; border: 1px solid #676377; padding: 5px; }
QScrollArea { background: transparent; border: 0; }
QProgressBar { border: 0; background: #373946; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #b09ad5; border-radius: 3px; }
QLabel#issue { color: #f3c6a8; background: #382e2b; padding: 5px; border-radius: 5px; }
QTabWidget::pane { border: 1px solid #343744; border-radius: 6px; }
QTabBar::tab { background: #272a35; color: #bec0cd; padding: 7px 9px; }
QTabBar::tab:selected { color: #e6d7ff; background: #403748; border-bottom: 2px solid #bd9ce3; }
QSplitter::handle:hover { background: #6b577d; }
QMenu { background: #272a35; color: #eeedf4; }
QMenu::item { padding: 6px 12px; }
QMenu::item:selected { background: #443955; }
QSlider::groove:horizontal { height: 5px; background: #454050; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ae8fd0; }
QSlider::handle:horizontal { width: 15px; margin: -5px 0; border-radius: 7px; background: #ddc6fa; }
"""
