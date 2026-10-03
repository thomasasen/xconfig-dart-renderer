from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import json, math
from io import BytesIO
from urllib.request import Request, urlopen
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'components'
SRC = ROOT / 'assets' / 'source'
OUT.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

# V1.3: Gabriel Clemens G2 and 95K use real product-image pixels.
# Full third-party product photographs are never persisted. The authoring step downloads
# them transiently, extracts only the dart/component pixels required by the renderer,
# records the exact source URL, and discards the original response bytes.
SOURCE_GROUNDED_WEB='SOURCE-GROUNDED-WEB-EXTRACT'

SOURCE_GROUNDED_SPECS = {
    'clemens-g2': {
        'integrated': False,
        'shape': 'No.6',
        'profile': None,  # filled after NO6 is defined
        'splits': [0.17, 0.51, 0.73],
        'officialPage': 'https://www.target-darts.co.uk/gabriel-clemens-g2-sp',
        'flightProductPage': 'https://www.target-darts.co.uk/gabriel-clemens-g2-flights',
        'flightSources': [
            # Exact G2 Pro.Ultra No.6 (SKU 336870), photographed flat. This is used
            # instead of the assembled-dart composite flight crop.
            'https://www.bullydarts.co.uk/cdn/shop/files/336870GABRIELCLEMENSG2x3SETSPRO.ULTRANO.6FLIGHTBAGGED2023FLAT_1.jpg?v=1694594825&width=3111',
            'https://dartgott.de/media/02/e0/25/1718815398/target-gabriel-clemens-g2-pro-ultra-no6-flights-3-sets.webp?ts=1781909020',
        ],
        'sources': [
            # Manufacturer first. Retail broadside is a fallback if the official box-content
            # composition does not contain a usable complete assembled dart.
            'https://www.target-darts.co.uk/media/catalog/product/g/a/gabriel-clemens-g2-sp-darts-set-box-contents-main-image.jpg?fit=bounds&height=1200&quality=80&width=1200',
            # Kilo80 provides a clean orthogonal product-family broadside on white.
            # The URL contains the 23g GTIN (5050807076109), while product design is
            # common to the G2 weight variants.
            'https://kilo80.de/media/image/53/3f/fa/5050807076109_N003_2000x2000.jpg',
            'https://www.klickers-fanoase.de/media/02/42/fe/1773054178/25137_190181_GABRIEL_CLEMENS_G2_21G_SP_STEELTIP_DARTS_2023-1.jpg',
            'https://www.doubletopdartshop.com/cdn/shop/files/190181_GabrielClemensG2SP.jpg?v=1728566875&width=1214',
        ],
    },
    'clemens-95k': {
        'integrated': True,
        'shape': 'No.6',
        'profile': None,  # filled after NO6 is defined
        'splits': [0.19, 0.565, 0.705],
        'officialPage': 'https://www.target-darts.co.uk/gabriel-clemens-95k-sp',
        'sources': [
            # Official Target side view: full assembled dart from point through No.6 K-Flex.
            'https://www.target-darts.co.uk/media/catalog/product/g/a/gabriel-clemens-95k-steel-tip-dart-sp-03.jpg?fit=bounds&height=1200&quality=80&width=1200',
            'https://www.target-darts.co.uk/media/catalog/product/g/a/gabriel-clemens-95k-steel-tip-dart-sp-01.jpg?fit=bounds&height=1200&quality=80&width=1200',
            # Retail fallback with complete assembled darts; used only if the official
            # manufacturer hero image fails the full-dart silhouette gate.
            'https://www.flightclub.ie/cdn/shop/files/download_31.png?v=1727272211',
            'https://dartshop-bonn.de/WebRoot/Store21/Shops/1be89036-dc4e-4547-8d3b-58f763e72e84/6709/06AB/5F9D/F017/838C/0A48/352D/E048/target-gabriel-clemens-95k-95-swiss.jpg',
            'https://www.dartswarehouse.nl/media/catalog/product/cache/f20831aa4fe732f409bd1d4a248f932d/image/314593a22/target-gabriel-clemens-95k-95-swiss.jpg',
        ],
    },
}

