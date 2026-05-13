"""Edge case / stress tests for image_processor.py and mouse_controller.py."""

import sys, os, tempfile, math, time, io
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_processor import (
    ImageConfig, Contour, ProcessResult, process_image,
    resize_fit, _dedup_contours, _chamfer, _sample_contour, _nearest_neighbor_sort
)
from mouse_controller import MouseConfig, Stroke, DrawResult, MouseDrawer


# ── helpers ──────────────────────────────────────────────────────────────────

PASS, FAIL = 0, 0

def test(name, passed):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")

def write_png(path, img):
    """Write numpy image (H,W) or (H,W,3) as PNG."""
    if img.dtype != np.uint8:
        if img.max() <= 1.0:
            img = (img * 255).astype(np.uint8)
        else:
            img = img.astype(np.uint8)
    if len(img.shape) == 2:
        cv2.imwrite(path, img)
    else:
        cv2.imwrite(path, img)

def run_to_file(img, cfg=None):
    """Create temp PNG from `img`, call process_image, clean up, return result."""
    fd, fpath = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        write_png(fpath, img)
        return process_image(fpath, cfg or ImageConfig())
    finally:
        os.unlink(fpath)


# ── IMAGE PROCESSOR TESTS ──

def test_empty_white():
    """1. Empty/white image (no edges)"""
    print("\n── Image Test 1: Empty/white image ──")
    img = np.full((200, 200), 255, dtype=np.uint8)
    r = run_to_file(img)
    test("returns ProcessResult", isinstance(r, ProcessResult))
    test("no contours", len(r.contours) == 0)
    test("correct dimensions", r.img_width == 200 and r.img_height == 200)

def test_1x1():
    """2. 1x1 pixel image"""
    print("\n── Image Test 2: 1x1 pixel image ──")
    img = np.array([[128]], dtype=np.uint8)
    r = run_to_file(img)
    test("returns ProcessResult", isinstance(r, ProcessResult))
    test("dimensions correct", r.img_width == 1 and r.img_height == 1)
    test("no crash", True)

def test_large_image():
    """3. Very large image (>4096px, test auto-resize)"""
    print("\n── Image Test 3: Very large image (>4096px) ──")
    # Create a 5000x3000 image with a circle (so it has edges)
    img = np.zeros((5000, 3000), dtype=np.uint8)
    cv2.circle(img, (1500, 2500), 200, 255, 3)
    r = run_to_file(img)
    test("auto-resized under 4096", max(r.img_width, r.img_height) <= 4096)
    test("image was downsized", r.img_width <= 2048 or r.img_height <= 2048)
    test("detected some contour", len(r.contours) > 0)
    test("no crash on large", True)

def test_small_contours():
    """4. Image with many small contours (< min_area)"""
    print("\n── Image Test 4: Many small contours (< min_area) ──")
    # Sprinkle tiny dots (area ~1-4 px) and one big box
    img = np.full((300, 400), 255, dtype=np.uint8)
    for _ in range(100):
        x, y = np.random.randint(5, 395), np.random.randint(5, 295)
        cv2.circle(img, (x, y), 1, 0, -1)
    cv2.rectangle(img, (50, 50), (100, 100), 0, -1)
    cfg = ImageConfig(min_contour_area=30)
    r = run_to_file(img, cfg)
    test("no tiny contours pass filter", all(c.area >= cfg.min_contour_area for c in r.contours))
    test("large contour found", len(r.contours) >= 1)
    test("filtered out noise", len(r.contours) < 100)

def test_touching_borders():
    """5. Image touching all 4 borders"""
    print("\n── Image Test 5: Contour touching all 4 borders ──")
    img = np.full((200, 200), 255, dtype=np.uint8)
    # full black border (touches all edges)
    cv2.rectangle(img, (0, 0), (199, 199), 0, 1)
    r = run_to_file(img)
    test("contours found", len(r.contours) > 0)
    for c in r.contours:
        x, y, bw, bh = c.bbox
        touches = (x <= 1) or (y <= 1) or (x + bw >= r.img_width - 1) or (y + bh >= r.img_height - 1)
        test(f"closed=False for border contour {c.bbox}", c.is_closed == False)

def test_blur_ksize():
    """6. Various blur_ksize values (even, 1, 0)"""
    print("\n── Image Test 6: blur_ksize edge cases ──")
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (150, 150), 0, 3)

    for label, ksize in [("even (4,4)", (4, 4)), ("(1,1)", (1, 1))]:
        cfg = ImageConfig(blur_ksize=ksize)
        actual = cfg.blur_ksize
        # __post_init__ fixes even -> odd
        if ksize == (4, 4):
            test(f"ksize {label} auto-fixed to odd", actual[0] % 2 == 1 and actual[1] % 2 == 1)
        try:
            r = run_to_file(img, cfg)
            test(f"process with ksize {label} works", isinstance(r, ProcessResult) and r.img_width > 0)
        except Exception as e:
            test(f"process with ksize {label} crashes: {e}", False)

    # (0,0) should be rejected by __post_init__
    try:
        ImageConfig(blur_ksize=(0, 0))
        test("ksize (0,0) rejected", False)
    except ValueError:
        test("ksize (0,0) rejected", True)

