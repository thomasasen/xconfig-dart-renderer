from pathlib import Path
import json, sys, math, re
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
cat=json.loads((ROOT/'data/catalog.json').read_text())
author=json.loads((ROOT/'data/authoring-metadata.json').read_text())
errors=[]
def check(cond,msg):
    if not cond: errors.append(msg)

check(cat['rendererContract']['width']==789,'renderer width != 789')
check(cat['rendererContract']['height']==331,'renderer height != 331')
check(cat['rendererContract']['tip']=={'x':0,'y':212},'tip != (0,212)')
check(cat['rendererContract']['flightPlaneModel']=='TWO_FULL_INTERSECTING_PLANES_SHARED_AXIS_90_DEG','wrong V4 flight model')
check(cat['rendererContract']['flatPerspective3DPath'] is False,'flatPerspective must be off in 3D path')
check(len(cat['sourceAnalysis'])==15,f"expected 15 sources, got {len(cat['sourceAnalysis'])}")
classes={'CLASSIC_MODULAR','INTEGRATED_REAR_SYSTEM','GEOMETRY_REFERENCE','ANGLED_REFERENCE','NEEDS_MANUAL_REVIEW'}
for s in cat['sourceAnalysis']:
    check(s['classification'] in classes,f"bad classification {s['file']}")
    check((ROOT/'assets/source'/s['file']).exists(),f"missing source {s['file']}")

required=[
    'prodigy-23','shift','gary-phase6','chrono','world-champion','auro','supa-venom','mandalorian-24',
    'clemens-g2-23','clemens-95k-23','cross-95k-23','aspinall-95k-22','bunting-95k-23',
    'mvg-signature-22','humphries-prestige-22',
]
for p in required: check(p in cat['presets'],f'missing required preset {p}')

c=cat['components']
for pid,p in cat['presets'].items():
    point=c['points'].get(p['pointId']); barrel=c['barrels'].get(p['barrelId'])
    check(point is not None,f'{pid}: missing point');check(barrel is not None,f'{pid}: missing barrel')
    if point and barrel: check(point['interface']==barrel['pointInterface'],f'{pid}: point/barrel interface mismatch')
    rid=p.get('rearSystemId')
    if rid:
        rear=c['rearSystems'].get(rid);check(rear is not None,f'{pid}: missing rear');check(not p.get('shaftId') and not p.get('flightId'),f'{pid}: integrated rear must exclude shaft/flight')
        if rear and barrel: check(rear['rearThread']==barrel['rearThread'],f'{pid}: rear/barrel thread mismatch')
    else:
        shaft=c['shafts'].get(p.get('shaftId')); flight=c['flights'].get(p.get('flightId'))
        check(shaft is not None,f'{pid}: missing shaft');check(flight is not None,f'{pid}: missing flight')
        if shaft and barrel:check(shaft['rearThread']==barrel['rearThread'],f'{pid}: shaft/barrel thread mismatch')
        if shaft and flight:check(shaft['flightMount']==flight['flightMount'],f'{pid}: shaft/flight mount mismatch')

# Every referenced texture must exist and every evidence status must be in the strict vocabulary.
statuses=set(cat['evidenceStatus'])
for group,items in c.items():
    for cid,o in items.items():
        for e in o.get('evidence',[]): check(e.get('status') in statuses,f'{group}/{cid}: bad evidence status {e.get("status")}')
        for k,v in o.items():
            if k.lower().endswith('texture') and isinstance(v,str): check((ROOT/v.replace('./','')).exists(),f'{group}/{cid}: missing texture {v}')
        if o.get('kind') in ('FlightDefinition','RearSystemDefinition'):
            check(len(o.get('planeProfile',[]))>=6,f'{group}/{cid}: flight profile too small')
            plane_a = o.get('faceEvidence',{}).get('planeA')
            if cid == 'generic-slim-geometry' or o.get('visualAuthoring') == 'WEB-REFERENCED-RECONSTRUCTION':
                check(plane_a=='HEURISTIC',f'{group}/{cid}: reconstructed/generic plane A must remain explicitly HEURISTIC')
            else:
                check(plane_a=='SOURCE-GROUNDED',f'{group}/{cid}: product plane A must be source grounded')
            check(o.get('faceEvidence',{}).get('planeB')=='APPROXIMATED',f'{group}/{cid}: plane B must be approximated unless verified')

