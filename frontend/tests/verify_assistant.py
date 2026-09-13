"""Browser acceptance: comparison, exports, scoped chat, restoration and keyboard/mobile.
Creates one labeled simulated plan-and-report workflow on the existing Dharnai demo.
No model calls are fabricated; missing-key behavior is explicitly tested.
"""
import json,os,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path(__file__).resolve().parent.parent/'test-results';OUT.mkdir(exist_ok=True)
URL=os.environ.get('JG_TEST_URL','http://127.0.0.1:5173')

def fetch(page,path,body=None):
    return page.evaluate('''async ([path,body])=>{const r=await fetch('/api'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',Authorization:'Bearer '+sessionStorage.getItem('jg-access')},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()}}''',[path,body])

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL+'/login');page.get_by_role('button',name='Agency administrator',exact=False).click()
    expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=20000)
    for name in ['Rewana · village demo','Bijua · enterprise demo']:page.get_by_role('checkbox',name='Compare '+name,exact=True).check()
    page.get_by_role('button',name='Open detailed comparison').click()
    dialog=page.get_by_role('dialog',name='Compare energy sites & plans');expect(dialog).to_be_visible()
    expect(dialog.get_by_role('columnheader',name='Daily measure',exact=True)).to_be_visible(timeout=20000)
    expect(dialog.get_by_role('rowheader',name='Margin above reserve',exact=False)).to_be_visible()
    dialog.get_by_label('Comparison measure').select_option('diesel_l_per_kwh')
    page.screenshot(path=str(OUT/'assistant-comparison.png'))
    page.keyboard.press('Escape');expect(dialog).to_have_count(0)
    page.get_by_role('button',name='Open JeevanGrid assistant').click()
    drawer=page.get_by_role('dialog',name='JeevanGrid assistant',exact=True);expect(drawer).to_be_visible()
    for _ in range(10):
        page.keyboard.press('Tab');assert drawer.evaluate('(n)=>n.contains(document.activeElement)')
    cfg=fetch(page,'/assistant/config')['data']
    if not cfg['configured']:
        drawer.get_by_role('textbox',name='Message JeevanGrid assistant').fill('Which sites need review?')
        drawer.get_by_role('button',name='Send',exact=True).click()
        expect(drawer.get_by_text('Provider unavailable',exact=False)).to_be_visible(timeout=20000)
    page.keyboard.press('Escape')
    site=next(s for s in fetch(page,'/sites')['data'] if s['name']=='Dharnai · village demo')
    c=fetch(page,'/assistant/conversations',{'site_id':site['id']})['data']
    started=fetch(page,f'/assistant/conversations/{c["id"]}/messages',{'text':'Browser acceptance: generate a simulated plan and PDF report.','workflow':'plan_and_report','inputs':{'mode':'simulated','format':'pdf'},'request_key':'browser-'+str(time.time_ns())})
    assert started['status']==202,started
    job_id=started['data']['workflow_id'];page.goto(URL+'/assistant?history=1')
    page.get_by_role('button',name='Browser acceptance: generate a simulated plan and PDF report.',exact=False).first.click()
    expect(page.get_by_text('Verified completion',exact=False)).to_be_visible(timeout=120000)
    job=fetch(page,f'/assistant/workflows/{job_id}')['data'];assert job['status']=='succeeded',job
    assert job['result']['run']['intervals'] and len(job['result']['checks'])==6
    with page.expect_download() as download:
        page.get_by_role('button',name='Download PDF · report',exact=False).click()
    artifact=OUT/'assistant-report.pdf';download.value.save_as(str(artifact));assert artifact.read_bytes().startswith(b'%PDF-')
    page.screenshot(path=str(OUT/'assistant-history.png'),full_page=True)
    page.reload();page.get_by_role('button',name='Browser acceptance: generate a simulated plan and PDF report.',exact=False).first.click()
    expect(page.get_by_text('Verified completion',exact=False)).to_be_visible(timeout=10000)
    page.goto(f'{URL}/sites/{site["id"]}')
    expect(page.get_by_role('heading',name=site['name'],exact=True)).to_be_visible(timeout=15000)
    existing=fetch(page,f'/sites/{site["id"]}/live')['data']['session']
    if not existing or not existing['active']:
        page.get_by_role('tab',name='2 Test plan',exact=True).click()
        page.get_by_role('button',name='Live replay',exact=True).click()
        page.get_by_label('Clock speed',exact=True).select_option('10')
        page.get_by_role('button',name='Start replay',exact=True).click()
        expect(page.get_by_role('heading',name='Is demand being supplied?')).to_be_visible(timeout=30000)
        page.get_by_role('button',name='Cloud cover',exact=True).click()
        page.get_by_role('button',name='Battery at 25%',exact=True).click()
        page.wait_for_timeout(4500)
        page.get_by_role('button',name='Pause replay',exact=True).click()
        expect(page.get_by_role('button',name='Start replay',exact=True)).to_be_visible(timeout=15000)
        replay=fetch(page,f'/sites/{site["id"]}/live')['data']['session']
        assert not replay['active'] and replay['history_complete'] and replay['sample_count']>0
        assert replay['modifiers']['solar_multiplier']==.25
        points=page.evaluate("async rows=>(await import('/src/ReplayChart.jsx')).intervalPoints(rows)",replay['samples'])
        assert points[0]['time']==page.evaluate('t=>Date.parse(t)',replay['samples'][0]['interval_start'])
        assert points[-1]['time']==page.evaluate('t=>Date.parse(t)',replay['samples'][-1]['timestamp'])
        exported=fetch(page,'/reports',{'kind':'replay','session_id':replay['id'],'format':'json'})['data']
        for _ in range(20):
            status=fetch(page,f'/reports/{exported["id"]}')['data']
            if status['status']!='queued':break
            page.wait_for_timeout(1000)
        assert status['status']=='ready',status
        evidence=fetch(page,f'/reports/{exported["id"]}/download')['data']
        assert evidence['verification']['passed'] and len(evidence['session']['samples'])==replay['sample_count']
        assert any(e['kind']=='low_battery' for e in evidence['session']['events'])
        page.screenshot(path=str(OUT/'assistant-replay.png'))
    page.get_by_role('button',name='Open JeevanGrid assistant').click()
    drawer=page.get_by_role('dialog',name='JeevanGrid assistant',exact=True)
    expect(drawer.get_by_text(f'Site #{site["id"]} only')).to_be_visible()
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500);page.screenshot(path=str(OUT/'assistant-mobile.png'))
    bounds=drawer.bounding_box();assert bounds['x']>=0 and bounds['width']<=391
    drawer.get_by_role('textbox',name='Message JeevanGrid assistant').fill('Explain reserve')
    expect(drawer.get_by_role('button',name='Send',exact=True)).to_be_visible()
    page.keyboard.press('Escape');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors,errors
    (OUT/'assistant-acceptance.json').write_text(json.dumps({'workflow_id':job_id,'run_id':job['result']['run']['id'],'artifact_id':job['result']['artifact_id'],'checks':['comparison window','all normalized metrics','keyboard drawer focus','missing-key honesty','verified plan-and-report workflow','PDF download','conversation restoration','site scope','mobile drawer fit'],'model_configured':cfg['configured']},indent=2))
    print('Assistant browser acceptance passed; workflow',job_id,'plan',job['result']['run']['id'],flush=True)
    browser.close()
