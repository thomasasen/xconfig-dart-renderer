from __future__ import annotations
import json, shutil, math
from io import BytesIO
from urllib.request import Request, urlopen
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import cv2
from tail_authoring import author_tail_components

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'assets/source'
OUT=ROOT/'assets/components'
OUT.mkdir(parents=True, exist_ok=True)

# Authoring coordinates are deliberately image-space only. Physical geometry lives in catalog.json.
# splits = fractions of the extracted horizontal dart length: point | barrel | shaft/rear | flight.
SPECS={
 'prodigy': dict(file='target-luke-littler-g1-prodigy-95-swiss-23-gram_3.webp', rotate=True, bg='white', splits=[0.1625,0.56875,0.6875], rear=True, canonicalFlight=True, canonicalProfile='NO2'),
 'shift': dict(file='target-shift-sp-steeltip-90_3.webp', rotate=False, bg='white', splits=[0.1857,0.5214,0.6929], rear=True, canonicalFlight=True, canonicalProfile='NO6'),
 'gary': dict(file='unicorn-w-c-gary-anderson-phase-6-90_1.webp', rotate=True, bg='white', splits=[0.1857,0.5214,0.7214], rear=False, canonicalFlight=True, canonicalProfile='STANDARD'),
 'chrono': dict(file='target-phil-taylor-power-chrono-sp-steeltip-95_3.webp', rotate=True, bg='white', splits=[0.2286,0.5714,0.7786], rear=False, canonicalFlight=True, canonicalProfile='VAPOR_S'),
 'world': dict(file='target-luke-littler-world-champion-90-swiss-23-gram_3.webp', rotate=True, bg='white', splits=[0.20625,0.55,0.7375], rear=True, canonicalFlight=True, canonicalProfile='NO6'),
 'auro': dict(file='shot-alchemy-auro-90_3.webp', rotate=True, bg='white', splits=[0.20,0.53125,0.73125], rear=False, canonicalFlight=True),
 'supa': dict(file='PW2022_SupaVenom_Steel_LEFT.webp', rotate=False, bg='alpha', splits=[0.15,0.525,0.7625], rear=False, canonicalFlight=True),
 'mandalorian': dict(
   file='190840STARWARSMANDALORIAN95_STEElTIP_GALLERY_DE_PT01.webp',
   rotate=False, bg='dark-roi', roi=(38,175,765,350),
   splits=[0.19,0.565,0.725], rear=True, canonicalFlight=False,
   flightWebMode='KFLEX_CENTER_DART_FRONT',
   flightProductPage='https://www.target-darts.co.uk/star-wars-mandalorian-sp',
   flightWebSources=[
      # Exact blue No.2 K-Flex supplied with the Mandalorian SP. The central dart is
      # photographed front-on, so its broad plane can be used without side-view
      # perspective or the wrong black No.6 gift-set artwork.
      'https://mcdart.de/media/2240x2240x100/e8/52/d4/1775636511/360523_Target_StarWars_Mandalorian_SP_Steeldarts_1Set.png?ts=1775687705',
      'https://arrowheadz.co.uk/cdn/shop/files/mandalorian95.png?v=1776884701&width=1500',
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

def alpha_connected_white_background(img:Image.Image)->Image.Image:
    """Remove only border-connected catalogue white, preserving white printed artwork."""
    arr=np.array(img.convert('RGBA')).copy()
    rgb=arr[:,:,:3].astype(np.int16)
    lo=rgb.min(axis=2); hi=rgb.max(axis=2); chroma=hi-lo
    candidate=((lo>242)&(chroma<12)).astype(np.uint8)
    n,labels,_,_=cv2.connectedComponentsWithStats(candidate,8)
    border_labels=set(np.unique(np.concatenate([labels[0,:],labels[-1,:],labels[:,0],labels[:,-1]])))
    bg=np.zeros(candidate.shape,np.uint8)
    for lab in border_labels:
        if lab==0: continue
        bg[labels==lab]=255
    # Slightly feather only the outside boundary; enclosed white logos remain opaque.
    bg=Image.fromarray(bg,'L').filter(ImageFilter.GaussianBlur(.65))
    alpha=255-np.asarray(bg,dtype=np.uint8)
    arr[:,:,3]=np.minimum(arr[:,:,3],alpha).astype(np.uint8)
    return trim_alpha(Image.fromarray(arr,'RGBA'),3)

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

def suppress_low_alpha_haze(img:Image.Image, cutoff=72):
    """Remove semi-transparent infographic background without hard-clipping real edges."""
    arr=np.array(img.convert('RGBA')).copy()
    a=arr[:,:,3].astype(np.float32)
    a=np.clip((a-cutoff)*255.0/max(1,255-cutoff),0,255).astype(np.uint8)
    arr[:,:,3]=a
    return trim_alpha(Image.fromarray(arr,'RGBA'),3)

def trim_rear_by_saturation(img:Image.Image):
    """Crop dark infographic residue around a coloured integrated shaft.

    The Mandalorian shaft itself is strongly blue/saturated while the infographic
    residue is neutral grey. Only vertical canvas is trimmed; shaft RGB is untouched.
    """
    rgba=img.convert('RGBA')
    arr=np.array(rgba)
    rgb=arr[:,:,:3].astype(np.int16)
    sat=rgb.max(axis=2)-rgb.min(axis=2)
    row_score=(sat>15).sum(axis=1)
    threshold=max(4,int(round(rgba.width*.18)))
    ys=np.where(row_score>=threshold)[0]
    if len(ys)==0:
        return trim_alpha(rgba,3)
    y0=max(0,int(ys.min())-3)
    y1=min(rgba.height,int(ys.max())+4)
    return trim_alpha(rgba.crop((0,y0,rgba.width,y1)),3)

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

NO6_PROFILE=[[0.00,0.00],[0.08,0.30],[0.22,0.90],[0.68,1.00],[0.94,0.72],[1.00,0.35],[1.00,-0.35],[0.94,-0.72],[0.68,-1.00],[0.22,-0.90],[0.08,-0.30]]
NO2_PROFILE=[[0.00,0.00],[0.06,0.34],[0.18,0.96],[0.60,1.00],[0.90,0.82],[1.00,0.45],[1.00,-0.45],[0.90,-0.82],[0.60,-1.00],[0.18,-0.96],[0.06,-0.34]]
STANDARD_PROFILE=[[0.00,0.00],[0.06,0.34],[0.18,0.96],[0.60,1.00],[0.90,0.82],[1.00,0.45],[1.00,-0.45],[0.90,-0.82],[0.60,-1.00],[0.18,-0.96],[0.06,-0.34]]
# Vapor S is a narrow elongated flight. Exact manufacturer CAD is not available in
# the source bundle, so this canonical outline is an explicit geometry heuristic,
# while the printed artwork remains source-grounded.
VAPOR_S_PROFILE=[[0.00,0.00],[0.10,0.24],[0.28,0.72],[0.56,1.00],[0.82,0.90],[1.00,0.48],[1.00,-0.48],[0.82,-0.90],[0.56,-1.00],[0.28,-0.72],[0.10,-0.24]]
CANONICAL_PROFILES={'NO6':NO6_PROFILE,'NO2':NO2_PROFILE,'STANDARD':STANDARD_PROFILE,'VAPOR_S':VAPOR_S_PROFILE}

def mask_to_flight_profile(image:Image.Image, profile):
    rgba=image.convert('RGBA')
    w,h=rgba.size
    scale=4
    mask=Image.new('L',(w*scale,h*scale),0)
    draw=ImageDraw.Draw(mask)
    pts=[]
    for u,v in profile:
        x=float(u)*(w-1)*scale
        y=(0.5-float(v)*0.5)*(h-1)*scale
        pts.append((x,y))
    draw.polygon(pts,fill=255)
    mask=mask.resize((w,h),Image.Resampling.LANCZOS)
    arr=np.asarray(rgba).copy()
    arr[:,:,3]=np.minimum(arr[:,:,3],np.asarray(mask,dtype=np.uint8)).astype(np.uint8)
    return trim_alpha(Image.fromarray(arr,'RGBA'),3)

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
    mode=spec.get('flightWebMode')
    if mode not in ('KFLEX_FRONTAL_LEFT','KFLEX_CENTER_DART_FRONT'):
        return None,None
    raw,url=download_reference_image(spec.get('flightWebSources'))

    if mode=='KFLEX_CENTER_DART_FRONT':
        # Blue Mandalorian artwork reference: isolate the central/front-facing
        # dart. Geometry is NOT taken from this retail image: the supplied infographic
        # explicitly defines the mounted flight as No.6, so a No.6 mask is applied later.
        x0=int(round(raw.width*.28)); x1=int(round(raw.width*.72))
        y1=int(round(raw.height*.48))
        central=raw.crop((x0,0,x1,max(1,y1)))
        isolated=largest_alpha_component(alpha_connected_white_background(central),20)
        a=np.array(isolated.getchannel('A'))
        widths=[]; bounds=[]
        for y in range(isolated.height):
            xs=np.where(a[y,:]>25)[0]
            if len(xs):
                widths.append(int(xs.max()-xs.min()+1)); bounds.append((int(xs.min()),int(xs.max())))
            else:
                widths.append(0); bounds.append(None)
        max_width=max(widths) if widths else 0
        if max_width<30:
            raise RuntimeError(f'dedicated blue K-Flex foreground too small: {isolated.size}')
        broad_threshold=max(12,int(round(max_width*.38)))
        broad=[i for i,v in enumerate(widths) if v>=broad_threshold]
        if not broad:
            raise RuntimeError('blue K-Flex source has no broad frontal flight face')
        top=max(0,min(broad)-3)
        last=max(broad)
        # Include the tapered flight root, but stop before the long narrow shaft.
        narrow_limit=max(6,int(round(max_width*.16)))
        bottom=last
        low_run=0
        for y in range(last+1,isolated.height):
            if widths[y] <= narrow_limit:
                low_run += 1
                if low_run>=5:
                    bottom=max(last,y-low_run+1)
                    break
            else:
                low_run=0; bottom=y
        face=trim_alpha(isolated.crop((0,top,isolated.width,min(isolated.height,bottom+2))),3)
        # Shaft points down in the reference; clockwise rotation makes the flight root
        # point left, matching the xConfig canonical texture convention.
        horizontal=trim_alpha(face.transpose(Image.Transpose.ROTATE_270),3)
    else:
        # Fallback helper retained for other future frontal pair references.
        left=raw.crop((0,0,max(1,raw.width//2),raw.height))
        isolated=largest_alpha_component(alpha_connected_white_background(left),20)
        horizontal=trim_alpha(isolated.transpose(Image.Transpose.ROTATE_270),3)
        a=np.array(horizontal.getchannel('A'))
        spans=[]
        for x in range(horizontal.width):
            ys=np.where(a[:,x]>25)[0]
            spans.append((int(ys.max()-ys.min()+1) if len(ys) else 0))
        max_span=max(spans) if spans else 0
        broad_threshold=max(8,int(round(max_span*.42)))
        broad=[i for i,s in enumerate(spans) if s>=broad_threshold]
        if not broad:
            raise RuntimeError('dedicated K-Flex source has no broad flight face')
        horizontal=trim_alpha(horizontal.crop((max(0,min(broad)-2),0,horizontal.width,horizontal.height)),3)

    # The front-facing artwork reference still contains the perpendicular K-Flex plane
    # edge-on across the axis. Remove ±10% around the axis. The two remaining halves
    # retain source pixels; canonical outer geometry comes from the supplied No.6 infographic.
    clean,qc=collapse_cross_fin_band(horizontal,half_band_ratio=.10)
    clean=mask_to_flight_profile(clean,NO6_PROFILE)
    qc.update({
        'mode':'DEDICATED_FRONTAL_KFLEX_SOURCE',
        'sourceUrl':url,
        'sourcePage':spec.get('flightProductPage'),
        'sourceImageSize':[raw.width,raw.height],
        'sourceGrounded':True,
        'design':'MANDALORIAN_BLUE_SOURCE_ARTWORK',
        'canonicalProfile':'NO6_SUPPLIED_INFOGRAPHIC',
        'profileMaskApplied':True,
    })
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

    # V1.3.3: the visible tail is authored from an axis/width profile instead of
    # trusting the legacy X split. The old split remains only as a seed/fallback.
    tail_result=author_tail_components(
        im,
        shaft_seed_range=(p2,p3),
        flight_start_px=p3,
        integrated=bool(spec['rear']),
    )
    tail_analysis=tail_result['analysis'].to_dict()
    tail_status=tail_analysis['status']
    # A hard axis/root failure must not silently replace a known-good legacy crop.
    # PASS and NEEDS_MANUAL_REVIEW are persisted for visual QA; explicit FAIL states
    # keep the legacy component but are still hard-visible in metadata/CI.
    if tail_status in ('PASS','NEEDS_MANUAL_REVIEW'):
        tail_name='rear-shaft' if spec['rear'] else 'shaft'
        crops[tail_name]=tail_result['shaftCoreImage']
        if spec['rear']:
            crops['rear-shaft-core']=tail_result['shaftCoreImage']
        if spec['rear'] and tail_result.get('rearRootImage') is not None:
            crops['rear-root']=tail_result['rearRootImage']
    if spec['bg']=='dark-roi':
        for component_name in ('point','barrel','rear-shaft','shaft'):
            if component_name in crops:
                crops[component_name]=suppress_low_alpha_haze(crops[component_name])
        crops['flight-plane-a']=mask_flight_polygon(clean_large_component(crops['flight-plane-a']))
    flight_qc=None
    dedicated_flight,dedicated_qc=prepare_dedicated_flight_face(spec)
    if dedicated_flight is not None:
        crops['flight-plane-a']=dedicated_flight
        flight_qc=dedicated_qc
    elif spec.get('canonicalFlight'):
        crops['flight-plane-a'],flight_qc=canonicalize_integrated_flight_face(crops['flight-plane-a'])

    # Batch 2A: photographed side-view silhouettes are not canonical fin geometry.
    # For product families whose actual mounted flight shape is known, keep the
    # source-grounded artwork but constrain alpha and renderer geometry to the
    # canonical No.2/No.6 envelope. This prevents photographed perspective and
    # cross-fin protrusions from becoming permanent 3D mesh geometry.
    canonical_profile=CANONICAL_PROFILES.get(spec.get('canonicalProfile'))
    if canonical_profile is not None:
        crops['flight-plane-a']=mask_to_flight_profile(crops['flight-plane-a'],canonical_profile)
        flight_qc=dict(flight_qc or {})
        flight_qc.update({
            'canonicalProfile':spec['canonicalProfile'],
            'profileMaskApplied':True,
            'geometrySource':(
                'HEURISTIC_FLIGHT_SHAPE'
                if spec['canonicalProfile']=='VAPOR_S'
                else 'KNOWN_FLIGHT_SHAPE'
            ),
        })

    for name,c in crops.items(): save_component(c,OUT/key/f'{name}.png')
    flight=trim_alpha(crops['flight-plane-a'],3)
    back=make_backface(flight)
    save_component(back,OUT/key/'flight-plane-b-approx.png')
    meta[key]={
      'sourceFile':spec['file'],
      'normalizedWidth':im.width,'normalizedHeight':im.height,
      'splitsPx':[p1,p2,p3],
      'splitFractions':spec['splits'],
      'flightProfile':canonical_profile if canonical_profile is not None else flight_profile(flight),
      'rearIntegrated':spec['rear'],
      'flightExtractionMode':(flight_qc or {}).get('mode','DIRECT_SOURCE_FACE'),
      'flightPlaneAProvenance':'SOURCE-GROUNDED+APPROXIMATED-OCCLUSION' if flight_qc and (flight_qc.get('mode') in ('PRIMARY_FACE_DEOCCLUDED','DEDICATED_FRONTAL_KFLEX_SOURCE')) else 'SOURCE-GROUNDED',
      'flightPlaneBProvenance':'APPROXIMATED',
      'flightSourceUrl':(flight_qc or {}).get('sourceUrl'),
      'flightSourcePage':(flight_qc or {}).get('sourcePage'),
      'flightQaSourceFile':'web-mandalorian-kflex-frontal-source-grounded.png' if (flight_qc or {}).get('mode')=='DEDICATED_FRONTAL_KFLEX_SOURCE' else None,
      'flightApproximation':flight_qc,
      'axisAuthoring':tail_result['axisAuthoring'],
      'tailSegmentation':tail_result['tailSegmentation'],
      'tailMetrics':tail_result['tailMetrics'],
      'tailAuthoring':{
        'axisConfidence':tail_result['axisAuthoring']['confidence'],
        'shaftCoreConfidence':tail_result['tailSegmentation']['confidence'],
        'rootBoundaryConfidence':tail_result['tailSegmentation']['confidence'] if spec['rear'] else 1.0,
        'flightSourceConfidence':1.0 if flight_qc is not None else 0.9,
        'overallConfidence':tail_analysis['confidence'],
        'status':tail_status,
      },
      'rootAuthored':bool(spec['rear'] and tail_status in ('PASS','NEEDS_MANUAL_REVIEW') and tail_result.get('rearRootImage') is not None),
      'authoringStatus':(
        'SOURCE-GROUNDED axis/width-profile tail authoring; '
        + tail_status
        + '; dedicated frontal flight sources are preferred over photographed composite side views; '
        + 'only explicitly recorded occlusion strips are approximated'
      ),
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
