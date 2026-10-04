from pathlib import Path
import json, sys, math, re
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from flight_geometry_reference import NO6_PROFILE, NO2_PROFILE, STANDARD_PROFILE, VAPOR_S_PROFILE, REFERENCE_DIMENSIONS
cat=json.loads((ROOT/'data/catalog.json').read_text())
author=json.loads((ROOT/'data/authoring-metadata.json').read_text())
errors=[]
def check(cond,msg):
    if not cond: errors.append(msg)

check(cat['rendererContract']['width']==789,'renderer width != 789')
check(cat['rendererContract']['height']==331,'renderer height != 331')
check(cat['rendererContract']['tip']=={'x':0,'y':212},'tip != (0,212)')
check(cat['rendererContract']['flightPlaneModel']=='FOUR_EXPLICIT_RADIAL_FINS_0_90_180_270_WITH_SEPARATE_FACE_SURFACES','wrong V4 flight model')
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

# V1.4.2 P5: No.2 must read as a dart flight, not an axe head.
# The contour must widen gradually from the shaft, reach maximum width only in the
# rear-middle region, then taper smoothly to a narrower trailing edge.
def positive_envelope(profile):
    return [(float(x), abs(float(y))) for x,y in profile if float(y) >= -1e-9]

no2_pos=positive_envelope(NO2_PROFILE)
check(len(NO2_PROFILE) >= 30, f'No.2 contour too coarse: {len(NO2_PROFILE)} points')
check(abs(NO2_PROFILE[0][1]) < 1e-9, 'No.2 root must start on the dart axis')
check(abs(NO2_PROFILE[-1][1]) < .10, 'No.2 mirrored root must return close to the dart axis')
peak=max(no2_pos,key=lambda p:p[1])
check(.68 <= peak[0] <= .78 and abs(peak[1]-1.0)<1e-9, f'No.2 peak in wrong place: {peak}')

def env_at(profile,u):
    pts=[(float(x),abs(float(y))) for x,y in profile if float(y)>=-1e-9]
    pts=sorted(pts,key=lambda p:p[0])
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        if x0 <= u <= x1 and x1>x0:
            t=(u-x0)/(x1-x0)
            return y0+(y1-y0)*t
    return pts[-1][1] if pts else 0

check(env_at(NO2_PROFILE,.20) <= .43, f'No.2 flares too early near shaft: {env_at(NO2_PROFILE,.20):.3f}')
check(.80 <= env_at(NO2_PROFILE,.50) <= .92, f'No.2 shoulder progression implausible: {env_at(NO2_PROFILE,.50):.3f}')
check(.36 <= env_at(NO2_PROFILE,1.0) <= .44, f'No.2 trailing edge too wide/narrow: {env_at(NO2_PROFILE,1.0):.3f}')

# Positive upper envelope is monotone rising to peak and monotone falling afterwards.
upper=sorted({(float(x),abs(float(y))) for x,y in NO2_PROFILE if float(y)>=-1e-9},key=lambda p:p[0])
peak_idx=max(range(len(upper)),key=lambda i:upper[i][1])
check(all(upper[i+1][1] >= upper[i][1]-1e-9 for i in range(peak_idx)), 'No.2 front shoulder contains an inward notch')
check(all(upper[i+1][1] <= upper[i][1]+1e-9 for i in range(peak_idx,len(upper)-1)), 'No.2 rear shoulder contains an outward notch')

# Prodigy is the regression preset that exposed the axe-head silhouette.
prodigy=cat['presets']['prodigy-23']
prodigy_rear=c['rearSystems'][prodigy['rearSystemId']]
check(prodigy_rear.get('flightShape')=='No.2','prodigy: expected No.2 K-Flex family')
check(prodigy_rear.get('planeProfile')==NO2_PROFILE,'prodigy: must use the canonical smooth No.2 contour')

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

# Web-researched player presets must keep their provenance explicit and their
# local source panels present. In particular, Gabriel Clemens is a hard user
# requirement and is covered in both a classic and integrated rear setup.
web_sources={x['presetId']:x for x in cat.get('webPlayerSources',[])}
check({'clemens-g2-23','clemens-95k-23'} <= set(web_sources),'Gabriel Clemens web presets missing')
source_grounded_players={'clemens-g2-23','clemens-95k-23','aspinall-95k-22','bunting-95k-23','humphries-prestige-22'}
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

