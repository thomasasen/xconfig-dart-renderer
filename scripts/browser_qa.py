from __future__ import annotations
import json, subprocess, time, sys
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'qa'
OUT.mkdir(parents=True,exist_ok=True)
out={'status':'NOT_RUN','notes':[]}
server=None

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    out={'status':'BLOCKED','reason':f'Playwright unavailable: {e}'}
    (OUT/'browser-qa.json').write_text(json.dumps(out,indent=2),encoding='utf8')
    print(json.dumps(out,indent=2));sys.exit(2)

def wait_render(page,pid,timeout=15000):
    page.wait_for_function(
        """pid => window.__POC_LAST_RENDER__ && window.__POC_LAST_RENDER__.presetId === pid""",
        pid,
        timeout=timeout,
    )
    return page.evaluate('window.__POC_LAST_RENDER__')

def save_seam_zoom(page,pid,render_meta):
    raw=page.locator('#orthogonal').screenshot(type='png')
    image=Image.open(BytesIO(raw)).convert('RGB')
    joint=(render_meta.get('ortho') or {}).get('jointSprite') or {}
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
    metrics=(render_meta.get('ortho') or {}).get('jointMetrics') or {}
    draw.text(
        (8,9),
        f"{pid} | visibleDelta={float(metrics.get('visibleDeltaMm',999)):.6f} mm | "
        f"slopeDelta={float(metrics.get('joinSlopeDeltaMmPerMm',999)):.6f}",
        fill='white',
    )
    canvas.save(OUT/f'seam-{pid}.png')

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
        results=[]
        seam_results={}
        max_tip=0.0
        max_visible_delta=0.0
        max_slope_delta=0.0
        self_tests=[]

        for pid in preset_ids:
            page.evaluate('(pid)=>window.__APP_API__.applyPreset(pid)',pid)
            render=wait_render(page,pid)
            posed=render.get('posed') or {}
            ortho=render.get('ortho') or {}
            metrics=posed.get('jointMetrics') or {}
            tip=max(
                abs(float(posed.get('tipDriftPx',0))),
                abs(float(ortho.get('tipDriftPx',0))),
                abs(float((render.get('screenPreview') or {}).get('pivotDriftPx',0))),
            )
            visible=abs(float(metrics.get('visibleDeltaMm',0)))
            slope=abs(float(metrics.get('joinSlopeDeltaMmPerMm',0)))
            max_tip=max(max_tip,tip)
            max_visible_delta=max(max_visible_delta,visible)
            max_slope_delta=max(max_slope_delta,slope)
            self_test=page.evaluate('window.__RENDERER__.selfTest()')
            self_tests.append({'presetId':pid,**self_test})
            results.append({
                'presetId':pid,
                'tipDriftPx':tip,
                'visibleDeltaMm':visible,
                'joinSlopeDeltaMmPerMm':slope,
                'selfTestPassed':bool(self_test.get('passed')),
            })
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
                before,
                timeout=4000,
            )
            page.wait_for_function(
                '(before)=>window.__RENDERER__.contextStats().restored > before.restored && window.__RENDERER__.invalid === false',
                before,
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
            abs(float(((m.get('ortho') or {}).get('jointMetrics') or {}).get('visibleDeltaMm',999))) < 1e-8 and
            abs(float(((m.get('ortho') or {}).get('jointMetrics') or {}).get('joinSlopeDeltaMmPerMm',999))) < 1e-8
            for m in seam_results.values()
        ) and len(seam_results)==2
        all_self_tests=all(bool(item.get('passed')) for item in self_tests)
        no_js_errors=not page_errors and not console_errors

        passed=(
            controls_ok and
            context_ok and
            seam_ok and
            all_self_tests and
            no_js_errors and
            max_tip < 1e-8 and
            max_visible_delta < 1e-8 and
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
            'poseControlChecks':[pose_changed,pose_changed_2],
            'controlsOk':controls_ok,
            'seamOk':seam_ok,
            'contextLoss':{
                'request':loss_request,
                'before':before,
                'after':after,
                'postRestoreSelfTest':post_restore_self,
                'passed':context_ok,
            },
            'allSelfTestsPassed':all_self_tests,
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
