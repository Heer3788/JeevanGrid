"""Browser acceptance for the local demo; creates labelled plans/replay on Dharnai only."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path(__file__).resolve().parent.parent/'test-results'
OUT.mkdir(exist_ok=True)
URL=os.environ.get('JG_TEST_URL','http://127.0.0.1:5173')
report={'checks':[],'weather':{}}


def fetch(page,path,body=None):
    return page.evaluate('''async ([path,body])=>{
      const r=await fetch('/api'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',Authorization:'Bearer '+sessionStorage.getItem('jg-access')},...(body?{body:JSON.stringify(body)}:{})});
      return {status:r.status,data:await r.json()};
    }''',[path,body])


if '--assistant-only' in sys.argv:
    import runpy
    runpy.run_path(str(Path(__file__).with_name('verify_assistant.py')))
    sys.exit(0)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1050})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    if '--metrics-only' in sys.argv:
        page.goto(URL+'/login')
        page.get_by_role('button',name='Agency administrator',exact=False).click()
        expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=20000)
        site=next(s for s in fetch(page,'/sites')['data'] if s['name']=='Dharnai · village demo')
        def check_metric(label,close='escape'):
            card=page.locator('.metric').filter(has_text=label).first
            trigger=card.locator('.metric-toggle')
            trigger.scroll_into_view_if_needed()
            before=card.bounding_box()
            trigger.click()
            dialog=page.get_by_role('dialog',name=label,exact=True)
            expect(dialog).to_be_visible()
            expect(dialog.locator('.metric-dialog-value')).to_be_visible()
            after=card.bounding_box()
            assert abs(before['height']-after['height'])<1,'KPI must keep its original height'
            assert abs(before['width']-after['width'])<1,'KPI must keep its original width'
            expect(card.locator('.metric-details')).to_have_count(0)
            for _ in range(5):
                page.keyboard.press('Tab')
                assert dialog.evaluate('(node)=>node.contains(document.activeElement)'),label
            bounds=dialog.bounding_box()
            assert bounds['x']>=0 and bounds['x']+bounds['width']<=page.viewport_size['width']+1
            if close=='button':dialog.get_by_role('button',name='Close dialog').click()
            elif close=='backdrop':page.mouse.click(2,2)
            else:page.keyboard.press('Escape')
            expect(dialog).to_have_count(0)
            expect(trigger).to_be_focused()
        for width in [1440,390]:
            page.set_viewport_size({'width':width,'height':960 if width>800 else 844})
            for i,label in enumerate(['Active sites','Need review','Stress-tested sites','Decision horizon']):
                check_metric(label,['escape','button','backdrop','escape'][i])
            page.locator('.metric').filter(has_text='Active sites').first.locator('.metric-toggle').click()
            page.screenshot(path=str(OUT/f'kpi-dialog-{width}.png'),full_page=True)
            page.keyboard.press('Escape')
        page.locator('.metric').filter(has_text='Active sites').first.locator('.metric-toggle').click()
        page.get_by_role('dialog').get_by_role('link',name='Dharnai · village demo',exact=False).click()
        expect(page.get_by_role('heading',name='Your day, hour by hour')).to_be_visible(timeout=20000)
        expect(page.get_by_role('dialog')).to_have_count(0)
        for label in ['Critical energy served','Dispatch cost','Diesel required','Renewable generation']:
            check_metric(label)
        page.goto(f'{URL}/sites/{site["id"]}/edit')
        page.get_by_role('button',name='5 Review',exact=True).click()
        check_metric('Daily demand','button')
        assert page.url.endswith('/edit'),'A KPI must not submit the configuration form'
        assert not errors,errors
        print('KPI dialogs passed: portfolio/site/configuration, unchanged card size, link navigation, keyboard focus, all close methods and mobile fit',flush=True)
        browser.close()
        sys.exit(0)
    if '--login-only' in sys.argv:
        for width in [390,768,1024,1440]:
            page.set_viewport_size({'width':width,'height':960 if width>800 else 844})
            page.goto(URL+'/login')
            expect(page.get_by_role('button',name='Agency administrator',exact=False)).to_be_visible(timeout=20000)
            email=page.get_by_role('textbox',name='Email address')
            email.scroll_into_view_if_needed()
            email.click()
            expect(email).to_be_focused()
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(OUT/f'visual-login-{width}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        print('Login form visible and clickable at 390, 768, 1024 and 1440 px',flush=True)
        browser.close()
        sys.exit(0)
    if '--charts-only' in sys.argv:
        page.goto(URL+'/login')
        page.get_by_role('button',name='Agency administrator',exact=False).click()
        expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=20000)
        site=next(s for s in fetch(page,'/sites')['data'] if s['name']=='Dharnai · village demo')
        page.goto(URL+'/sites')
        page.get_by_role('textbox',name='Search sites').fill('Dharnai')
        expect(page.locator('.site-card')).to_have_count(1)
        page.locator('.site-card').click()
        expect(page.get_by_role('heading',name='Your day, hour by hour')).to_be_visible(timeout=20000)
        page.get_by_text('Site equipment & source notes',exact=True).click()
        ring=page.locator('.equipment-overview .ring-center')
        page.locator('.ring-legend').get_by_role('button',name='Solar',exact=False).click()
        expect(ring.locator('strong')).to_have_text('100')
        page.get_by_role('button',name='24-hour energy',exact=True).click()
        expect(page.get_by_role('heading',name='Energy in this plan')).to_be_visible()
        page.locator('.ring-legend').get_by_role('button',name='Wind',exact=False).click()
        expect(ring.locator('strong')).to_have_text('0')
        page.get_by_label('Inspect stress scenario').select_option('low_wind')
        expect(page.locator('.stress-insight')).to_contain_text('No wind installed')
        page.get_by_label('Inspect stress scenario').select_option('low_battery')
        expect(page.locator('.stress-insight')).to_contain_text('Starting SOC 25%')
        for metric in ['Diesel','Cost','Unserved energy','Reserve margin']:
            page.get_by_label('Stress comparison metric').get_by_role('button',name=metric,exact=True).click()
        assert not errors,errors
        print('Site search, selected ring values, energy units and four stress metrics passed',flush=True)
        browser.close()
        sys.exit(0)
    if '--visual-only' in sys.argv:
        captures=[]
        def capture(name):
            if name.startswith('portfolio'):expect(page.locator('.portfolio-map')).to_be_visible(timeout=20000)
            page.wait_for_timeout(350)
            page.mouse.move(0,0)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(OUT/f'visual-{name}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),name
            captures.append(name)
        for width in [390,768,1024,1440]:
            page.set_viewport_size({'width':width,'height':960 if width>800 else 844})
            page.goto(URL+'/login')
            expect(page.get_by_role('button',name='Agency administrator',exact=False)).to_be_visible(timeout=20000)
            capture(f'login-{width}')
        page.get_by_role('button',name='Agency administrator',exact=False).click()
        expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=20000)
        site=next(s for s in fetch(page,'/sites')['data'] if s['name']=='Dharnai · village demo')
        site_id=site['id']
        run_id=site['latest_run']['id']
        for width in [1440,1024,390]:
            page.set_viewport_size({'width':width,'height':960 if width>800 else 844})
            for name,route,heading in [
                ('portfolio','/','Portfolio overview'),
                ('sites','/sites','Microgrid sites'),
                ('plan',f'/sites/{site_id}','Your day, hour by hour'),
                ('data',f'/data?site={site_id}&run={run_id}','Dataset Explorer'),
                ('people','/team','People & access'),
                ('account','/account','Account details'),
                ('configuration',f'/sites/{site_id}/edit','Site configuration'),
            ]:
                page.goto(URL+route)
                expect(page.get_by_role('heading',name=heading,exact=True)).to_be_visible(timeout=20000)
                capture(f'{name}-{width}')
            page.get_by_role('button',name='2 Equipment',exact=True).click()
            expect(page.get_by_role('heading',name='Equipment and engineering limits')).to_be_visible()
            capture(f'equipment-{width}')
            page.goto(f'{URL}/sites/{site_id}')
            expect(page.get_by_role('heading',name='Your day, hour by hour')).to_be_visible(timeout=20000)
            page.get_by_role('button',name='Update readings',exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible()
            capture(f'readings-dialog-{width}')
            page.keyboard.press('Escape')
            page.get_by_text('Site equipment & source notes',exact=True).click()
            expect(page.get_by_role('heading',name='Installed power',exact=True)).to_be_visible()
            capture(f'site-equipment-{width}')
            page.get_by_role('button',name='24-hour energy',exact=True).click()
            expect(page.get_by_role('heading',name='Energy in this plan',exact=True)).to_be_visible()
            capture(f'generation-energy-{width}')
            page.get_by_text('Site equipment & source notes',exact=True).click()
            for chart in ['Battery reserve','Flexible work']:
                page.get_by_role('button',name=chart,exact=True).click()
                capture(f'{chart.lower().replace(" ","-")}-{width}')
            page.get_by_role('tab',name='2 Test plan').click()
            capture(f'conditions-{width}')
            page.get_by_role('button',name='Live replay',exact=True).click()
            expect(page.get_by_role('heading',name=f'Watch plan #{run_id} respond')).to_be_visible()
            capture(f'replay-{width}')
        assert not errors,errors
        result={'captures':captures,'page_errors':errors,'horizontal_overflow':False}
        (OUT/'visual-review.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2),flush=True)
        browser.close()
        sys.exit(0)
    try:
        page.goto(URL+'/login')
        expect(page.get_by_role('button',name='Agency administrator',exact=False)).to_be_visible(timeout=20000)
        page.screenshot(path=str(OUT/'workspace-login.png'),full_page=True)
        page.get_by_role('button',name='Agency administrator',exact=False).click()
        expect(page.get_by_role('heading',name='Portfolio overview')).to_be_visible(timeout=20000)
        expect(page.locator('.sidebar nav a')).to_have_count(5)
        card=page.locator('.metric').filter(has_text='Active sites').first
        card.get_by_role('button').hover()
        expect(card.get_by_role('tooltip')).to_be_visible()
        card.get_by_role('button').click()
        expect(page.get_by_role('dialog',name='Active sites',exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        expect(card.get_by_role('button')).to_be_focused()
        page.mouse.move(0,0)
        page.screenshot(path=str(OUT/'workspace-portfolio.png'),full_page=True)
        report['checks'].append('Admin login, five navigation destinations and KPI tooltip/dialog')
        sites=fetch(page,'/sites')['data']
        site=next(s for s in sites if s['name']=='Dharnai · village demo')
        site_id=site['id']
        page.goto(f'{URL}/sites/{site_id}')
        expect(page.get_by_role('tablist',name='Site workflow')).to_be_visible(timeout=20000)
        expect(page.get_by_role('tab')).to_have_count(2)
        expect(page.get_by_role('heading',name='Your day, hour by hour')).to_be_visible()
        page.get_by_role('button',name='Battery reserve',exact=True).click()
        expect(page.get_by_text('Operating reserve',exact=False).first).to_be_visible()
        page.get_by_role('button',name='Flexible work',exact=True).click()
        expect(page.locator('.task-track')).to_have_count(2)
        page.get_by_role('button',name='Energy supply',exact=True).click()
        page.get_by_text('Site equipment & source notes',exact=True).click()
        expect(page.get_by_role('heading',name='Installed power',exact=True)).to_be_visible()
        expect(page.locator('.equipment-overview .energy-ring')).to_have_attribute('aria-label',__import__('re').compile('Solar 100 kW.*Diesel 75 kW'))
        page.get_by_role('button',name='24-hour energy',exact=True).click()
        expect(page.get_by_role('heading',name='Energy in this plan',exact=True)).to_be_visible()
        expect(page.locator('.equipment-overview .energy-ring')).to_have_attribute('aria-label',__import__('re').compile('Solar .* kWh'))
        page.get_by_text('Site equipment & source notes',exact=True).click()
        expect(page.get_by_label('Inspect stress scenario')).to_be_enabled(timeout=30000)
        page.get_by_label('Inspect stress scenario').select_option('low_battery')
        expect(page.locator('.stress-insight')).to_contain_text('Starting SOC 25%')
        page.get_by_label('Stress comparison metric').get_by_role('button',name='Cost',exact=True).click()
        expect(page.locator('.stress-chart')).to_have_attribute('aria-label',__import__('re').compile('Cost by scenario, INR'))
        page.get_by_role('button',name='Inspect hourly response',exact=True).click()
        expect(page.get_by_role('dialog')).to_be_visible()
        expect(page.get_by_label('Hourly comparison metric').get_by_role('button',name='Battery charge',exact=True)).to_have_attribute('aria-pressed','true')
        page.get_by_label('Hourly comparison metric').get_by_role('button',name='Demand served',exact=True).click()
        page.keyboard.press('Escape')
        report['checks'].append('Capacity and energy charts, actual stress comparisons, selectable battery/demand hourly response')
        page.get_by_role('button',name='Review plan',exact=True).click()
        expect(page.get_by_role('dialog')).to_be_visible()
        page.keyboard.press('Escape')
        page.get_by_role('button',name='Compare with reactive',exact=True).click()
        expect(page.get_by_role('dialog')).to_be_visible()
        page.get_by_role('button',name='Close dialog').click()
        page.screenshot(path=str(OUT/'workspace-plan.png'),full_page=True)
        report['checks'].append('Two site views, supply/battery/flexible graphs, plan review and reactive comparison')
        for mode in ['forecast','historical','simulated']:
            page.get_by_label('Weather source',exact=True).select_option(mode)
            if mode=='historical':page.get_by_label('Historical date',exact=True).fill('2025-01-15')
            with page.expect_response(lambda r:f'/api/sites/{site_id}/optimization-runs' in r.url and r.request.method=='POST',timeout=65000) as response:
                page.get_by_role('button',name='Generate plan',exact=True).click()
            result=response.value
            payload=result.json()
            report['weather'][mode]={'http_status':result.status,'source':payload.get('weather_source'),'run_id':payload.get('id'),'detail':payload.get('detail')}
            if result.ok:
                expect(page.locator('.plan-context')).to_contain_text(f"#{payload['id']}",timeout=20000)
                assert payload['weather_source']=={'forecast':'open_meteo','historical':'nasa_power','simulated':'simulated'}[mode]
            else:
                expect(page.get_by_role('alert').first).to_be_visible()
        baseline=fetch(page,f'/sites/{site_id}')['data']['latest_run']
        page.get_by_role('tab',name='2 Test plan').click()
        page.get_by_text('Try a custom combination',exact=True).click()
        page.get_by_label('Demand',exact=True).fill('1.5')
        page.get_by_role('button',name='Compare with original plan',exact=True).click()
        expect(page.locator('.scenario-result')).to_be_visible(timeout=30000)
        page.screenshot(path=str(OUT/'workspace-test.png'),full_page=True)
        report['checks'].append('Custom combined scenario and original-versus-test comparison')
        page.get_by_role('button',name='Live replay',exact=True).click()
        old=fetch(page,f'/sites/{site_id}/live')['data']['session']
        if old and old['active']:
            fetch(page,f'/sites/{site_id}/live',{'action':'pause'})
            expect(page.get_by_role('button',name='Start replay',exact=True)).to_be_visible(timeout=10000)
        page.get_by_label('Clock speed',exact=True).select_option('120')
        page.get_by_role('button',name='Start replay',exact=True).click()
        expect(page.get_by_role('heading',name='Is demand being supplied?')).to_be_visible(timeout=30000)
        live=fetch(page,f'/sites/{site_id}/live')['data']['session']
        assert live['baseline_id']==baseline['id']
        page.get_by_role('button',name='Approve simulated command',exact=True).click()
        page.wait_for_function('''()=>document.body.innerText.includes('1 verified')''',timeout=50000)
        page.get_by_role('button',name='Cloud cover',exact=True).click()
        page.screenshot(path=str(OUT/'workspace-live.png'),full_page=True)
        page.get_by_role('button',name='Pause replay',exact=True).click()
        report['checks'].append('Replay starts from selected plan, streams telemetry, verifies approval and accepts an event')
        page.goto(f"{URL}/data?site={site_id}&run={baseline['id']}")
        expect(page.get_by_role('heading',name='Dataset Explorer',exact=True)).to_be_visible(timeout=20000)
        with page.expect_download() as download:page.get_by_role('button',name='Download CSV',exact=True).click()
        assert download.value.suggested_filename.endswith('.csv')
        page.get_by_role('link',name='People & access',exact=True).click()
        expect(page.get_by_role('heading',name='People & access')).to_be_visible()
        expect(page.locator('.team-grid .panel')).to_have_count(5)
        page.get_by_role('button',name='Sign out',exact=True).click()
        expect(page.get_by_role('heading',name='Sign in')).to_be_visible()
        page.get_by_role('button',name='Bihar demo operator',exact=False).click()
        expect(page.get_by_role('heading',name='Assigned sites')).to_be_visible(timeout=20000)
        expect(page.locator('.site-card')).to_have_count(1)
        assert fetch(page,'/portfolio/reliability')['status']==403
        page.set_viewport_size({'width':390,'height':844})
        page.goto(f'{URL}/sites/{site_id}')
        expect(page.get_by_role('heading',name='Your day, hour by hour')).to_be_visible(timeout=20000)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/'workspace-mobile.png'),full_page=True)
        report['checks'].append('Dataset CSV, team page, regional-operator isolation and mobile layout')
        assert not errors,errors
        report['page_errors']=errors
        print(json.dumps(report,indent=2),flush=True)
    except Exception:
        page.screenshot(path=str(OUT/'workspace-failure.png'),full_page=True)
        print(json.dumps({'report':report,'page_errors':errors,'url':page.url},indent=2),flush=True)
        raise
    finally:
        browser.close()
        (OUT/'workspace-verification.json').write_text(json.dumps(report,indent=2))
