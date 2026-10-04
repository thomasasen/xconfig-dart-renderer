from pathlib import Path
import json, re
from flight_geometry_reference import reference_dimensions
ROOT=Path(__file__).resolve().parents[1]
meta=json.loads((ROOT/'data/authoring-metadata.json').read_text())

SRC='SOURCE-GROUNDED'; WEB='WEB-VERIFIED'; HEU='HEURISTIC'; APP='APPROXIMATED'; UNK='UNKNOWN'

def ev(status,note,source=None):
    d={'status':status,'note':note}
    if source:d['source']=source
    return d

def tex(product,name): return f'./assets/components/{product}/{name}.png'

def profile(product): return meta[product]['flightProfile']

def flight_meta(product):
 m=meta.get(product,{})
 provenance=m.get('componentProvenance',{})
 fin_authoring=m.get('finFaceAuthoring') or None
 fin_textures={}
 for fin_key,face in ((fin_authoring or {}).get('textures') or {}).items():
  front=face.get('front')
  back=face.get('back')
  fin_textures[fin_key]={
   **face,
   'front':tex(product,front) if front else None,
   'back':tex(product,back) if back else None,
  }
 return {
  'planeAProvenance':m.get('flightPlaneAProvenance') or provenance.get('flight-plane-a') or ('HEURISTIC' if str(m.get('authoringStatus','')).startswith('WEB-REFERENCED-RECONSTRUCTION') else 'SOURCE-GROUNDED'),
  'planeBProvenance':m.get('flightPlaneBProvenance') or provenance.get('flight-plane-b-approx') or 'APPROXIMATED',
  'flightExtractionMode':m.get('flightExtractionMode','DIRECT_SOURCE_FACE'),
  'flightApproximation':m.get('flightApproximation'),
  'flightGeometry':m.get('flightGeometry'),
  'finFaceAuthoring':fin_authoring,
  'finTextures':fin_textures or None,
 }

def tail_render_meta(product,total_length_mm,shaft_diameter_mm=5.2):
 m=meta.get(product,{})
 tail_authoring=m.get('tailAuthoring') or {}
 if tail_authoring.get('status') not in ('PASS','NEEDS_MANUAL_REVIEW'):
  return None
 seg=m.get('tailSegmentation') or {}
 core=seg.get('shaftCore')
 if not core or len(core)!=2:
  return None

 total=float(total_length_mm or 20)
 diameter=float(shaft_diameter_mm or 5.2)
 result={
  # A clean canonical shaft-core is useful independently of whether a distinct
  # physical root can be separated with enough confidence.
  'shaftTexture':tex(product,'rear-shaft-core'),
  'renderShaftLengthMm':total,
  'tailQa':{
    'axisAuthoring':m.get('axisAuthoring'),
    'tailSegmentation':seg,
    'tailMetrics':m.get('tailMetrics'),
    'tailAuthoring':tail_authoring,
  },
 }

 if not m.get('rootAuthored'):
  return result

 root=seg.get('rearRoot')
 if not root or len(root)!=2:
  return result

 core_px=max(1,float(core[1])-float(core[0]))
 root_px=max(1,float(root[1])-float(root[0]))
 ratio=root_px/(core_px+root_px)
 # Render geometry, not a manufacturer dimension: keep the source-derived proportion
 # within a conservative physical envelope so one noisy boundary cannot dominate.
 root_len=max(1.2,min(4.5,total*ratio))
 shaft_len=max(0.5,total-root_len)
 growth=float(seg.get('rootGrowthRatio') or 1.16)
 growth=max(1.0,min(1.45,growth))
 result.update({
  'renderShaftLengthMm':round(shaft_len,4),
  'rootTexture':tex(product,'rear-root'),
  'renderRootLengthMm':round(root_len,4),
  'renderRootFrontDiameterMm':diameter,
  'renderRootRearDiameterMm':round(diameter*growth,4),
  'flightRootOverlapMm':0.6,
 })
 return result

