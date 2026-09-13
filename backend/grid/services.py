from copy import deepcopy
from datetime import timedelta
import pandas as pd
from django.db import transaction
from django.utils import timezone
from . import models as m
from .defaults import default_configuration, daily_shape, STUDY
from .energy import solar_power, wind_power
from .optimizer import solve
from .validation import validate_configuration, validate_overrides, fail
from .weather import get_weather

CONFIG_MODELS = {'solar': m.SolarConfig, 'wind': m.WindConfig, 'battery': m.BatteryConfig,
                 'generator': m.GeneratorConfig, 'policy': m.SitePolicy}


def configuration(site):
    c = {key: getattr(site, key).data for key in CONFIG_MODELS}
    c['generator'] = {**default_configuration()['generator'], **c['generator']}
    c['demand'] = site.load_profile.data
    c['flexible_loads'] = list(site.flexible_loads.values_list('data', flat=True))
    return c


@transaction.atomic
def save_configuration(site, data, increment=True):
    c = validate_configuration(data)
    existing = m.LoadProfile.objects.filter(site=site).first()
    changed_demand = existing and existing.data != c['demand']
    for key, cls in CONFIG_MODELS.items(): cls.objects.update_or_create(site=site, defaults={'data': c[key]})
    profile, _ = m.LoadProfile.objects.update_or_create(site=site, defaults={'data': c['demand'], 'provenance': c['demand']['provenance']})
    if changed_demand: profile.intervals.all().delete()
    site.flexible_loads.all().delete()
    m.DispatchableLoad.objects.bulk_create([m.DispatchableLoad(site=site, data=f) for f in c['flexible_loads']])
    if increment:
        site.configuration_version += 1
        site.save(update_fields=['configuration_version'])


def current_state(site, c):
    reading = site.readings.first()
    base = {'soc_pct': 60, 'fuel_l': c['generator']['available_fuel_l'], 'generator_available': True,
            'generator_on': False, 'event': '', 'demand_multiplier': 1, 'diesel_price': c['generator']['diesel_price']}
    if reading: base.update(reading.data)
    base['provenance'] = reading.provenance if reading else 'simulated'
    base['timestamp'] = reading.timestamp.isoformat() if reading else None
    return base


def prepare_snapshot(site, mode, date=None, persist_weather=True):
    c = configuration(site)
    weather = get_weather(site, mode, date, persist=persist_weather)
    state = current_state(site, c)
    d = c['demand']
    shape = daily_shape(d['daily_kwh'], d['peak_kw'])
    uploaded = list(site.load_profile.intervals.all())
    lookup = {pd.Timestamp(r.timestamp).tz_convert(site.timezone).hour: r for r in uploaded}
    solar = solar_power(weather['intervals'], c['solar'], site.latitude, site.longitude)
    inputs = []
    for i, row in enumerate(weather['intervals']):
        hour = pd.Timestamp(row['timestamp']).tz_convert(site.timezone).hour
        if uploaded:
            load = lookup[hour]
            critical, normal = load.critical_kw, load.normal_kw
        else:
            critical = shape[hour]*d['critical_pct']/100
            normal = shape[hour]*(100-d['critical_pct']-d['flexible_pct'])/100
        inputs.append({'timestamp': row['timestamp'], 'critical_kw': critical, 'normal_kw': normal,
                       'solar_available': solar[i], 'wind_available': wind_power(row['wind_speed'], c['wind'])})
    return {'site': {'id': site.id, 'name': site.name, 'latitude': site.latitude, 'longitude': site.longitude, 'timezone': site.timezone},
            'configuration': c, 'configuration_version': site.configuration_version, 'state': state,
            'weather': weather, 'inputs': inputs, 'demand_source': site.load_profile.provenance,
            'demand_note': ('CSV reused as a local-hour daily template.' if site.load_profile.provenance == 'csv'
                            else 'Modelled appliance-based hourly template; see site inventory and assumptions.') if uploaded
                           else 'Deterministic demand shape; totals informed by study, intervals simulated.',
            'provenance': site.provenance}


@transaction.atomic
def persist_run(site, user, mode, snapshot, result):
    run = m.OptimizationRun.objects.create(site=site, created_by=user, mode=mode,
        configuration_version=snapshot['configuration_version'], snapshot=snapshot, status=result['status'],
        metrics=result['metrics'], next_action=result['next_action'], diagnostics=result['diagnostics'], solve_seconds=result['solve_seconds'])
    m.DispatchInterval.objects.bulk_create([m.DispatchInterval(run=run, timestamp=d['timestamp'], data=d) for d in result['intervals']])
    if mode not in ['scenario', 'live_simulation'] and result['status'] in ['optimal', 'feasible']:
        m.PlanAssessment.objects.create(run=run)
    return run


def optimize(site, user, mode='simulated', date=None):
    snapshot = prepare_snapshot(site, mode, date)
    return persist_run(site, user, mode, snapshot, solve(snapshot))


