"""Exercise the renewable intelligence UI against the local demo."""
import csv
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path(__file__).parent/'test-results'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
    errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:requests.append(r.url))
    page.goto('http://127.0.0.1:5173')
    page.get_by_label('Password',exact=True).fill(os.environ.get('JEEVANGRID_DEMO_PASSWORD','JeevanGridDemo!26'))
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.get_by_role('heading',name='Your energy network.')).to_be_visible()
    expect(page.locator('.leaflet-marker-icon').first).to_be_visible()
    page.get_by_label('Inspect map site').select_option('2')
    expect(page.locator('.map-inspector')).to_contain_text('compact demo')
    page.get_by_role('button',name='India overview').click()
    page.screenshot(path=str(OUT/'intelligence-portfolio.png'),full_page=True)
    page.goto('http://127.0.0.1:5173/sites/2')
    page.get_by_role('button',name='Optimize next 24 hours').click()
    expect(page.get_by_role('button',name='Optimize next 24 hours')).to_be_enabled(timeout=15000)
    expect(page.get_by_role('heading',name='24-hour energy plan')).to_be_visible()
    page.locator('.reason-details summary').click()
    expect(page.locator('.reason-details')).to_contain_text('Fuel is costed')
    page.get_by_label('Inspect dispatch hour').fill('18')
    expect(page.locator('.flow-panel')).to_contain_text('Selected hour')
    page.get_by_role('button',name='Solar',exact=True).click()
    expect(page.locator('.flow-detail')).to_contain_text('installed')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(OUT/'intelligence-plan.png'),full_page=True)
    page.get_by_role('button',name='Dataset Explorer',exact=True).click()
    expect(page.get_by_role('heading',name='Dataset Explorer')).to_be_visible()
    page.get_by_role('button',name='weather',exact=True).click()
    expect(page.get_by_role('columnheader',name='Irradiance (W/m²)')).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role('button',name='Download CSV',exact=True).click()
    rows=list(csv.reader(Path(download.value.path()).read_text(encoding='utf-8-sig').splitlines()))
    assert len(rows)==25 and len(rows[0])==19, 'CSV must contain 24 rows and labelled units'
    page.get_by_label('Filter dataset rows').select_option('missing')
    expect(page.get_by_text('No hours match this filter.')).to_be_visible()
    page.get_by_label('Filter dataset rows').select_option('all')
    page.screenshot(path=str(OUT/'intelligence-dataset.png'),full_page=True)
    page.get_by_role('button',name='Impact analysis',exact=True).click()
    expect(page.get_by_role('heading',name='What does planning ahead change?')).to_be_visible()
    expect(page.get_by_role('columnheader',name='Reactive rule',exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'intelligence-impact.png'),full_page=True)
    page.get_by_role('button',name='What if?',exact=True).click()
    page.get_by_role('button',name='Test six scenarios',exact=True).click()
    expect(page.get_by_role('button',name='Test six scenarios',exact=True)).to_be_enabled(timeout=45000)
    expect(page.get_by_text('Six scenarios saved.',exact=True)).to_be_visible()
    assert page.locator('table').first.locator('tbody tr').count()==7
    assert page.locator('table').first.get_by_text('Not tested',exact=True).count()==0
    page.screenshot(path=str(OUT/'intelligence-resilience.png'),full_page=True)
    page.get_by_role('button',name='Data & assumptions',exact=True).click()
    expect(page.locator('.config-card')).to_have_count(4)
    page.get_by_role('button',name='Operating plan',exact=True).click()
    page.set_viewport_size({'width':390,'height':844})
    expect(page.locator('.flow-mobile')).to_be_visible()
    expect(page.locator('.flow-mobile')).to_contain_text('Demand served')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(OUT/'intelligence-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Site page overflows mobile viewport'
    page.goto('http://127.0.0.1:5173/')
    expect(page.get_by_role('heading',name='Your energy network.')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Portfolio overflows mobile viewport'
    assert not any('tile.openstreetmap.org' in r for r in requests), 'Offline map must not request public tiles'
    assert not errors, errors
    print('PASS: map, dispatch selection, explanations, dataset filtering/CSV, impact, six scenarios, configuration cards and mobile; no browser errors.')
    browser.close()
