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
    comparison=p.get('comparisonSourceImage','').replace('./','')
    check(bool(comparison),f'{pid}: missing comparisonSourceImage')
    if comparison: check((ROOT/comparison).exists(),f'{pid}: comparison source missing: {comparison}')
    source_pose=p.get('sourceComparisonPose') or {}
    check(source_pose.get('provenance')=='HEURISTIC-SOURCE-MATCH',f'{pid}: source comparison pose must stay explicitly heuristic')
    check(abs(float(source_pose.get('incidenceDeg',999))) <= 1e-9,f'{pid}: source comparison must not add incidence perspective')
    rid=p.get('rearSystemId')
    if rid:
        rear=c['rearSystems'].get(rid);check(rear is not None,f'{pid}: missing rear');check(not p.get('shaftId') and not p.get('flightId'),f'{pid}: integrated rear must exclude shaft/flight')
        if rear and barrel: check(rear['rearThread']==barrel['rearThread'],f'{pid}: rear/barrel thread mismatch')
    else:
        shaft=c['shafts'].get(p.get('shaftId')); flight=c['flights'].get(p.get('flightId'))
        check(shaft is not None,f'{pid}: missing shaft');check(flight is not None,f'{pid}: missing flight')
        if shaft and barrel:check(shaft['rearThread']==barrel['rearThread'],f'{pid}: shaft/barrel thread mismatch')
        if shaft and flight:check(shaft['flightMount']==flight['flightMount'],f'{pid}: shaft/flight mount mismatch')

# V1.3.3 tail authoring metadata is a hard contract for every source-grounded
# product image that passed through the shared analyzer.
tail_statuses={'PASS','NEEDS_MANUAL_REVIEW','FAIL_AXIS','FAIL_ROOT_INCLUDED_IN_SHAFT','FAIL_ROOT_ALIGNMENT','FAIL_ALPHA_HAZE','FAIL_SOURCE_UNSUITABLE'}
for product,info in author.items():
    ta=info.get('tailAuthoring')
    metrics=info.get('tailMetrics')
    if not ta or not metrics:
        continue
    status=ta.get('status')
    check(status in tail_statuses,f'{product}: unknown tail authoring status {status}')
    median=max(1e-6,float(metrics.get('medianShaftWidthPx',1)))
    check(float(metrics.get('shaftWidthCV',999)) <= .18,f'{product}: shaft width CV too high: {metrics.get("shaftWidthCV")}')
    check(float(metrics.get('shaftAxisResidual',999)) <= median*.08,f'{product}: shaft axis residual too high: {metrics.get("shaftAxisResidual")} / {median}')
    check(float(metrics.get('shaftCenterJump',999)) <= .25,f'{product}: shaft center jump too high: {metrics.get("shaftCenterJump")}')
    check(float(metrics.get('tailAlphaHaze',999)) <= .10,f'{product}: tail alpha haze too high: {metrics.get("tailAlphaHaze")}')
    check(status in ('PASS','NEEDS_MANUAL_REVIEW'),f'{product}: hard tail QA failure: {status}')
    if info.get('rearIntegrated') and info.get('rootAuthored'):
        check((ROOT/'assets/components'/product/'rear-shaft-core.png').exists(),f'{product}: shaft-core asset missing')
        check((ROOT/'assets/components'/product/'rear-root.png').exists(),f'{product}: rear-root asset missing')

