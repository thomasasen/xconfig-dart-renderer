# 09 – Flight Geometry v4

## Ursache des weiter falschen v3-Eindrucks

V3 hatte zwar vier radiale Halb-Finnen mit gemeinsamer Achse, behandelte diese im Renderer aber weiterhin als vier eigenständige Mesh-/Textureinheiten. Dadurch blieb die visuelle Segmentierung in einzelne Lappen erhalten. Zusätzlich lag ein separater langer Flight-Core über der gesamten Flightlänge.

## V4-Korrektur

V4 modelliert den Flight als zwei vollständige, sich entlang derselben Dartlängsachse schneidende Planarflächen:

- Plane A: source-grounded Broadside-Ebene aus `design_02.jpg`
- Plane B: um 90° gedrehte Symmetrie-Ebene

Vier Finnen entstehen als die vier radialen Hälften dieser beiden Ebenen. Roll wird auf die gemeinsame Flightgruppe angewandt. Es gibt keinen separaten Flight-Core mehr.

## Textur

Die komplette Broadside-Fläche wird direkt aus dem Produktbild extrahiert. Die Quelle ist bereits nahe an einer orthogonalen Seitenansicht, deshalb ist keine aggressive Homographie nötig. Der weiße Hintergrund wird in Alpha überführt; die fotografierte Beleuchtung und das Artwork bleiben source-grounded.

## Profil

Die Debug-Geometrie nutzt den äußeren Quellkontur-Hull. Die exakte sichtbare Silhouette wird zusätzlich durch den Alpha-Cutout der Source-Textur bestimmt. Der Hull ist daher eine robuste Geometrieapproximation, nicht der Versuch, eine neue Flightform zu erfinden.

## Harte QA-Gates

1. `Incidence 0° / Roll 0°` rekonstruiert die Broadside-Silhouette.
2. Die zweite Plane ist bei Roll 0° edge-on.
3. Ein kleiner Roll macht die zweite Plane nur sekundär sichtbar.
4. Beide Planes bleiben exakt 90° zueinander.
5. Roll verändert keine lokale X-Koordinate.
6. Tip bleibt `(0,212)`.
7. Kein separater Core/Zylinder darf das Flightzentrum künstlich verdicken.

## Status

Die Software-Validierung besteht mit 15/15 Tests. Browser-/WebGL-Performance muss weiterhin im enthaltenen Three.js-Benchmark gemessen werden; die Python-Zeiten sind ausdrücklich keine WebGL-Messwerte.
