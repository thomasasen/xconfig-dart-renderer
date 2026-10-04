from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance


def _dominant_material_color(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    visible = alpha >= 176
    if not np.any(visible):
        visible = alpha > 24
    if not np.any(visible):
        return np.array([128.0, 128.0, 128.0], dtype=np.float32)

    sample = rgb[visible].astype(np.uint8)

    # Find the dominant source-material colour family instead of averaging all artwork.
    # Coarse RGB bins suppress anti-aliasing/noise while allowing a black, white, red,
    # purple, blue, etc. substrate to win over logos and decorative stripes.
    quant = (sample // 32).astype(np.int32)
    keys = quant[:, 0] * 64 + quant[:, 1] * 8 + quant[:, 2]
    counts = np.bincount(keys, minlength=512)
    winner = int(np.argmax(counts))
    winner_mask = keys == winner
    dominant = sample[winner_mask].astype(np.float32)
    return np.median(dominant, axis=0) if dominant.size else np.median(sample, axis=0)


def build_backface_approximation(front: Image.Image) -> Image.Image:
    """
    Build an explicitly APPROXIMATED reverse flight surface.

    The source image does not contain a trustworthy reverse face. We therefore retain
    the source silhouette and alpha/translucency plus the dominant source-material colour,
    while deliberately removing readable logos/text and source-specific colour patterns. Transparent matte pixels are filled from the robust interior material colour
    before downsampling so a white catalogue background cannot turn the backface grey.
    """
    base = front.convert("RGBA")
    rgba = np.asarray(base, dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].astype(np.uint8)
    h, w = alpha.shape
    if w < 1 or h < 1:
        return base

    material = _dominant_material_color(rgb, alpha)

    # Plane B must not look like a blurred copy of Plane A. Retain only a tiny amount of
    # very-low-frequency *luminance* variation. Hue/artwork information is discarded, so
    # coloured logos, text and asymmetric graphics cannot reappear as ghost imagery.
    luma = (
        rgb[:, :, 0] * 0.2126 +
        rgb[:, :, 1] * 0.7152 +
        rgb[:, :, 2] * 0.0722
    )
    visible = alpha > 24
    mean_luma = float(np.mean(luma[visible])) if np.any(visible) else 128.0
    luma_img = Image.fromarray(np.clip(luma, 0, 255).astype(np.uint8), "L")
    low = (
        luma_img
        .resize((4, 3), Image.Resampling.BOX)
        .resize((w, h), Image.Resampling.BILINEAR)
    )
    delta = (np.asarray(low, dtype=np.float32) - mean_luma) * 0.055
    delta = np.clip(delta, -7.0, 7.0)

    base_rgb = material[None, None, :] * 0.94
    mixed = np.clip(base_rgb + delta[:, :, None], 0, 255).astype(np.uint8)
    out = Image.fromarray(mixed, "RGB").convert("RGBA")

    # Preserve the authored front-face alpha exactly. For transparent flights this keeps
    # the material translucency instead of inventing an opaque grey reverse surface.
    out.putalpha(base.getchannel("A"))
    return out
