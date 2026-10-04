# xConfig Dart Renderer

Research, authoring tools and a lightweight 2.5D/3D rendering pipeline for realistic dart visualization in [autodarts-xconfig](https://github.com/thomasasen/autodarts-xconfig).

**Live-Test:** [xConfig Dart Renderer auf GitHub Pages öffnen](https://thomasasen.github.io/xconfig-dart-renderer/)

> **Status:** Experimental / Research & Development  
> This repository is currently a standalone development project and is not yet part of the production xConfig runtime.

## Goal

The goal of this project is to render darts on the virtual Autodarts board so that they appear to be physically embedded in the board rather than displayed as rotated or skewed 2D sprites.

A convincing representation requires a strict separation between:

1. **Dart design**
2. **Spatial dart pose**
3. **Camera and projection**
4. **xConfig integration**

The project therefore treats the problem primarily as a small **2.5D/3D rendering problem**, not as a traditional image transformation problem.

## Core requirements

The renderer is built around several hard constraints:

- The dart tip is the fixed geometric pivot.
- The projected tip must remain exactly on the Autodarts hit position.
- Dart design and dart pose are independent.
- A dart pose consists of a spatial axis plus roll.
- Flight fins are modeled as separate geometric surfaces.
- Composite product images must not simply be duplicated across multiple flight fins.
- Unknown or invisible surfaces are explicitly treated as approximations.
- Perspective must only be applied once.
- Multiple darts should have small, stable and plausible pose variations.
- Existing xConfig marker, overlay and lifecycle infrastructure should be reused wherever practical.

## Current xConfig integration contract

The current reference renderer targets the existing normalized dart asset contract:

```text
Canvas: 789 × 331
Tip:    (0, 212)
```

The renderer produces a horizontal transparent sprite with the tip fixed at the expected hotspot.

Spatial pose is resolved separately from screen rotation:

```text
3D renderer
    incidence
    roll
    flight geometry
    perspective

        ↓

horizontal transparent sprite
789 × 331
tip = (0,212)

        ↓

xConfig SVG rotateGroup
    screenRotation
```

This allows the existing xConfig overlay and rotation infrastructure to remain usable.

## Why a normal PNG transformation is not enough

A real dart is a three-dimensional object.

Simply applying:

```text
rotate
scale
skew
```

to a finished product image cannot reproduce:

- perspective-dependent visible dart length
- roll around the dart axis
- correct flight fin visibility
- front/back face changes
- depth ordering
- realistic overlaps
- spatial flight geometry

The flight is particularly important because a product photograph often already contains multiple perspectively projected flight surfaces.

Those surfaces cannot safely be copied or mirrored to simulate a four-fin flight.

## Architecture

The current project is divided into four major areas.

### Dart Design Model

A dart is represented as modular components:

```text
Point
Barrel
Shaft
Flight
```

or, for integrated systems:

```text
Point
Barrel
Rear System
```

Examples of integrated rear systems include molded shaft/flight combinations such as K-Flex or K-Shift.

Component compatibility is modeled explicitly. For example:

- Swiss Point vs. press-fit point systems
- barrel rear interface
- traditional shaft + flight
- integrated rear systems

### Dart Design Builder

The builder is used to:

- load complete dart presets
- exchange individual components
- validate component compatibility
- compare reconstructed darts against product references
- inspect provenance
- test different poses
- reset modified builds back to their original preset

The builder is intended to become the authoring environment for reusable xConfig dart designs.

### Pose Model

The internal target model is conceptually:

```text
axis: normalized Vec3
roll: radians
```

For xConfig integration this can be decomposed into:

```text
screenRotation
incidence
roll
```

`screenRotation` is deliberately kept outside the 3D renderer.

### Renderer

The current reference renderer uses **Three.js**.

Three.js is being used to establish the visual and geometric reference implementation. It is not yet a final decision for the production xConfig bundle.

The renderer currently uses:

- one shared renderer
- render-on-demand
- no permanent 60 FPS render loop
- perspective camera
- separate flight planes
- transparent sprite output
- deterministic pose handling

A later production comparison may evaluate a smaller renderer such as OGL against the accepted reference implementation.

## Flight model

Flights are not treated as flat sprite decorations.

The reference geometry starts from two perpendicular flight planes, but transparent
rendering does **not** keep them as two whole intersecting draw objects. Each plane is
split on the shared dart axis into two half-fins:

```text
        B+
         │
A- ──────┼────── A+
         │
        B-
```

The four half-fins meet only on the physical dart axis. They are sorted back-to-front
individually in camera space, avoiding the invalid whole-plane ordering that can make
one transparent fin look like a dark blade cutting through the other.

Roll rotates the complete four-fin structure around the dart axis.

Where possible, visible flight artwork is derived from actual source material.

Unknown surfaces are classified explicitly rather than silently invented.

## Provenance

Every design component should distinguish between different levels of certainty.

Current provenance classes include:

```text
SOURCE-GROUNDED
WEB-VERIFIED
HEURISTIC
APPROXIMATED
UNKNOWN
```

### SOURCE-GROUNDED

Visual information directly originates from an available source image.

### WEB-VERIFIED

Product dimensions or component specifications were confirmed from manufacturer or reliable product documentation.

### HEURISTIC

A visual representation was reconstructed using known characteristics but is not derived directly from original pixels.

### APPROXIMATED

The information is not visible in the available source and has been deliberately approximated.

This distinction is particularly important for:

- flight backsides
- logos
- text
- asymmetric artwork
- transparent flights
- hidden barrel surfaces

## Player dart presets

The current research set includes several commercial and player-oriented designs.

Examples include:

- Gabriel Clemens G2
- Gabriel Clemens 95K
- Rob Cross 95K
- Nathan Aspinall 95K
- Stephen Bunting 95K
- Michael van Gerwen Signature Edition
- Luke Humphries Prestige

These product references are used for research, geometry and reconstruction.

Third-party product imagery and trademarks remain property of their respective owners and should not be assumed to be covered by any software license in this repository.

## Barrel / shaft transition

The builder ensures that barrel and shaft or rear-system geometry meet at the same visible diameter at their connection point.

The transition is adjusted locally at the joint instead of globally scaling either component.

This prevents visible steps while preserving the characteristic geometry of the barrel.

## Pose controls

The current reference UI separates three independent controls:

### Screen Rotation

Rotates the complete rendered dart around the fixed tip in screen space.

### Incidence

Controls the spatial relationship between the dart axis and the board/camera and therefore influences visible dart length and perspective shortening.

### Roll

Rotates the flight structure around the dart's longitudinal axis.

This changes which flight surfaces are visible and how they overlap.

## Testing and QA

The project contains automated and visual checks for:

- fixed tip position
- barrel/shaft transition
- component compatibility
- preset reset behavior
- catalog integrity
- pose mathematics
- renderer syntax
- source provenance
- multiple dart poses
- flight geometry
- comparison renders

Run the validation suite with:

```bash
npm install
npm run validate
```

Additional QA:

```bash
python scripts/qa_static.py
python scripts/software_pose_qa.py
python scripts/browser_qa.py
```

## Running the current POC

Install dependencies:

```bash
npm install
```

Start the local server:

```bash
npm run serve
```

Then open:

```text
http://localhost:4173/
```

The current reference implementation uses Three.js `0.180.0`.

## Repository structure

```text
assets/
  components/          Reconstructed and extracted dart components

data/
  catalog and authoring metadata

src/
  builder
  compatibility logic
  geometry
  renderer
  application code

tests/
  catalog and geometry invariants

scripts/
  static QA
  pose QA
  browser QA

outputs/
  comparisons/
  gallery/
  qa/

reports/
  research
  provenance
  validation
  red-team reviews
```

## Relationship to autodarts-xconfig

This project is developed as a companion R&D repository for:

[`thomasasen/autodarts-xconfig`](https://github.com/thomasasen/autodarts-xconfig)

The production repository is intentionally kept separate while the renderer, design model and authoring workflow are still being validated.

The intended future integration point is the existing:

```text
src/features/dart-marker-replacer
```

Large parts of the existing xConfig infrastructure should remain reusable, including:

- marker detection
- board coordinates
- overlay
- hit anchoring
- lifecycle
- cleanup
- resize and zoom handling
- marker updates
- screen-space rotation

## Current limitations

This is not yet a production renderer.

Known limitations include:

- not all dart designs have complete source imagery
- rear and flight backfaces may be unknown
- some web-researched designs currently use reconstructed local visuals
- transparent flights require additional QA
- body geometry is still simpler than the flight geometry
- lighting and shadows are not final
- WebGL lifecycle and context-loss handling still require production integration testing
- the final production rendering library has not been selected

## Development principles

The project follows several rules:

- Never fake unavailable source information.
- Do not claim approximated surfaces are original.
- Preserve the fixed tip pivot.
- Prefer physically plausible geometry over aggressive image distortion.
- Keep design and pose independent.
- Avoid double perspective.
- Use real board photographs as pose references, not as design sources.
- Optimize bundle size only after the reference rendering model is visually correct.

## Roadmap

Current priorities:

1. Improve source-grounded component extraction.
2. Add more consistent product views per dart.
3. Improve barrel and shaft geometry.
4. Calibrate incidence and roll against real board photographs.
5. Improve transparent flight rendering.
6. Add physically consistent board shadows.
7. Benchmark Three.js against a smaller production renderer.
8. Integrate the accepted renderer into `autodarts-xconfig`.
9. Validate multiple darts, board zoom, corrections and lifecycle behavior in the real runtime.

## Asset and trademark notice

Product names, manufacturer names, player names, logos and product imagery referenced by this project may be trademarks or copyrighted material belonging to their respective owners.

They are used as research and visual references only.

Unless explicitly stated otherwise, third-party assets are **not** licensed for redistribution by this repository.

## License

Software licensing will be finalized before a public release.

Third-party reference images and trademarks are not covered by the software license.

---

This project is independent research and is not an official product of Autodarts, Target Darts, Winmau or any referenced manufacturer or player.
