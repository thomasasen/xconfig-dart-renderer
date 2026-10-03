# Arbeitsauftrag: Modularer Dart Component Builder + Presets

Du arbeitest weiter am Projekt:

`https://github.com/thomasasen/autodarts-xconfig`

Fokus:

`src/features/dart-marker-replacer`

Nutze vollständig die mitgelieferte Kontextdatei `xconfig-dart-realismus-kontext-masterprompt-v2.md` sowie den mitgelieferten V4-Referenz-POC.

Die grundlegende Problematik der realistischen Dartdarstellung gilt als verstanden. Beginne **nicht** wieder mit allgemeinen Diskussionen über PNG-Rotation, Skew, 2D vs. 3D oder Rendererwahl.

## Harte GitHub-Regel

Das GitHub-Repository bleibt vollständig **READ-ONLY**.

Ohne ausdrückliche Freigabe des Benutzers:

- keine Dateien im Repository ändern
- keine Commits
- keine Branches
- keine Pull Requests
- nichts mergen
- keine Assets ersetzen
- keine Issues oder sonstigen Schreibaktionen

Du darfst den aktuellen Stand auf `main` vollständig lesen und analysieren. Alle neuen POCs entstehen ausschließlich außerhalb des Repositorys.

---

# Mitgelieferte Dateien

Dieses Paket enthält:

1. `context/xconfig-dart-realismus-kontext-masterprompt-v2.md`
2. `reference-poc/dart-realism-reference-poc/` – aktueller akzeptierter V4-Referenz-POC
3. `dart-sources/darts/` – Produkt- und Referenzbilder für weitere Darts
4. `README_START_HERE.md`
5. diese Datei

Die früheren V1–V3-POCs sind absichtlich nicht enthalten. Sie enthalten Flight-Ansätze, die inzwischen verworfen wurden.

---

# Ausgangslage: V4 ist die visuelle Referenz

Der Flight-Renderer wurde mehrfach iteriert. Der aktuelle Referenzstand ist ausschließlich der mitgelieferte **V4-POC**.

Der Benutzer hat den V4-Stand visuell als gut bestätigt. Deshalb gilt:

- V4 nicht ohne klare neue Evidenz durch ältere Ansätze ersetzen.
- keine Rückkehr zu vier unabhängig wirkenden Flight-Sprites oder Rotor-/Blumenformen.
- die funktionierende V4-Flightgeometrie als Ausgangspunkt erhalten und verallgemeinern.

Zentrale Flight-Geometrie in V4:

- normaler Dartflight besitzt vier Finnen
- sinnvoll modelliert als zwei vollständige, sich kreuzende Ebenen
- beide Ebenen schneiden sich exakt entlang derselben Dart-Längsachse
- Ebenen stehen 90° zueinander
- Roll dreht die gesamte Kreuzstruktur um die Dartachse
- keine Finne darf sich durch Roll longitudinal verschieben
- kein vervielfachter Composite-Flight
- keine Rotor-/Blumen-/Propellerdarstellung
- keine künstliche Doppelperspektive

---

# Bestehende technische Grundregeln

Prüfe den aktuellen Stand auf `main` erneut read-only. Der bisherige Vertrag lautet:

```text
Export: 789 × 331
Tip:    (0,212)
```

Der Tip ist eine harte Invariante. Keine Pose, Perspektive oder Komponentenkombination darf sichtbaren Tip-Drift erzeugen.

Das Posemodell bleibt grundsätzlich:

```text
axis Vec3 + roll
```

Für die spätere xConfig-Integration gilt weiterhin:

```text
3D-Renderer:
- incidence
- roll
- räumliche Geometrie
- Perspektive

bestehender SVG rotateGroup:
- screenRotation
```

`flatPerspective` darf im 3D-Pfad **nicht** zusätzlich angewendet werden.

Shadow, Wobble und Fluganimation sind für diesen Builder-POC zunächst nicht das Hauptthema.

---

# Neues Ziel: Modularer Dart Component Builder

Baue außerhalb des GitHub-Repositories einen modularen **DART COMPONENT BUILDER**.

Der Benutzer soll einen Dart aus Einzelkomponenten zusammenstellen können.

