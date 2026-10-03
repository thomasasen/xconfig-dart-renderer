# 03 – Datenmodell und Kompatibilität

## Entitäten

- `PointDefinition`: Point-Interface, Länge/Durchmesser, Rendergeometrie, Textur, Evidence.
- `BarrelDefinition`: Point-Interface, Rear-Thread, reale Maße sofern bekannt, getrennte Rendermaße, Profil, Textur, Evidence.
- `ShaftDefinition`: Rear-Thread, Flight-Mount, Länge, Textur, Evidence.
- `FlightDefinition`: Flight-Mount, Shape, V4-Plane-Profile, Plane A/B Texturen und Face-Evidence.
- `RearSystemDefinition`: **eine einzige** logische Einheit für integrierte Shaft+Flight-Systeme. Intern darf der Renderer Shaft-Body + zwei Flight-Planes erzeugen; im Katalog/Builder bleibt es ein Bauteil.
- `DartPreset`: referenziert kompatible Komponenten und eine Quellabbildung.

## Kompatibilitätsregeln

1. `point.interface === barrel.pointInterface`.
2. `barrel.rearThread === shaft.rearThread` oder `rearSystem.rearThread`.
3. `shaft.flightMount === flight.flightMount`.
4. Ein aktives `RearSystemDefinition` ist gegenseitig ausschließend mit separatem Shaft + Flight.
5. `SWISS_POINT` wird nicht mit `PRESS_FIT` vermischt.
6. `2BA` beschreibt nur die Rear-Verbindung; es sagt nichts über Point-Kompatibilität aus.

## Evidence

Die einzige zulässige Vokabelliste ist `SOURCE-GROUNDED`, `WEB-VERIFIED`, `HEURISTIC`, `APPROXIMATED`, `UNKNOWN`. Renderheuristiken werden nicht in Herstellerdaten „hochgestuft“.

## Flightvertrag

V4 bleibt bindend: zwei vollständige, orthogonale Plane-Geometrien auf derselben Längsachse; Roll rotiert den gesamten Flight-Cross. Bei den **15 gelieferten Quellen** ist Plane A source-grounded. Die zusätzlich web-recherchierten Spieler-Darts verwenden bewusst `HEURISTIC` für Plane A, weil ihre lokalen Assets lediglich **WEB-REFERENCED RECONSTRUCTIONS** sind und keine heruntergeladenen Herstellerpixel. Plane B bleibt ohne verifizierte Gegenansicht `APPROXIMATED` und wird **nicht gespiegelt**; die UI zeigt einen konservativen Safe-Roll-Bereich.
