# 13 – Finaler Validierungsbericht V1.2

## Ergebnis

- Katalog-/Vertragstests: **PASS**.
- Preset → manuelle Änderung → Reset auf Preset: **PASS**.
- Kompatibilitätsmodell: **PASS**; Swiss/Press-fit-Fehlkombinationen und doppelte Rear-Assemblies werden abgelehnt.
- JavaScript-Syntax: **PASS** für Renderer, Compatibility, Builder-State und App.
- Presets: **16**, davon **7** neu web-recherchierte Spieler-Presets.
- Gabriel Clemens: **2 Presets** (`clemens-g2-23`, `clemens-95k-23`).
- Statische Preset-QA: **16 Presets**, Tip `(0,212)`, berechnete Komponenten-Gaps überall `0.0 px`.
- Builder-QA: **9 Kombinationen**, darunter Original, isolierter Point-, Barrel-, Shaft-, Flight- und Rear-System-Swap sowie drei Stresstests.
- Software-Pose-QA: **16 Preset-Galerien**, maximale gemeldete Tip-Drift `0.0 px`.
- Barrel→Shaft/Rear-Anschluss: vorhandene Seam-Invariante bleibt aktiv und wird durch den Geometrietest geprüft.
- Headless Browser/WebGL in dieser Chat-Sandbox: **BLOCKED** (`ERR_BLOCKED_BY_ADMINISTRATOR` für localhost); nicht als PASS ausgegeben.

## V1.2 – Spieler-Darts

Neu enthalten: Gabriel Clemens G2 23g, Gabriel Clemens 95K 23g, Rob Cross 95K 23g, Nathan Aspinall 95K 22g, Stephen Bunting 95K 23g, Michael van Gerwen Signature 22g und Luke Humphries Prestige 22g.

Die Produktgeometrie und Komponentenangaben sind `WEB-VERIFIED`. Die öffentlichen Produktbilder wurden als visuelle Referenz recherchiert und ihre URLs im Katalog gespeichert. Da externe Bildbytes in dieser Ausführungsumgebung nicht zuverlässig in den Container heruntergeladen werden können, sind die lokalen Player-Texturen **keine Herstellerpixel**, sondern klar markierte `WEB-REFERENCED-RECONSTRUCTION` / `HEURISTIC` Assets. Plane B bleibt `APPROXIMATED`. Der Browser zeigt bei verfügbarem Internet die recherchierte externe Produktreferenz und fällt bei Fehler auf die lokale Rekonstruktion zurück.

## Harte Invarianten

| Kriterium | Status |
|---|---|
| 789×331 Renderer-Vertrag | PASS |
| Tip `(0,212)` | PASS |
| V4: zwei vollständige 90°-Flight-Ebenen | PASS |
| `axis Vec3 + roll` / `screenRotation` außerhalb 3D | PASS |
| keine `flatPerspective` im 3D-Pfad | PASS |
| Barrel/Shaft sichtbare Anschlussdicke | PASS per Geometrietest |
| integrierte Rear-Systeme bleiben eine Einheit | PASS |
| strikte Evidence-Vokabeln | PASS |
| neue Web-Visuals nicht als SOURCE-GROUNDED ausgegeben | PASS |
| GitHub verändert | **NEIN**, Repository blieb read-only |

## Offener Punkt

Der echte Three.js/WebGL-Browserlauf muss weiterhin auf einer normalen Workstation ausgeführt werden (`npm install`, `npm run serve`, `python scripts/browser_qa.py`). Alle hier ausführbaren statischen, Daten-, Geometrie-, Reset-, Syntax- und Software-Pose-Tests sind grün.
