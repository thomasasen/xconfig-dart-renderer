from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import json, math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'components'
SRC = ROOT / 'assets' / 'source'
OUT.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

# These are deliberately WEB-REFERENCED RECONSTRUCTIONS, not downloaded source pixels.
# They are locally authored from inspected product images so the POC stays self-contained.
# Physical dimensions are kept separately in catalog.json and are not inferred from these drawings.

NO6 = [[0.00,0.00],[0.08,0.30],[0.22,0.90],[0.68,1.00],[0.94,0.72],[1.00,0.35],[1.00,-0.35],[0.94,-0.72],[0.68,-1.00],[0.22,-0.90],[0.08,-0.30]]
NO2 = [[0.00,0.00],[0.06,0.34],[0.18,0.96],[0.60,1.00],[0.90,0.82],[1.00,0.45],[1.00,-0.45],[0.90,-0.82],[0.60,-1.00],[0.18,-0.96],[0.06,-0.34]]
STD = NO2

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
    x=ImageEnhance.Color(front).enhance(.35); x=ImageEnhance.Brightness(x).enhance(.62)
    x.putalpha(front.getchannel('A')); return x

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
        d=OUT/key; d.mkdir(parents=True,exist_ok=True)
        point_black=key in ('clemens-95k','aspinall-95k','humphries-prestige')
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
