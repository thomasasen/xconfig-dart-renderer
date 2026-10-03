# 05 – Red Team, erster Durchlauf

## Rollen

1. **Technical Artist:** Silhouetten, Material, Übergänge, Flight-Lesbarkeit.
2. **Three.js/WebGL Engineer:** Shared Context, Cache, Depth/Alpha, Context Loss, Render-on-demand.
3. **Dart-Hardware-Reviewer:** 2BA/Swiss/Press-fit, Rear-Systeme, reale Komponenten.
4. **Reconstruction Reviewer:** Quellenstatus, Variantenkonflikte, unbekannte Backfaces.
5. **UX Reviewer:** Fehlkombinationen, Locking, Transparenz von Unsicherheit.
6. **Skeptical Visual Reviewer:** „Steckt der Dart im Board?“ statt „verzogenes Produktbild“.

## Befunde vor Korrektur

| Befund | Risiko | Maßnahme |
|---|---|---|
| Infografik-Extraktion zog Panel-Trennlinien in Mandalorian/AT-AT-Flight | hoch visuell | Dark-ROI-Extraktion verschärft; Flight zusätzlich mit geometrischer Envelope maskiert |
| Plane B aus Einzelansicht unbekannt | hoch bei Roll | keine Spiegelung; entsättigte/dunklere Approximation; Safe-Roll in UI |
| Prodigy-Dateiname „95“, Hersteller „90“ | Datenintegrität | beide Evidenzen getrennt; keine stille Korrektur |
| Auro 90-Source vs. aktuelle 95-Herstellerseite | Variantenintegrität | 90-Source als eigene/legacy Variante; 95-Seite nur als aktuelle Produktfamilienquelle |
| Unbekannte Gewichtsvarianten könnten falsche Ø-Werte bekommen | Scheingenauigkeit | factual Maße `null`; eigene `render*`-Heuristik |
| Integrierte Rear-Systeme könnten in Shaft + Flight zerfallen | Modellfehler | `RearSystemDefinition` als eine Entität; UI sperrt separate Dropdowns |
| Slider-Änderung könnte unnötig Scene-Rebuild triggern | Performance | Renderer merkt Assembly-Key und soll unveränderte Assembly wiederverwenden |
| Transparente Flight-Sortierung ist nicht ausreichend durch ein einzelnes opaque Preset abgedeckt | QA-Lücke | `9GHHawNA` bleibt Geometry/Transparency-Referenz; keine falsche Produktisierung; separate QA vor Produktion erforderlich |
| Body roll ist im Ribbon-Hybrid nicht physisch vollständig | visuelle Grenze | als POC-Limit dokumentieren; nicht als „vollständiges 3D-Modell“ ausgeben |
| Browser/WebGL-Automation in dieser Ausführungsumgebung blockiert localhost | Testumgebung | statische Tests + Software-Pose-QA laufen; `browser_qa.py` für normale Workstation mitgeliefert |
