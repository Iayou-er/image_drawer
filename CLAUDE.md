# CLAUDE.md — Image Drawer

Automatically draw image edge contours onto any window canvas by controlling the mouse.
Dual mode: CLI (`main.py`) + GUI (`ui.py`). Bilingual: English / 中文.

## Architecture

```
main.py (CLI entry)          ui.py (GUI entry)
     │                            │
     ├── image_processor.py       ├── ui_thread_worker.py (QThread)
     ├── window_finder.py         ├── canvas_selector.py (CanvasSelector + CanvasEditor)
     ├── mouse_controller.py      ├── i18n.py
     └── (argparse)               └── (PySide6 signals/slots)
```

## Module Responsibilities

| File | Role |
|---|---|
| `main.py` | CLI: argparse, orchestrate pipeline, coordinate conversion |
| `ui.py` | GUI: PySide6 MainWindow, all widgets, signal/slot wiring, wallpaper system, about dialog |
| `image_processor.py` | Core: load→grayscale→Canny→contours→simplify→dedup→sort. Pure computation, no UI. |
| `window_finder.py` | Window enumeration (pygetwindow), activation, CanvasRegion math, coordinate mapping, screenshot capture |
| `mouse_controller.py` | Low-level mouse drawing (pynput), interpolation, manual mode, hotkey abort. Runs in QThread via DrawWorker. |
| `canvas_selector.py` | Two canvas-definition widgets: CanvasSelector (frameless overlay on target window) and CanvasEditor (embedded in-app tab) |
| `ui_thread_worker.py` | QThread wrapper around MouseDrawer. Emits countdown_tick, phase_changed, elapsed_update, finished, error signals. |
| `i18n.py` | `_STRINGS` dict with en/zh entries. `tr(key)` returns current-language string. `set_language(lang)` switches. Language preference saved in QSettings. |
| `build.spec` | PyInstaller config for single-EXE distribution. |

## Key Data Flow (GUI)

```
User loads image
  → _process_image()
    → ImageConfig from spinboxes
    → process_image() → ProcessResult (contours, img_w, img_h)
    → Preview tabs updated (Original/Edges/Overlay)

User clicks Start Drawing
  → _build_canvas() → CanvasRegion from window + offsets
  → contours_to_strokes() → list[Stroke] in screen coordinates
  → DrawWorker(strokes, MouseConfig) starts QThread
    → MouseDrawer.draw_strokes()
      → pynput moves mouse, press/release per stroke
      → Esc aborts; Manual mode pauses for user hold
```

## UI Widget Hierarchy

```
MainWindow → #bgContainer (wallpaper)
  └── QSplitter
       ├── Left: QScrollArea → #leftPanel (QWidget)
       │    ├── QGroupBox "Image" (browse + path)
       │    ├── QGroupBox "Image Parameters" (sliders + spinboxes)
       │    ├── QGroupBox "Window" (combo + refresh)
       │    ├── QGroupBox "Canvas Offset" (L/T/W/H + auto-fill + select)
       │    ├── QGroupBox "Mouse Settings" (speed/pause/step/delay/button/manual)
       │    └── QGroupBox "Actions" (dry-run/start/abort + progress)
       └── Right: #rightPanel (QWidget)
            ├── QTabWidget
            │    ├── Tab 0: Original (QScrollArea → QLabel)
            │    ├── Tab 1: Edges (QScrollArea → QLabel)
            │    ├── Tab 2: Overlay (QScrollArea → QLabel)
            │    └── Tab 3: Canvas (CanvasEditor widget)
            └── QTextEdit (info panel, read-only)
```

## Signal/Slot Conventions

- Image param changes → 300ms debounce QTimer → `_process_image()`
- Slider ↔ SpinBox pairs synced via `valueChanged` cross-connections
- Canvas spinboxes ↔ CanvasEditor: two-way sync guarded by `_syncing_canvas` boolean flag
- `_combo_windows.currentIndexChanged` → `_capture_window_screenshot()` → loads into CanvasEditor
- DrawWorker signals: `countdown_tick(int)` → `phase_changed(str)` → `elapsed_update(float)` → `finished(DrawResult)`

## i18n Pattern

- All user-facing strings use `tr("key")` from `i18n.py`
- `_retranslate_ui()` re-applies all strings; called on language switch and in `__init__`
- New UI text requires: (1) entry in `_STRINGS` dict, (2) `self._label_xxx.setText(tr("key"))` in `_retranslate_ui`
- Language saved to `QSettings("ImageDrawer", "UI")` as `"language"` key

## Wallpaper System

- `QSettings` keys: `wallpaper_path`, `wallpaper_mode` ("stretch"/"tile"), `wallpaper_color`
- `_apply_wallpaper()` generates full app stylesheet
- When wallpaper is set: all container layers (QSplitter, QScrollArea viewports, #leftPanel, #rightPanel) get `background: transparent`
- Content panels (QGroupBox, QTabWidget::pane, QTextEdit) get semi-transparent `rgba()` backgrounds ("frosted glass")
- Dark wallpaper (brightness < 85) → dark panel theme; light wallpaper → light panel theme
- QMenuBar and QStatusBar also themed to match brightness
- No wallpaper + no color → `setStyleSheet("")` to restore system defaults

## Canvas Definition — Two Ways

1. **Numeric** — Left/Top/Width/Height spinboxes. Auto-fill sets L=0, T=0, W/H=window size.
2. **Visual** — Two widgets:
   - `CanvasSelector` — frameless overlay on the target window (opened via "Select Canvas Region" button). Enter=confirm, Esc=cancel, W=full, F=snap.
   - `CanvasEditor` — embedded tab in the right panel. Shows window screenshot with draggable rectangle. Two-way sync with spinboxes. W=full, F=snap.

Both store coordinates in **window space** (pixels relative to target window's top-left).

## Manual Mode

- `MouseConfig.manual_mode` — program moves cursor to stroke start, then waits for user to hold the configured button
- `_button_held` threading.Event tracks button state via pynput mouse listener
- `_wait_for_button()` blocks until button pressed or abort

## Key Conventions

- No comments explaining WHAT code does; only WHY for non-obvious decisions
- Coordinates: image→screen mapping via `image_to_screen()` in window_finder.py (aspect-ratio fit, centered)
- Mouse interpolation: `_move_to()` in mouse_controller.py inserts intermediate points when distance > `interpolate_step`
- Clipboard/image conversions: `cv2_to_qpixmap()` in ui.py (BGR→RGB→QImage→QPixmap)
- Screenshot capture uses `QScreen.grabWindow(0, x, y, w, h)` — no extra dependencies
- All file dialogs filter: `"Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;All Files (*.*)"`

## Dependencies

```
opencv-python>=4.8.0, numpy>=1.24.0, pynput>=1.7.6, pygetwindow>=0.0.9, PySide6>=6.6.0
```

## Build

```bash
build.bat             # one-click PyInstaller build
# or: python -m PyInstaller --clean build.spec
# Output: dist/ImageDrawer.exe
```

## Known Issues

- `test_edge_cases.py` Test 9 (dedup_distance) has 2 pre-existing failures unrelated to recent changes
- pygetwindow returns coordinates including title bar and borders; compensate via Canvas Offset
- Some windows may not be enumerable by pygetwindow (UWP apps, admin-elevated processes)
- `QScreen.grabWindow(0, ...)` captures from the root window on Windows; may include window shadows on some compositors
- `constBits()` memoryview→numpy conversion depends on PySide6 version; the copy-reshape approach is deliberately safe
