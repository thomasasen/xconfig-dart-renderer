from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import cv2
from PIL import Image

from flight_backface import build_backface_approximation


@dataclass
class HalfFinAuthoring:
    top: Image.Image
    bottom: Image.Image
    top_back: Image.Image
    bottom_back: Image.Image
    metadata: dict


def _trim_alpha(image: Image.Image, threshold: int = 3) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"))
    ys, xs = np.where(alpha > threshold)
    if not len(xs):
        return rgba
    return rgba.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def _dominant_material_rgb(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    visible = arr[:, :, 3] > 48
    if not np.any(visible):
        return np.array([128.0, 128.0, 128.0], dtype=np.float32)
    rgb = arr[:, :, :3][visible]
    # Coarse histogram: substrate normally occupies much more area than print/logo detail.
    q = (rgb // 32).astype(np.int32)
    keys = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    counts = np.bincount(keys, minlength=512)
    winner = int(np.argmax(counts))
    sample = rgb[keys == winner]
    return np.median(sample.astype(np.float32), axis=0) if len(sample) else np.median(rgb.astype(np.float32), axis=0)


def _material_only_backface(
    image: Image.Image,
    material_alpha: float | None = None,
) -> Image.Image:
    """Create a deliberately detail-free reverse surface for an authored half-fin.

    Reverse RGB and reverse alpha must both be free of source artwork. The raw source
    silhouette is retained, but printed logos/text are not allowed to become opacity
    variation because that would still reveal mirrored artwork after RGB neutralisation.
    """
    base = image.convert("RGBA")
    arr = np.asarray(base, dtype=np.uint8).copy()
    material = _dominant_material_rgb(base) * 0.92
    arr[:, :, :3] = np.clip(material[None, None, :], 0, 255).astype(np.uint8)
    if material_alpha is not None:
        coverage = arr[:, :, 3] > 8
        arr[:, :, 3] = np.where(
            coverage,
            np.clip(float(material_alpha) * 255.0, 0, 255),
            0,
        ).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _apply_material_alpha(image: Image.Image, material_alpha: float | None) -> Image.Image:
    """Approximate translucent moulded plastic from a catalogue image on white.

    RGB stays source-derived. Only alpha is reconstructed, and the result must therefore
    be labelled APPROXIMATED-ALPHA. Pixels that differ strongly from the dominant
    substrate colour are treated as printed artwork and remain more opaque.
    """
    if material_alpha is None:
        return image.convert("RGBA")
    base = image.convert("RGBA")
    arr = np.asarray(base, dtype=np.uint8).copy()
    source_alpha = arr[:, :, 3].astype(np.float32) / 255.0
    material = _dominant_material_rgb(base)
    dist = np.linalg.norm(arr[:, :, :3].astype(np.float32) - material[None, None, :], axis=2)
    artwork = np.clip((dist - 28.0) / 62.0, 0.0, 1.0)
    target = float(material_alpha) * (1.0 - artwork) + 0.96 * artwork

    source_rgb = arr[:, :, :3].astype(np.float32)
    visible = (arr[:, :, 3] > 8).astype(np.uint8)

    # Remove studio-white contamination only near the canonical material boundary.
    # Inpainting borrows neighbouring source colour instead of painting the edge with a
    # single flat colour, so gradients and real printed detail survive.
    distance = cv2.distanceTransform(visible, cv2.DIST_L2, 3)
    ring_width = max(3.0, min(10.0, round(min(arr.shape[:2]) * 0.055)))
    channel_spread = source_rgb.max(axis=2) - source_rgb.min(axis=2)
    near_white = (source_rgb.min(axis=2) > 188.0) & (channel_spread < 70.0)
    matte_mask = ((visible > 0) & (distance <= ring_width) & near_white).astype(np.uint8)
    cleaned_rgb = source_rgb
    if np.any(matte_mask):
        cleaned_rgb = cv2.inpaint(
            np.clip(source_rgb, 0, 255).astype(np.uint8),
            matte_mask * 255,
            3.0,
            cv2.INPAINT_TELEA,
        ).astype(np.float32)

    # Material opacity is independent from geometry coverage. Recover an approximate
    # foreground colour from the known white catalogue backdrop, then retain a small
    # observed-colour contribution to avoid over-correcting compression noise.
    target = np.where(visible > 0, target, 0.0).astype(np.float32)
    recovered_rgb = _recover_from_white_backdrop(cleaned_rgb, np.maximum(target, 0.08))
    cleaned_rgb = np.where(
        visible[:, :, None] > 0,
        recovered_rgb,
        0.0,
    )
    arr[:, :, :3] = np.clip(cleaned_rgb, 0, 255).astype(np.uint8)

    # Geometry clips the fin silhouette. Alpha now means material/print opacity only.
    arr[:, :, 3] = np.clip(target * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _canonical_radial_envelope(profile, width: int) -> np.ndarray:
    """Return positive radial extent r(u) in canonical fin coordinates.

    Geometry owns silhouette coverage. The texture only carries appearance, so source
    pixels are resampled into this canonical radial coordinate instead of preserving the
    photographed silhouette as alpha.
    """
    if not profile or width < 1:
        return np.ones(max(1, width), dtype=np.float32)

    pts = []
    for point in profile:
        try:
            x, y = float(point[0]), float(point[1])
        except Exception:
            continue
        if np.isfinite(x) and np.isfinite(y):
            pts.append((x, y))
    if len(pts) < 3:
        return np.ones(width, dtype=np.float32)

    envelope = np.zeros(width, dtype=np.float32)
    for ox in range(width):
        u = ox / max(1, width - 1)
        values = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            x0, y0 = a
            x1, y1 = b
            lo, hi = min(x0, x1), max(x0, x1)
            if u < lo - 1e-8 or u > hi + 1e-8:
                continue
            dx = x1 - x0
            if abs(dx) < 1e-8:
                if abs(u - x0) < 1e-6:
                    values.extend([y0, y1])
                continue
            t = (u - x0) / dx
            if -1e-6 <= t <= 1 + 1e-6:
                values.append(y0 + (y1 - y0) * t)
        positive = [y for y in values if y >= -1e-6]
        envelope[ox] = max(0.0, min(1.0, max(positive) if positive else 0.0))

    # Avoid isolated zero columns from vertex/vertical-edge numerical ambiguity.
    if width >= 3:
        padded = np.pad(envelope, (1, 1), mode="edge")
        envelope = np.maximum.reduce([padded[:-2], padded[1:-1], padded[2:]])
    return envelope.astype(np.float32)


def _recover_from_white_backdrop(rgb: np.ndarray, opacity: np.ndarray) -> np.ndarray:
    """Approximate foreground colour from a white-backed catalogue photograph."""
    a = np.clip(opacity.astype(np.float32), 0.08, 1.0)[:, :, None]
    recovered = (rgb.astype(np.float32) - 255.0 * (1.0 - a)) / a
    recovered = np.clip(recovered, 0, 255)
    # Keep a little observed colour to avoid over-saturating JPEG/product-photo noise.
    return recovered * 0.72 + rgb.astype(np.float32) * 0.28


def _column_bounds(alpha: np.ndarray, threshold: int = 12):
    bounds = []
    spans = []
    for x in range(alpha.shape[1]):
        ys = np.where(alpha[:, x] > threshold)[0]
        if len(ys):
            y0, y1 = int(ys.min()), int(ys.max())
            bounds.append((y0, y1))
            spans.append(y1 - y0 + 1)
        else:
            bounds.append(None)
            spans.append(0)
    return bounds, spans


def _rectify_half(
    rgba: np.ndarray,
    bounds,
    face_start: int,
    face_end: int,
    band: int,
    which: str,
    *,
    canonical_envelope: np.ndarray | None = None,
    source_outer_trim_fraction: float = 0.12,
    source_tail_trim_fraction: float = 0.025,
) -> Image.Image:
    width = max(2, face_end - face_start + 1)
    local_spans = []
    local_centres = []
    for x in range(face_start, face_end + 1):
        b = bounds[x]
        if not b:
            continue
        y0, y1 = b
        local_spans.append(y1 - y0 + 1)
        local_centres.append((y0 + y1) * 0.5)
    if not local_spans:
        return Image.new("RGBA", (width, 64), (0, 0, 0, 0))

    max_span = max(local_spans)
    out_h = max(128, min(320, int(round(max_span * 1.15))))
    map_x = np.zeros((out_h, width), dtype=np.float32)
    map_y = np.zeros((out_h, width), dtype=np.float32)
    valid = np.zeros((out_h, width), dtype=np.uint8)
    envelope = (
        np.asarray(canonical_envelope, dtype=np.float32)
        if canonical_envelope is not None
        else np.ones(width, dtype=np.float32)
    )
    if envelope.shape[0] != width:
        raise ValueError("canonical flight envelope width mismatch")

    source_width = max(2, face_end - face_start + 1)
    tail_trim = max(1, int(round(source_width * float(source_tail_trim_fraction))))
    source_end = max(face_start + 1, face_end - tail_trim)
    source_x_positions = np.linspace(face_start, source_end, width, dtype=np.float32)

    for ox, sx_float in enumerate(source_x_positions):
        sx_index = int(np.clip(round(float(sx_float)), 0, len(bounds) - 1))
        b = bounds[sx_index]
        if not b:
            continue
        y0, y1 = b
        centre = (y0 + y1) * 0.5
        radial = float(np.clip(envelope[ox], 0.0, 1.0))
        if radial <= 1e-4:
            continue

        if which == "top":
            source_outer = float(y0)
            axis = float(centre - band)
            source_span = axis - source_outer
            if source_span < 2:
                continue
            # Product-photo silhouettes carry the strongest white-matte/AA pollution at
            # their outer edge. Inset that uncertain source band and stretch reliable
            # interior appearance to the canonical geometric boundary.
            outer_trim = min(14.0, max(1.0, source_span * float(source_outer_trim_fraction)))
            outer = min(axis - 1.0, source_outer + outer_trim)
            # Global canonical V: v=1 at axis and v=0 at maximum radius.
            t0 = int(round((1.0 - radial) * (out_h - 1)))
            t1 = out_h - 1
            count = max(1, t1 - t0 + 1)
            map_x[t0:t1 + 1, ox] = float(sx_float)
            map_y[t0:t1 + 1, ox] = np.linspace(outer, axis, count, dtype=np.float32)
            valid[t0:t1 + 1, ox] = 255
        else:
            axis = float(centre + band)
            source_outer = float(y1)
            source_span = source_outer - axis
            if source_span < 2:
                continue
            outer_trim = min(14.0, max(1.0, source_span * float(source_outer_trim_fraction)))
            outer = max(axis + 1.0, source_outer - outer_trim)
            # Global canonical V: v=0 at axis and v=1 at maximum radius.
            t0 = 0
            t1 = int(round(radial * (out_h - 1)))
            count = max(1, t1 - t0 + 1)
            map_x[t0:t1 + 1, ox] = float(sx_float)
            map_y[t0:t1 + 1, ox] = np.linspace(axis, outer, count, dtype=np.float32)
            valid[t0:t1 + 1, ox] = 255

    sampled = cv2.remap(
        rgba,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    # Source alpha is a segmentation aid only. Canonical geometry now owns coverage.
    # Every mapped texel is valid material; opacity is authored separately below.
    sampled[:, :, 3] = valid
    return Image.fromarray(sampled, "RGBA")


def author_visible_half_fins(
    composite: Image.Image,
    *,
    material_alpha: float | None = None,
    source_label: str = "source",
    canonical_profile=None,
) -> HalfFinAuthoring:
    """Split a photographed integrated flight into the two actually visible fin faces.

    The input is expected to be a horizontal dart crop with the shaft/flight axis running
    left-to-right. We do not mirror either source face. Each visible half is rectified
    independently along radial strips. The two unseen opposite fins and every reverse
    surface remain approximated by the caller/renderer.
    """
    base = _trim_alpha(composite.convert("RGBA"), 3)
    rgba = np.asarray(base, dtype=np.uint8)
    alpha = rgba[:, :, 3]
    bounds, spans = _column_bounds(alpha)
    max_span = max(spans) if spans else 0
    if max_span < 12:
        raise ValueError("flight composite is too small for half-fin authoring")

    broad_threshold = max(8, int(round(max_span * 0.30)))
    broad = [x for x, span in enumerate(spans) if span >= broad_threshold]
    if len(broad) < 5:
        raise ValueError("no dominant broad flight face detected")
    face_start, face_end = min(broad), max(broad)

    centres = [
        (bounds[x][0] + bounds[x][1]) * 0.5
        for x in broad
        if bounds[x] is not None
    ]
    centre = float(np.median(centres)) if centres else base.height * 0.5
    band = max(1, int(round(max_span * 0.025)))

    canonical_envelope = _canonical_radial_envelope(
        canonical_profile,
        max(2, face_end - face_start + 1),
    )
    top_source = _rectify_half(
        rgba, bounds, face_start, face_end, band, "top",
        canonical_envelope=canonical_envelope,
    )
    bottom_source = _rectify_half(
        rgba, bounds, face_start, face_end, band, "bottom",
        canonical_envelope=canonical_envelope,
    )
    top = _apply_material_alpha(top_source, material_alpha)
    bottom = _apply_material_alpha(bottom_source, material_alpha)

    # Reverse faces derive from the unmodulated source silhouette, not from the
    # artwork-aware front alpha. This prevents text/logo shapes leaking through opacity.
    top_back = _material_only_backface(top_source, material_alpha)
    bottom_back = _material_only_backface(bottom_source, material_alpha)

    metadata = {
        "mode": "REFERENCE_PLANE_SOURCE_SAMPLES",
        "sourceLabel": source_label,
        "geometryModel": "FOUR_RADIAL_FINS_0_90_180_270",
        "geometryInferenceFromPhoto": False,
        "sourceAppearanceSampleCount": 2,
        "referencePlane": "A",
        "referenceRollDeg": 0,
        "referencePlaneCalibration": "PLAUSIBLE_BROADSIDE_NOT_EXACT_RECONSTRUCTION",
        "faceStartPx": int(face_start),
        "faceEndPx": int(face_end),
        "axisPx": round(centre, 3),
        "centreBandHalfWidthPx": int(band),
        "rectification": "PER_COLUMN_SOURCE_TO_CANONICAL_RADIAL_RESAMPLE",
        "textureCoordinateModel": "CANONICAL_GLOBAL_RADIAL_V",
        "geometryOwnsCoverage": True,
        "canonicalProfileApplied": bool(canonical_profile),
        "edgePolicy": "APPROXIMATED_SOURCE_BOUNDARY_INSET_AND_MATTE_DECONTAMINATION",
        "sourceOuterTrimFraction": 0.12,
        "sourceTailTrimFraction": 0.025,
        "mirroringUsed": False,
        "visibleSourceFinCount": 2,
        "hiddenFinCount": 2,
        "reverseFacePolicy": "APPROXIMATED",
        "alphaPolicy": (
            "APPROXIMATED_FROM_WHITE_BACKDROP"
            if material_alpha is not None
            else "SOURCE_ALPHA"
        ),
        "materialAlpha": material_alpha,
    }
    return HalfFinAuthoring(
        top=top,
        bottom=bottom,
        top_back=top_back,
        bottom_back=bottom_back,
        metadata=metadata,
    )
