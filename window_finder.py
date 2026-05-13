"""Window detection, activation, canvas region, coordinate mapping, screenshot."""

from __future__ import annotations

from dataclasses import dataclass
import sys

try:
    import pygetwindow as gw
except ImportError:
    gw = None

class WindowNotFoundError(Exception):
    """Raised when no window matches the keyword."""
    def __init__(self, keyword: str, available_titles: list[str]):
        self.keyword = keyword
        self.available_titles = available_titles
        msg = f"No window matching '{keyword}'"
        if available_titles:
            msg += "\nAvailable windows:\n  " + "\n  ".join(available_titles)
        super().__init__(msg)


@dataclass
class WindowInfo:
    title: str
    left: int
    top: int
    width: int
    height: int
    is_visible: bool


@dataclass
class CanvasRegion:
    window: WindowInfo
    offset_x: int
    offset_y: int
    width: int
    height: int

    @property
    def screen_left(self) -> int:
        return self.window.left + self.offset_x

    @property
    def screen_top(self) -> int:
        return self.window.top + self.offset_y


def _require_gw():
    if gw is None:
        raise ImportError("Missing dependency. Run: pip install -r requirements.txt")


def list_all_windows() -> list[WindowInfo]:
    """List all visible windows only."""
    _require_gw()
    results: list[WindowInfo] = []
    try:
        all_windows = gw.getAllWindows()
    except Exception:
        return results
    for w in all_windows:
        if not w.visible:
            continue
        title = w.title or ""
        results.append(WindowInfo(
            title=title,
            left=w.left,
            top=w.top,
            width=w.width,
            height=w.height,
            is_visible=True,
        ))
    return results


def _window_area(w) -> int:
    """Safe area calculation, returns 0 if width or height is None."""
    ww = getattr(w, 'width', 0) or 0
    wh = getattr(w, 'height', 0) or 0
    return ww * wh


def find_window(title_keyword: str = "Godot") -> WindowInfo:
    """Find first window whose title contains keyword (case-insensitive)."""
    _require_gw()

    try:
        all_windows = gw.getAllWindows()
    except Exception:
        all_windows = []

    keyword_lower = title_keyword.lower()

    matches = []
    for w in all_windows:
        title = w.title or ""
        if keyword_lower in title.lower():
            matches.append(w)

    if not matches:
        available = [w.title for w in all_windows if w.title]
        raise WindowNotFoundError(title_keyword, available)

    # Prefer visible, then largest area
    matches.sort(key=lambda w: (not w.visible, -_window_area(w)))
    best = matches[0]

    if len(matches) > 1:
        print(f"Multiple windows match '{title_keyword}', using: \"{best.title}\"")

    return WindowInfo(
        title=best.title or "",
        left=best.left,
        top=best.top,
        width=best.width,
        height=best.height,
        is_visible=best.visible,
    )


def activate_window(window: WindowInfo) -> None:
    """Bring window to foreground. Matches by exact title first, then substring."""
    _require_gw()

    try:
        all_windows = gw.getAllWindows()
    except Exception:
        all_windows = []

    # Exact match first
    for w in all_windows:
        if w.title == window.title:
            if w.isMinimized:
                w.restore()
            w.activate()
            return

    # Fallback: substring match (find_window uses substring, titles can drift)
    title_lower = window.title.lower()
    for w in all_windows:
        if title_lower in (w.title or "").lower():
            if w.isMinimized:
                w.restore()
            w.activate()
            return

    raise WindowNotFoundError(window.title, [])


def build_canvas(window: WindowInfo, offset_x: int, offset_y: int,
                 width: int, height: int) -> CanvasRegion:
    """Create canvas region from window and offset."""
    return CanvasRegion(
        window=window,
        offset_x=offset_x,
        offset_y=offset_y,
        width=width,
        height=height,
    )


def image_to_screen(point: tuple[float, float], img_w: int, img_h: int,
                    canvas: CanvasRegion) -> tuple[int, int]:
    """Map image pixel coordinate to screen absolute coordinate.
    Scales to fit canvas, preserving aspect ratio, centered.
    """
    img_x, img_y = point
    scale = min(canvas.width / img_w, canvas.height / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    center_x = canvas.screen_left + (canvas.width - draw_w) / 2.0
    center_y = canvas.screen_top + (canvas.height - draw_h) / 2.0
    screen_x = int(center_x + img_x * scale)
    screen_y = int(center_y + img_y * scale)
    return (screen_x, screen_y)


def contours_to_strokes(contours: list, img_w: int, img_h: int,
                        canvas: CanvasRegion) -> list[Stroke]:
    """Convert image-space contours to screen-space strokes."""
    from mouse_controller import Stroke
    strokes = []
    for c in contours:
        if c.points.shape[0] < 2:
            continue
        screen_pts = [
            image_to_screen((float(x), float(y)), img_w, img_h, canvas)
            for x, y in c.points
        ]
        strokes.append(Stroke(points=screen_pts, is_closed=c.is_closed))
    return strokes


def capture_window_screenshot(window: WindowInfo):
    """Capture a screenshot of the target window region using Qt.

    Returns a BGR numpy array (OpenCV-compatible), or None on failure.
    Only callable when a QApplication exists.
    """
    import numpy as np

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage

    app = QApplication.instance()
    if app is None:
        return None

    screen = app.primaryScreen()
    if screen is None:
        return None

    if window.width <= 0 or window.height <= 0:
        return None

    try:
        pixmap = screen.grabWindow(
            0, window.left, window.top, window.width, window.height
        )
        if pixmap.isNull():
            return None

        qimg = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
        w, h = qimg.width(), qimg.height()
        bpl = qimg.bytesPerLine()
        ptr = qimg.constBits()
        arr = np.array(ptr, copy=True).reshape(h, bpl)
        if bpl != w * 3:
            arr = arr[:, :w * 3]
        arr = arr.reshape(h, w, 3)
        arr = arr[..., ::-1]  # RGB → BGR
        return arr
    except Exception:
        return None


def estimate_draw_time(strokes: list[Stroke], start_delay: float, speed: float,
                       contour_pause: float, pause_between: bool,
                       interpolate_step: int) -> float:
    """Estimate total drawing time including interpolation overhead."""
    total_pts = sum(len(s.points) for s in strokes)
    interp_pts = 0
    for s in strokes:
        for i in range(1, len(s.points)):
            dx = s.points[i][0] - s.points[i - 1][0]
            dy = s.points[i][1] - s.points[i - 1][1]
            d = (dx * dx + dy * dy) ** 0.5
            if d > interpolate_step:
                interp_pts += int(d / interpolate_step) - 1
    effective_pts = total_pts + interp_pts
    pause_count = len(strokes) if pause_between else 0
    return start_delay + effective_pts * speed + pause_count * contour_pause
