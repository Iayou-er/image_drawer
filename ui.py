"""PySide6 desktop UI for Image Drawer.

Replaces the CLI with a graphical interface. All existing core modules
(image_processor, window_finder, mouse_controller, main) are imported
and used without modification.

Supports English and Chinese via the Language menu.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QSettings,
)
from PySide6.QtGui import (
    QAction, QImage, QPixmap, QKeySequence, QFont, QActionGroup, QColor,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QSlider, QSpinBox,
    QDoubleSpinBox, QCheckBox, QComboBox, QTabWidget,
    QScrollArea, QProgressBar, QStatusBar, QFileDialog,
    QMessageBox, QMenuBar, QTextEdit, QFrame, QColorDialog,
    QDialog, QDialogButtonBox,
)

from i18n import tr, set_language, get_language, LANGUAGES

if TYPE_CHECKING:
    import cv2
    import numpy as np
    from image_processor import ImageConfig, ProcessResult, process_image, resize_fit
    from window_finder import (
        WindowNotFoundError, WindowInfo, CanvasRegion,
        list_all_windows, find_window, build_canvas,
        contours_to_strokes, estimate_draw_time,
        capture_window_screenshot,
    )
    from mouse_controller import MouseConfig, DrawResult, MouseDrawer
    from ui_thread_worker import DrawWorker
    from canvas_selector import CanvasSelector, CanvasEditor, select_canvas


PRESETS = [
    {
        "key": "preset_general",
        "params": {
            "edge_mode": 0, "chk_auto_canny": True, "auto_canny_sigma": 0.33,
            "canny_low": 50, "canny_high": 150, "blur_ksize": 5,
            "chk_bilateral": False, "bilateral_d": 9,
            "epsilon": 0.002, "skip_points": 2, "min_area": 50,
            "chk_inner": False, "hierarchy_depth": 2,
            "dedup": 2.0, "morph": 0,
        },
    },
    {
        "key": "preset_illustration",
        "params": {
            "edge_mode": 1, "chk_auto_canny": True, "auto_canny_sigma": 0.20,
            "canny_low": 30, "canny_high": 100, "blur_ksize": 3,
            "chk_bilateral": True, "bilateral_d": 9,
            "epsilon": 0.001, "skip_points": 1, "min_area": 10,
            "chk_inner": True, "hierarchy_depth": 2,
            "dedup": 1.0, "morph": 0,
        },
    },
    {
        "key": "preset_photo",
        "params": {
            "edge_mode": 2, "chk_auto_canny": True, "auto_canny_sigma": 0.33,
            "canny_low": 40, "canny_high": 120, "blur_ksize": 5,
            "chk_bilateral": False, "bilateral_d": 9,
            "epsilon": 0.002, "skip_points": 2, "min_area": 30,
            "chk_inner": True, "hierarchy_depth": 3,
            "dedup": 2.0, "morph": 0,
        },
    },
    {
        "key": "preset_logo",
        "params": {
            "edge_mode": 0, "chk_auto_canny": True, "auto_canny_sigma": 0.25,
            "canny_low": 50, "canny_high": 150, "blur_ksize": 3,
            "chk_bilateral": False, "bilateral_d": 9,
            "epsilon": 0.0005, "skip_points": 1, "min_area": 5,
            "chk_inner": True, "hierarchy_depth": 1,
            "dedup": 0.5, "morph": 0,
        },
    },
]


def cv2_to_qpixmap(img) -> QPixmap:
    """Convert OpenCV image (BGR or grayscale) to QPixmap."""
    import cv2
    import numpy as np
    if img.ndim == 2:
        h, w = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    else:
        h, w, _ = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class MainWindow(QMainWindow):
    """Main application window for Image Drawer."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(1100, 700)

        # Internal state
        self._image_path: str | None = None
        self._raw_image: np.ndarray | None = None
        self._process_result: ProcessResult | None = None
        self._edges_image: np.ndarray | None = None
        self._overlay_image: np.ndarray | None = None
        self._worker: DrawWorker | None = None
        self._estimated_time: float = 0.0
        self._settings = QSettings("ImageDrawer", "UI")

        # Wallpaper state
        self._wallpaper_path: str | None = self._settings.value("wallpaper_path", None)
        self._wallpaper_mode: str = self._settings.value("wallpaper_mode", "stretch")
        self._wallpaper_color: str = self._settings.value("wallpaper_color", "")

        # Restore language preference
        saved_lang = self._settings.value("language", "en")
        set_language(saved_lang)

        # Widgets that hold references to labels (need retranslation)
        self._label_canny_low: QLabel = None
        self._label_canny_high: QLabel = None
        self._label_blur: QLabel = None
        self._label_epsilon: QLabel = None
        self._label_skip: QLabel = None
        self._label_min_area: QLabel = None
        self._label_morph: QLabel = None
        self._label_dedup: QLabel = None
        self._label_sort: QLabel = None
        self._label_target_size: QLabel = None
        self._label_target_w: QLabel = None
        self._label_target_h: QLabel = None
        self._label_edge_mode: QLabel = None
        self._label_inner_contours: QLabel = None
        self._label_hierarchy_depth: QLabel = None
        self._label_auto_canny_sigma: QLabel = None
        self._label_bilateral_d: QLabel = None
        self._label_speed: QLabel = None
        self._label_pause: QLabel = None
        self._label_step: QLabel = None
        self._label_delay: QLabel = None
        self._label_button: QLabel = None
        self._canvas_labels: list[QLabel] = []  # [left, top, width, height]
        self._syncing_canvas = False  # guard against signal feedback loops
        self._applying_preset = False
        self._board: object | None = None  # VirtualCanvas reference
        self._board_temp_path: str | None = None
        self._board_color: str = "#000000"

        self._build_menu_bar()
        self._build_ui()
        self._connect_signals()
        self._restore_geometry()
        self._retranslate_ui()

        # Initial state
        self._on_phase_changed("idle")
        self._apply_wallpaper()

    # ── Menu Bar ──────────────────────────────────────────────────────────

    def _build_menu_bar(self):
        mb = self.menuBar()

        # File menu
        self._menu_file = mb.addMenu("")
        self._act_open = QAction("", self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._on_browse)
        self._menu_file.addAction(self._act_open)
        self._menu_file.addSeparator()
        self._act_refresh = QAction("", self)
        self._act_refresh.setShortcut(QKeySequence("Ctrl+R"))
        self._act_refresh.triggered.connect(self._on_refresh_windows)
        self._menu_file.addAction(self._act_refresh)

        self._act_screenshot = QAction("", self)
        self._act_screenshot.setShortcut(QKeySequence("Ctrl+P"))
        self._act_screenshot.triggered.connect(self._on_screenshot)
        self._menu_file.addAction(self._act_screenshot)
        self._menu_file.addSeparator()
        self._act_exit = QAction("", self)
        self._act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self._act_exit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_exit)

        # View menu
        self._menu_view = mb.addMenu("")
        self._act_wallpaper = QAction("", self)
        self._act_wallpaper.triggered.connect(self._on_set_wallpaper)
        self._menu_view.addAction(self._act_wallpaper)

        self._menu_wallpaper_mode = self._menu_view.addMenu("")
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_actions: dict[str, QAction] = {}
        for mode_key in ["stretch", "tile"]:
            act = QAction("", self)
            act.setCheckable(True)
            act.setChecked(self._wallpaper_mode == mode_key)
            act.triggered.connect(lambda checked, m=mode_key: self._on_wallpaper_mode_changed(m))
            self._mode_group.addAction(act)
            self._mode_actions[mode_key] = act
            self._menu_wallpaper_mode.addAction(act)

        self._menu_view.addSeparator()
        self._act_clear_wallpaper = QAction("", self)
        self._act_clear_wallpaper.triggered.connect(self._on_clear_wallpaper)
        self._menu_view.addAction(self._act_clear_wallpaper)

        self._act_bg_color = QAction("", self)
        self._act_bg_color.triggered.connect(self._on_bg_color)
        self._menu_view.addAction(self._act_bg_color)

        # Language menu
        self._menu_lang = mb.addMenu("")
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)

        self._act_lang_en = QAction("", self)
        self._act_lang_en.setCheckable(True)
        self._act_lang_en.setChecked(get_language() == "en")
        self._act_lang_en.triggered.connect(lambda: self._on_language_changed("en"))
        self._lang_group.addAction(self._act_lang_en)
        self._menu_lang.addAction(self._act_lang_en)

        self._act_lang_zh = QAction("", self)
        self._act_lang_zh.setCheckable(True)
        self._act_lang_zh.setChecked(get_language() == "zh")
        self._act_lang_zh.triggered.connect(lambda: self._on_language_changed("zh"))
        self._lang_group.addAction(self._act_lang_zh)
        self._menu_lang.addAction(self._act_lang_zh)

        # Help menu
        self._menu_help = mb.addMenu("")
        self._act_about = QAction("", self)
        self._act_about.triggered.connect(self._show_about)
        self._menu_help.addAction(self._act_about)

    # ── Language Switching ────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        set_language(lang)
        self._settings.setValue("language", lang)
        self._retranslate_ui()

    # ── Wallpaper ──────────────────────────────────────────────────────────

    def _on_set_wallpaper(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu_view_wallpaper"), "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)",
        )
        if not path:
            return
        self._wallpaper_path = path
        self._settings.setValue("wallpaper_path", path)
        self._apply_wallpaper()

    def _on_clear_wallpaper(self):
        self._wallpaper_path = None
        self._settings.remove("wallpaper_path")
        self._apply_wallpaper()

    def _on_wallpaper_mode_changed(self, mode: str):
        self._wallpaper_mode = mode
        self._settings.setValue("wallpaper_mode", mode)
        self._apply_wallpaper()

    def _on_bg_color(self):
        initial = QColor(self._wallpaper_color) if self._wallpaper_color else QColor("#f0f0f0")
        color = QColorDialog.getColor(initial, self, tr("menu_view_bg_color"))
        if not color.isValid():
            return
        self._wallpaper_color = color.name()
        self._settings.setValue("wallpaper_color", self._wallpaper_color)
        self._apply_wallpaper()

    def _detect_brightness(self, path: str) -> float:
        """Return average brightness of the wallpaper image (0-255). 0=black, 255=white."""
        import cv2
        import numpy as np
        img = cv2.imread(path)
        if img is None:
            return 128
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _apply_wallpaper(self):
        # No wallpaper and no custom color → clear all styles, restore system default
        if self._wallpaper_path is None and not self._wallpaper_color:
            self.setStyleSheet("")
            self._bg_container.setStyleSheet("")
            self._status_bar.setStyleSheet("")
            self.menuBar().setStyleSheet("")
            return

        color = self._wallpaper_color or "#f0f0f0"

        # Determine theme based on wallpaper brightness
        if self._wallpaper_path:
            brightness = self._detect_brightness(self._wallpaper_path)
            dark = brightness < 85

            if dark:
                menu_style = (
                    "QMenuBar { background: #2b2b2b; color: #e0e0e0; }"
                    "QMenuBar::item:selected { background: #444; }"
                    "QMenu { background: #2b2b2b; color: #e0e0e0; }"
                    "QMenu::item:selected { background: #444; }"
                )
                status_style = "QStatusBar { background: #2b2b2b; color: #e0e0e0; }"
                panel_bg = "rgba(32, 32, 32, 0.78)"
                panel_color = "#e0e0e0"
                input_bg = "rgba(50, 50, 50, 0.88)"
                tab_inactive = "rgba(45, 45, 45, 0.75)"
                group_border = "rgba(255,255,255,0.12)"
            else:
                menu_style = (
                    "QMenuBar { background: #f5f5f5; color: #1a1a1a; }"
                    "QMenuBar::item:selected { background: #ddd; }"
                    "QMenu { background: #f5f5f5; color: #1a1a1a; }"
                    "QMenu::item:selected { background: #ddd; }"
                )
                status_style = "QStatusBar { background: #f5f5f5; color: #1a1a1a; }"
                panel_bg = "rgba(255, 255, 255, 0.70)"
                panel_color = "#1a1a1a"
                input_bg = "rgba(255, 255, 255, 0.90)"
                tab_inactive = "rgba(240, 240, 240, 0.65)"
                group_border = "rgba(0,0,0,0.10)"
        else:
            menu_style = ""
            status_style = ""
            panel_bg = ""
            panel_color = ""
            input_bg = ""
            tab_inactive = ""
            group_border = ""

        # Background container style (wallpaper image + fallback color)
        if self._wallpaper_path:
            img_path = self._wallpaper_path.replace("\\", "/").replace('"', '\\"')
            if self._wallpaper_mode == "tile":
                bg_style = (
                    f"#bgContainer {{"
                    f"  background-image: url(\"{img_path}\");"
                    f"  background-repeat: repeat;"
                    f"  background-color: {color};"
                    f"}}"
                )
            else:
                bg_style = (
                    f"#bgContainer {{"
                    f"  border-image: url(\"{img_path}\") 0 0 0 0 stretch stretch;"
                    f"  background-color: {color};"
                    f"}}"
                )
        else:
            bg_style = f"#bgContainer {{ background-color: {color}; }}"

        # Content panel frosted-glass transparency (only when wallpaper is set)
        if self._wallpaper_path and panel_bg:
            content_style = (
                # Strip opaque backgrounds from container layers
                f"QSplitter {{ background: transparent; }}"
                f"QSplitter::handle {{ background: rgba(128,128,128,0.25); }}"
                f"QScrollArea {{ background: transparent; }}"
                f"QScrollArea > QWidget {{ background: transparent; }}"
                f"#leftPanel {{ background: transparent; }}"
                f"#rightPanel {{ background: transparent; }}"
                f"QTabWidget > QWidget {{ background: transparent; }}"
                # Semitransparent content panels
                f"QGroupBox {{"
                f"  background: {panel_bg};"
                f"  color: {panel_color};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 5px;"
                f"  padding-top: 18px;"
                f"}}"
                f"QGroupBox::title {{"
                f"  subcontrol-origin: margin;"
                f"  left: 10px;"
                f"  padding: 0 5px;"
                f"  color: {panel_color};"
                f"  font-weight: bold;"
                f"}}"
                f"QTabWidget::pane {{"
                f"  background: {panel_bg};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 4px;"
                f"}}"
                f"QTabBar::tab {{"
                f"  background: {tab_inactive};"
                f"  color: {panel_color};"
                f"  padding: 5px 12px;"
                f"  border: 1px solid {group_border};"
                f"  border-bottom: none;"
                f"  border-top-left-radius: 4px;"
                f"  border-top-right-radius: 4px;"
                f"}}"
                f"QTabBar::tab:selected {{"
                f"  background: {panel_bg};"
                f"}}"
                f"QTextEdit {{"
                f"  background: {panel_bg};"
                f"  color: {panel_color};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 4px;"
                f"}}"
                f"QComboBox {{"
                f"  background: {input_bg};"
                f"  color: {panel_color};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 3px;"
                f"  padding: 2px 6px;"
                f"}}"
                f"QComboBox::drop-down {{ border: none; }}"
                f"QSpinBox, QDoubleSpinBox {{"
                f"  background: {input_bg};"
                f"  color: {panel_color};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 3px;"
                f"  padding: 2px 4px;"
                f"}}"
                f"QSlider::groove:horizontal {{ background: rgba(128,128,128,0.3); border-radius: 3px; }}"
                f"QSlider::handle:horizontal {{ background: {panel_color}; width: 12px; border-radius: 6px; }}"
                f"QCheckBox {{ color: {panel_color}; }}"
                f"QLabel {{ color: {panel_color}; }}"
                f"QLineEdit {{"
                f"  background: {input_bg};"
                f"  color: {panel_color};"
                f"  border: 1px solid {group_border};"
                f"  border-radius: 3px;"
                f"}}"
            )
        else:
            content_style = ""

        full_style = bg_style + menu_style + status_style + content_style
        self.setStyleSheet(full_style)

    def _retranslate_ui(self):
        """Re-apply all translatable strings across the UI."""
        self.setWindowTitle(tr("app_title"))

        # Menus
        self._menu_file.setTitle(tr("menu_file"))
        self._act_open.setText(tr("menu_file_open"))
        self._act_refresh.setText(tr("menu_file_refresh"))
        self._act_screenshot.setText(tr("menu_file_screenshot"))
        self._act_exit.setText(tr("menu_file_exit"))
        self._menu_lang.setTitle(tr("menu_language"))
        self._act_lang_en.setText(tr("menu_language_en"))
        self._act_lang_zh.setText(tr("menu_language_zh"))
        self._menu_view.setTitle(tr("menu_view"))
        self._act_wallpaper.setText(tr("menu_view_wallpaper"))
        self._menu_wallpaper_mode.setTitle(tr("menu_view_mode"))
        self._mode_actions["stretch"].setText(tr("menu_view_mode_stretch"))
        self._mode_actions["tile"].setText(tr("menu_view_mode_tile"))
        self._act_clear_wallpaper.setText(tr("menu_view_clear"))
        self._act_bg_color.setText(tr("menu_view_bg_color"))
        self._menu_help.setTitle(tr("menu_help"))
        self._act_about.setText(tr("menu_help_about"))

        # Groups
        self._combo_presets.setItemText(0, tr("preset_general"))
        self._combo_presets.setItemText(1, tr("preset_illustration"))
        self._combo_presets.setItemText(2, tr("preset_photo"))
        self._combo_presets.setItemText(3, tr("preset_logo"))
        self._combo_presets.setToolTip(tr("tooltip_preset"))

        self._group_image.setTitle(tr("group_image"))
        self._group_params.setTitle(tr("group_params"))
        self._group_window.setTitle(tr("group_window"))
        self._group_canvas.setTitle(tr("group_canvas"))
        self._group_mouse.setTitle(tr("group_mouse"))
        self._group_actions.setTitle(tr("group_actions"))

        # Image group
        self._line_path.setPlaceholderText(tr("placeholder_image_path"))
        self._btn_browse.setText(tr("btn_browse"))
        self._btn_browse.setToolTip(tr("tooltip_browse"))

        # Parameter labels
        self._label_canny_low.setText(tr("label_canny_low"))
        self._label_canny_high.setText(tr("label_canny_high"))
        self._label_blur.setText(tr("label_blur"))
        self._spin_blur.setToolTip(tr("tooltip_blur"))
        self._label_epsilon.setText(tr("label_epsilon"))
        self._spin_epsilon.setToolTip(tr("tooltip_epsilon"))
        self._label_skip.setText(tr("label_skip"))
        self._spin_skip.setToolTip(tr("tooltip_skip"))
        self._label_min_area.setText(tr("label_min_area"))
        self._spin_min_area.setToolTip(tr("tooltip_min_area"))
        self._label_morph.setText(tr("label_morph"))
        self._spin_morph.setToolTip(tr("tooltip_morph"))
        self._label_dedup.setText(tr("label_dedup"))
        self._spin_dedup.setToolTip(tr("tooltip_dedup"))
        self._label_sort.setText(tr("label_sort"))
        self._chk_neighbor.setText(tr("chk_neighbor"))
        self._label_target_size.setText(tr("label_target_size"))
        self._chk_target.setText(tr("chk_target_enable"))
        self._label_target_w.setText(tr("label_target_w"))
        self._label_target_h.setText(tr("label_target_h"))
        self._label_edge_mode.setText(tr("label_edge_mode"))
        self._combo_edge_mode.setItemText(0, tr("edge_mode_gray"))
        self._combo_edge_mode.setItemText(1, tr("edge_mode_rgb"))
        self._combo_edge_mode.setItemText(2, tr("edge_mode_lab"))
        self._combo_edge_mode.setToolTip(tr("tooltip_edge_mode"))
        self._label_inner_contours.setText(tr("label_inner_contours"))
        self._chk_inner_contours.setText(tr("chk_inner_contours"))
        self._chk_inner_contours.setToolTip(tr("tooltip_inner_contours"))
        self._label_hierarchy_depth.setText(tr("label_hierarchy_depth"))
        self._spin_hierarchy_depth.setToolTip(tr("tooltip_hierarchy_depth"))
        self._label_auto_canny_sigma.setText(tr("label_auto_canny_sigma"))
        self._chk_auto_canny.setText(tr("chk_auto_canny"))
        self._chk_auto_canny.setToolTip(tr("tooltip_auto_canny"))
        self._spin_auto_canny_sigma.setToolTip(tr("tooltip_auto_canny_sigma"))
        self._chk_bilateral.setText(tr("chk_bilateral"))
        self._chk_bilateral.setToolTip(tr("tooltip_bilateral"))
        self._label_bilateral_d.setText(tr("label_bilateral_d"))
        self._spin_bilateral_d.setToolTip(tr("tooltip_bilateral_d"))

        # Window group
        self._combo_windows.setToolTip(tr("tooltip_window_combo"))
        self._btn_refresh.setText(tr("btn_refresh"))
        self._btn_refresh.setToolTip(tr("tooltip_refresh"))

        # Canvas offset
        canvas_keys = ["label_canvas_l", "label_canvas_t", "label_canvas_w", "label_canvas_h"]
        for i, key in enumerate(canvas_keys):
            self._canvas_labels[i].setText(tr(key))
            # Spinbox tooltips
            if i < 4:
                pass  # tooltips set separately below
        self._btn_auto_fill.setText(tr("btn_auto_fill"))
        self._btn_auto_fill.setToolTip(tr("tooltip_auto_fill"))
        self._btn_select_canvas.setText(tr("btn_select_canvas"))
        self._btn_select_canvas.setToolTip(tr("tooltip_select_canvas"))
        for attr in ["_spin_canvas_l", "_spin_canvas_t", "_spin_canvas_w", "_spin_canvas_h"]:
            getattr(self, attr).setToolTip(tr("tooltip_canvas_offset"))

        # Mouse settings
        self._label_speed.setText(tr("label_speed"))
        self._spin_speed.setToolTip(tr("tooltip_speed"))
        self._label_pause.setText(tr("label_pause"))
        self._spin_pause.setToolTip(tr("tooltip_pause"))
        self._label_step.setText(tr("label_step"))
        self._spin_step.setToolTip(tr("tooltip_step"))
        self._label_delay.setText(tr("label_delay"))
        self._spin_delay.setToolTip(tr("tooltip_delay"))
        self._chk_pause_between.setText(tr("chk_pause_between"))
        self._label_button.setText(tr("label_button"))
        self._chk_manual.setText(tr("chk_manual"))

        # Draw target
        self._radio_draw_window.setText(tr("draw_target_window"))
        self._radio_draw_board.setText(tr("draw_target_board"))
        self._label_board_color.setText(tr("label_board_color"))
        self._label_board_width.setText(tr("label_board_width"))
        self._label_board_size.setText(tr("label_board_size"))
        self._btn_open_blank_board.setText(tr("btn_open_blank_board"))

        # Action buttons
        self._btn_dry_run.setText(tr("btn_dry_run"))
        self._btn_dry_run.setToolTip(tr("tooltip_dry_run"))
        self._btn_start.setText(tr("btn_start"))
        self._btn_start.setToolTip(tr("tooltip_start"))
        self._btn_abort.setText(tr("btn_abort"))
        self._btn_abort.setToolTip(tr("tooltip_abort"))

        # Preview tabs
        self._tab_preview.setTabText(0, tr("tab_original"))
        self._tab_preview.setTabText(1, tr("tab_edges"))
        self._tab_preview.setTabText(2, tr("tab_overlay"))
        self._tab_preview.setTabText(3, tr("tab_canvas"))
        for label in [self._label_original, self._label_edges, self._label_overlay]:
            if label.pixmap() is None:
                label.setText(tr("label_no_image"))

        # Refresh status bar and info
        if self._process_result:
            self._update_info_panel()
        else:
            self._status_bar.showMessage(tr("status_ready"))

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        self._bg_container = QWidget()
        self._bg_container.setObjectName("bgContainer")

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        container_layout = QVBoxLayout(self._bg_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(splitter)

        self.setCentralWidget(self._bg_container)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        panel = QWidget()
        panel.setObjectName("leftPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        layout.addWidget(self._build_image_group())
        layout.addWidget(self._build_params_group())
        layout.addWidget(self._build_window_group())
        layout.addWidget(self._build_canvas_group())
        layout.addWidget(self._build_mouse_group())
        layout.addWidget(self._build_action_group())
        layout.addStretch()

        scroll.setWidget(panel)
        return scroll

    # ── Image Group ───────────────────────────────────────────────────────

    def _build_image_group(self) -> QGroupBox:
        self._group_image = QGroupBox()
        ly = QHBoxLayout(self._group_image)
        self._line_path = QLineEdit()
        self._line_path.setReadOnly(True)
        self._btn_browse = QPushButton()
        ly.addWidget(self._line_path, 1)
        ly.addWidget(self._btn_browse)
        return self._group_image

    # ── Image Parameters Group ────────────────────────────────────────────

    def _build_params_group(self) -> QGroupBox:
        self._group_params = QGroupBox()
        form = QFormLayout(self._group_params)

        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Presets
        self._combo_presets = QComboBox()
        self._combo_presets.addItems(["General", "Complex Illustration", "Photo / Portrait", "Logo / Line Art"])
        form.addRow(tr("label_preset"), self._combo_presets)

        # Canny Low
        self._slider_canny_low = QSlider(Qt.Horizontal)
        self._slider_canny_low.setRange(0, 255)
        self._slider_canny_low.setValue(50)
        self._spin_canny_low = QSpinBox()
        self._spin_canny_low.setRange(0, 255)
        self._spin_canny_low.setValue(50)
        row = QHBoxLayout()
        row.addWidget(self._slider_canny_low)
        row.addWidget(self._spin_canny_low)
        self._label_canny_low = QLabel()
        form.addRow(self._label_canny_low, self._make_row_widget(row))

        # Canny High
        self._slider_canny_high = QSlider(Qt.Horizontal)
        self._slider_canny_high.setRange(0, 255)
        self._slider_canny_high.setValue(150)
        self._spin_canny_high = QSpinBox()
        self._spin_canny_high.setRange(0, 255)
        self._spin_canny_high.setValue(150)
        row = QHBoxLayout()
        row.addWidget(self._slider_canny_high)
        row.addWidget(self._spin_canny_high)
        self._label_canny_high = QLabel()
        form.addRow(self._label_canny_high, self._make_row_widget(row))

        # Auto Canny
        auto_canny_row = QHBoxLayout()
        self._chk_auto_canny = QCheckBox()
        self._chk_auto_canny.setChecked(True)
        self._spin_auto_canny_sigma = QDoubleSpinBox()
        self._spin_auto_canny_sigma.setRange(0.05, 1.0)
        self._spin_auto_canny_sigma.setDecimals(2)
        self._spin_auto_canny_sigma.setSingleStep(0.05)
        self._spin_auto_canny_sigma.setValue(0.33)
        self._label_auto_canny_sigma = QLabel()
        auto_canny_row.addWidget(self._chk_auto_canny)
        auto_canny_row.addWidget(self._label_auto_canny_sigma)
        auto_canny_row.addWidget(self._spin_auto_canny_sigma)
        auto_canny_row.addStretch()
        form.addRow(self._make_row_widget(auto_canny_row))

        # Blur Kernel
        self._spin_blur = QSpinBox()
        self._spin_blur.setRange(1, 31)
        self._spin_blur.setSingleStep(2)
        self._spin_blur.setValue(5)
        self._label_blur = QLabel()
        form.addRow(self._label_blur, self._spin_blur)

        # Bilateral Filter
        bilateral_row = QHBoxLayout()
        self._chk_bilateral = QCheckBox()
        self._chk_bilateral.setChecked(False)
        self._spin_bilateral_d = QSpinBox()
        self._spin_bilateral_d.setRange(3, 25)
        self._spin_bilateral_d.setSingleStep(2)
        self._spin_bilateral_d.setValue(9)
        self._spin_bilateral_d.setEnabled(False)
        self._label_bilateral_d = QLabel()
        bilateral_row.addWidget(self._chk_bilateral)
        bilateral_row.addWidget(self._label_bilateral_d)
        bilateral_row.addWidget(self._spin_bilateral_d)
        bilateral_row.addStretch()
        form.addRow(self._make_row_widget(bilateral_row))

        # Epsilon
        self._spin_epsilon = QDoubleSpinBox()
        self._spin_epsilon.setRange(0.0001, 1.0)
        self._spin_epsilon.setDecimals(4)
        self._spin_epsilon.setSingleStep(0.001)
        self._spin_epsilon.setValue(0.002)
        self._label_epsilon = QLabel()
        form.addRow(self._label_epsilon, self._spin_epsilon)

        # Skip Points
        self._spin_skip = QSpinBox()
        self._spin_skip.setRange(1, 100)
        self._spin_skip.setValue(2)
        self._label_skip = QLabel()
        form.addRow(self._label_skip, self._spin_skip)

        # Min Area
        self._spin_min_area = QSpinBox()
        self._spin_min_area.setRange(1, 100000)
        self._spin_min_area.setValue(50)
        self._label_min_area = QLabel()
        form.addRow(self._label_min_area, self._spin_min_area)

        # Morph Close
        self._spin_morph = QSpinBox()
        self._spin_morph.setRange(0, 31)
        self._spin_morph.setValue(0)
        self._label_morph = QLabel()
        form.addRow(self._label_morph, self._spin_morph)

        # Dedup Distance
        self._spin_dedup = QDoubleSpinBox()
        self._spin_dedup.setRange(0.0, 50.0)
        self._spin_dedup.setDecimals(1)
        self._spin_dedup.setSingleStep(0.5)
        self._spin_dedup.setValue(2.0)
        self._label_dedup = QLabel()
        form.addRow(self._label_dedup, self._spin_dedup)

        # Neighbor Sort
        self._chk_neighbor = QCheckBox()
        self._chk_neighbor.setChecked(False)
        self._label_sort = QLabel()
        form.addRow(self._label_sort, self._chk_neighbor)

        # Target Size
        target_row = QHBoxLayout()
        self._chk_target = QCheckBox()
        self._chk_target.setChecked(False)
        self._spin_target_w = QSpinBox()
        self._spin_target_w.setRange(1, 8192)
        self._spin_target_w.setValue(800)
        self._spin_target_w.setEnabled(False)
        self._spin_target_h = QSpinBox()
        self._spin_target_h.setRange(1, 8192)
        self._spin_target_h.setValue(600)
        self._spin_target_h.setEnabled(False)
        target_row.addWidget(self._chk_target)
        self._label_target_w = QLabel()
        target_row.addWidget(self._label_target_w)
        target_row.addWidget(self._spin_target_w)
        self._label_target_h = QLabel()
        target_row.addWidget(self._label_target_h)
        target_row.addWidget(self._spin_target_h)
        self._label_target_size = QLabel()
        form.addRow(self._label_target_size, self._make_row_widget(target_row))

        # Edge Mode
        self._combo_edge_mode = QComboBox()
        self._combo_edge_mode.addItems(["Grayscale", "RGB Channels", "LAB Channels"])
        self._label_edge_mode = QLabel()
        form.addRow(self._label_edge_mode, self._combo_edge_mode)

        # Inner Contours
        inner_row = QHBoxLayout()
        self._chk_inner_contours = QCheckBox()
        self._chk_inner_contours.setChecked(False)
        self._spin_hierarchy_depth = QSpinBox()
        self._spin_hierarchy_depth.setRange(0, 10)
        self._spin_hierarchy_depth.setValue(2)
        self._spin_hierarchy_depth.setEnabled(False)
        self._label_hierarchy_depth = QLabel()
        inner_row.addWidget(self._chk_inner_contours)
        inner_row.addWidget(self._label_hierarchy_depth)
        inner_row.addWidget(self._spin_hierarchy_depth)
        self._label_inner_contours = QLabel()
        form.addRow(self._label_inner_contours, self._make_row_widget(inner_row))

        return self._group_params

    # ── Window Group ──────────────────────────────────────────────────────

    def _build_window_group(self) -> QGroupBox:
        self._group_window = QGroupBox()
        ly = QHBoxLayout(self._group_window)
        self._combo_windows = QComboBox()
        self._combo_windows.setMinimumWidth(180)
        self._btn_refresh = QPushButton()
        ly.addWidget(self._combo_windows, 1)
        ly.addWidget(self._btn_refresh)
        return self._group_window

    # ── Canvas Offset Group ───────────────────────────────────────────────

    def _build_canvas_group(self) -> QGroupBox:
        self._group_canvas = QGroupBox()
        ly = QVBoxLayout(self._group_canvas)
        grid = QHBoxLayout()
        self._canvas_labels = []
        fields = [
            ("label_canvas_l", "_spin_canvas_l", 0, 99999, 0),
            ("label_canvas_t", "_spin_canvas_t", 0, 99999, 0),
            ("label_canvas_w", "_spin_canvas_w", 0, 99999, 0),
            ("label_canvas_h", "_spin_canvas_h", 0, 99999, 0),
        ]
        for key, attr, lo, hi, val in fields:
            lbl = QLabel()
            self._canvas_labels.append(lbl)
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(val)
            setattr(self, attr, sp)
            grid.addWidget(lbl)
            grid.addWidget(sp)
        ly.addLayout(grid)

        self._btn_auto_fill = QPushButton()
        ly.addWidget(self._btn_auto_fill)

        self._btn_select_canvas = QPushButton()
        ly.addWidget(self._btn_select_canvas)
        return self._group_canvas

    # ── Mouse Settings Group ──────────────────────────────────────────────

    def _build_mouse_group(self) -> QGroupBox:
        from PySide6.QtWidgets import QRadioButton, QButtonGroup

        self._group_mouse = QGroupBox()
        vly = QVBoxLayout(self._group_mouse)

        # Draw target radio buttons
        radio_ly = QHBoxLayout()
        self._radio_draw_window = QRadioButton()
        self._radio_draw_window.setChecked(True)
        self._radio_draw_board = QRadioButton()
        self._radio_group_target = QButtonGroup(self)
        self._radio_group_target.addButton(self._radio_draw_window, 0)
        self._radio_group_target.addButton(self._radio_draw_board, 1)
        radio_ly.addWidget(self._radio_draw_window)
        radio_ly.addWidget(self._radio_draw_board)
        radio_ly.addStretch()
        vly.addLayout(radio_ly)

        # Window-mode settings (existing, wrapped)
        self._window_settings_widget = QWidget()
        form = QFormLayout(self._window_settings_widget)

        self._spin_speed = QDoubleSpinBox()
        self._spin_speed.setRange(0.0, 1.0)
        self._spin_speed.setDecimals(4)
        self._spin_speed.setSingleStep(0.001)
        self._spin_speed.setValue(0.002)
        self._label_speed = QLabel()
        form.addRow(self._label_speed, self._spin_speed)

        self._spin_pause = QDoubleSpinBox()
        self._spin_pause.setRange(0.0, 10.0)
        self._spin_pause.setDecimals(1)
        self._spin_pause.setSingleStep(0.1)
        self._spin_pause.setValue(0.1)
        self._label_pause = QLabel()
        form.addRow(self._label_pause, self._spin_pause)

        self._spin_step = QSpinBox()
        self._spin_step.setRange(1, 100)
        self._spin_step.setValue(5)
        self._label_step = QLabel()
        form.addRow(self._label_step, self._spin_step)

        self._spin_delay = QDoubleSpinBox()
        self._spin_delay.setRange(0.0, 60.0)
        self._spin_delay.setDecimals(1)
        self._spin_delay.setSingleStep(1.0)
        self._spin_delay.setValue(3.0)
        self._label_delay = QLabel()
        form.addRow(self._label_delay, self._spin_delay)

        self._chk_pause_between = QCheckBox()
        self._chk_pause_between.setChecked(True)
        form.addRow(self._chk_pause_between)

        self._combo_button = QComboBox()
        self._combo_button.addItems(["left", "right", "middle", "x1", "x2"])
        self._label_button = QLabel()
        form.addRow(self._label_button, self._combo_button)

        self._chk_manual = QCheckBox()
        self._chk_manual.setChecked(False)
        form.addRow(self._chk_manual)

        vly.addWidget(self._window_settings_widget)

        # Board-mode settings (new)
        self._board_settings_widget = QWidget()
        self._board_settings_widget.setVisible(False)
        bly = QFormLayout(self._board_settings_widget)

        self._btn_board_color = QPushButton()
        self._btn_board_color.setFixedSize(32, 32)
        self._btn_board_color.setStyleSheet(
            "QPushButton { background: #000000; border: 1px solid #888; border-radius: 3px; }"
        )
        self._btn_board_color.clicked.connect(self._on_board_color_pick)
        self._label_board_color = QLabel()
        bly.addRow(self._label_board_color, self._btn_board_color)

        self._spin_board_width = QSpinBox()
        self._spin_board_width.setRange(1, 40)
        self._spin_board_width.setValue(3)
        self._label_board_width = QLabel()
        bly.addRow(self._label_board_width, self._spin_board_width)

        board_size_row = QHBoxLayout()
        self._spin_board_w = QSpinBox()
        self._spin_board_w.setRange(100, 4096)
        self._spin_board_w.setValue(800)
        self._spin_board_h = QSpinBox()
        self._spin_board_h.setRange(100, 4096)
        self._spin_board_h.setValue(600)
        board_size_row.addWidget(self._spin_board_w)
        board_size_row.addWidget(QLabel("x"))
        board_size_row.addWidget(self._spin_board_h)
        board_size_row.addStretch()
        self._label_board_size = QLabel()
        bly.addRow(self._label_board_size, self._make_row_widget(board_size_row))

        self._btn_open_blank_board = QPushButton()
        self._btn_open_blank_board.clicked.connect(self._on_open_blank_board)
        bly.addRow(self._btn_open_blank_board)

        vly.addWidget(self._board_settings_widget)

        # Make both widgets stretch to fill
        vly.addStretch()

        return self._group_mouse

    # ── Action Group ──────────────────────────────────────────────────────

    def _build_action_group(self) -> QGroupBox:
        self._group_actions = QGroupBox()
        ly = QVBoxLayout(self._group_actions)

        btn_row = QHBoxLayout()
        self._btn_dry_run = QPushButton()
        btn_row.addWidget(self._btn_dry_run)

        self._btn_start = QPushButton()
        self._btn_start.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; "
            "padding: 6px 16px; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        btn_row.addWidget(self._btn_start)

        self._btn_abort = QPushButton()
        self._btn_abort.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: bold; "
            "padding: 6px 16px; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        btn_row.addWidget(self._btn_abort)
        ly.addLayout(btn_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("")
        ly.addWidget(self._progress_bar)

        # Status label
        self._label_draw_status = QLabel("")
        self._label_draw_status.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        self._label_draw_status.setFont(font)
        ly.addWidget(self._label_draw_status)

        return self._group_actions

    # ── Right Panel ───────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        from canvas_selector import CanvasEditor

        panel = QWidget()
        panel.setObjectName("rightPanel")
        ly = QVBoxLayout(panel)

        self._tab_preview = QTabWidget()
        self._build_preview_tab("_label_original")
        self._build_preview_tab("_label_edges")
        self._build_preview_tab("_label_overlay")

        # 4th tab: embedded canvas editor
        self._canvas_editor = CanvasEditor()
        self._canvas_editor.selection_changed.connect(self._on_canvas_editor_changed)
        canvas_tab = QWidget()
        canvas_ly = QVBoxLayout(canvas_tab)
        canvas_ly.setContentsMargins(0, 0, 0, 0)
        canvas_ly.addWidget(self._canvas_editor)
        self._tab_preview.addTab(canvas_tab, "")  # text set in _retranslate_ui

        ly.addWidget(self._tab_preview, 1)

        self._info_panel = QTextEdit()
        self._info_panel.setReadOnly(True)
        self._info_panel.setMaximumHeight(180)
        mono = QFont("Consolas, monospace", 9)
        self._info_panel.setFont(mono)
        ly.addWidget(self._info_panel)

        return panel

    def _build_preview_tab(self, attr: str):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumSize(200, 200)
        scroll.setWidget(label)
        setattr(self, attr, label)
        self._tab_preview.addTab(scroll, "")  # Text set in _retranslate_ui

    # ── Signal Connections ────────────────────────────────────────────────

    def _connect_signals(self):
        self._btn_browse.clicked.connect(self._on_browse)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._process_image)

        self._slider_canny_low.valueChanged.connect(self._spin_canny_low.setValue)
        self._spin_canny_low.valueChanged.connect(self._slider_canny_low.setValue)
        self._slider_canny_high.valueChanged.connect(self._spin_canny_high.setValue)
        self._spin_canny_high.valueChanged.connect(self._slider_canny_high.setValue)

        for w in [
            self._spin_canny_low, self._spin_canny_high,
            self._spin_blur, self._spin_epsilon, self._spin_skip,
            self._spin_min_area, self._spin_morph, self._spin_dedup,
            self._spin_target_w, self._spin_target_h,
        ]:
            w.valueChanged.connect(self._debounce_start)
        for w in [self._chk_neighbor, self._chk_target, self._chk_inner_contours]:
            w.stateChanged.connect(self._debounce_start)

        self._combo_edge_mode.currentIndexChanged.connect(self._debounce_start)
        self._spin_hierarchy_depth.valueChanged.connect(self._debounce_start)

        self._chk_target.stateChanged.connect(self._on_target_toggle)
        self._chk_inner_contours.stateChanged.connect(self._on_inner_contours_toggle)
        self._chk_auto_canny.stateChanged.connect(self._on_auto_canny_toggle)
        self._chk_bilateral.stateChanged.connect(self._on_bilateral_toggle)

        self._combo_windows.currentIndexChanged.connect(self._capture_window_screenshot)

        self._btn_refresh.clicked.connect(self._on_refresh_windows)
        self._btn_auto_fill.clicked.connect(self._on_auto_fill)
        self._btn_select_canvas.clicked.connect(self._on_select_canvas)

        for attr in ["_spin_canvas_l", "_spin_canvas_t", "_spin_canvas_w", "_spin_canvas_h"]:
            getattr(self, attr).valueChanged.connect(self._on_canvas_spinbox_changed)

        self._combo_presets.currentIndexChanged.connect(self._on_preset_changed)

        self._radio_group_target.idClicked.connect(self._on_draw_target_changed)

        self._btn_dry_run.clicked.connect(self._on_dry_run)
        self._btn_start.clicked.connect(self._on_start_drawing)
        self._btn_abort.clicked.connect(self._on_abort)

    # ── Slot: Debounce ────────────────────────────────────────────────────

    def _debounce_start(self):
        self._debounce.start(300)

    # ── Slot: Browse ──────────────────────────────────────────────────────

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu_file_open"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;All Files (*.*)"
        )
        if path:
            self._image_path = path
            self._line_path.setText(path)
            self._process_image()

    # ── Slot: Target Size Toggle ──────────────────────────────────────────

    def _on_preset_changed(self, index: int):
        if index < 0 or index >= len(PRESETS) or self._applying_preset:
            return
        self._applying_preset = True
        p = PRESETS[index]["params"]

        # Edge detection
        self._combo_edge_mode.setCurrentIndex(p["edge_mode"])
        self._chk_auto_canny.setChecked(p["chk_auto_canny"])
        self._spin_auto_canny_sigma.setValue(p["auto_canny_sigma"])
        self._spin_canny_low.setValue(p["canny_low"])
        self._spin_canny_high.setValue(p["canny_high"])
        self._spin_blur.setValue(p["blur_ksize"])
        self._chk_bilateral.setChecked(p["chk_bilateral"])
        self._spin_bilateral_d.setValue(p["bilateral_d"])

        # Contour
        self._spin_epsilon.setValue(p["epsilon"])
        self._spin_skip.setValue(p["skip_points"])
        self._spin_min_area.setValue(p["min_area"])
        self._chk_inner_contours.setChecked(p["chk_inner"])
        self._spin_hierarchy_depth.setValue(p["hierarchy_depth"])

        # Other
        self._spin_dedup.setValue(p["dedup"])
        self._spin_morph.setValue(p["morph"])

        self._applying_preset = False
        self._debounce_start()

    def _on_target_toggle(self, state):
        enabled = state == Qt.Checked
        self._spin_target_w.setEnabled(enabled)
        self._spin_target_h.setEnabled(enabled)
        self._debounce_start()

    def _on_inner_contours_toggle(self, state):
        self._spin_hierarchy_depth.setEnabled(state == Qt.Checked)
        self._debounce_start()

    def _on_auto_canny_toggle(self, state):
        enabled = state != Qt.Checked
        self._slider_canny_low.setEnabled(enabled)
        self._spin_canny_low.setEnabled(enabled)
        self._slider_canny_high.setEnabled(enabled)
        self._spin_canny_high.setEnabled(enabled)
        self._spin_auto_canny_sigma.setEnabled(state == Qt.Checked)
        self._debounce_start()

    def _on_bilateral_toggle(self, state):
        self._spin_bilateral_d.setEnabled(state == Qt.Checked)
        self._debounce_start()

    # ── Slot: Process Image ───────────────────────────────────────────────

    def _process_image(self):
        if not self._image_path:
            return

        import cv2
        import numpy as np
        from image_processor import process_image, resize_fit

        cfg = self._build_image_config()

        try:
            result = process_image(self._image_path, cfg)
        except FileNotFoundError as e:
            self._show_error(tr("error_title_image"), str(e))
            self._clear_previews()
            return
        except ValueError as e:
            self._show_error(tr("error_title_image"), str(e))
            self._clear_previews()
            return

        self._process_result = result

        raw = cv2.imread(self._image_path)
        if raw is None:
            self._clear_previews()
            return

        if raw.ndim == 3 and raw.shape[2] == 4:
            raw = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

        h, w = raw.shape[:2]
        tw, th = result.img_width, result.img_height
        canvas_img = resize_fit(raw, (tw, th))
        self._raw_image = canvas_img

        if result.edges_image is not None:
            self._edges_image = cv2.cvtColor(result.edges_image, cv2.COLOR_GRAY2BGR)
        else:
            self._edges_image = np.zeros((th, tw, 3), dtype=np.uint8)

        overlay = canvas_img.copy()
        if result.contours:
            draw_contours = [c.points.reshape(-1, 1, 2).astype(np.int32) for c in result.contours]
            cv2.drawContours(overlay, draw_contours, -1, (0, 255, 0), 2)
        self._overlay_image = overlay

        self._update_preview_tabs()
        self._update_info_panel()

        if not result.contours:
            self._status_bar.showMessage(tr("status_no_contours"))

    def _update_preview_tabs(self):
        if self._raw_image is not None:
            pix = cv2_to_qpixmap(self._raw_image)
            self._label_original.setPixmap(self._scale_pixmap(pix, self._label_original))
        if self._edges_image is not None:
            pix = cv2_to_qpixmap(self._edges_image)
            self._label_edges.setPixmap(self._scale_pixmap(pix, self._label_edges))
        if self._overlay_image is not None:
            pix = cv2_to_qpixmap(self._overlay_image)
            self._label_overlay.setPixmap(self._scale_pixmap(pix, self._label_overlay))

    def _scale_pixmap(self, pix: QPixmap, label: QLabel) -> QPixmap:
        size = label.size()
        if size.width() > 10 and size.height() > 10:
            return pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pix

    def _clear_previews(self):
        for attr in ["_label_original", "_label_edges", "_label_overlay"]:
            label = getattr(self, attr)
            label.setText(tr("label_no_image_short"))
            label.setPixmap(None)
        self._raw_image = None
        self._edges_image = None
        self._overlay_image = None
        self._process_result = None
        self._info_panel.clear()

    def _update_info_panel(self):
        if not self._process_result:
            self._info_panel.clear()
            return
        r = self._process_result
        total_pts = sum(c.points.shape[0] for c in r.contours)
        closed = sum(1 for c in r.contours if c.is_closed)
        open_n = len(r.contours) - closed
        lines = [
            tr("info_contours").format(n=len(r.contours), c=closed, o=open_n),
            tr("info_points").format(n=total_pts),
            tr("info_size").format(w=r.img_width, h=r.img_height),
        ]
        if r.dedup_removed > 0:
            lines.append(tr("info_dedup").format(n=r.dedup_removed))
        self._info_panel.setText("\n".join(lines))

        self._status_bar.showMessage(
            tr("status_processed").format(n=len(r.contours), p=total_pts)
        )

    # ── Slot: Refresh Windows ─────────────────────────────────────────────

    def _on_refresh_windows(self):
        from window_finder import list_all_windows
        self._combo_windows.clear()
        try:
            windows = list_all_windows()
        except ImportError:
            self._combo_windows.addItem(tr("combo_no_pkg"))
            return

        if not windows:
            self._combo_windows.addItem(tr("combo_no_windows"))
            return

        for w in windows:
            display = f"{w.title}  ({w.width}x{w.height})"
            self._combo_windows.addItem(display, userData=w)

    # ── Slot: Auto-fill Canvas ────────────────────────────────────────────

    def _on_auto_fill(self):
        from window_finder import WindowInfo
        win = self._combo_windows.currentData()
        if isinstance(win, WindowInfo):
            self._spin_canvas_l.setValue(0)
            self._spin_canvas_t.setValue(0)
            self._spin_canvas_w.setValue(win.width)
            self._spin_canvas_h.setValue(win.height)

    def _on_select_canvas(self):
        from window_finder import WindowInfo, activate_window
        from canvas_selector import select_canvas
        win = self._combo_windows.currentData()
        if not isinstance(win, WindowInfo):
            self._show_error(tr("error_title_draw"), tr("error_no_window"))
            return

        self._selector = select_canvas(win)
        self._selector.confirmed.connect(self._on_canvas_confirmed)
        self._selector.cancelled.connect(self._on_canvas_cancelled)

        self._selector.show()  # show before minimizing so Qt.Tool window appears
        try:
            activate_window(win)
        except Exception:
            pass
        self.showMinimized()

    def _on_canvas_confirmed(self, left: int, top: int, width: int, height: int):
        self._spin_canvas_l.setValue(left)
        self._spin_canvas_t.setValue(top)
        self._spin_canvas_w.setValue(width)
        self._spin_canvas_h.setValue(height)
        self.showNormal()
        self.activateWindow()

    def _on_canvas_cancelled(self):
        self.showNormal()
        self.activateWindow()

    def _capture_window_screenshot(self):
        """Capture the selected window and load it into the canvas editor."""
        from window_finder import WindowInfo, capture_window_screenshot
        win = self._combo_windows.currentData()
        if not isinstance(win, WindowInfo):
            self._canvas_editor.set_screenshot(QPixmap(), 0, 0)
            return
        arr = capture_window_screenshot(win)
        if arr is None:
            self._canvas_editor.set_screenshot(QPixmap(), 0, 0)
            return
        pix = cv2_to_qpixmap(arr)
        self._canvas_editor.set_screenshot(pix, win.width, win.height)

    def _on_canvas_editor_changed(self, left: int, top: int, width: int, height: int):
        """Canvas editor selection → spinboxes (with feedback guard)."""
        if self._syncing_canvas:
            return
        self._syncing_canvas = True
        self._spin_canvas_l.setValue(left)
        self._spin_canvas_t.setValue(top)
        self._spin_canvas_w.setValue(width)
        self._spin_canvas_h.setValue(height)
        self._syncing_canvas = False

    def _on_canvas_spinbox_changed(self):
        """Spinboxes → canvas editor (with feedback guard)."""
        if self._syncing_canvas:
            return
        self._syncing_canvas = True
        self._canvas_editor.set_selection(
            self._spin_canvas_l.value(),
            self._spin_canvas_t.value(),
            self._spin_canvas_w.value(),
            self._spin_canvas_h.value(),
        )
        self._syncing_canvas = False

    # ── Slot: Dry Run ─────────────────────────────────────────────────────

    def _on_dry_run(self):
        if not self._process_result or not self._process_result.contours:
            self._show_error(tr("error_title_dryrun"), tr("error_no_contours"))
            return

        from window_finder import contours_to_strokes, estimate_draw_time

        canvas = self._build_canvas()
        if canvas is None:
            self._show_error(tr("error_title_dryrun"), tr("error_no_window"))
            return

        result = self._process_result
        strokes = contours_to_strokes(
            result.contours, result.img_width, result.img_height, canvas
        )

        mouse_cfg = self._build_mouse_config()
        est_time = estimate_draw_time(
            strokes, mouse_cfg.start_delay, mouse_cfg.speed,
            mouse_cfg.contour_pause, mouse_cfg.pause_between_strokes,
            mouse_cfg.interpolate_step,
        )
        self._estimated_time = est_time

        closed = sum(1 for c in result.contours if c.is_closed)
        open_n = len(result.contours) - closed

        total_pts = sum(len(s.points) for s in strokes)
        interp_overhead = 0
        for s in strokes:
            for i in range(1, len(s.points)):
                dx = s.points[i][0] - s.points[i - 1][0]
                dy = s.points[i][1] - s.points[i - 1][1]
                d = (dx * dx + dy * dy) ** 0.5
                if d > mouse_cfg.interpolate_step:
                    interp_overhead += int(d / mouse_cfg.interpolate_step) - 1
        effective_pts = total_pts + interp_overhead
        pause_count = len(strokes) if mouse_cfg.pause_between_strokes else 0

        sort_method = tr("dryrun_sort_nn") if self._chk_neighbor.isChecked() else tr("dryrun_sort_area")
        lines = [
            tr("dryrun_image").format(path=self._image_path, w=result.img_width, h=result.img_height),
            tr("dryrun_contours").format(n=len(result.contours), c=closed, o=open_n),
            tr("dryrun_points").format(n=total_pts),
            tr("dryrun_est_time").format(t=est_time),
            tr("dryrun_formula").format(
                d=mouse_cfg.start_delay, p=effective_pts, s=mouse_cfg.speed,
                c=pause_count, ps=mouse_cfg.contour_pause,
            ),
            tr("dryrun_canvas").format(x=canvas.screen_left, y=canvas.screen_top,
                                       w=canvas.width, h=canvas.height),
            tr("dryrun_window").format(
                title=canvas.window.title, l=canvas.window.left, t=canvas.window.top,
                w=canvas.window.width, h=canvas.window.height,
            ),
            tr("dryrun_sort").format(method=sort_method),
        ]
        if self._spin_dedup.value() > 0:
            lines.append(tr("dryrun_dedup").format(
                d=self._spin_dedup.value(), n=result.dedup_removed,
            ))

        self._info_panel.setText("\n".join(lines))
        self._status_bar.showMessage(
            tr("status_dry_run").format(s=len(strokes), t=est_time)
        )

    # ── Slot: Start Drawing ───────────────────────────────────────────────

    def _on_start_drawing(self):
        if not self._process_result or not self._process_result.contours:
            self._show_error(tr("error_title_draw"), tr("error_no_contours"))
            return

        if self._radio_draw_board.isChecked():
            self._start_board_drawing()
        else:
            self._start_window_drawing()

    def _start_window_drawing(self):
        from window_finder import contours_to_strokes, estimate_draw_time, activate_window
        from ui_thread_worker import DrawWorker

        canvas = self._build_canvas()
        if canvas is None:
            self._show_error(tr("error_title_draw"), tr("error_no_window"))
            return

        strokes = contours_to_strokes(
            self._process_result.contours,
            self._process_result.img_width,
            self._process_result.img_height,
            canvas,
        )
        if not strokes:
            self._show_error(tr("error_title_draw"), tr("error_no_strokes"))
            return

        mouse_cfg = self._build_mouse_config()

        self._estimated_time = estimate_draw_time(
            strokes, mouse_cfg.start_delay, mouse_cfg.speed,
            mouse_cfg.contour_pause, mouse_cfg.pause_between_strokes,
            mouse_cfg.interpolate_step,
        )

        self._worker = DrawWorker(
            strokes, mouse_cfg, self._estimated_time, self
        )
        self._worker.countdown_tick.connect(self._on_countdown_tick)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.elapsed_update.connect(self._on_elapsed_update)
        self._worker.finished.connect(self._on_draw_finished)
        self._worker.error.connect(self._on_draw_error)

        try:
            activate_window(canvas.window)
        except Exception:
            pass
        self.showMinimized()

        self._worker.start()

    # ── Board drawing ──────────────────────────────────────────────────────

    def _start_board_drawing(self):
        from virtual_canvas import BoardConfig, VirtualCanvas

        cfg = BoardConfig(
            canvas_width=self._spin_board_w.value(),
            canvas_height=self._spin_board_h.value(),
            brush_color=self._board_color,
            brush_width=self._spin_board_width.value(),
            auto_draw_speed=self._spin_speed.value(),
        )

        self._board = VirtualCanvas(
            self._process_result.contours,
            self._process_result.img_width,
            self._process_result.img_height,
            cfg,
        )
        self._board.confirmed_to_window.connect(self._on_board_confirm)
        self._board.closed.connect(self._on_board_closed)
        self._board.show()

    def _on_board_confirm(self, temp_path: str):
        self._board_temp_path = temp_path
        self._board = None
        # Process the board image and draw to window
        import cv2
        from image_processor import process_image
        from window_finder import contours_to_strokes, estimate_draw_time, activate_window
        from ui_thread_worker import DrawWorker

        canvas = self._build_canvas()
        if canvas is None:
            self._show_error(tr("error_title_draw"), tr("error_no_window"))
            self._cleanup_board_temp()
            return

        try:
            result = process_image(temp_path, self._build_image_config())
        except Exception as e:
            self._show_error(tr("error_title_draw"), str(e))
            self._cleanup_board_temp()
            return

        if not result.contours:
            self._show_error(tr("error_title_draw"), tr("error_no_contours"))
            self._cleanup_board_temp()
            return

        strokes = contours_to_strokes(
            result.contours, result.img_width, result.img_height, canvas,
        )
        if not strokes:
            self._show_error(tr("error_title_draw"), tr("error_no_strokes"))
            self._cleanup_board_temp()
            return

        mouse_cfg = self._build_mouse_config()
        self._estimated_time = estimate_draw_time(
            strokes, mouse_cfg.start_delay, mouse_cfg.speed,
            mouse_cfg.contour_pause, mouse_cfg.pause_between_strokes,
            mouse_cfg.interpolate_step,
        )

        self._worker = DrawWorker(strokes, mouse_cfg, self._estimated_time, self)
        self._worker.countdown_tick.connect(self._on_countdown_tick)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.elapsed_update.connect(self._on_elapsed_update)
        self._worker.finished.connect(self._on_draw_finished)
        self._worker.error.connect(self._on_draw_error)

        try:
            activate_window(canvas.window)
        except Exception:
            pass
        self.showMinimized()
        self._worker.start()

    def _on_board_closed(self):
        self._cleanup_board_temp()
        self._board = None

    def _cleanup_board_temp(self):
        if self._board_temp_path:
            import os
            try:
                os.unlink(self._board_temp_path)
            except OSError:
                pass
            self._board_temp_path = None

    def _on_open_blank_board(self):
        from virtual_canvas import BoardConfig, VirtualCanvas

        cfg = BoardConfig(
            canvas_width=self._spin_board_w.value(),
            canvas_height=self._spin_board_h.value(),
            brush_color=self._board_color,
            brush_width=self._spin_board_width.value(),
            auto_draw_speed=0.002,
        )
        # No contours — opens in pure edit mode
        self._board = VirtualCanvas([], 1, 1, cfg)
        self._board.confirmed_to_window.connect(self._on_board_confirm)
        self._board.closed.connect(self._on_board_closed)
        self._board.show()

    def _on_draw_target_changed(self, target_id: int):
        is_window = target_id == 0
        self._window_settings_widget.setVisible(is_window)
        self._board_settings_widget.setVisible(not is_window)

    # ── Board color picker ─────────────────────────────────────────────────

    def _on_board_color_pick(self):
        color = QColorDialog.getColor(Qt.black, self, tr("label_board_color"))
        if color.isValid():
            self._board_color = color.name()
            self._btn_board_color.setStyleSheet(
                f"QPushButton {{ background: {color.name()}; "
                f"border: 1px solid #888; border-radius: 3px; }}"
            )

    # ── Screenshot ─────────────────────────────────────────────────────────

    def _on_screenshot(self):
        """Hide window, capture full screen, then restore and prompt save."""
        self.hide()
        QApplication.processEvents()
        import time
        time.sleep(0.25)

        screen = QApplication.primaryScreen()
        if screen is None:
            self.show()
            self._show_error(tr("error_title_draw"), tr("error_screenshot_failed"))
            return

        geo = screen.geometry()
        pixmap = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
        self.show()

        if pixmap.isNull():
            self._show_error(tr("error_title_draw"), tr("error_screenshot_failed"))
            return

        qimg = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
        w, h = qimg.width(), qimg.height()
        bpl = qimg.bytesPerLine()
        ptr = qimg.constBits()
        import numpy as np
        arr = np.array(ptr, copy=True).reshape(h, bpl)
        if bpl != w * 3:
            arr = arr[:, :w * 3]
        arr = arr.reshape(h, w, 3)[..., ::-1]  # RGB → BGR

        path, _ = QFileDialog.getSaveFileName(
            self, tr("btn_screenshot"), "screenshot.png",
            "PNG (*.png);;JPEG (*.jpg);;All Files (*.*)",
        )
        if not path:
            return

        import cv2
        cv2.imwrite(path, arr)
        self._status_bar.showMessage(tr("screenshot_saved").format(path=path))

    # ── Slot: Abort ───────────────────────────────────────────────────────

    def _on_abort(self):
        if self._worker is not None:
            self._worker.request_abort()
            self._status_bar.showMessage(tr("status_aborting"))
            self._btn_abort.setEnabled(False)

    # ── Slot: Countdown Tick ──────────────────────────────────────────────

    @Slot(int)
    def _on_countdown_tick(self, remaining: int):
        if self._chk_manual.isChecked():
            self._label_draw_status.setText(tr("label_countdown_manual").format(n=remaining))
        else:
            self._label_draw_status.setText(tr("label_countdown").format(n=remaining))
        self._status_bar.showMessage(tr("status_countdown").format(n=remaining))

    # ── Slot: Phase Changed ───────────────────────────────────────────────

    @Slot(str)
    def _on_phase_changed(self, phase: str):
        if phase == "countdown":
            self._set_controls_enabled(False)
            self._btn_abort.setEnabled(True)
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat(tr("progress_countdown"))
        elif phase == "drawing":
            self._set_controls_enabled(False)
            self._btn_abort.setEnabled(True)
            self._progress_bar.setFormat(tr("progress_drawing"))
            if self._chk_manual.isChecked():
                self._label_draw_status.setText(tr("label_drawing_manual"))
                self._status_bar.showMessage(tr("status_drawing_manual"))
            else:
                self._label_draw_status.setText(tr("label_drawing"))
                self._status_bar.showMessage(tr("status_drawing"))
        elif phase == "done":
            self._set_controls_enabled(True)
            self._btn_abort.setEnabled(False)
            self._progress_bar.setFormat("")
            self._worker = None
        elif phase == "error":
            self._set_controls_enabled(True)
            self._btn_abort.setEnabled(False)
            self._progress_bar.setFormat("Error")
            self._worker = None
        else:  # idle
            self._set_controls_enabled(True)
            self._btn_abort.setEnabled(False)
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("")
            self._label_draw_status.setText("")

    # ── Slot: Elapsed Update ──────────────────────────────────────────────

    @Slot(float)
    def _on_elapsed_update(self, elapsed: float):
        if self._estimated_time > 0:
            pct = min(99, int(elapsed / self._estimated_time * 100))
            self._progress_bar.setValue(pct)
        if self._chk_manual.isChecked():
            self._label_draw_status.setText(tr("label_elapsed_manual").format(t=elapsed))
        else:
            self._label_draw_status.setText(tr("label_elapsed").format(t=elapsed))

    # ── Slot: Draw Finished ───────────────────────────────────────────────

    @Slot(object)
    def _on_draw_finished(self, result: DrawResult):
        self.showNormal()
        self.activateWindow()

        if result.aborted:
            self._progress_bar.setValue(0)
            msg = tr("status_aborted").format(
                d=result.strokes_drawn, t=result.strokes_total,
                p=result.points_moved, e=result.elapsed_seconds,
            )
        else:
            self._progress_bar.setValue(100)
            msg = tr("status_done").format(
                d=result.strokes_drawn, t=result.strokes_total,
                p=result.points_moved, e=result.elapsed_seconds,
            )
        self._label_draw_status.setText(msg)
        self._status_bar.showMessage(msg)
        self._info_panel.setText(msg)

    # ── Slot: Draw Error ──────────────────────────────────────────────────

    @Slot(str)
    def _on_draw_error(self, err: str):
        self.showNormal()
        self.activateWindow()
        self._show_error(tr("error_title_drawing"), err)
        self._status_bar.showMessage(tr("error_title_drawing") + f": {err}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _build_image_config(self) -> ImageConfig:
        from image_processor import ImageConfig
        target = None
        if self._chk_target.isChecked():
            target = (self._spin_target_w.value(), self._spin_target_h.value())
        edge_modes = ["gray", "rgb", "lab"]
        return ImageConfig(
            canny_low=self._spin_canny_low.value(),
            canny_high=self._spin_canny_high.value(),
            blur_ksize=(self._spin_blur.value(), self._spin_blur.value()),
            epsilon_factor=self._spin_epsilon.value(),
            skip_points=self._spin_skip.value(),
            min_contour_area=self._spin_min_area.value(),
            target_size=target,
            morph_close_ksize=self._spin_morph.value(),
            dedup_distance=self._spin_dedup.value(),
            neighbor_sort=self._chk_neighbor.isChecked(),
            include_inner_contours=self._chk_inner_contours.isChecked(),
            max_hierarchy_depth=self._spin_hierarchy_depth.value(),
            edge_mode=edge_modes[self._combo_edge_mode.currentIndex()],
            auto_canny=self._chk_auto_canny.isChecked(),
            auto_canny_sigma=self._spin_auto_canny_sigma.value(),
            bilateral_filter=self._chk_bilateral.isChecked(),
            bilateral_d=self._spin_bilateral_d.value(),
        )

    def _build_mouse_config(self) -> MouseConfig:
        from mouse_controller import MouseConfig
        return MouseConfig(
            speed=self._spin_speed.value(),
            pause_between_strokes=self._chk_pause_between.isChecked(),
            start_delay=self._spin_delay.value(),
            contour_pause=self._spin_pause.value(),
            interpolate_step=self._spin_step.value(),
            button=self._combo_button.currentText(),
            manual_mode=self._chk_manual.isChecked(),
        )

    def _build_canvas(self) -> CanvasRegion | None:
        from window_finder import WindowInfo, build_canvas
        win = self._combo_windows.currentData()
        if not isinstance(win, WindowInfo):
            return None
        w = self._spin_canvas_w.value() or win.width or 0
        h = self._spin_canvas_h.value() or win.height or 0
        return build_canvas(
            win,
            self._spin_canvas_l.value(),
            self._spin_canvas_t.value(),
            w, h,
        )

    def _set_controls_enabled(self, enabled: bool):
        self._btn_browse.setEnabled(enabled)
        self._btn_dry_run.setEnabled(enabled)
        self._btn_start.setEnabled(enabled)
        self._btn_refresh.setEnabled(enabled)
        self._btn_auto_fill.setEnabled(enabled)
        self._btn_select_canvas.setEnabled(enabled)
        self._act_screenshot.setEnabled(enabled)
        self._btn_open_blank_board.setEnabled(enabled)
        self._radio_draw_window.setEnabled(enabled)
        self._radio_draw_board.setEnabled(enabled)

    def _show_error(self, title: str, msg: str):
        QMessageBox.critical(self, title, msg)

    def _make_row_widget(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        return w

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("about_title"))
        dlg.resize(720, 560)
        dlg.setMinimumSize(500, 400)

        layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(tr("manual_html"))
        text.verticalScrollBar().setValue(0)
        layout.addWidget(text, 1)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        dlg.exec()

    def _restore_geometry(self):
        geo = self._settings.value("window_geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 750)

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.request_abort()
            if self._worker.isRunning():
                self._worker.wait(3000)
        if self._board is not None:
            self._board.close()
            self._board = None
        self._cleanup_board_temp()
        self._settings.setValue("window_geometry", self.saveGeometry())
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Drawer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()