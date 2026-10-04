from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from flight_fin_authoring import author_visible_half_fins


w, h = 420, 250
im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
# Two visibly different faces around a narrow central spine. Deliberately asymmetric
# markings let us detect accidental mirroring/copying.
d.polygon([(10, 124), (80, 40), (390, 55), (405, 120), (10, 124)], fill=(150, 35, 170, 255))
d.polygon([(10, 126), (405, 130), (390, 205), (80, 220), (10, 126)], fill=(150, 35, 170, 255))
d.rectangle((135, 62, 180, 82), fill=(245, 220, 45, 255))
d.rectangle((255, 180, 330, 202), fill=(30, 215, 230, 255))
d.rectangle((15, 121, 405, 129), fill=(95, 10, 110, 255))

result = author_visible_half_fins(im, material_alpha=0.68, source_label="synthetic")
assert result.metadata["mirroringUsed"] is False
assert result.metadata["visibleSourceFinCount"] == 2
assert result.metadata["hiddenFinCount"] == 2
assert result.metadata["alphaPolicy"] == "APPROXIMATED_FROM_WHITE_BACKDROP"
assert result.top.width > 100 and result.bottom.width > 100
assert result.top.height >= 64 and result.bottom.height >= 64

top = np.asarray(result.top)
bottom = np.asarray(result.bottom)
# Top contains yellow artwork, bottom cyan artwork. If one face was copied/mirrored
# from the other, these colour-family checks fail.
assert int(((top[:, :, 0] > 210) & (top[:, :, 1] > 180) & (top[:, :, 2] < 100)).sum()) > 20
assert int(((bottom[:, :, 0] < 80) & (bottom[:, :, 1] > 170) & (bottom[:, :, 2] > 170)).sum()) > 20
assert np.max(top[:, :, 3]) < 255, "material alpha reconstruction should keep moulded plastic translucent"
assert np.max(bottom[:, :, 3]) < 255, "material alpha reconstruction should keep moulded plastic translucent"

# Reverse surfaces are unseen source information. They must not contain a readable/
# mirrored copy of the source artwork. Material-only backfaces should therefore have
# near-zero RGB texture energy while preserving the authored alpha silhouette.
def rgb_energy(arr):
    rgb=arr[:, :, :3].astype(np.float32)
    return float(np.abs(np.diff(rgb,axis=0)).mean()+np.abs(np.diff(rgb,axis=1)).mean())

top_back=np.asarray(result.top_back)
bottom_back=np.asarray(result.bottom_back)
assert rgb_energy(top_back) < 0.15, f"top reverse still contains artwork RGB detail: {rgb_energy(top_back):.3f}"
assert rgb_energy(bottom_back) < 0.15, f"bottom reverse still contains artwork RGB detail: {rgb_energy(bottom_back):.3f}"

# Front artwork may intentionally be more opaque, but the unknown reverse material may
# not encode that artwork in alpha. Fully-covered reverse pixels therefore share the
# material alpha instead of reproducing logo/text silhouettes.
for name,arr in (("top",top_back),("bottom",bottom_back)):
    alpha=arr[:, :, 3]
    interior=alpha > 150
    assert interior.any(), f"{name} reverse has no visible material interior"
    assert int(alpha.max()) <= 176, f"{name} reverse alpha exceeds 0.68 material opacity: {alpha.max()}"
    assert float(alpha[interior].std()) < 2.0, (
        f"{name} reverse alpha still contains artwork structure: std={alpha[interior].std():.3f}"
    )

print("PASS: composite flight yields distinct source faces, matte-cleaned fronts and RGB/alpha-detail-free reverses")