Mindestens:

1. Point / Spitze
2. Barrel
3. Shaft / Schaft
4. Flight

Zusätzlich müssen integrierte Systeme unterstützt werden, bei denen Shaft und Flight konstruktiv zusammengehören, z. B.:

- Target K-Flex
- Target K-Shift
- andere molded / integrated rear systems

Solche Systeme dürfen **nicht künstlich in zwei frei kombinierbare Komponenten zerlegt** werden, wenn sie konstruktiv ein System darstellen.

Dafür soll eine eigene Entität existieren, z. B.:

```text
RearSystemDefinition
```

oder sinngemäß `ShaftFlightSystemDefinition`.

---

# Zweites zentrales Ziel: Presets

Zusätzlich zum freien Builder müssen fertige **Presets** existieren.

Jeder geeignete im Ordner `dart-sources/darts/` abgebildete Dart soll möglichst als Preset angelegt werden.

Ein Preset soll den Dart so rekonstruieren, wie er auf dem jeweiligen Produktbild dargestellt ist.

Beispiel:

```text
Preset: Target Luke Littler G1 Prodigy 23g

point  = passende Point-Komponente
barrel = passendes Barrel
rear   = passendes K-Flex-/Rear-System
```

Der Benutzer soll:

1. ein fertiges Preset laden können
2. anschließend – sofern konstruktiv sinnvoll – einzelne Komponenten ändern können
3. jederzeit auf das Original-Preset zurücksetzen können

Ein Preset ist **kein Screenshot** und darf nicht einfach das komplette Produktbild als Sprite verwenden.

Prinzip:

```text
Produktbild
→ Komponenten analysieren
→ Point
→ Barrel
→ Shaft / RearSystem
→ Flight
→ Presetdefinition
→ Renderer
```

Der Sinn des Builders ist ausdrücklich die Trennung der Komponenten.

---

# Quellmaterial vollständig analysieren

Analysiere **alle** Bilder in `dart-sources/darts/` zuerst.

Aktuell enthalten sind u. a.:

- `190840STARWARSMANDALORIAN95_STEElTIP_GALLERY_DE_PT01.webp`
- `190843-STARWARSAT-AT90_STEELTIP_GALLERY_DE_PT01.webp`
- `9GHHawNA.webp`
- `GNGTP_Gnasha-Angled.webp`
- `PT01_a83f80b3-c589-4f2e-85c1-7cf911048504.webp`
- `PT02_ffd9f2ed-6a52-43e8-9f62-027742ec8be4.webp`
- `PW2022_SupaVenom_Steel_LEFT.webp`
- `S5-1_22b0f7a4-0463-42e0-8623-49ef67353563_1.webp`
- `S5-1_d5e583f9-5bbe-4728-b176-4f516d0960b3.webp`
- `shot-alchemy-auro-90_3.webp`
- `target-luke-littler-g1-prodigy-95-swiss-23-gram_3.webp`
- `target-luke-littler-world-champion-90-swiss-23-gram_3.webp`
- `target-phil-taylor-power-chrono-sp-steeltip-95_3.webp`
- `target-shift-sp-steeltip-90_3.webp`
- `unicorn-w-c-gary-anderson-phase-6-90_1.webp`

Erstelle für jedes Bild eine Klassifikation:

- `CLASSIC_MODULAR`
- `INTEGRATED_REAR_SYSTEM`
- `GEOMETRY_REFERENCE`
- `ANGLED_REFERENCE`
- `NEEDS_MANUAL_REVIEW`

Begründe die Zuordnung.

---

# Quelltreue und Evidenzstatus

Unterscheide bei sämtlichen Daten streng zwischen:

**SOURCE-GROUNDED**  
Tatsächlich aus dem Produktbild ersichtlich.

**WEB-VERIFIED**  
Über Hersteller oder belastbare Produktquelle verifiziert.

**HEURISTIC**  
Geometrisch plausibel ergänzt.

**APPROXIMATED**  
Nicht sichtbare Information angenähert.

**UNKNOWN**  
Nicht zuverlässig bestimmbar.

Erfinde keine Maße, Logos, Rückseiten, Materialdetails oder Modellvarianten.

