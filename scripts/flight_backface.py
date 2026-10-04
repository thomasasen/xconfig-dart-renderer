from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance


def _robust_material_color(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    visible = alpha > 24
    if not np.any(visible):
        return np.array([128.0, 128.0, 128.0], dtype=np.float32)

    interior = alpha >= 176
    sample = rgb[interior] if np.any(interior) else rgb[visible]
    return np.median(sample.astype(np.float32), axis=0)


def build_backface_approximation(front: Image.Image) -> Image.Image:
    """
    Build an explicitly APPROXIMATED reverse flight surface.

    The source image does not contain a trustworthy reverse face. We therefore retain
    the source silhouette, alpha/translucency and low-frequency material colour while
    deliberately removing readable logos/text and other source-specific high-frequency
    detail. Transparent matte pixels are filled from the robust interior material colour
    before downsampling so a white catalogue background cannot turn the backface grey.
    """
    base = front.convert("RGBA")
    rgba = np.asarray(base, dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].astype(np.uint8)
    h, w = alpha.shape
    if w < 1 or h < 1:
        return base

    material = _robust_material_color(rgb, alpha)
    coverage = (alpha.astype(np.float32) / 255.0)[:, :, None]

    # Decontaminate transparent/anti-aliased pixels before the low-frequency reduction.
    filled = rgb * coverage + material[None, None, :] * (1.0 - coverage)
    filled = np.clip(filled, 0, 255).astype(np.uint8)

    grid_w = max(4, min(12, max(1, round(w / 48))))
    grid_h = max(4, min(10, max(1, round(h / 32))))
    local = (
        Image.fromarray(filled, "RGB")
        .resize((grid_w, grid_h), Image.Resampling.BOX)
        .resize((w, h), Image.Resampling.BILINEAR)
    )
    local_arr = np.asarray(local, dtype=np.float32)

    # Keep local colour families, but pull them toward a robust source-derived material
    # colour so logos and strongly contrasting typography cannot survive as silhouettes.
    mixed = local_arr * 0.60 + material[None, None, :] * 0.40
    out = Image.fromarray(np.clip(mixed, 0, 255).astype(np.uint8), "RGB")
    out = ImageEnhance.Contrast(out).enhance(0.88)
    out = ImageEnhance.Color(out).enhance(0.96)
    out = ImageEnhance.Brightness(out).enhance(0.93)
    out = out.convert("RGBA")

    # Preserve the authored front-face alpha exactly. For transparent flights this keeps
    # the material translucency instead of inventing an opaque grey reverse surface.
    out.putalpha(base.getchannel("A"))
    return out
