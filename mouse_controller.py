"""Mouse drag-drawing with interpolation and hotkey abort.

Uses raw Win32 SendInput during auto-mode drag to include button state in
each move event — required by UWP apps (e.g. Windows 11 Paint) that track
pointer state per-event rather than relying on system virtual-key state.
"""

import ctypes
import math
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

try:
    from pynput.mouse import Button, Controller as MouseController, Listener as MouseListener
    from pynput.keyboard import Key, Listener as KeyListener
except ImportError:
    print("Missing dependency. Run: pip install -r requirements.txt", file=sys.stderr)
    raise

# ═══════════════════════════════════════════════════════════════════════════════
# Raw Win32 SendInput structures (for move-with-button-down events)
# ═══════════════════════════════════════════════════════════════════════════════

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",     wintypes.LONG),
        ("dy",     wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags",   wintypes.DWORD),
        ("time",      wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type",  wintypes.DWORD),
        ("value", _INPUT_UNION),
    ]

_MOUSEEVENTF_MOVE     = 0x0001
_MOUSEEVENTF_LEFTDOWN  = 0x0002
_MOUSEEVENTF_LEFTUP    = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP   = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP  = 0x0040
_MOUSEEVENTF_XDOWN     = 0x0080
_MOUSEEVENTF_XUP       = 0x0100
_MOUSEEVENTF_ABSOLUTE  = 0x8000
_MOUSEEVENTF_VIRTUALDESK = 0x4000

_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = (wintypes.UINT, ctypes.c_void_p, ctypes.c_int)

_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

# Button → (down_flag, up_flag, xbutton_data)
_BTN_SENDINPUT_MAP = {
    "left":   (_MOUSEEVENTF_LEFTDOWN,   _MOUSEEVENTF_LEFTUP,   0),
    "right":  (_MOUSEEVENTF_RIGHTDOWN,  _MOUSEEVENTF_RIGHTUP,  0),
    "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP, 0),
    "x1":     (_MOUSEEVENTF_XDOWN,      _MOUSEEVENTF_XUP,      0x0001),
    "x2":     (_MOUSEEVENTF_XDOWN,      _MOUSEEVENTF_XUP,      0x0002),
}


@dataclass
class MouseConfig:
    speed: float = 0.002
    button: str = "left"
    pause_between_strokes: bool = True
    start_delay: float = 3.0
    contour_pause: float = 0.1
    interpolate_step: int = 5
    manual_mode: bool = False

    def __post_init__(self):
        if self.interpolate_step < 1:
            raise ValueError(f"interpolate_step must be >= 1, got {self.interpolate_step}")
        if self.speed < 0:
            raise ValueError(f"speed must be >= 0, got {self.speed}")
        if self.start_delay < 0:
            raise ValueError(f"start_delay must be >= 0, got {self.start_delay}")
        if self.contour_pause < 0:
            raise ValueError(f"contour_pause must be >= 0, got {self.contour_pause}")


@dataclass
class Stroke:
    points: list[tuple[int, int]]  # screen coordinates
    is_closed: bool = False


@dataclass
class DrawResult:
    strokes_drawn: int
    strokes_total: int
    points_moved: int
    aborted: bool
    elapsed_seconds: float


class MouseDrawer:
    def __init__(self, cfg: MouseConfig):
        self.cfg = cfg
        self._mouse = MouseController()
        self._abort_event = threading.Event()
        self._key_listener: KeyListener | None = None
        self._mouse_listener: MouseListener | None = None
        self._button_held = threading.Event()

        btn_map = {
            "left": Button.left, "right": Button.right, "middle": Button.middle,
            "x1": Button.x1, "x2": Button.x2,
        }
        if cfg.button not in btn_map:
            raise ValueError(f"Unknown button: {cfg.button}. Valid: {list(btn_map.keys())}")
        self._button = btn_map[cfg.button]

        # Raw SendInput button flags
        self._btn_down_flag, self._btn_up_flag, self._btn_xdata = _BTN_SENDINPUT_MAP[cfg.button]

        # Virtual desktop dimensions for absolute coordinate normalization
        self._vscreen_left = ctypes.windll.user32.GetSystemMetrics(_SM_XVIRTUALSCREEN)
        self._vscreen_top  = ctypes.windll.user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)
        self._vscreen_w    = ctypes.windll.user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN)
        self._vscreen_h    = ctypes.windll.user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)

    def abort(self):
        """Set abort flag (thread-safe). Called from hotkey callback."""
        self._abort_event.set()

    # ── Raw SendInput helpers ────────────────────────────────────────────────

    def _send_mouse_event(self, dx: int, dy: int, dw_flags: int, mouse_data: int = 0):
        """Send a single mouse input event via SendInput (thread-safe)."""
        inp = _INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.value.mi.dx = dx
        inp.value.mi.dy = dy
        inp.value.mi.mouseData = mouse_data
        inp.value.mi.dwFlags = dw_flags
        inp.value.mi.time = 0
        inp.value.mi.dwExtraInfo = None
        _SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _screen_to_absolute(self, x: int, y: int) -> tuple[int, int]:
        """Convert screen pixel coordinates to 0–65535 normalized absolute coords."""
        nx = int((x - self._vscreen_left) * 65535 / self._vscreen_w)
        ny = int((y - self._vscreen_top) * 65535 / self._vscreen_h)
        return (nx, ny)

    def _drag_move(self, x: int, y: int):
        """Move cursor to (x,y) via SendInput, carrying the button-down flag."""
        nx, ny = self._screen_to_absolute(x, y)
        flags = _MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_VIRTUALDESK | self._btn_down_flag
        self._send_mouse_event(nx, ny, flags, self._btn_xdata)

    def _drag_press(self):
        """Press the draw button via SendInput."""
        self._send_mouse_event(0, 0, self._btn_down_flag, self._btn_xdata)

    def _drag_release(self):
        """Release the draw button via SendInput."""
        self._send_mouse_event(0, 0, self._btn_up_flag, self._btn_xdata)

    # ── Main drawing loop ───────────────────────────────────────────────────

    def draw_strokes(self, strokes: list[Stroke]) -> DrawResult:
        """Draw all strokes by dragging mouse."""
        start_time = time.monotonic()

        # Countdown
        remaining = self.cfg.start_delay
        while remaining > 0:
            if self._abort_event.is_set():
                return DrawResult(0, len(strokes), 0, True, time.monotonic() - start_time)
            if self.cfg.manual_mode:
                print(f"Hold [{self.cfg.button}] to draw — starting in {remaining:.0f}s...")
            else:
                print(f"Starting in {remaining:.0f}s...")
            sleep_time = min(1.0, remaining)
            time.sleep(sleep_time)
            remaining -= sleep_time

        # Start listeners
        self._key_listener = KeyListener(on_press=self._on_key_press)
        self._key_listener.start()

        if self.cfg.manual_mode:
            self._mouse_listener = MouseListener(on_click=self._on_mouse_click)
            self._mouse_listener.start()

        strokes_drawn = 0
        points_moved = 0

        try:
            for s in strokes:
                if self._abort_event.is_set():
                    break
                if not s.points:
                    continue

                # Jump to start (SetCursorPos is fine here — we aren't drawing yet)
                self._mouse.position = s.points[0]
                time.sleep(0.02)

                if self._abort_event.is_set():
                    break

                if self.cfg.manual_mode:
                    print(f"Hold [{self.cfg.button}] to draw stroke {strokes_drawn + 1}/{len(strokes)}")
                    if not self._wait_for_button():
                        break
                    self._draw_manual(s)
                    strokes_drawn += 1
                    points_moved += len(s.points)
                else:
                    # Auto press → drag → release, all via raw SendInput
                    self._drag_press()
                    time.sleep(0.03)  # let the target app register the button-down

                    aborted_mid = False

                    if len(s.points) == 1:
                        time.sleep(self.cfg.speed)
                    else:
                        for i in range(1, len(s.points)):
                            if self._abort_event.is_set():
                                self._drag_release()
                                aborted_mid = True
                                break
                            self._move_to_drag(s.points[i - 1], s.points[i])

                    if not aborted_mid:
                        self._drag_release()
                        strokes_drawn += 1
                        points_moved += len(s.points)

                if self._abort_event.is_set():
                    break

                if self.cfg.pause_between_strokes and not self._abort_event.is_set():
                    time.sleep(self.cfg.contour_pause)
        finally:
            self._stop_listeners()

        elapsed = time.monotonic() - start_time
        return DrawResult(
            strokes_drawn=strokes_drawn,
            strokes_total=len(strokes),
            points_moved=points_moved,
            aborted=self._abort_event.is_set(),
            elapsed_seconds=elapsed,
        )

    # ── Movement ─────────────────────────────────────────────────────────────

    def _move_to_drag(self, start: tuple, end: tuple):
        """Interpolate from start to end using raw SendInput with button flag."""
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        step = self.cfg.interpolate_step
        if dist > step:
            steps = int(dist / step)
            for i in range(1, steps + 1):
                if self._abort_event.is_set():
                    return
                t = i / steps
                x = start[0] + (end[0] - start[0]) * t
                y = start[1] + (end[1] - start[1]) * t
                self._drag_move(int(x), int(y))
                time.sleep(self.cfg.speed)
        else:
            if not self._abort_event.is_set():
                self._drag_move(*end)
                time.sleep(self.cfg.speed)

    def _draw_manual(self, s: Stroke):
        """Draw a single stroke in manual mode (user controls press/release)."""
        if len(s.points) == 1:
            time.sleep(self.cfg.speed)
            return

        for i in range(1, len(s.points)):
            if self._abort_event.is_set():
                return
            if not self._button_held.is_set():
                print(f"Paused — hold [{self.cfg.button}] to continue")
                if not self._wait_for_button():
                    return
            self._move_manual(s.points[i - 1], s.points[i])

    def _move_manual(self, start: tuple, end: tuple):
        """Move with interpolation in manual mode (button is physically held by user)."""
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        step = self.cfg.interpolate_step
        if dist > step:
            steps = int(dist / step)
            for i in range(1, steps + 1):
                if not self._check_continue():
                    return
                t = i / steps
                x = start[0] + (end[0] - start[0]) * t
                y = start[1] + (end[1] - start[1]) * t
                self._mouse.position = (int(x), int(y))
                time.sleep(self.cfg.speed)
        else:
            if self._check_continue():
                self._mouse.position = end
                time.sleep(self.cfg.speed)

    # ── State checks ─────────────────────────────────────────────────────────

    def _check_continue(self) -> bool:
        """Return True if drawing should continue. False = aborted or paused."""
        if self._abort_event.is_set():
            return False
        if self.cfg.manual_mode and not self._button_held.is_set():
            print(f"Paused — hold [{self.cfg.button}] to continue")
            return self._wait_for_button()
        return True

    def _wait_for_button(self) -> bool:
        """Block until target button is pressed. Returns False if aborted."""
        while not self._abort_event.is_set():
            if self._button_held.is_set():
                return True
            time.sleep(0.05)
        return False

    # ── Listeners ────────────────────────────────────────────────────────────

    def _on_key_press(self, key):
        """Hotkey callback: Esc aborts drawing."""
        if key == Key.esc:
            self.abort()

    def _on_mouse_click(self, x, y, button, pressed):
        """Track target button hold state for manual mode."""
        if button == self._button:
            if pressed:
                self._button_held.set()
            else:
                self._button_held.clear()

    def _stop_listeners(self):
        if self._key_listener is not None:
            listener = self._key_listener
            listener.stop()
            try:
                listener.join(timeout=1.0)
            except RuntimeError:
                pass
            self._key_listener = None

        if self._mouse_listener is not None:
            listener = self._mouse_listener
            listener.stop()
            try:
                listener.join(timeout=1.0)
            except RuntimeError:
                pass
            self._mouse_listener = None