Wenn ein Produkt mit mehreren Gewichtsvarianten unterschiedliche Barrelmaße besitzt und das Bild die Variante nicht eindeutig bestimmt: **nicht raten**.

Stattdessen:

- Variante markieren
- Herstellerdaten recherchieren
- Unsicherheit dokumentieren

---

# Web-Recherche für Produktdaten

Für klar identifizierbare Produkte sollst du aktuelle offizielle Herstellerseiten bzw. belastbare Produktquellen recherchieren.

Ziel:

- Modellname
- Gewicht
- Barrel-Länge
- Barrel-Durchmesser
- Point-Typ und Point-Länge
- Shaft-Typ und Länge
- Flight-Form
- integriertes Rear-System
- verwendete Produktkomponenten

Quellenpriorität:

1. Hersteller
2. offizielle Händler / Distributoren
3. seriöse Dartshops

Kennzeichne externe Daten als `WEB-VERIFIED`.

Produktbilder bleiben die primäre Designquelle.

---

# Datenmodell

Entwickle ein sauberes, erweiterbares Datenmodell.

Mindestens folgende Entitäten:

- `PointDefinition`
- `BarrelDefinition`
- `ShaftDefinition`
- `FlightDefinition`
- `RearSystemDefinition`
- `DartPreset`

Beispielhaft:

```js
PointDefinition {
  id,
  label,
  geometry,
  dimensions,
  appearance,
  source,
  compatibility
}

BarrelDefinition {
  id,
  label,
  lengthMm,
  maxDiameterMm,
  profile,
  appearance,
  gripZones,
  source,
  compatibility
}

ShaftDefinition {
  id,
  label,
  lengthMm,
  profile,
  appearance,
  source,
  compatibility
}

FlightDefinition {
  id,
  label,
  shape,
  geometryProfile,
  texture,
  transparency,
  knownFaces,
  unknownFaces,
  rollPolicy,
  source
}

RearSystemDefinition {
  id,
  label,
  shaftGeometry,
  flightGeometry,
  integrationType,
  appearance,
  source,
  compatibility
}

DartPreset {
  id,
  label,
  sourceImage,
  components: {
    point,
    barrel,
    shaft,
    flight,
    rearSystem
  },
  lockedGroups,
  sourceStatus
}
```

Das Schema darf verbessert werden, wenn dafür eine klare technische Begründung besteht.

---

# Kompatibilität

Der Builder darf nicht jede beliebige Kombination blind erlauben.

Führe ein einfaches Kompatibilitätsmodell ein.

Mindestens unterscheiden:

- klassische 2BA-Verbindung
- Swiss Point / andere Point-Systeme
- klassischer Shaft
- normaler Flight
- integriertes Rear-System

Der POC muss keine vollständige weltweite Dart-Normdatenbank enthalten. Offensichtlich inkompatible Kombinationen sollen aber nicht als valide dargestellt werden.

---

# Presets: Priorität

Lege für möglichst viele geeignete Bilder Presets an.

Priorisiere zuerst mindestens:

1. Target Luke Littler G1 Prodigy
2. Target Shift
3. Unicorn Gary Anderson Phase 6
4. Target Phil Taylor Power Chrono
5. Target Luke Littler World Champion
6. Shot Alchemy Auro
7. Supa Venom
8. mindestens einen Dart aus den Maß-/Produktgrafiken

Danach weitere geeignete Quellen.

Ein Preset muss reproduzierbar sein und soll visuell möglichst den jeweiligen Produktdart ergeben.

---

# Point

Points dürfen zunächst relativ einfach geometrisch modelliert werden.

Mindestens berücksichtigen:

- Länge
- Durchmesser
- Konus / Spitze
- Farbe
- ggf. sichtbare Grip-/Groove-Bereiche

Source-grounded Textur ist optional, wenn einfache Geometrie visuell besser funktioniert.

---

# Barrel

Barrels sind visuell wichtig.

Versuche zu erfassen:

- reale Barrel-Silhouette
- Länge
- Durchmesserverlauf
- Taper
- Scallop
- Grip-Zonen
- Farbzonen
- Beschichtungen