source_analysis=[
 {'file':'190840STARWARSMANDALORIAN95_STEElTIP_GALLERY_DE_PT01.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Star Wars Mandalorian SP','confidence':'HIGH','reason':'Die gelieferte Infografik benennt K-Flex, 2BA, 30/35-mm Swiss Point, 52-mm Barrel und 19-mm Short und bezeichnet den montierten blauen Flight ausdrücklich als No.6 (Extra: No.2). Aktuelle Target-Webdaten widersprechen dieser Zuordnung; für die konkrete Designquelle hat deshalb die gelieferte Infografik Vorrang.','evidence':[ev(SRC,'Produkt-/Komponentenangaben sind direkt im Bild lesbar.'),ev(WEB,'Target bestätigt Mandalorian SP, 95% Tungsten, 52-mm Barrel, 30-mm Swiss Storm Point und Short K-Flex.','https://www.targetdarts.com/us/star-wars-mandalorian-sp')]},
 {'file':'190843-STARWARSAT-AT90_STEELTIP_GALLERY_DE_PT01.webp','classification':'CLASSIC_MODULAR','identifiedAs':'Target Star Wars AT-AT SP','confidence':'HIGH','reason':'Infografik zeigt Pro Grip Short plus separate No.6-Flights; kein integriertes Rear-System.','evidence':[ev(SRC,'30-mm Point, 47.55-mm Barrel, 34-mm Short-Shaft, No.6 im Bild.'),ev(WEB,'Target bestätigt 90% Tungsten, Pro Grip Short, No.6 Pro Ultra Flight.','https://www.targetdarts.com/us/star-wars-at-at-sp')]},
 {'file':'9GHHawNA.webp','classification':'GEOMETRY_REFERENCE','identifiedAs':None,'confidence':'LOW','reason':'Sehr sauberer freigestellter Broadside-Render mit deutlich sichtbarer Kreuzgeometrie am Rear-System; Produktidentität/Variante ist aus Datei und sichtbarer Beschriftung nicht belastbar rekonstruierbar. Deshalb Geometrie-Referenz, nicht Presetquelle.','evidence':[ev(SRC,'Transparenter/isolierter Broadside-Render; Hinten ist eine molded/integrated wirkende Kreuzgeometrie sichtbar.'),ev(UNK,'Exakte Produktidentität und Maße nicht verifiziert.')]},
 {'file':'GNGTP_Gnasha-Angled.webp','classification':'ANGLED_REFERENCE','identifiedAs':'Shot Gnarly Gnasha Steel Tip 95%','confidence':'HIGH','reason':'Dateiname und sichtbarer Aufbau passen zum offiziellen Shot-Modell; die Aufnahme ist absichtlich schräg und damit Pose-/Materialreferenz, nicht kanonische Komponentenansicht.','evidence':[ev(SRC,'Angled product view; kein orthogonaler Komponenten-Extract.'),ev(WEB,'Shot führt Gnarly Gnasha Steel Tip 95% mit Turbo Points, Carbon-Shafts und No.6 Flight.','https://www.shotdarts.com/products/gnarly-gnasha-steel-tip-dart-set-95-tungsten-barrels')]},
 {'file':'PT01_a83f80b3-c589-4f2e-85c1-7cf911048504.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Star Wars Darth Vader SP (matched)','confidence':'MEDIUM_HIGH','reason':'Infografik nennt 95%, 52 mm, 30/35-mm Swiss Point, 19-mm Short, K-Flex und No.6/No.2. Diese Kombination stimmt mit Darth Vader SP überein; Dateiname selbst nennt das Modell nicht.','evidence':[ev(SRC,'K-Flex/2BA und Maße direkt im Bild.'),ev(WEB,'Target Darth Vader SP hat dieselbe Kernkonfiguration.','https://www.targetdarts.com/us/darth-vader-sp'),ev(HEU,'Modellzuordnung ist ein Match aus Artwork + Spezifikationen, nicht aus dem Dateinamen.')]},
 {'file':'PT02_ffd9f2ed-6a52-43e8-9f62-027742ec8be4.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Luke Littler Edge SP (matched)','confidence':'HIGH','reason':'THE NUKE-Artwork, 95%, 52-mm Barrel, 30/42-mm Swiss Point und No.2 K-Flex Short stimmen mit Luke Littler Edge SP überein.','evidence':[ev(SRC,'K-Flex, Maße und Gewichte 22/23/24 direkt im Bild.'),ev(WEB,'Target Edge SP bestätigt 95%, 52-mm Barrel, No.2 K-Flex und Varianten.','https://www.targetdarts.com/us/luke-littler-edge-sp')]},
 {'file':'PW2022_SupaVenom_Steel_LEFT.webp','classification':'CLASSIC_MODULAR','identifiedAs':'Red Dragon Peter Wright Supa-Venom Steel Tip','confidence':'HIGH','reason':'Freigestellte orthogonale Seitenansicht mit klar getrenntem Barrel, klassischem Shaft und Standard-Flight.','evidence':[ev(SRC,'Broadside source suitable for modular extraction.'),ev(WEB,'Red Dragon bestätigt Nitrotech polycarbonate short shaft und Players extra thick standard flights.','https://www.reddragondarts.com/products/peter-wright-supa-venom-darts')]},
 {'file':'S5-1_22b0f7a4-0463-42e0-8623-49ef67353563_1.webp','classification':'NEEDS_MANUAL_REVIEW','identifiedAs':None,'confidence':'LOW','reason':'Broadside-Aufnahme ist sehr brauchbar, aber Produktname, Rear-Systemtyp und reale Maße sind nicht aus der Quelle verifizierbar. Ein Preset würde sonst Scheingenauigkeit erzeugen.','evidence':[ev(SRC,'Klarer Broadside-Render mit schwarzem Rear-System.'),ev(UNK,'Produktidentität, Verbindungstyp und Maße fehlen.')]},
 {'file':'S5-1_d5e583f9-5bbe-4728-b176-4f516d0960b3.webp','classification':'NEEDS_MANUAL_REVIEW','identifiedAs':None,'confidence':'LOW','reason':'Sehr sauberer Broadside-Render, aber unbekanntes Produkt/Logo und keine belastbaren Spezifikationen. Als Designquelle erst nach Identifikation freigeben.','evidence':[ev(SRC,'Broadside-Render mit schwarzem grafischem Flight.'),ev(UNK,'Produktidentität, Maße, Flight-/Shaftsystem nicht verifiziert.')]},
 {'file':'shot-alchemy-auro-90_3.webp','classification':'CLASSIC_MODULAR','identifiedAs':'Shot Alchemy Auro 90% source variant','confidence':'HIGH','reason':'Orthogonale Produktaufnahme mit separatem Shaft und Flight. Dateiname nennt 90%; aktuelle Shot-Seite führt eine 95%-Version. Daher Versionskonflikt ausdrücklich erhalten.','evidence':[ev(SRC,'Dateiname bezeichnet 90%-Variante; Bild zeigt klassisches Shaft+Flight-Setup.'),ev(WEB,'Aktuelle Shot-Seite führt Auro 95% mit 35-mm Point, Koi Carbon Inbetween und No.6.','https://www.shotdarts.com/products/alchemy-auro-steel-tip-dart-set-95-tungsten-barrels'),ev(WEB,'Retailer dokumentiert Auro 90% in 23/24/25g mit 46/47/47 mm Barrel.','https://www.dartswarehouse.de/shot-alchemy-auro-90.html')]},
 {'file':'target-luke-littler-g1-prodigy-95-swiss-23-gram_3.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Luke Littler G1 Prodigy SP 23g','confidence':'HIGH','reason':'Dateiname nennt Produkt und 23g; Bild zeigt K-Flex. Hersteller führt das aktuelle G1 Prodigy allerdings als 90%, nicht 95%; der Dateiname ist daher bezüglich Tungsten-Prozent widersprüchlich.','evidence':[ev(SRC,'Dateiname: G1 Prodigy, 23 gram, „95“; sichtbares purple K-Flex.'),ev(WEB,'Target: 23g = 52 x 6.5 mm, 26-mm Swiss DX, No.2 K-Flex Short; Material 90%.','https://www.targetdarts.com/eu/luke-littler-g1-prodigy-sp'),ev(UNK,'Warum die lokale Datei „95“ nennt, ist nicht geklärt; nicht als Herstellerfakt übernehmen.')]},
 {'file':'target-luke-littler-world-champion-90-swiss-23-gram_3.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Luke Littler G1 World Champion SP 23g','confidence':'HIGH','reason':'Dateiname und Produktbild eindeutig; integriertes World Champion K-Flex.','evidence':[ev(SRC,'23g im Dateinamen; sichtbares integriertes Rear-System.'),ev(WEB,'Target: 52 x 6.5 mm, 35-mm Swiss SLK, No.6, K-Flex Short.','https://www.targetdarts.com/us/luke-littler-world-champion-sp')]},
 {'file':'target-phil-taylor-power-chrono-sp-steeltip-95_3.webp','classification':'CLASSIC_MODULAR','identifiedAs':'Target Phil Taylor Power Chrono SP','confidence':'HIGH','reason':'Produktbild zeigt separates Power Chrono Shaft-/Flight-Setup; keine integrierte Rear-Einheit.','evidence':[ev(SRC,'Orthogonaler Produkt-Render.'),ev(WEB,'Target: 95%, 30/35-mm Swiss Chrono Points, Short 22.4-mm Titanium Shafts; Vapor S/No.2/No.6 im Set.','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp')]},
 {'file':'target-shift-sp-steeltip-90_3.webp','classification':'INTEGRATED_REAR_SYSTEM','identifiedAs':'Target Shift SP','confidence':'HIGH','reason':'Produktbild zeigt K-Shift-artiges einteiliges Rear-System; Hersteller bestätigt K-Shift als integriertes Flight-/Shaftsystem.','evidence':[ev(SRC,'Red integrated rear visible in source.'),ev(WEB,'Target: 90%, 50-mm Barrel, 30-mm Swiss GRD, No.6 K-Shift Short.','https://www.targetdarts.de/shift-sp')]},
 {'file':'unicorn-w-c-gary-anderson-phase-6-90_1.webp','classification':'CLASSIC_MODULAR','identifiedAs':'Unicorn Gary Anderson Phase 6 90%','confidence':'HIGH','reason':'Orthogonaler Produkt-Render mit klassischem Gripper-Shaft und separatem Flight.','evidence':[ev(SRC,'Separate shaft/flight visually clear.'),ev(WEB,'Dartshopper/Double Top dokumentieren die Gewichtsvarianten und Barrelmaße.','https://www.dartshopper.com/unicorn-gary-anderson-phase-6-90/'),ev(UNK,'Die konkrete Gewichtsvariante des lokalen Bildes ist nicht im Dateinamen codiert.')]},
]

# Component constructors
points={}; barrels={}; shafts={}; flights={}; rears={}; presets={}

def point(id,name,interface,length,diam,product,texname='point',evidence=None,render=None):
 points[id]={'kind':'PointDefinition','id':id,'name':visible_preset_name(name),'interface':interface,'lengthMm':length,'diameterMm':diam,'renderLengthMm':render or length or 30,'renderDiameterMm':diam or 2.1,'texture':tex(product,texname),'evidence':evidence or []}
