from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'data/catalog.json').read_text())
AUTHOR=json.loads((ROOT/'data/authoring-metadata.json').read_text())
OUT=ROOT/'outputs'
for _dir in ('comparisons','gallery','qa'):
    (OUT/_dir).mkdir(parents=True,exist_ok=True)

def img(path): return Image.open(ROOT/path.replace('./','')).convert('RGBA')

def fit(im,size,bg=(245,245,245,255)):
    w,h=size; c=Image.new('RGBA',size,bg); x=im.copy(); x.thumbnail((w-20,h-20),Image.Resampling.LANCZOS); c.alpha_composite(x,((w-x.width)//2,(h-x.height)//2)); return c

def comp_path(obj,key='texture'):
    return obj.get(key)

def assembly_for(p):
    c=CAT['components'];return {'point':c['points'][p['pointId']],'barrel':c['barrels'][p['barrelId']],'rearSystem':c['rearSystems'].get(p.get('rearSystemId')) if p.get('rearSystemId') else None,'shaft':c['shafts'].get(p.get('shaftId')) if p.get('shaftId') else None,'flight':c['flights'].get(p.get('flightId')) if p.get('flightId') else None}

def cropfit(texture_path,length_px,height_px):
    im=img(texture_path); bbox=im.getbbox(); im=im.crop(bbox) if bbox else im
    # Preserve source component image within exact physical component box; this is 2D QA, not runtime renderer.
    return im.resize((max(1,int(length_px)),max(1,int(height_px))),Image.Resampling.LANCZOS)

def render_assembly(a,scale=4.2):
    W,H=789,331; tip=(0,212); out=Image.new('RGBA',(W,H),(0,0,0,0)); x=0
    p=a['point']; b=a['barrel']; tail=a['rearSystem'] or a['flight']
    entries=[
        ('point',p['renderLengthMm'],p['renderDiameterMm'],p['texture']),
        ('barrel',b['renderLengthMm'],b['renderDiameterMm'],b['texture']),
    ]
    if a['rearSystem']:
        r=a['rearSystem']
        entries.append(('rear-shaft-core' if r.get('rootTexture') else 'rear-shaft',r['renderShaftLengthMm'],r['renderShaftDiameterMm'],r['shaftTexture']))
        if r.get('rootTexture') and r.get('renderRootLengthMm'):
            entries.append(('rear-root',r['renderRootLengthMm'],max(r.get('renderRootFrontDiameterMm',r['renderShaftDiameterMm']),r.get('renderRootRearDiameterMm',r['renderShaftDiameterMm'])),r['rootTexture']))
    else:
        shaft=a['shaft'];entries.append(('shaft',shaft['renderLengthMm'],shaft.get('renderDiameterMm',4.8),shaft['texture']))
    component_bounds={}
    for name,L,D,t in entries:
        start=x; lp=L*scale; hp=max(4,D*scale); ci=cropfit(t,lp,hp)
        y=int(tip[1]-ci.height/2); out.alpha_composite(ci,(int(x),y)); x+=lp
        component_bounds[name]=[start,x]
    fl=tail.get('renderFlightLengthMm',tail.get('renderLengthMm',42))*scale
    fr=tail.get('renderFlightRadiusMm',tail.get('renderRadiusMm',18))*scale
    overlap=tail.get('flightRootOverlapMm',1.5)*scale
    flight_root=max(0,x-overlap)
    fi=img(tail['planeATexture']);bbox=fi.getbbox();fi=fi.crop(bbox) if bbox else fi
    fi=fi.resize((max(1,int(fl)),max(1,int(fr*2))),Image.Resampling.LANCZOS)
    out.alpha_composite(fi,(int(flight_root),int(tip[1]-fi.height/2)))
    return out, {
        'tip':[0,212],
        'componentEndX':x,
        'flightRootX':flight_root,
        'flightEndX':flight_root+fl,
        'componentBounds':component_bounds,
        'gapPx':0.0,
    }

def composite_compare(preset_id,p):
    src=fit(img(p['sourceImage']),(520,420)); build,meta=render_assembly(assembly_for(p)); buildpanel=fit(build,(820,420),(25,29,37,255))
    source_label=p.get('sourceLabel') or ('web-referenced reconstruction' if p.get('sourceType')=='WEB-REFERENCED-RECONSTRUCTION' else 'supplied source')
    canvas=Image.new('RGBA',(1340,490),(13,16,22,255));canvas.alpha_composite(src,(0,50));canvas.alpha_composite(buildpanel,(520,50));d=ImageDraw.Draw(canvas);d.text((18,16),f'{p["name"]} — {source_label}',fill='white');d.text((540,16),'Builder orthogonal assembly (static QA)',fill='white');d.text((540,455),f'Tip=(0,212), calculated gaps={meta["gapPx"]:.1f}px',fill=(180,195,215));canvas.convert('RGB').save(OUT/'comparisons'/f'{preset_id}.jpg',quality=92)
    return meta

def high_frequency_energy(im):
    arr=np.asarray(im.convert('L'),dtype=np.float32)
    if arr.shape[0]<2 or arr.shape[1]<2:return 0.0
    return float(np.abs(np.diff(arr,axis=0)).mean()+np.abs(np.diff(arr,axis=1)).mean())

def center_ridge_score(im):
    rgba=np.asarray(im.convert('RGBA'))
    gray=np.asarray(im.convert('L'),dtype=np.float32)
    alpha=rgba[:,:,3]
    h,w=alpha.shape
    if h<16 or w<16:return 0.0
    cy=h//2
    delta=max(4,int(round(h*.075)))
    y0=max(0,cy-delta); y1=min(h-1,cy+delta)
    valid=(alpha[cy]>30)&(alpha[y0]>30)&(alpha[y1]>30)
    # Ignore the outer 8% where the silhouette itself dominates the metric.
    x0=int(round(w*.08)); x1=max(x0+1,int(round(w*.92)))
    valid[:x0]=False; valid[x1:]=False
    if not valid.any():return 0.0
    expected=(gray[y0]+gray[y1])*.5
    residual=np.abs(gray[cy]-expected)[valid]
    return float(np.mean(residual))

def flight_texture_audit(pid,p):
    a=assembly_for(p); tail=a['rearSystem'] or a['flight']
    source_path=p['sourceImage']
    if pid=='mandalorian-24':
        qa_file=(AUTHOR.get('mandalorian') or {}).get('flightQaSourceFile')
        candidate=ROOT/'assets/source'/qa_file if qa_file else None
        if candidate and candidate.exists(): source_path='./assets/source/'+qa_file
    source=fit(img(source_path),(520,360),(245,245,245,255))
    plane_a_raw=img(tail['planeATexture']); plane_b_raw=img(tail['planeBTexture'])
    plane_a=fit(plane_a_raw,(420,360),(25,29,37,255))
    plane_b=fit(plane_b_raw,(420,360),(25,29,37,255))
    build,_=render_assembly(a); build=fit(build,(820,360),(25,29,37,255))
    canvas=Image.new('RGBA',(2180,430),(13,16,22,255)); d=ImageDraw.Draw(canvas)
    d.text((14,12),f'{p["name"]} · original/source',fill='white')
    d.text((540,12),f'Plane A · {tail.get("planeAProvenance",tail.get("faceEvidence",{}).get("planeA"))}',fill='white')
    d.text((960,12),f'Plane B · {tail.get("planeBProvenance",tail.get("faceEvidence",{}).get("planeB"))}',fill='white')
    d.text((1380,12),f'Orthogonal assembly · {tail.get("flightExtractionMode","DIRECT_SOURCE_FACE")}',fill='white')
    canvas.alpha_composite(source,(0,50)); canvas.alpha_composite(plane_a,(520,50)); canvas.alpha_composite(plane_b,(940,50)); canvas.alpha_composite(build,(1360,50))
    ea=high_frequency_energy(plane_a_raw); eb=high_frequency_energy(plane_b_raw)
    ratio=(eb/ea) if ea>1e-6 else 0.0
    ridge=center_ridge_score(plane_a_raw)
    d.text((540,405),f'high-frequency A={ea:.2f} · B={eb:.2f} · ratio={ratio:.2f} · center-ridge={ridge:.2f}',fill=(180,195,215))
    canvas.convert('RGB').save(OUT/'qa'/f'flight-textures-{pid}.png')
    return {
      'name':p['name'],
      'planeAProvenance':tail.get('planeAProvenance',tail.get('faceEvidence',{}).get('planeA')),
      'planeBProvenance':tail.get('planeBProvenance',tail.get('faceEvidence',{}).get('planeB')),
      'flightExtractionMode':tail.get('flightExtractionMode','DIRECT_SOURCE_FACE'),
      'planeAHighFrequency':ea,
      'planeBHighFrequency':eb,
      'backfaceDetailRatio':ratio,
      'centerRidgeScore':ridge,
      'qaSource':source_path,
    }


def tail_texture_audit(pid,p):
    a=assembly_for(p)
    tail=a['rearSystem'] or a['flight']
    shaft_obj=a['rearSystem'] or a['shaft']
    texture_path=shaft_obj.get('shaftTexture') or shaft_obj.get('texture')
    product=Path(texture_path).parent.name
    author=AUTHOR.get(product,{})
    tail_qa=author.get('tailAuthoring')
    if not tail_qa:
        return None

    source=fit(img(p['sourceImage']),(420,300),(245,245,245,255))
    shaft=fit(img(texture_path),(360,300),(25,29,37,255))
    root_path=tail.get('rootTexture')
    if root_path:
        root=fit(img(root_path),(300,300),(25,29,37,255))
    else:
        root=Image.new('RGBA',(300,300),(25,29,37,255))
        ImageDraw.Draw(root).text((90,140),'no explicit root',fill=(180,195,215))
    plane_a=fit(img(tail['planeATexture']),(360,300),(25,29,37,255))
    plane_b=fit(img(tail['planeBTexture']),(360,300),(25,29,37,255))
    build,_=render_assembly(a)
    build=fit(build,(720,300),(25,29,37,255))

    widths=[420,360,300,360,360,720]
    labels=[
        'original/source',
        'shaft-core' if root_path else 'shaft',
        'rear-root',
        'Plane A',
        'Plane B',
        'assembly',
    ]
    panels=[source,shaft,root,plane_a,plane_b,build]
    canvas=Image.new('RGBA',(sum(widths),370),(13,16,22,255));d=ImageDraw.Draw(canvas)
    x=0
    for width,label,panel in zip(widths,labels,panels):
        d.text((x+10,12),label,fill='white')
        canvas.alpha_composite(panel,(x,48))
        x+=width
    metrics=(
        f"status={tail_qa.get('status')}  confidence={tail_qa.get('overallConfidence')}  "
        f"axisP95={tail_qa.get('shaftAxisResidualP95Px')}px  "
        f"jump={tail_qa.get('shaftCenterJumpMaxPx')}px  widthCV={tail_qa.get('shaftWidthCV')}  "
        f"rootOffset={tail_qa.get('rootAxisOffsetPx')}px  haze={tail_qa.get('tailAlphaHaze')}"
    )
    d.text((12,345),metrics,fill=(180,195,215))
    canvas.convert('RGB').save(OUT/'qa'/f'tail-authoring-{pid}.png',quality=94)
    return {
        'product':product,
        'status':tail_qa.get('status'),
        'overallConfidence':tail_qa.get('overallConfidence'),
        'shaftAxisResidualP95Px':tail_qa.get('shaftAxisResidualP95Px'),
        'shaftCenterJumpMaxPx':tail_qa.get('shaftCenterJumpMaxPx'),
        'shaftWidthCV':tail_qa.get('shaftWidthCV'),
        'rootAxisOffsetPx':tail_qa.get('rootAxisOffsetPx'),
        'rootWidthProgression':tail_qa.get('rootWidthProgression'),
        'tailAlphaHaze':tail_qa.get('tailAlphaHaze'),
        'rootLeakIntoShaftRatio':tail_qa.get('rootLeakIntoShaftRatio'),
        'rearRootAuthored':bool(author.get('rearRootAuthored')),
        'panel':f'outputs/qa/tail-authoring-{pid}.png',
    }

qa={'presets':{},'freeCombinations':[],'flightTextureQA':{},'tailQA':{}}
for pid,p in CAT['presets'].items():
    qa['presets'][pid]=composite_compare(pid,p)

REVIEW_PRESETS=tuple(pid for pid,p in CAT['presets'].items() if p.get('sourceType')!='WEB-REFERENCED-RECONSTRUCTION')
for pid in REVIEW_PRESETS:
    qa['flightTextureQA'][pid]=flight_texture_audit(pid,CAT['presets'][pid])

for pid,p in CAT['presets'].items():
    audit=tail_texture_audit(pid,p)
    if audit is not None:
        qa['tailQA'][pid]=audit

def comparison_contact_sheet(preset_ids, output_name, cols=2):
    cards=[]
    for pid in preset_ids:
        path=OUT/'comparisons'/f'{pid}.jpg'
        if not path.exists(): continue
        card=Image.open(path).convert('RGB')
        card.thumbnail((920,336),Image.Resampling.LANCZOS)
        cards.append((pid,card))
    if not cards: return
    cellw,cellh=940,385; rows=math.ceil(len(cards)/cols)
    sheet=Image.new('RGB',(cellw*cols,cellh*rows),(13,16,22)); d=ImageDraw.Draw(sheet)
    for i,(pid,card) in enumerate(cards):
        x=(i%cols)*cellw; y=(i//cols)*cellh
        d.text((x+10,y+8),pid,fill='white')
        sheet.paste(card,(x+10,y+36))
    sheet.save(OUT/'gallery'/output_name,quality=90)

comparison_contact_sheet(list(CAT['presets']), 'preset-comparisons-all.jpg')
comparison_contact_sheet([x['presetId'] for x in CAT.get('webPlayerSources',[])], 'player-darts-v1.2.jpg')

# Explicit builder QA: original plus one isolated swap per requested component class.
c=CAT['components']
def preset_assembly(pid):
    return assembly_for(CAT['presets'][pid])

def mk(point,barrel,shaft=None,flight=None,rear=None):
    return {
        'point': c['points'][point],
        'barrel': c['barrels'][barrel],
        'shaft': c['shafts'].get(shaft) if shaft else None,
        'flight': c['flights'].get(flight) if flight else None,
        'rearSystem': c['rearSystems'].get(rear) if rear else None,
    }

cases=[
 ('01-original-prodigy', preset_assembly('prodigy-23'), 'Original preset'),
 ('02-point-swap', mk('target-swiss-slk-gold-35','prodigy-23-barrel',rear='prodigy-kflex-no2-short'), 'Only point swapped'),
 ('03-barrel-swap', mk('target-swiss-dx-gold-26','shift-barrel',rear='prodigy-kflex-no2-short'), 'Only barrel swapped'),
 ('04-shaft-swap', mk('shot-auro-point-35','auro-90-barrel','gary-gripper4','auro-no6'), 'Only classic shaft swapped'),
 ('05-flight-swap', mk('shot-auro-point-35','auro-90-barrel','auro-koi-carbon','supa-standard'), 'Only classic flight swapped'),
 ('06-rear-system-swap', mk('target-swiss-dx-gold-26','prodigy-23-barrel',rear='world-kflex-no6-short'), 'Only integrated rear system swapped'),
]
# Keep a few cross-family stress combinations as additional coverage.
stress=[
 ('07-stress-shift-mando-rear', mk('target-swiss-grd-black-30','shift-barrel',rear='mandalorian-kflex-short'), 'Integrated rear cross-preset stress test'),
 ('08-stress-supa-gary-tail', mk('supa-steel-point','supa-barrel','gary-gripper4','gary-phase6-flight'), 'Classic modular cross-preset stress test'),
 ('09-stress-auro-supa-tail', mk('shot-auro-point-35','auro-90-barrel','supa-nitrotech-short','supa-standard'), 'Classic modular cross-preset stress test'),
]
all_cases=cases+stress
sheet=[]
for name,a,purpose in all_cases:
    im,meta=render_assembly(a); im.save(OUT/'gallery'/f'{name}.png')
    qa['freeCombinations'].append({'name':name,'purpose':purpose,**meta})
    sheet.append((name,purpose,im))
# Contact sheet: requested six tests plus additional stress tests.
cellw,cellh=820,390; cols=2; rows=math.ceil(len(sheet)/cols)
cs=Image.new('RGBA',(cellw*cols,cellh*rows),(18,22,29,255));d=ImageDraw.Draw(cs)
for idx,(name,purpose,im) in enumerate(sheet):
    x=(idx%cols)*cellw;y=(idx//cols)*cellh
    panel=fit(im,(cellw-20,315),(25,29,37,255));cs.alpha_composite(panel,(x+10,y+60))
    d.text((x+12,y+10),name,fill='white');d.text((x+12,y+31),purpose,fill=(180,195,215))
cs.convert('RGB').save(OUT/'gallery'/'free-combinations.jpg',quality=92)
(OUT/'qa'/'static-qa.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
print(json.dumps(qa,indent=2))