Vermeide Doppelbeleuchtung. Ein Produktfoto enthält bereits Beleuchtung. Wenn Textur verwendet wird, darf darauf nicht unkritisch ein starkes virtuelles Materiallicht gelegt werden.

---

# Shaft

Bei klassischen Shafts modellieren:

- Länge
- Durchmesser
- Form
- Farbe
- Übergang zum Barrel
- Übergang zum Flight

Bei integrierten Systemen **nicht künstlich separieren**.

---

# Flight

Nutze die Erkenntnisse und den funktionierenden Stand aus V4.

Ein normaler Flight:

- vier Finnen
- zwei vollständige sich kreuzende Ebenen
- gemeinsame Dart-Längsachse
- exakt 90° zueinander
- Roll dreht die Kreuzstruktur
- keine longitudinalen Verschiebungen
- keine Rotor-/Blumenwirkung

Für unterschiedliche Flightformen muss das Geometrieprofil austauschbar sein.

Mindestens vorbereiten für:

- No.2 / Standard
- No.6
- Slim
- weitere Formen aus dem Quellmaterial

Flight-Artwork und Flight-Geometrie müssen getrennt bleiben.

---

# Builder-UI

Baue eine einfache, funktionale POC-Oberfläche.

Mindestens:

```text
PRESET
[ Dropdown ]

POINT
[ Dropdown ]

BARREL
[ Dropdown ]

SHAFT / REAR SYSTEM
[ Dropdown ]

FLIGHT
[ Dropdown ]
```

Zusätzlich:

- Reset auf Preset
- aktuelle Zusammenstellung anzeigen
- SOURCE-GROUNDED-/WEB-VERIFIED-/APPROXIMATED-Status anzeigen
- inkompatible Kombinationen deaktivieren oder klar kennzeichnen

Wenn ein `RearSystem` aktiv ist:

- Shaft- und Flight-Auswahl entsprechend sperren oder ersetzen

---

# Vorschau

Die Vorschau soll den zusammengesetzten Dart mit dem bestehenden V4-Renderer darstellen.

Mindestens:

- orthogonale Designansicht
- eine realistische Standardpose
- Incidence-Regler
- Roll-Regler

`screenRotation` gehört weiterhin **nicht** in den 3D-Renderer.

---

# Preset-QA

Für jedes Preset soll ein Vergleich erzeugt werden:

```text
Produktbild
vs.
Builder-Preset
```

Zu prüfen:

- Gesamtlänge
- Point-Proportion
- Barrel-Länge
- Barrel-Durchmesser
- Shaft-Länge
- Flightgröße
- Flightform
- Farben
- charakteristische Designmerkmale
- Übergänge zwischen Komponenten

Kein Preset gilt als gut, nur weil alle Komponenten technisch geladen werden. Es muss visuell den Produktdart erkennbar reproduzieren.

---

# Builder-QA

Teste zusätzlich freie Kombinationen.

Mindestens:

1. Original-Preset
2. Point austauschen
3. Barrel austauschen
4. Shaft austauschen
5. Flight austauschen
6. komplettes RearSystem austauschen

Prüfe dabei:

- keine Lücken
- keine Überlappungsfehler
- keine falschen Maßstäbe
- kein Tip-Drift
- kein Flight-Drift
- saubere Komponentenanschlüsse
- glaubwürdige Gesamtproportion

---

# Normalisierung

Interne Geometrie soll möglichst mit realen bzw. relativen physikalischen Maßen arbeiten.

```text
Bildpixel ≠ Geometriemaß
```

Wo reale Millimeterwerte vorhanden sind: nutzen.

Wo nicht: aus bekannten Referenzen oder Verhältnissen approximieren und entsprechend kennzeichnen.

---

# Renderer

Three.js bleibt für diesen POC der Referenzrenderer.

Noch kein OGL-Port.

- kein permanenter Renderloop
- Shared Renderer
- render on demand

Weiterhin:

```text
Export: 789×331
Tip:    (0,212)
```

---

# Noch nicht tun

Noch nicht:

- GitHub-Integration
- produktive xConfig-UI
- Shadow perfektionieren
- Wobble
- Flight-Animation
- OGL
- WebGPU
- große Performanceoptimierung
- automatische KI-Segmentierung aller Designs