def barrel(id,name,pointInterface,length,diam,product,profileName='straight',evidence=None,renderLength=None,renderDiam=None):
 barrels[id]={'kind':'BarrelDefinition','id':id,'name':visible_preset_name(name),'pointInterface':pointInterface,'rearThread':'2BA','lengthMm':length,'diameterMm':diam,'profile':profileName,'renderLengthMm':renderLength or (length if isinstance(length,(int,float)) else 50),'renderDiameterMm':renderDiam or (diam if isinstance(diam,(int,float)) else 7.0),'texture':tex(product,'barrel'),'evidence':evidence or []}
def shaft(id,name,length,product,evidence=None,renderLength=None):
 shafts[id]={'kind':'ShaftDefinition','id':id,'name':visible_preset_name(name),'rearThread':'2BA','flightMount':'FOLDED_FLIGHT_SLOT','lengthMm':length,'renderLengthMm':renderLength or length or 30,'renderDiameterMm':4.8,'texture':tex(product,'shaft'),'evidence':evidence or []}
def flight(id,name,shape,product,evidence=None,renderLength=42,renderRadius=18,planeAStatus=SRC,visualAuthoring='SOURCE-GROUNDED',safe=None):
 fm=flight_meta(product)
 resolved_len,resolved_radius,geometry_source=reference_dimensions(shape,renderLength,renderRadius)
 flights[id]={'kind':'FlightDefinition','id':id,'name':visible_preset_name(name),'flightMount':'FOLDED_FLIGHT_SLOT','shape':shape,'renderLengthMm':resolved_len,'renderRadiusMm':resolved_radius,'renderWidthMm':round(resolved_radius*2,4),'renderGeometrySource':geometry_source,'planeProfile':profile(product),'planeATexture':tex(product,'flight-plane-a'),'planeBTexture':tex(product,'flight-plane-b-approx'),'faceEvidence':{'planeA':planeAStatus,'planeB':APP},'planeAProvenance':fm['planeAProvenance'],'planeBProvenance':fm['planeBProvenance'],'flightExtractionMode':fm['flightExtractionMode'],'flightApproximation':fm['flightApproximation'],'flightGeometry':fm['flightGeometry'],'visualAuthoring':visualAuthoring,'evidence':evidence or []}
 if fm.get('finTextures'):
  flights[id]['finTextures']=fm['finTextures']
  flights[id]['finFaceAuthoring']={k:v for k,v in (fm.get('finFaceAuthoring') or {}).items() if k!='textures'}
 if safe:
  flights[id]['safeRollMinDeg']=safe[0]; flights[id]['safeRollMaxDeg']=safe[1]
def rear(id,name,system,length,shape,product,evidence=None,renderFlightLength=42,renderRadius=18,safe=(-18,18),planeAStatus=SRC,visualAuthoring='SOURCE-GROUNDED'):
 fm=flight_meta(product)
 diameter=5.2
 resolved_len,resolved_radius,geometry_source=reference_dimensions(shape,renderFlightLength,renderRadius)
 authored=tail_render_meta(product,length or 20,diameter)
 rears[id]={'kind':'RearSystemDefinition','id':id,'name':visible_preset_name(name),'rearThread':'2BA','integrated':True,'system':system,'shaftLengthMm':length,'flightShape':shape,'renderShaftLengthMm':length or 20,'renderShaftDiameterMm':diameter,'renderFlightLengthMm':resolved_len,'renderFlightRadiusMm':resolved_radius,'renderFlightWidthMm':round(resolved_radius*2,4),'renderGeometrySource':geometry_source,'shaftTexture':tex(product,'rear-shaft'),'planeProfile':profile(product),'planeATexture':tex(product,'flight-plane-a'),'planeBTexture':tex(product,'flight-plane-b-approx'),'faceEvidence':{'planeA':planeAStatus,'planeB':APP},'planeAProvenance':fm['planeAProvenance'],'planeBProvenance':fm['planeBProvenance'],'flightExtractionMode':fm['flightExtractionMode'],'flightApproximation':fm['flightApproximation'],'flightGeometry':fm['flightGeometry'],'visualAuthoring':visualAuthoring,'safeRollMinDeg':safe[0],'safeRollMaxDeg':safe[1],'evidence':evidence or []}
 if fm.get('finTextures'):
  rears[id]['finTextures']=fm['finTextures']
  rears[id]['finFaceAuthoring']={k:v for k,v in (fm.get('finFaceAuthoring') or {}).items() if k!='textures'}
 if authored:
  rears[id].update(authored)
WEIGHT_RE=re.compile(r'\s+(\d+(?:[.,]\d+)?)\s*g\b',re.IGNORECASE)

def visible_preset_name(name):
 # Weight is variant metadata, never part of the user-facing render-design identity.
 return WEIGHT_RE.sub('',name).strip()

def preset_weight_g(name):
 m=WEIGHT_RE.search(name)
 if not m:return None
 value=float(m.group(1).replace(',','.'))
 return int(value) if value.is_integer() else value

def preset(id,name,source,pointId,barrelId,shaftId=None,flightId=None,rearId=None,inc=35,roll=0,notes=None,sourcePage=None,sourceLabel=None,sourceType='SUPPLIED_SOURCE'):
 presets[id]={'kind':'DartPreset','id':id,'name':visible_preset_name(name),'variantWeightG':preset_weight_g(name),'sourceImage':f'./assets/source/{source}','sourcePage':sourcePage,'sourceLabel':sourceLabel or ('Supplied source' if sourceType=='SUPPLIED_SOURCE' else sourceType),'sourceType':sourceType,'pointId':pointId,'barrelId':barrelId,'shaftId':shaftId,'flightId':flightId,'rearSystemId':rearId,'defaultPose':{'incidenceDeg':inc,'rollDeg':roll},'notes':notes or []}

# Prodigy 23g exact variant
point('target-swiss-dx-gold-26','Target Swiss DX Gold 26 mm','SWISS_POINT',26,2.1,'prodigy',evidence=[ev(WEB,'26-mm Swiss DX is the fitted point; 30 mm also supplied.','https://www.targetdarts.com/eu/luke-littler-g1-prodigy-sp')])
barrel('prodigy-23-barrel','Luke Littler G1 Prodigy 23g Barrel','SWISS_POINT',52,6.5,'prodigy','straight',evidence=[ev(WEB,'23g: 52 x 6.5 mm; current official material 90%.','https://www.targetdarts.com/eu/luke-littler-g1-prodigy-sp'),ev(UNK,'Local filename says 95; not treated as manufacturer fact.')])
rear('prodigy-kflex-no2-short','Prodigy Purple K-Flex No.2 Short','K-FLEX',19,'No.2','prodigy',evidence=[ev(WEB,'No.2 K-Flex Short 19 mm.','https://www.targetdarts.com/eu/luke-littler-g1-prodigy-sp')],renderFlightLength=43,renderRadius=18.5,safe=(-12,12))
preset('prodigy-23','Target Luke Littler G1 Prodigy 23g','target-luke-littler-g1-prodigy-95-swiss-23-gram_3.webp','target-swiss-dx-gold-26','prodigy-23-barrel',rearId='prodigy-kflex-no2-short',notes=['Local file says 95; current manufacturer page says 90%. Conflict is surfaced, not reconciled silently.'])