# V1.4.1b: the four user-reported integrated designs must keep source artwork only on
# the broadside A-plane front faces. Nothing may obtain readable source art by mirroring
# it onto a reverse face or onto the perpendicular B plane.
critical_fin_presets={
    'prodigy-23',
    'shift',
    'aspinall-95k-22',
    'bunting-95k-23',
}
for pid in critical_fin_presets:
    p=cat['presets'][pid]
    tail=c['rearSystems'][p['rearSystemId']]
    fins=tail.get('finTextures') or {}
    check(set(fins)=={'A-positive','A-negative','B-positive','B-negative'},f'{pid}: missing explicit four-fin face map')
    meta_face=tail.get('finFaceAuthoring') or {}
    check(meta_face.get('mirroringUsed') is False,f'{pid}: source fin authoring must not mirror artwork')
    check(meta_face.get('geometryModel')=='FOUR_RADIAL_FINS_0_90_180_270',f'{pid}: canonical four-fin geometry contract missing')
    check(meta_face.get('geometryInferenceFromPhoto') is False,f'{pid}: product photo must not be treated as recovered flight geometry')
    check(meta_face.get('sourceAppearanceSampleCount')==2,f'{pid}: expected two source appearance samples')
    check(meta_face.get('referencePlane')=='A' and meta_face.get('referenceRollDeg')==0,f'{pid}: source samples must be calibrated to the reference plane only')
    check(meta_face.get('referencePlaneCalibration')=='PLAUSIBLE_BROADSIDE_NOT_EXACT_RECONSTRUCTION',f'{pid}: photo-roll uncertainty not disclosed')
    spine=meta_face.get('spineMaterial') or {}
    check(spine.get('provenance')=='APPROXIMATED_SOURCE_DERIVED_MATERIAL',f'{pid}: integrated flight spine provenance missing')
    check(spine.get('diameterProvenance')=='HEURISTIC',f'{pid}: spine diameter must remain explicitly heuristic')
    check(abs(float(spine.get('diameterMm',0))-1.0)<1e-9,f'{pid}: unexpected spine diameter {spine.get("diameterMm")}')
    check(len(spine.get('colorRgb') or [])==3,f'{pid}: source-derived spine material colour missing')
    check(.72 <= float(spine.get('opacity',0)) <= .96,f'{pid}: spine opacity implausible')
    check(meta_face.get('visibleSourceFinCount')==2,f'{pid}: compatibility source sample count changed')
    check(meta_face.get('hiddenFinCount')==2,f'{pid}: expected two unobserved perpendicular half-fins')
    expected_layout={
        'A-positive':(0,'FRONT'),
        'B-positive':(90,'FRONT'),
        'A-negative':(180,'BACK'),
        'B-negative':(270,'BACK'),
    }
    for key in ('A-positive','A-negative','B-positive','B-negative'):
        face=fins.get(key) or {}
        expected_azimuth,expected_front_side=expected_layout[key]
        check(face.get('azimuthDeg')==expected_azimuth,f'{pid}/{key}: wrong radial fin azimuth {face.get("azimuthDeg")}')
        check(face.get('frontSide')==expected_front_side,f'{pid}/{key}: wrong physical source-face side {face.get("frontSide")}')
        front=face.get('front'); back=face.get('back')
        check(bool(front) and (ROOT/front.replace('./','')).exists(),f'{pid}/{key}: missing front texture')
        check(bool(back) and (ROOT/back.replace('./','')).exists(),f'{pid}/{key}: missing back texture')
        check(face.get('backProvenance')=='APPROXIMATED',f'{pid}/{key}: reverse face must remain APPROXIMATED')
        if key.startswith('A-'):
            check(str(face.get('frontProvenance','')).startswith('SOURCE-GROUNDED'),f'{pid}/{key}: broadside source face must stay source-grounded')
            check(front != back,f'{pid}/{key}: readable source front must not be reused as reverse texture')
        else:
            check(face.get('frontProvenance')=='APPROXIMATED',f'{pid}/{key}: perpendicular unobserved face must remain APPROXIMATED')
    check(fins['A-positive']['front'] != fins['A-negative']['front'],f'{pid}: two visible source half-fins must remain distinct assets')

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
check((mandalorian_author.get('flightApproximation') or {}).get('geometrySource')=='KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION','mandalorian: No.6 family/contour provenance missing')
mando_rear=c['rearSystems'].get('mandalorian-kflex-short',{})
check(mando_rear.get('flightShape')=='No.6',f"mandalorian: mounted flight shape must follow supplied infographic No.6, got {mando_rear.get('flightShape')}")
check(abs(float(mando_rear.get('renderFlightLengthMm',0))-REFERENCE_DIMENSIONS['No.6']['lengthMm'])<1e-9,'mandalorian: No.6 reference length drift')
check(abs(float(mando_rear.get('renderFlightRadiusMm',0))-REFERENCE_DIMENSIONS['No.6']['radiusMm'])<1e-9,'mandalorian: No.6 reference radius drift')
m_frac=float((mandalorian_author.get('flightApproximation') or {}).get('approximatedPixelFraction',0))
check(.15 < m_frac < .35,f'mandalorian: dedicated-source approximation fraction implausible: {m_frac}')

