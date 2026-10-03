# xConfig Dart Component Builder – Reference POC

Lokaler, **außerhalb des GitHub-Repositories** erstellter Referenz-POC für einen modularen Dart-Builder. Er verwendet das akzeptierte V4-Flightmodell: zwei vollständige, sich auf derselben Längsachse im Winkel von 90° schneidende Flight-Ebenen. Der Renderer ist Three.js-basiert, rendert bei Bedarf auf ein transparentes `789 × 331`-Sprite und verankert den Tip bei `(0,212)`.

## Start

### Windows

`START_POC.cmd` doppelklicken.

### Linux / macOS

```bash
./START_POC.sh
```

Danach im Browser `http://localhost:4173/` öffnen. Der POC versucht zuerst `node_modules/three`. Falls `npm install` noch nicht ausgeführt wurde, nutzt er einen jsDelivr-CDN-Fallback.

Für einen komplett lokalen Betrieb ohne CDN:

```bash
npm install
npm run serve
```



## Update V1.2 – weitere Spieler-Darts

Der lokale Builder enthält jetzt zusätzlich sieben recherchierte Spieler-Presets:

- **Gabriel Clemens G2 23g** – klassisch: Swiss Point + Pro Grip + No.6
- **Gabriel Clemens 95K 23g** – integriertes No.6 K-Flex
- **Rob Cross 95K 23g** – integriertes No.6 K-Flex
- **Nathan Aspinall 95K 22g** – integriertes No.2 K-Flex
- **Stephen Bunting 95K 23g** – integriertes No.2 K-Flex
- **Michael van Gerwen Signature Edition 22g** – klassisch: Vecta + #2 Flight
- **Luke Humphries Prestige 22g** – klassisch: Nitrotech + Standard Flight

Produktmaße und Komponenten werden als `WEB-VERIFIED` aus Hersteller-/Händlerquellen geführt. Die öffentlichen Produktbilder wurden recherchiert und visuell geprüft. Da die Ausführungsumgebung externe Bildbytes nicht in den lokalen Container herunterladen kann, sind die eingebetteten neuen Player-Assets bewusst als **WEB-REFERENCED RECONSTRUCTION** gekennzeichnet. Sie sind **nicht** als Original-Herstellerpixel oder `SOURCE-GROUNDED` deklariert. Die originalen Bildreferenz-URLs bleiben in `catalog.json` und `reports/15-player-darts-v1.2.md` erhalten.

## Update V1.1 – Übergang und Pose-Steuerung

Auf Basis des Praxisfeedbacks wurden zwei Bereiche gezielt korrigiert:

- **Barrel → Shaft/Rear-System:** Die sichtbare Dicke an der Naht wird jetzt dynamisch aus der Alpha-Silhouette beider verwendeten Texturen bestimmt; deren Provenienz kann source-grounded oder bei den neuen Web-Presets klar als Reconstruction markiert sein. Transparenter Bildrand zählt nicht mehr als Bauteildicke. Barrel und Shaft treffen sich dadurch sichtbar mit derselben Anschlussdicke. Die Korrektur erfolgt nur lokal am Übergang; der Barrel behält außerhalb der Anschlusszone seine eigene Dicke.
- **Pose-Steuerung:** Der Builder trennt nun drei Regler sichtbar: `Bildschirmrotation`, `Incidence` und `Roll`. Die Bildschirmrotation wird ausdrücklich **nach** dem 3D-Render tip-verankert angewandt und simuliert damit den späteren xConfig-`rotateGroup`, ohne `screenRotation` in den 3D-Renderer einzumischen.
- **Roll/Flight:** Transparente Flight-Ebenen werden nach Kameratiefe sortiert. Dadurch reagiert die Darstellung bei Roll stabiler und die beiden Plane-Meshes hängen nicht mehr an derselben Sortierposition.
- **UI-Renderpfad:** Slider-Updates werden über `requestAnimationFrame` zusammengefasst; veraltete asynchrone Renderläufe dürfen neuere Zustände nicht mehr überschreiben.

Neue Tests prüfen die sichtbare Nahtgleichheit sowie die harte Pivot-Invariante der Bildschirmrotation.

## Validierung

```bash
npm run validate
python scripts/qa_static.py
python scripts/software_pose_qa.py
```

Optionaler echter Browser-/WebGL-Test:

```bash
python scripts/browser_qa.py
```

In der Chat-Sandbox konnte dieser Browser-Test nicht bis `localhost` navigieren (`ERR_BLOCKED_BY_ADMINISTRATOR`). Das ist in `outputs/qa/browser-qa.json` dokumentiert. Katalog-, Kompatibilitäts-, Syntax-, statische Render- und unabhängige Pose-QA laufen lokal ohne GitHub-Zugriff.

## Wichtige Architekturregeln

- `PointDefinition`, `BarrelDefinition`, `ShaftDefinition`, `FlightDefinition`, `RearSystemDefinition`, `DartPreset` sind getrennte Datenobjekte.
- Swiss-Point und klassische Press-Fit-Points sind nicht austauschbar.
- Die hintere Barrel-Schnittstelle ist separat als `2BA` modelliert.
- Ein integriertes Rear-System wie K-Flex/K-Shift ersetzt **Shaft + Flight als eine Baugruppe**.
- Flights aus den 15 gelieferten Quellen verwenden source-grounded Plane A. Die sieben neuen web-recherchierten Player-Designs verwenden ausdrücklich `HEURISTIC` Plane A, weil die lokalen Visuals Rekonstruktionen sind; Plane B bleibt jeweils `APPROXIMATED`, solange keine zweite belastbare Ansicht vorliegt.
- Es werden keine Flight-Logos gespiegelt, um unbekannte Rückseiten zu erfinden.
- `screenRotation` ist nicht Bestandteil des 3D-Renderers.
- `flatPerspective` ist für den 3D-Pfad ausgeschaltet.
- Point/Barrel/Shaft sind in diesem POC bewusst Textur-Ribbons; bei gelieferten Quellen source-grounded, bei den neuen Web-Presets klar als Rekonstruktion markiert; das Flightkreuz ist echte räumliche Geometrie. Ein hochwertiges rotationssymmetrisches Barrel-Mesh ist ein späterer Schritt.

## Ordner

- `data/` – Katalog, Klassifikation aller 15 gelieferten Quellen, Web-Player-Referenzen und Authoring-Metadaten
- `assets/components/` – extrahierte modulare Komponenten
- `src/` – Builder, Kompatibilitätslogik, Three.js-Renderer
- `outputs/comparisons/` – Produktbild-vs-Preset-Vergleiche
- `outputs/gallery/` – Pose- und freie Kombinations-QA
- `outputs/qa/` – maschinenlesbare QA-Ergebnisse
- `reports/` – Analyse, Web-Recherche, Red Team, Grenzen und Validierungsbericht
- `tests/` – Katalog-/Vertragsinvarianten

## GitHub

Der POC verändert `thomasasen/autodarts-xconfig` nicht. Der Repository-Stand wurde ausschließlich read-only abgeglichen.