# Shift: image weight unresolved. Length constant; render diameter heuristic.
point('target-swiss-grd-black-30','Target Swiss GRD Black 30 mm','SWISS_POINT',30,2.1,'shift',evidence=[ev(WEB,'30-mm Swiss GRD fitted; 35-mm options in box.','https://www.targetdarts.de/shift-sp')])
barrel('shift-barrel','Target Shift SP Barrel (source weight unresolved)','SWISS_POINT',50,None,'shift','straight',evidence=[ev(WEB,'50 mm for 23/24/25g; diameters 6.7/6.8/7.0 mm.','https://www.targetdarts.de/shift-sp'),ev(UNK,'Local source does not identify weight; exact diameter unknown.')],renderDiam=6.8)
rear('shift-kshift-no6-short','Target K-Shift No.6 Short','K-SHIFT',19,'No.6','shift',evidence=[ev(WEB,'K-Shift is an integrated flight+shaft; fitted Short 19 mm, No.6.','https://www.targetdarts.de/shift-sp')],renderFlightLength=41.5,renderRadius=17.2,safe=(-12,12))
preset('shift','Target Shift SP','target-shift-sp-steeltip-90_3.webp','target-swiss-grd-black-30','shift-barrel',rearId='shift-kshift-no6-short',notes=['Barrel diameter uses 6.8 mm as render heuristic because source weight is unknown.'])

# World Champion exact 23g
point('target-swiss-slk-gold-35','Target Swiss SLK Gold 35 mm','SWISS_POINT',35,2.1,'world',evidence=[ev(WEB,'Fitted 35-mm Swiss SLK; 42-mm alternative included.','https://www.targetdarts.com/us/luke-littler-world-champion-sp')])
barrel('world-champ-23-barrel','Luke Littler G1 World Champion 23g Barrel','SWISS_POINT',52,6.5,'world','straight',evidence=[ev(WEB,'23g only: 52 x 6.5 mm, 90% tungsten.','https://www.targetdarts.com/us/luke-littler-world-champion-sp')])
rear('world-kflex-no6-short','World Champion K-Flex No.6 Short','K-FLEX',19,'No.6','world',evidence=[ev(WEB,'World Champion No.6 K-Flex, Short.','https://www.targetdarts.com/us/luke-littler-world-champion-sp')],renderFlightLength=41.5,renderRadius=17.2,safe=(-10,10))
preset('world-champion','Target Luke Littler G1 World Champion 23g','target-luke-littler-world-champion-90-swiss-23-gram_3.webp','target-swiss-slk-gold-35','world-champ-23-barrel',rearId='world-kflex-no6-short')

# Chrono source variant unknown
point('target-swiss-chrono-silver-30','Target Swiss Chrono Silver 30 mm','SWISS_POINT',30,2.1,'chrono',evidence=[ev(WEB,'30-mm Swiss Chrono fitted; 35 mm also included.','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp')])
barrel('chrono-barrel','Phil Taylor Power Chrono Barrel (source weight unresolved)','SWISS_POINT',None,None,'chrono','torpedo',evidence=[ev(WEB,'22g 41x7.55; 24g 41x7.85; 26g 42.5x7.85 mm.','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp'),ev(UNK,'Local source weight not encoded.')],renderLength=41,renderDiam=7.75)
shaft('chrono-titanium-short','Power Chrono Titanium Short 22.4 mm',22.4,'chrono',evidence=[ev(WEB,'Power Chrono shaft Short 22.4 mm.','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp')])
flight('chrono-vapor-s','Power Chrono Vapor S Flight','Vapor S','chrono',evidence=[ev(WEB,'Vapor S, No.2 and No.6 are supplied; source broadside visually matches the selected Vapor-S-like profile, but exact fitted flight is image-derived.','https://www.targetdarts.com/us/phil-taylor-power-chrono-sp'),ev(HEU,'Exact flight selection in source is inferred from silhouette.')],renderLength=40,renderRadius=16.5)
preset('chrono','Target Phil Taylor Power Chrono SP','target-phil-taylor-power-chrono-sp-steeltip-95_3.webp','target-swiss-chrono-silver-30','chrono-barrel','chrono-titanium-short','chrono-vapor-s',notes=['Weight variant not identifiable from local filename; render width is a neutral heuristic.'])

# Gary Anderson
point('unicorn-steel-point-heuristic','Unicorn Steel Point (source setup)','PRESS_FIT',None,2.1,'gary',evidence=[ev(UNK,'Exact point model/length not established from the supplied broadside image; retailer notes longer points in player setup, but source-specific length is not proven.')],render=36)
barrel('gary-phase6-barrel','Unicorn Gary Anderson Phase 6 Barrel (source weight unresolved)','PRESS_FIT',None,None,'gary','teardrop',evidence=[ev(WEB,'21g 46.3x7.2; 22g 48.5x7.2; 23g 50.7x7.2; 24g 50.7x7.3; 25g 50.7x7.5 mm.','https://www.dartshopper.com/unicorn-gary-anderson-phase-6-90/'),ev(UNK,'Local source weight unknown.')],renderLength=50.7,renderDiam=7.2)
shaft('gary-gripper4','Unicorn Gripper 4 Shaft',None,'gary',evidence=[ev(WEB,'Double Top lists Gripper 4 shafts with the Phase 6 set.','https://www.doubletopdartshop.com/products/gary-anderson-phase-6-world-champion-90-tungsten-steel-tip-darts-by-unicorn')])
flight('gary-phase6-flight','Unicorn Gary Anderson Phase 6 Flight','player standard','gary',evidence=[ev(WEB,'Double Top lists Ultrafly Gary Anderson AR2 World Champion Phase 6 flights.','https://www.doubletopdartshop.com/products/gary-anderson-phase-6-world-champion-90-tungsten-steel-tip-darts-by-unicorn')],renderLength=42,renderRadius=17.8)
preset('gary-phase6','Unicorn Gary Anderson Phase 6 90%','unicorn-w-c-gary-anderson-phase-6-90_1.webp','unicorn-steel-point-heuristic','gary-phase6-barrel','gary-gripper4','gary-phase6-flight',notes=['Source weight/point length unresolved; exact physical diameter must not be read from render heuristic.'])

# Shot Auro 90 source variant
point('shot-auro-point-35','Shot/Alchemy Steel Point 35 mm','PRESS_FIT',35,2.1,'auro',evidence=[ev(SRC,'Source shows gold steel point.'),ev(WEB,'Current 95% Auro page specifies Alchemy 35-mm steel points; old 90% source variant point model is not independently confirmed.','https://www.shotdarts.com/products/alchemy-auro-steel-tip-dart-set-95-tungsten-barrels'),ev(HEU,'35 mm used for builder geometry across the visually matching source setup.')])
barrel('auro-90-barrel','Shot Alchemy Auro 90% Barrel (source weight unresolved)','PRESS_FIT',None,None,'auro','tapered',evidence=[ev(WEB,'Auro 90 retailer: 23g 46x7.5; 24g 47x7.5; 25g 47x7.6 mm.','https://www.dartswarehouse.de/shot-alchemy-auro-90.html'),ev(UNK,'Source weight unknown; current manufacturer page is a 95% version.')],renderLength=47,renderDiam=7.5)
shaft('auro-koi-carbon','Shot Koi Carbon Shaft Helioknot Gold Inbetween',None,'auro',evidence=[ev(WEB,'Current Auro page names Koi Carbon Shaft Helioknot Gold Inbetween.','https://www.shotdarts.com/products/alchemy-auro-steel-tip-dart-set-95-tungsten-barrels'),ev(HEU,'Used as closest named setup for supplied Auro source; source is labeled 90%.')])
flight('auro-no6','Shot Alchemy No.6 Small Standard Flight','No.6','auro',evidence=[ev(WEB,'Current Auro page specifies No.6 Small Standard.','https://www.shotdarts.com/products/alchemy-auro-steel-tip-dart-set-95-tungsten-barrels')],renderLength=41.5,renderRadius=17.2)
preset('auro','Shot Alchemy Auro (supplied 90% source)','shot-alchemy-auro-90_3.webp','shot-auro-point-35','auro-90-barrel','auro-koi-carbon','auro-no6',notes=['Source filename says 90%; current Shot Auro is 95%. Builder keeps the supplied source as a distinct/legacy variant and labels the version uncertainty.'])

