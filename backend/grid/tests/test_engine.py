from copy import deepcopy
import pandas as pd
import pytest
from grid.defaults import default_configuration, daily_shape
from grid.energy import solar_power, wind_power, simulated_weather
from grid.optimizer import solve
from grid.validation import validate_configuration
from rest_framework.exceptions import ValidationError


def snapshot():
    c=default_configuration()
    c['battery'].update(capacity_kwh=100,min_soc=20,max_soc=95,reserve_soc=20,max_charge_kw=30,max_discharge_kw=30,
                        replacement_cost=600000,lifetime_throughput_kwh=300000)
    c['generator'].update(capacity_kw=20,min_power_kw=0,fuel_slope=.246,fuel_intercept=.84,start_cost=0)
    c['policy'].update(terminal_soc=20,curtailment_penalty=0,renewable_shortfall_penalty=0)
    c['flexible_loads']=[]
    return {'configuration':c,'configuration_version':1,'site':{'timezone':'UTC'},
            'state':{'soc_pct':20,'generator_available':True,'generator_on':False,'fuel_l':1000,'demand_multiplier':1},
            'inputs':[{'timestamp':(pd.Timestamp('2025-01-15',tz='UTC')+pd.Timedelta(hours=t)).isoformat(),
                       'critical_kw':2.,'normal_kw':3.,'solar_available':0.,'wind_available':0.} for t in range(24)]}


def check_balance(result, c):
    assert result['status'] in ['optimal','feasible'], result
    prev=None
    for row in result['intervals']:
        assert abs(row['solar_used']+row['wind_used']+row['battery_discharge']+row['diesel_power']-row['served_load']-row['battery_charge']) < .001
        assert c['battery']['min_soc']-1e-5 <= row['battery_soc'] <= c['battery']['max_soc']+1e-5
        assert row['battery_charge']*row['battery_discharge'] < 1e-5
        assert row['solar_used'] <= row['solar_available']+1e-5
        assert row['wind_used'] <= row['wind_available']+1e-5
        expected=row['soc_start']+(row['battery_charge']*c['battery']['charge_efficiency']-row['battery_discharge']/c['battery']['discharge_efficiency'])/c['battery']['capacity_kwh']*100
        assert abs(expected-row['battery_soc'])<.001
        if prev is not None: assert abs(prev-row['soc_start'])<.001
        prev=row['battery_soc']
    assert result['intervals'][-1]['battery_soc']>=c['policy']['terminal_soc']-1e-5


def test_reference_shape_exact_energy_and_peak():
    shape=daily_shape(876.41,101)
    assert sum(shape)==pytest.approx(876.41,abs=1e-9)
    assert max(shape)==pytest.approx(101)
    assert shape[18]==101


@pytest.mark.parametrize('daily,peak',[(240,10),(20,20),(180,15),(876.41,101)])
def test_shape_extremes(daily,peak):
    a=daily_shape(daily,peak)
    assert sum(a)==pytest.approx(daily)
    assert max(a)<=peak+1e-9 and min(a)>=0


def test_solar_dark_and_capacity():
    weather=simulated_weather(pd.Timestamp('2025-01-15',tz='UTC'))
    result=solar_power(weather,default_configuration()['solar'],27.2297,93.3412)
    assert all(0<=v<=600 for v in result)
    assert any(v>0 for v in result)
    assert all(v==0 for v,r in zip(result,weather) if r['ghi']==0)


def test_wind_curve_boundaries():
    c=default_configuration()['wind'];c['hub_height_m']=10
    assert wind_power(2,c)==0
    assert wind_power(3,c)==0
    assert wind_power(7.5,c)==pytest.approx(50)
    assert wind_power(12,c)==100
    assert wind_power(24.99,c)==100
    assert wind_power(25,c)==0


def test_fuel_hand_calculation():
    s=snapshot();s['configuration']['battery'].update(max_charge_kw=0,max_discharge_kw=0)
    for t,r in enumerate(s['inputs']): r.update(critical_kw=8 if t<2 else 0,normal_kw=0)
    result=solve(s);check_balance(result,s['configuration'])
    assert result['metrics']['diesel_litres']==pytest.approx(5.616,abs=.001)
    assert result['metrics']['fuel_cost_inr']==pytest.approx(505.44,abs=.1)


def test_sunny_day_charges_storage_and_limits_diesel():
    s=snapshot()
    for t,row in enumerate(s['inputs']): row['solar_available']=25 if 7<=t<=17 else 0
    result=solve(s);check_balance(result,s['configuration'])
    assert sum(r['battery_charge'] for r in result['intervals'])>0
    dark=deepcopy(s)
    for r in dark['inputs']: r['solar_available']=0
    assert result['metrics']['diesel_litres']<solve(dark)['metrics']['diesel_litres']
    assert result['metrics']['battery_wear_cost_inr']==pytest.approx(result['metrics']['battery_discharge_kwh']*2)


