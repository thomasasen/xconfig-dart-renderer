from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional
import math

import cv2
import numpy as np
from PIL import Image

PASS = "PASS"
FAIL_AXIS = "FAIL_AXIS"
FAIL_ROOT_INCLUDED_IN_SHAFT = "FAIL_ROOT_INCLUDED_IN_SHAFT"
FAIL_ROOT_ALIGNMENT = "FAIL_ROOT_ALIGNMENT"
FAIL_ALPHA_HAZE = "FAIL_ALPHA_HAZE"
FAIL_COMPOSITE_FLIGHT = "FAIL_COMPOSITE_FLIGHT"
FAIL_SOURCE_UNSUITABLE = "FAIL_SOURCE_UNSUITABLE"
NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"


@dataclass
class AxisAnalysis:
    angle_deg: float
    axis_center_y_px: float
    fit_residual_p95_px: float
    median_width_px: float
    confidence: float

    def to_dict(self):
        return {
            "angleDeg": round(float(self.angle_deg), 4),
            "axisCenterYPx": round(float(self.axis_center_y_px), 3),
            "fitResidualPxP95": round(float(self.fit_residual_p95_px), 3),
            "medianWidthPx": round(float(self.median_width_px), 3),
            "confidence": round(float(self.confidence), 4),
        }


@dataclass
class SilhouetteProfile:
    x: np.ndarray
    top: np.ndarray
    bottom: np.ndarray
    center: np.ndarray
    width: np.ndarray
    valid: np.ndarray
    axis_y: float


@dataclass
class TailAnalysis:
    axis_angle_deg: float
    shaft_start_px: int
    shaft_end_px: int
    root_start_px: Optional[int]
    root_end_px: Optional[int]
    shaft_width_median_px: float
    shaft_width_cv: float
    shaft_center_residual_p95_px: float
    shaft_center_jump_max_px: float
    root_axis_offset_px: Optional[float]
    root_width_progression: Optional[float]
    haze_ratio: float
    root_leak_ratio: float
    axis_confidence: float
    shaft_core_confidence: float
    root_boundary_confidence: float
    confidence: float
    status: str

    def to_dict(self):
        raw = asdict(self)
        names = {
            "axis_angle_deg": "axisAngleDeg",
            "shaft_start_px": "shaftStartPx",
            "shaft_end_px": "shaftEndPx",
            "root_start_px": "rootStartPx",
            "root_end_px": "rootEndPx",
            "shaft_width_median_px": "shaftWidthMedianPx",
            "shaft_width_cv": "shaftWidthCV",
            "shaft_center_residual_p95_px": "shaftAxisResidualP95Px",
            "shaft_center_jump_max_px": "shaftCenterJumpMaxPx",
            "root_axis_offset_px": "rootAxisOffsetPx",
            "root_width_progression": "rootWidthProgression",
            "haze_ratio": "tailAlphaHaze",
            "root_leak_ratio": "rootLeakIntoShaftRatio",
            "axis_confidence": "axisConfidence",
            "shaft_core_confidence": "shaftCoreConfidence",
            "root_boundary_confidence": "rootBoundaryConfidence",
            "confidence": "overallConfidence",
            "status": "status",
        }
        result = {}
        for key, value in raw.items():
            if isinstance(value, float):
                value = round(value, 4)
            result[names[key]] = value
        return result