# Supa Venom
point('supa-steel-point','Red Dragon Supa-Venom steel point (source)','PRESS_FIT',None,2.1,'supa',evidence=[ev(UNK,'Exact factory point length not stated on the product page captured; do not infer from optional repointing products.')],render=32)
barrel('supa-barrel','Peter Wright Supa-Venom Barrel (source weight unresolved)','PRESS_FIT',54.6,None,'supa','straight',evidence=[ev(WEB,'All steel variants are 54.6 mm; diameters 6.0/6.1/6.25/6.35 for 21/22/23/24g.','https://www.reddragondarts.com/products/peter-wright-supa-venom-darts'),ev(UNK,'Source image weight unknown.')],renderDiam=6.25)
shaft('supa-nitrotech-short','Red Dragon Nitrotech Polycarbonate Short',None,'supa',evidence=[ev(WEB,'Product information lists Nitrotech polycarbonate short.','https://www.reddragondarts.com/products/peter-wright-supa-venom-darts')])
flight('supa-standard','Peter Wright Players Extra Thick Standard','Standard','supa',evidence=[ev(WEB,'Product information lists Players extra thick standard flights.','https://www.reddragondarts.com/products/peter-wright-supa-venom-darts')],renderLength=43,renderRadius=18.2)
preset('supa-venom','Red Dragon Peter Wright Supa-Venom','PW2022_SupaVenom_Steel_LEFT.webp','supa-steel-point','supa-barrel','supa-nitrotech-short','supa-standard')

# Geometry-only Slim flight preparation (not a product preset).
flights['generic-slim-geometry']={
 'kind':'FlightDefinition','id':'generic-slim-geometry','name':'Generic Slim Geometry QA','flightMount':'FOLDED_FLIGHT_SLOT','shape':'Slim',
 'renderLengthMm':46,'renderRadiusMm':10.5,
 'planeProfile':[[0,0],[0.09,0.35],[0.23,0.72],[1,0.48],[1,-0.48],[0.23,-0.72],[0.09,-0.35]],
 'planeATexture':'./assets/components/generic/slim-plane-a.png','planeBTexture':'./assets/components/generic/slim-plane-b-approx.png',
 'faceEvidence':{'planeA':HEU,'planeB':APP},
 'evidence':[ev(HEU,'Generic Slim flight geometry prepared for builder compatibility/shape testing; not tied to a supplied product image.')]
}

# Mandalorian infographic exact physical dimensions except barrel diameter depends weight. Pick 24g only as an explicit authored preset because infographic offers 22/24/26 and source appearance is common.
point('mandalorian-storm-black-30','Target Swiss Storm Black 30 mm','SWISS_POINT',30,2.1,'mandalorian',evidence=[ev(SRC,'30 mm plus extra 35 mm shown in infographic.'),ev(WEB,'Target confirms Swiss Storm Black 30/35.','https://www.targetdarts.com/us/star-wars-mandalorian-sp')])
barrel('mandalorian-24-barrel','Star Wars Mandalorian 24g Barrel','SWISS_POINT',52,6.5,'mandalorian','straight',evidence=[ev(SRC,'Infographic: 52 mm, 95%; weights include 24g.'),ev(WEB,'24g = 52 x 6.5 mm.','https://www.targetdarts.com/us/star-wars-mandalorian-sp')])
rear('mandalorian-kflex-short','Mandalorian K-Flex No.6 Short','K-FLEX',19,'No.6','mandalorian',evidence=[ev(SRC,'The supplied infographic explicitly labels the mounted blue K-Flex as No.6, Short 19 mm, with No.2 as the extra shape.'),ev(SRC,'Plane A artwork uses pixels from a separate frontal blue Mandalorian product image; its outer geometry is normalized to the No.6 shape stated by the supplied infographic, and the infographic composite flight is not used as a plane texture.'),ev(APP,'Only the thin edge-on cross-fin ridge removed from the frontal source and the unseen Plane B are approximated.'),ev(WEB,'The current Target page lists Blue No.2 and Black No.6; this conflicts with the supplied infographic, so current web copy is not used to override the supplied source geometry.','https://www.target-darts.co.uk/star-wars-mandalorian-sp')],renderFlightLength=41.5,renderRadius=17.2,safe=(-10,10))
preset('mandalorian-24','Target Star Wars Mandalorian 24g','190840STARWARSMANDALORIAN95_STEElTIP_GALLERY_DE_PT01.webp','mandalorian-storm-black-30','mandalorian-24-barrel',rearId='mandalorian-kflex-short',notes=['Point/barrel/rear-shaft still use the supplied infographic source. Flight Plane A uses a separate frontal blue Mandalorian artwork source normalized to the supplied No.6 geometry to avoid photographed composite-flight leakage.'])

# AT-AT additional classic infographic preset
point('atat-storm-silver-30','Target Swiss Storm Silver 30 mm','SWISS_POINT',30,2.1,'atat',evidence=[ev(SRC,'Infographic 30 mm.'),ev(WEB,'Target confirms 30 mm Silver Swiss Storm.','https://www.targetdarts.com/us/star-wars-at-at-sp')])
barrel('atat-23-barrel','Star Wars AT-AT 23g Barrel','SWISS_POINT',47.55,7.0,'atat','straight',evidence=[ev(WEB,'23g = 47.55 x 7.0 mm.','https://www.targetdarts.com/us/star-wars-at-at-sp')])
shaft('atat-progrip-short','Star Wars Pro Grip Short 34 mm',34,'atat',evidence=[ev(SRC,'34 mm Short shown in infographic.'),ev(WEB,'Target confirms grey Pro Grip Short 34 mm.','https://www.targetdarts.com/us/star-wars-at-at-sp')])
flight('atat-no6','AT-AT Pro Ultra No.6','No.6','atat',evidence=[ev(WEB,'Target confirms Pro Ultra AT-AT No.6.','https://www.targetdarts.com/us/star-wars-at-at-sp')],renderLength=41.5,renderRadius=17.2)
preset('atat-23','Target Star Wars AT-AT 23g (infographic preset)','190843-STARWARSAT-AT90_STEELTIP_GALLERY_DE_PT01.webp','atat-storm-silver-30','atat-23-barrel','atat-progrip-short','atat-no6',notes=['Infographic appearance extraction is heuristic; dimensions are source/manufacturer grounded.'])

# ---------------------------------------------------------------------------
# Web-researched player additions (V1.2)
# ---------------------------------------------------------------------------
# Important provenance rule: the physical/product specifications below are web
# verified, but this execution environment cannot download the external image
# bytes into the self-contained POC. The local component artwork is therefore a
# WEB-REFERENCED RECONSTRUCTION authored from inspected public product images.
# It is intentionally marked HEURISTIC/APPROXIMATED and must never be laundered
# into SOURCE-GROUNDED evidence.

WEB_RECON='WEB-REFERENCED-RECONSTRUCTION'
WEB_SOURCE='SOURCE-GROUNDED-WEB-EXTRACT'

