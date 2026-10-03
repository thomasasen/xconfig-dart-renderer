from __future__ import annotations
import json, shutil, math
from io import BytesIO
from urllib.request import Request, urlopen
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import cv2

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'assets/source'
OUT=ROOT/'assets/components'
OUT.mkdir(parents=True, exist_ok=True)

# Authoring coordinates are deliberately image-space only. Physical geometry lives in catalog.json.
# splits = fractions of the extracted horizontal dart length: point | barrel | shaft/rear | flight.
SPECS={
 'prodigy': dict(file='target-luke-littler-g1-prodigy-95-swiss-23-gram_3.webp', rotate=True, bg='white', splits=[0.1625,0.56875,0.6875], rear=True, canonicalFlight=True),
 'shift': dict(file='target-shift-sp-steeltip-90_3.webp', rotate=False, bg='white', splits=[0.1857,0.5214,0.6929], rear=True, canonicalFlight=True),
 'gary': dict(file='unicorn-w-c-gary-anderson-phase-6-90_1.webp', rotate=True, bg='white', splits=[0.1857,0.5214,0.7214], rear=False, canonicalFlight=True),
 'chrono': dict(file='target-phil-taylor-power-chrono-sp-steeltip-95_3.webp', rotate=True, bg='white', splits=[0.2286,0.5714,0.7786], rear=False, canonicalFlight=True),
 'world': dict(file='target-luke-littler-world-champion-90-swiss-23-gram_3.webp', rotate=True, bg='white', splits=[0.20625,0.55,0.7375], rear=True, canonicalFlight=True),
 'auro': dict(file='shot-alchemy-auro-90_3.webp', rotate=True, bg='white', splits=[0.20,0.53125,0.73125], rear=False, canonicalFlight=True),
 'supa': dict(file='PW2022_SupaVenom_Steel_LEFT.webp', rotate=False, bg='alpha', splits=[0.15,0.525,0.7625], rear=False, canonicalFlight=True),
 'mandalorian': dict(
   file='190840STARWARSMANDALORIAN95_STEElTIP_GALLERY_DE_PT01.webp',
   rotate=False, bg='dark-roi', roi=(38,175,765,350),
   splits=[0.19,0.565,0.725], rear=True, canonicalFlight=False,
   flightWebMode='KFLEX_FRONTAL_LEFT',
   flightProductPage='https://a-zdarts.com/products/target-star-wars-mandalorian-k-flex-flight-system-no6-short',
   flightWebSources=[
      'https://a-zdarts.com/cdn/shop/files/15-410623_01.jpg?v=1776815492&width=960',
      'https://a-zdarts.com/cdn/shop/files/15-410624_01.jpg?v=1776815674&width=960',
   ],
),
 'atat': dict(file='190843-STARWARSAT-AT90_STEELTIP_GALLERY_DE_PT01.webp', rotate=False, bg='dark-roi', roi=(35,180,765,350), splits=[0.19,0.54,0.73], rear=False, canonicalFlight=True),
 'edge': dict(file='PT02_ffd9f2ed-6a52-43e8-9f62-027742ec8be4.webp', rotate=False, bg='dark-roi', roi=(34,175,766,352), splits=[0.19,0.56,0.73], rear=True, canonicalFlight=True),
 'vader': dict(file='PT01_a83f80b3-c589-4f2e-85c1-7cf911048504.webp', rotate=False, bg='dark-roi', roi=(35,175,765,352), splits=[0.19,0.56,0.73], rear=True, canonicalFlight=True),
}

def alpha_white(img: Image.Image)->Image.Image:
    arr=np.array(img.convert('RGBA')).astype(np.uint8)
    rgb=arr[:,:,:3].astype(np.int16)
    # White/near-white to transparent, with antialias preserving edge pixels.
    m=rgb.min(axis=2)
    alpha=np.clip((252-m)*16,0,255).astype(np.uint8)
    # Keep originally non-white saturated/dark pixels opaque.
    chroma=rgb.max(axis=2)-rgb.min(axis=2)
    keep=(m<238)|(chroma>8)
    alpha=np.where(keep,np.maximum(alpha,220),alpha).astype(np.uint8)
    arr[:,:,3]=alpha
    return Image.fromarray(arr,'RGBA')

