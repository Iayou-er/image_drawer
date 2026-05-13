"""Internationalization: English and Chinese translations.

Usage:
    from i18n import tr, LANG
    label.setText(tr("key", LANG))
"""

LANGUAGES = {"en": "English", "zh": "中文"}

# Current language (set by UI)
_lang = "en"


def set_language(lang: str):
    global _lang
    if lang in LANGUAGES:
        _lang = lang


def get_language() -> str:
    return _lang


def tr(key: str, lang: str | None = None) -> str:
    """Return translated string for key in the given language."""
    if lang is None:
        lang = _lang
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get("en", key))


# ── Translation dictionary ────────────────────────────────────────────────
# Keys are organized by UI section. Values are {en: ..., zh: ...}.

_STRINGS: dict[str, dict[str, str]] = {
    # ── Window & Menu ──
    "app_title":              {"en": "Image Drawer",                          "zh": "图片绘制器"},
    "menu_file":              {"en": "&File",                                 "zh": "文件(&F)"},
    "menu_file_open":         {"en": "&Open Image...",                        "zh": "打开图片(&O)"},
    "menu_file_refresh":      {"en": "&Refresh Windows",                      "zh": "刷新窗口列表(&R)"},
    "menu_file_screenshot":          {"en": "&Screenshot",                   "zh": "截图(&S)"},
    "menu_file_screenshot_region":  {"en": "Select &Region...",               "zh": "自选区域(&R)..."},
    "menu_file_screenshot_full":    {"en": "&Full Screen\tCtrl+P",            "zh": "全屏截图(&F)\tCtrl+P"},
    "menu_file_exit":         {"en": "E&xit",                                 "zh": "退出(&X)"},
    "menu_language":          {"en": "&Language",                             "zh": "语言(&L)"},
    "menu_language_en":       {"en": "&English",                              "zh": "英文(&E)"},
    "menu_language_zh":       {"en": "中文 (&Chinese)",                       "zh": "中文(&C)"},
    "menu_help":              {"en": "&Help",                                 "zh": "帮助(&H)"},
    "menu_help_about":        {"en": "&About",                                "zh": "关于(&A)"},

    # ── About ──
    "about_title":            {"en": "About Image Drawer",                    "zh": "关于 图片绘制器"},

    # ── In-App User Manual (HTML) ─────────────────────────────────────────────
    "manual_html": {
        "en": """
<h2>Image Drawer</h2>
<p>Automatically draw image outlines onto any window canvas by controlling the mouse. Supports both CLI and GUI modes.</p>

<h3>Recommended Presets</h3>
	<p>Choose a preset from the dropdown in Image Parameters to get started quickly. Each preset tunes all parameters for a specific image type.</p>
	<table>
	<tr><th width=100>Preset</th><th width=115>Best for</th><th width=50>Edge</th><th width=45>Sigma</th><th width=40>Blur</th><th width=60>Bilateral</th><th width=55>Epsilon</th><th width=35>Skip</th><th width=50>Min Area</th><th width=40>Inner</th></tr>
	<tr><td><b>General</b></td><td>Most images</td><td>Gray</td><td>0.33</td><td>5</td><td>Off</td><td>0.002</td><td>2</td><td>50</td><td>Off</td></tr>
	<tr><td><b>Complex Illustration</b></td><td>Cartoon, line art</td><td>RGB</td><td>0.20</td><td>3</td><td>On (d=9)</td><td>0.001</td><td>1</td><td>10</td><td>On (d=2)</td></tr>
	<tr><td><b>Photo/Portrait</b></td><td>Photos, portraits</td><td>LAB</td><td>0.33</td><td>5</td><td>Off</td><td>0.002</td><td>2</td><td>30</td><td>On (d=3)</td></tr>
	<tr><td><b>Logo/Line Art</b></td><td>Logos, icons, text</td><td>Gray</td><td>0.25</td><td>3</td><td>Off</td><td>0.0005</td><td>1</td><td>5</td><td>On (d=1)</td></tr>
	</table>

	<h3>Interface Overview</h3>
<p>The GUI is split into a <b>left control panel</b> and a <b>right preview panel</b>.</p>

<hr>

<h3>Left Panel &mdash; Image</h3>
<table>
<tr><td width=130><b>Browse&hellip;</b></td><td>Open an image file (PNG/JPG/BMP/TIFF/WebP). Ctrl+O. After loading, edge detection runs automatically and results appear in the right tabs.</td></tr>
<tr><td><b>Path display</b></td><td>Read-only field showing the full path of the loaded image.</td></tr>
</table>

<h3>Left Panel &mdash; Image Parameters</h3>
<p>Adjust these to control edge detection and contour extraction. The right-side previews update in real time.</p>
<table>
<tr><th width=140>Parameter</th><th width=60>Default</th><th>Description</th></tr>
<tr><td><b>Canny Low</b></td><td>50</td><td>Low threshold for Canny edge detection. Pixels below this are ignored. Lower = more edges but more noise. Range 0&ndash;255.</td></tr>
<tr><td><b>Canny High</b></td><td>150</td><td>High threshold for Canny. Pixels above this are strong edges. If Low &ge; High, the two are auto-swapped.</td></tr>
<tr><td><b>Blur Kernel</b></td><td>5</td><td>Gaussian blur kernel size applied before edge detection. Larger = less noise but fewer edges. Must be odd (even values auto +1). Range 1&ndash;31.</td></tr>
<tr><td><b>Epsilon</b></td><td>0.002</td><td>Contour simplification factor. Larger = fewer points, rougher shapes. Formula: epsilon &times; contour perimeter. Range 0.0001&ndash;1.0.</td></tr>
<tr><td><b>Skip Points</b></td><td>2</td><td>Sample every N points along the contour. 1 = keep all, 5 = keep 1/5th. Reduces total points to speed up drawing.</td></tr>
<tr><td><b>Min Area</b></td><td>50</td><td>Minimum contour area in pixels. Smaller contours are discarded. Filters out noise and speckles.</td></tr>
<tr><td><b>Morph Close</b></td><td>0</td><td>Morphological close kernel size. 0 = disabled. Values 3&ndash;7 can bridge small gaps between nearby edges. Must be odd.</td></tr>
<tr><td><b>Dedup Dist</b></td><td>2.0</td><td>Chamfer-distance deduplication threshold in pixels. Contours closer than this are considered duplicates; only the larger one is kept. 0 = disabled.</td></tr>
<tr><td><b>Nearest-neighbor sort</b></td><td>off</td><td>When enabled, reorders contours using a greedy nearest-neighbor algorithm starting from the largest, reducing total pen-up travel distance.</td></tr>
<tr><td><b>Target Size</b></td><td>off</td><td>When enabled, the image is resized to fit W&times;H while preserving aspect ratio, padded with black. Off = auto-downscale only if any side &gt; 4096px. Range 1&ndash;8192.</td></tr>
</table>

<h3>Left Panel &mdash; Window</h3>
<table>
<tr><td width=130><b>Dropdown</b></td><td>Lists all visible windows on the system. Select one as the draw target.</td></tr>
<tr><td><b>Refresh</b></td><td>Re-scan visible windows and refresh the dropdown. Ctrl+R.</td></tr>
</table>

<h3>Left Panel &mdash; Canvas Offset</h3>
<p>The canvas is the rectangular area inside the target window where drawing happens. The image is scaled to fit and centered within this region. You can define it either numerically or visually.</p>
<table>
<tr><th width=140>Control</th><th>Description</th></tr>
<tr><td><b>Left / Top</b></td><td>Canvas offset from the window's top-left corner (pixels). Compensates for title bars and borders.</td></tr>
<tr><td><b>Width / Height</b></td><td>Canvas size in pixels. 0 = automatically uses the full window size.</td></tr>
<tr><td><b>Auto-fill</b></td><td>Resets Left/Top to 0 and sets Width/Height to match the selected window.</td></tr>
<tr><td><b>Select Canvas Region&hellip;</b></td><td>Opens a semi-transparent overlay on the target window. Drag the rectangle handles to visually define the canvas area. <b>Enter</b> to confirm, <b>Esc</b> to cancel, <b>W</b> for full window, <b>F</b> to snap to top-left.</td></tr>
</table>

<h3>Left Panel &mdash; Mouse Settings</h3>
<table>
<tr><th width=150>Parameter</th><th width=60>Default</th><th>Description</th></tr>
<tr><td><b>Speed</b></td><td>0.002</td><td>Seconds to pause after each interpolated mouse point. Smaller = faster drawing but target app may drop input. 0 = full speed. Range 0&ndash;1.0.</td></tr>
<tr><td><b>Contour Pause</b></td><td>0.1</td><td>Seconds to pause between strokes (after releasing the mouse button). Gives the target app time to process the mouse-up event.</td></tr>
<tr><td><b>Interp. Step</b></td><td>5</td><td>Interpolation step in pixels. When two consecutive points are farther apart than this, intermediate points are inserted to keep mouse movement smooth. Smaller = smoother but more points.</td></tr>
<tr><td><b>Start Delay</b></td><td>3.0</td><td>Countdown seconds before drawing begins. Gives you time to move the cursor over the target window.</td></tr>
<tr><td><b>Pause between strokes</b></td><td>on</td><td>When enabled, pauses for <i>Contour Pause</i> seconds after each stroke. When off, strokes are drawn continuously.</td></tr>
<tr><td><b>Button</b></td><td>left</td><td>Mouse button used for drawing. Options: left / right / middle / x1 / x2.</td></tr>
<tr><td><b>Manual mode</b></td><td>off</td><td>When enabled, the program moves the cursor to each stroke&rsquo;s starting point and then waits for <i>you</i> to hold the selected mouse button to draw. Release to pause. Useful when you need to interact with the target window during drawing.</td></tr>
</table>

<h3>Left Panel &mdash; Actions</h3>
<table>
<tr><td width=130><b>Dry Run</b></td><td>Calculate and display statistics (contour count, point count, estimated time, canvas position) without actually moving the mouse. Use this to preview before committing to a real draw.</td></tr>
<tr><td><b>Start Drawing</b></td><td>Begin the countdown, then control the mouse to draw all contours stroke by stroke onto the target window. Progress bar and elapsed time update in real time.</td></tr>
<tr><td><b>Abort</b></td><td>Immediately stop drawing. The mouse button is released and already-drawn strokes remain. You can also press <b>Esc</b> during drawing to abort.</td></tr>
</table>
<p>During drawing, all controls except <b>Abort</b> are disabled to prevent accidental changes.</p>

<hr>

<h3>Right Panel &mdash; Preview Tabs</h3>
<table>
<tr><th width=100>Tab</th><th>Shows</th></tr>
<tr><td><b>Original</b></td><td>The loaded image after optional resize/padding &mdash; exactly what the processing pipeline receives as input.</td></tr>
<tr><td><b>Edges</b></td><td>Canny edge detection output. White lines = detected edges. Use this to tune Canny Low/High and Morph Close.</td></tr>
<tr><td><b>Overlay</b></td><td>Green contour lines drawn on top of the original image. Shows the final strokes that will be drawn. Use this to tune Epsilon, Skip Points, Min Area, etc.</td></tr>
<tr><td><b>Canvas</b></td><td>A screenshot of the selected target window with a draggable rectangle overlay. Drag handles to visually define the canvas area. Left/Top/Width/Height spinboxes sync in real time. <b>W</b> = select full window, <b>F</b> = snap to top-left.</td></tr>
</table>

<h3>Right Panel &mdash; Info Panel</h3>
<p>Below the preview tabs, a read-only text panel displays statistics about the processed image: contour count, total points, image dimensions, and dedup removals. After a Dry Run or completed drawing, it updates with the detailed report.</p>

<hr>

<h3>Menu Bar</h3>
<table>
<tr><th width=180>Menu</th><th>Action</th></tr>
<tr><td><b>File &rarr; Open Image</b></td><td>Open an image file. Ctrl+O.</td></tr>
<tr><td><b>File &rarr; Refresh Windows</b></td><td>Refresh the window list. Ctrl+R.</td></tr>
<tr><td><b>File &rarr; Exit</b></td><td>Quit the program. Ctrl+Q.</td></tr>
<tr><td><b>View &rarr; Set Wallpaper</b></td><td>Choose an image as the program&rsquo;s background wallpaper. Panels become semi-transparent (frosted glass) to show the wallpaper through.</td></tr>
<tr><td><b>View &rarr; Wallpaper Mode</b></td><td>Stretch (single image scaled to fill) or Tile (image repeated).</td></tr>
<tr><td><b>View &rarr; Clear Wallpaper</b></td><td>Remove the wallpaper and restore opaque panels.</td></tr>
<tr><td><b>View &rarr; Background Color</b></td><td>Choose a solid background color (used when no wallpaper is set, or as fallback behind the wallpaper).</td></tr>
<tr><td><b>Language &rarr; English / &#20013;&#25991;</b></td><td>Switch the UI language. The preference is saved and restored on next launch.</td></tr>
<tr><td><b>Help &rarr; About</b></td><td>Show this user guide.</td></tr>
</table>

<hr>

<h3>Keyboard Shortcuts</h3>
<table>
<tr><th width=100>Key</th><th width=140>Context</th><th>Action</th></tr>
<tr><td><b>Ctrl+O</b></td><td>Anywhere</td><td>Open image file</td></tr>
<tr><td><b>Ctrl+R</b></td><td>Anywhere</td><td>Refresh window list</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Anywhere</td><td>Exit program</td></tr>
<tr><td><b>Esc</b></td><td>Drawing</td><td>Abort drawing immediately</td></tr>
<tr><td><b>Enter</b></td><td>Canvas overlay</td><td>Confirm selection</td></tr>
<tr><td><b>Esc</b></td><td>Canvas overlay</td><td>Cancel selection</td></tr>
<tr><td><b>W</b></td><td>Overlay / Editor</td><td>Set selection to full window</td></tr>
<tr><td><b>F</b></td><td>Overlay / Editor</td><td>Snap selection to top-left</td></tr>
</table>

<hr>

<h3>Command Line</h3>
<pre># Preview edges (no drawing)
python main.py cat.png --preview

# Show statistics only
python main.py cat.png --dry-run

# List all visible windows
python main.py --list-windows

# Full draw with options
python main.py cat.png --window-title "My App" --canvas-offset "10,10,780,580" --start-delay 5

# Use right mouse button
python main.py cat.png --button right

# Manual mode
python main.py cat.png --manual</pre>

<table>
<tr><th width=180>Flag</th><th width=60>Default</th><th>Description</th></tr>
<tr><td><code>--preview</code></td><td>&mdash;</td><td>Show processed contours, do not draw</td></tr>
<tr><td><code>--dry-run</code></td><td>&mdash;</td><td>Show statistics, do not draw</td></tr>
<tr><td><code>--list-windows</code></td><td>&mdash;</td><td>List all visible windows and exit</td></tr>
<tr><td><code>--window-title</code></td><td>Godot</td><td>Target window title keyword (case-insensitive)</td></tr>
<tr><td><code>--canvas-offset</code></td><td>0,0,0,0</td><td>Canvas region: left,top,width,height</td></tr>
<tr><td><code>--start-delay</code></td><td>3.0</td><td>Countdown seconds before drawing</td></tr>
<tr><td><code>--speed</code></td><td>0.002</td><td>Mouse speed in seconds per interpolated point</td></tr>
<tr><td><code>--button</code></td><td>left</td><td>Mouse button: left/right/middle/x1/x2</td></tr>
<tr><td><code>--manual</code></td><td>&mdash;</td><td>Manual mode: user holds button to draw</td></tr>
<tr><td><code>--canny-low</code></td><td>50</td><td>Canny low threshold</td></tr>
<tr><td><code>--canny-high</code></td><td>150</td><td>Canny high threshold</td></tr>
<tr><td><code>--morph-close</code></td><td>0</td><td>Morphology close kernel (0=off)</td></tr>
<tr><td><code>--nearest-neighbor</code></td><td>&mdash;</td><td>Use nearest-neighbor path sort</td></tr>
<tr><td><code>--no-pause</code></td><td>&mdash;</td><td>No pause between strokes</td></tr>
<tr><td><code>--interpolate-step</code></td><td>5</td><td>Mouse interpolation step in pixels</td></tr>
<tr><td><code>--skip-points</code></td><td>2</td><td>Sample every N contour points</td></tr>
<tr><td><code>--min-area</code></td><td>50</td><td>Minimum contour area filter</td></tr>
</table>

<hr>

<h3>Pipeline</h3>
<pre>Image &rarr; Grayscale &rarr; Canny Edges &rarr; Contour Extraction &rarr; Simplify &amp; Sort &rarr; Mouse Drawing</pre>

<h3>Dependencies</h3>
<p>OpenCV &bull; NumPy &bull; PySide6 &bull; pynput &bull; pygetwindow</p>
""",
        "zh": """
<h2>&#22270;&#29255;&#32472;&#21046;&#22120; Image Drawer</h2>
<p>&#33258;&#21160;&#23558;&#22270;&#29255;&#30340;&#36793;&#32536;&#36718;&#24275;&#36890;&#36807;&#40736;&#26631;&#25302;&#25341;&#32472;&#21046;&#21040;&#20219;&#24847;&#31383;&#21475;&#30011;&#24067;&#19978;&#12290;&#25903;&#25345;&#21629;&#20196;&#34892;&#21644;&#22270;&#24418;&#30028;&#38754;&#20004;&#31181;&#26041;&#24335;&#12290;</p>

<h3>&#25512;&#33616;&#39044;&#35774;&#21442;&#25968;</h3>
	<p>&#20174;"&#22270;&#20687;&#21442;&#25968;"&#20998;&#32452;&#30340;&#19979;&#25289;&#33756;&#21333;&#20013;&#36873;&#25321;&#39044;&#35774;&#20197;&#24555;&#36895;&#19978;&#25163;&#12290;&#27599;&#20010;&#39044;&#35774;&#20250;&#38024;&#23545;&#29305;&#23450;&#22270;&#20687;&#31867;&#22411;&#35843;&#25972;&#25152;&#26377;&#21442;&#25968;&#12290;</p>
	<table>
	<tr><th width=100>&#39044;&#35774;</th><th width=115>&#36866;&#29992;&#22330;&#26223;</th><th width=50>&#36793;&#32536;</th><th width=45>Sigma</th><th width=40>&#27169;&#31946;</th><th width=60>&#21452;&#36793;&#28342;&#27874;</th><th width=55>Epsilon</th><th width=35>&#37319;&#26679;</th><th width=50>&#26368;&#23567;&#38754;&#31215;</th><th width=40>&#20869;&#37096;</th></tr>
	<tr><td><b>&#36890;&#29992;</b></td><td>&#22823;&#22810;&#25968;&#22270;&#29255;</td><td>&#28784;&#24230;</td><td>0.33</td><td>5</td><td>&#20851;</td><td>0.002</td><td>2</td><td>50</td><td>&#20851;</td></tr>
	<tr><td><b>&#22797;&#26434;&#25554;&#30011;</b></td><td>&#21345;&#36890;&#12289;&#32447;&#31295;</td><td>RGB</td><td>0.20</td><td>3</td><td>&#24320;(d=9)</td><td>0.001</td><td>1</td><td>10</td><td>&#24320;(d=2)</td></tr>
	<tr><td><b>&#29031;&#29255;/&#20154;&#20687;</b></td><td>&#29031;&#29255;&#12289;&#20154;&#20687;</td><td>LAB</td><td>0.33</td><td>5</td><td>&#20851;</td><td>0.002</td><td>2</td><td>30</td><td>&#24320;(d=3)</td></tr>
	<tr><td><b>Logo/&#32447;&#31295;</b></td><td>Logo&#12289;&#22270;&#26631;&#12289;&#25991;&#23383;</td><td>&#28784;&#24230;</td><td>0.25</td><td>3</td><td>&#20851;</td><td>0.0005</td><td>1</td><td>5</td><td>&#24320;(d=1)</td></tr>
	</table>

	<h3>&#30028;&#38754;&#27010;&#35272;</h3>
<p>GUI &#20998;&#20026;<b>&#24038;&#20391;&#25511;&#21046;&#38754;&#26495;</b>&#21644;<b>&#21491;&#20391;&#39044;&#35272;&#38754;&#26495;</b>&#12290;</p>

<hr>

<h3>&#24038;&#20391; &mdash; &#22270;&#29255;</h3>
<table>
<tr><td width=130><b>&#27983;&#35272;&hellip;</b></td><td>&#25171;&#24320;&#22270;&#29255;&#25991;&#20214; (PNG/JPG/BMP/TIFF/WebP)&#12290;Ctrl+O&#12290;&#21152;&#36733;&#21518;&#33258;&#21160;&#25191;&#34892;&#36793;&#32536;&#26816;&#27979;&#24182;&#22312;&#21491;&#20391;&#26631;&#31614;&#39029;&#20013;&#26174;&#31034;&#32467;&#26524;&#12290;</td></tr>
<tr><td><b>&#36335;&#24452;&#26174;&#31034;&#26694;</b></td><td>&#21482;&#35835;&#65292;&#26174;&#31034;&#24050;&#21152;&#36733;&#22270;&#29255;&#30340;&#23436;&#25972;&#36335;&#24452;&#12290;</td></tr>
</table>

<h3>&#24038;&#20391; &mdash; &#22270;&#29255;&#21442;&#25968;</h3>
<p>&#35843;&#25972;&#36825;&#20123;&#21442;&#25968;&#24433;&#21709;&#36793;&#32536;&#26816;&#27979;&#21644;&#36718;&#24275;&#25552;&#21462;&#12290;&#21491;&#20391;&#39044;&#35272;&#20250;&#23454;&#26102;&#26356;&#26032;&#12290;</p>
<table>
<tr><th width=140>&#21442;&#25968;</th><th width=60>&#40664;&#35748;</th><th>&#35828;&#26126;</th></tr>
<tr><td><b>Canny Low</b><br/>&#20302;&#38408;&#20540;</td><td>50</td><td>Canny &#36793;&#32536;&#26816;&#27979;&#30340;&#20302;&#38408;&#20540;&#12290;&#20302;&#20110;&#27492;&#20540;&#30340;&#20687;&#32032;&#34987;&#24573;&#30053;&#12290;&#38477;&#20302;&#21487;&#26816;&#27979;&#26356;&#22810;&#24369;&#36793;&#32536;&#65292;&#20294;&#20063;&#20250;&#24341;&#20837;&#22122;&#22768;&#12290;&#33539;&#22260; 0&ndash;255&#12290;</td></tr>
<tr><td><b>Canny High</b><br/>&#39640;&#38408;&#20540;</td><td>150</td><td>Canny &#30340;&#39640;&#38408;&#20540;&#12290;&#39640;&#20110;&#27492;&#20540;&#30340;&#20687;&#32032;&#30452;&#25509;&#34987;&#35748;&#23450;&#20026;&#36793;&#32536;&#12290;&#33509; Low &ge; High&#65292;&#31995;&#32479;&#33258;&#21160;&#20132;&#25442;&#20004;&#32773;&#12290;</td></tr>
<tr><td><b>Blur Kernel</b><br/>&#27169;&#31946;&#26680;</td><td>5</td><td>&#39640;&#26031;&#27169;&#31946;&#26680;&#22823;&#23567;&#65292;&#22312;&#36793;&#32536;&#26816;&#27979;&#21069;&#21435;&#38500;&#22122;&#28857;&#12290;&#36234;&#22823;&#36234;&#24178;&#20928;&#20294;&#36793;&#32536;&#36234;&#23569;&#12290;&#24517;&#39035;&#20026;&#22855;&#25968;&#65288;&#20598;&#25968;&#33258;&#21160;+1&#65289;&#12290;&#33539;&#22260; 1&ndash;31&#12290;</td></tr>
<tr><td><b>Epsilon</b><br/>&#31616;&#21270;&#31995;&#25968;</td><td>0.002</td><td>&#36718;&#24275;&#31616;&#21270;&#31995;&#25968;&#12290;&#36234;&#22823;&#36718;&#24275;&#36234;&#31895;&#31961;&#65288;&#28857;&#25968;&#36234;&#23569;&#65289;&#12290;&#20844;&#24335;&#65306;epsilon &times; &#36718;&#24275;&#21608;&#38271;&#12290;&#33539;&#22260; 0.0001&ndash;1.0&#12290;</td></tr>
<tr><td><b>Skip Points</b><br/>&#37319;&#26679;&#38388;&#38548;</td><td>2</td><td>&#27599;&#38548; N &#20010;&#28857;&#21462; 1 &#20010;&#12290;1 = &#20840;&#37096;&#20445;&#30041;&#65292;5 = &#21482;&#20445;&#30041; 1/5&#12290;&#29992;&#20110;&#20943;&#23569;&#24635;&#28857;&#25968;&#65292;&#21152;&#24555;&#32472;&#21046;&#36895;&#24230;&#12290;</td></tr>
<tr><td><b>Min Area</b><br/>&#26368;&#23567;&#38754;&#31215;</td><td>50</td><td>&#26368;&#23567;&#36718;&#24275;&#38754;&#31215;&#36807;&#28388;&#65288;&#20687;&#32032;&#65289;&#12290;&#23567;&#20110;&#27492;&#20540;&#30340;&#36718;&#24275;&#34987;&#20002;&#24323;&#65292;&#29992;&#20110;&#21435;&#38500;&#22122;&#22768;&#21644;&#30862;&#22359;&#12290;</td></tr>
<tr><td><b>Morph Close</b><br/>&#38381;&#36816;&#31639;</td><td>0</td><td>&#24418;&#24577;&#23398;&#38381;&#36816;&#31639;&#26680;&#22823;&#23567;&#12290;0 = &#31105;&#29992;&#12290;&#35774;&#20026; 3&ndash;7 &#21487;&#23558;&#26029;&#35010;&#30340;&#37051;&#36817;&#36793;&#32536;&#36830;&#25509;&#36215;&#26469;&#12290;&#24517;&#39035;&#20026;&#22855;&#25968;&#12290;</td></tr>
<tr><td><b>Dedup Dist</b><br/>&#21435;&#37325;&#36317;&#31163;</td><td>2.0</td><td>Chamfer &#36317;&#31163;&#21435;&#37325;&#38408;&#20540;&#65288;&#20687;&#32032;&#65289;&#12290;&#30456;&#20284;&#24230;&#20302;&#20110;&#27492;&#20540;&#30340;&#36718;&#24275;&#35270;&#20026;&#37325;&#22797;&#65292;&#21482;&#20445;&#30041;&#38754;&#31215;&#36739;&#22823;&#32773;&#12290;0 = &#19981;&#21435;&#37325;&#12290;</td></tr>
<tr><td><b>Nearest-neighbor sort</b><br/>&#26368;&#36817;&#37051;&#25490;&#24207;</td><td>&#20851;</td><td>&#24320;&#21551;&#21518;&#65292;&#29992;&#36138;&#24515;&#26368;&#36817;&#37051;&#31639;&#27861;&#37325;&#26032;&#25490;&#21015;&#36718;&#24275;&#32472;&#21046;&#39034;&#24207;&#65292;&#20174;&#38754;&#31215;&#26368;&#22823;&#30340;&#24320;&#22987;&#65292;&#27599;&#27425;&#36339;&#21040;&#26368;&#36817;&#30340;&#26410;&#32472;&#36718;&#24275;&#65292;&#20943;&#23569;&#25260;&#31508;&#31354;&#31227;&#36317;&#31163;&#12290;</td></tr>
<tr><td><b>Target Size</b><br/>&#30446;&#26631;&#23610;&#23544;</td><td>&#20851;</td><td>&#24320;&#21551;&#21518;&#65292;&#22270;&#29255;&#34987;&#31561;&#27604;&#32553;&#25918;&#24182;&#23621;&#20013;&#25918;&#32622;&#22312;&#40657;&#33394;&#30011;&#24067;&#19978;&#12290;&#20851;&#38381;&#26102;&#19981;&#38480;&#21046;&#65292;&#20294;&#20219;&#20309;&#19968;&#36793; &gt; 4096px &#20250;&#33258;&#21160;&#32553;&#23567;&#12290;&#33539;&#22260; 1&ndash;8192&#12290;</td></tr>
</table>

<h3>&#24038;&#20391; &mdash; &#31383;&#21475;</h3>
<table>
<tr><td width=130><b>&#19979;&#25289;&#26694;</b></td><td>&#21015;&#20986;&#31995;&#32479;&#20013;&#25152;&#26377;&#21487;&#35265;&#31383;&#21475;&#12290;&#36873;&#25321;&#19968;&#20010;&#20316;&#20026;&#32472;&#21046;&#30446;&#26631;&#12290;</td></tr>
<tr><td><b>&#21047;&#26032;</b></td><td>&#37325;&#26032;&#25195;&#25551;&#21487;&#35265;&#31383;&#21475;&#24182;&#21047;&#26032;&#19979;&#25289;&#21015;&#34920;&#12290;Ctrl+R&#12290;</td></tr>
</table>

<h3>&#24038;&#20391; &mdash; &#30011;&#24067;&#20559;&#31227;</h3>
<p>&#30011;&#24067;&#26159;&#31383;&#21475;&#20869;&#23454;&#38469;&#29992;&#20110;&#32472;&#21046;&#30340;&#30697;&#24418;&#21306;&#22495;&#12290;&#22270;&#29255;&#20250;&#34987;&#31561;&#27604;&#32553;&#25918;&#24182;&#23621;&#20013;&#25918;&#32622;&#22312;&#27492;&#21306;&#22495;&#20869;&#12290;&#21487;&#20197;&#25968;&#20540;&#36755;&#20837;&#25110;&#21487;&#35270;&#21270;&#23450;&#20041;&#12290;</p>
<table>
<tr><th width=140>&#25511;&#20214;</th><th>&#35828;&#26126;</th></tr>
<tr><td><b>&#24038; / &#19978; (L/T)</b></td><td>&#30011;&#24067;&#30456;&#23545;&#20110;&#31383;&#21475;&#24038;&#19978;&#35282;&#30340;&#20559;&#31227;&#37327;&#65288;&#20687;&#32032;&#65289;&#12290;&#29992;&#20110;&#34917;&#20607;&#26631;&#39064;&#26639;&#21644;&#36793;&#26694;&#12290;</td></tr>
<tr><td><b>&#23485; / &#39640; (W/H)</b></td><td>&#30011;&#24067;&#23610;&#23544;&#65288;&#20687;&#32032;&#65289;&#12290;0 = &#33258;&#21160;&#20351;&#29992;&#31383;&#21475;&#23485;&#39640;&#12290;</td></tr>
<tr><td><b>&#33258;&#21160;&#22635;&#20805; (Auto-fill)</b></td><td>&#23558;&#24038;/&#19978;&#24402;&#38646;&#65292;&#24182;&#23558;&#23485;/&#39640;&#35774;&#20026;&#24403;&#21069;&#36873;&#20013;&#31383;&#21475;&#30340;&#23610;&#23544;&#12290;</td></tr>
<tr><td><b>&#36873;&#21462;&#30011;&#24067;&#21306;&#22495; (Select Canvas)</b></td><td>&#22312;&#30446;&#26631;&#31383;&#21475;&#19978;&#24377;&#20986;&#21322;&#36879;&#26126;&#36974;&#32617;&#23618;&#65292;&#21487;&#25302;&#25341;&#30697;&#24418;&#25163;&#26564;&#30452;&#35266;&#36873;&#21462;&#30011;&#24067;&#21306;&#22495;&#12290;<b>Enter</b> = &#30830;&#35748;&#65292;<b>Esc</b> = &#21462;&#28040;&#65292;<b>W</b> = &#20840;&#31383;&#21475;&#65292;<b>F</b> = &#36148;&#24038;&#19978;&#35282;&#12290;</td></tr>
</table>

<h3>&#24038;&#20391; &mdash; &#40736;&#26631;&#35774;&#32622;</h3>
<table>
<tr><th width=150>&#21442;&#25968;</th><th width=60>&#40664;&#35748;</th><th>&#35828;&#26126;</th></tr>
<tr><td><b>Speed</b><br/>&#36895;&#24230;</td><td>0.002</td><td>&#27599;&#20010;&#25554;&#20540;&#28857;&#20043;&#21518;&#26242;&#20572;&#30340;&#31186;&#25968;&#12290;&#36234;&#23567;&#36234;&#24555;&#65292;&#20294;&#30446;&#26631;&#31243;&#24207;&#21487;&#33021;&#20002;&#22833;&#36755;&#20837;&#12290;0 = &#20840;&#36895;&#12290;&#33539;&#22260; 0&ndash;1.0&#12290;</td></tr>
<tr><td><b>Contour Pause</b><br/>&#31508;&#30011;&#26242;&#20572;</td><td>0.1</td><td>&#27599;&#31508;&#32467;&#26463;&#21518;&#30340;&#26242;&#20572;&#31186;&#25968;&#12290;&#32473;&#30446;&#26631;&#31243;&#24207;&#22788;&#29702;&#40736;&#26631;&#37322;&#25918;&#20107;&#20214;&#30340;&#26102;&#38388;&#12290;</td></tr>
<tr><td><b>Interp. Step</b><br/>&#25554;&#20540;&#27493;&#38271;</td><td>5</td><td>&#25554;&#20540;&#27493;&#38271;&#65288;&#20687;&#32032;&#65289;&#12290;&#20004;&#20010;&#28857;&#38388;&#36317;&#31163;&#36229;&#36807;&#27492;&#20540;&#26102;&#65292;&#25554;&#20837;&#20013;&#38388;&#28857;&#20197;&#30830;&#20445;&#40736;&#26631;&#31227;&#21160;&#24179;&#28369;&#12290;&#36234;&#23567;&#36234;&#24179;&#28369;&#20294;&#28857;&#25968;&#36234;&#22810;&#12290;</td></tr>
<tr><td><b>Start Delay</b><br/>&#21551;&#21160;&#24310;&#36831;</td><td>3.0</td><td>&#24320;&#22987;&#32472;&#21046;&#21069;&#30340;&#20498;&#35745;&#26102;&#31186;&#25968;&#65292;&#32473;&#20320;&#26102;&#38388;&#25226;&#40736;&#26631;&#31227;&#21040;&#30446;&#26631;&#31383;&#21475;&#19978;&#26041;&#12290;</td></tr>
<tr><td><b>Pause between strokes</b><br/>&#31508;&#30011;&#38388;&#26242;&#20572;</td><td>&#24320;</td><td>&#24320;&#21551;&#26102;&#65292;&#27599;&#31508;&#20043;&#38388;&#26242;&#20572; <i>&#31508;&#30011;&#26242;&#20572;</i> &#31186;&#12290;&#20851;&#38381;&#21017;&#36830;&#32493;&#32472;&#21046;&#12290;</td></tr>
<tr><td><b>Button</b><br/>&#25353;&#38190;</td><td>left</td><td>&#32472;&#21046;&#20351;&#29992;&#30340;&#40736;&#26631;&#25353;&#38190;&#65306;left / right / middle / x1 / x2&#12290;</td></tr>
<tr><td><b>Manual mode</b><br/>&#25163;&#21160;&#27169;&#24335;</td><td>&#20851;</td><td>&#24320;&#21551;&#21518;&#65292;&#31243;&#24207;&#23558;&#40736;&#26631;&#31227;&#21160;&#21040;&#27599;&#31508;&#36215;&#28857;&#21518;&#26242;&#20572;&#65292;&#30001;<b>&#29992;&#25143;</b>&#25353;&#20303;&#25353;&#38190;&#26469;&#25511;&#21046;&#32472;&#21046;&#33410;&#22863;&#65292;&#26494;&#24320;&#21017;&#26242;&#20572;&#12290;</td></tr>
</table>

<h3>&#24038;&#20391; &mdash; &#25805;&#20316;&#25353;&#38062;</h3>
<table>
<tr><td width=130><b>&#35797;&#36816;&#34892; (Dry Run)</b></td><td>&#19981;&#23454;&#38469;&#25805;&#20316;&#40736;&#26631;&#65292;&#20165;&#35745;&#31639;&#24182;&#23637;&#31034;&#32479;&#35745;&#20449;&#24687;&#65288;&#36718;&#24275;&#25968;&#12289;&#28857;&#25968;&#12289;&#39044;&#35745;&#32791;&#26102;&#12289;&#30011;&#24067;&#20301;&#32622;&#65289;&#12290;&#29992;&#20110;&#23454;&#38469;&#32472;&#21046;&#21069;&#39044;&#20272;&#12290;</td></tr>
<tr><td><b>&#24320;&#22987;&#32472;&#21046; (Start)</b></td><td>&#24320;&#22987;&#20498;&#35745;&#26102;&#65292;&#28982;&#21518;&#25511;&#21046;&#40736;&#26631;&#36880;&#31508;&#22312;&#30446;&#26631;&#31383;&#21475;&#20869;&#25551;&#30011;&#36718;&#24275;&#12290;&#36827;&#24230;&#26465;&#21644;&#24050;&#32791;&#26102;&#38388;&#23454;&#26102;&#26356;&#26032;&#12290;</td></tr>
<tr><td><b>&#20013;&#27490; (Abort)</b></td><td>&#31435;&#21363;&#20572;&#27490;&#32472;&#21046;&#12290;&#24050;&#32472;&#21046;&#30340;&#31508;&#30011;&#20445;&#30041;&#12290;&#20063;&#21487;&#25353;<b>Esc</b>&#38190;&#35302;&#21457;&#12290;</td></tr>
</table>
<p>&#32472;&#21046;&#36807;&#31243;&#20013;&#65292;&#38500;&#20102;<b>&#20013;&#27490;</b>&#20197;&#22806;&#30340;&#25152;&#26377;&#25511;&#20214;&#37117;&#34987;&#31105;&#29992;&#65292;&#38450;&#27490;&#35823;&#25805;&#20316;&#12290;</p>

<hr>

<h3>&#21491;&#20391; &mdash; &#39044;&#35272;&#26631;&#31614;&#39029;</h3>
<table>
<tr><th width=100>&#26631;&#31614;&#39029;</th><th>&#26174;&#31034;&#20869;&#23481;</th></tr>
<tr><td><b>&#21407;&#22270; (Original)</b></td><td>&#21152;&#36733;&#30340;&#21407;&#22987;&#22270;&#29255;&#65288;&#32463;&#36807;&#32553;&#25918;&#21644;&#40657;&#36793;&#34917;&#30333;&#22788;&#29702;&#21518;&#30340;&#29256;&#26412;&#65292;&#19982;&#22788;&#29702;&#31649;&#32447;&#30340;&#36755;&#20837;&#23436;&#20840;&#19968;&#33268;&#65289;&#12290;</td></tr>
<tr><td><b>&#36793;&#32536; (Edges)</b></td><td>Canny &#36793;&#32536;&#26816;&#27979;&#36755;&#20986;&#12290;&#30333;&#33394;&#32447;&#26465; = &#24050;&#26816;&#27979;&#30340;&#36793;&#32536;&#12290;&#29992;&#20110;&#35843;&#25972; Canny Low/High &#21644; Morph Close&#12290;</td></tr>
<tr><td><b>&#36718;&#24275;&#21472;&#21152; (Overlay)</b></td><td>&#32511;&#33394;&#36718;&#24275;&#32447;&#21472;&#21152;&#22312;&#21407;&#22270;&#19978;&#12290;&#26174;&#31034;&#26368;&#32456;&#20250;&#34987;&#32472;&#21046;&#30340;&#31508;&#30011;&#24418;&#29366;&#12290;&#29992;&#20110;&#35843;&#25972; Epsilon&#12289;Skip Points&#12289;Min Area &#31561;&#21442;&#25968;&#12290;</td></tr>
<tr><td><b>&#30011;&#24067; (Canvas)</b></td><td>&#30446;&#26631;&#31383;&#21475;&#25130;&#22270; + &#21487;&#25302;&#25341;&#30697;&#24418;&#36873;&#21306;&#12290;&#25302;&#25341;&#25163;&#26564;&#21487;&#35270;&#21270;&#23450;&#20041;&#30011;&#24067;&#21306;&#22495;&#65292;&#24038;/&#19978;/&#23485;/&#39640;&#25968;&#20540;&#26694;&#23454;&#26102;&#21516;&#27493;&#12290;<b>W</b> = &#20840;&#31383;&#21475;&#65292;<b>F</b> = &#36148;&#24038;&#19978;&#35282;&#12290;</td></tr>
</table>

<h3>&#21491;&#20391; &mdash; &#20449;&#24687;&#38754;&#26495;</h3>
<p>&#39044;&#35272;&#26631;&#31614;&#39029;&#19979;&#26041;&#30340;&#21482;&#35835;&#25991;&#26412;&#38754;&#26495;&#65292;&#26174;&#31034;&#22788;&#29702;&#21518;&#30340;&#32479;&#35745;&#25968;&#25454;&#65306;&#36718;&#24275;&#25968;&#12289;&#24635;&#28857;&#25968;&#12289;&#22270;&#29255;&#23610;&#23544;&#12289;&#21435;&#37325;&#24773;&#20917;&#12290;Dry Run &#25110;&#32472;&#21046;&#23436;&#25104;&#21518;&#26356;&#26032;&#20026;&#35814;&#32454;&#25253;&#21578;&#12290;</p>

<hr>

<h3>&#33756;&#21333;&#26639;</h3>
<table>
<tr><th width=190>&#33756;&#21333;</th><th>&#21151;&#33021;</th></tr>
<tr><td><b>&#25991;&#20214; &rarr; &#25171;&#24320;&#22270;&#29255;</b></td><td>&#25171;&#24320;&#22270;&#29255;&#25991;&#20214;&#12290;Ctrl+O&#12290;</td></tr>
<tr><td><b>&#25991;&#20214; &rarr; &#21047;&#26032;&#31383;&#21475;&#21015;&#34920;</b></td><td>&#21047;&#26032;&#31383;&#21475;&#21015;&#34920;&#12290;Ctrl+R&#12290;</td></tr>
<tr><td><b>&#25991;&#20214; &rarr; &#36864;&#20986;</b></td><td>&#36864;&#20986;&#31243;&#24207;&#12290;Ctrl+Q&#12290;</td></tr>
<tr><td><b>&#35270;&#22270; &rarr; &#35774;&#32622;&#22721;&#32440;</b></td><td>&#36873;&#25321;&#22270;&#29255;&#20316;&#20026;&#31243;&#24207;&#32972;&#26223;&#22721;&#32440;&#12290;&#38754;&#26495;&#21464;&#20026;&#21322;&#36879;&#26126;&#65288;&#27611;&#29627;&#29827;&#25928;&#26524;&#65289;&#20197;&#26174;&#29616;&#22721;&#32440;&#12290;</td></tr>
<tr><td><b>&#35270;&#22270; &rarr; &#22721;&#32440;&#27169;&#24335;</b></td><td>&#25289;&#20280;&#65288;&#21333;&#24352;&#32553;&#25918;&#22635;&#28385;&#65289;&#25110;&#24179;&#38138;&#65288;&#22270;&#29255;&#37325;&#22797;&#65289;&#12290;</td></tr>
<tr><td><b>&#35270;&#22270; &rarr; &#28165;&#38500;&#22721;&#32440;</b></td><td>&#31227;&#38500;&#22721;&#32440;&#24182;&#24674;&#22797;&#19981;&#36879;&#26126;&#38754;&#26495;&#12290;</td></tr>
<tr><td><b>&#35270;&#22270; &rarr; &#32972;&#26223;&#39068;&#33394;</b></td><td>&#36873;&#25321;&#32431;&#33394;&#32972;&#26223;&#65288;&#26410;&#35774;&#22721;&#32440;&#26102;&#29983;&#25928;&#65292;&#25110;&#20316;&#20026;&#22721;&#32440;&#32972;&#21518;&#30340;&#24213;&#33394;&#65289;&#12290;</td></tr>
<tr><td><b>&#35821;&#35328; &rarr; English / &#20013;&#25991;</b></td><td>&#20999;&#25442;&#30028;&#38754;&#35821;&#35328;&#12290;&#20559;&#22909;&#33258;&#21160;&#20445;&#23384;&#65292;&#19979;&#27425;&#21551;&#21160;&#26102;&#29983;&#25928;&#12290;</td></tr>
<tr><td><b>&#24110;&#21161; &rarr; &#20851;&#20110;</b></td><td>&#26174;&#31034;&#26412;&#20351;&#29992;&#35828;&#26126;&#12290;</td></tr>
</table>

<hr>

<h3>&#24555;&#25463;&#38190;</h3>
<table>
<tr><th width=100>&#25353;&#38190;</th><th width=140>&#22330;&#26223;</th><th>&#21151;&#33021;</th></tr>
<tr><td><b>Ctrl+O</b></td><td>&#20219;&#24847;</td><td>&#25171;&#24320;&#22270;&#29255;&#25991;&#20214;</td></tr>
<tr><td><b>Ctrl+R</b></td><td>&#20219;&#24847;</td><td>&#21047;&#26032;&#31383;&#21475;&#21015;&#34920;</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>&#20219;&#24847;</td><td>&#36864;&#20986;&#31243;&#24207;</td></tr>
<tr><td><b>Esc</b></td><td>&#32472;&#21046;&#20013;</td><td>&#31435;&#21363;&#20013;&#27490;&#32472;&#21046;</td></tr>
<tr><td><b>Enter</b></td><td>&#36974;&#32617;&#36873;&#30011;&#24067;</td><td>&#30830;&#35748;&#36873;&#21306;</td></tr>
<tr><td><b>Esc</b></td><td>&#36974;&#32617;&#36873;&#30011;&#24067;</td><td>&#21462;&#28040;&#36873;&#30011;&#24067;</td></tr>
<tr><td><b>W</b></td><td>&#36974;&#32617;/&#32534;&#36753;&#22120;</td><td>&#36873;&#21306;&#35774;&#20026;&#31383;&#21475;&#20840;&#23610;&#23544;</td></tr>
<tr><td><b>F</b></td><td>&#36974;&#32617;/&#32534;&#36753;&#22120;</td><td>&#36873;&#21306;&#36148;&#21040;&#31383;&#21475;&#24038;&#19978;&#35282;</td></tr>
</table>

<hr>

<h3>&#21629;&#20196;&#34892;</h3>
<pre># &#39044;&#35272;&#36793;&#32536;&#25928;&#26524;&#65288;&#19981;&#23454;&#38469;&#32472;&#21046;&#65289;
python main.py cat.png --preview

# &#21482;&#26597;&#30475;&#32479;&#35745;&#20449;&#24687;
python main.py cat.png --dry-run

# &#21015;&#20986;&#25152;&#26377;&#21487;&#35265;&#31383;&#21475;
python main.py --list-windows

# &#23436;&#25972;&#32472;&#21046;
python main.py cat.png --window-title "My App" --canvas-offset "10,10,780,580" --start-delay 5

# &#20351;&#29992;&#21491;&#38190;
python main.py cat.png --button right

# &#25163;&#21160;&#27169;&#24335;
python main.py cat.png --manual</pre>

<table>
<tr><th width=190>&#21442;&#25968;</th><th width=60>&#40664;&#35748;</th><th>&#35828;&#26126;</th></tr>
<tr><td><code>--preview</code></td><td>&mdash;</td><td>&#39044;&#35272;&#22788;&#29702;&#32467;&#26524;&#65292;&#19981;&#32472;&#21046;</td></tr>
<tr><td><code>--dry-run</code></td><td>&mdash;</td><td>&#26174;&#31034;&#32479;&#35745;&#20449;&#24687;&#65292;&#19981;&#32472;&#21046;</td></tr>
<tr><td><code>--list-windows</code></td><td>&mdash;</td><td>&#21015;&#20986;&#25152;&#26377;&#21487;&#35265;&#31383;&#21475;&#24182;&#36864;&#20986;</td></tr>
<tr><td><code>--window-title</code></td><td>Godot</td><td>&#30446;&#26631;&#31383;&#21475;&#26631;&#39064;&#20851;&#38190;&#35789;&#65288;&#19981;&#21306;&#20998;&#22823;&#23567;&#20889;&#65289;</td></tr>
<tr><td><code>--canvas-offset</code></td><td>0,0,0,0</td><td>&#30011;&#24067;&#21306;&#22495;&#65306; left,top,width,height</td></tr>
<tr><td><code>--start-delay</code></td><td>3.0</td><td>&#24320;&#22987;&#21069;&#20498;&#35745;&#26102;&#31186;&#25968;</td></tr>
<tr><td><code>--speed</code></td><td>0.002</td><td>&#40736;&#26631;&#36895;&#24230;&#65288;&#31186;/&#25554;&#20540;&#28857;&#65289;</td></tr>
<tr><td><code>--button</code></td><td>left</td><td>&#40736;&#26631;&#25353;&#38190;&#65306;left/right/middle/x1/x2</td></tr>
<tr><td><code>--manual</code></td><td>&mdash;</td><td>&#25163;&#21160;&#27169;&#24335;&#65292;&#29992;&#25143;&#25353;&#20303;&#25353;&#38190;&#32472;&#21046;</td></tr>
<tr><td><code>--canny-low</code></td><td>50</td><td>Canny &#20302;&#38408;&#20540;</td></tr>
<tr><td><code>--canny-high</code></td><td>150</td><td>Canny &#39640;&#38408;&#20540;</td></tr>
<tr><td><code>--morph-close</code></td><td>0</td><td>&#38381;&#36816;&#31639;&#26680;&#22823;&#23567; (0=&#31105;&#29992;)</td></tr>
<tr><td><code>--nearest-neighbor</code></td><td>&mdash;</td><td>&#26368;&#36817;&#37051;&#36335;&#24452;&#25490;&#24207;</td></tr>
<tr><td><code>--no-pause</code></td><td>&mdash;</td><td>&#31508;&#30011;&#38388;&#19981;&#26242;&#20572;</td></tr>
<tr><td><code>--interpolate-step</code></td><td>5</td><td>&#40736;&#26631;&#25554;&#20540;&#27493;&#38271;&#65288;&#20687;&#32032;&#65289;</td></tr>
<tr><td><code>--skip-points</code></td><td>2</td><td>&#27599;&#38548; N &#20010;&#36718;&#24275;&#28857;&#21462; 1 &#20010;</td></tr>
<tr><td><code>--min-area</code></td><td>50</td><td>&#26368;&#23567;&#36718;&#24275;&#38754;&#31215;&#36807;&#28388;</td></tr>
</table>

<hr>

<h3>&#22788;&#29702;&#27969;&#31243;</h3>
<pre>&#22270;&#29255; &rarr; &#28784;&#24230;&#21270; &rarr; Canny &#36793;&#32536;&#26816;&#27979; &rarr; &#36718;&#24275;&#25552;&#21462; &rarr; &#31616;&#21270;&#19982;&#25490;&#24207; &rarr; &#40736;&#26631;&#32472;&#21046;</pre>

<h3>&#20381;&#36182;</h3>
<p>OpenCV &bull; NumPy &bull; PySide6 &bull; pynput &bull; pygetwindow</p>
""",
    },

    # ── Image Group ──
    "group_image":            {"en": "Image",                                 "zh": "图片"},
    "placeholder_image_path": {"en": "Select an image file...",               "zh": "选择图片文件..."},
    "btn_browse":             {"en": "Browse...",                             "zh": "浏览..."},
    "tooltip_browse":         {"en": "Open an image file (Ctrl+O)",           "zh": "打开图片文件 (Ctrl+O)"},

    # ── Image Parameters Group ──
    "group_params":           {"en": "Image Parameters",                      "zh": "图片参数"},
    "label_preset":           {"en": "Preset:",                              "zh": "预设:"},
    "preset_general":         {"en": "General",                              "zh": "通用"},
    "preset_illustration":    {"en": "Complex Illustration",                  "zh": "复杂插画"},
    "preset_photo":           {"en": "Photo / Portrait",                     "zh": "照片 / 人像"},
    "preset_logo":            {"en": "Logo / Line Art",                      "zh": "Logo / 线条画"},
    "tooltip_preset":         {"en": "Apply a recommended preset for your image type", "zh": "根据你的图片类型应用推荐参数预设"},
    "label_canny_low":        {"en": "Canny Low:",                            "zh": "Canny 低阈值:"},
    "label_canny_high":       {"en": "Canny High:",                           "zh": "Canny 高阈值:"},
    "label_blur":             {"en": "Blur Kernel:",                          "zh": "模糊核:"},
    "tooltip_blur":           {"en": "Gaussian blur kernel size (odd, 1-31)", "zh": "高斯模糊核大小 (奇数, 1-31)"},
    "label_epsilon":          {"en": "Epsilon:",                              "zh": "简化系数:"},
    "tooltip_epsilon":        {"en": "Contour simplification factor",         "zh": "轮廓简化系数"},
    "label_skip":             {"en": "Skip Points:",                          "zh": "采样间隔:"},
    "tooltip_skip":           {"en": "Sample every N points (1 = all)",       "zh": "每隔 N 个点采 1 个 (1=全部)"},
    "label_min_area":         {"en": "Min Area:",                             "zh": "最小面积:"},
    "tooltip_min_area":       {"en": "Minimum contour area filter (px)",      "zh": "最小轮廓面积过滤 (像素)"},
    "label_morph":            {"en": "Morph Close:",                          "zh": "闭运算:"},
    "tooltip_morph":          {"en": "Morphology close kernel (0 = off)",     "zh": "形态学闭运算核大小 (0=禁用)"},
    "label_dedup":            {"en": "Dedup Dist:",                           "zh": "去重距离:"},
    "tooltip_dedup":          {"en": "Chamfer distance dedup threshold (0 = off)", "zh": "Chamfer 距离去重阈值 (0=禁用)"},
    "label_sort":             {"en": "Sort:",                                 "zh": "排序:"},
    "chk_neighbor":           {"en": "Nearest-neighbor path sort",            "zh": "贪心最近邻路径排序"},
    "label_target_size":      {"en": "Target Size:",                          "zh": "目标尺寸:"},
    "chk_target_enable":      {"en": "Enable",                                "zh": "启用"},
    "label_target_w":         {"en": "W:",                                    "zh": "宽:"},
    "label_target_h":         {"en": "H:",                                    "zh": "高:"},
    "label_edge_mode":        {"en": "Edge Mode:",                            "zh": "边缘检测模式:"},
    "edge_mode_gray":         {"en": "Grayscale",                             "zh": "灰度"},
    "edge_mode_rgb":          {"en": "RGB Channels",                          "zh": "RGB 通道"},
    "edge_mode_lab":          {"en": "LAB Channels",                          "zh": "LAB 通道"},
    "tooltip_edge_mode":      {"en": "Edge detection color space",            "zh": "边缘检测使用的色彩空间"},
    "label_inner_contours":   {"en": "Inner Contours:",                       "zh": "内部轮廓:"},
    "chk_inner_contours":     {"en": "Include inner contours (RETR_TREE)",    "zh": "包含内部轮廓 (RETR_TREE)"},
    "tooltip_inner_contours": {"en": "Capture nested contours inside shapes, not just outer boundaries", "zh": "捕获形状内部的嵌套轮廓，而不仅仅是外边界"},
    "label_hierarchy_depth":  {"en": "Max Depth:",                            "zh": "最大层级深度:"},
    "tooltip_hierarchy_depth":{"en": "Max nesting depth for inner contours (0 = outer only, 2 = default)", "zh": "内部轮廓的最大嵌套深度 (0=仅外轮廓, 2=默认)"},
    "chk_auto_canny":         {"en": "Auto Canny (image-adaptive thresholds)", "zh": "自动 Canny (根据图像自适应阈值)"},
    "tooltip_auto_canny":     {"en": "Compute Canny thresholds from image median intensity — adapts to each image", "zh": "根据图像中位数值自动计算 Canny 阈值——每张图自适应"},
    "label_auto_canny_sigma": {"en": "Sigma:",                                "zh": "灵敏度:"},
    "tooltip_auto_canny_sigma":{"en": "Sensitivity factor for auto threshold (0.1 = sensitive, 0.5 = conservative)", "zh": "自动阈值的灵敏度系数 (0.1=敏感, 0.5=保守)"},
    "chk_bilateral":           {"en": "Bilateral Filter (edge-preserving denoise)", "zh": "双边滤波 (保留边缘的去噪)"},
    "tooltip_bilateral":       {"en": "Preserves sharp edges while smoothing flat areas — better than Gaussian for illustrations", "zh": "平滑平坦区域同时保留锐利边缘——对插画效果优于高斯模糊"},
    "label_bilateral_d":       {"en": "Diameter:",                             "zh": "滤波直径:"},
    "tooltip_bilateral_d":     {"en": "Bilateral filter diameter (odd, 3-25). Larger = more smoothing", "zh": "双边滤波直径 (奇数, 3-25)。越大去噪越强"},

    # ── Window Group ──
    "group_window":           {"en": "Window",                                "zh": "窗口"},
    "tooltip_window_combo":   {"en": "Target game window for drawing",        "zh": "选择绘制的目标游戏窗口"},
    "btn_refresh":            {"en": "Refresh",                                "zh": "刷新"},
    "tooltip_refresh":        {"en": "Refresh window list (Ctrl+R)",          "zh": "刷新窗口列表 (Ctrl+R)"},
    "combo_no_windows":       {"en": "(no windows found)",                    "zh": "(未找到窗口)"},
    "combo_no_pkg":           {"en": "(pygetwindow not installed)",           "zh": "(pygetwindow 未安装)"},

    # ── Canvas Offset Group ──
    "group_canvas":           {"en": "Canvas Offset",                         "zh": "画布偏移"},
    "label_canvas_l":         {"en": "Left:",                                 "zh": "左:"},
    "label_canvas_t":         {"en": "Top:",                                  "zh": "上:"},
    "label_canvas_w":         {"en": "Width:",                                "zh": "宽:"},
    "label_canvas_h":         {"en": "Height:",                               "zh": "高:"},
    "tooltip_canvas_offset":  {"en": "Canvas offset within the window (0 = auto)", "zh": "画布在窗口内的偏移量 (0=自动)"},
    "btn_auto_fill":          {"en": "Auto-fill from selected window",        "zh": "从选中窗口自动填充"},
    "tooltip_auto_fill":      {"en": "Set canvas width/height to match window", "zh": "将画布宽高设为窗口尺寸"},
    "btn_select_canvas":      {"en": "Select Canvas Region...",               "zh": "选取画布区域..."},
    "tooltip_select_canvas":  {"en": "Visually drag to select the canvas area on the game window", "zh": "在游戏窗口上可视化拖拽选取画布区域"},

    # ── Mouse Settings Group ──
    "group_mouse":            {"en": "Mouse Settings",                        "zh": "鼠标设置"},
    "label_speed":            {"en": "Speed (s/pt):",                         "zh": "速度 (秒/点):"},
    "tooltip_speed":          {"en": "Seconds per interpolated point",        "zh": "插值点之间的间隔秒数"},
    "label_pause":            {"en": "Contour Pause (s):",                    "zh": "笔画间暂停 (秒):"},
    "tooltip_pause":          {"en": "Pause between strokes (seconds)",       "zh": "每笔之间的暂停秒数"},
    "label_step":             {"en": "Interp. Step (px):",                    "zh": "插值步长 (px):"},
    "tooltip_step":           {"en": "Mouse interpolation step (px)",         "zh": "鼠标插值步长 (像素)"},
    "label_delay":            {"en": "Start Delay (s):",                      "zh": "启动延迟 (秒):"},
    "tooltip_delay":          {"en": "Countdown seconds before drawing",      "zh": "开始绘制前的倒计时秒数"},
    "chk_pause_between":      {"en": "Pause between strokes",                 "zh": "笔画间暂停"},
    "label_button":           {"en": "Button:",                               "zh": "鼠标按键:"},
    "chk_manual":             {"en": "Manual mode (hold button to draw)",     "zh": "手动模式 (按住按键绘制)"},

    # ── Actions Group ──
    "group_actions":          {"en": "Actions",                               "zh": "操作"},
    "btn_dry_run":            {"en": "Dry Run",                               "zh": "试运行"},
    "tooltip_dry_run":        {"en": "Show drawing statistics without moving mouse", "zh": "显示绘图统计信息，不实际操作鼠标"},
    "btn_start":              {"en": "Start Drawing",                         "zh": "开始绘制"},
    "tooltip_start":          {"en": "Begin drawing contours to the selected window", "zh": "开始向选中窗口绘制轮廓"},
    "btn_abort":              {"en": "Abort",                                 "zh": "中止"},
    "tooltip_abort":          {"en": "Stop drawing immediately (or press Esc)", "zh": "立即停止绘制 (或按 Esc 键)"},

    # ── Preview Tabs ──
    "tab_original":           {"en": "Original",                              "zh": "原图"},
    "tab_edges":              {"en": "Edges",                                 "zh": "边缘"},
    "tab_overlay":            {"en": "Overlay",                               "zh": "轮廓叠加"},
    "tab_canvas":             {"en": "Canvas",                                "zh": "画布编辑"},
    "label_no_image":         {"en": "Load an image to preview",              "zh": "加载图片以预览"},
    "label_no_image_short":   {"en": "No image",                              "zh": "无图片"},
    # ── Info Panel ──
    "info_contours":          {"en": "Contours: {n}  (closed: {c}, open: {o})", "zh": "轮廓: {n}  (闭合: {c}, 开放: {o})"},
    "info_points":            {"en": "Total points: {n}",                     "zh": "总点数: {n}"},
    "info_size":              {"en": "Image size: {w} x {h}",                 "zh": "图片尺寸: {w} x {h}"},
    "info_dedup":             {"en": "Dedup removed: {n}",                    "zh": "去重移除: {n}"},

    # ── Dry Run ──
    "dryrun_image":           {"en": "Image: {path} ({w}x{h})",               "zh": "图片: {path} ({w}x{h})"},
    "dryrun_contours":        {"en": "Contours: {n}  (closed: {c}, open: {o})", "zh": "轮廓: {n}  (闭合: {c}, 开放: {o})"},
    "dryrun_points":          {"en": "Total points: {n}",                     "zh": "总点数: {n}"},
    "dryrun_est_time":        {"en": "Estimated time: ~{t:.1f}s",             "zh": "预计耗时: ~{t:.1f}秒"},
    "dryrun_formula":         {"en": "  = {d:.1f}s delay + {p}pts * {s}s + {c} strokes * {ps}s pause",
                               "zh": "  = {d:.1f}秒 延迟 + {p}点 * {s}秒 + {c} 笔画 * {ps}秒 暂停"},
    "dryrun_canvas":          {"en": "Canvas: ({x}, {y}) {w}x{h}",           "zh": "画布: ({x}, {y}) {w}x{h}"},
    "dryrun_window":          {"en": "Window: \"{title}\" at ({l},{t}) {w}x{h}",
                               "zh": "窗口: \"{title}\" 位置 ({l},{t}) 尺寸 {w}x{h}"},
    "dryrun_sort_nn":         {"en": "nearest-neighbor",                      "zh": "最近邻"},
    "dryrun_sort_area":       {"en": "area-descending",                       "zh": "面积降序"},
    "dryrun_sort":            {"en": "Sort: {method}",                        "zh": "排序: {method}"},
    "dryrun_dedup":           {"en": "Dedup: {d}px threshold ({n} duplicates removed)",
                               "zh": "去重: {d}px 阈值 ({n} 个重复已移除)"},

    # ── Status Bar ──
    "status_ready":           {"en": "Ready — Open an image to begin (Ctrl+O)", "zh": "就绪 — 打开图片开始 (Ctrl+O)"},
    "status_processed":       {"en": "Processed: {n} contours, {p} points",  "zh": "已处理: {n} 个轮廓, {p} 个点"},
    "status_no_contours":     {"en": "No contours found — try lowering Canny thresholds or Min Area",
                               "zh": "未找到轮廓 — 尝试降低 Canny 阈值或最小面积"},
    "status_dry_run":         {"en": "Dry run: {s} strokes, ~{t:.1f}s estimated",
                               "zh": "试运行: {s} 笔画, 预计 ~{t:.1f}秒"},
    "status_countdown":       {"en": "Starting in {n}s... Move cursor to target window",
                               "zh": "{n}秒后开始... 将鼠标移到目标窗口"},
    "status_drawing":         {"en": "Drawing — Esc or Abort to stop",        "zh": "绘制中 — 按 Esc 或点击中止"},
    "status_drawing_manual":  {"en": "Drawing — hold the button, Esc to stop", "zh": "绘制中 — 按住按键绘制, Esc 中止"},
    "status_aborting":        {"en": "Aborting...",                           "zh": "正在中止..."},
    "status_done":            {"en": "Done: {d}/{t} strokes, {p} points, {e:.1f}s",
                               "zh": "完成: {d}/{t} 笔画, {p} 点, {e:.1f}秒"},
    "status_aborted":         {"en": "Aborted: {d}/{t} strokes, {p} points, {e:.1f}s",
                               "zh": "已中止: {d}/{t} 笔画, {p} 点, {e:.1f}秒"},

    # ── Draw UI ──
    "progress_countdown":     {"en": "Countdown...",                           "zh": "倒计时..."},
    "progress_drawing":       {"en": "Drawing... %p%",                         "zh": "绘制中... %p%"},
    "label_countdown":        {"en": "Starting in {n}s...",                    "zh": "{n}秒后开始..."},
    "label_countdown_manual": {"en": "Starting in {n}s... (manual mode)",      "zh": "{n}秒后开始... (手动模式)"},
    "label_drawing":          {"en": "Drawing...",                             "zh": "绘制中..."},
    "label_drawing_manual":   {"en": "Hold the button to draw...",            "zh": "按住按键以绘制..."},
    "label_elapsed":          {"en": "Drawing... Elapsed: {t:.1f}s",           "zh": "绘制中... 已用: {t:.1f}秒"},
    "label_elapsed_manual":   {"en": "Hold button to draw... Elapsed: {t:.1f}s", "zh": "按住绘制... 已用: {t:.1f}秒"},

    # ── Error Dialogs ──
    "error_title_image":      {"en": "Image Error",                            "zh": "图片错误"},
    "error_title_dryrun":     {"en": "Dry Run",                                "zh": "试运行"},
    "error_title_draw":       {"en": "Cannot Draw",                            "zh": "无法绘制"},
    "error_title_drawing":    {"en": "Drawing Error",                          "zh": "绘制错误"},
    "error_no_contours":      {"en": "No contours to draw. Process an image first.", "zh": "没有可绘制的轮廓，请先处理图片。"},
    "error_no_window":        {"en": "No window selected. Refresh window list first.", "zh": "未选择窗口，请先刷新窗口列表。"},
    "error_no_strokes":       {"en": "No valid strokes generated.",            "zh": "未生成有效的笔画。"},

    # ── View / Wallpaper ──
    "menu_view":              {"en": "&View",                                 "zh": "视图(&V)"},
    "menu_view_wallpaper":    {"en": "Set &Wallpaper...",                     "zh": "设置壁纸(&W)"},
    "menu_view_mode":         {"en": "Wallpaper &Mode",                       "zh": "壁纸模式(&M)"},
    "menu_view_mode_stretch": {"en": "&Stretch",                              "zh": "拉伸(&S)"},
    "menu_view_mode_tile":    {"en": "&Tile",                                 "zh": "平铺(&T)"},
    "menu_view_clear":        {"en": "Clear &Wallpaper",                      "zh": "清除壁纸(&W)"},
    "menu_view_bg_color":     {"en": "Background &Color...",                  "zh": "背景颜色(&C)"},

    # ── Draw Target ──
    "draw_target_window":     {"en": "External window",                       "zh": "外部窗口"},
    "draw_target_board":      {"en": "Virtual board  →  edit  →  window",     "zh": "自带画板 → 编辑 → 输出到窗口"},
    "label_board_color":      {"en": "Pen color:",                            "zh": "画笔颜色:"},
    "label_board_width":      {"en": "Pen width:",                            "zh": "画笔粗细:"},
    "label_board_size":       {"en": "Board size:",                           "zh": "画板大小:"},
    "btn_open_blank_board":   {"en": "Open blank board",                      "zh": "打开空白画板"},

    # ── Screenshot ──
    "btn_screenshot":         {"en": "Screenshot",                            "zh": "截图"},
    "screenshot_saved":       {"en": "Screenshot saved: {path}",              "zh": "截图已保存: {path}"},
    "error_screenshot_failed": {"en": "Failed to capture screenshot.",         "zh": "截图失败。"},
}