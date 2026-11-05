"""Reference palettes use user-selected source regions, never redraw the target scan."""
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout

from .canvas import Canvas
from .engine import open_page
from .i18n import tr
from . import layout


class ReferenceDialog(QDialog):
    def __init__(self,path,parent):
        super().__init__(parent)
        self.setWindowTitle(tr('Цвет из референса'));self.resize(850,750)
        self.color=QColor()
        self.original=open_page(path)
        lay=QVBoxLayout(self)
        lay.addWidget(layout.label(tr('Обведите материал на референсе. Будет взят его средний цвет.')))
        self.canvas=Canvas();self.canvas.tool='lasso';self.canvas.view='original'
        pixels=self.original.tobytes()
        image=QImage(pixels,self.original.width,self.original.height,self.original.width*3,QImage.Format_RGB888).copy()
        self.canvas.load_page(QPixmap.fromImage(image),QPixmap(),[])
        self.canvas.stroked.connect(self.selected);lay.addWidget(self.canvas,1)
        self.label=layout.label('');lay.addWidget(self.label)
        self.accept_button=layout.button(tr('Применить цвет'),self.accept,'primary');self.accept_button.setEnabled(False)
        layout.row(lay,self.accept_button,layout.button(tr('Отмена'),self.reject))

    def selected(self,stroke):
        from .regions import paint_mask
        mask=paint_mask(np.zeros((self.original.height,self.original.width),np.uint8),stroke.points,stroke.width,True,True)
        pixels=np.asarray(self.original)[mask>0]
        if not len(pixels):return
        # Ignore ink and extreme highlights when enough material pixels are available.
        bright=pixels.max(1);mid=pixels[(bright>40)&(pixels.min(1)<245)]
        if len(mid)>10:pixels=mid
        value=np.median(pixels,axis=0).astype(int)
        self.color=QColor(*value.tolist());self.label.setText(self.color.name().upper())
        self.accept_button.setEnabled(True)