def test_morph_edge_cases():
    """7. morph_close_ksize edge cases (0, 1, even)"""
    print("\n── Image Test 7: morph_close_ksize edge cases ──")
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (150, 150), 0, 3)

    for label, k in [("0 (skip)", 0), ("1 (min)", 1), ("2 (even->3)", 2)]:
        cfg = ImageConfig(morph_close_ksize=k)
        actual = cfg.morph_close_ksize
        if k == 2:
            test(f"ksize {label} auto-fixed to {actual}", actual == 3)
        try:
            r = run_to_file(img, cfg)
            test(f"process with morph k={label} works", isinstance(r, ProcessResult) and len(r.contours) > 0)
        except Exception as e:
            test(f"process with morph k={label} crashes: {e}", False)

def test_skip_points():
    """8. skip_points extremes (1, 100)"""
    print("\n── Image Test 8: skip_points extremes ──")
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.rectangle(img, (30, 30), (270, 270), 0, 3)

    for skip in [1, 100]:
        cfg = ImageConfig(skip_points=skip, min_contour_area=20)
        r = run_to_file(img, cfg)
        test(f"skip_points={skip} no crash", isinstance(r, ProcessResult))
        if len(r.contours) > 0:
            pts = r.contours[0].points
            test(f"skip_points={skip} has >=2 points", pts.shape[0] >= 2)

def test_dedup_distance():
    """9. dedup_distance = 0 (disabled) and 10 (aggressive)"""
    print("\n── Image Test 9: dedup_distance ──")
    # Two nearly identical circles
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img, (90, 150), 40, 0, 3)
    cv2.circle(img, (95, 150), 42, 0, 3)

    cfg0 = ImageConfig(dedup_distance=0, min_contour_area=20)
    r0 = run_to_file(img, cfg0)
    test("dedup=0 keeps both", len(r0.contours) >= 2)

    cfg10 = ImageConfig(dedup_distance=10, min_contour_area=20)
    r10 = run_to_file(img, cfg10)
    test("dedup=10 merges near-duplicates", len(r10.contours) < len(r0.contours))

def test_neighbor_sort():
    """10. neighbor_sort=True"""
    print("\n── Image Test 10: neighbor_sort=True ──")
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img, (50, 50), 30, 0, 3)
    cv2.circle(img, (200, 200), 30, 0, 3)
    cv2.circle(img, (51, 55), 25, 0, 3)

    cfg = ImageConfig(neighbor_sort=True, min_contour_area=10)
    r = run_to_file(img, cfg)
    test("neighbor_sort=True no crash", isinstance(r, ProcessResult))
    # With neighbor sort, order is greedy nearest-neighbor
    test("contours present", len(r.contours) >= 2)

def test_canny_invalid():
    """Extra: canny_low >= canny_high auto-swap"""
    print("\n── Image Test EXTRA: canny_low >= canny_high ──")
    cfg = ImageConfig(canny_low=200, canny_high=50)
    test("auto-swapped", cfg.canny_low == 50 and cfg.canny_high == 200)

def test_target_size():
    """Extra: explicit target_size resizes"""
    print("\n── Image Test EXTRA: target_size ──")
    img = np.full((500, 800), 255, dtype=np.uint8)
    cv2.circle(img, (400, 250), 50, 0, 3)
    cfg = ImageConfig(target_size=(400, 300), min_contour_area=20)
    r = run_to_file(img, cfg)
    test("resized to target width", r.img_width <= 400)
    test("resized to target height", r.img_height <= 300)


# ── MOUSE CONTROLLER TESTS ──

def test_mouse_config_validation():
    """1. MouseConfig validation"""
    print("\n── Mouse Test 1: MouseConfig validation ──")
    ok, ng = 0, 0

    # negative speed
    try:
        MouseConfig(speed=-0.1)
        test("speed < 0 rejected", False)
    except ValueError as e:
        test("speed < 0 raises ValueError", "speed" in str(e).lower())

    # step=0
    try:
        MouseConfig(interpolate_step=0)
        test("step=0 rejected", False)
    except ValueError as e:
        test("step=0 raises ValueError", "step" in str(e).lower() or "interpolate" in str(e).lower())

    # valid defaults
    try:
        mc = MouseConfig()
        test("default config valid", mc.speed == 0.002 and mc.interpolate_step == 5)
    except Exception as e:
        test(f"default config fails: {e}", False)

