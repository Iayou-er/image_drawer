"""CLI entry point: parse args, orchestrate modules, convert coordinates."""

import argparse
import sys
import time

# Fix Windows GBK encoding issues with Unicode window titles
if sys.platform == "win32" and sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import cv2
    import numpy as np
    from image_processor import ImageConfig, ProcessResult, process_image, resize_fit
    from window_finder import (
        WindowNotFoundError,
        WindowInfo,
        CanvasRegion,
        list_all_windows,
        find_window,
        activate_window,
        build_canvas,
        contours_to_strokes,
        estimate_draw_time,
    )
    from mouse_controller import MouseConfig, MouseDrawer
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Auto-draw image outlines via mouse in a Godot game.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py cat.png
  python main.py cat.png --preview
  python main.py cat.png --window-title "My Game" --start-delay 5
  python main.py cat.png --nearest-neighbor --morph-close 3
  python main.py cat.png --list-windows
""",
    )
    p.add_argument("input", nargs="?", help="Input image path")
    p.add_argument("--window-title", default="Godot", help="Window title keyword")
    p.add_argument("--canvas-offset", default="0,0,0,0",
                   help="Canvas offset: left,top,width,height (comma-separated)")
    p.add_argument("--speed", type=float, default=0.002, help="Seconds per interpolated point")
    p.add_argument("--canny-low", type=int, default=50, help="Canny low threshold")
    p.add_argument("--canny-high", type=int, default=150, help="Canny high threshold")
    p.add_argument("--epsilon", type=float, default=0.002, help="Contour simplification factor")
    p.add_argument("--skip-points", type=int, default=2, help="Sample every N points")
    p.add_argument("--min-area", type=int, default=50, help="Minimum contour area filter")
    p.add_argument("--target-size", default=None, help="Max image size: w,h (e.g. 800,600)")
    p.add_argument("--start-delay", type=float, default=3.0, help="Countdown seconds before drawing")
    p.add_argument("--contour-pause", type=float, default=0.1, help="Pause between strokes")
    p.add_argument("--no-pause", action="store_true", help="No pause between strokes")
    p.add_argument("--morph-close", type=int, default=0, help="Morphology close kernel size (0=off)")
    p.add_argument("--dedup-distance", type=float, default=2.0,
                   help="Dedup Chamfer distance threshold (0=off)")
    p.add_argument("--nearest-neighbor", action="store_true", help="Use nearest-neighbor path sort")
    p.add_argument("--interpolate-step", type=int, default=5, help="Mouse interpolation step (px)")
    p.add_argument("--button", default="left", choices=["left", "right", "middle", "x1", "x2"],
                   help="Mouse button for drawing")
    p.add_argument("--manual", action="store_true",
                   help="Manual mode: hold the mouse button yourself to draw")
    p.add_argument("--preview", action="store_true", help="Show processed contours only")
    p.add_argument("--list-windows", action="store_true", help="List all windows and exit")
    p.add_argument("--dry-run", action="store_true", help="Show stats without drawing")
    return p.parse_args()


def parse_pair(s: str, label: str) -> tuple[int, int]:
    """Parse 'w,h' string into (int, int). Validates both > 0."""
    try:
        parts = [int(x.strip()) for x in s.split(",")]
        if len(parts) != 2:
            raise ValueError
        if parts[0] <= 0 or parts[1] <= 0:
            print(f"Error: {label} values must be > 0, got ({parts[0]},{parts[1]})", file=sys.stderr)
            sys.exit(1)
        return (parts[0], parts[1])
    except (ValueError, AttributeError):
        print(f"Error: {label} must be \"width,height\" (e.g. \"800,600\")", file=sys.stderr)
        sys.exit(1)


def parse_offset(s: str) -> tuple[int, int, int, int]:
    """Parse 'left,top,width,height' string. w/h allowed to be 0 (use window size)."""
    try:
        parts = [int(x.strip()) for x in s.split(",")]
        if len(parts) != 4:
            raise ValueError
        left, top, w, h = parts
        if w < 0 or h < 0:
            print(f"Error: canvas width/height must be >= 0, got ({w},{h})", file=sys.stderr)
            sys.exit(1)
        return (left, top, w, h)
    except (ValueError, AttributeError):
        print(f"Error: --canvas-offset must be \"left,top,width,height\"", file=sys.stderr)
        sys.exit(1)


def validate_mouse_args(args: argparse.Namespace) -> None:
    """Validate mouse-related args early, before window lookup."""
    # This triggers MouseConfig.__post_init__ validation
    try:
        MouseConfig(
            start_delay=args.start_delay,
            speed=args.speed,
            contour_pause=args.contour_pause,
            interpolate_step=args.interpolate_step,
            button=args.button,
            manual_mode=args.manual,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_args()

    if not args.input and not args.list_windows:
        print("Error: INPUT image path is required", file=sys.stderr)
        sys.exit(1)

    # --list-windows (no input needed)
    if args.list_windows:
        windows = list_all_windows()
        if not windows:
            print("No windows found.")
        else:
            for w in windows:
                print(f"  [visible] \"{w.title}\"  ({w.left},{w.top}) {w.width}x{w.height}")
        sys.exit(0)

    # --- Early validation (before any heavy work) ---
    # Parse and validate string-format args
    target_size = None
    if args.target_size:
        target_size = parse_pair(args.target_size, "--target-size")

    ox, oy, ow, oh = parse_offset(args.canvas_offset)

    # Validate ALL mouse args (including button and manual_mode)
    validate_mouse_args(args)

    # --- Image processing ---
    image_cfg = ImageConfig(
        canny_low=args.canny_low,
        canny_high=args.canny_high,
        epsilon_factor=args.epsilon,
        skip_points=args.skip_points,
        min_contour_area=args.min_area,
        target_size=target_size,
        morph_close_ksize=args.morph_close,
        dedup_distance=args.dedup_distance,
        neighbor_sort=args.nearest_neighbor,
    )

    try:
        result = process_image(args.input, image_cfg)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not result.contours:
        print("No contours found. Try --canny-low 30 --canny-high 100", file=sys.stderr)
        sys.exit(1)

    # --- Preview (no window needed — exits before any window lookup) ---
    if args.preview:
        _show_preview(args.input, result, target_size)
        sys.exit(0)

    # --- Window lookup (only now we know we need a real window) ---
    try:
        window = find_window(args.window_title)
    except WindowNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build canvas
    if ow == 0:
        ow = window.width
    if oh == 0:
        oh = window.height
    canvas = build_canvas(window, ox, oy, ow, oh)

    # Convert coordinates
    strokes = contours_to_strokes(result.contours, result.img_width, result.img_height, canvas)

    # --- Dry run (no window activation needed) ---
    if args.dry_run:
        _print_dry_run(args, result, strokes, canvas, window)
        sys.exit(0)

    # --- Draw ---
    activate_window(window)

    mouse_cfg = MouseConfig(
        start_delay=args.start_delay,
        speed=args.speed,
        contour_pause=args.contour_pause,
        pause_between_strokes=not args.no_pause,
        interpolate_step=args.interpolate_step,
        button=args.button,
        manual_mode=args.manual,
    )
    drawer = MouseDrawer(mouse_cfg)

    try:
        draw_result = drawer.draw_strokes(strokes)
    except KeyboardInterrupt:
        print("Aborted.", file=sys.stderr)
        sys.exit(0)

    if draw_result.aborted:
        print(f"Aborted: {draw_result.strokes_drawn}/{draw_result.strokes_total} strokes, "
              f"{draw_result.points_moved} points, {draw_result.elapsed_seconds:.1f}s")
    else:
        print(f"Done: {draw_result.strokes_drawn}/{draw_result.strokes_total} strokes, "
              f"{draw_result.points_moved} points, {draw_result.elapsed_seconds:.1f}s")


def _show_preview(input_path: str, result: ProcessResult, target_size: tuple | None) -> None:
    """Show processed contours on the image."""
    img = cv2.imread(input_path)
    if img is None:
        print(f"Error: cannot read image for preview: {input_path}", file=sys.stderr)
        sys.exit(1)

    ih, iw = img.shape[:2]
    if target_size is not None:
        tw, th = target_size
    elif max(ih, iw) > 4096:
        tw, th = 2048, 2048
    else:
        tw, th = iw, ih

    canvas_img = resize_fit(img, (tw, th))
    draw_contours = [c.points.reshape(-1, 1, 2).astype(np.int32) for c in result.contours]
    cv2.drawContours(canvas_img, draw_contours, -1, (0, 255, 0), 2)
    cv2.imshow(f"Preview [{len(result.contours)} contours] - press any key to close", canvas_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def _print_dry_run(args, result: ProcessResult, strokes: list,
                   canvas: CanvasRegion, window: WindowInfo) -> None:
    """Print dry-run statistics."""
    est_time = estimate_draw_time(
        strokes, args.start_delay, args.speed,
        args.contour_pause, not args.no_pause, args.interpolate_step,
    )
    closed_count = sum(1 for c in result.contours if c.is_closed)
    open_count = len(result.contours) - closed_count
    total_pts = sum(len(s.points) for s in strokes)

    print(f"Image: {args.input} ({result.img_width}x{result.img_height})")
    print(f"Contours: {len(result.contours)}  (closed: {closed_count}, open: {open_count})")
    print(f"Total points: {total_pts}")
    print(f"Estimated time: ~{est_time:.1f}s")
    print(f"Canvas: ({canvas.screen_left}, {canvas.screen_top}) "
          f"{canvas.width}x{canvas.height}")
    print(f"Window: \"{window.title}\" at ({window.left},{window.top}) "
          f"{window.width}x{window.height}")
    sort_method = "nearest-neighbor" if args.nearest_neighbor else "area-descending"
    if not args.nearest_neighbor:
        sort_method += " (use --nearest-neighbor for path optimization)"
    print(f"Sort: {sort_method}")
    if args.dedup_distance > 0:
        removed = result.dedup_removed
        print(f"Dedup: {args.dedup_distance}px threshold ({removed} duplicates removed)")


if __name__ == "__main__":
    main()
