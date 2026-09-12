from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
import pandas as pd
import pytest
import requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from grid import models as m, services as svc
from grid.defaults import default_configuration
from grid.energy import simulated_weather
from grid.weather import forecast, horizon_start, store_weather

pytestmark=pytest.mark.django_db


@pytest.fixture
def setup():
    org=m.Organization.objects.create(name='Test');other=m.Organization.objects.create(name='Other')
    users={}
    for name,organization,r in [('admin',org,'admin'),('operator',org,'operator'),('outsider',other,'admin')]:
        u=get_user_model().objects.create_user(username=f'{name}@test.local',email=f'{name}@test.local',password='TestPassword!26')
        m.UserRole.objects.create(user=u,organization=organization,role=r);users[name]=u
    sites=[]
    for name,organization in [('A',org),('B',org),('C',other)]:
        s=m.Site.objects.create(organization=organization,name=name)
        svc.save_configuration(s,default_configuration(),False);sites.append(s)
    m.SiteAssignment.objects.create(site=sites[0],user=users['operator'])
    client=APIClient();client.force_authenticate(users['admin'])
    return client,users,sites


def test_authentication_and_refresh(setup):
    client,_,_=setup;client.force_authenticate(None)
    assert client.get('/api/sites').status_code==401
    login=client.post('/api/auth/login',{'email':'admin@test.local','password':'TestPassword!26'},format='json')
    assert login.status_code==200
    client.credentials(HTTP_AUTHORIZATION='Bearer '+login.data['access'])
    assert client.get('/api/auth/me').data['role']=='admin'
    refresh=client.post('/api/auth/refresh',{'refresh':login.data['refresh']},format='json')
    assert refresh.status_code==200
    assert client.post('/api/auth/refresh',{'refresh':login.data['refresh']},format='json').status_code==401


def test_operator_and_organization_isolation(setup):
    client,users,sites=setup
    assert len(client.get('/api/sites').data)==2
    assert client.get(f'/api/sites/{sites[2].id}').status_code==404
    client.force_authenticate(users['operator'])
    assert len(client.get('/api/sites').data)==1
    assert client.get(f'/api/sites/{sites[1].id}').status_code==404
    assert client.put(f'/api/sites/{sites[0].id}/configuration',default_configuration(),format='json').status_code==403
    assert client.get('/api/portfolio/reliability').status_code==403
    assert client.post('/api/sites',{'name':'Unauthorized'},format='json').status_code==403


def test_admin_create_assign_archive(setup):
    client,users,_=setup
    d=client.post('/api/sites',{'name':'New site','operator_ids':[users['operator'].id],'configuration':default_configuration()},format='json')
    assert d.status_code==201,d.data
    pk=d.data['id']
    assert client.patch(f'/api/sites/{pk}',{'archived':True},format='json').status_code==200
    assert client.post(f'/api/sites/{pk}/optimization-runs',{'mode':'simulated'},format='json').status_code==400
    assert client.patch(f'/api/sites/{pk}',{'archived':False},format='json').status_code==200
    assert client.patch(f'/api/sites/{pk}',{'operator_ids':[users['outsider'].id]},format='json').status_code==400


def test_india_location_search_filters_state(setup):
    client,_,_=setup
    response = type('Response', (), {
        'raise_for_status': lambda self: None,
        'json': lambda self: {'results': [
            {'id': 1, 'name': 'Itanagar', 'latitude': 27.1, 'longitude': 93.6,
             'country_code': 'IN', 'admin1': 'Arunachal Pradesh', 'admin2': 'Papum Pare', 'timezone': 'Asia/Kolkata'},
            {'id': 2, 'name': 'Itanagar', 'latitude': 99, 'longitude': 99,
             'country_code': 'XX', 'admin1': 'Arunachal Pradesh'},
        ]},
    })()
    with patch('grid.views.requests.get', return_value=response) as get:
        result=client.get('/api/locations/search',{'q':'Itanagar','state':'Arunachal Pradesh'})
    assert result.status_code==200 and len(result.data['results'])==1
    assert result.data['results'][0]['district']=='Papum Pare'
    assert get.call_args.kwargs['params']['countryCode']=='IN'
    assert get.call_args.kwargs['params']['name']=='Itanagar'


def test_location_search_can_find_place_before_state_selection(setup):
    client,_,_=setup
    response = type('Response', (), {
        'raise_for_status': lambda self: None,
        'json': lambda self: {'results': [
            {'id': 3, 'name': 'Ahmedabad', 'latitude': 23.02, 'longitude': 72.57,
             'country_code': 'IN', 'admin1': 'Gujarat', 'admin2': 'Ahmedabad', 'timezone': 'Asia/Kolkata'},
        ]},
    })()
    with patch('grid.views.requests.get', return_value=response):
        result=client.get('/api/locations/search',{'q':'Ahm'})
    assert result.status_code==200
    assert result.data['results'][0]['state']=='Gujarat'