def test_stroke_edge_cases():
    """2. Stroke with 0, 1, 2, 100 points"""
    print("\n── Mouse Test 2: Stroke edge cases ──")
    # Stroke objects store metadata, nothing crashes on construction
    for n, label in [(0, "empty"), (1, "single"), (2, "pair"), (100, "100 pts")]:
        pts = [(i * 10, i * 10) for i in range(n)]
        s = Stroke(points=pts, is_closed=(n >= 3))
        test(f"Stroke({label}) points={len(s.points)}", len(s.points) == n)

def test_draw_result():
    """3. DrawResult field correctness"""
    print("\n── Mouse Test 3: DrawResult ──")
    r = DrawResult(strokes_drawn=5, strokes_total=10, points_moved=42,
                   aborted=False, elapsed_seconds=2.5)
    test("strokes_drawn", r.strokes_drawn == 5)
    test("strokes_total", r.strokes_total == 10)
    test("points_moved", r.points_moved == 42)
    test("aborted=False", r.aborted is False)
    test("elapsed_seconds", abs(r.elapsed_seconds - 2.5) < 0.001)

def test_drawer_creation():
    """Extra: MouseDrawer instantiation"""
    print("\n── Mouse Test EXTRA: MouseDrawer creation ──")
    try:
        d = MouseDrawer(MouseConfig())
        test("drawer created", hasattr(d, "cfg") and hasattr(d, "_mouse"))
    except Exception as e:
        test(f"drawer creation failed: {e}", False)

def test_move_to_math():
    """Extra: _move_to interpolation with step=1"""
    print("\n── Mouse Test EXTRA: _move_to with step=1 ──")
    md = MouseDrawer(MouseConfig(interpolate_step=1, speed=0))
    # call _move_to manually; it should not crash
    try:
        md._move_manual((0, 0), (10, 10))
        test("_move_to intra-step works (dist > step)", True)
    except Exception as e:
        test(f"_move_to failed: {e}", False)
    try:
        md._move_manual((0, 0), (1, 0))
        test("_move_to single-step works (dist <= step)", True)
    except Exception as e:
        test(f"_move_to failed: {e}", False)

def test_move_to_speed_zero():
    """Extra: speed=0 should not crash"""
    print("\n── Mouse Test EXTRA: speed=0 ──")
    mc = MouseConfig(speed=0, interpolate_step=1)
    test("speed=0 valid", mc.speed == 0)
    md = MouseDrawer(mc)
    try:
        md._move_manual((0, 0), (5, 5))
        test("_move_to with speed=0 works", True)
    except Exception as e:
        test(f"_move_to with speed=0: {e}", False)


# ── STRESS TEST ──

def stress_test_many_contours():
    """Generate ~300 contours in a large image."""
    print("\n── Stress Test: many contours ──")
    img = np.full((600, 800), 255, dtype=np.uint8)
    for i in range(50):
        for j in range(50):
            x, y = i * 16 + 4, j * 12 + 4
            if np.random.random() > 0.88:
                cv2.circle(img, (x, y), 3, np.random.randint(0, 100), -1)
    # Add one big recognizable contour
    cv2.rectangle(img, (100, 100), (200, 200), 0, 3)

    cfg = ImageConfig(dedup_distance=3, min_contour_area=5, neighbor_sort=True)
    fd, fpath = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        write_png(fpath, img)
        import time as tmodule
        start = tmodule.time()
        r = process_image(fpath, cfg)
        elapsed = tmodule.time() - start
        test("stress test completes", isinstance(r, ProcessResult))
        test(f"stress test under 5s ({elapsed:.1f}s)", elapsed < 5.0)
        print(f"      contours: {len(r.contours)}, elapsed: {elapsed:.2f}s")
    finally:
        os.unlink(fpath)


# ── RUN ALL ──

if __name__ == "__main__":
    print("=" * 60)
    print("IMAGE PROCESSOR EDGE CASE / STRESS TESTS")
    print("=" * 60)

    test_empty_white()
    test_1x1()
    test_large_image()
    test_small_contours()
    test_touching_borders()
    test_blur_ksize()
    test_morph_edge_cases()
    test_skip_points()
    test_dedup_distance()
    test_neighbor_sort()
    test_canny_invalid()
    test_target_size()

    print("\n" + "=" * 60)
    print("MOUSE CONTROLLER EDGE CASE / STRESS TESTS")
    print("=" * 60)

    test_mouse_config_validation()
    test_stroke_edge_cases()
    test_draw_result()
    test_drawer_creation()
    test_move_to_math()
    test_move_to_speed_zero()

    print("\n" + "=" * 60)
    print("STRESS TESTS")
    print("=" * 60)

    stress_test_many_contours()

    # Summary
    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"SUMMARY: {total} tests, {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("  STATUS: FAILURES DETECTED")
        sys.exit(1)
    else:
        print("  STATUS: ALL CLEAR")
    print("=" * 60)