def _download_product_image(urls):
    errors=[]
    for url in urls:
        try:
            req=Request(url,headers={
                'User-Agent':'Mozilla/5.0 (compatible; xConfig-Dart-Renderer-Research/1.3)',
                'Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            })
            with urlopen(req,timeout=25) as response:
                data=response.read()
            image=Image.open(BytesIO(data)).convert('RGBA')
            if image.width < 300 or image.height < 300:
                raise ValueError(f'image too small: {image.size}')
            return image,url
        except Exception as exc:
            errors.append(f'{url}: {exc}')
    raise RuntimeError('No usable product image source could be downloaded. ' + ' | '.join(errors))

def _corner_background(rgb):
    h,w,_=rgb.shape
    bh=max(4,h//20); bw=max(4,w//20)
    sample=np.concatenate([
        rgb[:bh,:bw].reshape(-1,3),
        rgb[:bh,-bw:].reshape(-1,3),
        rgb[-bh:,:bw].reshape(-1,3),
        rgb[-bh:,-bw:].reshape(-1,3),
    ],axis=0)
    return np.median(sample,axis=0)

def _foreground_mask(image):
    arr=np.asarray(image.convert('RGBA'))
    rgb=arr[:,:,:3].astype(np.float32)
    alpha=arr[:,:,3]
    bg=_corner_background(rgb)
    dist=np.linalg.norm(rgb-bg[None,None,:],axis=2)
    # Real product photos are typically neutral-background catalogue images. Keep
    # coloured/metallic/dark detail, then bridge the thin point/shaft gaps only for
    # object detection; source RGB itself is never painted or reconstructed.
    mask=((dist>19) & (alpha>10)).astype(np.uint8)*255
    k=max(3,round(min(image.width,image.height)*0.004))
    k += 1-k%2
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((k,k),np.uint8))
    return mask,dist,alpha

def _best_elongated_roi(image):
    mask,dist,source_alpha=_foreground_mask(image)
    h,w=mask.shape
    candidates=[]

    # Clean catalogue broadside images often contain exactly one dart whose physical
    # components are separated by tiny antialiased gaps. Treat the bounding box of all
    # foreground pixels as an additional candidate instead of requiring connectivity.
    ys_all,xs_all=np.where(mask>0)
    if len(xs_all):
        gx0,gx1=int(xs_all.min()),int(xs_all.max())+1
        gy0,gy1=int(ys_all.min()),int(ys_all.max())+1
        gw,gh=gx1-gx0,gy1-gy0
        gmajor=max(gw,gh); gminor=max(1,min(gw,gh)); gratio=gmajor/gminor
        foreground_fraction=float((mask[gy0:gy1,gx0:gx1]>0).mean())
        if gmajor >= max(w,h)*0.35 and gratio >= 3.3 and foreground_fraction < 0.72:
            # Slight score boost: when the whole image is a single broadside this is
            # more robust than a morphology-dependent contour.
            candidates.append((gmajor*gratio*1.15,gx0,gy0,gw,gh,'global'))

    # Build two detection masks so a horizontal or vertical dart can be found.
    for orientation,kernel in [
        ('horizontal',np.ones((max(3,h//220),max(15,w//45)),np.uint8)),
        ('vertical',np.ones((max(15,h//45),max(3,w//220)),np.uint8)),
    ]:
        joined=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel,iterations=2)
        joined=cv2.dilate(joined,np.ones((3,3),np.uint8),iterations=1)
        contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x,y,cw,ch=cv2.boundingRect(contour)
            major=max(cw,ch); minor=max(1,min(cw,ch)); ratio=major/minor
            if major < max(w,h)*0.25 or ratio < 4.0:
                continue
            # Prefer long/slender objects over boxes and packaging panels.
            score=major*ratio*(0.6+min(1.0,cv2.contourArea(contour)/(cw*ch+1)))
            candidates.append((score,x,y,cw,ch,orientation))
    if not candidates:
        raise RuntimeError('No sufficiently elongated dart candidate found in product image')
    _,x,y,cw,ch,orientation=max(candidates,key=lambda item:item[0])
    pad=max(4,round(min(cw,ch)*0.20))
    x0=max(0,x-pad); y0=max(0,y-pad); x1=min(w,x+cw+pad); y1=min(h,y+ch+pad)
    crop=image.crop((x0,y0,x1,y1)).convert('RGBA')
    if crop.height > crop.width:
        crop=crop.transpose(Image.Transpose.ROTATE_270)

    # Ensure point is left and flight is right. The flight end has much larger
    # foreground vertical coverage than the point end.
    cmask,cdist,calpha=_foreground_mask(crop)
    band=max(2,round(crop.width*0.14))
    def end_span(m):
        ys=np.where(m>0)[0]
        return 0 if len(ys)==0 else int(ys.max()-ys.min()+1)
    left=end_span(cmask[:,:band]); right=end_span(cmask[:,-band:])
    if left > right*1.15:
        crop=crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        cmask,cdist,calpha=_foreground_mask(crop)

    # Build alpha from the detected silhouette. Filling between top/bottom foreground
    # pixels per x preserves genuinely white flight artwork that colour-keying alone
    # would incorrectly erase. RGB pixels remain untouched original source pixels.
    silhouette=np.zeros_like(cmask)
    for xcol in range(cmask.shape[1]):
        ys=np.where(cmask[:,xcol]>0)[0]
        if len(ys):
            silhouette[ys.min():ys.max()+1,xcol]=255
    silhouette=cv2.morphologyEx(
        silhouette,cv2.MORPH_CLOSE,
        np.ones((max(3,crop.height//90),max(3,crop.width//250)),np.uint8)
    )
    silhouette=cv2.GaussianBlur(silhouette,(0,0),0.65)
    rgba=np.asarray(crop).copy()
    rgba[:,:,3]=np.minimum(np.asarray(crop)[:,:,3],silhouette).astype(np.uint8)
    result=Image.fromarray(rgba,'RGBA')
    bbox=result.getbbox()
    if not bbox:
        raise RuntimeError('Extracted dart candidate has empty alpha')
    result=result.crop(bbox)
    if result.width/result.height < 3.2:
        raise RuntimeError(f'Extracted candidate is not dart-like enough: {result.size}')

    # A barrel close-up is also long and slender, so aspect ratio alone is not enough.
    # Require a genuine tail/flight signature: the rear end must be substantially taller
    # than the central body band. This rejects barrel-only manufacturer hero images.
    rmask,_,_=_foreground_mask(result)
    spans=[]
    for xcol in range(rmask.shape[1]):
        ys=np.where(rmask[:,xcol]>0)[0]
        spans.append(0 if len(ys)==0 else int(ys.max()-ys.min()+1))
    n=len(spans)
    body=np.array([v for v in spans[int(n*.30):int(n*.62)] if v>0],dtype=float)
    tail=np.array([v for v in spans[int(n*.82):] if v>0],dtype=float)
    if len(body)==0 or len(tail)==0:
        raise RuntimeError('Extracted candidate lacks measurable body/tail silhouette')
    body_span=float(np.median(body))
    tail_span=float(np.percentile(tail,75))
    if tail_span < body_span*1.45:
        raise RuntimeError(
            f'Candidate looks like barrel/body only: tail span {tail_span:.1f}px '
            f'vs body {body_span:.1f}px (need >= 1.45x)'
        )
    return result

def _mask_to_flight_profile(image, profile):
    rgba=image.convert('RGBA')
    w,h=rgba.size
    # Build alpha exclusively from the canonical flight geometry. This preserves white
    # printed artwork even when the catalogue background is also white.
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
    source_alpha=rgba.getchannel('A')
    alpha=np.minimum(np.asarray(source_alpha,dtype=np.uint8),np.asarray(mask,dtype=np.uint8))
    out=np.asarray(rgba).copy()
    out[:,:,3]=alpha
    return Image.fromarray(out,'RGBA')

def _prepare_flat_flight_texture(spec):
    urls=spec.get('flightSources') or []
    if not urls:
        return None,None
    image,source_url=_download_product_image(urls)
    rgba=image.convert('RGBA')
    # Flat accessory photos are intentionally not colour-keyed: white artwork is part
    # of the printed flight and must not disappear into a white catalogue background.
    # Geometry supplies the No.6 silhouette, so only trim a tiny outer catalogue margin.
    w,h=rgba.size
    margin=max(0,round(min(w,h)*0.005))
    if margin and w>margin*2 and h>margin*2:
        rgba=rgba.crop((margin,margin,w-margin,h-margin))
    # Product face is photographed upright; rotate to the canonical xConfig convention
    # where the flight root is on the left and the trailing edge on the right.
    rgba=rgba.transpose(Image.Transpose.ROTATE_270)
    rgba=_mask_to_flight_profile(rgba,spec['profile'])
    return rgba,source_url

def _canonicalize_integrated_flight_face(image):
    """Remove the already-photographed perpendicular fin from a side-view flight crop.

    The broad face remains source-grounded. Only the narrow centre strip hidden by the
    perpendicular fin is reconstructed from adjacent source pixels and is explicitly
    reported as APPROXIMATED-OCCLUSION.
    """
    base=image.convert('RGBA')
    bbox=base.getbbox()
    if bbox: base=base.crop(bbox)
    arr=np.asarray(base).copy()
    alpha=arr[:,:,3]
    h,w=alpha.shape
    spans=[]; bounds=[]
    for x in range(w):
        ys=np.where(alpha[:,x]>28)[0]
        if len(ys):
            y0,y1=int(ys.min()),int(ys.max())
            spans.append(y1-y0+1); bounds.append((y0,y1))
        else:
            spans.append(0); bounds.append(None)
    max_span=max(spans) if spans else 0
    if max_span<8:
        return base,{'mode':'PASSTHROUGH','reason':'flight face too small for de-occlusion'}

    broad_threshold=max(6,int(round(max_span*.30)))
    broad=[i for i,s in enumerate(spans) if s>=broad_threshold]
    if not broad:
        return base,{'mode':'PASSTHROUGH','reason':'no dominant broad face detected'}
    face_start,face_end=min(broad),max(broad)
    centres=[(bounds[x][0]+bounds[x][1])/2 for x in broad if bounds[x]]
    center=int(round(float(np.median(centres)))) if centres else h//2

    envelope=np.zeros_like(alpha)
    for x,b in enumerate(bounds):
        if not b: continue
        y0,y1=b
        if x<face_start:
            envelope[y0:y1+1,x]=255
        elif x<=face_end and spans[x]>=max(3,int(broad_threshold*.55)):
            envelope[y0:y1+1,x]=255
    arr[:,:,3]=np.minimum(alpha,envelope).astype(np.uint8)

    band=max(1,int(round(max_span*.035)))
    approx_pixels=0
    for x in range(face_start,face_end+1):
        if spans[x]<broad_threshold: continue
        y_top=max(0,center-band-2); y_bot=min(h-1,center+band+2)
        if y_bot<=y_top: continue
        fill=((arr[y_top,x,:3].astype(np.uint16)+arr[y_bot,x,:3].astype(np.uint16))//2).astype(np.uint8)
        ya=max(0,center-band); yb=min(h,center+band+1)
        valid=arr[ya:yb,x,3]>0
        arr[ya:yb,x,:3][valid]=fill
        approx_pixels+=int(valid.sum())

    out=Image.fromarray(arr,'RGBA')
    bbox=out.getbbox()
    if bbox: out=out.crop(bbox)
    visible=max(1,int((arr[:,:,3]>3).sum()))
    return out,{
        'mode':'PRIMARY_FACE_DEOCCLUDED',
        'faceStartPx':int(face_start),
        'faceEndPx':int(face_end),
        'centreBandHalfWidthPx':int(band),
        'approximatedPixelFraction':round(approx_pixels/visible,4),
    }

def _split_source_grounded(key,spec):
    errors=[]
    dart=None
    source_url=None
    for candidate_url in spec['sources']:
        try:
            raw,_=_download_product_image([candidate_url])
            candidate=_best_elongated_roi(raw)
            dart=candidate
            source_url=candidate_url
            break
        except Exception as exc:
            errors.append(f'{candidate_url}: {exc}')
    if dart is None:
        raise RuntimeError(f'{key}: no full-dart source passed visual-geometry checks. ' + ' | '.join(errors))
    w=dart.width
    p1,p2,p3=[max(1,min(w-1,round(v*w))) for v in spec['splits']]
    if not (0 < p1 < p2 < p3 < w):
        raise RuntimeError(f'{key}: invalid component split {[p1,p2,p3]} for width {w}')
    names=['point','barrel','rear-shaft' if spec['integrated'] else 'shaft','flight-plane-a']
    ranges=[(0,p1),(p1,p2),(p2,p3),(p3,w)]
    parts={}
    for name,(x0,x1) in zip(names,ranges):
        part=dart.crop((x0,0,x1,dart.height))
        bbox=part.getbbox()
        if bbox: part=part.crop(bbox)
        parts[name]=part

    flight_texture,flight_source_url=_prepare_flat_flight_texture(spec)
    flight_qc=None
    if flight_texture is not None:
        parts['flight-plane-a']=flight_texture
        flight_qc={'mode':'FLAT_FLIGHT_SOURCE','approximatedPixelFraction':0.0}
    elif spec['integrated']:
        parts['flight-plane-a'],flight_qc=_canonicalize_integrated_flight_face(parts['flight-plane-a'])

    # Plane B is intentionally only an approximation. Do not mirror/copy source
    # artwork: repeated text/logos on a perpendicular fin falsely implies known pixels.
    parts['flight-plane-b-approx']=backface(parts['flight-plane-a'])

    d=OUT/key
    d.mkdir(parents=True,exist_ok=True)
    for name,part in parts.items():
        save(part,d/f'{name}.png')
    # The UI comparison gets only the extracted dart strip, not the full manufacturer
    # photo/box-art. This keeps the research bundle narrowly scoped to required pixels.
    source_name=f'web-{key}-source-grounded.png'
    save(dart,SRC/source_name)
    return {
        'sourceFile':source_name,
        'sourceUrl':source_url,
        'sourcePage':spec['officialPage'],
        'flightProductPage':spec.get('flightProductPage'),
        'componentSources':{
            'point':source_url,
            'barrel':source_url,
            'rear-shaft' if spec['integrated'] else 'shaft':source_url,
            'flight-plane-a':flight_source_url or source_url,
            'flight-plane-b-approx':'derived approximation; no independent source',
        },
        'originalPixels':True,
        'processing':[
            'temporary web download',
            'neutral-background foreground detection',
            'automatic elongated-dart crop',
            'orientation normalisation (tip left)',
            'alpha silhouette extraction',
            'component crop only; RGB pixels not redrawn',
            'when an exact flat flight source exists, Plane A is replaced by that flat source before 3D mapping',
            'integrated side-view flights are de-occluded only in the source-hidden centre strip before 3D mapping',
            'Plane B is a low-frequency approximation with no copied readable logo/text',
        ],
        'splitFractions':spec['splits'],
        'splitsPx':[p1,p2,p3],
        'flightProfile':spec['profile'],
        'rearIntegrated':spec['integrated'],
        'flightExtractionMode':(flight_qc or {}).get('mode','DIRECT_SOURCE_FACE'),
        'flightApproximation':flight_qc,
        'componentProvenance':{
            'point':'SOURCE-GROUNDED',
            'barrel':'SOURCE-GROUNDED',
            'rear-shaft' if spec['integrated'] else 'shaft':'SOURCE-GROUNDED',
            'flight-plane-a':(
                'SOURCE-GROUNDED' if flight_qc and flight_qc.get('mode')=='FLAT_FLIGHT_SOURCE'
                else 'SOURCE-GROUNDED+APPROXIMATED-OCCLUSION' if flight_qc and flight_qc.get('mode')=='PRIMARY_FACE_DEOCCLUDED'
                else 'SOURCE-GROUNDED'
            ),
            'flight-plane-b-approx':'APPROXIMATED',
        },
        'authoringStatus':SOURCE_GROUNDED_WEB,
    }

# These are deliberately WEB-REFERENCED RECONSTRUCTIONS, not downloaded source pixels.
# They are locally authored from inspected product images so the POC stays self-contained.
# Physical dimensions are kept separately in catalog.json and are not inferred from these drawings.

NO6 = [[0.00,0.00],[0.08,0.30],[0.22,0.90],[0.68,1.00],[0.94,0.72],[1.00,0.35],[1.00,-0.35],[0.94,-0.72],[0.68,-1.00],[0.22,-0.90],[0.08,-0.30]]
NO2 = [[0.00,0.00],[0.06,0.34],[0.18,0.96],[0.60,1.00],[0.90,0.82],[1.00,0.45],[1.00,-0.45],[0.90,-0.82],[0.60,-1.00],[0.18,-0.96],[0.06,-0.34]]
STD = NO2
SOURCE_GROUNDED_SPECS['clemens-g2']['profile']=NO6
SOURCE_GROUNDED_SPECS['clemens-95k']['profile']=NO6

def font(size=24, bold=False):
    paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def canvas(w,h): return Image.new('RGBA',(w,h),(0,0,0,0))

def linear_grad(w,h,c1,c2,horizontal=True):
    im=canvas(w,h); px=im.load()
    for y in range(h):
        for x in range(w):
            t=(x/(w-1)) if horizontal else (y/(h-1))
            px[x,y]=tuple(round(c1[i]*(1-t)+c2[i]*t) for i in range(4))
    return im

def rounded_body(w,h,base,outline=(40,40,40,255),radius=None):
    im=canvas(w,h); d=ImageDraw.Draw(im)
    r=radius or h//2
    d.rounded_rectangle((1,1,w-2,h-2),radius=r,fill=base,outline=outline,width=max(2,h//24))
    return im

def draw_point(color=(175,180,185,255), dark=(70,75,80,255), black=False):
    w,h=520,70; im=canvas(w,h); d=ImageDraw.Draw(im)
    cy=h//2
    col=(35,35,38,255) if black else color
    d.polygon([(0,cy),(70,cy-3),(500,cy-11),(519,cy),(500,cy+11),(70,cy+3)],fill=col)
    d.line([(80,cy-2),(498,cy-9)],fill=(235,235,235,130) if not black else (100,100,100,120),width=2)
    return im

def draw_barrel(style):
    w,h=900,180; im=canvas(w,h); d=ImageDraw.Draw(im); cy=h//2
    if style=='clemens-g2':
        d.rounded_rectangle((2,32,w-3,h-33),radius=42,fill=(145,146,145,255),outline=(70,70,70,255),width=3)
        for x in list(range(35,360,34))+list(range(610,875,30)):
            d.rectangle((x,32,x+10,h-33),fill=(88,89,88,255))
            d.line((x+2,36,x+2,h-37),fill=(205,205,200,170),width=2)
        for x in range(385,585,14): d.line((x,45,x,h-46),fill=(75,75,75,230),width=3)
        d.rectangle((438,32,500,h-33),fill=(170,171,170,255))
        d.text((448,69),'T',font=font(34,True),fill=(90,90,90,255))
    elif style=='clemens-95k':
        d.rounded_rectangle((2,30,w-3,h-31),radius=38,fill=(36,38,40,255),outline=(15,15,15,255),width=3)
        for x in range(35,300,29): d.rectangle((x,30,x+10,h-31),fill=(15,16,17,255))
        for x in range(320,520,22):
            for y in range(49,h-49,19): d.ellipse((x,y,x+8,y+8),fill=(110,112,112,255))
        d.rectangle((535,30,595,h-31),fill=(172,174,172,255)); d.rectangle((548,30,559,h-31),fill=(196,26,31,255)); d.rectangle((579,30,590,h-31),fill=(196,26,31,255))
        for x in range(610,875,28): d.rectangle((x,30,x+9,h-31),fill=(10,10,10,255))
    elif style=='cross-95k':
        d.rounded_rectangle((2,34,w-3,h-35),radius=34,fill=(39,40,42,255),outline=(15,15,15,255),width=3)
        for x in range(28,875,38):
            d.rectangle((x,34,x+13,h-35),fill=(20,21,22,255))
            if (x//38)%2==0: d.rectangle((x+13,34,x+22,h-35),fill=(160,154,135,255))
        d.rectangle((w-72,34,w-42,h-35),fill=(163,150,105,255))
    elif style=='aspinall-95k':
        d.polygon([(0,cy),(45,42),(w-38,28),(w,cy),(w-38,h-28),(45,h-42)],fill=(38,39,42,255),outline=(15,15,15,255))
        for x in range(45,345,32): d.rectangle((x,35,x+12,h-35),fill=(15,16,17,255))
        for x in [375,410,445,610,645,680]: d.rectangle((x,32,x+12,h-32),fill=(190,25,32,255))
        for x in range(485,585,24): d.rectangle((x,42,x+12,h-42),fill=(150,153,151,255))
        for x in range(710,860,26): d.rectangle((x,38,x+10,h-38),fill=(10,10,10,255))
    elif style=='bunting-95k':
        d.polygon([(0,cy),(55,45),(w-50,34),(w,cy),(w-50,h-34),(55,h-45)],fill=(170,172,170,255),outline=(65,65,65,255))
        for x in range(85,365,26):
            d.rectangle((x,43,x+13,h-43),fill=(115,20,38,255)); d.line((x+4,47,x+4,h-47),fill=(205,82,99,220),width=2)
        d.rectangle((390,38,515,h-38),fill=(105,108,108,255))
        for x in range(540,850,28):
            d.rectangle((x,36,x+13,h-36),fill=(125,22,40,255)); d.rectangle((x+4,42,x+8,h-42),fill=(210,85,100,255))
    elif style=='mvg-signature':
        d.rounded_rectangle((2,36,w-3,h-37),radius=34,fill=(112,112,108,255),outline=(48,48,47,255),width=3)
        for x in range(35,875,34):
            d.rectangle((x,36,x+12,h-37),fill=(68,68,66,255)); d.line((x+4,41,x+4,h-42),fill=(165,165,157,180),width=2)
        for x in [285,570]: d.rectangle((x,36,x+20,h-37),fill=(210,210,203,255))
        d.text((420,69),'MVG',font=font(30,True),fill=(70,70,67,255))
    elif style=='humphries-prestige':
        # torpedo shape: thicker at front, narrowing rear
        pts=[(0,cy),(55,30),(330,24),(650,42),(850,57),(900,cy),(850,h-57),(650,h-42),(330,h-24),(55,h-30)]
        d.polygon(pts,fill=(65,66,67,255),outline=(20,20,20,255))
        for x in range(70,820,36):
            top=35 if x<400 else 48; bot=h-top
            d.rectangle((x,top,x+13,bot),fill=(22,23,24,255))
            d.line((x+3,top+3,x+3,bot-3),fill=(180,180,175,150),width=2)
        for x in [470,505,540]: d.rectangle((x,44,x+8,h-44),fill=(205,154,51,255))
        d.text((596,69),'#1',font=font(30,True),fill=(213,164,60,255))
    return im

def draw_shaft(style):
    w,h=520,120; im=canvas(w,h); d=ImageDraw.Draw(im); cy=h//2
    if style=='clemens-g2':
        d.rounded_rectangle((2,33,w-3,h-34),radius=24,fill=(241,199,20,255),outline=(55,55,55,255),width=2)
        d.rectangle((0,33,65,h-34),fill=(65,65,65,255)); d.text((180,43),'PRO GRIP',font=font(24,True),fill=(25,25,25,255))
    elif style=='mvg-signature':
        d.rounded_rectangle((2,35,w-3,h-36),radius=21,fill=(25,27,30,255),outline=(5,5,5,255),width=2)
        d.text((188,43),'VECTA',font=font(25,True),fill=(220,220,220,255))
    elif style=='humphries-prestige':
        d.rounded_rectangle((2,35,w-3,h-36),radius=21,fill=(20,21,23,255),outline=(5,5,5,255),width=2)
        d.text((130,43),'COOLHAND',font=font(24,True),fill=(211,159,55,255))
    else:
        d.rounded_rectangle((2,35,w-3,h-36),radius=21,fill=(35,35,37,255),outline=(5,5,5,255),width=2)
    return im

def flight_polygon(profile,w,h):
    pts=[]
    for x,y in profile:
        pts.append((int(x*(w-1)), int(h/2-y*(h*.46))))
    return pts

def draw_flight(style,shape='No.6'):
    prof=NO6 if shape=='No.6' else NO2
    w,h=560,440; im=canvas(w,h); d=ImageDraw.Draw(im); poly=flight_polygon(prof,w,h)
    if style=='clemens-g2':
        d.polygon(poly,fill=(250,250,246,255),outline=(40,40,40,255),width=3)
        # German color wedges, visually based on the product image.
        d.polygon([(85,120),(350,58),(500,86),(220,205)],fill=(35,35,35,255))
        d.polygon([(105,215),(510,110),(535,174),(135,280)],fill=(218,32,42,255))
        d.polygon([(120,300),(520,195),(525,300),(180,365)],fill=(245,207,26,255))
        d.text((315,176),'GIANT',font=font(30,True),fill=(35,35,35,255))
    elif style=='clemens-95k':
        d.polygon(poly,fill=(202,25,31,205),outline=(150,15,20,255),width=3)
        d.line((80,220,520,220),fill=(245,80,80,120),width=4)
        d.text((250,145),'CLEMENS',font=font(22,True),fill=(120,10,15,210))
    elif style=='cross-95k':
        d.polygon(poly,fill=(245,248,246,210),outline=(210,215,210,255),width=3)
        for x in range(195,470,38): d.line((x,135,x+40,170),fill=(0,157,166,230),width=6)
        d.text((320,205),'VOLTAGE',font=font(18,True),fill=(0,142,151,235))
    elif style=='aspinall-95k':
        d.polygon(poly,fill=(190,24,39,170),outline=(148,17,29,255),width=3)
        d.polygon([(160,85),(470,85),(440,250),(190,245)],fill=(210,58,69,100))
        d.text((315,155),'ASP',font=font(34,True),fill=(95,13,20,220))
    elif style=='bunting-95k':
        d.polygon(poly,fill=(30,31,32,210),outline=(10,10,10,255),width=3)
        d.polygon([(100,105),(480,105),(455,190),(125,190)],fill=(220,170,70,175))
        d.text((310,135),'BULLET',font=font(24,True),fill=(140,83,25,255))
        d.polygon([(105,205),(480,205),(455,330),(125,330)],fill=(245,245,245,90))
    elif style=='mvg-signature':
        d.polygon(poly,fill=(18,20,22,255),outline=(5,5,5,255),width=3)
        for y in range(85,350,22): d.line((130,y,500,y-55),fill=(90,95,95,160),width=2)
        d.ellipse((170,125,225,180),outline=(201,228,29,255),width=4); d.text((182,137),'M',font=font(24,True),fill=(201,228,29,255))
        d.line((125,286,500,170),fill=(201,228,29,255),width=4)
    elif style=='humphries-prestige':
        d.polygon(poly,fill=(18,18,19,255),outline=(4,4,4,255),width=3)
        # geometric gold/white chevrons
        d.polygon([(250,70),(315,70),(510,180),(510,225),(315,120)],fill=(226,190,112,255))
        d.polygon([(190,80),(225,75),(505,245),(505,282),(220,120)],fill=(230,230,224,255))
        d.text((130,150),'COOLHAND',font=font(22,True),fill=(214,164,65,255)); d.text((160,177),'LUKE',font=font(22,True),fill=(214,164,65,255))
    # clip all artwork to flight polygon
    mask=Image.new('L',(w,h),0); md=ImageDraw.Draw(mask); md.polygon(poly,fill=255)
    a=im.getchannel('A'); import PIL.ImageChops as IC; im.putalpha(IC.multiply(a,mask))
    return im

def backface(front):
    # Unknown reverse faces keep only low-frequency colour identity. This avoids the
    # V1.3 failure where readable front-side logos/text reappeared on Plane B.
    base=front.convert('RGBA')
    w,h=base.size
    sw=max(6,min(18,max(1,w//18))); sh=max(6,min(18,max(1,h//18)))
    low=base.convert('RGB').resize((sw,sh),Image.Resampling.BOX).resize((w,h),Image.Resampling.BILINEAR)
    low=ImageEnhance.Color(low).enhance(.45)
    low=ImageEnhance.Brightness(low).enhance(.68)
    out=low.convert('RGBA')
    out.putalpha(base.getchannel('A'))
    return out

def draw_integrated_shaft(style):
    w,h=500,120; im=canvas(w,h); d=ImageDraw.Draw(im)
    colors={
      'clemens-95k':(35,37,40,255),'cross-95k':(38,39,41,255),'aspinall-95k':(36,37,39,255),'bunting-95k':(128,30,45,255)
    }
    c=colors[style]; d.rounded_rectangle((2,34,w-3,h-35),radius=22,fill=c,outline=(10,10,10,255),width=2)
    for x in range(55,430,42): d.rectangle((x,35,x+10,h-36),fill=(170,170,165,180) if style!='bunting-95k' else (205,125,135,190))
    return im

def save(im,path): path.parent.mkdir(parents=True,exist_ok=True); im.save(path)

def compose_reference(key, integrated, shape, url):
    # Local, clearly labelled reconstruction so source panel remains useful offline.
    p=Image.open(OUT/key/'point.png').convert('RGBA'); b=Image.open(OUT/key/'barrel.png').convert('RGBA')
    rear=Image.open(OUT/key/('rear-shaft.png' if integrated else 'shaft.png')).convert('RGBA')
    fl=Image.open(OUT/key/'flight-plane-a.png').convert('RGBA')
    C=Image.new('RGBA',(1200,420),(248,248,246,255)); d=ImageDraw.Draw(C)
    d.text((24,16),f'{key} · WEB-REFERENCED RECONSTRUCTION',font=font(24,True),fill=(28,32,38,255))
    d.text((24,48),'Nicht das heruntergeladene Herstellerfoto; lokal aus der recherchierten Produktansicht nachgebaut.',font=font(16),fill=(90,95,103,255))
    y=225; x=30
    def place(im,w,h):
        nonlocal x
        z=im.copy(); z.thumbnail((w,h),Image.Resampling.LANCZOS); C.alpha_composite(z,(x,y-z.height//2)); x += z.width-2
    place(p,250,45); place(b,430,90); place(rear,230,65); place(fl,260,180)
    d.text((24,388),url,font=font(13),fill=(75,95,130,255))
    save(C, SRC/f'web-{key}-reconstruction.png')

PLAYERS={
 'clemens-g2': {'style':'clemens-g2','integrated':False,'shape':'No.6','profile':NO6,'url':'https://www.target-darts.co.uk/gabriel-clemens-g2-sp'},
 'clemens-95k': {'style':'clemens-95k','integrated':True,'shape':'No.6','profile':NO6,'url':'https://www.target-darts.co.uk/gabriel-clemens-95k-sp'},
 'cross-95k': {'style':'cross-95k','integrated':True,'shape':'No.6','profile':NO6,'url':'https://www.target-darts.co.uk/rob-cross-95k-sp'},
 'aspinall-95k': {'style':'aspinall-95k','integrated':True,'shape':'No.2','profile':NO2,'url':'https://www.target-darts.co.uk/nathan-aspinall-95k-sp'},
 'bunting-95k': {'style':'bunting-95k','integrated':True,'shape':'No.2','profile':NO2,'url':'https://www.target-darts.co.uk/stephen-bunting-95k-sp'},
 'mvg-signature': {'style':'mvg-signature','integrated':False,'shape':'No.2','profile':NO2,'url':'https://winmau.com/products/mvg-signature-edition'},
 'humphries-prestige': {'style':'humphries-prestige','integrated':False,'shape':'Standard','profile':STD,'url':'https://www.reddragondarts.com/products/luke-humphries-prestige-darts'},
}

def generate():
    meta={}
    for key,s in PLAYERS.items():
        if key in SOURCE_GROUNDED_SPECS:
            meta[key]=_split_source_grounded(key,SOURCE_GROUNDED_SPECS[key])
            continue

        d=OUT/key; d.mkdir(parents=True,exist_ok=True)
        point_black=key in ('aspinall-95k','humphries-prestige')
        point_gold=key in ('cross-95k','bunting-95k')
        p=draw_point(color=(202,163,65,255) if point_gold else (178,180,180,255),black=point_black)
        save(p,d/'point.png')
        save(draw_barrel(s['style']),d/'barrel.png')
        if s['integrated']: save(draw_integrated_shaft(s['style']),d/'rear-shaft.png')
        else: save(draw_shaft(s['style']),d/'shaft.png')
        f=draw_flight(s['style'],s['shape']); save(f,d/'flight-plane-a.png'); save(backface(f),d/'flight-plane-b-approx.png')
        meta[key]={'sourceFile':None,'webReference':s['url'],'flightProfile':s['profile'],'rearIntegrated':s['integrated'],'authoringStatus':'WEB-REFERENCED-RECONSTRUCTION: colors/silhouette/artwork simplified from inspected public product image; not pixel-extracted source.'}
        compose_reference(key,s['integrated'],s['shape'],s['url'])
    return meta

if __name__=='__main__':
    print(json.dumps(generate(),indent=2))
