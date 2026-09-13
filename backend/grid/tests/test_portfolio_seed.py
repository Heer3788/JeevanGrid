from io import StringIO
import pandas as pd
import pytest
from django.core.management import call_command
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from grid import models as m, services as svc
from grid.energy import simulated_weather, solar_power
from grid.optimizer import solve
from grid.portfolio_seed import spec
from grid.validation import validate_configuration


def test_all_108_inventories_are_deterministic_and_reconcile():
    names, operators = set(), set()
    for i in range(108):
        s = spec(i)
        assert s == spec(i)
        c, rows = s['configuration'], s['intervals']
        validate_configuration(c)
        assert len(rows) == 24 and {r['hour'] for r in rows} == set(range(24))
        energy = sum(sum(r[k] for k in ['critical_kw','normal_kw','flexible_kw']) for r in rows)
        assert energy == pytest.approx(c['demand']['daily_kwh'])
        fixed = sum(x['daily_kwh'] for x in s['provenance']['inventory'])
        assert fixed + sum(t['required_kwh'] for t in c['flexible_loads']) == pytest.approx(energy, abs=.0001)
        assert c['battery']['max_charge_kw'] <= c['battery']['capacity_kwh']*.5 + .001
        assert c['battery']['max_discharge_kw'] <= c['battery']['capacity_kwh']*.5 + .001
        assert c['generator']['capacity_kw'] >= c['demand']['peak_kw']
        assert all(min(r['critical_kw'],r['normal_kw'],r['flexible_kw']) >= 0 for r in rows)
        assert c['wind']['capacity_kw'] == 0
        assert s['provenance']['site'] == 'simulated'
        names.add(s['name']); operators.add(s['operator_email'])
    assert len(names) == 108 and len(operators) == 27


@pytest.mark.parametrize('index', range(12))
def test_each_use_and_size_solves_and_balances(index):
    item = spec(index)
    c = item['configuration']
    weather = simulated_weather(pd.Timestamp('2026-09-14T00:00:00+05:30'))
    pv = solar_power(weather,c['solar'],item['latitude'],item['longitude'])
    inputs = [{'timestamp':w['timestamp'],'critical_kw':r['critical_kw'],'normal_kw':r['normal_kw'],
               'solar_available':pv[h],'wind_available':0} for h,(r,w) in enumerate(zip(item['intervals'],weather))]
    result = solve({'site':{'name':item['name'],'timezone':'Asia/Kolkata'},'configuration':c,
                    'state':item['reading'],'inputs':inputs})
    assert result['status'] in ['optimal','feasible'], result['diagnostics']
    assert len(result['intervals']) == 24
    for r in result['intervals']:
        supply = r['solar_used']+r['wind_used']+r['battery_discharge']+r['diesel_power']
        assert abs(supply-r['served_load']-r['battery_charge']) < .001
    assert result['metrics']['critical_load_served_pct'] == pytest.approx(100)


@pytest.mark.django_db
def test_seed_is_additive_and_preserves_edits_passwords_and_operator_scope():
    org = m.Organization.objects.create(name='JeevanGrid Demo Agency')
    admin = get_user_model().objects.create_user('admin-seed',password='test')
    m.UserRole.objects.create(user=admin,organization=org,role='admin')
    call_command('seed_portfolio',count=5,with_runs=True,stdout=StringIO())
    assert m.Site.objects.count() == 5 and m.LoadInterval.objects.count() == 120
    assert m.OptimizationRun.objects.count() == 5
    site = m.Site.objects.get(provenance__seed_index=0)
    operator = site.assignments.first().user
    operator.set_password('user-changed-password'); operator.save()
    site.name = 'User edited site'; site.save()
    ids = list(m.Site.objects.values_list('id',flat=True))
    run_ids = set(m.OptimizationRun.objects.values_list('id',flat=True))
    call_command('seed_portfolio',count=5,with_runs=True,stdout=StringIO())
    site.refresh_from_db(); operator.refresh_from_db()
    assert site.name == 'User edited site' and operator.check_password('user-changed-password')
    assert ids == list(m.Site.objects.values_list('id',flat=True))
    assert run_ids == set(m.OptimizationRun.objects.values_list('id',flat=True))
    snapshot = svc.prepare_snapshot(site,'simulated')
    assert 'CSV' not in snapshot['demand_note'] and snapshot['demand_source'] == 'simulated'
    from grid.forecasting import demo_dataset
    training = demo_dataset(site,svc.configuration(site))
    by_hour = {pd.Timestamp(r.timestamp).tz_convert(site.timezone).hour:r.critical_kw+r.normal_kw
               for r in site.load_profile.intervals.all()}
    assert len(training) == 2160
    for r in training:
        assert r['baseline_demand_kw'] == pytest.approx(by_hour[pd.Timestamp(r['timestamp']).tz_convert(site.timezone).hour])
    client = APIClient(); client.force_authenticate(operator)
    assert len(client.get('/api/sites').data) == 4
    forbidden = m.Site.objects.get(provenance__seed_index=4)
    assert client.get(f'/api/sites/{forbidden.pk}').status_code == 404
    assert client.put(f'/api/sites/{site.pk}/configuration',svc.configuration(site),format='json').status_code == 403
