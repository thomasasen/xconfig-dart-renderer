from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tail_authoring import (  # noqa: E402
    FAIL_ALPHA_HAZE,
    FAIL_ROOT_ALIGNMENT,
    PASS,
    author_tail_components,
)


def synthetic_tail(*, rotate_deg=0.0, integrated=False, haze=False, root_offset=0):
    width, height = 500, 120
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    axis = 60

    draw.polygon([(5, axis), (40, axis - 3), (40, axis + 3)], fill=(175, 175, 178, 255))
    draw.rectangle((40, 48, 210, 72), fill=(145, 145, 150, 255))
    draw.rectangle((210, 56, 345, 64), fill=(45, 75, 120, 255))

    if integrated:
        for x in range(345, 401):
            t = (x - 345) / 55
            smooth = t * t * (3 - 2 * t)
            half = 4 + int(round(7 * smooth))
            draw.line(
                (x, axis + root_offset - half, x, axis + root_offset + half),
                fill=(45, 75, 120, 255),
            )
    else:
        draw.rectangle((345, 56, 400, 64), fill=(45, 75, 120, 255))

    draw.polygon(
        [(398, 60), (420, 30), (485, 25), (495, 45), (495, 75), (485, 95), (420, 90)],
        fill=(60, 90, 180, 255),
    )

    if haze:
        draw.rectangle((225, 32, 340, 52), fill=(100, 100, 100, 80))

    if rotate_deg:
        image = image.rotate(
            rotate_deg,
            resample=Image.Resampling.BICUBIC,
            expand=True,
            fillcolor=(0, 0, 0, 0),
        )
    return image


def analyze(image, integrated):
    return author_tail_components(image, seed_range=(0.42, 0.80), integrated=integrated)


straight = analyze(synthetic_tail(integrated=False), False)
assert straight["analysis"].status == PASS
assert straight["rearRoot"] is None
assert straight["analysis"].shaft_center_residual_p95_px <= 0.5

rooted = analyze(synthetic_tail(integrated=True), True)
assert rooted["analysis"].status == PASS
assert rooted["rearRoot"] is not None
assert rooted["analysis"].root_leak_ratio < 1.28
assert rooted["analysis"].root_axis_offset_px <= 0.5

rotated = analyze(synthetic_tail(integrated=True, rotate_deg=-2.2), True)
assert abs(rotated["axisSource"].angle_deg) > 1.5
assert abs(rotated["axisAligned"].angle_deg) < 0.15
assert rotated["analysis"].status == PASS

off_axis = analyze(synthetic_tail(integrated=True, root_offset=5), True)
assert off_axis["rearRoot"] is not None
assert off_axis["analysis"].status == FAIL_ROOT_ALIGNMENT

hazy = analyze(synthetic_tail(integrated=True, haze=True), True)
assert hazy["analysis"].haze_ratio > 0.12
assert hazy["analysis"].status == FAIL_ALPHA_HAZE

print("PASS: tail analyzer detects stable core/root, straightens small source rotation, and rejects haze/off-axis roots")