# Gabriel Clemens Generation 2 – physical specifications web-verified; V1.3 visual
# pixels are extracted from a real product photograph during the authoring step.
point('clemens-g2-storm-nano-26','Gabriel Clemens G2 Swiss Storm Nano 26 mm','SWISS_POINT',26,2.1,'clemens-g2',evidence=[ev(WEB,'Target specifies fitted 26-mm Storm Nano Swiss Points.','https://www.target-darts.co.uk/gabriel-clemens-g2-sp'),ev(SRC,'Local point texture is cropped from the recorded real product-image source; RGB detail is not redrawn.')])
barrel('clemens-g2-23-barrel','Gabriel Clemens G2 23g Barrel','SWISS_POINT',52,6.9,'clemens-g2','straight',evidence=[ev(WEB,'Target: 23g = 52 x 6.9 mm, 90% tungsten.','https://www.target-darts.co.uk/gabriel-clemens-g2-sp'),ev(SRC,'Local barrel texture uses original product-image pixels from the recorded authoring source.')])
shaft('clemens-g2-progrip-short','Gabriel Clemens G2 Pro Grip Short',None,'clemens-g2',evidence=[ev(WEB,'Target specifies a short Pro Grip shaft; exact millimetre length is not stated on the product page.','https://www.target-darts.co.uk/gabriel-clemens-g2-sp'),ev(SRC,'Local shaft appearance is source-grounded.'),ev(HEU,'30-mm render length remains a builder heuristic; factual length stays null.')],renderLength=30)
flight('clemens-g2-no6','Gabriel Clemens G2 Edition No.6','No.6','clemens-g2',evidence=[ev(WEB,'Target specifies Gabriel Clemens G2 edition No.6 flights.','https://www.target-darts.co.uk/gabriel-clemens-g2-sp'),ev(SRC,'Plane A uses cropped original product-image pixels.'),ev(APP,'Plane B is deliberately derived as an unknown/backface approximation and is not mirrored.')],renderLength=41.5,renderRadius=17.2,planeAStatus=SRC,visualAuthoring=WEB_SOURCE,safe=(-12,12))
preset('clemens-g2-23','Gabriel Clemens G2 23g',meta['clemens-g2']['sourceFile'],'clemens-g2-storm-nano-26','clemens-g2-23-barrel','clemens-g2-progrip-short','clemens-g2-no6',notes=['V1.3 uses a transiently downloaded real product photograph and persists only extracted dart/component pixels. Plane B remains APPROXIMATED.'],sourcePage='https://www.target-darts.co.uk/gabriel-clemens-g2-sp',sourceLabel='Gabriel Clemens G2 · source-grounded product-image extract',sourceType=WEB_SOURCE)

# Gabriel Clemens 95K – integrated K-Flex; the observed plane/body pixels come from
# a real product photograph, while unseen reverse flight surfaces remain approximated.
point('clemens-95k-storm-black-26','Gabriel Clemens 95K Swiss Storm Black 26 mm','SWISS_POINT',26,2.1,'clemens-95k',evidence=[ev(WEB,'Target specifies 26-mm Black Swiss Storm Points; 30-mm alternatives are also included.','https://www.target-darts.co.uk/gabriel-clemens-95k-sp'),ev(SRC,'Local point appearance uses original product-image pixels.')])
barrel('clemens-95k-23-barrel','Gabriel Clemens 95K 23g Barrel','SWISS_POINT',52,6.9,'clemens-95k','straight',evidence=[ev(WEB,'Target: 23g = 52 x 6.9 mm, 95% tungsten.','https://www.target-darts.co.uk/gabriel-clemens-95k-sp'),ev(SRC,'Black PVD/red-accent visual detail is retained from real product-image pixels, not redrawn.')])
rear('clemens-95k-kflex-no6-short','Gabriel Clemens 95K K-Flex No.6 Short','K-FLEX',19,'No.6','clemens-95k',evidence=[ev(WEB,'Target specifies Player-Edition No.6 K-Flex, Short, 19-mm shaft.','https://www.target-darts.co.uk/gabriel-clemens-95k-sp'),ev(SRC,'Visible rear/Plane-A pixels are source-grounded.'),ev(APP,'The unobserved second plane/backface remains approximated and the safe roll stays deliberately narrow.')],renderFlightLength=41.5,renderRadius=17.2,safe=(-12,12),planeAStatus=SRC,visualAuthoring=WEB_SOURCE)
preset('clemens-95k-23','Gabriel Clemens 95K 23g',meta['clemens-95k']['sourceFile'],'clemens-95k-storm-black-26','clemens-95k-23-barrel',rearId='clemens-95k-kflex-no6-short',notes=['Integrated K-Flex remains one RearSystemDefinition. V1.3 replaces the stylised reconstruction with original product-image pixels for the visible source-grounded side; unknown reverse surfaces remain APPROXIMATED.'],sourcePage='https://www.target-darts.co.uk/gabriel-clemens-95k-sp',sourceLabel='Gabriel Clemens 95K · source-grounded product-image extract',sourceType=WEB_SOURCE)

# Rob Cross 95K – 23g, integrated K-Flex.
point('cross-95k-storm-surge-gold-26','Rob Cross 95K Swiss Storm Surge Gold 26 mm','SWISS_POINT',26,2.1,'cross-95k',evidence=[ev(WEB,'Target specifies fitted Swiss Storm Surge Gold 26-mm points.','https://www.target-darts.co.uk/rob-cross-95k-sp'),ev(HEU,'Local appearance reconstruction only.')])
barrel('cross-95k-23-barrel','Rob Cross 95K 23g Barrel','SWISS_POINT',48,6.6,'cross-95k','straight',evidence=[ev(WEB,'Target: 23g = 48 x 6.6 mm, 95% tungsten.','https://www.target-darts.co.uk/rob-cross-95k-sp'),ev(HEU,'Local visual appearance reconstructed from web reference.')])
rear('cross-95k-kflex-no6-short','Rob Cross 95K K-Flex No.6 Short','K-FLEX',19,'No.6','cross-95k',evidence=[ev(WEB,'Target specifies No.6 Player-Edition K-Flex, Short. K-Flex keeps the planes at 90 degrees.','https://www.target-darts.co.uk/rob-cross-95k-sp'),ev(HEU,'Artwork/color is a local web-referenced reconstruction.')],renderFlightLength=41.5,renderRadius=17.2,safe=(-12,12),planeAStatus=HEU,visualAuthoring=WEB_RECON)
preset('cross-95k-23','Rob Cross 95K 23g','web-cross-95k-reconstruction.png','cross-95k-storm-surge-gold-26','cross-95k-23-barrel',rearId='cross-95k-kflex-no6-short',sourcePage='https://www.target-darts.co.uk/rob-cross-95k-sp',sourceLabel='Target Rob Cross 95K · web-referenced reconstruction',sourceType=WEB_RECON)

