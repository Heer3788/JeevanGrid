"""Integration smoke test against the local seeded demo. Uses a dedicated test site."""
import json
import os
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

OUT=Path(__file__).parent/'test-results'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:5173')
    page.get_by_label('Password',exact=True).fill(os.environ.get('JEEVANGRID_DEMO_PASSWORD','JeevanGridDemo!26'))
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.get_by_role('heading',name='A clearer view of every site.')).to_be_visible(timeout=15000)
    expect(page.get_by_role('link',name='Leporiang · study reference')).to_be_visible(timeout=15000)
    page.screenshot(path=str(OUT/'portfolio.png'),full_page=True)
    page.get_by_role('link',name='Leporiang · study reference').click()
    expect(page.get_by_role('heading',name='Leporiang · study reference',exact=True)).to_be_visible()
    page.get_by_role('button',name='Optimize next 24 hours').click()
    expect(page.get_by_role('button',name='Optimize next 24 hours')).to_be_enabled(timeout=15000)
    expect(page.get_by_role('heading',name='24-hour energy plan')).to_be_visible()
    page.get_by_label('Review / override reason').fill('Browser check: verified local context.')
    page.get_by_role('button',name='Record override').click()
    expect(page.get_by_role('status')).to_contain_text('Override recorded',timeout=15000)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(OUT/'site-plan.png'),full_page=True)
    page.get_by_role('button',name='What if?',exact=True).click()
    page.get_by_role('button',name='Run & save simulation').click()
    expect(page.get_by_role('heading',name='Baseline vs. cloudy')).to_be_visible(timeout=15000)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(OUT/'simulation.png'),full_page=True)
    page.get_by_role('link',name='Open saved experiment').click()
    expect(page.get_by_role('button',name='Export run')).to_be_visible()
    page.goto('http://127.0.0.1:5173/sites/new')
    name='Browser smoke '+uuid4().hex[:8]
    page.get_by_label('Site name',exact=True).fill(name)
    page.get_by_label('operator@jeevangrid.local',exact=True).check()
    for _ in range(4):page.get_by_role('button',name='Continue',exact=True).click()
    page.get_by_role('button',name='Save site configuration').click()
    expect(page.get_by_role('heading',name=name,exact=True)).to_be_visible(timeout=15000)
    test_id=page.url.rsplit('/',1)[1]
    page.get_by_role('button',name='Optimize next 24 hours').click()
    expect(page.get_by_role('heading',name='24-hour energy plan')).to_be_visible(timeout=15000)
    page.get_by_role('button',name='Site readings',exact=True).click()
    page.get_by_label('Battery SOC (%)',exact=True).fill('55')
    page.get_by_role('button',name='Save reading',exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('Reading saved',timeout=15000)
    page.get_by_role('button',name='Archive',exact=True).click()
    expect(page.get_by_role('button',name='Restore site')).to_be_visible(timeout=15000)
    page.goto('http://127.0.0.1:5173')
    page.get_by_role('button',name='Run resilience pack').click()
    expect(page.get_by_role('button',name='Run resilience pack')).to_be_enabled(timeout=60000)
    page.screenshot(path=str(OUT/'portfolio-assessed.png'),full_page=True)
    page.get_by_role('button',name='Sign out',exact=True).click()
    page.get_by_label('Email address',exact=True).fill('operator@jeevangrid.local')
    page.get_by_label('Password',exact=True).fill(os.environ.get('JEEVANGRID_DEMO_PASSWORD','JeevanGridDemo!26'))
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.get_by_role('heading',name='Your assigned sites.')).to_be_visible(timeout=15000)
    expect(page.get_by_role('link',name='Portfolio',exact=True)).to_have_count(0)
    expect(page.get_by_role('link',name='Leporiang area · constrained demo')).to_have_count(0)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'operator-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page overflows mobile width'
    assert not errors, errors
    print(json.dumps({'browser':'passed','console_errors':errors,'created_archived_test_site_id':test_id,'screenshots':str(OUT)}))
    browser.close()
