from __future__ import annotations
from pathlib import Path
import json, math
import cv2, numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'data/catalog.json').read_text())
W,H=789,331; TIP=np.array([0.0,212.0]); SCALE=3.35; CAM=800.0
for _dir in ('comparisons','gallery','qa'):
    (ROOT/'outputs'/_dir).mkdir(parents=True,exist_ok=True)

def load_rgba(path): return np.array(Image.open(ROOT/path.replace('./','')).convert('RGBA'))
def assembly(p):
 c=CAT['components'];rid=p.get('rearSystemId');return {'point':c['points'][p['pointId']],'barrel':c['barrels'][p['barrelId']],'rearSystem':c['rearSystems'].get(rid) if rid else None,'shaft':c['shafts'].get(p.get('shaftId')) if p.get('shaftId') else None,'flight':c['flights'].get(p.get('flightId')) if p.get('flightId') else None}

def basis(inc_deg):
    i=math.radians(inc_deg); axis=np.array([math.cos(i),0.0,math.sin(i)])
    ey=np.array([0.0,1.0,0.0])
    ez=np.cross(axis,ey); ez=ez/np.linalg.norm(ez)
    return axis,ey,ez

def project(pt):
    x,y,z=pt; den=max(80,CAM-z); k=CAM/den
    return np.array([TIP[0]+x*SCALE*k,TIP[1]-y*SCALE*k])

def local(axis,ey,ez,x,y=0,z=0): return axis*x+ey*y+ez*z

