"""Visual canvas region selector overlay and embedded canvas editor.

Provides two ways to define the canvas drawing area:
  - CanvasSelector: a frameless overlay window on top of the target window
  - CanvasEditor: an embedded widget for in-app tab-based editing
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QKeyEvent, QMouseEvent,
    QPaintEvent, QPixmap,
)
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from window_finder import WindowInfo

HANDLE_SIZE = 10
MIN_RECT = 20


class CanvasSelector(QWidget):
    """Overlay for visually selecting a canvas region within a window.

    Signals:
        confirmed(int, int, int, int): left, top, width, height (relative to window)
        cancelled()
    """

    confirmed = Signal(int, int, int, int)
    cancelled = Signal()

    def __init__(self, window: WindowInfo):
        super().__init__()

        self._win = window
        self._selection = QRect(0, 0, window.width, window.height)

        self._dragging = False
        self._drag_mode: str | None = None  # "move" | handle key like "tl", "tr", "bl", "br", "t", "b", "l", "r"
        self._drag_start = QPoint()
        self._drag_rect_start = QRect()

        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(self._win.left, self._win.top, self._win.width, self._win.height)
        self.setMouseTracking(True)

    # ── Public API ──────────────────────────────────────────────────────────

    def selection(self) -> tuple[int, int, int, int]:
        """Return current selection as (left, top, width, height)."""
        r = self._selection
        return (r.x(), r.y(), r.width(), r.height())

    # ── Keyboard ────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            r = self._selection
            self.confirmed.emit(r.x(), r.y(), r.width(), r.height())
            self.close()
        elif event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
        elif event.key() == Qt.Key_W:
            self._selection = QRect(0, 0, self._win.width, self._win.height)
            self.update()
        elif event.key() == Qt.Key_F:
            r = self._selection
            r.moveTo(0, 0)
            self._selection = r
            self.update()

    # ── Mouse ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        handle = self._hit_handle(pos)
        if handle:
            self._drag_mode = handle
            self._drag_start = pos
            self._drag_rect_start = QRect(self._selection)
            self._dragging = True
        elif self._selection.contains(pos):
            self._drag_mode = "move"
            self._drag_start = pos
            self._drag_rect_start = QRect(self._selection)
            self._dragging = True

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        if self._dragging:
            self._apply_drag(pos)
            self.update()
        else:
            handle = self._hit_handle(pos)
            if handle in ("tl", "br"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ("tr", "bl"):
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ("t", "b"):
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ("l", "r"):
                self.setCursor(Qt.SizeHorCursor)
            elif self._selection.contains(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self._drag_mode = None

    def _apply_drag(self, pos: QPoint):
        dx = pos.x() - self._drag_start.x()
        dy = pos.y() - self._drag_start.y()
        r = QRect(self._drag_rect_start)
        mode = self._drag_mode

        if mode == "move":
            r.translate(dx, dy)
            r.setLeft(max(0, r.left()))
            r.setTop(max(0, r.top()))
            r.setRight(min(self._win.width, r.right()))
            r.setBottom(min(self._win.height, r.bottom()))
        elif mode == "tl":
            r.setLeft(min(r.left() + dx, r.right() - MIN_RECT))
            r.setTop(min(r.top() + dy, r.bottom() - MIN_RECT))
        elif mode == "tr":
            r.setRight(max(r.right() + dx, r.left() + MIN_RECT))
            r.setTop(min(r.top() + dy, r.bottom() - MIN_RECT))
        elif mode == "bl":
            r.setLeft(min(r.left() + dx, r.right() - MIN_RECT))
            r.setBottom(max(r.bottom() + dy, r.top() + MIN_RECT))
        elif mode == "br":
            r.setRight(max(r.right() + dx, r.left() + MIN_RECT))
            r.setBottom(max(r.bottom() + dy, r.top() + MIN_RECT))
        elif mode == "t":
            r.setTop(min(r.top() + dy, r.bottom() - MIN_RECT))
        elif mode == "b":
            r.setBottom(max(r.bottom() + dy, r.top() + MIN_RECT))
        elif mode == "l":
            r.setLeft(min(r.left() + dx, r.right() - MIN_RECT))
        elif mode == "r":
            r.setRight(max(r.right() + dx, r.left() + MIN_RECT))

        # Clamp to window bounds
        r.setLeft(max(0, r.left()))
        r.setTop(max(0, r.top()))
        r.setRight(min(self._win.width, r.right()))
        r.setBottom(min(self._win.height, r.bottom()))

        self._selection = r

    def _hit_handle(self, pos: QPoint) -> str | None:
        """Return handle key if pos is over a handle, else None."""
        r = self._selection
        hs = HANDLE_SIZE
        # Corners first (they overlap with edges)
        corners = [
            ("tl", r.topLeft()),
            ("tr", r.topRight()),
            ("bl", r.bottomLeft()),
            ("br", r.bottomRight()),
        ]
        for key, p in corners:
            if QRect(p.x() - hs, p.y() - hs, hs * 2, hs * 2).contains(pos):
                return key
        # Edges
        mid_t = QPoint(r.center().x(), r.top())
        mid_b = QPoint(r.center().x(), r.bottom())
        mid_l = QPoint(r.left(), r.center().y())
        mid_r = QPoint(r.right(), r.center().y())
        edges = [
            ("t", mid_t, hs, hs * 2),
            ("b", mid_b, hs, hs * 2),
            ("l", mid_l, hs * 2, hs),
            ("r", mid_r, hs * 2, hs),
        ]
        for key, p, hw, hh in edges:
            if QRect(p.x() - hw, p.y() - hh, hw * 2, hh * 2).contains(pos):
                return key
        return None

    # ── Paint ───────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self._win.width, self._win.height
        sel = self._selection

        # Dim area outside the selection
        if sel.x() > 0:
            p.fillRect(0, 0, sel.x(), h, QColor(0, 0, 0, 100))
        if sel.right() < w:
            p.fillRect(sel.right(), 0, w - sel.right(), h, QColor(0, 0, 0, 100))
        if sel.y() > 0:
            p.fillRect(sel.x(), 0, sel.width(), sel.y(), QColor(0, 0, 0, 100))
        if sel.bottom() < h:
            p.fillRect(sel.x(), sel.bottom(), sel.width(), h - sel.bottom(), QColor(0, 0, 0, 100))

        # Selection fill
        p.fillRect(sel, QColor(0, 140, 255, 50))

        # Selection border
        pen = QPen(QColor(0, 140, 255, 200), 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(sel)

        # Handles
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        handle_rects = self._handle_rects()
        for hr in handle_rects:
            p.drawRoundedRect(hr, 2, 2)

        # Center text
        font = QFont("Consolas, monospace", 11)
        font.setBold(True)
        p.setFont(font)
        text = f"({sel.x()}, {sel.y()})  {sel.width()} x {sel.height()}"
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(sel, Qt.AlignCenter, text)

        # Help text at bottom-right
        help_font = QFont("Consolas, monospace", 9)
        p.setFont(help_font)
        help_text = "Drag handles  |  Enter=Confirm  |  Esc=Cancel  |  W=Full  |  F=Snap top-left"
        tm = p.fontMetrics()
        tw = tm.horizontalAdvance(help_text)
        th = tm.height()
        p.fillRect(0, h - th - 12, tw + 16, th + 8, QColor(0, 0, 0, 150))
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(8, h - th - 4, help_text)

        p.end()

    def _handle_rects(self) -> list[QRect]:
        hs = HANDLE_SIZE
        r = self._selection
        pts = [
            r.topLeft(), r.topRight(),
            r.bottomLeft(), r.bottomRight(),
            QPoint(r.center().x(), r.top()),
            QPoint(r.center().x(), r.bottom()),
            QPoint(r.left(), r.center().y()),
            QPoint(r.right(), r.center().y()),
        ]
        return [QRect(p.x() - hs, p.y() - hs, hs * 2, hs * 2) for p in pts]


def select_canvas(window: WindowInfo) -> CanvasSelector:
    """Create and show the canvas selector overlay. Returns the selector widget.

    Connect to confirmed(canvas_left, canvas_top, canvas_w, canvas_h) and
    cancelled() signals before calling show().
    """
    from window_finder import WindowInfo
    selector = CanvasSelector(window)
    return selector


# ═══════════════════════════════════════════════════════════════════════════════
# Embedded Canvas Editor (for in-app tab, not overlay)
# ═══════════════════════════════════════════════════════════════════════════════

_EDITOR_MIN_RECT = 20
_EDITOR_HANDLE = 8


class CanvasEditor(QWidget):
    """Embedded widget showing a window screenshot with a resizable selection.

    The user drags a rectangle over the screenshot to define the canvas area.
    Coordinates are always in *window space* — the same coordinate system
    used by the canvas-offset spinboxes.

    Signals:
        selection_changed(int, int, int, int): left, top, width, height
    """

    selection_changed = Signal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._win_w = 0
        self._win_h = 0
        self._selection = QRect()
        self._dragging = False
        self._drag_mode: str | None = None
        self._drag_start = QPoint()
        self._drag_rect_start = QRect()
        self._scale = 1.0
        self._off_x = 0.0
        self._off_y = 0.0

        self.setMinimumSize(200, 150)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_screenshot(self, pixmap: QPixmap, win_w: int, win_h: int):
        """Load a new window screenshot and reset selection to full window."""
        self._pixmap = pixmap
        self._win_w = win_w
        self._win_h = win_h
        self._selection = QRect(0, 0, win_w, win_h)
        self._recalc_scale()
        self.update()

    def set_selection(self, left: int, top: int, width: int, height: int):
        """Programmatically update the selection rectangle (window coords)."""
        r = QRect(left, top, width, height)
        r.setLeft(max(0, r.left()))
        r.setTop(max(0, r.top()))
        r.setRight(min(self._win_w or 99999, r.right()))
        r.setBottom(min(self._win_h or 99999, r.bottom()))
        if r != self._selection:
            self._selection = r
            self.update()

    def selection(self) -> tuple[int, int, int, int]:
        """Return current selection as (left, top, width, height)."""
        r = self._selection
        return (r.x(), r.y(), r.width(), r.height())

    def has_screenshot(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    # ── Coordinate helpers ─────────────────────────────────────────────────

    def _recalc_scale(self):
        """Recompute scale and offset so the screenshot fits centered."""
        if self._pixmap is None or self._win_w <= 0 or self._win_h <= 0:
            self._scale = 1.0
            self._off_x = 0.0
            self._off_y = 0.0
            return
        cw = self.width()
        ch = self.height()
        if cw <= 0 or ch <= 0:
            return
        self._scale = min(cw / self._win_w, ch / self._win_h)
        self._off_x = (cw - self._win_w * self._scale) / 2.0
        self._off_y = (ch - self._win_h * self._scale) / 2.0

    def _to_widget_point(self, p: QPoint) -> QPoint:
        return QPoint(
            int(p.x() * self._scale + self._off_x),
            int(p.y() * self._scale + self._off_y),
        )

    def _to_widget_rect(self, r: QRect) -> QRect:
        tl = self._to_widget_point(r.topLeft())
        br = self._to_widget_point(r.bottomRight())
        return QRect(tl, br)

    def _to_window_point(self, p: QPoint) -> QPoint:
        return QPoint(
            int((p.x() - self._off_x) / self._scale),
            int((p.y() - self._off_y) / self._scale),
        )

    # ── Resize ─────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalc_scale()

    # ── Keyboard ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_W:
            self._selection = QRect(0, 0, self._win_w, self._win_h)
            self._emit_selection()
            self.update()
        elif event.key() == Qt.Key_F:
            r = self._selection
            r.moveTo(0, 0)
            self._selection = r
            self._emit_selection()
            self.update()

    # ── Mouse ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton or not self.has_screenshot():
            return
        pos = event.position().toPoint()
        handle = self._hit_handle(pos)
        win_sel = self._to_widget_rect(self._selection)
        if handle:
            self._drag_mode = handle
            self._drag_start = pos
            self._drag_rect_start = QRect(self._selection)
            self._dragging = True
        elif win_sel.contains(pos):
            self._drag_mode = "move"
            self._drag_start = pos
            self._drag_rect_start = QRect(self._selection)
            self._dragging = True

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        if self._dragging:
            self._apply_drag(pos)
            self.update()
            self._emit_selection()
        elif self.has_screenshot():
            handle = self._hit_handle(pos)
            if handle in ("tl", "br"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ("tr", "bl"):
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ("t", "b"):
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ("l", "r"):
                self.setCursor(Qt.SizeHorCursor)
            elif self._to_widget_rect(self._selection).contains(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self._drag_mode = None

    def _apply_drag(self, pos: QPoint):
        wpos = self._to_window_point(pos)
        wstart = self._to_window_point(self._drag_start)
        dx = wpos.x() - wstart.x()
        dy = wpos.y() - wstart.y()
        r = QRect(self._drag_rect_start)
        mode = self._drag_mode

        if mode == "move":
            r.translate(dx, dy)
            r.setLeft(max(0, r.left()))
            r.setTop(max(0, r.top()))
            r.setRight(min(self._win_w, r.right()))
            r.setBottom(min(self._win_h, r.bottom()))
        elif mode == "tl":
            r.setLeft(min(r.left() + dx, r.right() - _EDITOR_MIN_RECT))
            r.setTop(min(r.top() + dy, r.bottom() - _EDITOR_MIN_RECT))
        elif mode == "tr":
            r.setRight(max(r.right() + dx, r.left() + _EDITOR_MIN_RECT))
            r.setTop(min(r.top() + dy, r.bottom() - _EDITOR_MIN_RECT))
        elif mode == "bl":
            r.setLeft(min(r.left() + dx, r.right() - _EDITOR_MIN_RECT))
            r.setBottom(max(r.bottom() + dy, r.top() + _EDITOR_MIN_RECT))
        elif mode == "br":
            r.setRight(max(r.right() + dx, r.left() + _EDITOR_MIN_RECT))
            r.setBottom(max(r.bottom() + dy, r.top() + _EDITOR_MIN_RECT))
        elif mode == "t":
            r.setTop(min(r.top() + dy, r.bottom() - _EDITOR_MIN_RECT))
        elif mode == "b":
            r.setBottom(max(r.bottom() + dy, r.top() + _EDITOR_MIN_RECT))
        elif mode == "l":
            r.setLeft(min(r.left() + dx, r.right() - _EDITOR_MIN_RECT))
        elif mode == "r":
            r.setRight(max(r.right() + dx, r.left() + _EDITOR_MIN_RECT))

        r.setLeft(max(0, r.left()))
        r.setTop(max(0, r.top()))
        r.setRight(min(self._win_w, r.right()))
        r.setBottom(min(self._win_h, r.bottom()))
        self._selection = r

    def _hit_handle(self, pos: QPoint) -> str | None:
        r = self._to_widget_rect(self._selection)
        hs = _EDITOR_HANDLE
        corners = [
            ("tl", r.topLeft()), ("tr", r.topRight()),
            ("bl", r.bottomLeft()), ("br", r.bottomRight()),
        ]
        for key, p in corners:
            if QRect(p.x() - hs, p.y() - hs, hs * 2, hs * 2).contains(pos):
                return key
        edges = [
            ("t", QPoint(r.center().x(), r.top()), hs, hs * 2),
            ("b", QPoint(r.center().x(), r.bottom()), hs, hs * 2),
            ("l", QPoint(r.left(), r.center().y()), hs * 2, hs),
            ("r", QPoint(r.right(), r.center().y()), hs * 2, hs),
        ]
        for key, p, hw, hh in edges:
            if QRect(p.x() - hw, p.y() - hh, hw * 2, hh * 2).contains(pos):
                return key
        return None

    def _emit_selection(self):
        r = self._selection
        self.selection_changed.emit(r.x(), r.y(), r.width(), r.height())

    # ── Paint ───────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cw, ch = self.width(), self.height()

        # Background
        p.fillRect(0, 0, cw, ch, QColor("#2b2b2b"))

        if not self.has_screenshot():
            p.setPen(QColor("#888"))
            font = QFont("Consolas, monospace", 11)
            p.setFont(font)
            p.drawText(QRect(0, 0, cw, ch), Qt.AlignCenter, "No window selected")
            p.end()
            return

        # Screenshot centered
        draw_rect = QRect(
            int(self._off_x), int(self._off_y),
            int(self._win_w * self._scale), int(self._win_h * self._scale),
        )
        p.drawPixmap(draw_rect, self._pixmap)

        # Widget-space selection rect
        wsel = self._to_widget_rect(self._selection)

        # Dim outside the selection
        dim = QColor(0, 0, 0, 140)
        if wsel.x() > draw_rect.x():
            p.fillRect(draw_rect.x(), draw_rect.y(),
                       wsel.x() - draw_rect.x(), draw_rect.height(), dim)
        if wsel.right() < draw_rect.right():
            p.fillRect(wsel.right(), draw_rect.y(),
                       draw_rect.right() - wsel.right(), draw_rect.height(), dim)
        if wsel.y() > draw_rect.y():
            p.fillRect(wsel.x(), draw_rect.y(),
                       wsel.width(), wsel.y() - draw_rect.y(), dim)
        if wsel.bottom() < draw_rect.bottom():
            p.fillRect(wsel.x(), wsel.bottom(),
                       wsel.width(), draw_rect.bottom() - wsel.bottom(), dim)

        # Selection fill
        p.fillRect(wsel, QColor(0, 140, 255, 50))

        # Selection border
        pen = QPen(QColor(0, 180, 255, 220), 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(wsel)

        # Handles
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        for hr in self._editor_handle_rects():
            p.drawRoundedRect(hr, 2, 2)

        # Size / position text
        sel = self._selection
        font = QFont("Consolas, monospace", 10)
        font.setBold(True)
        p.setFont(font)
        text = f"({sel.x()}, {sel.y()})  {sel.width()} x {sel.height()}"
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(wsel, Qt.AlignCenter, text)

        # Help text
        help_font = QFont("Consolas, monospace", 8)
        p.setFont(help_font)
        help_text = "Drag handles  |  W=Full  |  F=Snap top-left"
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(help_text)
        th = fm.height()
        p.fillRect(0, ch - th - 10, tw + 12, th + 6, QColor(0, 0, 0, 150))
        p.setPen(QColor(255, 255, 255, 180))
        p.drawText(6, ch - th + 2, help_text)

        p.end()

    def _editor_handle_rects(self) -> list[QRect]:
        hs = _EDITOR_HANDLE
        r = self._to_widget_rect(self._selection)
        pts = [
            r.topLeft(), r.topRight(),
            r.bottomLeft(), r.bottomRight(),
            QPoint(r.center().x(), r.top()),
            QPoint(r.center().x(), r.bottom()),
            QPoint(r.left(), r.center().y()),
            QPoint(r.right(), r.center().y()),
        ]
        return [QRect(p.x() - hs, p.y() - hs, hs * 2, hs * 2) for p in pts]