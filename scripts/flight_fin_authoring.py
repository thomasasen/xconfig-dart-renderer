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
    # Preserve antialiased silhouette coverage from the source extraction.
    arr[:, :, 3] = np.clip(source_alpha * target * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


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
    out_h = max(64, int(round(max_span * 0.58)))
    map_x = np.zeros((out_h, width), dtype=np.float32)
    map_y = np.zeros((out_h, width), dtype=np.float32)
    valid = np.zeros((out_h, width), dtype=np.uint8)

    for ox, sx in enumerate(range(face_start, face_end + 1)):
        b = bounds[sx]
        if not b:
            continue
        y0, y1 = b
        centre = (y0 + y1) * 0.5
        if which == "top":
            outer = float(y0)
            axis = float(centre - band)
            if axis - outer < 2:
                continue
            # Keep source orientation: texture top = outer edge, bottom = dart axis.
            sample_y = np.linspace(outer, axis, out_h, dtype=np.float32)
        else:
            axis = float(centre + band)
            outer = float(y1)
            if outer - axis < 2:
                continue
            # Keep source orientation: texture top = dart axis, bottom = outer edge.
            sample_y = np.linspace(axis, outer, out_h, dtype=np.float32)
        map_x[:, ox] = float(sx)
        map_y[:, ox] = sample_y
        valid[:, ox] = 255

    sampled = cv2.remap(
        rgba,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    sampled[:, :, 3] = np.minimum(sampled[:, :, 3], valid)
    return _trim_alpha(Image.fromarray(sampled, "RGBA"), 3)


def author_visible_half_fins(
    composite: Image.Image,
    *,
    material_alpha: float | None = None,
    source_label: str = "source",
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

    top = _rectify_half(rgba, bounds, face_start, face_end, band, "top")
    bottom = _rectify_half(rgba, bounds, face_start, face_end, band, "bottom")
    top = _apply_material_alpha(top, material_alpha)
    bottom = _apply_material_alpha(bottom, material_alpha)

    top_back = build_backface_approximation(top)
    bottom_back = build_backface_approximation(bottom)

    metadata = {
        "mode": "TWO_VISIBLE_HALF_FINS_RECTIFIED",
        "sourceLabel": source_label,
        "faceStartPx": int(face_start),
        "faceEndPx": int(face_end),
        "axisPx": round(centre, 3),
        "centreBandHalfWidthPx": int(band),
        "rectification": "PER_COLUMN_RADIAL_RESAMPLE",
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