# Nathan Aspinall 95K – 22g, integrated K-Flex No.2. V1.4.1b replaces the
# earlier schematic reconstruction with source-grounded product-image pixels.
point('aspinall-95k-storm-black-26','Nathan Aspinall 95K Swiss Storm Black 26 mm','SWISS_POINT',26,2.1,'aspinall-95k',evidence=[ev(WEB,'Target specifies fitted Black Swiss Storm 26-mm points.','https://www.target-darts.co.uk/nathan-aspinall-95k-sp'),ev(SRC,'Point appearance is cropped from the recorded complete-dart product image.')])
barrel('aspinall-95k-22-barrel','Nathan Aspinall 95K 22g Barrel','SWISS_POINT',50,6.8,'aspinall-95k','tapered',evidence=[ev(WEB,'Target: 22g = 50 x 6.8 mm; product description identifies Nathan’s preferred tapered front profile.','https://www.target-darts.co.uk/nathan-aspinall-95k-sp'),ev(SRC,'Barrel texture uses original product-image pixels rather than the former Pillow reconstruction.')])
rear('aspinall-95k-kflex-no2-short','Nathan Aspinall 95K K-Flex No.2 Short','K-FLEX',19,'No.2','aspinall-95k',evidence=[ev(WEB,'Target specifies K-Flex No.2, Short, 19-mm shaft.','https://www.target-darts.co.uk/nathan-aspinall-95k-sp'),ev(SRC,'Rear shaft and the two face-on A-plane half-fins use pixels from the recorded product image.'),ev(APP,'White-backdrop material alpha, reverse faces and the perpendicular B-plane surfaces are approximated; no artwork is mirrored onto them.')],renderFlightLength=43,renderRadius=18.5,safe=(-12,12),planeAStatus=SRC,visualAuthoring=WEB_SOURCE)
preset('aspinall-95k-22','Nathan Aspinall 95K 22g',meta['aspinall-95k']['sourceFile'],'aspinall-95k-storm-black-26','aspinall-95k-22-barrel',rearId='aspinall-95k-kflex-no2-short',sourcePage='https://www.target-darts.co.uk/nathan-aspinall-95k-sp',sourceLabel='Target Nathan Aspinall 95K · source-grounded product-image extract',sourceType=WEB_SOURCE,notes=['Visible broadside K-Flex halves are independently rectified without mirroring. Reverse faces and the perpendicular plane remain APPROXIMATED.'])

# Stephen Bunting 95K – 23g. The page says Short; an in-box line contains a
# suspicious "33m" value, therefore factual shaftLengthMm deliberately remains
# null. V1.4.1b replaces the schematic visual reconstruction with source pixels.
point('bunting-95k-diamond-gold-26','Stephen Bunting 95K Swiss Diamond Pro Gold 26 mm','SWISS_POINT',26,2.1,'bunting-95k',evidence=[ev(WEB,'Target specifies Gold Swiss Diamond Pro Points, 26 mm.','https://www.target-darts.co.uk/stephen-bunting-95k-sp'),ev(SRC,'Gold point appearance is cropped from the recorded complete-dart product image.')])
barrel('bunting-95k-23-barrel','Stephen Bunting 95K 23g Barrel','SWISS_POINT',47,6.9,'bunting-95k','tapered',evidence=[ev(WEB,'Target: 23g = 47 x 6.9 mm, 95% tungsten; product description identifies a tapered/front-nose profile.','https://www.target-darts.co.uk/stephen-bunting-95k-sp'),ev(SRC,'Red/silver barrel surface detail is retained from original product-image pixels.')])
rear('bunting-95k-kflex-no2-short','Stephen Bunting 95K K-Flex No.2 Short','K-FLEX',None,'No.2','bunting-95k',evidence=[ev(WEB,'Target specifies Player-Edition No.2 K-Flex and Shaft Length “Short”.','https://www.target-darts.co.uk/stephen-bunting-95k-sp'),ev(UNK,'Product page box copy contains “33m”; exact millimetre shaft length is therefore intentionally not adopted as fact.'),ev(SRC,'Rear and the two face-on A-plane half-fins use source product pixels.'),ev(APP,'Smoke-flight alpha is reconstructed from the white-backdrop source; reverse faces and the perpendicular B-plane remain approximated.')],renderFlightLength=43,renderRadius=18.5,safe=(-10,10),planeAStatus=SRC,visualAuthoring=WEB_SOURCE)
preset('bunting-95k-23','Stephen Bunting 95K 23g',meta['bunting-95k']['sourceFile'],'bunting-95k-diamond-gold-26','bunting-95k-23-barrel',rearId='bunting-95k-kflex-no2-short',sourcePage='https://www.target-darts.co.uk/stephen-bunting-95k-sp',sourceLabel='Target Stephen Bunting 95K · source-grounded product-image extract',sourceType=WEB_SOURCE,notes=['Exact K-Flex millimetre length remains UNKNOWN. Visible broadside K-Flex halves are source-grounded; reverse/perpendicular surfaces remain APPROXIMATED.'])

# Michael van Gerwen Signature Edition – 22g classic modular.
point('mvg-signature-steel-point','MvG Signature Steeltip (exact length unknown)','PRESS_FIT',None,2.1,'mvg-signature',evidence=[ev(WEB,'Winmau specifies Steeltip, but not the point length on the product page.','https://winmau.com/en-de/products/mvg-signature-edition'),ev(UNK,'Exact point length remains unknown; 32-mm render length is heuristic.')],render=32)
barrel('mvg-signature-22-barrel','Michael van Gerwen Signature 22g Barrel','PRESS_FIT',53,6.3,'mvg-signature','straight',evidence=[ev(WEB,'Winmau verifies 90% tungsten, centre weighting and parallel barrel profile.','https://winmau.com/en-de/products/mvg-signature-edition'),ev(WEB,'Dartworld lists the 22g barrel at 53.00 x 6.30 mm.','https://www.dartworld.de/steel-darts/nach-preis/winmau-michael-van-gerwen-mvg-signature-edition-90?c=22162'),ev(HEU,'Local visual appearance reconstructed from inspected product image.')])
shaft('mvg-signature-vecta-short','MvG Signature Vecta Short Shaft',None,'mvg-signature',evidence=[ev(WEB,'Winmau specifies Short Vecta shafts.','https://winmau.com/en-de/products/mvg-signature-edition'),ev(HEU,'30-mm render length used because the product page does not state physical shaft length.')],renderLength=30)
flight('mvg-signature-no2','MvG Signature #2 100 Micron Flight','No.2','mvg-signature',evidence=[ev(WEB,'Winmau specifies #2 Shape 100 Micron flights.','https://winmau.com/en-de/products/mvg-signature-edition'),ev(HEU,'Artwork is a local reconstruction from public product imagery.')],renderLength=43,renderRadius=18.5,planeAStatus=HEU,visualAuthoring=WEB_RECON)
preset('mvg-signature-22','Michael van Gerwen Signature Edition 22g','web-mvg-signature-reconstruction.png','mvg-signature-steel-point','mvg-signature-22-barrel','mvg-signature-vecta-short','mvg-signature-no2',sourcePage='https://winmau.com/en-de/products/mvg-signature-edition',sourceLabel='Winmau MvG Signature · web-referenced reconstruction',sourceType=WEB_RECON,notes=['22g barrel dimensions come from a current retailer because Winmau’s current page exposes weights and profile but not dimensional table.'])

