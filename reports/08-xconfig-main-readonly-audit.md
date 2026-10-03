# 08 – xConfig main, read-only Audit

Geprüfter Branch: `main`

Geprüfter Commit zum Zeitpunkt dieser Arbeit: `5f41fd515b65cafa3ccf2643b5e462805227f6c3` (`release: prepare 3.3.1`, 02.10.2026 UTC).

Bestätigt im aktuellen `src/features/dart-marker-replacer/logic.js`:

```text
DART_IMAGE_SOURCE_WIDTH  = 789
DART_IMAGE_SOURCE_HEIGHT = 331
DART_IMAGE_TIP_Y         = 212
TIP_X ratio              = 0
```

Bestätigt in `pose.js`:

- `realisticDirection` löst primär eine 2D-Bildschirmrichtung aus einem angenommenen Wurfpunkt.
- `natural`/`dramatic` erzeugen deterministische 2D-Jitter/Skew/Scale/Tail-Lift-Werte.
- `flatPerspective` nutzt weiterhin affine Scale-Werte (mild ≈ 0.85, strong ≈ 0.65).
- Tip-verankerte Matrizen sind bereits Teil der Legacy-Pipeline.

Konsequenz für später: Der Builder/3D-Pfad soll nicht Marker-Erkennung, Overlay, Cleanup oder `rotateGroup` ersetzen. Der wahrscheinlich kleinste Eingriff bleibt ein horizontaler 789×331 Render-to-Sprite mit Tip `(0,212)`, `screenRotation` danach im bestehenden SVG-`rotateGroup`, und `flatPerspective` im 3D-Pfad **aus**.

Während dieser Arbeit wurden keinerlei GitHub-Dateien verändert.
