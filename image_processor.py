"""Image processing: edge detection, contour extraction, path simplification."""

import os
import sys
from dataclasses import dataclass

import numpy as np
import cv2


@dataclass
class ImageConfig:
    canny_low: int = 50
    canny_high: int = 150
    blur_ksize: tuple[int, int] = (5, 5)
    epsilon_factor: float = 0.002
    skip_points: int = 2
    min_contour_area: int = 50
    target_size: tuple[int, int] | None = None
    morph_close_ksize: int = 0
    dedup_distance: float = 2.0
    neighbor_sort: bool = False
    include_inner_contours: bool = False
    max_hierarchy_depth: int = 2
    edge_mode: str = "gray"  # "gray", "rgb", "lab"
    auto_canny: bool = True
    auto_canny_sigma: float = 0.33
    bilateral_filter: bool = False
    bilateral_d: int = 9

    def __post_init__(self):
        if self.skip_points < 1:
            raise ValueError(f"skip_points must be >= 1, got {self.skip_points}")
        if self.canny_low >= self.canny_high:
            self.canny_low, self.canny_high = self.canny_high, self.canny_low
        b0, b1 = self.blur_ksize
        if b0 < 1 or b1 < 1:
            raise ValueError(f"blur_ksize values must be >= 1, got {self.blur_ksize}")
        if b0 % 2 == 0:
            b0 += 1
        if b1 % 2 == 0:
            b1 += 1
        self.blur_ksize = (b0, b1)
        if self.morph_close_ksize > 0 and self.morph_close_ksize % 2 == 0:
            self.morph_close_ksize += 1
        if self.target_size is not None:
            tw, th = self.target_size
            if tw <= 0 or th <= 0:
                raise ValueError(f"target_size values must be > 0, got {self.target_size}")
        if self.max_hierarchy_depth < 0:
            raise ValueError(f"max_hierarchy_depth must be >= 0, got {self.max_hierarchy_depth}")
        if self.edge_mode not in ("gray", "rgb", "lab"):
            raise ValueError(f"edge_mode must be 'gray', 'rgb', or 'lab', got {self.edge_mode}")
        if self.auto_canny_sigma <= 0 or self.auto_canny_sigma > 1.0:
            raise ValueError(f"auto_canny_sigma must be in (0, 1.0], got {self.auto_canny_sigma}")
        if self.bilateral_d < 1:
            raise ValueError(f"bilateral_d must be >= 1, got {self.bilateral_d}")
        if self.bilateral_d % 2 == 0:
            self.bilateral_d += 1


@dataclass
class Contour:
    points: np.ndarray  # (N, 2), already squeeze'd
    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    area: float
    is_closed: bool


@dataclass
class ProcessResult:
    contours: list  # list[Contour]
    img_width: int
    img_height: int
    edges_image: np.ndarray | None = None
    dedup_removed: int = 0


