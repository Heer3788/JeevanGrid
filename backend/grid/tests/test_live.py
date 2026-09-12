from copy import deepcopy
from datetime import timedelta
import asyncio
import json
import pandas as pd
import pytest
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import ValidationError
from grid import live, models as m, services as svc, forecasting
from grid.optimizer import solve
from grid.tests.test_api import setup
from grid.tests.test_engine import snapshot, check_balance

pytestmark=pytest.mark.django_db


def test_simulated_physics_and_approval_loop(setup):
    client,users,sites=setup
    session=live.start(sites[0],users['admin'],{'speed':1})
    assert session.site.configuration_version==1
    live.advance(session.pk)
    session.refresh_from_db();cmd=session.commands.filter(status='proposed').first()
    live.review(session,cmd,users['admin'],'approve','Test')
    live.advance(session.pk)
    cmd.refresh_from_db();session.refresh_from_db()
    assert cmd.status=='verified'
    t=session.state['telemetry']
    assert abs(t['balance_error_kw'])<1e-6
    assert 20<=t['soc_pct']<=95
    before=deepcopy(session.state)
    data=live.status(sites[0]);json.dumps(data,cls=DjangoJSONEncoder)
    session.refresh_from_db();assert session.state==before # GET never advances the simulation
    assert data['session']['evidence']['verified_commands']==1


def test_five_minute_replan_and_event(setup):
    _,users,sites=setup
    session=live.start(sites[0],users['admin'],{'speed':30})
    session.refresh_from_db();first=session.latest_run_id;config=deepcopy(svc.configuration(sites[0]))
    for _ in range(5):live.advance(session.pk)
    session.refresh_from_db();assert session.latest_run_id!=first
    assert (session.last_plan_at-pd.Timestamp(session.snapshot['inputs'][0]['timestamp']).to_pydatetime()).total_seconds()==300
    live.inject(session,'cloud');live.advance(session.pk);session.refresh_from_db()
    assert session.latest_run.snapshot['inputs'][0]['solar_available']<session.snapshot['inputs'][0]['solar_available']*.3
    assert svc.configuration(sites[0])==config


def test_command_expiry_rejection_and_permissions(setup):
    client,users,sites=setup
    session=live.start(sites[0],users['admin'],{})
    live.advance(session.pk);session.refresh_from_db();cmd=session.commands.filter(status='proposed').first()
    client.force_authenticate(users['operator'])
    assert client.get(f'/api/sites/{sites[1].pk}/live').status_code==404
    assert client.post(f'/api/sites/{sites[0].pk}/forecast-model',{'source':'simulated'},format='json').status_code==403
    assert client.post(f'/api/sites/{sites[0].pk}/live/commands/{cmd.pk}',{'decision':'reject'},format='json').status_code==400
    live.review(session,cmd,users['operator'],'reject','Keep current plan')
    with pytest.raises(ValidationError):live.review(session,cmd,users['operator'],'approve','')
    live.replan(session.pk,'Test');session.refresh_from_db();cmd=session.commands.filter(status='proposed').first()
    session.simulated_at=cmd.expires_at
    with pytest.raises(ValidationError):live.review(session,cmd,users['operator'],'approve','')


def test_stale_command_and_config_pause(setup):
    _,users,sites=setup
    session=live.start(sites[0],users['admin'],{})
    session.refresh_from_db();cmd=session.commands.filter(status='proposed').first()
    with pytest.raises(ValidationError):live.review(session,cmd,users['admin'],'approve','')
    sites[0].configuration_version+=1;sites[0].save()
    live.advance(session.pk);session.refresh_from_db();assert not session.active


def test_outage_reports_observed_critical_shortage(setup):
    _,users,sites=setup
    c=svc.configuration(sites[0]);c['solar']['capacity_kw']=0;c['wind']['capacity_kw']=0
    c['battery']['max_discharge_kw']=0
    svc.save_configuration(sites[0],c)
    session=live.start(sites[0],users['admin'],{})
    live.inject(session,'generator_outage');live.advance(session.pk);session.refresh_from_db()
    assert session.state['critical_unserved_kwh']>0
    assert session.state['telemetry']['generator_kw']==0
    assert abs(session.state['telemetry']['balance_error_kw'])<1e-6


