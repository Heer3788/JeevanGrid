from copy import deepcopy
import random
import pytest
from grid.intelligence import reactive_dispatch, analyze_run
from grid.tests.test_engine import snapshot
from grid.tests.test_api import setup
from grid import models as m, services as svc


def assert_physics(s, result):
    b, g, p = (s['configuration'][k] for k in ['battery', 'generator', 'policy'])
    for r in result['intervals']:
        assert r['solar_used'] + r['wind_used'] + r['diesel_power'] + r['battery_discharge'] == pytest.approx(r['served_load'] + r['battery_charge'], abs=.001)
        assert r['battery_charge'] * r['battery_discharge'] < 1e-6
        assert b['min_soc'] - 1e-6 <= r['battery_soc'] <= b['max_soc'] + 1e-6
        expected = r['soc_start'] + (r['battery_charge'] * b['charge_efficiency'] - r['battery_discharge'] / b['discharge_efficiency']) / b['capacity_kwh'] * 100
        assert r['battery_soc'] == pytest.approx(expected)
        assert r['solar_used'] <= r['solar_available'] + 1e-6
        assert r['wind_used'] <= r['wind_available'] + 1e-6
        if r['diesel_on']: assert g['min_power_kw'] <= r['diesel_power'] + 1e-6 <= g['capacity_kw'] + 1e-6
    assert result['metrics']['diesel_litres'] <= s['state']['fuel_l'] + 1e-6
    assert result['metrics']['generator_starts'] <= p['max_starts']


def test_reactive_hand_calculated_fuel_and_priority():
    s = snapshot()
    s['configuration']['battery'].update(max_charge_kw=0, max_discharge_kw=0)
    for i, r in enumerate(s['inputs']): r.update(critical_kw=8 if i < 2 else 0, normal_kw=0)
    original = deepcopy(s)
    result = reactive_dispatch(s)
    assert result['metrics']['diesel_litres'] == pytest.approx(5.616)
    assert result['metrics']['fuel_cost_inr'] == pytest.approx(505.44)
    assert result['metrics']['critical_load_served_pct'] == pytest.approx(100)
    assert s == original
    assert_physics(s, result)
    s['configuration']['generator']['capacity_kw'] = 3
    result = reactive_dispatch(s)
    assert result['metrics']['critical_unserved_kwh'] == pytest.approx(10)


def test_reactive_asap_tasks_and_shortage():
    s=snapshot()
    s['configuration']['flexible_loads']=[{'name':'Pump','required_kwh':8,'power_kw':4,'start_hour':9,'end_hour':12}]
    result=reactive_dispatch(s)
    assert [r['flexible_load_scheduled'] for r in result['intervals'][9:12]]==pytest.approx([4,4,0])
    s['state']['generator_available']=False
    result=reactive_dispatch(s)
    assert result['metrics']['flexible_unserved_kwh']==8
    assert result['metrics']['critical_unserved_kwh']==48
    assert_physics(s,result)


def test_reactive_outages_and_zero_slope():
    s=snapshot()
    s['configuration']['generator']['fuel_slope']=0
    s['overrides']={'outage_start':18,'outage_end':24,'solar_multiplier':.5,'starting_soc':25,'demand_multiplier':1.25}
    result=reactive_dispatch(s)
    assert all(r['diesel_power']==0 for r in result['intervals'][18:])
    assert result['metrics']['critical_required_kwh']==60
    assert_physics(s,result)


@pytest.mark.parametrize('seed',range(15))
def test_reactive_physical_bounds_with_varied_resources(seed):
    rng=random.Random(seed);s=snapshot()
    s['state'].update(soc_pct=rng.uniform(20,95),fuel_l=rng.uniform(0,100))
    s['configuration']['battery']['reserve_soc']=30
    s['configuration']['generator']['min_power_kw']=rng.uniform(0,20)
    s['configuration']['policy']['max_starts']=rng.randrange(0,6)
    for r in s['inputs']: r.update(solar_available=rng.uniform(0,30),wind_available=rng.uniform(0,10),critical_kw=rng.uniform(0,20),normal_kw=rng.uniform(0,30))
    result=reactive_dispatch(s)
    assert_physics(s,result)
    assert result['metrics']['dispatch_cost_inr']==pytest.approx(result['metrics']['fuel_cost_inr']+result['metrics']['generator_start_cost_inr']+result['metrics']['battery_wear_cost_inr'])


@pytest.mark.django_db
def test_analysis_permissions_snapshot_stability_and_scenario_dataset(setup):
    client,users,sites=setup
    run=svc.optimize(sites[0],users['admin'])
    saved=deepcopy(run.snapshot)
    url=f'/api/optimization-runs/{run.id}/analysis'
    response=client.get(url)
    assert response.status_code==200
    assert len(response.data['dataset'])==24
    assert response.data['comparison']['baseline']['metrics']['basis']=='projected'
    first=deepcopy(response.data['comparison'])
    client.force_authenticate(users['outsider'])
    assert client.get(url).status_code==404
    assert client.get(f'/api/optimization-runs/{run.id}/scenarios').status_code==404
    client.force_authenticate(users['operator'])
    assert client.get(url).status_code==200
    other=svc.optimize(sites[1],users['admin'])
    assert client.get(f'/api/optimization-runs/{other.id}/analysis').status_code==404
    config=deepcopy(svc.configuration(sites[0]));config['generator']['diesel_price']=999
    svc.save_configuration(sites[0],config)
    response=client.get(url)
    assert response.data['comparison']==first
    assert any('changed' in w for w in response.data['trust']['warnings'])
    run.refresh_from_db();assert run.snapshot==saved
    scenario=svc.simulate(sites[0],users['admin'],run,'cloudy',{'solar_multiplier':.5,'demand_multiplier':1.25})
    report=analyze_run(scenario)
    assert report['dataset'][0]['critical_required']==pytest.approx(saved['inputs'][0]['critical_kw']*1.25)
    assert report['dataset'][0]['solar_available']==pytest.approx(saved['inputs'][0]['solar_available']*.5)
    scenarios=client.get(f'/api/optimization-runs/{run.id}/scenarios').data
    assert len(scenarios)==1 and scenarios[0]['baseline_id']==run.id


@pytest.mark.django_db
def test_comparison_warns_about_service_and_storage_differences(setup):
    client,users,sites=setup
    s=snapshot();s['state']['soc_pct']=95;s['configuration']['battery']['reserve_soc']=90
    s['state']['generator_available']=False
    from grid.optimizer import solve
    run=svc.persist_run(sites[0],users['admin'],'simulated',s,solve(s))
    comparison=analyze_run(run)['comparison']
    assert not comparison['like_for_like']
    assert any('Served demand differs' in w for w in comparison['warnings'])
    assert any('Ending battery SOC differs' in w for w in comparison['warnings'])
