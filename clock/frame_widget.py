"""Фон циферблата + золотая обводка, работающая как прогресс-бар (v3)"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath

from config import (
    COLOR_BG, COLOR_FRAME_GOLD, COLOR_FRAME_GOLD_DIM,
    FRAME_RADIUS, FRAME_BORDER_WIDTH,
)


class FrameWidget(QWidget):
    """Центральный виджет окна: рисует фон и золотую рамку.

    Рамка состоит из двух слоёв:
      - тусклая база — полный периметр, видна всегда (гарантирует
        требование ТЗ "обводка золотого цвета" даже когда прогресс = 0);
      - яркая часть — оставшаяся доля периметра, "стирается" по часовой
        стрелке от левого верхнего угла (см. set_progress).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 1.0  # доля периметра, которая ещё "горит" (1.0 = полностью)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

    def set_progress(self, lit_fraction: float):
        lit_fraction = max(0.0, min(1.0, lit_fraction))
        if abs(lit_fraction - self._progress) > 0.0005:
            self._progress = lit_fraction
            self.update()

    @staticmethod
    def _point_at_fraction(rect: QRectF, frac: float) -> QPointF:
        """0.0 = левый верхний угол, далее по часовой стрелке."""
        frac = frac % 1.0
        w, h = rect.width(), rect.height()
        perim = 2 * (w + h)
        dist = frac * perim

        if dist <= w:  # верхняя грань, слева направо
            return QPointF(rect.left() + dist, rect.top())
        dist -= w
        if dist <= h:  # правая грань, сверху вниз
            return QPointF(rect.right(), rect.top() + dist)
        dist -= h
        if dist <= w:  # нижняя грань, справа налево
            return QPointF(rect.right() - dist, rect.bottom())
        dist -= w
        return QPointF(rect.left(), rect.bottom() - dist)  # левая грань, снизу вверх

    def _build_path(self, rect: QRectF, start_frac: float) -> QPainterPath:
        corners = (0.25, 0.5, 0.75, 1.0)
        stops = [f for f in corners if f > start_frac]
        fracs = [start_frac] + stops

        path = QPainterPath()
        path.moveTo(self._point_at_fraction(rect, fracs[0]))
        for f in fracs[1:]:
            path.lineTo(self._point_at_fraction(rect, f))
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        half = FRAME_BORDER_WIDTH / 2
        rect = QRectF(self.rect()).adjusted(half, half, -half, -half)

        # Фон панели
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_BG))
        painter.drawRoundedRect(rect, FRAME_RADIUS, FRAME_RADIUS)

        # Тусклая база обводки — весь периметр
        dim_pen = QPen(QColor(COLOR_FRAME_GOLD_DIM), FRAME_BORDER_WIDTH)
        dim_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(dim_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, FRAME_RADIUS, FRAME_RADIUS)

        # Яркая обводка — оставшаяся доля периметра (прогресс-бар)
        if self._progress > 0.001:
            erased = 1.0 - self._progress
            bright_pen = QPen(QColor(COLOR_FRAME_GOLD), FRAME_BORDER_WIDTH)
            bright_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            bright_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(bright_pen)
            painter.drawPath(self._build_path(rect, erased))