def test_run_snapshot_immutable_and_scenarios(setup):
    client,users,sites=setup;s=sites[0]
    d=client.post(f'/api/sites/{s.id}/optimization-runs',{'mode':'simulated'},format='json')
    assert d.status_code==201,d.data
    assert d.data['status']=='optimal' and len(d.data['intervals'])==24
    assert d.data['solve_seconds']<5
    assert d.data['weather_source']=='simulated'
    run_id=d.data['id'];original=deepcopy(d.data['snapshot']);config=svc.configuration(s)
    scenario=client.post(f'/api/sites/{s.id}/scenario-runs',{'baseline_id':run_id,'preset':'cloudy'},format='json')
    assert scenario.status_code==201,scenario.data
    assert scenario.data['overrides']=={'solar_multiplier':.5}
    assert svc.configuration(m.Site.objects.get(pk=s.id))==config
    c=default_configuration();c['generator']['diesel_price']=110
    assert client.put(f'/api/sites/{s.id}/configuration',c,format='json').status_code==200
    assert client.get(f'/api/optimization-runs/{run_id}').data['snapshot']==original
    assert client.post(f'/api/optimization-runs/{run_id}/decision',{'decision':'confirm'},format='json').status_code==400


def test_operator_reading_and_override(setup):
    client,users,sites=setup;s=sites[0];client.force_authenticate(users['operator'])
    assert client.post(f'/api/sites/{s.id}/readings',{'soc_pct':65,'event':'Market day'},format='json').status_code==201
    assert client.post(f'/api/sites/{s.id}/readings',{'min_soc':0},format='json').status_code==400
    run=client.post(f'/api/sites/{s.id}/optimization-runs',{'mode':'simulated'},format='json').data
    assert run['state_source']=='operator'
    assert client.post(f"/api/optimization-runs/{run['id']}/decision",{'decision':'override'},format='json').status_code==400
    assert client.post(f"/api/optimization-runs/{run['id']}/decision",{'decision':'override','reason':'Local event'},format='json').status_code==201
    assert client.get(f"/api/optimization-runs/{run['id']}").data['decisions'][0]['reason']=='Local event'


def test_cross_site_scenario_and_run_denied(setup):
    client,users,sites=setup
    run=svc.optimize(sites[1],users['admin'])
    assert client.post(f'/api/sites/{sites[0].id}/scenario-runs',{'baseline_id':run.id,'preset':'cloudy'},format='json').status_code==400
    client.force_authenticate(users['operator'])
    assert client.get(f'/api/optimization-runs/{run.id}').status_code==404


def make_csv(kind='valid'):
    header='timestamp,critical_kw,normal_kw,flexible_kw\n'
    dates=[pd.Timestamp('2025-01-15',tz='Asia/Kolkata')+pd.Timedelta(hours=i) for i in range(24)]
    if kind=='duplicate':dates[2]=dates[1]
    if kind=='missing':dates=dates[:-1]
    if kind=='naive':dates=[d.tz_localize(None) for d in dates]
    if kind=='units':header=header.replace('critical_kw','critical_kwh')
    value='nan' if kind=='nonfinite' else '1'
    content=header+'\n'.join(f'{d.isoformat()},{value},2,1' for d in dates)
    return SimpleUploadedFile('load.csv',content.encode(),content_type='text/csv')


@pytest.mark.parametrize('kind',['duplicate','missing','naive','units','nonfinite'])
def test_bad_csv_rejected(setup,kind):
    client,_,sites=setup
    assert client.post(f'/api/sites/{sites[0].id}/load-profile/import',{'file':make_csv(kind)},format='multipart').status_code==400


def test_valid_csv_becomes_daily_template(setup):
    client,_,sites=setup
    r=client.post(f'/api/sites/{sites[0].id}/load-profile/import',{'file':make_csv()},format='multipart')
    assert r.status_code==200,r.data
    run=client.post(f'/api/sites/{sites[0].id}/optimization-runs',{'mode':'simulated'},format='json')
    assert run.status_code==201,run.data
    assert run.data['demand_source']=='csv'
    assert run.data['metrics']['requested_kwh']==pytest.approx(96)


def test_weather_failure_cache_policy(setup):
    _,_,sites=setup;s=sites[0]
    with patch('grid.weather.requests.get',side_effect=requests.ConnectionError('offline')):
        with pytest.raises(ValidationError):forecast(s)
        store_weather(s,simulated_weather(horizon_start(s.timezone)),'open_meteo')
        assert forecast(s)['cached'] is True
        s.weather.update(retrieved_at=timezone.now()-timedelta(hours=7))
        with pytest.raises(ValidationError):forecast(s)


def test_portfolio_cohorts_and_stress_assessment(setup):
    client,users,sites=setup
    r=svc.optimize(sites[0],users['admin'])
    result=client.get('/api/portfolio/reliability')
    assert result.status_code==200
    assert result.data['sites'][0]['reliability_status']=='amber'
    assert result.data['cohorts'][0]['weighted_critical_service_pct']==pytest.approx(100,abs=.001)
    pack=client.post('/api/portfolio/resilience-runs',{},format='json')
    assert pack.status_code==201 and len(pack.data['results'])==7
    assert m.ScenarioRun.objects.filter(baseline=r).count()==6
    assert client.get('/api/portfolio/reliability').data['sites'][0]['stress_tested']