def test_solar_and_demand_backtest_roundtrip(setup):
    _,_,sites=setup;site=sites[0];c=svc.configuration(site)
    rows=forecasting.demo_dataset(site,c);assert len(rows)==2160
    version=forecasting.train(site,c,rows,'simulated')
    r=version.report
    assert r['split']['training'][1]<r['split']['calibration'][0]<r['split']['test'][0]
    assert r['demand']['ml_mae_kw']<r['demand']['baseline_mae_kw']
    assert r['solar']['ml_mae_kw']<r['solar']['baseline_mae_kw']
    snap=svc.prepare_snapshot(site,'simulated')
    forecasting.apply_forecast(site,snap)
    assert snap['forecast_model']['id']==version.pk
    for row in snap['inputs']:
        assert 0<=row['solar_available']<=row['solar_forecast_kw']<=c['solar']['capacity_kw']
        assert row['demand_upper_kw']>=row['demand_forecast_kw']
    snap['weather']['source']='open_meteo';forecasting.apply_forecast(site,snap)
    assert snap['forecast_model']['id'] is None


def test_generator_minimum_run_cooldown_and_ramp():
    s=snapshot();s['configuration']['generator'].update(min_up_hours=3,min_down_hours=2,ramp_kw_per_hour=4)
    result=solve(s);check_balance(result,s['configuration'])
    rows=result['intervals']
    for i,row in enumerate(rows):
        if row['diesel_start']:assert all(r['diesel_on'] for r in rows[i:i+3])
        if i and not row['diesel_on'] and rows[i-1]['diesel_on']:assert all(not r['diesel_on'] for r in rows[i:i+2])
        if i:assert abs(row['diesel_power']-rows[i-1]['diesel_power'])<=4.001


def test_emissions_preference_protects_reliability():
    s=snapshot();s['configuration']['battery'].update(replacement_cost=300000000)
    for i,row in enumerate(s['inputs']):row['solar_available']=20 if 8<=i<16 else 0
    low=solve(s);s['strategy']='lowest_emissions';green=solve(s)
    check_balance(green,s['configuration'])
    assert green['metrics']['critical_unserved_kwh']<=low['metrics']['critical_unserved_kwh']+.001
    assert green['metrics']['emissions_kg_co2']<=low['metrics']['emissions_kg_co2']+.001


def test_restart_preserves_old_session_evidence(setup):
    client,users,sites=setup
    a=live.start(sites[0],users['admin'],{});live.advance(a.pk)
    client.post(f'/api/sites/{sites[0].pk}/live',{'action':'pause'},format='json')
    b=live.start(sites[0],users['admin'],{})
    assert a.pk!=b.pk and a.samples.count()==1 and b.samples.count()==0


def test_strategy_api_with_multiple_sessions(setup):
    client,users,sites=setup
    a=live.start(sites[0],users['admin'],{})
    client.post(f'/api/sites/{sites[0].pk}/live',{'action':'pause'},format='json')
    live.start(sites[0],users['admin'],{})
    result=client.post(f'/api/sites/{sites[0].pk}/live/strategies',{},format='json')
    assert result.status_code==200 and len(result.data['results'])==3


@pytest.mark.django_db(transaction=True)
def test_websocket_authentication_and_site_isolation(setup):
    from config.asgi import application
    from rest_framework_simplejwt.tokens import RefreshToken
    _,users,sites=setup
    token=str(RefreshToken.for_user(users['operator']).access_token)
    async def check(site,access,allowed):
        incoming,outgoing=asyncio.Queue(),asyncio.Queue()
        scope={'type':'websocket','path':f'/ws/sites/{site.pk}/live',
            'headers':[(b'origin',b'http://localhost:5173')],'query_string':b'','subprotocols':[]}
        task=asyncio.create_task(application(scope,incoming.get,outgoing.put))
        try:
            await incoming.put({'type':'websocket.connect'})
            assert (await asyncio.wait_for(outgoing.get(),5))['type']=='websocket.accept'
            await incoming.put({'type':'websocket.receive','text':json.dumps({'access':access})})
            result=await asyncio.wait_for(outgoing.get(),5)
            assert result['type']==('websocket.send' if allowed else 'websocket.close')
            await incoming.put({'type':'websocket.disconnect','code':1000})
            await asyncio.wait_for(task,5)
        finally:
            task.cancel()
    asyncio.run(check(sites[0],token,True))
    asyncio.run(check(sites[1],token,False))
    asyncio.run(check(sites[0],'invalid',False))
