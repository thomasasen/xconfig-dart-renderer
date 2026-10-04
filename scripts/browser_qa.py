from __future__ import annotations
import json, subprocess, time, sys, re, base64
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'qa'
OUT.mkdir(parents=True,exist_ok=True)
CAT=json.loads((ROOT/'data'/'catalog.json').read_text())
REVIEW_PRESETS=tuple(CAT['presets'].keys())
out={'status':'NOT_RUN','notes':[]}
server=None

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    out={'status':'BLOCKED','reason':f'Playwright unavailable: {e}'}
    (OUT/'browser-qa.json').write_text(json.dumps(out,indent=2),encoding='utf8')
    print(json.dumps(out,indent=2));sys.exit(2)

def canvas_image(page, selector):
    data_url=page.evaluate("(sel)=>document.querySelector(sel).toDataURL('image/png')",selector)
    return Image.open(BytesIO(base64.b64decode(data_url.split(',',1)[1]))).convert('RGBA')

def wait_render(page,pid,timeout=15000):
    page.wait_for_function(
        """pid => window.__POC_LAST_RENDER__ && window.__POC_LAST_RENDER__.presetId === pid""",
        arg=pid,
        timeout=timeout,
    )
    return page.evaluate('window.__POC_LAST_RENDER__')

def save_seam_zoom(page,pid,render_meta):
    image=canvas_image(page,'#orthogonal').convert('RGB')
    joint=(render_meta.get('reference') or {}).get('jointSprite') or {}
    jx=float(joint.get('x',0)); jy=float(joint.get('y',212))
    sx=image.width/789.0; sy=image.height/331.0
    cx=jx*sx; cy=jy*sy
    half_w=max(24,int(38*sx)); half_h=max(18,int(24*sy))
    x0=max(0,int(cx-half_w)); x1=min(image.width,int(cx+half_w))
    y0=max(0,int(cy-half_h)); y1=min(image.height,int(cy+half_h))
    crop=image.crop((x0,y0,x1,y1))
    scale=max(4,min(10,round(720/max(1,crop.width))))
    crop=crop.resize((crop.width*scale,crop.height*scale),Image.Resampling.NEAREST)
    canvas=Image.new('RGB',(crop.width,crop.height+34),(20,23,29))
    canvas.paste(crop,(0,34))
    draw=ImageDraw.Draw(canvas)
    metrics=(render_meta.get('reference') or {}).get('jointMetrics') or {}
    draw.text(
        (8,9),
        f"{pid} | visibleDelta={float(metrics.get('visibleDeltaMm',999)):.6f} mm | "
        f"slopeDelta={float(metrics.get('joinSlopeDeltaMmPerMm',999)):.6f}",
        fill='white',
    )
    canvas.save(OUT/f'seam-{pid}.png')


