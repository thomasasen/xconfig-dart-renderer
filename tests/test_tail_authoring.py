from pathlib import Path
import sys
import math
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from tail_authoring import analyze_axis, author_tail_components, build_silhouette_profile, detect_shaft_core, detect_rear_root


def synthetic(*, angle=0.0, root=True, haze=False, root_offset=0):
    w,h=380,120
    im=Image.new('RGBA',(w,h),(0,0,0,0))
    d=ImageDraw.Draw(im)
    cy=h//2
    # Point/barrel are only context; tail seed starts at x=155.
    d.polygon([(8,cy),(55,cy-2),(55,cy+2)],fill=(180,180,180,255))
    d.rounded_rectangle((55,cy-10,155,cy+10),radius=8,fill=(110,110,115,255))
    d.rectangle((155,cy-4,255,cy+4),fill=(35,35,40,255))
    if root:
        pts=[
            (255,cy-4+root_offset),(270,cy-6+root_offset),(285,cy-10+root_offset),
            (285,cy+10+root_offset),(270,cy+6+root_offset),(255,cy+4+root_offset),
        ]
        d.polygon(pts,fill=(45,45,50,255))
    else:
        d.rectangle((255,cy-4,285,cy+4),fill=(35,35,40,255))
    d.polygon([(282,cy),(305,cy-30),(365,cy-36),(374,cy),(365,cy+36),(305,cy+30)],fill=(70,90,140,255))
    if haze:
        for x in range(165,275,8):
            d.point((x,cy+18),fill=(120,120,120,36))
            d.point((x,cy-18),fill=(120,120,120,36))
    if angle:
        im=im.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True,fillcolor=(0,0,0,0))
    return im


# Straight integrated rear: stable core, explicit widening root, no axis break.
base=synthetic()
axis=analyze_axis(base)
assert abs(axis['angleDeg']) < .35, axis
result=author_tail_components(base,shaft_seed_range=(155,285),flight_start_px=285,integrated=True)
analysis=result['analysis'].to_dict()
assert result['rearRootImage'] is not None, analysis
assert analysis['shaft_width_cv'] < .18, analysis
assert analysis['shaft_center_residual_p95_px'] <= analysis['shaft_width_median_px']*.12, analysis
assert result['tailSegmentation']['rootGrowthRatio'] > 1.08, result['tailSegmentation']
assert analysis['status'] in ('PASS','NEEDS_MANUAL_REVIEW'), analysis

# Slightly rotated source must be globally normalised, not locally warped.
rot=synthetic(angle=3.2)
axis=analyze_axis(rot)
assert 2.0 < abs(axis['angleDeg']) < 4.5, axis
rot_result=author_tail_components(rot,shaft_seed_range=(155,285),flight_start_px=285,integrated=True)
rot_analysis=rot_result['analysis'].to_dict()
assert rot_analysis['shaft_center_residual_p95_px'] <= rot_analysis['shaft_width_median_px']*.15, rot_analysis

# Classic shaft has no mandatory root and must not invent one.
classic=synthetic(root=False)
classic_result=author_tail_components(classic,shaft_seed_range=(155,285),flight_start_px=285,integrated=False)
assert classic_result['rearRootImage'] is None
assert classic_result['tailSegmentation']['rearRoot'] is None

# Off-axis integrated root is a hard QA failure when the offset is large enough.
off=synthetic(root_offset=8)
off_result=author_tail_components(off,shaft_seed_range=(155,285),flight_start_px=285,integrated=True)
assert off_result['analysis'].status in ('FAIL_ROOT_ALIGNMENT','FAIL_SOURCE_UNSUITABLE','NEEDS_MANUAL_REVIEW'), off_result['analysis']

# Weak detached haze must be measurable and may not disappear from QA metadata.
hz=synthetic(haze=True)
hz_result=author_tail_components(hz,shaft_seed_range=(155,285),flight_start_px=285,integrated=True)
assert hz_result['tailMetrics']['tailAlphaHaze'] > 0, hz_result['tailMetrics']

print('PASS: tail analyzer detects axis, stable shaft core, integrated root, off-axis root and alpha haze')