def test_critical_has_priority_even_with_extreme_renewable_penalty():
    s=snapshot();s['configuration']['generator']['capacity_kw']=3
    s['configuration']['policy']['renewable_shortfall_penalty']=1e8
    s['configuration']['battery'].update(max_charge_kw=0,max_discharge_kw=0)
    result=solve(s);check_balance(result,s['configuration'])
    assert result['metrics']['critical_unserved_kwh']<.001
    assert result['metrics']['normal_unserved_kwh']>0
    assert any('Normal demand' in d for d in result['diagnostics'])
    assert result['metrics']['renewable_shortfall_kwh']>0


def test_generator_unavailable_reports_shortage():
    s=snapshot();s['state']['generator_available']=False
    result=solve(s);check_balance(result,s['configuration'])
    assert result['metrics']['critical_unserved_kwh']==pytest.approx(48)
    assert result['metrics']['reliability_status']=='red'
    assert result['next_action']['action']=='CRITICAL_SHORTAGE'


def test_flexible_windows_and_unfinished_work_reported():
    s=snapshot()
    s['configuration']['flexible_loads']=[{'name':'Pump','power_kw':5,'required_kwh':10,'start_hour':10,'end_hour':14}]
    for t,r in enumerate(s['inputs']): r['solar_available']=30 if 10<=t<14 else 0
    result=solve(s);check_balance(result,s['configuration'])
    assert sum(r['flexible_load_scheduled'] for r in result['intervals'])==pytest.approx(10,abs=.001)
    assert all(r['flexible_load_scheduled']<.001 for t,r in enumerate(result['intervals']) if t not in range(10,14))
    bad=solve(s,{'demand_multiplier':3})
    assert bad['metrics']['flexible_unserved_kwh']>=10-.001


def test_invalid_terminal_reserve_returns_no_plan():
    s=snapshot();s['state']['generator_available']=False;s['configuration']['policy']['terminal_soc']=90
    result=solve(s)
    assert result['status']=='infeasible'
    assert result['intervals']==[] and result['diagnostics']


def test_outage_hours_starts_and_fuel_limits():
    s=snapshot();s['state']['fuel_l']=15;s['configuration']['policy']['max_starts']=1
    result=solve(s,{'outage_start':10,'outage_end':14});check_balance(result,s['configuration'])
    assert result['metrics']['diesel_litres']<=15.001
    assert result['metrics']['generator_starts']<=1
    assert all(result['intervals'][t]['diesel_power']==0 for t in range(10,14))


def test_scenario_does_not_mutate_snapshot():
    s=snapshot();before=deepcopy(s)
    solve(s,{'solar_multiplier':.5,'demand_multiplier':1.25,'starting_soc':25})
    assert s==before


def test_scenario_availability_cannot_exceed_installed_capacity():
    s=snapshot();s['configuration']['solar']['capacity_kw']=10;s['configuration']['wind']['capacity_kw']=5
    for r in s['inputs']:r.update(solar_available=9,wind_available=4)
    result=solve(s,{'solar_multiplier':3,'wind_multiplier':3})
    assert all(r['solar_available']<=10 and r['wind_available']<=5 for r in result['intervals'])


def test_half_hour_history_respects_complete_operating_windows():
    s=snapshot();s['site']['timezone']='Asia/Kolkata'
    s['configuration']['flexible_loads']=[{'name':'Pump','power_kw':10,'required_kwh':20,'start_hour':9,'end_hour':12}]
    result=solve(s,{'outage_start':10,'outage_end':11})
    for r in result['intervals']:
        t=pd.Timestamp(r['timestamp']).tz_convert('Asia/Kolkata');h=t.hour+t.minute/60
        if r['flexible_load_scheduled']>.001: assert 9<=h and h+1<=12
        if h<11 and h+1>10:assert r['diesel_power']<.001


@pytest.mark.parametrize('key,value',[('charge_efficiency',0),('min_soc',99),('capacity_kwh',float('nan'))])
def test_bad_battery_configuration_rejected(key,value):
    c=default_configuration();c['battery'][key]=value
    with pytest.raises(ValidationError):validate_configuration(c)


def test_infeasible_flexible_window_rejected():
    c=default_configuration();c['flexible_loads'][0]['power_kw']=1
    with pytest.raises(ValidationError):validate_configuration(c)
