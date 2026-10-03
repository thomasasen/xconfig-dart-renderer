# 04 – Builder- und Rendererarchitektur

## Pipeline

```text
source image / verified specs
        ↓
authoring split (image-space only)
        ↓
Point / Barrel / Shaft / Flight OR RearSystem catalog entities
        ↓
compatibility resolver
        ↓
SharedDartComponentRenderer (Three.js reference renderer)
        ↓
axis Vec3 + roll
        ↓
two full intersecting flight planes
        ↓
transparent 789×331 sprite, Tip=(0,212)
        ↓
screenRotation intentionally outside renderer
```

## Was V4 unverändert bleibt

- Tip ist harte Invariante.
- Flight = zwei vollständige, 90° gekreuzte Planes, keine vier unabhängigen Sprites.
- `axis Vec3 + roll`; im Builder wird die kanonische Projektion horizontal gehalten.
- keine `flatPerspective`-Nachbearbeitung.
- `MeshBasicMaterial`: keine zusätzliche virtuelle Beleuchtung auf bereits fotografierter Beleuchtung.
- Shared Renderer, Render-on-demand, kein permanenter 60-FPS-Loop.
- WebGL-Context-Loss-Handler und Sprite-Cache sind vorgesehen.

## Bewusster Hybrid

Point, Barrel und Shaft sind in diesem Builder-POC source-grounded **Ribbons** mit realer Längengeometrie. Das ist absichtlich noch kein rotationssymmetrisches 3D-Barrel-Mesh. Flight-Geometrie ist der räumlich wichtigste Teil und wird V4-konform modelliert.

## xConfig-Integrationsgrenze

Dieser POC schreibt nichts in xConfig. Der spätere Integrationspfad bleibt Render-to-Sprite: der 3D-Renderer erzeugt einen horizontalen 789×331-Sprite; xConfigs bestehender `rotateGroup` kann `screenRotation` übernehmen. Im 3D-Pfad muss `flatPerspective` ausbleiben.
