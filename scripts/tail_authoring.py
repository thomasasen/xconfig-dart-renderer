from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math
import numpy as np
import cv2
from PIL import Image, ImageFilter


@dataclass
class TailAnalysis:
    axis_angle_deg: float
    shaft_start_px: int
    shaft_end_px: int
    root_start_px: int | None
    root_end_px: int | None
    shaft_width_median_px: float
    shaft_width_cv: float
    shaft_center_residual_p95_px: float
    shaft_center_jump_max_px: float
    root_axis_offset_px: float | None
    haze_ratio: float
    confidence: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rgba(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA"))


def _primary_mask(image: Image.Image, alpha_threshold: int = 28) -> np.ndarray:
    arr = _rgba(image)
    binary = (arr[:, :, 3] >= alpha_threshold).astype(np.uint8)
    if not binary.any():
        return binary
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n <= 1:
        return binary
    # Keep all meaningful elongated/large components. Thin point pixels may be detached
    # after anti-aliasing, so do not blindly keep only the single largest component.
    areas = stats[1:, cv2.CC_STAT_AREA]
    max_area = max(1, int(areas.max()))
    keep = np.zeros_like(binary)
    for idx, area in enumerate(areas, start=1):
        x, y, w, h, _ = stats[idx]
        if area >= max(8, max_area * 0.006) or w >= binary.shape[1] * 0.08:
            keep[labels == idx] = 1
    return keep


def _median(values: np.ndarray, size: int = 7) -> np.ndarray:
    if len(values) == 0:
        return values
    k = max(3, int(size) | 1)
    radius = k // 2
    arr = np.asarray(values, dtype=np.float32).reshape(-1)
    padded = np.pad(arr, (radius, radius), mode='edge')
    windows = np.lib.stride_tricks.sliding_window_view(padded, k)
    return np.median(windows, axis=1).astype(np.float32)


def build_silhouette_profile(image: Image.Image, axis: dict[str, float] | None = None) -> dict[str, Any]:
    mask = _primary_mask(image)
    h, w = mask.shape
    top = np.full(w, np.nan, dtype=np.float32)
    bottom = np.full(w, np.nan, dtype=np.float32)
    for x in range(w):
        ys = np.flatnonzero(mask[:, x])
        if len(ys):
            top[x] = float(ys.min())
            bottom[x] = float(ys.max())
    center = (top + bottom) * 0.5
    width = bottom - top + 1.0
    valid = np.isfinite(center)
    if valid.any():
        # Interpolate small alpha gaps before robust filtering.
        xs = np.arange(w, dtype=np.float32)
        center = np.interp(xs, xs[valid], center[valid]).astype(np.float32)
        width = np.interp(xs, xs[valid], width[valid]).astype(np.float32)
        center = _median(center, 7)
        width = _median(width, 7)
    return {
        "top": top,
        "bottom": bottom,
        "center": center,
        "width": width,
        "valid": valid,
        "mask": mask,
        "axis": axis,
    }


def analyze_axis(image: Image.Image) -> dict[str, float]:
    profile = build_silhouette_profile(image)
    center = profile["center"]
    width = profile["width"]
    valid = np.isfinite(center) & np.isfinite(width)
    if valid.sum() < 12:
        return {"angleDeg": 0.0, "interceptPx": image.height / 2, "fitResidualPxP95": 999.0, "confidence": 0.0}

    x = np.arange(len(center), dtype=np.float64)
    # Prefer long/narrow body columns; broad flight columns otherwise dominate a PCA fit.
    vv = width[valid]
    narrow_limit = float(np.percentile(vv, 58))
    body = valid & (width <= narrow_limit * 1.35)
    # Bias away from the final 20%, which is commonly flight-dominated.
    body &= x <= (len(center) - 1) * 0.82
    if body.sum() < 12:
        body = valid & (x <= (len(center) - 1) * 0.78)
    if body.sum() < 12:
        body = valid

    xb = x[body]
    yb = center[body].astype(np.float64)
    slope, intercept = np.polyfit(xb, yb, 1)
    # Two robust trimming passes approximating RANSAC without adding another dependency.
    for _ in range(2):
        residual = yb - (slope * xb + intercept)
        limit = max(1.0, float(np.percentile(np.abs(residual), 82)))
        keep = np.abs(residual) <= limit
        if keep.sum() < 8:
            break
        slope, intercept = np.polyfit(xb[keep], yb[keep], 1)
        xb, yb = xb[keep], yb[keep]

    all_residual = center[body] - (slope * x[body] + intercept)
    p95 = float(np.percentile(np.abs(all_residual), 95)) if len(all_residual) else 999.0
    med_width = max(1.0, float(np.median(width[body])))
    confidence = float(np.clip(1.0 - p95 / max(2.0, med_width * 0.45), 0.0, 1.0))
    return {
        "angleDeg": float(math.degrees(math.atan(slope))),
        "slope": float(slope),
        "interceptPx": float(intercept),
        "fitResidualPxP95": p95,
        "confidence": confidence,
    }


def normalize_axis(image: Image.Image, axis: dict[str, float] | None = None) -> tuple[Image.Image, dict[str, float]]:
    axis = axis or analyze_axis(image)
    angle = float(axis.get("angleDeg", 0.0))
    if abs(angle) < 0.03:
        return image.convert("RGBA"), axis
    # PIL positive angle rotates counter-clockwise; an image-space positive slope therefore
    # needs a positive correction to level the dart axis.
    rotated = image.convert("RGBA").rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    return rotated, analyze_axis(rotated)


def detect_shaft_core(profile: dict[str, Any], seed_range: tuple[int, int] | None = None) -> tuple[int, int, dict[str, float]]:
    width = np.asarray(profile["width"], dtype=np.float64)
    center = np.asarray(profile["center"], dtype=np.float64)
    n = len(width)
    if seed_range is None:
        seed_range = (int(n * 0.55), int(n * 0.77))
    s0 = max(0, min(n - 2, int(seed_range[0])))
    s1 = max(s0 + 2, min(n, int(seed_range[1])))
    segment = width[s0:s1]
    finite = np.isfinite(segment)
    if finite.sum() < 6:
        return s0, s1, {"confidence": 0.0}

    base_width = max(1.0, float(np.percentile(segment[finite], 42)))
    axis_center = float(np.median(center[s0:s1][np.isfinite(center[s0:s1])]))
    stable = (
        np.isfinite(width)
        & np.isfinite(center)
        & (width >= base_width * 0.68)
        & (width <= base_width * 1.32)
        & (np.abs(center - axis_center) <= max(2.0, base_width * 0.16))
    )

    # Search the largest stable run that intersects the legacy seed. Morphological closing
    # suppresses one/two-column anti-aliasing gaps.
    stable_u8 = stable.astype(np.uint8).reshape(1, -1)
    stable_u8 = cv2.morphologyEx(stable_u8, cv2.MORPH_CLOSE, np.ones((1, 5), np.uint8)).reshape(-1)
    best = (s0, s1, 0)
    start = None
    for i, value in enumerate(np.r_[stable_u8, 0]):
        if value and start is None:
            start = i
        elif not value and start is not None:
            end = i
            overlap = max(0, min(end, s1) - max(start, s0))
            score = (end - start) + overlap * 2
            if overlap > 0 and score > best[2]:
                best = (start, end, score)
            start = None
    c0, c1, _ = best
    # A seed is a physical prior from the current catalog split. Never let a stable
    # barrel run pull the shaft core forward across the known barrel/shaft boundary.
    c0 = max(c0, s0)
    # Never consume beyond the known flight boundary.
    c1 = min(c1, s1)
    values = width[c0:c1]
    cv = float(np.std(values) / max(1e-6, np.median(values))) if len(values) else 999.0
    residual = np.abs(center[c0:c1] - np.median(center[c0:c1])) if c1 > c0 else np.array([999.0])
    residual95 = float(np.percentile(residual, 95))
    # The plan's nominal acceptable core is CV<=0.12 and center residual<=8% width.
    # Treat values inside that envelope as high confidence instead of penalising them
    # linearly from zero, which incorrectly made good real shafts score ~0.4.
    width_conf = 1.0 if cv <= .12 else float(np.clip(1.0 - (cv-.12)/.10, 0, 1))
    center_ratio = residual95 / max(1.0, base_width)
    center_conf = 1.0 if center_ratio <= .08 else float(np.clip(1.0 - (center_ratio-.08)/.14, 0, 1))
    length_conf = float(np.clip((c1-c0) / max(8.0, (s1-s0)*.55), 0, 1))
    confidence = float(width_conf * center_conf * (.85 + .15*length_conf))
    return int(c0), int(c1), {"confidence": confidence, "baseWidthPx": base_width, "widthCV": cv, "centerResidualRatio": center_ratio}


def detect_rear_root(
    profile: dict[str, Any],
    shaft_core: tuple[int, int],
    flight_start_px: int | None = None,
) -> tuple[int | None, int | None, dict[str, float]]:
    width = np.asarray(profile["width"], dtype=np.float64)
    center = np.asarray(profile["center"], dtype=np.float64)
    c0, c1 = shaft_core
    if c1 - c0 < 4:
        return None, None, {"confidence": 0.0}
    limit = min(len(width), int(flight_start_px) if flight_start_px is not None else len(width))
    # Estimate the true shaft diameter from the front/middle of the legacy tail seed;
    # the last part may already contain the molded K-Flex/K-Shift root.
    core_len=max(1,c1-c0)
    baseline_end=max(c0+3,min(c1,c0+int(round(core_len*.62))))
    baseline=width[c0:baseline_end]
    baseline=baseline[np.isfinite(baseline)]
    base=max(1.0,float(np.median(baseline))) if len(baseline) else max(1.0,float(np.nanmedian(width[c0:c1])))
    # Search the rear half of the candidate tail, not merely the final 3 pixels.
    # This is what allows a source-grounded root flare to be separated before flight.
    search0=max(c0+3,c0+int(round(core_len*.45)))
    if limit - search0 < 3:
        return None, None, {"confidence": 0.0, "baseWidthPx": base}

    smooth = _median(np.nan_to_num(width, nan=base), 7)
    threshold = base * 1.10
    root_start = None
    run = 0
    for x in range(search0, limit):
        widening = smooth[x] >= threshold
        if widening:
            run += 1
            if run >= 3:
                root_start = x - run + 1
                break
        else:
            run = 0
    if root_start is None:
        return None, None, {"confidence": 0.25, "baseWidthPx": base}

    root_end = limit
    shaft_axis = float(np.median(center[c0:c1]))
    root_center = center[root_start:root_end]
    root_center = root_center[np.isfinite(root_center)]
    axis_offset = abs(float(np.median(root_center)) - shaft_axis) if len(root_center) else 999.0
    growth = float(np.median(smooth[max(root_start, root_end - max(3, (root_end-root_start)//3)):root_end]) / base)
    growth_conf = 1.0 if growth >= 1.14 else float(np.clip((growth-1.06)/.08,0,1))
    offset_ratio = axis_offset / max(1.0, base)
    offset_conf = 1.0 if offset_ratio <= .08 else float(np.clip(1.0-(offset_ratio-.08)/.20,0,1))
    length_conf = float(np.clip((root_end-root_start)/max(3.0,(limit-search0)*.22),0,1))
    confidence = float(growth_conf * offset_conf * (.85+.15*length_conf))
    return int(root_start), int(root_end), {
        "confidence": confidence,
        "baseWidthPx": base,
        "growthRatio": growth,
        "axisOffsetPx": axis_offset,
    }


def extract_centered_component(
    image: Image.Image,
    bounds: tuple[int, int],
    axis: dict[str, float] | None = None,
    alpha_threshold: int = 4,
) -> Image.Image:
    rgba = image.convert("RGBA")
    x0, x1 = max(0, int(bounds[0])), min(rgba.width, int(bounds[1]))
    crop = rgba.crop((x0, 0, max(x0 + 1, x1), rgba.height))
    arr = np.asarray(crop)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > alpha_threshold)
    if not len(xs):
        return crop
    cy = float(np.median((ys.min() + ys.max()) * .5))
    fitted = axis or analyze_axis(rgba)
    global_mid_x = (x0 + x1 - 1) * .5
    axis_y = float(fitted.get("slope", 0.0)) * global_mid_x + float(fitted.get("interceptPx", cy))
    half = int(math.ceil(max(axis_y - ys.min(), ys.max() - axis_y))) + 2
    y0 = max(0, int(round(axis_y)) - half)
    y1 = min(rgba.height, int(round(axis_y)) + half + 1)
    centered = rgba.crop((x0, y0, max(x0 + 1, x1), y1))
    # Suppress only very weak alpha haze; retain real anti-aliased edges.
    data = np.asarray(centered).copy()
    a = data[:, :, 3]
    a = np.where(a < 10, 0, a).astype(np.uint8)
    data[:, :, 3] = a
    return Image.fromarray(data, "RGBA")


def extract_axial_root_component(
    image: Image.Image,
    bounds: tuple[int, int],
    axis: dict[str, float],
    alpha_threshold: int = 10,
) -> Image.Image:
    """Keep only source pixels that have an axial counterpart around the shaft axis.

    Integrated product photos often contain the first one-sided flight fin inside the
    legacy rear crop. Those pixels are flight, not physical root. They are removed by
    silhouette classification only; RGB pixels that remain are never moved or repainted.
    """
    rgba=image.convert("RGBA")
    x0,x1=max(0,int(bounds[0])),min(rgba.width,int(bounds[1]))
    crop=np.asarray(rgba.crop((x0,0,max(x0+1,x1),rgba.height))).copy()
    alpha=crop[:,:,3]
    h,w=alpha.shape
    cleaned=np.zeros_like(alpha)
    slope=float(axis.get("slope",0.0))
    intercept=float(axis.get("interceptPx",rgba.height/2))
    for lx in range(w):
        gx=x0+lx
        ay=slope*gx+intercept
        ys=np.flatnonzero(alpha[:,lx] >= alpha_threshold)
        if not len(ys):
            continue
        top=float(ys.min()); bottom=float(ys.max())
        upper=max(0.0,ay-top); lower=max(0.0,bottom-ay)
        # Source-grounded axial root must exist on both sides of the axis.
        radius=min(upper,lower)
        if radius < 1.0:
            continue
        ylo=max(0,int(math.ceil(ay-radius)))
        yhi=min(h,int(math.floor(ay+radius))+1)
        cleaned[ylo:yhi,lx]=alpha[ylo:yhi,lx]
    crop[:,:,3]=cleaned
    out=Image.fromarray(crop,"RGBA")
    bbox=out.getbbox()
    return out.crop(bbox) if bbox else out


def _component_axis_offset(image: Image.Image) -> float | None:
    arr=_rgba(image)
    alpha=arr[:,:,3]
    centers=[]
    for x in range(alpha.shape[1]):
        ys=np.flatnonzero(alpha[:,x] >= 18)
        if len(ys):
            centers.append((float(ys.min())+float(ys.max()))*.5)
    if not centers:
        return None
    center=float(np.median(centers))
    return abs(center-(image.height-1)*.5)


def measure_tail_quality(
    image: Image.Image,
    profile: dict[str, Any],
    shaft_core: tuple[int, int],
    root: tuple[int | None, int | None] = (None, None),
    axis: dict[str, float] | None = None,
    canonical_root_axis_offset_px: float | None = None,
) -> dict[str, float | str | None]:
    axis = axis or analyze_axis(image)
    width = np.asarray(profile["width"], dtype=np.float64)
    center = np.asarray(profile["center"], dtype=np.float64)
    c0, c1 = shaft_core
    sw = width[c0:c1]
    sc = center[c0:c1]
    sw = sw[np.isfinite(sw)]
    sc = sc[np.isfinite(sc)]
    medw = max(1.0, float(np.median(sw))) if len(sw) else 1.0
    shaft_cv = float(np.std(sw) / medw) if len(sw) else 999.0
    expected = float(axis.get("slope", 0.0)) * np.arange(c0, c1) + float(axis.get("interceptPx", image.height / 2))
    valid = np.isfinite(center[c0:c1])
    residual = np.abs(center[c0:c1][valid] - expected[valid])
    residual_p95 = float(np.percentile(residual, 95)) if len(residual) else 999.0
    smooth_center = _median(np.nan_to_num(center[c0:c1], nan=np.nanmedian(sc) if len(sc) else 0), 5)
    jumps = np.abs(np.diff(smooth_center))
    jump = float(jumps.max()) if len(jumps) else 0.0

    r0, r1 = root
    root_offset = None
    raw_root_offset = None
    if r0 is not None and r1 is not None and r1 > r0:
        rc = center[r0:r1]
        rc = rc[np.isfinite(rc)]
        if len(rc):
            raw_root_offset = abs(float(np.median(rc)) - float(np.median(sc)))
            root_offset = raw_root_offset
    if canonical_root_axis_offset_px is not None:
        root_offset = float(canonical_root_axis_offset_px)

    rgba = _rgba(image)
    alpha = rgba[:, :, 3]
    primary = _primary_mask(image)
    semi = ((alpha >= 8) & (alpha < 72) & (primary == 0)).sum()
    haze = float(semi / max(1, int(primary.sum())))

    leak = False
    if c1 - c0 >= 10:
        tail_n = max(3, int(round((c1 - c0) * .18)))
        first = np.nanmedian(width[c0:max(c0 + 1, c1 - tail_n)])
        last = np.nanmedian(width[c1 - tail_n:c1])
        leak = bool(last > max(1.0, first) * 1.22)

    status = "PASS"
    if residual_p95 > medw * .08:
        status = "FAIL_AXIS"
    elif leak:
        status = "FAIL_ROOT_INCLUDED_IN_SHAFT"
    elif root_offset is not None and root_offset > medw * .12:
        status = "FAIL_ROOT_ALIGNMENT"
    elif haze > .08:
        status = "FAIL_ALPHA_HAZE"

    return {
        "shaftAxisResidual": residual_p95,
        "shaftCenterJump": jump / medw,
        "shaftWidthCV": shaft_cv,
        "rootAxisOffset": root_offset,
        "rootRawAxisOffset": raw_root_offset,
        "tailAlphaHaze": haze,
        "rootLeakIntoShaft": leak,
        "medianShaftWidthPx": medw,
        "status": status,
    }


def author_tail_components(
    image: Image.Image,
    *,
    shaft_seed_range: tuple[int, int],
    flight_start_px: int,
    integrated: bool,
) -> dict[str, Any]:
    axis0 = analyze_axis(image)
    normalized, axis = normalize_axis(image, axis0)
    # Map legacy seed fractions when rotation expansion changes width.
    scale = normalized.width / max(1, image.width)
    seed = (
        int(round(shaft_seed_range[0] * scale)),
        int(round(shaft_seed_range[1] * scale)),
    )
    flight_start = int(round(flight_start_px * scale))
    profile = build_silhouette_profile(normalized, axis)
    c0, c1, core_info = detect_shaft_core(profile, seed)
    r0 = r1 = None
    root_info = {"confidence": 1.0 if not integrated else 0.0}
    if integrated:
        r0, r1, root_info = detect_rear_root(profile, (c0, c1), flight_start)
        if r0 is not None:
            c1 = min(c1, r0)
    shaft = extract_centered_component(normalized, (c0, c1), axis)
    root = extract_axial_root_component(normalized, (r0, r1), axis) if r0 is not None and r1 is not None else None
    canonical_root_offset = _component_axis_offset(root) if root is not None else None
    metrics = measure_tail_quality(
        normalized,
        profile,
        (c0, c1),
        (r0, r1),
        axis,
        canonical_root_axis_offset_px=canonical_root_offset,
    )
    effective_root_conf=float(root_info.get("confidence",0.0)) if integrated else 1.0
    if integrated and root is not None and canonical_root_offset is not None:
        # A one-sided photographed fin can make the raw root silhouette look off-axis.
        # After that fin is classified out, confidence follows the canonical axial root.
        med_for_root=max(1.0,float(metrics.get("medianShaftWidthPx",1.0)))
        canonical_ratio=float(canonical_root_offset)/med_for_root
        growth=float(root_info.get("growthRatio",1.0))
        if canonical_ratio <= .08 and growth >= 1.10:
            effective_root_conf=max(effective_root_conf,.90)
    confidence = float(np.mean([
        float(axis.get("confidence", 0.0)),
        float(core_info.get("confidence", 0.0)),
        effective_root_conf,
    ]))
    if metrics["status"] != "PASS":
        status = str(metrics["status"])
    elif integrated and r0 is None:
        # An integrated source can provide a geometrically excellent shaft core while
        # the molded root is hidden by a transparent/photographed flight. Do not turn
        # missing root evidence into invented geometry, but also do not reject an
        # objectively stable shaft merely because the heuristic confidence score is
        # depressed by source contrast. Hard geometry metrics above remain mandatory.
        med=max(1.0,float(metrics.get("medianShaftWidthPx",1.0)))
        shaft_objectively_stable=(
            float(metrics.get("shaftAxisResidual",999.0)) <= med*.08
            and float(metrics.get("shaftWidthCV",999.0)) <= .18
            and float(metrics.get("shaftCenterJump",999.0)) <= .25
            and float(metrics.get("tailAlphaHaze",999.0)) <= .10
            and float(core_info.get("confidence",0.0)) >= .50
            and float(axis.get("confidence",0.0)) >= .35
        )
        status = "NEEDS_MANUAL_REVIEW" if shaft_objectively_stable else "FAIL_SOURCE_UNSUITABLE"
    elif confidence >= .85:
        status = "PASS"
    elif confidence >= .65:
        status = "NEEDS_MANUAL_REVIEW"
    else:
        status = "FAIL_SOURCE_UNSUITABLE"

    return {
        "normalizedImage": normalized,
        "shaftCoreImage": shaft,
        "rearRootImage": root,
        "analysis": TailAnalysis(
            axis_angle_deg=float(axis0.get("angleDeg", 0.0)),
            shaft_start_px=int(c0),
            shaft_end_px=int(c1),
            root_start_px=int(r0) if r0 is not None else None,
            root_end_px=int(r1) if r1 is not None else None,
            shaft_width_median_px=float(metrics["medianShaftWidthPx"]),
            shaft_width_cv=float(metrics["shaftWidthCV"]),
            shaft_center_residual_p95_px=float(metrics["shaftAxisResidual"]),
            shaft_center_jump_max_px=float(metrics["shaftCenterJump"]) * float(metrics["medianShaftWidthPx"]),
            root_axis_offset_px=float(metrics["rootAxisOffset"]) if metrics["rootAxisOffset"] is not None else None,
            haze_ratio=float(metrics["tailAlphaHaze"]),
            confidence=confidence,
            status=status,
        ),
        "axisAuthoring": {
            "angleDeg": float(axis0.get("angleDeg", 0.0)),
            "fitResidualPxP95": float(axis0.get("fitResidualPxP95", 999.0)),
            "confidence": float(axis0.get("confidence", 0.0)),
        },
        "tailSegmentation": {
            "shaftCore": [int(c0), int(c1)],
            "rearRoot": [int(r0), int(r1)] if r0 is not None and r1 is not None else None,
            "rootGrowthRatio": float(root_info.get("growthRatio", 1.0)) if integrated else None,
            "rootAxisOffsetPx": float(metrics.get("rootAxisOffset")) if integrated and metrics.get("rootAxisOffset") is not None else None,
            "rootRawAxisOffsetPx": float(metrics.get("rootRawAxisOffset")) if integrated and metrics.get("rootRawAxisOffset") is not None else None,
            "method": "AXIS_WIDTH_PROFILE_V1",
            "confidence": confidence,
        },
        "tailMetrics": metrics,
    }