def alpha_dark_roi(img: Image.Image, roi)->Image.Image:
    # Tight infographic extraction. We deliberately reject panel rules/text and keep only
    # pixels that differ materially from a per-column background estimate inside a dart-shaped corridor.
    x0,y0,x1,y1=roi
    crop=np.array(img.convert('RGB').crop((x0,y0,x1,y1))).astype(np.int16)
    h,w,_=crop.shape
    top=np.median(crop[:max(5,h//10)],axis=0)
    bot=np.median(crop[-max(5,h//10):],axis=0)
    col=(top+bot)/2.0
    bg=np.broadcast_to(col[None,:,:],crop.shape)
    dist=np.linalg.norm(crop-bg,axis=2)
    # Locate the horizontal dart axis from strong foreground pixels.
    score=(dist>28).sum(axis=1)
    center=int(np.argmax(score))
    yy=np.arange(h)[:,None]; xx=np.arange(w)[None,:]; xn=xx/max(1,w-1)
    # Body corridor is intentionally tight; flight region opens up near the last quarter.
    half=np.where(xn<0.70, np.where(xn<0.20,h*0.055,h*0.13), h*0.49)
    corridor=np.abs(yy-center)<=half
    alpha=np.clip((dist-16)*20,0,255)
    alpha=np.where((dist>24)&corridor,np.maximum(alpha,225),0)
    # Remove isolated specks while preserving the thin point via horizontal closing only.
    aimg=Image.fromarray(alpha.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.45))
    rgba=np.dstack([crop,np.asarray(aimg)])
    out=Image.fromarray(rgba.astype(np.uint8),'RGBA')
    return trim_alpha(out, threshold=28)

def trim_alpha(img:Image.Image, threshold=4)->Image.Image:
    a=np.array(img.getchannel('A'))
    ys,xs=np.where(a>threshold)
    if len(xs)==0: return img
    box=(max(0,xs.min()),max(0,ys.min()),min(img.width,xs.max()+1),min(img.height,ys.max()+1))
    return img.crop(box)

def normalize_source(spec):
    im=Image.open(SRC/spec['file']).convert('RGBA')
    if spec.get('rotate'):
        im=im.transpose(Image.Transpose.ROTATE_270)
    if spec['bg']=='white':
        im=alpha_white(im)
        im=trim_alpha(im,5)
    elif spec['bg']=='alpha':
        # preserve source alpha; black RGB behind transparency is okay
        im=trim_alpha(im,5)
    elif spec['bg']=='dark-roi':
        im=alpha_dark_roi(im,spec['roi'])
    return im

def flight_profile(img:Image.Image, samples=14):
    a=np.array(img.getchannel('A'))
    h,w=a.shape
    if not a.max():
        return [[0,0],[1,-1],[1,1]]
    # remove thin shaft/root bleed by requiring local width > 10% max width
    cols=[]
    for i in range(samples):
        x=min(w-1,round(i*(w-1)/(samples-1)))
        ys=np.where(a[:,x]>30)[0]
        if len(ys):
            cols.append((x,ys.min(),ys.max()))
        else: cols.append((x,h//2,h//2))
    center=h/2
    rad=max(1,max(max(abs(y0-center),abs(y1-center)) for _,y0,y1 in cols))
    upper=[]; lower=[]
    for x,y0,y1 in cols:
        xn=x/max(1,w-1)
        upper.append([round(xn,4),round((center-y0)/rad,4)])
        lower.append([round(xn,4),round((center-y1)/rad,4)])
    # Shape expects mathematical Y; use top positive. Ensure root nearly zero if neck is narrow.
    poly=[[x,y] for x,y in upper] + [[x,y] for x,y in reversed(lower)]
    return poly

def mask_flight_polygon(img: Image.Image)->Image.Image:
    rgba=img.convert('RGBA')
    w,h=rgba.size
    # Conservative small-standard / No.6-like envelope for infographic sources.
    pts=[(0,.50),(.10,.36),(.22,.09),(.72,.05),(.93,.20),(1,.50),(.93,.80),(.72,.95),(.22,.91),(.10,.64)]
    mask=Image.new('L',(w,h),0); d=ImageDraw.Draw(mask)
    d.polygon([(int(x*w),int(y*h)) for x,y in pts],fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(.7))
    arr=np.array(rgba); arr[:,:,3]=np.minimum(arr[:,:,3],np.array(mask)).astype(np.uint8)
    return trim_alpha(Image.fromarray(arr,'RGBA'),3)

def clean_large_component(img: Image.Image)->Image.Image:
    arr=np.array(img.convert('RGBA'))
    alpha=arr[:,:,3]
    binary=(alpha>35).astype(np.uint8)*255
    # Remove thin infographic separator rules without eroding the flight body.
    opened=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    n,labels,stats,_=cv2.connectedComponentsWithStats(opened,8)
    if n<=1:
        return img
    largest=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    keep=(labels==largest).astype(np.uint8)*255
    keep=cv2.dilate(keep,np.ones((3,3),np.uint8),iterations=1)
    arr[:,:,3]=np.minimum(alpha,keep).astype(np.uint8)
    return trim_alpha(Image.fromarray(arr,'RGBA'),3)

def save_component(img, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    trim_alpha(img,3).save(path)

def download_reference_image(urls):
    errors=[]
    for url in urls or []:
        try:
            req=Request(url,headers={
                'User-Agent':'Mozilla/5.0 xConfig-Dart-Renderer/1.3.2',
                'Accept':'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            })
            with urlopen(req,timeout=30) as response:
                raw=response.read()
            im=Image.open(BytesIO(raw)).convert('RGBA')
            if im.width < 300 or im.height < 300:
                raise RuntimeError(f'image too small: {im.size}')
            return im,url
        except Exception as exc:
            errors.append(f'{url}: {exc}')
    raise RuntimeError('No dedicated flight reference could be downloaded. ' + ' | '.join(errors))

def largest_alpha_component(img:Image.Image, threshold=24):
    rgba=np.array(img.convert('RGBA')).copy()
    binary=(rgba[:,:,3]>threshold).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(binary,8)
    if n<=1:return trim_alpha(img,threshold)
    idx=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    keep=(labels==idx).astype(np.uint8)*255
    keep=cv2.dilate(keep,np.ones((3,3),np.uint8),iterations=1)
    rgba[:,:,3]=np.minimum(rgba[:,:,3],keep).astype(np.uint8)
    return trim_alpha(Image.fromarray(rgba,'RGBA'),threshold)

def collapse_cross_fin_band(img:Image.Image, half_band_ratio=.022):
    """Remove the edge-on perpendicular fin from an otherwise frontal K-Flex face.

    The two source-grounded halves above/below the ridge are joined geometrically.
    No opposite-face artwork is mirrored or copied. The removed strip is the only
    approximated region.
    """
    base=trim_alpha(img.convert('RGBA'),3)
    arr=np.array(base).copy(); alpha=arr[:,:,3]
    h,w=alpha.shape
    center=h//2
    band=max(1,int(round(h*half_band_ratio)))
    y0=max(0,center-band); y1=min(h,center+band+1)
    removed=int((alpha[y0:y1,:]>3).sum())
    before=max(1,int((alpha>3).sum()))
    collapsed=np.concatenate([arr[:y0,:,:],arr[y1:,:,:]],axis=0)
    if collapsed.shape[0]<8:
        raise RuntimeError('cross-fin collapse removed too much of the texture')
    restored=Image.fromarray(collapsed,'RGBA').resize((w,h),Image.Resampling.LANCZOS)
    return trim_alpha(restored,3),{
        'deocclusionMethod':'FRONTAL_RIDGE_STRIP_COLLAPSE',
        'centreBandHalfWidthPx':band,
        'approximatedPixelFraction':round(removed/before,4),
    }

def prepare_dedicated_flight_face(spec):
    if spec.get('flightWebMode')!='KFLEX_FRONTAL_LEFT':
        return None,None
    raw,url=download_reference_image(spec.get('flightWebSources'))
    # The selected catalogue image is a clean front view with the black K-Flex on
    # the left and a clear/red K-Flex on the right. Work only with the black half.
    left=raw.crop((0,0,max(1,raw.width//2),raw.height))
    isolated=largest_alpha_component(alpha_white(left),20)
    # Catalogue orientation: shaft points down. Rotate clockwise so the flight root
    # points left, matching the xConfig canonical component convention.
    horizontal=trim_alpha(isolated.transpose(Image.Transpose.ROTATE_270),3)
    a=np.array(horizontal.getchannel('A'))
    spans=[]
    for x in range(horizontal.width):
        ys=np.where(a[:,x]>25)[0]
        spans.append((int(ys.max()-ys.min()+1) if len(ys) else 0))
    max_span=max(spans) if spans else 0
    if max_span<20:
        raise RuntimeError(f'dedicated K-Flex foreground too small: {horizontal.size}')
    broad_threshold=max(8,int(round(max_span*.42)))
    broad=[i for i,s in enumerate(spans) if s>=broad_threshold]
    if not broad:
        raise RuntimeError('dedicated K-Flex source has no broad flight face')
    x0=max(0,min(broad)-2)
    face=trim_alpha(horizontal.crop((x0,0,horizontal.width,horizontal.height)),3)
    clean,qc=collapse_cross_fin_band(face)
    qc.update({
        'mode':'DEDICATED_FRONTAL_KFLEX_SOURCE',
        'sourceUrl':url,
        'sourcePage':spec.get('flightProductPage'),
        'sourceImageSize':[raw.width,raw.height],
        'sourceGrounded':True,
    })
    # Persist only the isolated/cropped K-Flex reference needed for QA, not the
    # full retailer catalogue image.
    save_component(horizontal,SRC/'web-mandalorian-kflex-frontal-source-grounded.png')
    return clean,qc

def canonicalize_integrated_flight_face(img:Image.Image):
    """Extract the dominant broad flight face from a photographed integrated rear.

    A side product photo already contains the perpendicular fin as a thin horizontal
    occluder. Mapping that composite crop onto a 3D plane duplicates the fin. Keep the
    source-grounded broad face, remove thin trailing protrusions and approximate only the
    narrow occluded centre band. The approximation is explicitly recorded in metadata.
    """
    base=trim_alpha(img.convert('RGBA'),3)
    arr=np.array(base).copy()
    alpha=arr[:,:,3]
    h,w=alpha.shape
    spans=[]; bounds=[]
    for x in range(w):
        ys=np.where(alpha[:,x]>30)[0]
        if len(ys):
            y0,y1=int(ys.min()),int(ys.max())
            spans.append(y1-y0+1); bounds.append((y0,y1))
        else:
            spans.append(0); bounds.append(None)
    max_span=max(spans) if spans else 0
    if max_span < 8:
        return base, {'mode':'PASSTHROUGH','reason':'flight face too small for de-occlusion'}

    broad_threshold=max(6,int(round(max_span*.30)))
    broad=[i for i,s in enumerate(spans) if s>=broad_threshold]
    if not broad:
        return base, {'mode':'PASSTHROUGH','reason':'no dominant broad face detected'}

    face_start=min(broad); face_end=max(broad)
    centres=[(bounds[x][0]+bounds[x][1])/2 for x in broad if bounds[x]]
    center=int(round(float(np.median(centres)))) if centres else h//2

    # Remove the thin perpendicular fin where it protrudes beyond the broad face.
    envelope=np.zeros_like(alpha)
    for x in range(w):
        b=bounds[x]
        if not b: continue
        y0,y1=b
        if x < face_start:
            # Keep the narrow root leading into the broad face.
            envelope[y0:y1+1,x]=255
        elif x <= face_end and spans[x] >= max(3,int(broad_threshold*.55)):
            envelope[y0:y1+1,x]=255
    arr[:,:,3]=np.minimum(alpha,envelope).astype(np.uint8)

    # The broad face is genuinely visible, but the centre strip is hidden by the
    # perpendicular fin in the source photo. Fill only that unknown strip from the
    # immediately adjacent source pixels instead of copying the composite fin into
    # Plane A. This is APPROXIMATED-OCCLUSION, not claimed original artwork.
    # Remove the source-hidden cross-fin band geometrically instead of painting a
    # synthetic blurred stripe into the artwork. We discard the occluded horizontal
    # strip, join the genuinely visible source pixels above/below it, then resample the
    # canonical face back to its original height. No logo/text is mirrored or invented.
    band=max(1,int(round(max_span*.06)))
    y0=max(0,center-band)
    y1=min(h,center+band+1)
    visible_before=max(1,int((arr[:,:,3]>3).sum()))
    removed_visible=int((arr[y0:y1,:,3]>3).sum())
    collapsed=np.concatenate([arr[:y0,:,:],arr[y1:,:,:]],axis=0)
    if collapsed.shape[0] < 2:
        return Image.fromarray(arr,'RGBA'), {'mode':'PASSTHROUGH','reason':'occlusion strip collapse would empty texture'}
    collapsed_img=Image.fromarray(collapsed,'RGBA').resize((w,h),Image.Resampling.LANCZOS)
    out=trim_alpha(collapsed_img,3)
    approx_pixels=removed_visible
    visible_pixels=max(1,int((arr[:,:,3]>3).sum()))
    return out,{
        'mode':'PRIMARY_FACE_DEOCCLUDED',
        'faceStartPx':int(face_start),
        'faceEndPx':int(face_end),
        'centreBandHalfWidthPx':int(band),
        'deocclusionMethod':'STRIP_COLLAPSE_RESAMPLE',
        'approximatedPixelFraction':round(approx_pixels/visible_before,4),
    }

def make_backface(front:Image.Image)->Image.Image:
    # Unknown reverse faces must not repeat legible logos/text from Plane A. Preserve
    # the silhouette and low-frequency colour identity, but deliberately remove detail.
    base=trim_alpha(front.convert('RGBA'),3)
    w,h=base.size
    sw=max(6,min(18,max(1,w//18))); sh=max(6,min(18,max(1,h//18)))
    low=base.convert('RGB').resize((sw,sh),Image.Resampling.BOX).resize((w,h),Image.Resampling.BILINEAR)
    low=ImageEnhance.Color(low).enhance(.45)
    low=ImageEnhance.Brightness(low).enhance(.68)
    rgba=low.convert('RGBA')
    rgba.putalpha(base.getchannel('A'))
    return rgba

meta={}
for key,spec in SPECS.items():
    im=normalize_source(spec)
    save_component(im, OUT/key/'normalized-source.png')
    W=im.width
    p1,p2,p3=[int(round(v*W)) for v in spec['splits']]
    # generous vertical canvas but no x overlap: physical component boundaries stay deterministic.
    crops={
      'point': im.crop((0,0,p1,im.height)),
      'barrel': im.crop((p1,0,p2,im.height)),
      ('rear-shaft' if spec['rear'] else 'shaft'): im.crop((p2,0,p3,im.height)),
      'flight-plane-a': im.crop((p3,0,W,im.height)),
    }
    if spec['bg']=='dark-roi':
        crops['flight-plane-a']=mask_flight_polygon(clean_large_component(crops['flight-plane-a']))
    flight_qc=None
    dedicated_flight,dedicated_qc=prepare_dedicated_flight_face(spec)
    if dedicated_flight is not None:
        crops['flight-plane-a']=dedicated_flight
        flight_qc=dedicated_qc
    elif spec.get('canonicalFlight'):
        crops['flight-plane-a'],flight_qc=canonicalize_integrated_flight_face(crops['flight-plane-a'])
    for name,c in crops.items(): save_component(c,OUT/key/f'{name}.png')
    flight=trim_alpha(crops['flight-plane-a'],3)
    back=make_backface(flight)
    save_component(back,OUT/key/'flight-plane-b-approx.png')
    meta[key]={
      'sourceFile':spec['file'],
      'normalizedWidth':im.width,'normalizedHeight':im.height,
      'splitsPx':[p1,p2,p3],
      'splitFractions':spec['splits'],
      'flightProfile':flight_profile(flight),
      'rearIntegrated':spec['rear'],
      'flightExtractionMode':(flight_qc or {}).get('mode','DIRECT_SOURCE_FACE'),
      'flightPlaneAProvenance':'SOURCE-GROUNDED+APPROXIMATED-OCCLUSION' if flight_qc and (flight_qc.get('mode') in ('PRIMARY_FACE_DEOCCLUDED','DEDICATED_FRONTAL_KFLEX_SOURCE')) else 'SOURCE-GROUNDED',
      'flightPlaneBProvenance':'APPROXIMATED',
      'flightSourceUrl':(flight_qc or {}).get('sourceUrl'),
      'flightSourcePage':(flight_qc or {}).get('sourcePage'),
      'flightApproximation':flight_qc,
      'authoringStatus':'SOURCE-GROUNDED component split; dedicated frontal flight sources are preferred over photographed composite side views; only explicitly recorded occlusion strips are approximated',
    }

# Generic geometry-only Slim flight reference. It is intentionally not a product preset.
gdir=OUT/'generic'; gdir.mkdir(parents=True,exist_ok=True)
w,h=512,220
slim=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(slim)
poly=[(0,h//2),(45,70),(120,38),(w-1,62),(w-1,h-62),(120,h-38),(45,h-70)]
d.polygon(poly,fill=(92,103,122,245),outline=(190,200,215,255),width=3)
d.line([(0,h//2),(w-1,h//2)],fill=(215,220,230,210),width=2)
slim.save(gdir/'slim-plane-a.png')
make_backface(slim).save(gdir/'slim-plane-b-approx.png')

# Additional player darts researched on the web. These are deliberately local
# WEB-REFERENCED RECONSTRUCTIONS, not downloaded/manufacturer pixels. Keeping
# them in the same metadata file lets the normal catalog/build/QA pipeline treat
# them exactly like every other authored component while preserving provenance.
from web_player_assets import generate as generate_web_player_assets
meta.update(generate_web_player_assets())

(ROOT/'data/authoring-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta,indent=2))
