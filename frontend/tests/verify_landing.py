"""Public landing/routing regression. API fixtures only; no real login or writes."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

URL='http://127.0.0.1:5173'
OUT=Path(__file__).resolve().parents[1]/'test-results'
OUT.mkdir(exist_ok=True)
USER={'id':1,'name':'Demo administrator','email':'landing-test@local','role':'admin','organization':'Landing test'}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/opt/google/chrome/chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def api(route):
        path=urlparse(route.request.url).path
        payload={
            '/api/auth/demo-accounts':[], '/api/auth/me':USER,
            '/api/auth/login':{'user':USER,'access':'fixture-access','refresh':'fixture-refresh'},
            '/api/auth/logout':{},'/api/portfolio/reliability':{'sites':[]},'/api/sites':[],
        }
        if path not in payload:raise AssertionError('Unexpected request: '+path)
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload[path]))
    page.route('**/api/**',api)
    page.goto(URL)
    expect(page.get_by_role('heading',name='Every watt. A wiser decision.',exact=True)).to_be_visible()
    expect(page.locator('.sidebar')).to_have_count(0)
    page.screenshot(path=str(OUT/'landing-desktop.png'))
    page.get_by_role('navigation',name='Page sections').get_by_role('link',name='Intelligence',exact=True).click()
    expect(page.get_by_role('navigation',name='Reading progress').get_by_role('link',name='Intelligence',exact=True)).to_have_attribute('aria-current','location')
    page.get_by_role('button',name='Generate a plan',exact=True).click()
    expect(page.locator('.lp-demo-result')).to_contain_text('OptimizationRun + 24 DispatchIntervals')
    expect(page.locator('.lp-agent-demo')).to_contain_text('No records are written on this page')
    page.screenshot(path=str(OUT/'landing-intelligence.png'))
    page.get_by_role('navigation',name='Page sections').get_by_role('link',name='Architecture',exact=True).click()
    expect(page.locator('.lp-architecture')).to_contain_text('Django REST API')
    page.locator('.lp-header').get_by_role('link',name='Get started',exact=False).click()
    expect(page).to_have_url(URL+'/login')
    expect(page.get_by_role('heading',name='Sign in',exact=True)).to_be_visible()
    page.get_by_label('Email address').fill('landing-test@local')
    page.get_by_label('Password',exact=True).fill('fixture-password')
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page).to_have_url(URL+'/workspace')
    expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible()
    # Public home is still public with a logged-in session; CTA returns to workspace.
    page.goto(URL)
    expect(page.get_by_role('heading',name='Every watt. A wiser decision.',exact=True)).to_be_visible()
    page.locator('.lp-header').get_by_role('link',name='Log in',exact=True).click()
    expect(page).to_have_url(URL+'/workspace')
    page.get_by_role('button',name='Sign out',exact=True).click()
    expect(page).to_have_url(URL+'/')
    expect(page.get_by_role('heading',name='Every watt. A wiser decision.',exact=True)).to_be_visible()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflows'
    page.screenshot(path=str(OUT/'landing-mobile.png'))
    page.get_by_role('button',name='Open navigation').click()
    page.get_by_role('navigation',name='Page sections').get_by_role('link',name='Intelligence',exact=True).click()
    expect(page.get_by_role('button',name='Open navigation')).to_have_attribute('aria-expanded','false')
    expect(page.locator('#intelligence')).to_contain_text('ML is not automatically enabled')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile intelligence overflows'
    page.locator('.lp-header').get_by_role('link',name='Log in',exact=True).click()
    expect(page.get_by_role('heading',name='Sign in',exact=True)).to_be_visible()
    assert not errors,errors
    print('PASS: public landing, active scroll-spy, workflow illustration, unchanged login, authenticated routing, logout and mobile navigation; no browser errors.')
    browser.close()
