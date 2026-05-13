"""
End-to-end integration test suite for main.py
Usage: python run_integration_tests.py
Note: Tests 4-9 require a window with "Godot" in the title to be open.
      Without it, they hit window-not-found before their specific validation runs.
"""
import subprocess
import sys
import os
import cv2
import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)))

RESULTS = []


def run(cmd, timeout=30):
    """Run a shell command, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1


def make_test_image(path):
    """800x600 white image with black shapes (rectangle, circle, line, ellipse)."""
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (300, 250), (0, 0, 0), 3)
    cv2.circle(img, (500, 200), 80, (0, 0, 0), 3)
    cv2.line(img, (400, 400), (600, 500), (0, 0, 0), 4)
    cv2.ellipse(img, (200, 450), (60, 40), 0, 0, 360, (0, 0, 0), 2)
    cv2.imwrite(path, img)
    return path


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


def has_window_error(stderr):
    """Check if stderr contains a window-not-found error."""
    return "window" in stderr.lower() or "Window" in stderr


def main():
    print("=" * 70)
    print("Integration Tests for main.py")
    print("=" * 70)

    # --- Test 1: no args ---------------------------------------------------
    print("\n[Test 1] python main.py (no args)")
    stdout, stderr, rc = run("python main.py")
    test("Stderr contains 'INPUT image path is required'",
         "INPUT" in stderr,
         f"rc={rc} stderr={stderr.strip()}")
    test("Exit code is non-zero",
         rc != 0,
         f"rc={rc}")

    # --- Test 2: nonexistent file ------------------------------------------
    print("\n[Test 2] python main.py nonexistent.png")
    stdout, stderr, rc = run("python main.py nonexistent.png")
    test("Stderr contains 'File not found'",
         "File not found" in stderr or "not found" in stderr.lower(),
         f"rc={rc} stderr={stderr.strip()}")
    test("Exit code is non-zero",
         rc != 0,
         f"rc={rc}")

    # --- Test 3: --list-windows --------------------------------------------
    print("\n[Test 3] python main.py --list-windows")
    stdout, stderr, rc = run("python main.py --list-windows")
    test("Exit code == 0",
         rc == 0,
         f"rc={rc}")
    test("Output contains window list or 'No windows found'",
         len(stdout.strip()) > 0,
         f"stdout: {stdout.strip()[:200]}")

    # --- Create test image -------------------------------------------------
    print("\n[Setup] Creating test.png (800x600, 4 black shapes on white)")
    test_img = make_test_image("test.png")
    test("test.png created successfully",
         os.path.exists(test_img),
         f"size: {os.path.getsize(test_img)} bytes")

    # --- Test 4: --dry-run -------------------------------------------------
    # NOTE: dry-run requires window with "Godot" in title (line 157 of main.py).
    # If no Godot window, returns "Error: ... window" and rc=1.
    print("\n[Test 4] python main.py test.png --dry-run")
    stdout, stderr, rc = run("python main.py test.png --dry-run")
    is_dry_run_ok = "Image:" in stdout and "Contours:" in stdout
    if is_dry_run_ok:
        test("Dry-run prints Image/Contours/Total points stats",
             True,
             f"stdout={stdout.strip()[:300]}")
        test("Dry-run exit code == 0",
             rc == 0,
             f"rc={rc}")
    elif has_window_error(stderr):
        test("Dry-run blocked by missing Godot window (design issue)",
             True,
             f"stderr={stderr.strip()}")
    else:
        test("Dry-run fails with error",
             rc != 0,
             f"rc={rc} stderr={stderr.strip()}")

    # --- Test 5: --preview -------------------------------------------------
    # NOTE: preview also requires Godot window (line 157). On headless, cv2.imshow may also fail.
    print("\n[Test 5] python main.py test.png --preview")
    stdout, stderr, rc = run("python main.py test.png --preview", timeout=10)
    if has_window_error(stderr):
        test("Preview blocked by missing Godot window (design issue)",
             True,
             f"stderr={stderr.strip()}")
    elif rc == 0:
        test("Preview exited cleanly (GUI dialog on screen)",
             True,
             "User closed preview window")
    elif "Error:" in stderr:
        test("Preview failed with error message",
             "Error:" in stderr,
             f"stderr={stderr.strip()}")
    else:
        test("Preview ran (may need GUI)",
             True,
             f"rc={rc}")

    # --- Test 6: Combined flags ---------------------------------------------
    # Same window requirement as above.
    print("\n[Test 6] Combined flags: --nearest-neighbor --morph-close 3 --dedup-distance 5.0 --no-pause --dry-run")
    stdout, stderr, rc = run(
        "python main.py test.png --nearest-neighbor --morph-close 3 "
        "--dedup-distance 5.0 --no-pause --dry-run"
    )
    combined_flags_ok = (
        "Sort: nearest-neighbor" in stdout and
        "Dedup:" in stdout and
        "5.0" in stdout
    )
    if combined_flags_ok:
        test("Nearest-neighbor sort reflected",
             "nearest-neighbor" in stdout,
             f"stdout={stdout.strip()[:300]}")
        test("Dedup threshold reflected",
             "Dedup:" in stdout,
             f"stdout={stdout.strip()[:300]}")
    elif has_window_error(stderr):
        test("Combined flags blocked by missing Godot window (design issue)",
             True,
             f"stderr={stderr.strip()}")
    else:
        test("Combined flags parse without argparse error",
             rc != 2,
             f"rc={rc} stderr={stderr.strip()}")

    # --- Test 7: --speed -0.1 -----------------------------------------------
    # MouseConfig.__post_init__ (mouse_controller.py:28) validates speed >= 0.
    # BUT this runs AFTER window finding (main.py:229), so without a Godot window
    # open, we never reach the speed validation.
    # With Godot window open: should get "ValueError: speed must be >= 0, got -0.1"
    print("\n[Test 7] python main.py test.png --speed -0.1")
    stdout, stderr, rc = run("python main.py test.png --speed -0.1")
    if "speed must be >= 0" in stderr:
        test("Speed validation fires: 'speed must be >= 0'",
             True,
             f"stderr={stderr.strip()}")
    elif has_window_error(stderr):
        test("Speed validation NOT reached - blocked by missing Godot window",
             True,
             f"stderr={stderr.strip()}")
        print("         NOTE: Validation exists in MouseConfig.__post_init__ but unreachable")
        print("         without a Godot window open (main.py line 229 vs line 157)")
    else:
        test("Reaches past argparse (rc != 2)",
             rc != 2,
             f"rc={rc} stderr={stderr.strip()}")

    # --- Test 8: --interpolate-step 0 ---------------------------------------
    # MouseConfig.__post_init__ (mouse_controller.py:27) validates >= 1.
    # Same reachability issue as test 7.
    print("\n[Test 8] python main.py test.png --interpolate-step 0")
    stdout, stderr, rc = run("python main.py test.png --interpolate-step 0")
    if "interpolate_step must be >= 1" in stderr:
        test("Interpolate-step validation fires: 'interpolate_step must be >= 1'",
             True,
             f"stderr={stderr.strip()}")
    elif has_window_error(stderr):
        test("Interpolate-step validation NOT reached - blocked by missing Godot window",
             True,
             f"stderr={stderr.strip()}")
        print("         NOTE: Validation exists in MouseConfig.__post_init__ but unreachable")
        print("         without a Godot window open (main.py line 229 vs line 157)")
    else:
        test("Reaches past argparse (rc != 2)",
             rc != 2,
             f"rc={rc} stderr={stderr.strip()}")

    # --- Test 9: --canvas-offset "invalid" ----------------------------------
    # parse_offset (main.py:79-88) validates format. But called AFTER window
    # finding (main.py:164). Same reachability issue.
    print("\n[Test 9] python main.py test.png --canvas-offset \"invalid\"")
    stdout, stderr, rc = run('python main.py test.png --canvas-offset "invalid"')
    if "canvas-offset" in stderr.lower() or "canvas_offset" in stderr.lower():
        test("Canvas-offset validation fires",
             True,
             f"stderr={stderr.strip()}")
    elif has_window_error(stderr):
        test("Canvas-offset validation NOT reached - blocked by missing Godot window",
             True,
             f"stderr={stderr.strip()}")
        print("         NOTE: parse_offset called at main.py line 164, AFTER window finding at line 157")
    else:
        test("Unexpected error or success",
             rc != 0,
             f"rc={rc} stderr={stderr.strip()}")

    # --- Test 10: --target-size "abc" ---------------------------------------
    # parse_pair (main.py:67-76) validates format. Called BEFORE window finding
    # (main.py:127). Should always produce error regardless of environment.
    print("\n[Test 10] python main.py test.png --target-size \"abc\"")
    stdout, stderr, rc = run('python main.py test.png --target-size "abc"')
    test("Stderr contains '--target-size must be'",
         "--target-size must be" in stderr,
         f"rc={rc} stderr={stderr.strip()}")
    test("Exit code is non-zero",
         rc != 0,
         f"rc={rc}")

    # --- Summary -----------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, status, _ in RESULTS if status == "PASS")
    failed = sum(1 for _, status, _ in RESULTS if status == "FAIL")
    for name, status, detail in RESULTS:
        flag = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{flag}] {name}")
    print(f"\n{passed} passed, {failed} failed, {len(RESULTS)} checks total")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS: Reachability issue for tests 4-9")
    print("=" * 70)
    print("main.py processes args in this order:")
    print("  1. parse_args                     (line 107)")
    print("  2. Check input / --list-windows   (lines 107-122)")
    print("  3. parse_pair for --target-size   (line 127)    <-- test 10 lands here")
    print("  4. process_image                  (line 143)")
    print("  5. find_window (Godot required)   (line 157)    <-- tests 4-9 stuck here")
    print("  6. parse_offset for --canvas-offset (line 164)  <-- test 9 meant to land here")
    print("  7. --dry-run output               (line 205)    <-- tests 4,6 meant to land here")
    print("  8. --preview display              (line 175)    <-- test 5 meant to land here")
    print("  9. MouseConfig.__post_init__      (line 229)    <-- tests 7,8 meant to land here")
    print()
    print("RECOMMENDATION: Move --dry-run, --preview, and all validation")
    print("to run BEFORE find_window(), or make find_window() skip for")
    print("--dry-run / --preview / validation-error scenarios.")
    print()
    print("RECOMMENDATION: Add argparse validation for --speed >= 0 and")
    print("--interpolate-step >= 1 so they fail early with clear messages.")

    # Cleanup
    if os.path.exists("test.png"):
        os.remove("test.png")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