# V1.4 Batch 2A: known flight families must use canonical fin geometry rather
# than a silhouette sampled from a photographed side view. RGB artwork remains
# source-grounded; only the alpha/mesh envelope is normalized to the known shape.
for product,expected_name,expected_profile in (
    ('prodigy','NO2',NO2_PROFILE),
    ('shift','NO6',NO6_PROFILE),
):
    qa=author.get(product,{}).get('flightApproximation') or {}
    check(qa.get('canonicalProfile')==expected_name,f'{product}: canonical profile not recorded')
    check(qa.get('profileMaskApplied') is True,f'{product}: canonical flight alpha mask not applied')
    check(qa.get('geometrySource')=='KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION',f'{product}: flight family/contour provenance wrong')
    preset_id='prodigy-23' if product=='prodigy' else 'shift'
    preset=cat['presets'][preset_id]
    tail=c['rearSystems'][preset['rearSystemId']]
    check(tail.get('planeProfile')==expected_profile,f'{product}: renderer plane profile is not canonical {expected_name}')

g2_qa=author.get('clemens-g2',{}).get('flightApproximation') or {}
check(g2_qa.get('mode')=='FLAT_FLIGHT_SOURCE','clemens-g2: flat flight source regressed')
check(g2_qa.get('profileMaskApplied') is True,'clemens-g2: flat flight is not masked to canonical No.6 geometry')
check(g2_qa.get('geometrySource')=='KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION','clemens-g2: No.6 family/contour provenance wrong')
check(c['flights']['clemens-g2-no6'].get('planeProfile')==NO6_PROFILE,'clemens-g2: renderer plane profile is not canonical No.6')


# V1.4 Batch 2D: source-grounded side views may supply artwork pixels, but the
# canonical fin envelope comes from the verified flight family.
for product,preset_id,expected_name,expected_profile in (
    ('clemens-95k','clemens-95k-23','No.6',NO6_PROFILE),
    ('aspinall-95k','aspinall-95k-22','No.2',NO2_PROFILE),
    ('bunting-95k','bunting-95k-23','No.2',NO2_PROFILE),
    ('humphries-prestige','humphries-prestige-22','Standard',STANDARD_PROFILE),
):
    qa=author.get(product,{}).get('flightApproximation') or {}
    check(qa.get('profileMaskApplied') is True,f'{product}: canonical profile mask not applied')
    check(qa.get('geometrySource')=='KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION',f'{product}: geometry family/contour provenance wrong')
    check(qa.get('canonicalProfile')==expected_name,f'{product}: wrong canonical profile tag {qa.get("canonicalProfile")}')
    preset=cat['presets'][preset_id]
    tail=c['rearSystems'][preset['rearSystemId']] if preset.get('rearSystemId') else c['flights'][preset['flightId']]
    check(tail.get('planeProfile')==expected_profile,f'{product}: renderer plane profile is not canonical {expected_name}')

check(c['rearSystems']['mandalorian-kflex-short'].get('planeProfile')==NO6_PROFILE,'mandalorian: renderer plane profile is not canonical No.6')

