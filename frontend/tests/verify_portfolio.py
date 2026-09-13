"""Read-only browser acceptance of the populated portfolio; no provider calls."""
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from grid import models as m
from grid.portfolio_seed import SEED_KEY
from rest_framework_simplejwt.tokens import RefreshToken
from playwright.sync_api import sync_playwright,expect

site=m.Site.objects.get(provenance__seed_key=SEED_KEY,provenance__seed_index=3)
admin=m.UserRole.objects.get(organization=site.organization,user__username='admin@jeevangrid.local').user
token=RefreshToken.for_user(admin)
run=site.runs.exclude(mode__in=['scenario','live_simulation']).first()
output=ROOT/'frontend'/'test-results'; output.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/opt/google/chrome/chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('sessionStorage.setItem("jg-access",'+json.dumps(str(token.access_token))+');sessionStorage.setItem("jg-refresh",'+json.dumps(str(token))+');')
    page.goto('http://127.0.0.1:5173/sites')
    page.get_by_role('textbox',name='Search sites').fill('JG')
    expect(page.locator('.site-card')).to_have_count(108,timeout=30000)
    page.screenshot(path=str(output/'portfolio-108-sites.png'))
    page.goto(f'http://127.0.0.1:5173/data?site={site.pk}&run={run.pk}')
    inventory=page.locator('details').filter(has=page.locator('summary').filter(has_text="How this site's demand was calculated")).first
    inventory.locator('summary').first.click()
    expect(inventory.get_by_text('Clinic vaccine refrigerator',exact=True)).to_be_visible()
    expect(inventory).to_contain_text('NOT a surveyed or operating installation')
    expect(inventory).to_contain_text('Drinking water:')
    inventory.scroll_into_view_if_needed()
    page.screenshot(path=str(output/'portfolio-load-inventory.png'))
    page.goto('http://127.0.0.1:5173/team')
    expect(page.get_by_text('jehanabad.ops1@jeevangrid.local',exact=True)).to_be_visible(timeout=20000)
    card=page.locator('.person-card').filter(has_text='jehanabad.ops1@jeevangrid.local')
    expect(card.locator('.assignment-link')).to_have_count(4)
    page.goto('http://127.0.0.1:5173/workspace')
    expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=30000)
    expect(page.locator('.portfolio-map')).to_be_visible()
    page.screenshot(path=str(output/'portfolio-regional-map.png'))
    assert not errors,errors
    print('PASS: 108 searchable sites, readable sourced inventory, four operator assignments, portfolio map; no browser errors.')
    browser.close()