# Every referenced texture must exist and every evidence status must be in the strict vocabulary.
statuses=set(cat['evidenceStatus'])
for group,items in c.items():
    for cid,o in items.items():
        for e in o.get('evidence',[]): check(e.get('status') in statuses,f'{group}/{cid}: bad evidence status {e.get("status")}')
        for k,v in o.items():
            if k.lower().endswith('texture') and isinstance(v,str): check((ROOT/v.replace('./','')).exists(),f'{group}/{cid}: missing texture {v}')
        if o.get('kind') == 'RearSystemDefinition' and o.get('tailQa'):
            check(o.get('shaftTexture','').endswith('/rear-shaft-core.png'),f'{group}/{cid}: tail-authored rear must use shaft-core texture')
        if o.get('kind') == 'RearSystemDefinition' and o.get('rootTexture'):
            check(float(o.get('renderRootLengthMm',0)) > 0,f'{group}/{cid}: root length must be positive')
            check(float(o.get('renderRootFrontDiameterMm',0)) > 0,f'{group}/{cid}: root front diameter missing')
            check(float(o.get('renderRootRearDiameterMm',0)) >= float(o.get('renderRootFrontDiameterMm',0))*.9,f'{group}/{cid}: root rear diameter implausible')
            check(0 <= float(o.get('flightRootOverlapMm',-1)) <= 2.0,f'{group}/{cid}: flight root overlap out of range')
            check(bool(o.get('tailQa')),f'{group}/{cid}: root-enabled rear missing tail QA metadata')
        if o.get('kind') in ('FlightDefinition','RearSystemDefinition'):
            check(len(o.get('planeProfile',[]))>=6,f'{group}/{cid}: flight profile too small')
            plane_a = o.get('faceEvidence',{}).get('planeA')
            if cid == 'generic-slim-geometry' or o.get('visualAuthoring') == 'WEB-REFERENCED-RECONSTRUCTION':
                check(plane_a=='HEURISTIC',f'{group}/{cid}: reconstructed/generic plane A must remain explicitly HEURISTIC')
            else:
                check(plane_a=='SOURCE-GROUNDED',f'{group}/{cid}: product plane A must be source grounded')
            check(o.get('faceEvidence',{}).get('planeB')=='APPROXIMATED',f'{group}/{cid}: plane B must be approximated unless verified')
            # V1.4: photographed silhouette/perspective is artwork evidence only.
            # Physical fin geometry must come from a canonical profile, while source
            # pixels are fitted through an explicit UV envelope.
            check(o.get('planeProfileProvenance')=='CANONICAL-GEOMETRY-NOT-PHOTOGRAPHED-POSE',
                  f'{group}/{cid}: photographed flight silhouette leaked into 3D geometry')
            profile=o.get('planeProfile') or []
            if profile:
                top=max(float(p[1]) for p in profile)
                bottom=min(float(p[1]) for p in profile)
                check(top > .5 and bottom < -.5,f'{group}/{cid}: canonical flight profile has insufficient fin extent')
                check(abs(top + bottom) <= .08,f'{group}/{cid}: canonical flight profile is not vertically balanced ({top}, {bottom})')
            envelope=o.get('planeUvEnvelope') or []
            check(len(envelope)>=12,f'{group}/{cid}: source UV envelope too small')
            previous_u=-1.0
            for row in envelope:
                check(len(row)==3,f'{group}/{cid}: malformed UV envelope row {row}')
                if len(row)!=3: continue
                u,upper,lower=map(float,row)
                check(previous_u <= u <= 1.0,f'{group}/{cid}: UV envelope is not monotonic')
                check(0.0 <= upper <= lower <= 1.0,f'{group}/{cid}: invalid UV envelope bounds {row}')
                previous_u=u