def process_image(filepath: str, cfg: ImageConfig) -> ProcessResult:
    """Full pipeline: load -> edges -> contours -> simplify -> dedup -> sort."""

    # Step 1: Load & preprocess
    img = cv2.imread(filepath)
    if img is None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        raise ValueError(f"Cannot decode image: {filepath}")

    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    color_img = img if cfg.edge_mode != "gray" else None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    need_resize = cfg.target_size is not None or max(h, w) > 4096
    target = cfg.target_size if cfg.target_size is not None else (2048, 2048)
    if need_resize:
        gray = resize_fit(gray, target)
        if color_img is not None:
            color_img = resize_fit(color_img, target)

    img_h, img_w = gray.shape

    # Step 2: Edge detection
    low, high = resolve_thresholds(gray, cfg) if cfg.auto_canny else (cfg.canny_low, cfg.canny_high)
    if cfg.edge_mode == "gray":
        edges = detect_edges_gray(gray, low, high, cfg)
    else:
        edges = multi_channel_edges(color_img, gray, low, high, cfg)

    if cfg.morph_close_ksize > 0:
        kernel = np.ones((cfg.morph_close_ksize, cfg.morph_close_ksize), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    # Step 3: Contour extraction
    mode = cv2.RETR_TREE if cfg.include_inner_contours else cv2.RETR_EXTERNAL
    raw_contours, hierarchy = cv2.findContours(edges, mode, cv2.CHAIN_APPROX_SIMPLE)

    if cfg.include_inner_contours and hierarchy is not None:
        raw_contours = _filter_by_hierarchy(raw_contours, hierarchy[0], cfg.max_hierarchy_depth)

    contours = []
    for c in raw_contours:
        area = cv2.contourArea(c)
        if area < cfg.min_contour_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        contours.append(Contour(
            points=c,  # placeholder, simplified below
            bbox=(x, y, bw, bh),
            area=area,
            is_closed=True,
        ))

    # Step 4: Path simplification
    for c in contours:
        peri = cv2.arcLength(c.points, closed=True)
        epsilon = max(cfg.epsilon_factor * peri, 0.01)
        approx = cv2.approxPolyDP(c.points, epsilon, closed=True)
        pts = approx.squeeze()

        if pts.ndim < 2:
            if pts.size >= 2:
                if pts.size % 2 != 0:
                    pts = pts[:-1]
                pts = pts.reshape(-1, 2)
            else:
                pts = np.array([], dtype=np.int32).reshape(0, 2)

        if pts.shape[0] > 0:
            pts = pts[::cfg.skip_points]

        x, y, bw, bh = c.bbox
        touches_border = (x <= 1 or y <= 1 or x + bw >= img_w - 1 or y + bh >= img_h - 1)
        c.is_closed = not touches_border

        if c.is_closed and pts.shape[0] >= 2:
            pts = np.vstack([pts, pts[0:1]])
        elif not c.is_closed and pts.shape[0] >= 2:
            pass
        else:
            pts = np.array([], dtype=np.int32).reshape(0, 2)

        c.points = pts

    contours = [c for c in contours if c.points.shape[0] >= 2]

    # Step 5: Dedup
    dedup_removed = 0
    if cfg.dedup_distance > 0 and len(contours) > 1:
        if len(contours) <= 500:
            contours, dedup_removed = _dedup_contours(contours, cfg.dedup_distance)
        else:
            print(f"Warning: {len(contours)} contours, skipping dedup", file=sys.stderr)

    # Step 6: Sort
    if cfg.neighbor_sort:
        contours = _nearest_neighbor_sort(contours)
    else:
        contours.sort(key=lambda c: (-round(c.area, 2), c.bbox[1]))

    return ProcessResult(
        contours=contours, img_width=img_w, img_height=img_h,
        edges_image=edges, dedup_removed=dedup_removed,
    )


def resolve_thresholds(gray: np.ndarray, cfg: ImageConfig) -> tuple[int, int]:
    """Compute Canny thresholds from image statistics when auto_canny is enabled."""
    sigma = cfg.auto_canny_sigma
    v = float(np.median(gray))
    low = int(max(0, (1.0 - sigma) * v))
    high = int(min(255, (1.0 + sigma) * v))
    if low >= high:
        low, high = high, min(255, high + 1)
    return low, high


def detect_edges_gray(gray: np.ndarray, low: int, high: int,
                       cfg: ImageConfig) -> np.ndarray:
    """Single-channel edge detection with optional bilateral filter."""
    if cfg.bilateral_filter:
        smoothed = cv2.bilateralFilter(gray, cfg.bilateral_d, 75, 75)
        smoothed = cv2.GaussianBlur(smoothed, cfg.blur_ksize, 0)
    else:
        smoothed = cv2.GaussianBlur(gray, cfg.blur_ksize, 0)
    return cv2.Canny(smoothed, low, high)


def multi_channel_edges(color_img: np.ndarray, gray_img: np.ndarray,
                        low: int, high: int, cfg: ImageConfig) -> np.ndarray:
    """Edge detection across multiple color channels, merged via bitwise OR."""
    if cfg.edge_mode == "rgb":
        channels = cv2.split(color_img)
    elif cfg.edge_mode == "lab":
        lab = cv2.cvtColor(color_img, cv2.COLOR_BGR2LAB)
        channels = cv2.split(lab)
    else:
        channels = [gray_img]

    edges = None
    for ch in channels:
        if cfg.bilateral_filter:
            smoothed = cv2.bilateralFilter(ch, cfg.bilateral_d, 75, 75)
            smoothed = cv2.GaussianBlur(smoothed, cfg.blur_ksize, 0)
        else:
            smoothed = cv2.GaussianBlur(ch, cfg.blur_ksize, 0)
        ch_edges = cv2.Canny(smoothed, low, high)
        if edges is None:
            edges = ch_edges
        else:
            edges = cv2.bitwise_or(edges, ch_edges)
    return edges


def _filter_by_hierarchy(contours: list, hierarchy: np.ndarray,
                         max_depth: int) -> list:
    """Filter contours by hierarchy nesting depth (0 = outermost only)."""
    filtered = []
    for i in range(len(contours)):
        depth = 0
        parent = hierarchy[i][3]
        while parent != -1:
            depth += 1
            parent = hierarchy[parent][3]
        if depth <= max_depth:
            filtered.append(contours[i])
    return filtered


def resize_fit(img: np.ndarray, target: tuple) -> np.ndarray:
    """Resize to fit within target, preserving aspect ratio. Pad with black.
    Works with grayscale (H,W), color (H,W,C), or any ndim >= 2 arrays.
    """
    h, w = img.shape[:2]
    tw, th = target
    scale = min(tw / w, th / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))
    canvas = np.zeros((th, tw) + img.shape[2:], dtype=img.dtype)
    x_off = (tw - new_w) // 2
    y_off = (th - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def _dedup_contours(contours: list, threshold: float) -> tuple:
    """Remove near-duplicate contours using Chamfer distance sampling.
    Returns (filtered_list, removed_count).
    """
    kept = list(contours)
    removed = set()
    sample_n = 20

    for i in range(len(kept)):
        if i in removed:
            continue
        pts_i = _sample_contour(kept[i].points, sample_n)
        if len(pts_i) == 0:
            continue
        for j in range(i + 1, len(kept)):
            if j in removed:
                continue
            pts_j = _sample_contour(kept[j].points, sample_n)
            if len(pts_j) == 0:
                continue
            dist_ij = _chamfer(pts_i, pts_j)
            dist_ji = _chamfer(pts_j, pts_i)
            if min(dist_ij, dist_ji) < threshold:
                if kept[i].area >= kept[j].area:
                    removed.add(j)
                else:
                    removed.add(i)
                    break

    result = [c for idx, c in enumerate(kept) if idx not in removed]
    if not result:
        return (list(contours), 0)
    return (result, len(removed))


def _sample_contour(points: np.ndarray, n: int) -> np.ndarray:
    """Sample n evenly-spaced points from contour."""
    if points.shape[0] < 2:
        return np.array([], dtype=np.float32)
    idx = np.linspace(0, points.shape[0] - 1, min(n, points.shape[0]), dtype=int)
    return points[idx].astype(np.float32)


def _chamfer(a: np.ndarray, b: np.ndarray) -> float:
    """Mean min-distance from each point in a to any point in b."""
    if len(a) == 0 or len(b) == 0:
        return float("inf")
    dists = np.linalg.norm(a[:, None] - b[None, :], axis=2)
    return float(np.mean(np.min(dists, axis=1)))


def _nearest_neighbor_sort(contours: list) -> list:
    """Greedy nearest-neighbor: start from largest, always visit closest unvisited."""
    if len(contours) <= 1:
        return list(contours)
    remaining = list(contours)
    remaining.sort(key=lambda c: -c.area)
    result = [remaining.pop(0)]

    while remaining:
        last_end = result[-1].points[-1]
        best_idx = 0
        best_dist = float("inf")
        for i, c in enumerate(remaining):
            d = np.linalg.norm(last_end.astype(float) - c.points[0].astype(float))
            if d < best_dist:
                best_dist = d
                best_idx = i
        result.append(remaining.pop(best_idx))

    return result
