"""Opt-in real UI replay check on the newly seeded demo site; software only."""
import json
import os
import re
import sys
import time
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

if '--execute' not in sys.argv: raise SystemExit('Pass --execute: creates a simulated replay, event and command review on JG004.')
site=m.Site.objects.get(provenance__seed_key=SEED_KEY,provenance__seed_index=3)
admin=m.UserRole.objects.get(organization=site.organization,user__username='admin@jeevangrid.local').user
token=RefreshToken.for_user(admin)
output=ROOT/'frontend'/'test-results'; output.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/opt/google/chrome/chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('sessionStorage.setItem("jg-access",'+json.dumps(str(token.access_token))+');sessionStorage.setItem("jg-refresh",'+json.dumps(str(token))+');')
    def status():
        return page.evaluate('async id => {const r=await fetch(`/api/sites/${id}/live`,{headers:{Authorization:`Bearer ${sessionStorage.getItem("jg-access")}`}});return await r.json()}',site.pk)
    def await_state(predicate, timeout=45):
        started=time.monotonic()
        while time.monotonic()-started<timeout:
            current=status()
            if predicate(current.get('session')): return current['session']
            page.wait_for_timeout(1000)
        raise AssertionError('Replay state timed out: '+str(current))
    page.goto(f'http://127.0.0.1:5173/sites/{site.pk}')
    page.get_by_role('tab',name=re.compile('Test plan')).click()
    page.get_by_role('button',name='Live replay',exact=True).click()
    page.get_by_label('Clock speed').select_option('30')
    page.get_by_role('button',name='Start replay',exact=True).click()
    try:
        await_state(lambda s:s and s.get('telemetry') and not s['stale'])
        page.get_by_role('button',name='Cloud cover',exact=True).click()
        current=await_state(lambda s:s and s.get('modifiers',{}).get('solar_multiplier',1)<1 and s.get('run'))
        button=page.get_by_role('button',name='Approve simulated command',exact=True)
        expect(button).to_be_enabled(timeout=30000)
        page.get_by_role('textbox',name='Command review reason').fill('Final-round software replay verification')
        button.click()
        current=await_state(lambda s:s and s['evidence']['verified_commands']>=1)
        assert abs(current['telemetry']['balance_error_kw']) < .001
        expect(page.locator('summary').filter(has_text=re.compile(r'Command history & evidence \([1-9][0-9]* verified\)'))).to_be_visible(timeout=15000)
        page.locator('summary').filter(has_text='Command history & evidence').click()
        page.locator('.replay-decision').scroll_into_view_if_needed()
        page.screenshot(path=str(output/'showcase-live-replay.png'))
        (output/'showcase-live-replay.json').write_text(json.dumps({'session_id':current['id'],'site_id':site.pk,
            'verified_commands':current['evidence']['verified_commands'],'evidence':current['evidence'],
            'modifiers':current['modifiers'],'telemetry':current['telemetry']},indent=2),encoding='utf-8')
        print('PASS: WebSocket UI, simulated telemetry, cloud event, rolling plan, operator approval and verified command; balance within 0.001 kW.')
    finally:
        pause=page.get_by_role('button',name='Pause replay',exact=True)
        if pause.is_visible(): pause.click()
        browser.close()
    assert not errors,errors