def _panel(im,title,width=789,height=365):
    canvas=Image.new('RGB',(width,height),(18,22,29))
    src=im.convert('RGBA')
    src.thumbnail((width-20,height-46),Image.Resampling.LANCZOS)
    # Composite transparency on the dark QA background.
    bg=Image.new('RGBA',src.size,(18,22,29,255)); bg.alpha_composite(src)
    canvas.paste(bg.convert('RGB'),((width-src.width)//2,36))
    ImageDraw.Draw(canvas).text((10,10),title,fill='white')
    return canvas


def _foreground_mask(im):
    rgba=np.asarray(im.convert('RGBA'))
    alpha=rgba[:,:,3]
    if float((alpha<250).mean())>.01:
        return alpha>20
    rgb=rgba[:,:,:3].astype(np.int16)
    band=max(2,rgb.shape[0]//12)
    sample=np.concatenate([rgb[:band,:],rgb[-band:,:]],axis=0)
    bg=np.median(sample.reshape(-1,3),axis=0)
    dist=np.linalg.norm(rgb-bg[None,None,:],axis=2)
    return dist>18

def _silhouette_metrics(im):
    mask=_foreground_mask(im)
    ys,xs=np.where(mask)
    if len(xs)<20:
        return {'valid':False}
    x0,x1=int(xs.min()),int(xs.max()); y0,y1=int(ys.min()),int(ys.max())
    crop=mask[y0:y1+1,x0:x1+1]
    h,w=crop.shape
    spans=[]
    for x in range(w):
        yy=np.where(crop[:,x])[0]
        spans.append(int(yy.max()-yy.min()+1) if len(yy) else 0)
    body_lo=max(0,int(w*.18)); body_hi=max(body_lo+1,int(w*.62))
    body_vals=[v for v in spans[body_lo:body_hi] if v>0]
    body=float(np.median(body_vals)) if body_vals else 1.0
    max_span=float(max(spans) or 1)
    flight_cols=[i for i,v in enumerate(spans) if v>=max(body*1.65,body+4)]
    flight_fraction=((max(flight_cols)-min(flight_cols)+1)/w) if flight_cols else 0.0
    return {
        'valid':True,
        'bboxAspect':round(w/max(1,h),4),
        'flightHeightToBody':round(max_span/max(1.0,body),4),
        'flightLengthFraction':round(flight_fraction,4),
        'bodySpanPx':round(body,3),
    }

def _visual_delta(source,rendered):
    a=_silhouette_metrics(source); b=_silhouette_metrics(rendered)
    if not a.get('valid') or not b.get('valid'):
        return {'passed':False,'source':a,'rendered':b,'reason':'foreground extraction failed'}
    aspect_err=abs(b['bboxAspect']-a['bboxAspect'])/max(.1,a['bboxAspect'])
    height_err=abs(b['flightHeightToBody']-a['flightHeightToBody'])/max(.1,a['flightHeightToBody'])
    length_err=abs(b['flightLengthFraction']-a['flightLengthFraction'])
    passed=aspect_err<=.40 and height_err<=.42 and length_err<=.22
    return {
        'passed':passed,'source':a,'rendered':b,
        'bboxAspectRelativeError':round(aspect_err,4),
        'flightHeightRelativeError':round(height_err,4),
        'flightLengthFractionAbsError':round(length_err,4),
        'limits':{'bboxAspectRelativeError':.40,'flightHeightRelativeError':.42,'flightLengthFractionAbsError':.22},
    }

def save_runtime_review(page,pid):
    preset=CAT['presets'][pid]
    source=Image.open(ROOT/preset.get('comparisonSourceImage',preset['sourceImage']).replace('./','')).convert('RGBA')
    orthogonal=canvas_image(page,'#orthogonal')
    posed=canvas_image(page,'#posed')
    c=CAT['components']
    tail=c['rearSystems'][preset['rearSystemId']] if preset.get('rearSystemId') else c['flights'][preset['flightId']]
    titles=[
        f'Original/source · {preset["name"]}',
        f'Source-calibrated runtime · roll={preset.get("sourceReferencePose",{}).get("rollDeg",40)}° · {tail.get("flightExtractionMode","DIRECT_SOURCE_FACE")}',
        f'Posed runtime · Plane B {tail.get("planeBProvenance",tail.get("faceEvidence",{}).get("planeB"))}',
    ]
    cards=[_panel(source,titles[0]),_panel(orthogonal,titles[1]),_panel(posed,titles[2])]
    sheet=Image.new('RGB',(789*3,365),(10,13,18))
    for i,card in enumerate(cards): sheet.paste(card,(i*789,0))
    sheet.save(OUT/f'runtime-{pid}-source-vs-render.png')

try:
    server=subprocess.Popen(
        [sys.executable,'-m','http.server','4173'],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    with sync_playwright() as p:
        browser=p.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=swiftshader','--enable-webgl']
        )
        page=browser.new_page(viewport={'width':1600,'height':1200})
        page_errors=[]
        console_errors=[]
        page.on('pageerror',lambda e:page_errors.append(str(e)))
        page.on(
            'console',
            lambda m: console_errors.append(m.text)
            if m.type=='error' and 'WebGL context was lost' not in m.text else None
        )
        page.goto('http://127.0.0.1:4173',wait_until='domcontentloaded',timeout=20000)
        page.wait_for_function('window.__POC_READY__ === true',timeout=30000)
        status=page.locator('#status').inner_text()

        preset_ids=page.evaluate('Object.keys(window.__CATALOG__.presets)')
        visible_names=page.evaluate('Object.fromEntries(Object.entries(window.__CATALOG__.presets).map(([id,p])=>[id,p.name]))')
        weight_re=re.compile(r'\b\d+(?:[.,]\d+)?\s*g\b',re.I)
        weight_label_violations={pid:name for pid,name in visible_names.items() if weight_re.search(name or '')}
        labels_ok=not weight_label_violations
        results=[]
        seam_results={}
        max_tip=0.0
        max_visible_delta=0.0
        max_slope_delta=0.0
        max_shaft_root_delta=0.0
        self_tests=[]
        visual_checks=[]

        for pid in preset_ids:
            page.evaluate('(pid)=>window.__APP_API__.applyPreset(pid)',pid)
            render=wait_render(page,pid)
            posed=render.get('posed') or {}
            ortho=render.get('reference') or {}
            metrics=posed.get('jointMetrics') or {}
            tip=max(
                abs(float(posed.get('tipDriftPx',0))),
                abs(float(ortho.get('tipDriftPx',0))),
                abs(float((render.get('screenPreview') or {}).get('pivotDriftPx',0))),
            )
            visible=abs(float(metrics.get('visibleDeltaMm',0)))
            slope=abs(float(metrics.get('joinSlopeDeltaMmPerMm',0)))
            root_delta=abs(float(metrics.get('shaftRootVisibleDeltaMm',0)))
            max_tip=max(max_tip,tip)
            max_visible_delta=max(max_visible_delta,visible)
            max_slope_delta=max(max_slope_delta,slope)
            max_shaft_root_delta=max(max_shaft_root_delta,root_delta)
            self_test=page.evaluate('window.__RENDERER__.selfTest()')
            self_tests.append({'presetId':pid,**self_test})
            preset=CAT['presets'][pid]
            source_path=preset.get('comparisonSourceImage',preset['sourceImage']).replace('./','')
            source_image=Image.open(ROOT/source_path).convert('RGBA')
            reference_image=canvas_image(page,'#orthogonal')
            visual=_visual_delta(source_image,reference_image)
            visual_checks.append({'presetId':pid,**visual})
            results.append({
                'presetId':pid,
                'visibleName':visible_names.get(pid),
                'tipDriftPx':tip,
                'visibleDeltaMm':visible,
                'joinSlopeDeltaMmPerMm':slope,
                'shaftRootVisibleDeltaMm':root_delta,
                'rootPresent':bool(metrics.get('rootPresent')),
                'selfTestPassed':bool(self_test.get('passed')),
                'sourceVisualPassed':bool(visual.get('passed')),
                'sourceVisual':visual,
            })
            if pid in REVIEW_PRESETS:
                save_runtime_review(page,pid)
            if pid in ('clemens-g2-23','clemens-95k-23'):
                seam_results[pid]=render
                save_seam_zoom(page,pid,render)

        # Verify all three independent pose controls update final render metadata.
        page.evaluate('window.__APP_API__.setPose({screenRotationDeg: 32, incidenceDeg: 52, rollDeg: 28})')
        page.wait_for_timeout(300)
        pose_changed=page.evaluate('window.__POC_LAST_RENDER__')
        page.evaluate('window.__APP_API__.setPose({screenRotationDeg: -24, incidenceDeg: 18, rollDeg: -26})')
        page.wait_for_timeout(300)
        pose_changed_2=page.evaluate('window.__POC_LAST_RENDER__')
        controls_ok=(
            pose_changed.get('pose',{}).get('screenRotationDeg')==32 and
            pose_changed.get('pose',{}).get('incidenceDeg')==52 and
            pose_changed.get('pose',{}).get('rollDeg')==28 and
            pose_changed_2.get('pose',{}).get('screenRotationDeg')==-24 and
            pose_changed_2.get('pose',{}).get('incidenceDeg')==18 and
            pose_changed_2.get('pose',{}).get('rollDeg')==-26
        )

        bench=page.evaluate('window.__RENDERER__.benchmark()')

        # Explicit WebGL context-loss lifecycle test. We require one loss event, one
        # restore event and a successful render/self-test afterwards.
        before=page.evaluate('window.__RENDERER__.contextStats()')
        loss_request=page.evaluate('window.__RENDERER__.simulateContextLoss()')
        context_ok=True
        after=before
        post_restore_self=None
        if loss_request.get('supported'):
            page.wait_for_function(
                '(before)=>window.__RENDERER__.contextStats().lost > before.lost',
                arg=before,
                timeout=4000,
            )
            page.wait_for_function(
                '(before)=>window.__RENDERER__.contextStats().restored > before.restored && window.__RENDERER__.invalid === false',
                arg=before,
                timeout=10000,
            )
            after=page.evaluate('window.__RENDERER__.contextStats()')
            page.evaluate('window.__APP_API__.renderAll()')
            page.wait_for_timeout(500)
            post_restore_self=page.evaluate('window.__RENDERER__.selfTest()')
            context_ok=(
                after.get('lost',0)>before.get('lost',0) and
                after.get('restored',0)>before.get('restored',0) and
                after.get('invalid') is False and
                bool(post_restore_self.get('passed'))
            )

        page.screenshot(path=str(OUT/'builder-ui.png'),full_page=True)

        seam_ok=all(
            abs(float(((m.get('reference') or {}).get('jointMetrics') or {}).get('visibleDeltaMm',999))) < 1e-8 and
            abs(float(((m.get('reference') or {}).get('jointMetrics') or {}).get('joinSlopeDeltaMmPerMm',999))) < 1e-8
            for m in seam_results.values()
        ) and len(seam_results)==2
        all_self_tests=all(bool(item.get('passed')) for item in self_tests)
        all_visual_checks=all(bool(item.get('passed')) for item in visual_checks)
        no_js_errors=not page_errors and not console_errors

        passed=(
            controls_ok and
            context_ok and
            seam_ok and
            labels_ok and
            all_self_tests and
            all_visual_checks and
            no_js_errors and
            max_tip < 1e-8 and
            max_visible_delta < 1e-8 and
            max_shaft_root_delta < 1e-8 and
            max_slope_delta < 1e-8
        )

        out={
            'status':'PASS' if passed else 'FAIL',
            'uiStatus':status,
            'presetCount':len(preset_ids),
            'presetResults':results,
            'maxTipDriftPx':max_tip,
            'maxJointVisibleDeltaMm':max_visible_delta,
            'maxJoinSlopeDeltaMmPerMm':max_slope_delta,
            'maxShaftRootVisibleDeltaMm':max_shaft_root_delta,
            'poseControlChecks':[pose_changed,pose_changed_2],
            'controlsOk':controls_ok,
            'seamOk':seam_ok,
            'labelsOk':labels_ok,
            'weightLabelViolations':weight_label_violations,
            'runtimeReviewPresets':list(REVIEW_PRESETS),
            'contextLoss':{
                'request':loss_request,
                'before':before,
                'after':after,
                'postRestoreSelfTest':post_restore_self,
                'passed':context_ok,
            },
            'allSelfTestsPassed':all_self_tests,
            'allSourceVisualChecksPassed':all_visual_checks,
            'sourceVisualChecks':visual_checks,
            'benchmark':bench,
            'pageErrors':page_errors,
            'consoleErrors':console_errors,
        }
        browser.close()
except Exception as e:
    out={
        'status':'FAIL',
        'reason':str(e),
        'notes':['Browser/WebGL QA is required for V1.3 and may not silently degrade to a skipped check.'],
    }
finally:
    if server:
        server.terminate()
        try: server.wait(timeout=3)
        except Exception: server.kill()

(OUT/'browser-qa.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out,indent=2))
if out['status']!='PASS':
    sys.exit(2)