# V1.4 Batch 2E legacy reconstructions that have not yet been upgraded to
# source-grounded artwork. Aspinall/Bunting intentionally moved out of this set
# in V1.4.1b because real product pixels are now extracted.
for product,preset_id,component_group,component_id,expected_shape,expected_profile in (
    ('cross-95k','cross-95k-23','rearSystems','cross-95k-kflex-no6-short','No.6',NO6_PROFILE),
    ('mvg-signature','mvg-signature-22','flights','mvg-signature-no2','No.2',NO2_PROFILE),
):
    info=author.get(product,{})
    geometry=info.get('flightGeometry') or {}
    check(geometry.get('canonicalProfile')==expected_shape,f'{product}: wrong verified flight family')
    check(geometry.get('geometrySource')=='WEB_VERIFIED_FLIGHT_TYPE',f'{product}: geometry provenance not web-verified')
    check(geometry.get('artworkSource')=='HEURISTIC_RECONSTRUCTION',f'{product}: artwork must remain explicitly heuristic')
    component=c[component_group][component_id]
    check(component.get('planeProfile')==expected_profile,f'{product}: renderer plane profile drifted from verified {expected_shape}')
    check(component.get('faceEvidence',{}).get('planeA')=='HEURISTIC',f'{product}: reconstructed Plane A must remain HEURISTIC')
    cg=component.get('flightGeometry') or {}
    check(cg.get('geometrySource')=='WEB_VERIFIED_FLIGHT_TYPE',f'{product}: catalog lost geometry provenance')
    check(cg.get('artworkSource')=='HEURISTIC_RECONSTRUCTION',f'{product}: catalog launders reconstructed artwork into source-grounded data')

for product,preset_id,expected_name,expected_profile,expected_source in (
    ('world','world-champion','NO6',NO6_PROFILE,'KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION'),
    ('gary','gary-phase6','STANDARD',STANDARD_PROFILE,'KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION'),
    ('chrono','chrono','VAPOR_S',VAPOR_S_PROFILE,'HEURISTIC_FLIGHT_SHAPE'),
    ('auro','auro','NO6',NO6_PROFILE,'KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION'),
    ('supa','supa-venom','STANDARD',STANDARD_PROFILE,'KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION'),
    ('atat','atat-23','NO6',NO6_PROFILE,'KNOWN_FLIGHT_FAMILY+REFERENCE_CONTOUR_APPROXIMATION'),
):
    qa=author.get(product,{}).get('flightApproximation') or {}
    check(qa.get('canonicalProfile')==expected_name,f'{product}: canonical profile not recorded')
    check(qa.get('profileMaskApplied') is True,f'{product}: canonical flight alpha mask not applied')
    check(qa.get('geometrySource')==expected_source,f'{product}: wrong geometry source {qa.get("geometrySource")}')
    preset=cat['presets'][preset_id]
    tail=c['rearSystems'][preset['rearSystemId']] if preset.get('rearSystemId') else c['flights'][preset['flightId']]
    check(tail.get('planeProfile')==expected_profile,f'{product}: renderer plane profile is not canonical {expected_name}')

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

# Project flight reference dimensions are render references, not universal manufacturer CAD.
for group,items in (('flights',c['flights']),('rearSystems',c['rearSystems'])):
    for cid,obj in items.items():
        shape=obj.get('shape') if group=='flights' else obj.get('flightShape')
        if shape in REFERENCE_DIMENSIONS and cid != 'generic-slim-geometry':
            ref=REFERENCE_DIMENSIONS[shape]
            length_key='renderLengthMm' if group=='flights' else 'renderFlightLengthMm'
            radius_key='renderRadiusMm' if group=='flights' else 'renderFlightRadiusMm'
            check(abs(float(obj.get(length_key,0))-float(ref['lengthMm']))<1e-9,f'{group}/{cid}: reference flight length drift')
            check(abs(float(obj.get(radius_key,0))-float(ref['radiusMm']))<1e-9,f'{group}/{cid}: reference flight radius drift')
            check(obj.get('renderGeometrySource')=='PROJECT_REFERENCE_DIMENSIONS_NOT_MANUFACTURER_CAD',f'{group}/{cid}: render dimension provenance missing')

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
