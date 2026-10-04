from __future__ import annotations

# Canonical *render* geometry for flight families used by the POC.
#
# Source basis:
# - project reference package: four radial fins; No.2 ~= 34 x 44 mm, No.6 ~= 30 x 44 mm
# - supplied broadside product images for the normalized outline progression
#
# These are NOT manufacturer CAD profiles. The family dimensions are reference values
# and the normalized outlines are calibrated approximations. The No.2 outline keeps the broad rear edge and smooth shoulder progression visible
# on standard/Target K-Flex No.2 references. A narrow pointed rear edge is explicitly
# avoided because it creates the incorrect 'axe head' / leaf silhouette seen on Prodigy. Product artwork remains
# independent source evidence.

NO6_PROFILE = [
    [0.00, 0.00],
    [0.08, 0.18],
    [0.18, 0.42],
    [0.32, 0.74],
    [0.48, 0.95],
    [0.65, 1.00],
    [0.80, 0.98],
    [0.92, 0.88],
    [1.00, 0.64],
    [1.00, -0.64],
    [0.92, -0.88],
    [0.80, -0.98],
    [0.65, -1.00],
    [0.48, -0.95],
    [0.32, -0.74],
    [0.18, -0.42],
    [0.08, -0.18],
]

NO2_PROFILE = [
    [0.00,  0.00],
    [0.04,  0.08],
    [0.08,  0.18],
    [0.14,  0.30],
    [0.22,  0.46],
    [0.32,  0.64],
    [0.44,  0.82],
    [0.56,  0.94],
    [0.66,  1.00],
    [0.74,  0.99],
    [0.82,  0.96],
    [0.90,  0.90],
    [0.96,  0.82],
    [1.00,  0.74],
    [1.00, -0.74],
    [0.96, -0.82],
    [0.90, -0.90],
    [0.82, -0.96],
    [0.74, -0.99],
    [0.66, -1.00],
    [0.56, -0.94],
    [0.44, -0.82],
    [0.32, -0.64],
    [0.22, -0.46],
    [0.14, -0.30],
    [0.08, -0.18],
    [0.04, -0.08],
]

# In the project reference material "No.2 / Standard" is the same broad family.
STANDARD_PROFILE = NO2_PROFILE

# Vapor S remains explicitly heuristic; no exact contour/dimension is supplied by the
# project reference package.
VAPOR_S_PROFILE = [
    [0.00, 0.00],
    [0.10, 0.24],
    [0.28, 0.72],
    [0.56, 1.00],
    [0.82, 0.90],
    [1.00, 0.48],
    [1.00, -0.48],
    [0.82, -0.90],
    [0.56, -1.00],
    [0.28, -0.72],
    [0.10, -0.24],
]

CANONICAL_PROFILES = {
    "NO6": NO6_PROFILE,
    "NO2": NO2_PROFILE,
    "STANDARD": STANDARD_PROFILE,
    "VAPOR_S": VAPOR_S_PROFILE,
}

REFERENCE_DIMENSIONS = {
    # Project reference package / Winmau 2025 examples. These are render references,
    # not universal manufacturer specifications.
    "No.2": {"lengthMm": 44.0, "widthMm": 34.0, "radiusMm": 17.0},
    "No.6": {"lengthMm": 44.0, "widthMm": 30.0, "radiusMm": 15.0},
    "Standard": {"lengthMm": 44.0, "widthMm": 34.0, "radiusMm": 17.0},
    "Pear": {"lengthMm": 42.0, "widthMm": 30.0, "radiusMm": 15.0},
    "Kite": {"lengthMm": 44.0, "widthMm": 31.0, "radiusMm": 15.5},
    "Slim": {"lengthMm": 44.0, "widthMm": 23.5, "radiusMm": 11.75},
}

PROFILE_PROVENANCE = {
    "NO2": "PROJECT_REFERENCE_FAMILY+SUPPLIED_BROADSIDE_CALIBRATION",
    "NO6": "PROJECT_REFERENCE_FAMILY+SUPPLIED_BROADSIDE_CALIBRATION",
    "STANDARD": "PROJECT_REFERENCE_FAMILY+SUPPLIED_BROADSIDE_CALIBRATION",
    "VAPOR_S": "HEURISTIC",
}


def reference_dimensions(shape: str, fallback_length: float, fallback_radius: float):
    ref = REFERENCE_DIMENSIONS.get(shape)
    if not ref:
        return float(fallback_length), float(fallback_radius), "EXISTING_HEURISTIC"
    return (
        float(ref["lengthMm"]),
        float(ref["radiusMm"]),
        "PROJECT_REFERENCE_DIMENSIONS_NOT_MANUFACTURER_CAD",
    )
