"""QThread worker that runs MouseDrawer in the background.

Emits signals for countdown, elapsed time, and completion so the UI
can show progress without blocking.
"""

import dataclasses
import math
import threading
import time

from PySide6.QtCore import QThread, Signal

from mouse_controller import MouseConfig, Stroke, DrawResult, MouseDrawer


class DrawWorker(QThread):
    """Runs MouseDrawer.draw_strokes() in a background thread.

    Signals:
        countdown_tick(int): remaining countdown seconds
        phase_changed(str): "countdown" | "drawing" | "done" | "error"
        elapsed_update(float): elapsed drawing seconds
        finished(DrawResult): final result
        error(str): error message
    """

    countdown_tick = Signal(int)
    phase_changed = Signal(str)
    elapsed_update = Signal(float)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, strokes: list[Stroke], mouse_cfg: MouseConfig,
                 estimated_time: float, parent=None):
        super().__init__(parent)
        self._strokes = strokes
        self._mouse_cfg = mouse_cfg
        self._estimated_time = estimated_time
        self._drawer: MouseDrawer | None = None
        self._abort_requested = False

    def request_abort(self):
        """Thread-safe abort. Called from UI thread."""
        self._abort_requested = True
        if self._drawer is not None:
            self._drawer.abort()

    def run(self):
        try:
            # Phase 1: Countdown (handled here so we can emit signals)
            remaining = self._mouse_cfg.start_delay
            while remaining > 0:
                if self._abort_requested:
                    self.phase_changed.emit("done")
                    self.finished.emit(DrawResult(
                        strokes_drawn=0, strokes_total=len(self._strokes),
                        points_moved=0, aborted=True, elapsed_seconds=0,
                    ))
                    return
                self.countdown_tick.emit(int(math.ceil(remaining)))
                self.phase_changed.emit("countdown")
                sleep_time = min(0.25, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time

            # Phase 2: Drawing (use start_delay=0 since we already counted down)
            cfg_no_delay = dataclasses.replace(self._mouse_cfg, start_delay=0)
            self._drawer = MouseDrawer(cfg_no_delay)

            if self._abort_requested:
                self.phase_changed.emit("done")
                self.finished.emit(DrawResult(
                    strokes_drawn=0, strokes_total=len(self._strokes),
                    points_moved=0, aborted=True, elapsed_seconds=0,
                ))
                return

            self.phase_changed.emit("drawing")

            # Elapsed-time emitter thread
            start_time = time.monotonic()
            running = threading.Event()
            running.set()

            def emit_elapsed():
                while running.is_set():
                    self.elapsed_update.emit(time.monotonic() - start_time)
                    time.sleep(0.2)

            timer_thread = threading.Thread(target=emit_elapsed, daemon=True)
            timer_thread.start()

            try:
                result = self._drawer.draw_strokes(self._strokes)
            finally:
                running.clear()
                timer_thread.join(timeout=1.0)

            self.phase_changed.emit("done")
            self.finished.emit(result)

        except Exception as e:
            self.phase_changed.emit("error")
            self.error.emit(str(e))