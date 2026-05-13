"""Virtual whiteboard — auto-draw contours then manual edit, export to target window."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPixmap, QKeyEvent,
    QMouseEvent, QWheelEvent, QPaintEvent, QCloseEvent, QResizeEvent,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFrame,
)

import numpy as np

BUTTON_STYLE = """
    QPushButton {
        background: rgba(60,60,60,0.85); color: #e0e0e0;
        border: 1px solid rgba(255,255,255,0.15); border-radius: 3px;
        padding: 3px 10px; font-size: 11px;
    }
    QPushButton:hover { background: rgba(80,80,80,0.9); }
    QPushButton:checked { background: #3a6fc5; color: white; border-color: #5a8fe5; }
    QPushButton:disabled { color: #666; }
"""

TOOLBAR_BG = "background: rgba(32,32,32,0.82); border-radius: 6px;"


@dataclass
class BoardConfig:
    canvas_width: int = 800
    canvas_height: int = 600
    brush_color: str = "#000000"
    brush_width: int = 3
    auto_draw_speed: float = 0.002


class VirtualCanvas(QWidget):
    confirmed_to_window = Signal(str)
    saved = Signal(str)
    closed = Signal()

    def __init__(self, contours: list, img_w: int, img_h: int, cfg: BoardConfig):
        super().__init__()
        self._cfg = cfg
        self._contours = contours
        self._img_w = img_w
        self._img_h = img_h

        self._pixmap: QPixmap | None = None
        self._init_pixmap()

        # Auto-draw
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._auto_draw_active = False
        self._auto_draw_paused = False
        self._auto_draw_finished = not contours
        self._current_contour_idx = 0
        self._current_point_idx = 0
        self._scaled_contours: list[np.ndarray] = []

        # Manual draw
        self._drawing = False
        self._last_pos = None
        self._edit_mode = "brush"  # "brush" | "eraser"

        # Current appearance (can be changed via toolbar)
        self._pen_color = QColor(cfg.brush_color)
        self._pen_width = cfg.brush_width

        self._init_ui()

        if contours:
            self._prepare_contours()
            self._start_auto_draw()
        else:
            self._update_toolbar_state()

    # ── Pixmap ───────────────────────────────────────────────────────────────

    def _init_pixmap(self):
        self._pixmap = QPixmap(self._cfg.canvas_width, self._cfg.canvas_height)
        self._pixmap.fill(Qt.white)

    def canvas_pixmap(self) -> QPixmap:
        return QPixmap(self._pixmap) if self._pixmap else QPixmap()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("Image Drawer — Board")
        self.resize(self._cfg.canvas_width + 40, self._cfg.canvas_height + 110)
        self.setMinimumSize(320, 200)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Toolbar
        self._toolbar = QFrame(self)
        self._toolbar.setStyleSheet(TOOLBAR_BG)
        self._toolbar.setFixedHeight(40)
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(8, 4, 8, 4)
        tb.setSpacing(6)

        # Brush / Eraser
        self._btn_brush = QPushButton("Brush")
        self._btn_brush.setCheckable(True)
        self._btn_brush.setChecked(True)
        self._btn_brush.setStyleSheet(BUTTON_STYLE)
        self._btn_brush.clicked.connect(lambda: self._set_edit_mode("brush"))
        tb.addWidget(self._btn_brush)

        self._btn_eraser = QPushButton("Eraser")
        self._btn_eraser.setCheckable(True)
        self._btn_eraser.setStyleSheet(BUTTON_STYLE)
        self._btn_eraser.clicked.connect(lambda: self._set_edit_mode("eraser"))
        tb.addWidget(self._btn_eraser)

        tb.addWidget(self._make_sep())

        # Colors
        self._color_btns: dict[str, QPushButton] = {}
        for color in ["#000000", "#ffffff", "#e53935", "#1e88e5", "#43a047", "#f9a825"]:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; border: 1px solid #888; border-radius: 10px; }}"
                f"QPushButton:hover {{ border: 2px solid #fff; }}"
            )
            btn.clicked.connect(lambda checked, c=color: self._set_color(c))
            tb.addWidget(btn)
            self._color_btns[color] = btn

        tb.addWidget(self._make_sep())

        # Width
        self._btn_width_minus = QPushButton("-")
        self._btn_width_minus.setFixedSize(24, 24)
        self._btn_width_minus.setStyleSheet(BUTTON_STYLE)
        self._btn_width_minus.clicked.connect(lambda: self._change_width(-1))
        tb.addWidget(self._btn_width_minus)

        self._lbl_width = QLabel(str(self._pen_width))
        self._lbl_width.setStyleSheet("color: #e0e0e0; font-weight: bold; min-width: 20px;")
        self._lbl_width.setAlignment(Qt.AlignCenter)
        tb.addWidget(self._lbl_width)

        self._btn_width_plus = QPushButton("+")
        self._btn_width_plus.setFixedSize(24, 24)
        self._btn_width_plus.setStyleSheet(BUTTON_STYLE)
        self._btn_width_plus.clicked.connect(lambda: self._change_width(1))
        tb.addWidget(self._btn_width_plus)

        tb.addWidget(self._make_sep())

        # Actions
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setStyleSheet(BUTTON_STYLE)
        self._btn_clear.clicked.connect(self._on_clear)
        tb.addWidget(self._btn_clear)

        self._btn_save = QPushButton("Save PNG")
        self._btn_save.setStyleSheet(BUTTON_STYLE)
        self._btn_save.clicked.connect(self._on_save)
        tb.addWidget(self._btn_save)

        self._btn_to_window = QPushButton("Draw to Window")
        self._btn_to_window.setStyleSheet(
            BUTTON_STYLE.replace("rgba(60,60,60,0.85)", "#3a6fc5")
        )
        self._btn_to_window.clicked.connect(self._on_draw_to_window)
        tb.addWidget(self._btn_to_window)

        tb.addStretch()

        self._btn_close = QPushButton("X")
        self._btn_close.setFixedSize(28, 28)
        self._btn_close.setStyleSheet(BUTTON_STYLE)
        self._btn_close.clicked.connect(self.close)
        tb.addWidget(self._btn_close)

        # Status bar
        self._status_bar = QFrame(self)
        self._status_bar.setStyleSheet("background: rgba(0,0,0,0.6); border-radius: 4px;")
        self._status_bar.setFixedHeight(24)
        sb = QHBoxLayout(self._status_bar)
        sb.setContentsMargins(10, 2, 10, 2)
        self._lbl_status = QLabel()
        self._lbl_status.setStyleSheet("color: #ccc; font-size: 10px;")
        sb.addWidget(self._lbl_status)
        sb.addStretch()
        self._lbl_progress = QLabel()
        self._lbl_progress.setStyleSheet("color: #aaa; font-size: 10px;")
        sb.addWidget(self._lbl_progress)

        self._update_toolbar_state()

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.2);")
        sep.setFixedWidth(1)
        return sep

    # ── Resize ───────────────────────────────────────────────────────────────

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._position_bars()

    def _position_bars(self):
        cw = self.width()
        ch = self.height()
        tb_w = min(1100, cw - 20)
        self._toolbar.setGeometry((cw - tb_w) // 2, 8, tb_w, 40)
        sb_w = min(500, cw - 40)
        self._status_bar.setGeometry((cw - sb_w) // 2, ch - 36, sb_w, 24)

    # ── Toolbar state ────────────────────────────────────────────────────────

    def _update_toolbar_state(self):
        editing = self._auto_draw_finished and not self._auto_draw_active
        self._btn_brush.setEnabled(editing)
        self._btn_eraser.setEnabled(editing)
        for b in self._color_btns.values():
            b.setEnabled(editing)
        self._btn_width_minus.setEnabled(editing)
        self._btn_width_plus.setEnabled(editing)
        self._btn_clear.setEnabled(editing or self._auto_draw_paused)
        self._btn_save.setEnabled(editing or self._auto_draw_paused)
        self._btn_to_window.setEnabled(editing or self._auto_draw_paused)

    # ── Contour scaling ──────────────────────────────────────────────────────

    def _prepare_contours(self):
        cw = self._cfg.canvas_width
        ch = self._cfg.canvas_height
        scale = min(cw / self._img_w, ch / self._img_h)
        off_x = (cw - self._img_w * scale) / 2.0
        off_y = (ch - self._img_h * scale) / 2.0

        self._scaled_contours = []
        for c in self._contours:
            pts = c.points.astype(float)
            pts = pts * scale + [off_x, off_y]
            # Close the contour for drawing
            if c.is_closed and pts.shape[0] >= 2:
                pts = np.vstack([pts, pts[0:1]])
            self._scaled_contours.append(pts)

    # ── Auto-draw ────────────────────────────────────────────────────────────

    def _start_auto_draw(self):
        self._current_contour_idx = 0
        self._current_point_idx = 1  # start from second point of first contour
        self._auto_draw_active = True
        self._auto_draw_paused = False
        self._auto_draw_finished = False
        self._update_toolbar_state()
        self._update_status()
        self._timer.start(16)  # ~60fps

    def _on_timer_tick(self):
        if not self._auto_draw_active or self._auto_draw_paused:
            return

        points_per_tick = max(1, int(0.016 / max(0.0001, self._cfg.auto_draw_speed)))
        drawn = 0

        while drawn < points_per_tick and self._auto_draw_active:
            if self._current_contour_idx >= len(self._scaled_contours):
                self._finish_auto_draw()
                return

            pts = self._scaled_contours[self._current_contour_idx]
            if pts.shape[0] < 2:
                self._current_contour_idx += 1
                self._current_point_idx = 1
                continue

            if self._current_point_idx >= pts.shape[0]:
                self._current_contour_idx += 1
                self._current_point_idx = 1
                self._update_status()
                continue

            p0 = pts[self._current_point_idx - 1]
            p1 = pts[self._current_point_idx]

            p = QPainter(self._pixmap)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(self._pen_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]))
            p.end()

            self._current_point_idx += 1
            drawn += 1
            self.update()

        self._update_progress()

    def _finish_auto_draw(self):
        self._auto_draw_active = False
        self._auto_draw_finished = True
        self._timer.stop()
        self._update_toolbar_state()
        self._lbl_status.setText("Edit mode — draw freely on the canvas")
        self._lbl_progress.setText("")
        self.update()

    def _update_status(self):
        total = len(self._scaled_contours)
        cur = self._current_contour_idx + 1
        if self._auto_draw_paused:
            self._lbl_status.setText(f"Paused — {cur}/{total} strokes")
        else:
            self._lbl_status.setText(f"Auto-drawing... {cur}/{total} strokes")

    def _update_progress(self):
        total_pts = sum(c.shape[0] for c in self._scaled_contours)
        done_pts = 0
        for i in range(self._current_contour_idx):
            done_pts += self._scaled_contours[i].shape[0]
        done_pts += self._current_point_idx
        pct = min(99, int(done_pts / max(1, total_pts) * 100))
        self._lbl_progress.setText(f"{pct}%")

    def toggle_pause(self):
        if not self._auto_draw_active:
            return
        self._auto_draw_paused = not self._auto_draw_paused
        self._update_status()
        self._update_toolbar_state()
        if self._auto_draw_paused:
            self._lbl_progress.setText("PAUSED")

    # ── Manual drawing ───────────────────────────────────────────────────────

    def _set_edit_mode(self, mode: str):
        self._edit_mode = mode
        self._btn_brush.setChecked(mode == "brush")
        self._btn_eraser.setChecked(mode == "eraser")
        self._update_status_text()

    def _set_color(self, color: str):
        self._pen_color = QColor(color)
        self._update_status_text()

    def _change_width(self, delta: int):
        self._pen_width = max(1, min(40, self._pen_width + delta))
        self._lbl_width.setText(str(self._pen_width))

    def _update_status_text(self):
        if self._auto_draw_finished and not self._auto_draw_active:
            mode = "Brush" if self._edit_mode == "brush" else "Eraser"
            self._lbl_status.setText(
                f"Edit mode — {mode}  |  {self._pen_color.name()}  |  {self._pen_width}px"
            )

    def mousePressEvent(self, event: QMouseEvent):
        if not self._auto_draw_finished or self._auto_draw_active:
            return
        if event.button() != Qt.LeftButton:
            return
        self._drawing = True
        self._last_pos = self._canvas_pos(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._drawing:
            return
        pos = self._canvas_pos(event)
        if self._last_pos is None:
            self._last_pos = pos
            return

        color = Qt.white if self._edit_mode == "eraser" else self._pen_color
        p = QPainter(self._pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(self._last_pos, pos)
        p.end()

        self._last_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drawing = False
        self._last_pos = None

    def wheelEvent(self, event: QWheelEvent):
        if not self._auto_draw_finished or self._auto_draw_active:
            return
        delta = 1 if event.angleDelta().y() > 0 else -1
        self._change_width(delta)

    def _canvas_pos(self, event: QMouseEvent) -> QPoint:
        """Mouse position mapped to pixmap coordinates."""
        pos = event.position().toPoint()
        ox, oy = self._pixmap_origin()
        return QPoint(pos.x() - ox, pos.y() - oy)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_clear(self):
        self._pixmap.fill(Qt.white)
        self.update()

    def _on_save(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Canvas", "canvas.png",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;All Files (*.*)",
        )
        if path:
            self._pixmap.save(path, "PNG")
            self.saved.emit(path)

    def _on_draw_to_window(self):
        fd, fpath = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        self._pixmap.save(fpath, "PNG")
        self.confirmed_to_window.emit(fpath)
        self.close()

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            if self._auto_draw_active:
                self._finish_auto_draw()
            else:
                self.close()
        elif event.key() == Qt.Key_Space:
            self.toggle_pause()
        elif event.key() == Qt.Key_B:
            self._set_edit_mode("brush")
        elif event.key() == Qt.Key_E:
            self._set_edit_mode("eraser")
        elif event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
            self._on_save()
        elif event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            self._on_draw_to_window()
        else:
            super().keyPressEvent(event)

    # ── Paint ────────────────────────────────────────────────────────────────

    def _pixmap_origin(self) -> tuple[int, int]:
        """(ox, oy) top-left of pixmap in widget coordinates."""
        cw = self.width()
        pw = self._cfg.canvas_width
        ph = self._cfg.canvas_height
        ox = (cw - pw) // 2
        oy = 60  # below toolbar
        return (ox, oy)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2b2b2b"))

        if self._pixmap and not self._pixmap.isNull():
            ox, oy = self._pixmap_origin()
            pw = self._cfg.canvas_width
            ph = self._cfg.canvas_height

            # Drop shadow
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 40))
            p.drawRect(ox + 3, oy + 3, pw, ph)

            # White canvas background
            p.fillRect(ox, oy, pw, ph, Qt.white)

            # Pixmap
            p.drawPixmap(ox, oy, self._pixmap)

            # Border around canvas
            p.setPen(QPen(QColor("#666"), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(ox - 1, oy - 1, pw + 2, ph + 2)
        p.end()

    def closeEvent(self, event: QCloseEvent):
        self._timer.stop()
        self._auto_draw_active = False
        self.closed.emit()
        super().closeEvent(event)