Zuerst muss der Komponenten-Builder visuell funktionieren.

---

# Red Team

Nach dem ersten funktionierenden Stand stelle ein Red Team zusammen aus mindestens:

- Technical Artist
- Three.js/WebGL Engineer
- Dartspieler / Dart-Hardware-Kenner
- Product-Design-Reconstruction Reviewer
- UX-/Builder-Reviewer
- skeptischem visuellen Reviewer

Prüfe mindestens:

- Sind Komponenten wirklich modular oder nur optisch ausgeschnitten?
- Sind Presets originalgetreu genug?
- Ist ein K-Flex korrekt als integriertes System behandelt?
- Sind klassische Flights korrekt getrennt?
- Stimmen Größenverhältnisse?
- Stimmen Komponentenübergänge?
- Wird irgendwo ein komplettes Produktbild nur kaschiert?
- Werden unbekannte Rückseiten erfunden?
- Gibt es Doppelbeleuchtung?
- Ist der Barrel zu flach?
- Ist der Flight weiterhin geometrisch korrekt?
- Bleibt der Tip stabil?
- Funktioniert Roll?
- Funktioniert Incidence?
- Gibt es inkompatible Builder-Kombinationen?
- Funktioniert Reset auf Preset?
- Kann ein Preset nach manuellen Änderungen zuverlässig wiederhergestellt werden?
- Sind SOURCE-GROUNDED / WEB-VERIFIED / HEURISTIC / APPROXIMATED / UNKNOWN sauber getrennt?

Gefundene Probleme nicht nur dokumentieren.

Danach:

1. Ursache bestimmen
2. POC korrigieren
3. neu rendern
4. Presets erneut vergleichen
5. Builder erneut testen
6. Red-Team-Nachprüfung

---

# Akzeptanzkriterien

Der POC ist erfolgreich, wenn:

1. der Benutzer einen Dart aus Komponenten zusammenstellen kann
2. Points austauschbar sind
3. Barrels austauschbar sind
4. klassische Shafts austauschbar sind
5. klassische Flights austauschbar sind
6. integrierte Rear-Systeme korrekt unterstützt werden
7. mehrere Presets aus dem Quellpaket existieren
8. Presets die abgebildeten Produktdarts plausibel reproduzieren
9. Komponenten maßstäblich zueinander passen
10. keine sichtbaren Anschlussfehler entstehen
11. der V4-Flight nicht regressiert
12. Tip `(0,212)` stabil bleibt
13. Roll geometrisch korrekt bleibt
14. Incidence geometrisch korrekt bleibt
15. Evidenzstatus sauber dokumentiert werden
16. Preset → manuelle Änderung → Reset auf Preset funktioniert
17. keine Änderungen am GitHub-Repository vorgenommen wurden

---

# Erwartetes Ergebnis

Liefere am Ende:

1. vollständige Analyse aller Dart-Quellen
2. Klassifikation aller Quellen
3. Komponenten-Inventar
4. Preset-Inventar
5. Datenmodell
6. Kompatibilitätsmodell
7. Builder-UI
8. funktionierenden Three.js-POC
9. mehrere fertige Presets
10. freie Beispielkombinationen
11. Produktbild-vs-Preset-Vergleiche
12. QA-Galerien
13. Red-Team-Ergebnisse
14. nach Red-Team korrigierte Endversion
15. dokumentierte Grenzen
16. Liste noch unsicherer Produktdaten
17. Einschätzung, welche Designs weitere Produktansichten benötigen
18. vollständigen aktualisierten POC als ZIP

Keine GitHub-Änderungen.

---

# Oberstes Qualitätskriterium

Bei einem Preset soll ein Mensch sagen:

> „Das ist dieser konkrete Dart.“

Beim Builder soll ein Mensch sagen:

> „Das sieht wie ein tatsächlich aus diesen Teilen gebauter Dart aus.“

Nicht:

> „Mehrere Produktbilder wurden nebeneinander geklebt.“

Arbeite iterativ und höre nicht beim ersten technisch funktionierenden Stand auf.
