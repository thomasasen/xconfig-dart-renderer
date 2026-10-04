from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from flight_backface import build_backface_approximation


def high_frequency_energy(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    return float(np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean())


def visible_median_rgb(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    mask = rgba[:, :, 3] >= 176
    if not np.any(mask):
        mask = rgba[:, :, 3] > 24
    return np.median(rgba[:, :, :3][mask].astype(np.float32), axis=0)


w, h = 360, 220
front = Image.new("RGBA", (w, h), (0, 0, 0, 0))
draw = ImageDraw.Draw(front)
base_color = (116, 47, 170, 255)
draw.polygon([(4, h // 2), (58, 24), (w - 8, 44), (w - 8, h - 44), (58, h - 24)], fill=base_color)
draw.rectangle((105, 62, 285, 91), fill=(242, 242, 248, 255))
draw.rectangle((105, 103, 285, 132), fill=(25, 20, 32, 255))
for x in range(120, 280, 22):
    draw.rectangle((x, 145, x + 8, 181), fill=(238, 196, 55, 255))

# Add semi-transparent edge material to verify that the reverse keeps alpha rather than
# replacing the flight with an opaque neutral blade.
rgba = np.asarray(front).copy()
alpha = rgba[:, :, 3]
edge = (alpha > 0) & (
    (np.indices(alpha.shape)[1] < 24) |
    (np.indices(alpha.shape)[0] < 34) |
    (np.indices(alpha.shape)[0] > h - 35)
)
rgba[:, :, 3][edge] = np.minimum(rgba[:, :, 3][edge], 128)
front = Image.fromarray(rgba, "RGBA")

back = build_backface_approximation(front)
front_arr = np.asarray(front)
back_arr = np.asarray(back)

assert np.array_equal(front_arr[:, :, 3], back_arr[:, :, 3]), "backface must preserve authored source alpha exactly"

front_hf = high_frequency_energy(front)
back_hf = high_frequency_energy(back)
assert back_hf < front_hf * 0.58, f"backface still retains too much logo/text detail: {back_hf:.3f} vs {front_hf:.3f}"

front_material = np.array(base_color[:3], dtype=np.float32)
back_median = visible_median_rgb(back)
assert np.linalg.norm(back_median - front_material) < 42, (
    f"backface colour identity drifted too far from source material: {back_median} vs {front_material}"
)

assert np.any(back_arr[:, :, 3] == 128), "semi-transparent source material must remain semi-transparent"


# A dark flight with large gold/white artwork is the regression case that previously
# collapsed into a muddy brown/grey blurred backside. Dominant substrate colour must win.
dark = Image.new("RGBA", (360, 220), (0, 0, 0, 0))
dd = ImageDraw.Draw(dark)
dd.polygon([(4, 110), (58, 20), (352, 42), (352, 178), (58, 200)], fill=(24, 25, 22, 255))
dd.rectangle((80, 118, 350, 150), fill=(222, 179, 93, 255))
dd.rectangle((105, 155, 350, 190), fill=(232, 230, 220, 255))
for x in range(95, 340, 46):
    dd.rectangle((x, 62, x + 16, 103), fill=(196, 142, 52, 255))
dark_back = build_backface_approximation(dark)
dark_median = visible_median_rgb(dark_back)
assert float(np.mean(dark_median)) < 70, (
    f"dark substrate must not turn into a muddy bright/brown backface: {dark_median}"
)
assert high_frequency_energy(dark_back) < high_frequency_energy(dark) * 0.30, (
    "dark regression backface must not preserve blurred artwork ghosts"
)
print(
    "PASS: approximated backface removes high-frequency artwork while preserving material colour and alpha"
)