def simulate(site, user, baseline, name, overrides):
    if baseline.site_id != site.id or baseline.mode == 'scenario': fail('Select an original baseline belonging to this site.')
    if baseline.status not in ['optimal', 'feasible']: fail('Simulation needs a valid baseline plan.')
    overrides = validate_overrides(overrides)
    snapshot = deepcopy(baseline.snapshot)
    snapshot['overrides'] = overrides
    result = solve(snapshot, overrides)
    with transaction.atomic():
        run = persist_run(site, user, 'scenario', snapshot, result)
        m.ScenarioRun.objects.create(baseline=baseline, result=run, name=name[:120], overrides=overrides)
    return run


def run_summary(run, details=False):
    if not run: return None
    weather = run.snapshot.get('weather', {})
    data = {'id': run.pk, 'site_id': run.site_id, 'site_name': run.site.name, 'mode': run.mode,
            'created_at': run.created_at, 'configuration_version': run.configuration_version,
            'status': run.status, 'metrics': run.metrics, 'next_action': run.next_action,
            'diagnostics': run.diagnostics, 'solve_seconds': run.solve_seconds,
            'weather_source': weather.get('source'), 'weather_retrieved_at': weather.get('retrieved_at'),
            'horizon_start': run.snapshot.get('inputs', [{}])[0].get('timestamp'),
            'demand_source': run.snapshot.get('demand_source'), 'state_source': run.snapshot.get('state', {}).get('provenance'),
            'decisions': list(run.decisions.values('decision','reason','created_at','user__email'))}
    if run.mode == 'scenario':
        scenario = run.scenario
        data.update({'scenario_name': scenario.name, 'overrides': scenario.overrides, 'baseline_id': scenario.baseline_id,
                     'baseline_metrics': scenario.baseline.metrics,
                     'delta': {k: run.metrics[k]-v for k,v in scenario.baseline.metrics.items()
                               if isinstance(v, (float,int)) and isinstance(run.metrics.get(k), (float,int))}})
    if details:
        data.update({'snapshot': run.snapshot, 'intervals': list(run.intervals.values_list('data', flat=True))})
    return data


def latest_plan(site):
    return site.runs.exclude(mode__in=['scenario', 'live_simulation']).first() or site.runs.exclude(mode='scenario').first()


def site_summary(site):
    run = latest_plan(site)
    return {'id': site.pk, 'name': site.name, 'state': site.state, 'district': site.district,
            'latitude': site.latitude, 'longitude': site.longitude, 'timezone': site.timezone,
            'archived': site.archived, 'configuration_version': site.configuration_version,
            'configuration_status': 'ready' if hasattr(site, 'solar') else 'incomplete',
            'operator_ids': list(site.assignments.values_list('user_id', flat=True)),
            'operators': list(site.assignments.values_list('user__email', flat=True)), 'latest_run': run_summary(run), 'provenance': site.provenance}


def reliability(site):
    from .assessment import preset_results
    baseline = latest_plan(site)
    data = site_summary(site)
    data.update({'reliability_status': 'red', 'assessment': 'No plan available', 'stress_tested': False, 'inputs_current': False})
    if not baseline: return data
    stale_config = baseline.configuration_version != site.configuration_version
    weather = baseline.snapshot['weather']
    forecast_old = weather['source'] == 'open_meteo' and timezone.now()-pd.Timestamp(weather['retrieved_at']).to_pydatetime() > timedelta(hours=6)
    if stale_config or forecast_old:
        data['assessment'] = 'Configuration changed; rerun the plan.' if stale_config else 'Forecast is stale; refresh it.'
        return data
    data['inputs_current'] = True
    if baseline.status not in ['optimal','feasible'] or baseline.metrics.get('critical_unserved_kwh', 1) > .001:
        data['assessment'] = 'Critical shortage or no feasible baseline.'
        return data
    scenarios = list(preset_results(baseline).values())
    assessment = m.PlanAssessment.objects.filter(run=baseline).first()
    data['assessment_state'] = assessment.status if assessment else 'not_started'
    data['assessment_error'] = assessment.error if assessment else ''
    data['stress_tested'] = len(scenarios) == 6
    risk = baseline.metrics.get('reserve_compliance_pct', 0) < 100
    risk |= any(x.result.status not in ['optimal','feasible'] or x.result.metrics.get('critical_unserved_kwh',1)>.001
                or x.result.metrics.get('reserve_compliance_pct',0)<100 for x in scenarios)
    data['reliability_status'] = 'amber' if risk or not data['stress_tested'] else 'green'
    data['assessment'] = 'Reserve/stress scenario risk.' if risk else 'Automatic checks pending or incomplete.' if not data['stress_tested'] else 'Baseline and six standard checks preserve critical supply and reserve.'
    data['scenario_count'] = len(scenarios)
    return data