# Web-researched player presets must keep their provenance explicit and their
# local source panels present. In particular, Gabriel Clemens is a hard user
# requirement and is covered in both a classic and integrated rear setup.
web_sources={x['presetId']:x for x in cat.get('webPlayerSources',[])}
check({'clemens-g2-23','clemens-95k-23'} <= set(web_sources),'Gabriel Clemens web presets missing')
source_grounded_players={'clemens-g2-23','clemens-95k-23','humphries-prestige-22'}
for pid,entry in web_sources.items():
    p=cat['presets'].get(pid)
    check(p is not None,f'web source points at missing preset {pid}')
    if not p: continue
    expected='SOURCE-GROUNDED-WEB-EXTRACT' if pid in source_grounded_players else 'WEB-REFERENCED-RECONSTRUCTION'
    check(p.get('sourceType')==expected,f'{pid}: wrong source type {p.get("sourceType")} != {expected}')
    check(bool(p.get('sourcePage')),f'{pid}: missing official/source page')
    check(bool(entry.get('imageReference')),f'{pid}: missing researched image reference')
    src=p.get('sourceImage','').replace('./','')
    check((ROOT/src).exists(),f'{pid}: missing local source panel {src}')
    if pid in source_grounded_players:
        check(entry.get('originalPixels') is True,f'{pid}: source-grounded entry must assert originalPixels=true')
        provenance=entry.get('componentProvenance',{})
        check(provenance.get('barrel')=='SOURCE-GROUNDED',f'{pid}: barrel not source-grounded')
        if pid=='clemens-g2-23':
            check(provenance.get('flight-plane-a')=='SOURCE-GROUNDED',f'{pid}: flat-source Plane A must remain source-grounded')
            check(entry.get('flightExtractionMode')=='FLAT_FLIGHT_SOURCE',f'{pid}: expected dedicated flat-flight extraction')
        else:
            check(provenance.get('flight-plane-a')=='SOURCE-GROUNDED+APPROXIMATED-OCCLUSION',f'{pid}: side-view Plane A must disclose de-occlusion approximation')
            check(entry.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED',f'{pid}: side-view must de-occlude photographed cross-fin')
        check(provenance.get('flight-plane-b-approx')=='APPROXIMATED',f'{pid}: plane B must remain approximated')

# G2 Plane A must come from the exact flat No.6 source, not from the assembled
# dart's already-perspectival composite flight. This prevents a regression to the
# original four-times/composite-flight failure mode.
g2_author=author.get('clemens-g2',{})
g2_sources=g2_author.get('componentSources',{})
check(bool(g2_sources.get('flight-plane-a')), 'clemens-g2: missing dedicated Plane-A source')
check(g2_sources.get('flight-plane-a') != g2_author.get('sourceUrl'), 'clemens-g2: Plane A must not reuse assembled composite-flight image')
check('336870' in g2_sources.get('flight-plane-a',''), 'clemens-g2: Plane A must use exact G2 No.6 SKU 336870 source')

k95_author=author.get('clemens-95k',{})
check('gabriel-clemens-95k-steel-tip-dart-sp-03.jpg' in k95_author.get('sourceUrl',''), 'clemens-95k: expected official complete side-view source')

# Side-view integrated systems must no longer feed a photographed composite flight
# directly into a renderer plane. Plane A is de-occluded at the source-hidden cross-fin
# band; Plane B deliberately suppresses readable front-side artwork.
for product in ('prodigy','shift','world'):
    info=author.get(product,{})
    check(info.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED',f'{product}: composite flight was not canonicalized')
    check(info.get('flightPlaneAProvenance')=='SOURCE-GROUNDED+APPROXIMATED-OCCLUSION',f'{product}: Plane A provenance does not disclose de-occlusion')
    check(info.get('flightPlaneBProvenance')=='APPROXIMATED',f'{product}: Plane B must remain approximated')
    frac=float((info.get('flightApproximation') or {}).get('approximatedPixelFraction',0))
    check(0 < frac < .45,f'{product}: de-occlusion fraction implausible: {frac}')

check(k95_author.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED','clemens-95k: composite K-Flex face must be de-occluded')
check((k95_author.get('componentProvenance') or {}).get('flight-plane-a')=='SOURCE-GROUNDED+APPROXIMATED-OCCLUSION','clemens-95k: Plane A provenance must disclose approximated occlusion strip')

def high_frequency_energy(path):
    im=Image.open(ROOT/path.replace('./','')).convert('L')
    arr=np.asarray(im,dtype=np.float32)
    if arr.shape[0]<2 or arr.shape[1]<2:return 0.0
    return float(np.abs(np.diff(arr,axis=0)).mean()+np.abs(np.diff(arr,axis=1)).mean())

for group in ('flights','rearSystems'):
    for cid,obj in c[group].items():
        a=obj.get('planeATexture'); b=obj.get('planeBTexture')
        if not a or not b: continue
        ea=high_frequency_energy(a); eb=high_frequency_energy(b)
        if ea>3.0:
            check(eb <= ea*.82+0.25,f'{group}/{cid}: approximated Plane B retains too much copied front-side detail ({eb:.2f} vs {ea:.2f})')

# Visible preset labels are render-design identities, not SKU/weight identities.
weight_re=re.compile(r'\b\d+(?:[.,]\d+)?\s*g\b',re.I)
for pid,p in cat['presets'].items():
    check(weight_re.search(p.get('name','')) is None,f'{pid}: visible preset name still contains gram weight: {p.get("name")}')
for group,items in c.items():
    for cid,obj in items.items():
        check(weight_re.search(obj.get('name','')) is None,f'{group}/{cid}: visible component name still contains gram weight: {obj.get("name")}')
expected_names={
    'prodigy-23':'Target Luke Littler G1 Prodigy',
    'shift':'Target Shift SP',
    'world-champion':'Target Luke Littler G1 World Champion',
    'clemens-g2-23':'Gabriel Clemens G2',
    'clemens-95k-23':'Gabriel Clemens 95K',
    'humphries-prestige-22':'Luke Humphries Prestige',
}
for pid,name in expected_names.items():
    check(cat['presets'][pid]['name']==name,f'{pid}: wrong visible name {cat["presets"][pid]["name"]!r}')

# Explicit uncertainty checks prevent accidental laundering of heuristic dimensions into facts.
check(c['barrels']['shift-barrel']['diameterMm'] is None,'Shift source weight unresolved: factual diameter must stay null')
check(c['barrels']['gary-phase6-barrel']['lengthMm'] is None,'Gary source weight unresolved: factual length must stay null')
check(c['barrels']['auro-90-barrel']['lengthMm'] is None,'Auro source weight unresolved: factual length must stay null')

if errors:
    print('FAIL')
    for e in errors:print('-',e)
    sys.exit(1)
print(f"PASS: {len(cat['sourceAnalysis'])} sources, {len(cat['presets'])} presets, strict evidence and compatibility invariants valid")
