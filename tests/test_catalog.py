from pathlib import Path
import json, sys, math, re
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
source_grounded_players={'clemens-g2-23','clemens-95k-23'}
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
        check(provenance.get('flight-plane-a')=='SOURCE-GROUNDED',f'{pid}: plane A not source-grounded')
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

# Visible preset labels are render-design identities, not SKU/weight identities.
for pid,p in cat['presets'].items():
    check(re.search(r'\\b\\d+(?:[.,]\\d+)?g\\b',p.get('name',''),re.I) is None,f'{pid}: visible preset name still contains gram weight: {p.get("name")}')

# Explicit uncertainty checks prevent accidental laundering of heuristic dimensions into facts.
check(c['barrels']['shift-barrel']['diameterMm'] is None,'Shift source weight unresolved: factual diameter must stay null')
check(c['barrels']['gary-phase6-barrel']['lengthMm'] is None,'Gary source weight unresolved: factual length must stay null')
check(c['barrels']['auro-90-barrel']['lengthMm'] is None,'Auro source weight unresolved: factual length must stay null')

if errors:
    print('FAIL')
    for e in errors:print('-',e)
    sys.exit(1)
print(f"PASS: {len(cat['sourceAnalysis'])} sources, {len(cat['presets'])} presets, strict evidence and compatibility invariants valid")
