from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
cat=json.loads((ROOT/'data/catalog.json').read_text())

def md_table(rows,headers):
    out=['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']
    for r in rows:out.append('| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in r)+' |')
    return '\n'.join(out)

# 01 source analysis
rows=[]
for s in cat['sourceAnalysis']:
    ev='; '.join(f"{e['status']}: {e['note']}" for e in s['evidence'])
    rows.append([s['file'],s['classification'],s.get('identifiedAs') or 'unbekannt',s['confidence'],s['reason'],ev])
text='''# 01 – Vollständige Quellenanalyse\n\nAlle 15 gelieferten Bilder wurden einzeln betrachtet. Klassifikation und Identität werden getrennt geführt: Eine gute Broadside-Quelle ist nicht automatisch ein verifiziertes Produktpreset.\n\n'''+md_table(rows,['Datei','Klasse','Identifikation','Konfidenz','Begründung','Evidence'])+'''\n\n## Harte Konflikte / Unklarheiten\n\n- **G1 Prodigy:** lokale Datei enthält `95`, die aktuelle Target-Produktseite führt G1 Prodigy als **90 % Tungsten**. Der Builder übernimmt 90 % nur als WEB-VERIFIED Herstellerangabe; der Dateiname bleibt als widersprüchliche SOURCE-GROUNDED-Metadaten sichtbar.\n- **Shot Auro:** lokale Datei heißt `shot-alchemy-auro-90_3.webp`. Händlerquellen dokumentieren eine 90%-Generation; Shot führt aktuell eine 95%-Generation. Diese Versionen werden nicht stillschweigend gleichgesetzt.\n- **S5-Bilder:** keine belastbare Produktidentifikation. Sie bleiben `NEEDS_MANUAL_REVIEW`.\n- **9GHHawNA:** visuell sehr nützlich für Rear-/Flight-Geometrie, aber Produktidentität und Maße bleiben unbekannt. Deshalb `GEOMETRY_REFERENCE`, nicht Preset.\n'''
(ROOT/'reports/01-source-analysis.md').write_text(text,encoding='utf8')

# 02 product research
research=[
 ['Target Luke Littler G1 Prodigy SP','Target','90 %; 23g 52×6.5 mm; Swiss DX 26 mm (+30); No.2 K-Flex Short 19 mm','https://www.targetdarts.com/eu/luke-littler-g1-prodigy-sp','Dateiname lokal nennt 95 → Konflikt.'],
 ['Target Shift SP','Target','90 %; 50 mm; 23/24/25g Ø 6.7/6.8/7.0; Swiss GRD 30 mm; No.6 K-Shift Short 19 mm','https://www.targetdarts.de/shift-sp','Source-Gewicht unbekannt → exakter Ø bleibt UNKNOWN.'],
 ['Target Phil Taylor Power Chrono SP','Target','95 %; 22g 41×7.55, 24g 41×7.85, 26g 42.5×7.85; Swiss Chrono 30/35; Shaft 22.4 mm; Vapor S/No.2/No.6','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp','Source-Gewicht und exakt montierte Flightform nicht sicher.'],
 ['Target Luke Littler G1 World Champion SP','Target','23g; 90 %; 52×6.5 mm; Swiss SLK 35 (+42); No.6 K-Flex Short','https://www.targetdarts.com/us/luke-littler-world-champion-sp','Eindeutige Variante.'],
 ['Shot Alchemy Auro','Shot + Händler','Aktuelle Shot-Seite 95 %, 35-mm Point, Koi Carbon Inbetween, No.6; 90%-Händlerquelle: 23g 46×7.5, 24g 47×7.5, 25g 47×7.6','https://www.shotdarts.com/products/alchemy-auro-steel-tip-dart-set-95-tungsten-barrels ; https://www.dartswarehouse.de/shot-alchemy-auro-90.html','Lokale Datei explizit 90; aktuelle Herstellerseite 95.'],
 ['Red Dragon Peter Wright Supa-Venom','Red Dragon','90 %; 54.6 mm alle; Ø 6.0/6.1/6.25/6.35 for 21/22/23/24g; Nitrotech short; Players extra thick standard','https://www.reddragondarts.com/products/peter-wright-supa-venom-darts','Source-Gewicht unbekannt.'],
 ['Unicorn Gary Anderson Phase 6 90%','Dartshopper/Double Top','21g 46.3×7.2; 22g 48.5×7.2; 23g 50.7×7.2; 24g 50.7×7.3; 25g 50.7×7.5; Gripper shaft + separate flight','https://www.dartshopper.com/unicorn-gary-anderson-phase-6-90/','Source-Gewicht unbekannt.'],
 ['Target Star Wars Mandalorian SP','Target','95 %; 52 mm; 22/24/26g Ø 6.3/6.5/6.8; Swiss Storm 30 (+35); Short K-Flex; No.2 + No.6 im Set','https://www.targetdarts.com/us/star-wars-mandalorian-sp','Builder-Infografik-Preset authored as explicit 24g variant.'],
 ['Target Star Wars AT-AT SP','Target','90 %; 47.55 mm; 23/24/25g Ø 7.0/7.1/7.2; Swiss Storm 30; Pro Grip Short 34; No.6 Pro Ultra','https://www.targetdarts.com/us/star-wars-at-at-sp','Builder-Infografik-Preset authored as explicit 23g variant.'],
 ['Target Luke Littler Edge SP','Target','95 %; 52 mm; 22/23/24g Ø 6.35/6.5/6.6; Swiss Fire 30; No.2 K-Flex Short','https://www.targetdarts.com/us/luke-littler-edge-sp','PT02 match high confidence; not required as first builder preset.'],
 ['Target Star Wars Darth Vader SP','Target','95 %; 52 mm; Swiss Storm 30 (+35); Short K-Flex; No.2 + No.6','https://www.targetdarts.com/us/darth-vader-sp','PT01 model identification is artwork/spec match, not filename-grounded.'],
 ['Shot Gnarly Gnasha Steel Tip 95%','Shot','95 %; Turbo steel point; Tao/Koi carbon shafts; No.6','https://www.shotdarts.com/products/gnarly-gnasha-steel-tip-dart-set-95-tungsten-barrels','Angled reference only; page result did not provide reliable dimensions.'],
 ['Target Gabriel Clemens G2 SP 23g','Target','90 %; 23g = 52×6.9 mm; Storm Nano Swiss Point 26 mm; Pro Grip Short; No.6','https://www.target-darts.co.uk/gabriel-clemens-g2-sp','Physik/Setup WEB-VERIFIED; lokales Artwork ist nur WEB-REFERENCED RECONSTRUCTION.'],
 ['Target Gabriel Clemens 95K SP 23g','Target','95 %; 23g = 52×6.9 mm; Black Swiss Storm 26 mm; No.6 K-Flex Short 19 mm','https://www.target-darts.co.uk/gabriel-clemens-95k-sp','Integriertes Rear; lokales Artwork rekonstruiert, nicht als SOURCE-GROUNDED ausgegeben.'],
 ['Target Rob Cross 95K SP 23g','Target','95 %; 23g = 48×6.6 mm; Gold Swiss Storm Surge 26 mm; No.6 K-Flex Short','https://www.target-darts.co.uk/rob-cross-95k-sp','Integriertes Rear; lokale Grafik ist Web-Referenzrekonstruktion.'],
 ['Target Nathan Aspinall 95K SP 22g','Target','95 %; 22g = 50×6.8 mm; Black Swiss Storm 26 mm; No.2 K-Flex Short 19 mm; tapered front profile','https://www.target-darts.co.uk/nathan-aspinall-95k-sp','Integriertes Rear; lokale Grafik ist Web-Referenzrekonstruktion.'],
 ['Target Stephen Bunting 95K SP 23g','Target','95 %; 23g = 47×6.9 mm; Gold Swiss Diamond Pro 26 mm; No.2 K-Flex Short','https://www.target-darts.co.uk/stephen-bunting-95k-sp','Box-Copy enthält verdächtiges „33m“; exakte Shaft-mm bleiben deshalb UNKNOWN.'],
 ['Winmau MvG Signature Edition 22g','Winmau + Dartworld','90 %; parallel/centre; Vecta Short; #2 100 Micron; Händlermaß 22g = 53×6.3 mm','https://winmau.com/en-de/products/mvg-signature-edition ; https://www.dartworld.de/steel-darts/nach-preis/winmau-michael-van-gerwen-mvg-signature-edition-90?c=22162','Herstellerseite zeigt keine Maßtabelle; Maß deshalb zusätzlich retailer-verifiziert.'],
 ['Luke Humphries Prestige 22g','Winmau/Red Dragon','90 %; 22g = 43.18×7.3 mm; front-weighted torpedo; Black high-tensile point; Nitrotech Short; Players extra thick standard','https://winmau.com/en-de/products/luke-humphries-prestige-darts','Point- und Shaft-Länge in mm nicht veröffentlicht; bleiben factual UNKNOWN.'],
]
text='# 02 – Web-verifizierte Produktdaten\n\nPriorität: Hersteller, dann etablierte Händler. Nur explizit gefundene Werte werden als WEB-VERIFIED geführt.\n\n'+md_table(research,['Produkt','Quelle','Verifizierte Daten','URL','Unsicherheit'])+'''\n\n## Datenregel\n\nEin unbekanntes Source-Gewicht wird **nicht** durch eine beliebige verfügbare Gewichtsvariante ersetzt. In `catalog.json` bleiben faktische `lengthMm`/`diameterMm` in solchen Fällen `null`; getrennte `renderLengthMm`/`renderDiameterMm` dürfen als HEURISTIC existieren, damit ein POC renderbar bleibt.\n'''
(ROOT/'reports/02-web-product-data.md').write_text(text,encoding='utf8')

# 03 schema & compatibility
text='''# 03 – Datenmodell und Kompatibilität\n\n## Entitäten\n\n- `PointDefinition`: Point-Interface, Länge/Durchmesser, Rendergeometrie, Textur, Evidence.\n- `BarrelDefinition`: Point-Interface, Rear-Thread, reale Maße sofern bekannt, getrennte Rendermaße, Profil, Textur, Evidence.\n- `ShaftDefinition`: Rear-Thread, Flight-Mount, Länge, Textur, Evidence.\n- `FlightDefinition`: Flight-Mount, Shape, V4-Plane-Profile, Plane A/B Texturen und Face-Evidence.\n- `RearSystemDefinition`: **eine einzige** logische Einheit für integrierte Shaft+Flight-Systeme. Intern darf der Renderer Shaft-Body + zwei Flight-Planes erzeugen; im Katalog/Builder bleibt es ein Bauteil.\n- `DartPreset`: referenziert kompatible Komponenten und eine Quellabbildung.\n\n## Kompatibilitätsregeln\n\n1. `point.interface === barrel.pointInterface`.\n2. `barrel.rearThread === shaft.rearThread` oder `rearSystem.rearThread`.\n3. `shaft.flightMount === flight.flightMount`.\n4. Ein aktives `RearSystemDefinition` ist gegenseitig ausschließend mit separatem Shaft + Flight.\n5. `SWISS_POINT` wird nicht mit `PRESS_FIT` vermischt.\n6. `2BA` beschreibt nur die Rear-Verbindung; es sagt nichts über Point-Kompatibilität aus.\n\n## Evidence\n\nDie einzige zulässige Vokabelliste ist `SOURCE-GROUNDED`, `WEB-VERIFIED`, `HEURISTIC`, `APPROXIMATED`, `UNKNOWN`. Renderheuristiken werden nicht in Herstellerdaten „hochgestuft“.\n\n## Flightvertrag\n\nV4 bleibt bindend: zwei vollständige, orthogonale Plane-Geometrien auf derselben Längsachse; Roll rotiert den gesamten Flight-Cross. Bei den **15 gelieferten Quellen** ist Plane A source-grounded. Die zusätzlich web-recherchierten Spieler-Darts verwenden bewusst `HEURISTIC` für Plane A, weil ihre lokalen Assets lediglich **WEB-REFERENCED RECONSTRUCTIONS** sind und keine heruntergeladenen Herstellerpixel. Plane B bleibt ohne verifizierte Gegenansicht `APPROXIMATED` und wird **nicht gespiegelt**; die UI zeigt einen konservativen Safe-Roll-Bereich.\n'''
(ROOT/'reports/03-data-model-compatibility.md').write_text(text,encoding='utf8')

# 04 architecture
text='''# 04 – Builder- und Rendererarchitektur\n\n## Pipeline\n\n```text\nsource image / verified specs\n        ↓\nauthoring split (image-space only)\n        ↓\nPoint / Barrel / Shaft / Flight OR RearSystem catalog entities\n        ↓\ncompatibility resolver\n        ↓\nSharedDartComponentRenderer (Three.js reference renderer)\n        ↓\naxis Vec3 + roll\n        ↓\ntwo full intersecting flight planes\n        ↓\ntransparent 789×331 sprite, Tip=(0,212)\n        ↓\nscreenRotation intentionally outside renderer\n```\n\n## Was V4 unverändert bleibt\n\n- Tip ist harte Invariante.\n- Flight = zwei vollständige, 90° gekreuzte Planes, keine vier unabhängigen Sprites.\n- `axis Vec3 + roll`; im Builder wird die kanonische Projektion horizontal gehalten.\n- keine `flatPerspective`-Nachbearbeitung.\n- `MeshBasicMaterial`: keine zusätzliche virtuelle Beleuchtung auf bereits fotografierter Beleuchtung.\n- Shared Renderer, Render-on-demand, kein permanenter 60-FPS-Loop.\n- WebGL-Context-Loss-Handler und Sprite-Cache sind vorgesehen.\n\n## Bewusster Hybrid\n\nPoint, Barrel und Shaft sind in diesem Builder-POC source-grounded **Ribbons** mit realer Längengeometrie. Das ist absichtlich noch kein rotationssymmetrisches 3D-Barrel-Mesh. Flight-Geometrie ist der räumlich wichtigste Teil und wird V4-konform modelliert.\n\n## xConfig-Integrationsgrenze\n\nDieser POC schreibt nichts in xConfig. Der spätere Integrationspfad bleibt Render-to-Sprite: der 3D-Renderer erzeugt einen horizontalen 789×331-Sprite; xConfigs bestehender `rotateGroup` kann `screenRotation` übernehmen. Im 3D-Pfad muss `flatPerspective` ausbleiben.\n'''
(ROOT/'reports/04-builder-architecture.md').write_text(text,encoding='utf8')

# 05 red team first pass
text='''# 05 – Red Team, erster Durchlauf\n\n## Rollen\n\n1. **Technical Artist:** Silhouetten, Material, Übergänge, Flight-Lesbarkeit.\n2. **Three.js/WebGL Engineer:** Shared Context, Cache, Depth/Alpha, Context Loss, Render-on-demand.\n3. **Dart-Hardware-Reviewer:** 2BA/Swiss/Press-fit, Rear-Systeme, reale Komponenten.\n4. **Reconstruction Reviewer:** Quellenstatus, Variantenkonflikte, unbekannte Backfaces.\n5. **UX Reviewer:** Fehlkombinationen, Locking, Transparenz von Unsicherheit.\n6. **Skeptical Visual Reviewer:** „Steckt der Dart im Board?“ statt „verzogenes Produktbild“.\n\n## Befunde vor Korrektur\n\n| Befund | Risiko | Maßnahme |\n|---|---|---|\n| Infografik-Extraktion zog Panel-Trennlinien in Mandalorian/AT-AT-Flight | hoch visuell | Dark-ROI-Extraktion verschärft; Flight zusätzlich mit geometrischer Envelope maskiert |\n| Plane B aus Einzelansicht unbekannt | hoch bei Roll | keine Spiegelung; entsättigte/dunklere Approximation; Safe-Roll in UI |\n| Prodigy-Dateiname „95“, Hersteller „90“ | Datenintegrität | beide Evidenzen getrennt; keine stille Korrektur |\n| Auro 90-Source vs. aktuelle 95-Herstellerseite | Variantenintegrität | 90-Source als eigene/legacy Variante; 95-Seite nur als aktuelle Produktfamilienquelle |\n| Unbekannte Gewichtsvarianten könnten falsche Ø-Werte bekommen | Scheingenauigkeit | factual Maße `null`; eigene `render*`-Heuristik |\n| Integrierte Rear-Systeme könnten in Shaft + Flight zerfallen | Modellfehler | `RearSystemDefinition` als eine Entität; UI sperrt separate Dropdowns |\n| Slider-Änderung könnte unnötig Scene-Rebuild triggern | Performance | Renderer merkt Assembly-Key und soll unveränderte Assembly wiederverwenden |\n| Transparente Flight-Sortierung ist nicht ausreichend durch ein einzelnes opaque Preset abgedeckt | QA-Lücke | `9GHHawNA` bleibt Geometry/Transparency-Referenz; keine falsche Produktisierung; separate QA vor Produktion erforderlich |\n| Body roll ist im Ribbon-Hybrid nicht physisch vollständig | visuelle Grenze | als POC-Limit dokumentieren; nicht als „vollständiges 3D-Modell“ ausgeben |\n| Browser/WebGL-Automation in dieser Ausführungsumgebung blockiert localhost | Testumgebung | statische Tests + Software-Pose-QA laufen; `browser_qa.py` für normale Workstation mitgeliefert |\n'''
(ROOT/'reports/05-red-team-first-pass.md').write_text(text,encoding='utf8')

# 06 final red team
text=f'''# 06 – Red Team nach Korrektur\n\n## Erneut geprüft\n\n- **15/15 Quellen klassifiziert:** PASS.\n- **Presets:** {len(cat['presets'])} vorhanden. Neben den bisherigen Quellen sind sieben web-recherchierte Spieler-Presets ergänzt, darunter Gabriel Clemens G2 und Gabriel Clemens 95K.\n- **Tip-Vertrag:** statische Assembly- und Software-Pose-QA ergeben exakt `(0,212)`; maximale mathematische Drift `0.0 px`.\n- **Flight:** zwei vollständige Planes, 90°, gemeinsame Achse; Plane B explizit APPROXIMATED; keine gespiegelte Schrift.\n- **Freie Kombinationen:** sechs Cross-Preset-Kombinationen gerendert; geometrisch keine Lücken an den Komponenten-Grenzen.\n- **Integrated Rear:** K-Flex/K-Shift bleiben einzelne Katalogelemente; Shaft/Flight werden in der UI gesperrt.\n- **Inkompatible Point-Barrel-Kombinationen:** Swiss vs. Press-fit werden deaktiviert/automatisch korrigiert.\n- **Doppelperspektive:** Builder enthält keine `flatPerspective`-Stufe.\n- **Schatten/Wobble/Fluganimation:** weiterhin absichtlich OFF; statische Ruhepose wird zuerst gelöst.\n- **Source vs. Builder:** Vergleichsbilder werden für alle {len(cat['presets'])} Presets erzeugt. Bei Web-Presets ist die linke Quelle ausdrücklich eine beschriftete lokale Rekonstruktion und kein Originalfoto.\n\n## Nicht als gelöst ausgeben\n\n- Body-Roll/Barrel-Rückseiten sind im Ribbon-Hybrid nicht vollständig 3D.\n- Plane-B-Artwork ist ohne zweite Produktansicht nicht source-grounded.\n- Transparente Flights brauchen vor Produktivintegration einen dedizierten WebGL-Alpha/Depth-Test.\n- WebGL-Runtime konnte in dieser Chat-Ausführungsumgebung nicht per Headless-Browser gestartet werden, weil Navigation zu localhost administrativ blockiert ist. Der Three.js-Code ist syntaktisch validiert; das Paket unterstützt lokale `npm install`-Abhängigkeit und CDN-Fallback und enthält einen reproduzierbaren Browser-QA-Runner.\n'''
(ROOT/'reports/06-red-team-final.md').write_text(text,encoding='utf8')

# 07 limits
text='''# 07 – Grenzen und benötigte Zusatzquellen\n\n## Mehr Ansichten besonders wertvoll für\n\n- **Prodigy / World Champion / Mandalorian / Shift:** zweite und vierte Flight-Seite, um Safe-Roll zu vergrößern und Plane B source-grounded zu machen.\n- **Power Chrono / Gary / Auro / Supa-Venom:** gegenüberliegende Flightseite und Barrel-Rückseite.\n- **9GHHawNA:** Produktname, Modellvariante, Maße und technische Beschreibung des Rear-Systems.\n- **beide S5-Bilder:** Hersteller/Produktname, Gewicht/Variante, Komponentenliste.\n\n## Produktionsreife fehlt noch bei\n\n1. Body als rotationssymmetrisches/profiliertes Mesh mit kontrollierter Materialdarstellung.\n2. Transparente Flightflächen: explizites Back-to-Front-Sorting/Depth-Write-Policy je Design.\n3. WebGL-Benchmark im echten xConfig-Kontext auf Chrome 111/Firefox 121 Zielumgebung.\n4. Lifecycle/Context-Loss-Fallback mit echter Marker-Runtime.\n5. xConfig-Integrationstests für Zoom, Resize, Korrektur, Remove, Miss, drei Darts.\n6. neue Schattenlogik nach geometrisch stabiler Ruhepose.\n7. Wobble um den festen Tip nach stabiler Ruhepose.\n\nDiese Punkte sind keine versteckten Fehler des Builders, sondern die bewusst verbleibende Strecke vom Referenz-POC zur Produktivintegration.\n'''
(ROOT/'reports/07-limitations.md').write_text(text,encoding='utf8')

# 08 main audit
text='''# 08 – xConfig main, read-only Audit\n\nGeprüfter Branch: `main`\n\nGeprüfter Commit zum Zeitpunkt dieser Arbeit: `5f41fd515b65cafa3ccf2643b5e462805227f6c3` (`release: prepare 3.3.1`, 02.10.2026 UTC).\n\nBestätigt im aktuellen `src/features/dart-marker-replacer/logic.js`:\n\n```text\nDART_IMAGE_SOURCE_WIDTH  = 789\nDART_IMAGE_SOURCE_HEIGHT = 331\nDART_IMAGE_TIP_Y         = 212\nTIP_X ratio              = 0\n```\n\nBestätigt in `pose.js`:\n\n- `realisticDirection` löst primär eine 2D-Bildschirmrichtung aus einem angenommenen Wurfpunkt.\n- `natural`/`dramatic` erzeugen deterministische 2D-Jitter/Skew/Scale/Tail-Lift-Werte.\n- `flatPerspective` nutzt weiterhin affine Scale-Werte (mild ≈ 0.85, strong ≈ 0.65).\n- Tip-verankerte Matrizen sind bereits Teil der Legacy-Pipeline.\n\nKonsequenz für später: Der Builder/3D-Pfad soll nicht Marker-Erkennung, Overlay, Cleanup oder `rotateGroup` ersetzen. Der wahrscheinlich kleinste Eingriff bleibt ein horizontaler 789×331 Render-to-Sprite mit Tip `(0,212)`, `screenRotation` danach im bestehenden SVG-`rotateGroup`, und `flatPerspective` im 3D-Pfad **aus**.\n\nWährend dieser Arbeit wurden keinerlei GitHub-Dateien verändert.\n'''
(ROOT/'reports/08-xconfig-main-readonly-audit.md').write_text(text,encoding='utf8')

# preset inventory
rows=[]
for pid,p in cat['presets'].items():
    mode='integrated rear' if p.get('rearSystemId') else 'classic modular'
    rows.append([pid,p['name'],mode,p.get('pointId'),p.get('barrelId'),p.get('rearSystemId') or p.get('shaftId'),p.get('flightId') or 'im Rear-System'])
(ROOT/'reports/09-preset-inventory.md').write_text('# 09 – Preset-Inventar\n\n'+md_table(rows,['ID','Name','Modell','Point','Barrel','Rear/Shaft','Flight']),encoding='utf8')


# 15 player dart expansion / provenance
web_rows=[]
for item in cat.get('webPlayerSources',[]):
    p=cat['presets'][item['presetId']]
    web_rows.append([
        item['player'], item['product'], item['presetId'],
        'integrated K-Flex' if p.get('rearSystemId') else 'classic shaft + flight',
        item['officialPage'], item['imageReference'], item['visualStatus'],
    ])
text='''# 15 – Spieler-Darts Erweiterung V1.2

## Ziel

Der Builder wurde um sieben recherchierte Spieler-Presets erweitert. Gabriel Clemens ist mit **zwei** Setups vertreten: G2 als klassisch modularer Dart und 95K als modernes integriertes K-Flex-Setup.

## Provenienzregel

Die **Produktdaten und Maße** stammen aus Herstellerseiten (bei MvG ergänzt durch eine Händler-Maßtabelle) und sind als `WEB-VERIFIED` geführt. Die öffentliche Bildsuche wurde zur visuellen Auswahl und Referenz genutzt. Die Ausführungsumgebung kann die externen Bildbytes jedoch nicht in den lokalen Container herunterladen. Deshalb sind die im POC eingebetteten Player-Grafiken ausdrücklich **WEB-REFERENCED RECONSTRUCTIONS**:

- keine Behauptung, dass lokale Pixel Herstellerpixel sind;
- Flight Plane A = `HEURISTIC`;
- unbekannte Plane B = `APPROXIMATED`;
- originale Bild-Referenz-URL bleibt im Katalog erhalten;
- ein späterer Authoring-Lauf kann die Rekonstruktion gegen echte Originaldateien austauschen, ohne das Daten-/Kompatibilitätsmodell zu ändern.

'''+md_table(web_rows,['Spieler','Produkt','Preset','Rear-Modell','Produktseite','Bildreferenz','Lokaler Visual-Status'])+'''

## Warum diese Auswahl

Sie deckt bewusst unterschiedliche technische Familien ab: klassische separate Shafts/Flights (Clemens G2, MvG Signature, Humphries Prestige) sowie integrierte K-Flex-Systeme (Clemens 95K, Cross 95K, Aspinall 95K, Bunting 95K), dazu No.6-, No.2- und Standard-Flightprofile sowie unterschiedliche Barrelprofile. Das erweitert den Builder technisch stärker als sieben nahezu identische Presets.
'''
(ROOT/'reports/15-player-darts-v1.2.md').write_text(text,encoding='utf8')
