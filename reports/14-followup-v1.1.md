# Follow-up V1.1 – Barrel/Shaft-Naht und Pose-Steuerung

## Anlass

Praxisfeedback: Der Builder funktioniert grundsätzlich, aber Barrel und Shaft dürfen am Übergang keine unterschiedliche sichtbare Dicke haben. Außerdem war die Rotation/Pose-Steuerung in der UI nicht ausreichend bzw. nicht eindeutig wirksam.

## Korrektur 1: sichtbare Anschlussdicke

Die Ursache lag nicht primär in den Produktbildern, sondern in der Runtime-Skalierung: Barrel und Shaft wurden mit nominellen Durchmessern auf Textur-Ribbons gelegt, obwohl die alpha-freigestellte Silhouette am jeweiligen Bildrand nicht immer die volle Texturhöhe belegt. Dadurch konnte ein nominell 5,2-mm-Rear-System sichtbar deutlich dünner werden.

V1.1 misst deshalb für Barrel-Rear und Shaft/Rear-Front die tatsächlich belegte Alpha-Höhe. Die transparenten Mesh-Envelopes werden so skaliert, dass die **sichtbare** Silhouette auf beiden Seiten exakt auf die nominelle Rear-/Shaft-Anschlussdicke trifft. Der Barrel tapert nur in einer kurzen Zone vor der Verbindung; Shaft bzw. Rear-System normalisieren sich ebenfalls lokal auf ihre Body-Dicke.

Harte QA-Invariante:

```text
visible barrel thickness at join == visible shaft/rear thickness at join
```

## Korrektur 2: Pose-Steuerung

Die UI besitzt jetzt drei getrennte Freiheitsgrade:

1. `Bildschirmrotation`: 2D-Rotation des bereits gerenderten Sprites um den Tip; bleibt außerhalb des 3D-Renderers.
2. `Incidence`: 3D-Achsneigung und damit perspektivische Verkürzung.
3. `Roll`: Rotation des Flightkreuzes um die lokale Dartachse.

Damit bleibt die xConfig-Zielarchitektur erhalten: Der Renderer erzeugt weiterhin ein horizontales 789×331-Sprite mit Tip `(0,212)`; die Bildschirmrichtung kann später vom bestehenden `rotateGroup` übernommen werden.

## Korrektur 3: transparenter Flight bei Roll

Die beiden Flight-Ebenen hatten denselben Objektursprung. Für transparente Three.js-Objekte ist das für die Sortierung ungünstig. V1.1 berechnet nach jeder Pose die Weltposition des Geometriezentrums und setzt die Render-Reihenfolge far-to-near. `depthWrite` ist für Flightflächen deaktiviert, `depthTest` bleibt aktiv.

## Korrektur 4: UI-Race-Schutz

Slider-Events rendern nicht mehr ungebremst parallel. Eingaben werden per `requestAnimationFrame` gebündelt, und jeder Renderlauf besitzt einen Epoch-Zähler. Ein älterer asynchroner Lauf darf damit kein neueres Ergebnis überschreiben.

## Validierung

Bestanden:

- Katalog-/Evidence-Invarianten
- Builder Reset
- Kompatibilitätsregeln
- neue Seam-/Pivot-Unit-Tests
- JavaScript Syntaxchecks
- statische QA
- unabhängige Software-Pose-QA, weiterhin 0,0 px Tip-Drift

Nicht in dieser Sandbox verifiziert:

- echter Chromium/WebGL-Lauf, da Navigation zu `127.0.0.1` weiterhin mit `ERR_BLOCKED_BY_ADMINISTRATOR` blockiert wird. Der Browser-QA-Test wurde erweitert und prüft lokal zusätzlich alle drei Pose-Regler sowie die Join-Metrik.
