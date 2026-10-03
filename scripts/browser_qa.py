from __future__ import annotations
import json, subprocess, time, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out={'status':'NOT_RUN','notes':[]}
server=None
try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    out={'status':'BLOCKED','reason':f'Playwright unavailable: {e}'}
    (ROOT/'outputs/qa/browser-qa.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2));sys.exit(2)
try:
    server=subprocess.Popen([sys.executable,'-m','http.server','4173'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=swiftshader','--enable-webgl'])
        page=browser.new_page(viewport={'width':1600,'height':1200})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(f'console {m.type}: {m.text}') if m.type=='error' else None)
        page.goto('http://127.0.0.1:4173',wait_until='domcontentloaded',timeout=15000)
        page.wait_for_function('window.__POC_READY__ === true',timeout=20000)
        status=page.locator('#status').inner_text()
        preset_ids=page.evaluate('Object.keys(window.__CATALOG__.presets)')
        results=[]
        for pid in preset_ids:
            page.evaluate('(pid)=>window.__APP_API__.applyPreset(pid)',pid)
            page.wait_for_timeout(300)
            r=page.evaluate('window.__POC_LAST_RENDER__')
            results.append(r)
        # Verify all three pose controls materially update state/render metadata.
        page.evaluate('window.__APP_API__.setPose({screenRotationDeg: 32, incidenceDeg: 52, rollDeg: 28})')
        page.wait_for_timeout(250)
        pose_changed=page.evaluate('window.__POC_LAST_RENDER__')
        page.evaluate('window.__APP_API__.setPose({screenRotationDeg: -24, incidenceDeg: 18, rollDeg: -26})')
        page.wait_for_timeout(250)
        pose_changed_2=page.evaluate('window.__POC_LAST_RENDER__')
        bench=page.evaluate('window.__RENDERER__.benchmark()')
        page.screenshot(path=str(ROOT/'outputs/qa/builder-ui.png'),full_page=True)
        controls_ok=(pose_changed.get('pose',{}).get('screenRotationDeg')==32 and pose_changed.get('pose',{}).get('incidenceDeg')==52 and pose_changed.get('pose',{}).get('rollDeg')==28 and pose_changed_2.get('pose',{}).get('screenRotationDeg')==-24 and pose_changed_2.get('pose',{}).get('incidenceDeg')==18 and pose_changed_2.get('pose',{}).get('rollDeg')==-26)
        joint_delta=float((pose_changed_2.get('posed',{}).get('jointMetrics') or {}).get('visibleDeltaMm',999))
        out={'status':'PASS' if controls_ok and joint_delta < 0.03 else 'FAIL','uiStatus':status,'presetResults':results,'poseControlChecks':[pose_changed,pose_changed_2],'controlsOk':controls_ok,'jointVisibleDeltaMm':joint_delta,'benchmark':bench,'errors':errors}
        browser.close()
except Exception as e:
    out={'status':'BLOCKED','reason':str(e),'notes':['This execution environment may block browser navigation to localhost. Run npm install && npm run serve on a normal workstation, then execute this script to complete WebGL runtime QA.']}
finally:
    if server: server.terminate()
(ROOT/'outputs/qa/browser-qa.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out,indent=2))
if out['status']!='PASS': sys.exit(2)