# Luke Humphries Prestige – classic modular. V1.3.1 uses extracted product pixels;
# the internal 22g ID remains only as compatibility/variant metadata.
point('humphries-prestige-black-point','Luke Humphries Prestige Black High Tensile Point','PRESS_FIT',None,2.1,'humphries-prestige',evidence=[ev(WEB,'Winmau identifies the point type as Black high tensile; exact length is not published.','https://winmau.com/en-de/products/luke-humphries-prestige-darts'),ev(SRC,'Local point texture is cropped from the recorded real product-image source.'),ev(UNK,'Exact point length remains unknown; 32-mm render length is heuristic.')],render=32)
barrel('humphries-prestige-22-barrel','Luke Humphries Prestige 22g Barrel','PRESS_FIT',43.18,7.3,'humphries-prestige','torpedo',evidence=[ev(WEB,'Winmau: 22g = 7.3 x 43.18 mm; 90% tungsten; front-weighted torpedo profile.','https://winmau.com/en-de/products/luke-humphries-prestige-darts'),ev(SRC,'Local barrel appearance uses extracted product-image pixels rather than a redrawn approximation.')])
shaft('humphries-prestige-nitrotech-short','Luke Humphries Prestige Nitrotech Short',None,'humphries-prestige',evidence=[ev(WEB,'Winmau specifies Nitrotech polycarbonate short shafts.','https://winmau.com/en-de/products/luke-humphries-prestige-darts'),ev(SRC,'Local shaft appearance uses extracted product-image pixels.'),ev(HEU,'30-mm render length is a geometry heuristic; factual millimetre length remains unknown.')],renderLength=30)
flight('humphries-prestige-standard','Luke Humphries Players Extra Thick Standard','Standard','humphries-prestige',evidence=[ev(WEB,'Winmau specifies Players extra thick standard flights.','https://winmau.com/en-de/products/luke-humphries-prestige-darts'),ev(SRC,'Visible Plane-A pixels are extracted from the product broadside; the photographed fold/cross-fin is de-occluded before 3D mapping.'),ev(APP,'Plane B and the source-hidden de-occlusion strip remain approximated.')],renderLength=43,renderRadius=18.2,planeAStatus=SRC,visualAuthoring=WEB_SOURCE,safe=(-10,10))
preset('humphries-prestige-22','Luke Humphries Prestige 22g',meta['humphries-prestige']['sourceFile'],'humphries-prestige-black-point','humphries-prestige-22-barrel','humphries-prestige-nitrotech-short','humphries-prestige-standard',sourcePage='https://winmau.com/en-de/products/luke-humphries-prestige-darts',sourceLabel='Winmau Luke Humphries Prestige · source-grounded product-image extract',sourceType=WEB_SOURCE,notes=['Plane A uses source pixels with an explicitly approximated centre strip where the product photo is occluded by the folded cross-fin; Plane B remains APPROXIMATED.'])

web_player_sources=[
 {'presetId':'clemens-g2-23','player':'Gabriel Clemens','product':'Target Gabriel Clemens G2 SP','officialPage':'https://www.target-darts.co.uk/gabriel-clemens-g2-sp','imageReference':meta['clemens-g2']['sourceUrl'],'visualStatus':WEB_SOURCE,'originalPixels':True,'componentProvenance':meta['clemens-g2']['componentProvenance'],'flightExtractionMode':meta['clemens-g2'].get('flightExtractionMode'),'flightApproximation':meta['clemens-g2'].get('flightApproximation')},
 {'presetId':'clemens-95k-23','player':'Gabriel Clemens','product':'Target Gabriel Clemens 95K SP','officialPage':'https://www.target-darts.co.uk/gabriel-clemens-95k-sp','imageReference':meta['clemens-95k']['sourceUrl'],'visualStatus':WEB_SOURCE,'originalPixels':True,'componentProvenance':meta['clemens-95k']['componentProvenance'],'flightExtractionMode':meta['clemens-95k'].get('flightExtractionMode'),'flightApproximation':meta['clemens-95k'].get('flightApproximation')},
 {'presetId':'cross-95k-23','player':'Rob Cross','product':'Target Rob Cross 95K SP 23g','officialPage':'https://www.target-darts.co.uk/rob-cross-95k-sp','imageReference':'https://www.thedartdepot.co.nz/cdn/shop/files/RobCross95kDart_1_1024x.png?v=1733949037','visualStatus':WEB_RECON},
 {'presetId':'aspinall-95k-22','player':'Nathan Aspinall','product':'Target Nathan Aspinall 95K SP 22g','officialPage':'https://www.target-darts.co.uk/nathan-aspinall-95k-sp','imageReference':meta['aspinall-95k']['sourceUrl'],'visualStatus':WEB_SOURCE,'originalPixels':True,'componentProvenance':meta['aspinall-95k']['componentProvenance'],'flightExtractionMode':meta['aspinall-95k'].get('flightExtractionMode'),'flightApproximation':meta['aspinall-95k'].get('flightApproximation'),'finFaceAuthoring':meta['aspinall-95k'].get('finFaceAuthoring')},
 {'presetId':'bunting-95k-23','player':'Stephen Bunting','product':'Target Stephen Bunting 95K SP 23g','officialPage':'https://www.target-darts.co.uk/stephen-bunting-95k-sp','imageReference':meta['bunting-95k']['sourceUrl'],'visualStatus':WEB_SOURCE,'originalPixels':True,'componentProvenance':meta['bunting-95k']['componentProvenance'],'flightExtractionMode':meta['bunting-95k'].get('flightExtractionMode'),'flightApproximation':meta['bunting-95k'].get('flightApproximation'),'finFaceAuthoring':meta['bunting-95k'].get('finFaceAuthoring')},
 {'presetId':'mvg-signature-22','player':'Michael van Gerwen','product':'Winmau MvG Signature Edition 22g','officialPage':'https://winmau.com/en-de/products/mvg-signature-edition','imageReference':'https://www.bullydarts.co.uk/cdn/shop/files/1550_MVG_Signature_22g_image1.jpg?v=1765467371&width=4472','visualStatus':WEB_RECON},
 {'presetId':'humphries-prestige-22','player':'Luke Humphries','product':'Luke Humphries Prestige','officialPage':'https://winmau.com/en-de/products/luke-humphries-prestige-darts','imageReference':meta['humphries-prestige']['sourceUrl'],'visualStatus':WEB_SOURCE,'originalPixels':True,'componentProvenance':meta['humphries-prestige']['componentProvenance'],'flightExtractionMode':meta['humphries-prestige'].get('flightExtractionMode'),'flightApproximation':meta['humphries-prestige'].get('flightApproximation')},
]
for item in web_player_sources:
    presets[item['presetId']]['referenceImageUrl']=item['imageReference']

catalog={
 'schemaVersion':1,
 'rendererContract':{'width':789,'height':331,'tip':{'x':0,'y':212},'flightPlaneModel':'FOUR_EXPLICIT_RADIAL_FINS_0_90_180_270_WITH_SEPARATE_FACE_SURFACES','poseModel':'axis Vec3 + roll','screenRotation':'outside renderer','flatPerspective3DPath':False},
 'evidenceStatus':[SRC,WEB,HEU,APP,UNK],
 'compatibility':{
   'rules':[
     'PointDefinition.interface must equal BarrelDefinition.pointInterface.',
     'BarrelDefinition.rearThread must equal ShaftDefinition.rearThread or RearSystemDefinition.rearThread.',
     'ShaftDefinition.flightMount must equal FlightDefinition.flightMount.',
     'RearSystemDefinition is mutually exclusive with ShaftDefinition + FlightDefinition.',
     'Integrated rear system remains one catalog entity; renderer may internally split it into shaft-core + optional rear-root + four radial flight fins.',
   ],
   'interfaces':{'SWISS_POINT':'Target Swiss Point compatible barrel nose','PRESS_FIT':'traditional steel point press-fit','2BA':'standard rear barrel thread','FOLDED_FLIGHT_SLOT':'classic shaft slot / separate folded flight'}
 },
 'components':{'points':points,'barrels':barrels,'shafts':shafts,'flights':flights,'rearSystems':rears},
 'presets':presets,
 'sourceAnalysis':source_analysis,
 'webPlayerSources':web_player_sources,
}
(ROOT/'data/catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf-8')
(ROOT/'data/source-analysis.json').write_text(json.dumps(source_analysis,indent=2,ensure_ascii=False),encoding='utf-8')
print(f"{len(points)} points, {len(barrels)} barrels, {len(shafts)} shafts, {len(flights)} flights, {len(rears)} rear systems, {len(presets)} presets")