def warp_quad(canvas, tex, src_quad, dst_quad):
    src=np.float32(src_quad); dst=np.float32(dst_quad); M=cv2.getPerspectiveTransform(src,dst)
    warped=cv2.warpPerspective(tex,M,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
    a=warped[:,:,3:4].astype(np.float32)/255.0
    canvas[:,:,:3]=(warped[:,:,:3]*a+canvas[:,:,:3]*(1-a)).astype(np.uint8)
    canvas[:,:,3]=np.maximum(canvas[:,:,3],warped[:,:,3])

def render(a,inc=35,roll=0):
    canvas=np.zeros((H,W,4),dtype=np.uint8);axis,ey,ez=basis(inc);x=0.0
    bodies=[]
    for o,L,D,T in [(a['point'],a['point']['renderLengthMm'],a['point']['renderDiameterMm'],a['point']['texture']), (a['barrel'],a['barrel']['renderLengthMm'],a['barrel']['renderDiameterMm'],a['barrel']['texture'])]: bodies.append((x,x+L,D,T));x+=L
    if a['rearSystem']:
        r=a['rearSystem'];L=r['renderShaftLengthMm'];D=r['renderShaftDiameterMm'];T=r['shaftTexture']
    else:
        s=a['shaft'];L=s['renderLengthMm'];D=s.get('renderDiameterMm',4.8);T=s['texture']
    bodies.append((x,x+L,D,T));x+=L
    for x0,x1,d,tpath in bodies:
        tex=load_rgba(tpath);h,w=tex.shape[:2]
        src=[[0,h-1],[w-1,h-1],[w-1,0],[0,0]]
        dst=[project(local(axis,ey,ez,x0,-d/2)),project(local(axis,ey,ez,x1,-d/2)),project(local(axis,ey,ez,x1,d/2)),project(local(axis,ey,ez,x0,d/2))]
        warp_quad(canvas,tex,src,dst)
    tail=a['rearSystem'] or a['flight']; fl=float(tail.get('renderFlightLengthMm',tail.get('renderLengthMm',42))); rad=float(tail.get('renderFlightRadiusMm',tail.get('renderRadiusMm',18)));root=x-1.5
    phi=math.radians(roll)
    planes=[]
    for idx,extra in enumerate([0,math.pi/2]):
        ang=phi+extra; fin=ey*math.cos(ang)+ez*math.sin(ang)
        # average depth used for painter sorting. Camera is +Z, farther = smaller z.
        avgz=(local(axis,ey,ez,root+fl/2,0,0)+fin*0)[2]
        planes.append((avgz,idx,fin))
    planes.sort(key=lambda q:q[0])
    for _,idx,fin in planes:
        tex=load_rgba(tail['planeATexture'] if idx==0 else tail.get('planeBTexture',tail['planeATexture']));h,w=tex.shape[:2]
        src=[[0,h-1],[w-1,h-1],[w-1,0],[0,0]]
        dst=[project(local(axis,ey,ez,root)-fin*rad), project(local(axis,ey,ez,root+fl)-fin*rad), project(local(axis,ey,ez,root+fl)+fin*rad), project(local(axis,ey,ez,root)+fin*rad)]
        warp_quad(canvas,tex,src,dst)
    # hard invariant marker, only debug metadata: projected local origin is exactly TIP by formula.
    drift=float(np.linalg.norm(project(np.zeros(3))-TIP))
    return Image.fromarray(canvas,'RGBA'),{'tipDriftPx':drift,'incidenceDeg':inc,'rollDeg':roll,'planeModel':'TWO_FULL_INTERSECTING_PLANES_SHARED_AXIS_90_DEG'}

def panel(im,title,size=(789,365)):
    c=Image.new('RGBA',size,(18,22,29,255));thumb=im.copy();thumb.thumbnail((size[0],331),Image.Resampling.LANCZOS);c.alpha_composite(thumb,(0,30));ImageDraw.Draw(c).text((10,8),title,fill='white');return c

poses=[(20,-15),(35,0),(35,18),(50,-12)]
rows=[];qa={}
for pid,p in CAT['presets'].items():
    a=assembly(p); tiles=[];qa[pid]=[]
    for inc,roll in poses:
        im,m=render(a,inc,roll);tiles.append(panel(im,f'{p["name"]} · i={inc}° r={roll:+}°'));qa[pid].append(m)
    row=Image.new('RGBA',(789*4,365),(12,15,20,255))
    for j,t in enumerate(tiles):row.alpha_composite(t,(j*789,0))
    row.convert('RGB').save(ROOT/'outputs/gallery'/f'pose-{pid}.jpg',quality=90);rows.append((pid,row))
# master contact sheet scaled for review
cw,ch=789*2,365*math.ceil(len(rows)/2);master=Image.new('RGBA',(cw,ch),(10,13,18,255))
for k,(pid,row) in enumerate(rows):
    thumb=row.copy();thumb.thumbnail((789,350),Image.Resampling.LANCZOS);master.alpha_composite(thumb,((k%2)*789,(k//2)*365))
master.convert('RGB').save(ROOT/'outputs/gallery'/'pose-gallery-all-presets.jpg',quality=90)
# V1.3.1 visual review triptychs: the four user-reported designs plus Clemens 95K
# as an integrated source-grounded regression check.
REVIEW_PRESETS=('clemens-g2-23','prodigy-23','shift','world-champion','clemens-95k-23')
for pid in REVIEW_PRESETS:
    preset=CAT['presets'][pid]; a=assembly(preset)
    source=Image.open(ROOT/preset['sourceImage'].replace('./','')).convert('RGBA')
    orthogonal,_=render(a,0,0)
    pose=preset.get('defaultPose',{})
    posed,_=render(a,float(pose.get('incidenceDeg',35)),float(pose.get('rollDeg',0)))
    cards=[
        panel(source,f'Original/source reference · {preset["name"]}'),
        panel(orthogonal,'Orthogonal builder projection'),
        panel(posed,f'Posed projection · incidence={pose.get("incidenceDeg",35)}° · roll={pose.get("rollDeg",0)}°'),
    ]
    sheet=Image.new('RGBA',(789*3,365),(10,13,18,255))
    for i,card in enumerate(cards): sheet.alpha_composite(card,(i*789,0))
    sheet.convert('RGB').save(ROOT/'outputs/comparisons'/f'{pid}-v1.3.1-triptych.jpg',quality=92)

(ROOT/'outputs/qa'/'software-pose-qa.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
print('rendered',len(rows),'preset pose galleries; max drift',max(m['tipDriftPx'] for arr in qa.values() for m in arr))
