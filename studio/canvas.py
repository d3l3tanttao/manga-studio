from .i18n import tr
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .engine import Stroke


class Canvas(QWidget):
    open_requested = Signal()
    stroked = Signal(object)
    scale_changed = Signal(int)
    moved = Signal()
    picked = Signal(object)
    sampled = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(280, 240)
        self.setMouseTracking(True)
        self.original = QPixmap()
        self.result = QPixmap()
        self.before = QPixmap()
        self.show_marks = True
        self.sample_source = "result"
        self.view = "compare"
        self.tool = "view"
        self.diameter = 18
        self.guides = True
        self.hover = None
        self.color = QColor("#e49573")
        self.strokes = []
        self.current = []
        self.split = 0.5
        self.zoom = 1.0
        self.native_scale = None
        self.pan = QPointF()
        self.drag = ""
        self.last = QPointF()
        self.error = ""

    def load_page(self, original, result, strokes, reset=True):
        self.original, self.result = original, result
        self.strokes = strokes
        self.current = []
        self.drag = ""
        if reset:
            self.fit()
        self.update()

    def page_rect(self):
        if self.original.isNull():
            return QRectF()
        fit = min((self.width() - 36) / self.original.width(),
                  (self.height() - 32) / self.original.height())
        scale = self.native_scale / self.devicePixelRatioF() if self.native_scale else fit * self.zoom
        w, h = self.original.width() * scale, self.original.height() * scale
        return QRectF((self.width() - w) / 2 + self.pan.x(), (self.height() - h) / 2 + self.pan.y(), w, h)

    def fit(self):
        self.zoom, self.pan = 1.0, QPointF()
        self.native_scale = None
        self.report_scale()

    def report_scale(self):
        if not self.original.isNull():
            self.scale_changed.emit(round(self.page_rect().width() * self.devicePixelRatioF() / self.original.width() * 100))
        self.update()

    def zoom_by(self, factor, point=None):
        if self.original.isNull():
            return
        old = self.zoom
        previous_scale = self.page_rect().width() * self.devicePixelRatioF() / self.original.width()
        maximum = max(12, 4 * self.original.width() * old / (self.page_rect().width() * self.devicePixelRatioF()))
        self.zoom = max(0.05, min(maximum, old * factor))
        anchor = (point or QPointF(self.rect().center())) - QPointF(self.rect().center())
        self.pan = anchor + (self.pan - anchor) * (self.zoom / old)
        self.native_scale = previous_scale * self.zoom / old
        self.report_scale()
        self.moved.emit()

    def actual_size(self):
        if not self.original.isNull():
            self.zoom_by(self.original.width() / (self.devicePixelRatioF() * self.page_rect().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.report_scale()

    def wheelEvent(self, event):
        self.zoom_by(1.2 ** (event.angleDelta().y() / 120), event.position())
        event.accept()

    def split_x(self):
        rect = self.page_rect().intersected(QRectF(self.rect()))
        return rect.left() + rect.width() * self.split

    def normalized(self, pos):
        rect = self.page_rect()
        return (min(1, max(0, (pos.x() - rect.left()) / rect.width())),
                min(1, max(0, (pos.y() - rect.top()) / rect.height())))

    def mousePressEvent(self, event):
        if self.original.isNull():
            if not self.error and event.button() == Qt.LeftButton:
                self.open_requested.emit()
            return
        pos = event.position()
        self.last = pos
        if event.button() == Qt.MiddleButton:
            self.drag = "pan"
        elif event.button() == Qt.LeftButton:
            temporary_pick = bool(event.modifiers() & Qt.AltModifier)
            if (self.tool == "pick" or temporary_pick) and self.page_rect().contains(pos):
                picture = self.original if self.sample_source == "original" or self.result.isNull() else self.result
                x, y = self.normalized(pos)
                signal = self.sampled if temporary_pick else self.picked
                signal.emit(picture.toImage().pixelColor(round(x * (picture.width()-1)), round(y * (picture.height()-1))))
                return
            if self.tool != "view" and self.page_rect().contains(pos):
                self.drag = "stroke"
                self.current = [self.normalized(pos)]
            elif self.guides and self.view in ("compare","previous") and not self.result.isNull() and abs(pos.x() - self.split_x()) < 14:
                self.drag = "split"
            else:
                self.drag = "pan"
        self.update()

    def mouseMoveEvent(self, event):
        if self.original.isNull():
            return
        pos = event.position()
        self.hover = pos
        if self.drag == "pan":
            self.pan += pos - self.last
        elif self.drag == "split":
            rect = self.page_rect().intersected(QRectF(self.rect()))
            if rect.width() > 0:
                self.split = max(0, min(1, (pos.x() - rect.left()) / rect.width()))
        elif self.drag == "stroke":
            self.extend_stroke(pos)
        self.last = pos
        split_hover = self.view in ("compare","previous") and not self.result.isNull() and abs(pos.x() - self.split_x()) < 14
        self.setCursor(Qt.CrossCursor if self.tool != "view" else Qt.SizeHorCursor if split_hover and self.guides else Qt.OpenHandCursor)
        self.update()

    def extend_stroke(self, pos):
        rect = self.page_rect()
        end = ((pos.x()-rect.x())/rect.width(), (pos.y()-rect.y())/rect.height())
        x,y = self.current[-1]
        dx,dy = end[0]-x,end[1]-y
        t = 1.0
        for origin,step in ((x,dx),(y,dy)):
            if step:
                limit = ((1 if step > 0 else 0)-origin)/step
                t = min(t,limit)
        point = (min(1,max(0,x+t*dx)),min(1,max(0,y+t*dy)))
        if point != self.current[-1]:
            self.current.append(point)
        if not rect.contains(pos):
            self.commit_stroke()

    def commit_stroke(self):
        points = tuple(self.current)
        self.drag, self.current = "", []
        if points and (self.tool != "lasso" or len(set(points)) >= 3):
            self.stroked.emit(Stroke(self.color.getRgb()[:3],self.diameter/self.original.width(),points,self.tool))

    def mouseReleaseEvent(self, event):
        if self.drag == "stroke" and self.current:
            self.extend_stroke(event.position())
            if self.current:
                self.commit_stroke()
        if self.drag in ("pan", "split"):
            self.moved.emit()
        self.drag = ""
        self.current = []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#11141b"))
        if self.original.isNull():
            self.paint_empty(p)
            p.end()
            return
        rect = self.page_rect()
        p.fillRect(rect.translated(3, 4), QColor("#0b0d12"))
        base = self.before if self.view=="previous" and not self.before.isNull() else self.original
        p.drawPixmap(rect, base, QRectF(base.rect()))
        compare = self.tool == "view" and not self.result.isNull() and self.view in ("compare","previous")
        original_pick = self.tool=="pick" and self.sample_source=="original"
        if not self.result.isNull() and self.view != "original" and not original_pick:
            p.save()
            if compare:
                p.setClipRect(QRectF(self.split_x(), 0, self.width(), self.height()))
            p.drawPixmap(rect, self.result, QRectF(self.result.rect()))
            p.restore()
        if compare and self.guides:
            x = self.split_x()
            visible = rect.intersected(QRectF(self.rect()))
            mid = visible.center().y()
            p.setPen(QPen(QColor("#f3eefe"), 2))
            p.drawLine(QPointF(x, visible.top()), QPointF(x, visible.bottom()))
            p.setBrush(QColor("#7860be"))
            p.drawEllipse(QPointF(x, mid), 15, 15)
            p.drawText(QRectF(x - 14, mid - 14, 28, 28), Qt.AlignCenter, "‹ ›")
            for name, side in (((tr("До правки") if self.view=="previous" else tr("Оригинал")), QRectF(visible.left(), visible.top(), x-visible.left(), 25)),
                               (tr("Предпросмотр"), QRectF(x, visible.top(), visible.right()-x, 25))):
                tag_width = p.fontMetrics().horizontalAdvance(name) + 14
                if side.width() >= tag_width + 8:
                    tag = QRectF(side.left()+4, side.top()+4, tag_width, 21)
                    p.fillRect(tag, QColor(28, 29, 39, 210))
                    p.drawText(tag, Qt.AlignCenter, name)
        if self.show_marks and self.view != "previous":
            for stroke in self.strokes:
                if stroke.kind == "hint":
                    self.paint_stroke(p, rect, stroke)
        if self.current:
            stroke = Stroke(self.color.getRgb()[:3], self.diameter / self.original.width(), self.current, self.tool)
            if self.tool == "restore":
                points = [QPointF(rect.x()+x*rect.width(), rect.y()+y*rect.height()) for x,y in self.current]
                path = QPainterPath(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                pen = QPainterPathStroker()
                pen.setWidth(stroke.width * rect.width())
                pen.setCapStyle(Qt.RoundCap)
                clip = pen.createStroke(path)
                radius = stroke.width * rect.width() / 2
                clip.addEllipse(points[0], radius, radius)
                p.save()
                p.setClipPath(clip)
                p.drawPixmap(rect, self.original, QRectF(self.original.rect()))
                p.restore()
            elif self.tool in ("paint","lasso"):
                color = QColor(self.color)
                color.setAlpha(100)
                pts = [QPointF(rect.x()+x*rect.width(),rect.y()+y*rect.height()) for x,y in self.current]
                if self.tool == "lasso":
                    p.setBrush(color)
                    p.setPen(QPen(self.color,1,Qt.DashLine))
                    p.drawPolygon(pts)
                else:
                    p.setPen(QPen(color,max(1,self.diameter*rect.width()/self.original.width()),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
                    if len(pts)>1:
                        p.drawPolyline(pts)
                    else:
                        p.drawPoint(pts[0])
            elif self.tool == "hint":
                self.paint_stroke(p, rect, stroke)
        if self.tool in ("hint","restore","erase","paint") and self.hover and rect.contains(self.hover):
            radius = self.diameter * rect.width() / (2*self.original.width())
            p.setBrush(Qt.NoBrush)
            for color, width in (("#24212a", 3), ("#ffffff", 1)):
                p.setPen(QPen(QColor(color), width))
                p.drawEllipse(self.hover, radius, radius)
        p.end()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    @staticmethod
    def paint_stroke(p, rect, stroke):
        points = [QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height()) for x, y in stroke.points]
        p.setPen(QPen(QColor(*stroke.color), max(2, stroke.width * rect.width()),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if len(points) == 1:
            p.drawPoint(points[0])
        else:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            p.drawPath(path)

    def paint_empty(self, p):
        cx, cy = self.width() / 2, self.height() / 2
        p.setPen(QPen(QColor("#353044"), 1))
        p.setBrush(QColor("#232330"))
        p.drawRoundedRect(QRectF(cx - 40, cy - 100, 77, 89), 8, 8)
        p.setBrush(QColor("#343043"))
        p.drawRoundedRect(QRectF(cx - 29, cy - 91, 77, 89), 8, 8)
        for i, color in enumerate(("#b6a0ee", "#e7ab8d", "#8bc5b1")):
            p.fillRect(QRectF(cx - 18, cy - 78 + i * 20, 50 - i * 7, 12), QColor(color))
        p.setPen(QColor("#edeaf2"))
        p.setFont(QFont("Segoe UI", 15, QFont.DemiBold))
        p.drawText(QRectF(2, cy + 15, self.width() - 4, 35), Qt.AlignCenter,
                   tr("Не удалось открыть страницу") if self.error else tr("Перетащите страницы сюда"))
        p.setPen(QColor("#aaa9b8"))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(10, cy + 55, self.width() - 20, 52), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                   self.error or tr("Или нажмите, чтобы выбрать PNG и JPEG"))