def _rgba(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA")).copy()


def _largest_component(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n <= 1:
        return binary.astype(bool)
    candidates = []
    for lab in range(1, n):
        _, _, width, height, area = stats[lab]
        if area <= 0:
            continue
        elongation = width / max(1, height)
        candidates.append((area * (1.0 + min(elongation, 20.0) / 8.0), lab))
    if not candidates:
        return binary.astype(bool)
    return labels == max(candidates)[1]


def alpha_foreground_mask(image: Image.Image, threshold: int = 40) -> np.ndarray:
    alpha = _rgba(image)[:, :, 3]
    strong = (alpha >= threshold).astype(np.uint8) * 255
    strong = cv2.morphologyEx(strong, cv2.MORPH_CLOSE, np.ones((1, 3), np.uint8))
    return _largest_component(strong)


def _raw_profile(mask: np.ndarray):
    width_px = mask.shape[1]
    top = np.full(width_px, np.nan, dtype=np.float64)
    bottom = np.full(width_px, np.nan, dtype=np.float64)
    center = np.full(width_px, np.nan, dtype=np.float64)
    width = np.full(width_px, np.nan, dtype=np.float64)
    for x in range(width_px):
        ys = np.flatnonzero(mask[:, x])
        if not ys.size:
            continue
        top[x], bottom[x] = float(ys[0]), float(ys[-1])
        center[x] = (top[x] + bottom[x]) * 0.5
        width[x] = bottom[x] - top[x] + 1.0
    return top, bottom, center, width


def _interpolate(values: np.ndarray) -> np.ndarray:
    data = np.asarray(values, dtype=np.float64).copy()
    good = np.isfinite(data)
    if not good.any():
        return np.zeros_like(data)
    x = np.arange(data.size)
    data[~good] = np.interp(x[~good], x[good], data[good])
    return data


def _median_filter(values: np.ndarray, ksize: int = 7) -> np.ndarray:
    data = _interpolate(values)
    k = max(3, int(ksize))
    if k % 2 == 0:
        k += 1
    if data.size < k:
        return data
    pad = k // 2
    padded = np.pad(data, (pad, pad), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, k)
    return np.median(windows, axis=-1).astype(np.float64)


def analyze_axis(image: Image.Image, x_range=None) -> AxisAnalysis:
    mask = alpha_foreground_mask(image)
    _, _, center, width = _raw_profile(mask)
    valid = np.isfinite(center) & np.isfinite(width) & (width >= 2)
    if valid.sum() < 12:
        return AxisAnalysis(0.0, image.height / 2.0, 999.0, 1.0, 0.0)

    xs = np.flatnonzero(valid).astype(np.float64)
    widths = width[valid]
    centers = center[valid]
    if x_range is not None:
        range_start,range_end=_bounds_px(x_range,image.width)
        in_range=(xs>=range_start)&(xs<range_end)
        if in_range.sum()>=12:
            xs=xs[in_range]
            widths=widths[in_range]
            centers=centers[in_range]
    xmin, xmax = xs.min(), xs.max()
    span = max(1.0, xmax - xmin)
    width_cut = np.percentile(widths, 68)
    selected = (
        (widths <= max(width_cut * 1.35, np.median(widths) * 1.75))
        & (xs >= xmin + span * 0.03)
        & (xs <= xmin + span * 0.84)
    )
    if selected.sum() < 12:
        selected = widths <= np.percentile(widths, 82)

    fit_x = xs[selected]
    fit_y = centers[selected]
    weights = np.maximum(1.0, width_cut / np.maximum(widths[selected], 1.0))
    A = np.column_stack([fit_x, np.ones_like(fit_x)])
    coeff, *_ = np.linalg.lstsq(A * weights[:, None], fit_y * weights, rcond=None)
    for _ in range(3):
        residual = fit_y - (coeff[0] * fit_x + coeff[1])
        median = np.median(residual)
        mad = np.median(np.abs(residual - median))
        limit = max(1.25, 3.2 * 1.4826 * mad)
        keep = np.abs(residual - median) <= limit
        if keep.sum() < 10:
            break
        coeff, *_ = np.linalg.lstsq(
            A[keep] * weights[keep, None],
            fit_y[keep] * weights[keep],
            rcond=None,
        )

    slope, intercept = float(coeff[0]), float(coeff[1])
    residual = fit_y - (slope * fit_x + intercept)
    p95 = float(np.percentile(np.abs(residual), 95))
    median_width = float(np.median(widths[selected]))
    normalized = p95 / max(1.0, median_width)
    support = min(1.0, selected.sum() / max(20.0, valid.sum() * 0.45))
    confidence = float(np.clip((1.0 - normalized / 0.28) * 0.82 + support * 0.18, 0, 1))
    axis_y = slope * ((image.width - 1) * 0.5) + intercept
    return AxisAnalysis(
        math.degrees(math.atan(slope)),
        float(axis_y),
        p95,
        median_width,
        confidence,
    )


def align_image_to_axis(image: Image.Image, axis: AxisAnalysis, max_auto_angle_deg: float = 6.0) -> Image.Image:
    angle = float(axis.angle_deg)
    if not math.isfinite(angle) or abs(angle) < 0.03 or abs(angle) > max_auto_angle_deg:
        return image.convert("RGBA")
    return image.convert("RGBA").rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )


def build_silhouette_profile(
    image: Image.Image,
    axis: AxisAnalysis | None = None,
    median_window: int = 7,
) -> SilhouetteProfile:
    mask = alpha_foreground_mask(image)
    top, bottom, center, width = _raw_profile(mask)
    valid = np.isfinite(center) & np.isfinite(width) & (width > 0)
    top = _median_filter(top, median_window)
    bottom = _median_filter(bottom, median_window)
    center = _median_filter(center, median_window)
    width = np.maximum(0.0, bottom - top + 1.0)
    axis_y = float(axis.axis_center_y_px) if axis else float(np.median(center[valid]))
    return SilhouetteProfile(
        np.arange(image.width, dtype=np.float64),
        top,
        bottom,
        center,
        width,
        valid,
        axis_y,
    )


def _bounds_px(seed_range, width: int):
    if seed_range is None:
        return 0, width
    start, end = seed_range
    if 0 <= float(start) <= 1 and 0 <= float(end) <= 1:
        start, end = round(float(start) * width), round(float(end) * width)
    start = max(0, min(width - 2, int(start)))
    end = max(start + 2, min(width, int(end)))
    return start, end


def _first_sustained(values: np.ndarray, min_run: int):
    run = 0
    for index, value in enumerate(values):
        run = run + 1 if value else 0
        if run >= min_run:
            return index - run + 1
    return None


def detect_shaft_core(profile: SilhouetteProfile, seed_range=None, integrated: bool = False):
    start, end = _bounds_px(seed_range, len(profile.x))
    widths = profile.width[start:end]
    centers = profile.center[start:end]
    valid = profile.valid[start:end] & np.isfinite(widths) & (widths > 0)
    if valid.sum() < max(8, int((end - start) * 0.25)):
        return {
            "start": start,
            "end": end,
            "baselineWidth": 0.0,
            "centerBase": profile.axis_y,
            "confidence": 0.0,
            "stableMask": np.zeros(end - start, dtype=bool),
            "candidateRootStart": None,
        }

    n = end - start
    base_start = int(n * 0.10)
    base_end = max(base_start + 3, int(n * (0.65 if integrated else 0.80)))
    baseline_values = widths[base_start:base_end][valid[base_start:base_end]]
    if baseline_values.size < 4:
        baseline_values = widths[valid]
    baseline = float(np.median(baseline_values))
    center_base = float(np.median(centers[valid]))
    width_delta = np.abs(widths - baseline) / max(1.0, baseline)
    center_delta = np.abs(centers - center_base) / max(1.0, baseline)
    derivative = np.abs(np.gradient(widths)) / max(1.0, baseline)
    stable = valid & (width_delta <= 0.22) & (center_delta <= 0.13) & (derivative <= 0.13)

    kernel = max(3, min(9, (n // 20) * 2 + 1))
    stable = cv2.morphologyEx(
        stable.astype(np.uint8).reshape(1, -1) * 255,
        cv2.MORPH_CLOSE,
        np.ones((1, kernel), np.uint8),
    ).reshape(-1) > 0

    root_start = None
    if n >= 12:
        # Integrated systems may flare relatively early. Classic systems are much more
        # conservative: only a sustained late widening is treated as slot/root leakage.
        search_start = max(int(n * (0.45 if integrated else 0.68)), 2)
        width_threshold = 1.16 if integrated else 1.28
        derivative_threshold = 0.055 if integrated else 0.08
        relative_width = widths / max(1.0, baseline)
        signed_derivative = np.gradient(widths) / max(1.0, baseline)
        opening = valid & ((relative_width >= width_threshold) | (signed_derivative >= derivative_threshold))
        min_run = max(3, int(n * (0.055 if integrated else 0.075)))
        candidate = _first_sustained(opening[search_start:], min_run)
        if candidate is not None:
            index = search_start + candidate
            local_end = min(n, index + max(min_run * 2, 6))
            offset = np.nanmedian(np.abs(centers[index:local_end] - center_base))
            allowed_offset = max(2.0, baseline * (0.80 if integrated else 0.35))
            if offset <= allowed_offset:
                root_start = start + index

    core_end = root_start if root_start is not None else end
    core_stable = stable[:max(1, core_end - start)]
    stable_fraction = float(core_stable.mean()) if core_stable.size else 0.0
    confidence = float(np.clip((stable_fraction - 0.45) / 0.45, 0, 1))
    return {
        "start": start,
        "end": core_end,
        "baselineWidth": baseline,
        "centerBase": center_base,
        "confidence": confidence,
        "stableMask": stable,
        "candidateRootStart": root_start,
    }


def detect_rear_root(profile: SilhouetteProfile, shaft_core):
    start = shaft_core.get("candidateRootStart")
    if start is None:
        return None
    seed_start = int(shaft_core["start"])
    seed_end = seed_start + len(shaft_core["stableMask"])
    start = max(seed_start, min(seed_end - 1, int(start)))
    widths = profile.width[start:seed_end]
    centers = profile.center[start:seed_end]
    valid = profile.valid[start:seed_end]
    if valid.sum() < 3:
        return None
    baseline = max(1.0, float(shaft_core["baselineWidth"]))
    center_base = float(shaft_core.get("centerBase", profile.axis_y))
    signed_offset = float(np.median(centers[valid] - center_base))
    offset = abs(signed_offset)
    progression = float(
        (np.percentile(widths[valid], 80) - np.percentile(widths[valid], 20)) / baseline
    )
    growth = float(np.clip(progression / 0.45, 0, 1))
    axis_ok = float(np.clip(1.0 - offset / max(1.0, baseline * 0.30), 0, 1))
    return {
        "start": start,
        "end": seed_end,
        "axisOffset": offset,
        "axisOffsetSigned": signed_offset,
        "widthProgression": progression,
        "confidence": float(np.clip(growth * 0.65 + axis_ok * 0.35, 0, 1)),
    }


def _recenter_component_by_translation(image: Image.Image, signed_offset_px: float):
    offset=float(signed_offset_px or 0)
    if abs(offset)<0.5:
        return image,0.0
    extra=int(math.ceil(abs(offset)))+2
    canvas=Image.new("RGBA",(image.width,image.height+extra*2),(0,0,0,0))
    # One rigid translation only. No local warp/resampling of RGB pixels.
    paste_y=extra-int(round(offset))
    canvas.alpha_composite(image,(0,paste_y))
    return canvas,float(-offset)


def _remove_alpha_haze(arr: np.ndarray, strong_threshold: int = 180):
    out = arr.copy()
    alpha = out[:, :, 3]
    strong = alpha >= strong_threshold
    keep = np.zeros_like(strong)
    strong_pixels = int(strong.sum())
    outside_semi = 0
    for x in range(alpha.shape[1]):
        ys = np.flatnonzero(strong[:, x])
        if not ys.size:
            continue
        y0 = max(0, int(ys[0]) - 1)
        y1 = min(alpha.shape[0], int(ys[-1]) + 2)
        keep[y0:y1, x] = True
        outside_semi += int(((alpha[:, x] > 3) & (alpha[:, x] < strong_threshold) & ~keep[:, x]).sum())
    haze_ratio = outside_semi / max(1, strong_pixels)
    out[:, :, 3][(alpha > 0) & ~keep & (alpha < strong_threshold)] = 0
    return out, float(haze_ratio)


def extract_centered_component(
    image: Image.Image,
    bounds,
    axis_y: float | None = None,
    pad: int = 2,
):
    x0, x1 = _bounds_px(bounds, image.width)
    arr, haze_ratio = _remove_alpha_haze(_rgba(image))
    region = arr[:, x0:x1, 3]
    ys, xs = np.where(region > 3)
    if not xs.size:
        return Image.new("RGBA", (max(1, x1 - x0), 3), (0, 0, 0, 0)), haze_ratio
    axis = float(axis_y if axis_y is not None else (ys.min() + ys.max()) * 0.5)
    radius = int(math.ceil(max(abs(float(ys.min()) - axis), abs(float(ys.max()) - axis)))) + pad
    y0 = max(0, int(math.floor(axis - radius)))
    y1 = min(image.height, int(math.ceil(axis + radius + 1)))
    crop = Image.fromarray(arr[y0:y1, x0:x1], "RGBA")
    target_h = max(3, radius * 2 + 1)
    canvas = Image.new("RGBA", (crop.width, target_h), (0, 0, 0, 0))
    target_axis = (target_h - 1) * 0.5
    canvas.alpha_composite(crop, (0, int(round(target_axis - (axis - y0)))))
    return canvas, haze_ratio


def _profile_metrics(profile: SilhouetteProfile, start: int, end: int):
    start, end = max(0, int(start)), min(len(profile.x), int(end))
    valid = profile.valid[start:end]
    widths = profile.width[start:end][valid]
    centers = profile.center[start:end][valid]
    if widths.size < 2:
        return {"medianWidth": 1.0, "widthCV": 999.0, "residualP95": 999.0, "jumpMax": 999.0}
    median_width = float(np.median(widths))
    width_cv = float(1.4826 * np.median(np.abs(widths - median_width)) / max(1.0, median_width))
    residual = float(np.percentile(np.abs(centers - profile.axis_y), 95))
    jump = float(np.max(np.abs(np.diff(centers)))) if centers.size > 1 else 0.0
    return {
        "medianWidth": median_width,
        "widthCV": width_cv,
        "residualP95": residual,
        "jumpMax": jump,
    }


def measure_tail_quality(
    profile: SilhouetteProfile,
    axis: AxisAnalysis,
    shaft_core,
    rear_root=None,
    haze_ratio: float = 0.0,
    integrated: bool = False,
):
    metrics = _profile_metrics(profile, shaft_core["start"], shaft_core["end"])
    median_width = max(1.0, metrics["medianWidth"])
    start, end = int(shaft_core["start"]), int(shaft_core["end"])
    widths = profile.width[start:end][profile.valid[start:end]]
    root_leak = 1.0
    if widths.size >= 8:
        split = max(2, int(widths.size * 0.80))
        early = float(np.median(widths[:split]))
        late = float(np.median(widths[split:])) if widths[split:].size else early
        root_leak = late / max(1.0, early)

    root_offset = float(rear_root["axisOffset"]) if rear_root else None
    root_progression = float(rear_root["widthProgression"]) if rear_root else None
    root_confidence = float(rear_root["confidence"]) if rear_root else (1.0 if not integrated else 0.0)
    residual_norm = metrics["residualP95"] / median_width
    jump_norm = metrics["jumpMax"] / median_width

    status = PASS
    if abs(axis.angle_deg) > 6.0:
        status = FAIL_AXIS
    elif integrated and rear_root is None:
        status = NEEDS_MANUAL_REVIEW
    elif root_leak > 1.28:
        status = FAIL_ROOT_INCLUDED_IN_SHAFT
    elif root_offset is not None and root_offset / median_width > 0.20:
        status = FAIL_ROOT_ALIGNMENT
    elif axis.confidence < 0.45:
        status = FAIL_AXIS
    elif haze_ratio > 0.12:
        status = FAIL_ALPHA_HAZE
    elif residual_norm > 0.11 or jump_norm > 0.20 or metrics["widthCV"] > 0.18:
        status = NEEDS_MANUAL_REVIEW

    quality = 1.0
    quality -= min(0.32, residual_norm * 1.5)
    quality -= min(0.20, jump_norm * 0.7)
    quality -= min(0.18, max(0.0, metrics["widthCV"] - 0.06) * 1.2)
    quality -= min(0.15, max(0.0, haze_ratio - 0.01) * 1.1)
    if integrated:
        quality -= (1.0 - root_confidence) * 0.15
    quality = float(np.clip(quality, 0, 1))
    overall = float(np.clip(
        axis.confidence * 0.25
        + float(shaft_core["confidence"]) * 0.35
        + root_confidence * 0.15
        + quality * 0.25,
        0,
        1,
    ))
    if status == PASS and overall < 0.85:
        status = NEEDS_MANUAL_REVIEW
    if overall < 0.65 and status == NEEDS_MANUAL_REVIEW:
        status = FAIL_SOURCE_UNSUITABLE

    return TailAnalysis(
        axis.angle_deg,
        int(shaft_core["start"]),
        int(shaft_core["end"]),
        int(rear_root["start"]) if rear_root else None,
        int(rear_root["end"]) if rear_root else None,
        metrics["medianWidth"],
        metrics["widthCV"],
        metrics["residualP95"],
        metrics["jumpMax"],
        root_offset,
        root_progression,
        float(haze_ratio),
        float(root_leak),
        float(axis.confidence),
        float(shaft_core["confidence"]),
        root_confidence,
        overall,
        status,
    )


def author_tail_components(image: Image.Image, seed_range=None, integrated: bool = False):
    source = image.convert("RGBA")
    source_axis = analyze_axis(source)
    coarse = align_image_to_axis(source, source_axis)

    # Refine the global fit using the known tail seed, but only its front/stable part.
    # This prevents flight facets, infographic remnants and a rear flare from steering
    # the main dart axis.
    seed_start,seed_end=_bounds_px(seed_range,coarse.width)
    seed_span=max(2,seed_end-seed_start)
    fit_fraction=.64 if integrated else .72
    refine_range=(seed_start,seed_start+max(2,int(seed_span*fit_fraction)))
    refinement_axis=analyze_axis(coarse,refine_range)
    aligned=align_image_to_axis(coarse,refinement_axis,max_auto_angle_deg=4.0)

    final_seed_start,final_seed_end=_bounds_px(seed_range,aligned.width)
    final_span=max(2,final_seed_end-final_seed_start)
    final_fit_range=(
        final_seed_start,
        final_seed_start+max(2,int(final_span*fit_fraction)),
    )
    aligned_axis=analyze_axis(aligned,final_fit_range)
    profile = build_silhouette_profile(aligned, aligned_axis)
    shaft = detect_shaft_core(profile, seed_range=seed_range, integrated=integrated)
    root_candidate = detect_rear_root(profile, shaft)
    root = root_candidate if integrated else None

    shaft_image, shaft_haze = extract_centered_component(
        aligned, (shaft["start"], shaft["end"]), profile.axis_y
    )
    root_image, root_haze = None, 0.0
    root_translation=0.0
    root_source_offset=None
    root_for_quality=root
    if root:
        root_image, root_haze = extract_centered_component(
            aligned, (root["start"], root["end"]), profile.axis_y
        )
        root_source_offset=float(root.get("axisOffset",0))
        signed=float(root.get("axisOffsetSigned",0))
        ratio=root_source_offset/max(1.0,float(shaft.get("baselineWidth") or 1))
        # A modest photographic/perspective offset may be canonicalized by one rigid
        # translation of the whole root component. Large offsets remain a hard QA fail.
        if ratio <= .30:
            root_image,root_translation=_recenter_component_by_translation(root_image,signed)
            root_for_quality=dict(root)
            root_for_quality["axisOffset"]=0.0

    legacy_bounds = _bounds_px(seed_range, aligned.width)
    legacy_image, legacy_haze = extract_centered_component(aligned, legacy_bounds, profile.axis_y)
    haze = max(shaft_haze, root_haze, legacy_haze)
    analysis = measure_tail_quality(
        profile,
        aligned_axis,
        shaft,
        rear_root=root_for_quality,
        haze_ratio=haze,
        integrated=integrated,
    )
    return {
        "alignedImage": aligned,
        "axisSource": source_axis,
        "axisRefinement": refinement_axis,
        "axisAligned": aligned_axis,
        "profile": profile,
        "shaftCore": shaft_image,
        "rearRoot": root_image,
        "legacyTail": legacy_image,
        "analysis": analysis,
        "tailSegmentation": {
            "shaftCorePx": [int(shaft["start"]), int(shaft["end"])],
            "rearRootPx": [int(root["start"]), int(root["end"])] if root else None,
            "classicRootTrimPx": (
                [int(root_candidate["start"]), int(root_candidate["end"])]
                if root_candidate and not integrated else None
            ),
            "rootSourceAxisOffsetPx": (
                round(root_source_offset,4) if root_source_offset is not None else None
            ),
            "rootCanonicalTranslationYPx": round(root_translation,4),
            "method": "AXIS_WIDTH_PROFILE_V1",
            "confidence": round(float(analysis.confidence), 4),
        },
    }

