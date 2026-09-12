"""Browser acceptance check. Run against an isolated seeded test database/server."""
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('JG_TEST_URL','http://127.0.0.1:5183')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE)
    page.get_by_label('Email address').fill('admin@jeevangrid.local')
    page.get_by_label('Password').fill('JeevanGridDemo!26')
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.get_by_role('heading',name='Your energy network.')).to_be_visible(timeout=20000)
    page.get_by_role('link',name='Sites',exact=True).click()
    page.locator('.site-card').first.click()
    page.get_by_role('button',name='Live Control',exact=True).click()
    expect(page.get_by_text('Live stream connected')).to_be_visible(timeout=20000)
    page.get_by_role('button',name='Train on 90 simulated days').click()
    expect(page.get_by_text('2160 hourly rows',exact=False)).to_be_visible(timeout=30000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download training dataset CSV').click()
    assert download.value.suggested_filename.endswith('.csv')
    if page.get_by_role('button',name='Pause simulation',exact=True).count():
        page.get_by_role('button',name='Pause simulation',exact=True).click()
        expect(page.get_by_role('button',name='Start simulation',exact=True)).to_be_visible()
    page.get_by_label('Clock speed').select_option('10')
    page.get_by_role('button',name='Start simulation',exact=True).click()
    approve=page.get_by_role('button',name='Approve simulated command',exact=True)
    expect(approve).to_be_enabled(timeout=20000)
    approve.click()
    page.get_by_text('Command audit and event timeline',exact=True).click()
    expect(page.get_by_text('verified',exact=True).first).to_be_visible(timeout=20000)
    before=page.locator('.live-clock strong').inner_text()
    expect(page.locator('.live-clock strong')).not_to_have_text(before,timeout=10000)
    page.get_by_role('button',name='Cloud cover −75%').click()
    expect(page.get_by_text('Cloud event applied;',exact=False)).to_be_visible(timeout=15000)
    page.get_by_role('button',name='Battery at 25%').click()
    page.get_by_role('button',name='Compare strategies',exact=True).click()
    expect(page.get_by_text('lowest emissions',exact=True)).to_be_visible(timeout=20000)
    page.get_by_role('button',name='Generator outage',exact=True).click()
    expect(page.get_by_text('Generator Outage event applied;',exact=False)).to_be_visible(timeout=15000)
    page.get_by_role('button',name='Pause simulation',exact=True).click()
    expect(page.get_by_role('button',name='Start simulation',exact=True)).to_be_visible()
    with page.expect_download():page.get_by_role('button',name='Export evidence',exact=True).click()
    page.screenshot(path='/tmp/jeevangrid-live-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path='/tmp/jeevangrid-live-mobile.png',full_page=True)
    overflow=page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+2 && getComputedStyle(e).position!=='absolute').map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,text:e.innerText?.slice(0,60)})).slice(0,20)")
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2'), f'Mobile page overflows: {overflow}'
    assert not errors,errors
    print(json.dumps({'browser':'passed','websocket':'connected','command':'verified','training':'passed','events':'passed','downloads':'passed','mobile':'passed'}))
    browser.close()
