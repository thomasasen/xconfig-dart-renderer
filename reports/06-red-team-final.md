# 06 – Red Team nach Korrektur

## Erneut geprüft

- **15/15 Quellen klassifiziert:** PASS.
- **Presets:** 16 vorhanden. Neben den bisherigen Quellen sind sieben web-recherchierte Spieler-Presets ergänzt, darunter Gabriel Clemens G2 und Gabriel Clemens 95K.
- **Tip-Vertrag:** statische Assembly- und Software-Pose-QA ergeben exakt `(0,212)`; maximale mathematische Drift `0.0 px`.
- **Flight:** zwei vollständige Planes, 90°, gemeinsame Achse; Plane B explizit APPROXIMATED; keine gespiegelte Schrift.
- **Freie Kombinationen:** neun QA-Kombinationen gerendert (sechs gezielte Einzeländerungen plus drei Cross-Preset-Stresstests); geometrisch keine Lücken an den Komponenten-Grenzen.
- **Integrated Rear:** K-Flex/K-Shift bleiben einzelne Katalogelemente; Shaft/Flight werden in der UI gesperrt.
- **Inkompatible Point-Barrel-Kombinationen:** Swiss vs. Press-fit werden deaktiviert/automatisch korrigiert.
- **Doppelperspektive:** Builder enthält keine `flatPerspective`-Stufe.
- **Schatten/Wobble/Fluganimation:** weiterhin absichtlich OFF; statische Ruhepose wird zuerst gelöst.
- **Source vs. Builder:** Vergleichsbilder werden für alle 16 Presets erzeugt. Bei Web-Presets ist die linke Quelle ausdrücklich eine beschriftete lokale Rekonstruktion und kein Originalfoto.

## Nicht als gelöst ausgeben

- Body-Roll/Barrel-Rückseiten sind im Ribbon-Hybrid nicht vollständig 3D.
- Plane-B-Artwork ist ohne zweite Produktansicht nicht source-grounded.
- Transparente Flights brauchen vor Produktivintegration einen dedizierten WebGL-Alpha/Depth-Test.
- WebGL-Runtime konnte in dieser Chat-Ausführungsumgebung nicht per Headless-Browser gestartet werden, weil Navigation zu localhost administrativ blockiert ist. Der Three.js-Code ist syntaktisch validiert; das Paket unterstützt lokale `npm install`-Abhängigkeit und CDN-Fallback und enthält einen reproduzierbaren Browser-QA-Runner.
- Die sieben neuen Player-Designs sind visuell noch nicht pixel-source-grounded. Geometrie/Komponenten kommen aus verifizierten Produktdaten; Artwork/Silhouetten sind klar als `HEURISTIC` rekonstruiert.
