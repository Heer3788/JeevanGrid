"""Verify the compiled frontend and real weather services using the seeded demo."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'test-results'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:4173')
    page.get_by_label('Password',exact=True).fill(os.environ.get('JEEVANGRID_DEMO_PASSWORD','JeevanGridDemo!26'))
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.get_by_role('heading',name='A clearer view of every site.')).to_be_visible(timeout=15000)
    access=page.evaluate("sessionStorage.getItem('jg-access')")
    headers={'Authorization':f'Bearer {access}'}
    def post(path,data):
        r=context.request.post('http://127.0.0.1:4173/api'+path,data=data,headers=headers,timeout=90000)
        assert r.ok,(r.status,r.text())
        return r.json()
    weather=[]
    for mode in ['forecast','historical']:
        r=post('/sites/1/optimization-runs',{'mode':mode,'date':'2025-01-15'})
        assert r['status'] in ['optimal','feasible'],r
        assert len(r['intervals'])==24
        weather.append({'mode':mode,'source':r['weather_source'],'run_id':r['id'],'solve_seconds':r['solve_seconds'],'intervals':24})
    baselines=[]
    for site_id in [1,2,3]:
        r=post(f'/sites/{site_id}/optimization-runs',{'mode':'simulated'})
        assert r['status'] in ['optimal','feasible']
        assert r['solve_seconds']<5
        baselines.append({'site_id':site_id,'run_id':r['id'],'solve_seconds':r['solve_seconds'],'critical_served_pct':r['metrics']['critical_load_served_pct']})
    pack=post('/portfolio/resilience-runs',{})
    assert len(pack['results'])==18
    page.reload()
    expect(page.get_by_role('heading',name='Site reliability',exact=True)).to_be_visible(timeout=15000)
    page.get_by_role('checkbox',name='Compare Leporiang · study reference',exact=True).check()
    page.get_by_role('checkbox',name='Compare Leporiang area · compact demo',exact=True).check()
    expect(page.get_by_role('heading',name='Selected sites',exact=True)).to_be_visible()
    expect(page.get_by_role('alert')).to_have_count(0)
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(2000)  # Let Recharts finish its entry animation before capture.
    page.screenshot(path=str(OUT/'final-portfolio.png'),full_page=True)
    page.get_by_role('link',name='Leporiang area · compact demo',exact=True).click()
    expect(page.get_by_role('heading',name='24-hour energy plan')).to_be_visible(timeout=15000)
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT/'final-operating-plan.png'),full_page=True)
    page.get_by_role('button',name='What if?',exact=True).click()
    page.get_by_role('button',name='Generator outage',exact=False).click()
    page.get_by_label('Outage start (local hour)').fill('0')
    page.get_by_label('Outage end (local hour)').fill('24')
    page.get_by_role('button',name='Run & save simulation').click()
    expect(page.get_by_role('heading',name='Baseline vs. generator outage')).to_be_visible(timeout=15000)
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT/'final-simulation.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Operating plan',exact=True).click()
    page.evaluate('window.scrollTo(0,0)')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT/'final-mobile.png'),full_page=True)
    page.get_by_role('link',name='Account',exact=True).click()
    page.get_by_role('button',name='Sign out of this account',exact=True).click()
    expect(page.get_by_role('heading',name='Welcome back.')).to_be_visible(timeout=15000)
    assert not errors,errors
    result={'production_browser':'passed','console_errors':errors,'weather':weather,'baselines':baselines,'resilience_runs':18}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    browser.close()