# Web-researched player presets must keep their provenance explicit and their
# local source panels present. In particular, Gabriel Clemens is a hard user
# requirement and is covered in both a classic and integrated rear setup.
web_sources={x['presetId']:x for x in cat.get('webPlayerSources',[])}
check({'clemens-g2-23','clemens-95k-23'} <= set(web_sources),'Gabriel Clemens web presets missing')
source_grounded_players={
    'clemens-g2-23','clemens-95k-23','cross-95k-23','aspinall-95k-22',
    'bunting-95k-23','mvg-signature-22','humphries-prestige-22'
}
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
for product in ('prodigy','shift','gary','chrono','world','auro','supa','atat'):
    info=author.get(product,{})
    check(info.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED',f'{product}: photographed composite flight was not canonicalized')
    check(info.get('flightPlaneAProvenance')=='SOURCE-GROUNDED+APPROXIMATED-OCCLUSION',f'{product}: Plane A provenance does not disclose de-occlusion')
    check(info.get('flightPlaneBProvenance')=='APPROXIMATED',f'{product}: Plane B must remain approximated')
    approx=info.get('flightApproximation') or {}
    check(approx.get('deocclusionMethod')=='STRIP_COLLAPSE_RESAMPLE',f'{product}: wrong de-occlusion method {approx.get("deocclusionMethod")}')
    frac=float(approx.get('approximatedPixelFraction',0))
    check(0 < frac < .45,f'{product}: de-occlusion fraction implausible: {frac}')

mandalorian_author=author.get('mandalorian',{})
check(mandalorian_author.get('flightExtractionMode')=='DEDICATED_FRONTAL_KFLEX_SOURCE','mandalorian: must use a dedicated frontal K-Flex source instead of the infographic composite crop')
check((mandalorian_author.get('flightApproximation') or {}).get('deocclusionMethod')=='FRONTAL_RIDGE_STRIP_COLLAPSE','mandalorian: frontal K-Flex ridge removal is not active')
check('360523_Target_StarWars_Mandalorian_SP_Steeldarts_1Set.png' in (mandalorian_author.get('flightSourceUrl') or '') or 'mandalorian95.png' in (mandalorian_author.get('flightSourceUrl') or ''),'mandalorian: unexpected dedicated blue No.2 flight source')
check((ROOT/'assets/source/web-mandalorian-kflex-frontal-source-grounded.png').exists(),'mandalorian: dedicated frontal QA source missing')
check((mandalorian_author.get('flightApproximation') or {}).get('design')=='MANDALORIAN_BLUE_SOURCE_ARTWORK','mandalorian: dedicated flight source is not tagged as blue Mandalorian artwork')
check((mandalorian_author.get('flightApproximation') or {}).get('canonicalProfile')=='NO6_SUPPLIED_INFOGRAPHIC','mandalorian: dedicated flight is not masked to supplied No.6 profile')
check((mandalorian_author.get('flightApproximation') or {}).get('profileMaskApplied') is True,'mandalorian: No.6 profile mask was not applied')
mando_rear=c['rearSystems'].get('mandalorian-kflex-short',{})
check(mando_rear.get('flightShape')=='No.6',f"mandalorian: mounted flight shape must follow supplied infographic No.6, got {mando_rear.get('flightShape')}")
check(abs(float(mando_rear.get('renderFlightLengthMm',0))-41.5)<1e-9,'mandalorian: No.6 render length must be 41.5 mm')
check(abs(float(mando_rear.get('renderFlightRadiusMm',0))-17.2)<1e-9,'mandalorian: No.6 render radius must be 17.2 mm')
m_frac=float((mandalorian_author.get('flightApproximation') or {}).get('approximatedPixelFraction',0))
check(.15 < m_frac < .35,f'mandalorian: dedicated-source approximation fraction implausible: {m_frac}')

check(k95_author.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED','clemens-95k: composite K-Flex face must be de-occluded')
check((k95_author.get('flightApproximation') or {}).get('deocclusionMethod')=='STRIP_COLLAPSE_RESAMPLE','clemens-95k: wrong de-occlusion method')
check((k95_author.get('componentProvenance') or {}).get('flight-plane-a')=='SOURCE-GROUNDED+APPROXIMATED-OCCLUSION','clemens-95k: Plane A provenance must disclose approximated occlusion strip')

humphries_author=author.get('humphries-prestige',{})
check(humphries_author.get('flightExtractionMode')=='PRIMARY_FACE_DEOCCLUDED','humphries-prestige: product side-view flight must be canonicalized')
check((humphries_author.get('flightApproximation') or {}).get('deocclusionMethod')=='STRIP_COLLAPSE_RESAMPLE','humphries-prestige: wrong de-occlusion method')

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
