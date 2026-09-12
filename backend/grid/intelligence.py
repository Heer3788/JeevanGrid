"""Reproducible, read-only analysis of saved inputs. All values are projections."""
from copy import deepcopy
import math
import pandas as pd


def effective_inputs(snapshot):
    c, state = snapshot['configuration'], snapshot['state']
    o = snapshot.get('overrides', {})
    factor = state.get('demand_multiplier', 1) * o.get('demand_multiplier', 1)
    rows = deepcopy(snapshot['inputs'])
    for r in rows:
        r['critical_required'] = r['critical_kw'] * factor
        r['normal_required'] = r['normal_kw'] * factor
        for source in ['solar', 'wind']:
            r[source + '_available'] = min(c[source]['capacity_kw'], r[source + '_available'] * o.get(source + '_multiplier', 1))
    return rows, factor


def reactive_dispatch(snapshot):
    """Renewables, battery to operating reserve, then diesel; tasks run ASAP.

    No future resource information is used in an interval's decision. Unfinished
    task energy is retried inside its window. Terminal SOC is reported, not forced.
    """
    c, state = snapshot['configuration'], snapshot['state']
    b, g, policy = c['battery'], c['generator'], c['policy']
    o = snapshot.get('overrides', {})
    initial = o.get('starting_soc', state['soc_pct'])
    if not b['min_soc'] <= initial <= b['max_soc']:
        return {'status': 'invalid', 'intervals': [], 'metrics': {}}
    rows, factor = effective_inputs(snapshot)
    if len(rows) != 24:
        return {'status': 'invalid', 'intervals': [], 'metrics': {}}
    energy = initial / 100 * b['capacity_kwh']
    floor = max(b['min_soc'], b['reserve_soc']) / 100 * b['capacity_kwh']
    ceiling = b['max_soc'] / 100 * b['capacity_kwh']
    fuel_left = state['fuel_l']
    previous = int(state.get('generator_on', False))
    starts_used = 0
    remaining = [f['required_kwh'] * factor for f in c['flexible_loads']]
    result = []
    for r in rows:
        local = pd.Timestamp(r['timestamp']).tz_convert(snapshot['site']['timezone'])
        h = local.hour + local.minute / 60 + local.second / 3600
        overlap = [local.hour] + ([(local.hour + 1) % 24] if h % 1 else [])
        tasks = [min(f['power_kw'], remaining[j]) if f['start_hour'] <= h and h + 1 <= f['end_hour'] else 0.
                 for j, f in enumerate(c['flexible_loads'])]
        required = r['critical_required'] + r['normal_required'] + sum(tasks)
        available = r['solar_available'] + r['wind_available']
        start_energy = energy
        discharge = min(max(0, required - available), b['max_discharge_kw'], max(0, energy - floor) * b['discharge_efficiency'])
        charge_room = min(b['max_charge_kw'], max(0, ceiling - energy) / b['charge_efficiency'])
        deficit = max(0, required - available - discharge)
        allowed = (state['generator_available'] and g['capacity_kw'] > 0
                   and all(x in policy['allowed_generator_hours'] for x in overlap)
                   and not any(o.get('outage_start', 24) <= x < o.get('outage_end', 24) for x in overlap)
                   and (previous or starts_used < policy['max_starts']))
        max_fuel_power = (max(0, (fuel_left - g['fuel_intercept']) / g['fuel_slope'])
                          if g['fuel_slope'] > 0 else g['capacity_kw'] if fuel_left >= g['fuel_intercept'] else 0)
        diesel = min(g['capacity_kw'], max(deficit, g['min_power_kw']), max_fuel_power) if allowed and deficit > 1e-8 else 0.
        if diesel < g['min_power_kw'] - 1e-8 or fuel_left < g['fuel_intercept']:
            diesel = 0.
        # Minimum generator loading may displace battery discharge. Any excess
        # can charge storage; a generator that cannot stably load stays off.
        if diesel > 0:
            if diesel > max(0, required - available) + charge_room + 1e-8:
                diesel = 0.
            else:
                discharge = min(discharge, max(0, required - available - diesel))
        on = int(diesel > 1e-8)
        start = int(on and not previous)
        starts_used += start
        fuel = g['fuel_slope'] * diesel + g['fuel_intercept'] * on
        fuel_left = max(0, fuel_left - fuel)
        supply = available + diesel + discharge
        served_c = min(r['critical_required'], supply)
        supply -= served_c
        served_n = min(r['normal_required'], supply)
        supply -= served_n
        served_tasks = []
        for j, power in enumerate(tasks):
            served = min(power, max(0, supply))
            served_tasks.append({'name': c['flexible_loads'][j]['name'], 'power_kw': served})
            remaining[j] = max(0, remaining[j] - served)
            supply -= served
        charge = min(max(0, supply), charge_room) if discharge < 1e-8 else 0.
        load = served_c + served_n + sum(x['power_kw'] for x in served_tasks)
        renewable_used = max(0, load + charge - diesel - discharge)
        solar = min(r['solar_available'], renewable_used)
        wind = max(0, renewable_used - solar)
        energy += charge * b['charge_efficiency'] - discharge / b['discharge_efficiency']
        result.append({**r, 'solar_used': solar, 'wind_used': wind, 'battery_charge': charge,
                       'battery_discharge': discharge, 'battery_soc': energy / b['capacity_kwh'] * 100,
                       'soc_start': start_energy / b['capacity_kwh'] * 100, 'diesel_power': diesel,
                       'diesel_on': on, 'diesel_start': start, 'diesel_litres': fuel,
                       'critical_unserved': r['critical_required'] - served_c,
                       'normal_unserved': r['normal_required'] - served_n,
                       'served_load': load, 'flexible_load_scheduled': sum(x['power_kw'] for x in served_tasks),
                       'flexible_tasks': served_tasks, 'renewable_curtailment': max(0, available - renewable_used)})
        previous = on
    total = lambda key: sum(r[key] for r in result)
    pct = lambda a, b: 100 * a / b if b > 1e-9 else None
    critical = total('critical_required')
    served = total('served_load')
    required = critical + total('normal_required') + sum(f['required_kwh'] * factor for f in c['flexible_loads'])
    renewable = total('solar_used') + total('wind_used')
    price = state.get('diesel_price', g['diesel_price']) * o.get('fuel_price_multiplier', 1)
    fuel_cost = total('diesel_litres') * price
    start_cost = starts_used * g['start_cost']
    wear = total('battery_discharge') * b['replacement_cost'] / b['lifetime_throughput_kwh']
    metrics = {'critical_required_kwh': critical, 'critical_unserved_kwh': total('critical_unserved'),
               'critical_load_served_pct': pct(critical - total('critical_unserved'), critical),
               'normal_unserved_kwh': total('normal_unserved'), 'flexible_unserved_kwh': sum(remaining),
               'served_kwh': served, 'requested_kwh': required, 'unserved_kwh': max(0, required - served),
               'total_energy_served_pct': pct(served, required),
               'renewable_share_pct': pct(renewable, renewable + total('diesel_power')),
               'diesel_litres': total('diesel_litres'), 'fuel_cost_inr': fuel_cost,
               'generator_starts': starts_used, 'generator_hours': total('diesel_on'),
               'generator_start_cost_inr': start_cost, 'battery_wear_cost_inr': wear,
               'cash_cost_inr': fuel_cost + start_cost, 'dispatch_cost_inr': fuel_cost + start_cost + wear,
               'emissions_kg_co2': total('diesel_litres') * g['emissions_factor'],
               'minimum_soc_pct': min([initial] + [r['battery_soc'] for r in result]),
               'terminal_soc_pct': result[-1]['battery_soc'],
               'reserve_compliance_pct': sum(r['battery_soc'] >= b['reserve_soc'] - 1e-5 for r in result) / 24 * 100,
               'terminal_reserve_met': result[-1]['battery_soc'] >= policy['terminal_soc'] - 1e-5,
               'cost_per_kwh': (fuel_cost + start_cost + wear) / served if served > 1e-9 else None,
               'diesel_l_per_kwh': total('diesel_litres') / served if served > 1e-9 else None,
               'basis': 'projected'}
    return {'status': 'simulated', 'intervals': result, 'metrics': metrics}


def analyze_run(run, now=None):
    snapshot = run.snapshot
    dispatch = list(run.intervals.values_list('data', flat=True))
    intervals, factor = effective_inputs(snapshot)
    weather = {pd.Timestamp(r['timestamp']).value: r for r in snapshot.get('weather', {}).get('intervals', [])}
    dispatched = {pd.Timestamp(r['timestamp']).value: r for r in dispatch}
    dataset = []
    for row in intervals:
        key = pd.Timestamp(row['timestamp']).value
        w, d = weather.get(key, {}), dispatched.get(key, {})
        missing = [k for k in ['ghi', 'temperature', 'wind_speed'] if not isinstance(w.get(k), (int, float)) or not math.isfinite(w[k])]
        dataset.append({**row, **d, 'ghi': w.get('ghi'), 'temperature': w.get('temperature'),
                        'wind_speed': w.get('wind_speed'), 'missing_fields': missing,
                        'weather_source': snapshot.get('weather', {}).get('source'),
                        'demand_source': snapshot.get('demand_source'), 'dispatch_available': bool(d)})
    notes = []
    retrieved = snapshot.get('weather', {}).get('retrieved_at')
    age = max(0, ((now or pd.Timestamp.now(tz='UTC')) - pd.Timestamp(retrieved)).total_seconds() / 3600) if retrieved else None
    source = snapshot.get('weather', {}).get('source')
    stale = source == 'open_meteo' and (age is None or age > 6)
    if stale: notes.append('This saved forecast is over six hours old. Refresh and optimize before using it for a new decision.')
    if snapshot['configuration_version'] != run.site.configuration_version: notes.append('Site configuration or readings have changed since this run.')
    if any(r['missing_fields'] for r in dataset): notes.append('Some weather fields are missing. Inspect the flagged rows.')
    if len(intervals) != 24: notes.append('The saved inputs do not contain a complete 24-hour horizon.')
    if source == 'simulated': notes.append('Weather is simulated. Outcomes demonstrate model behaviour, not measured performance.')
    if source == 'nasa_power': notes.append('Historical weather replay uses hindsight; it does not validate forecast accuracy.')
    state_stamp = snapshot['state'].get('timestamp')
    result = {'analysis_version': 'reactive-v1', 'run_id': run.pk, 'dataset': dataset,
              'trust': {'weather_age_hours': age, 'forecast_stale': stale, 'warnings': notes,
                        'missing_weather_rows': sum(bool(r['missing_fields']) for r in dataset),
                        'state_timestamp': state_stamp, 'row_count': len(dataset)},
              'explanation': [], 'comparison': None}
    if run.status not in ['optimal', 'feasible'] or not dispatch:
        result['explanation'] = run.diagnostics
        return result
    c, state = snapshot['configuration'], snapshot['state']
    b, g, p = c['battery'], c['generator'], c['policy']
    metrics = run.metrics
    notes = result['explanation']
    start = next((r for r in dispatch if r['diesel_start']), None)
    if start:
        time = pd.Timestamp(start['timestamp']).tz_convert(snapshot['site']['timezone']).strftime('%H:%M')
        notes.append(f"At {time}, scheduled demand is {start['critical_required'] + start['normal_required'] + start['flexible_load_scheduled']:.1f} kW and available renewables are {start['solar_available'] + start['wind_available']:.1f} kW. The plan schedules {start['diesel_power']:.1f} kW of backup.")
    else:
        notes.append(f"The plan uses {metrics['diesel_litres']:.1f} L of diesel and requires no new generator start.")
    notes.append(f"Battery minimum is {metrics['minimum_soc_pct']:.1f}%. Safety floor: {b['min_soc']:g}%; operating reserve: {b['reserve_soc']:g}%; required ending SOC: {p['terminal_soc']:g}%.")
    price = state.get('diesel_price', g['diesel_price']) * snapshot.get('overrides', {}).get('fuel_price_multiplier', 1)
    notes.append(f"Fuel is costed at INR {price:.2f}/L. Battery wear is INR {b['replacement_cost'] / b['lifetime_throughput_kwh']:.2f} per discharged kWh. These values come from the saved site inputs.")
    notes.append('Critical service is optimized first, followed by normal service, flexible work and operating cost. These observations describe the solved schedule; they are not causal attributions to individual constraints.')
    reactive = reactive_dispatch(snapshot)
    rm = reactive['metrics']
    if not rm: return result
    differences = {k: metrics[k] - v for k, v in rm.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(metrics.get(k), (int, float))}
    cautions = []
    service_equal = all(abs(metrics[k] - rm[k]) <= .001 for k in ['critical_unserved_kwh', 'normal_unserved_kwh', 'flexible_unserved_kwh'])
    terminal_equal = abs(metrics['terminal_soc_pct'] - rm['terminal_soc_pct']) <= .1
    if not service_equal: cautions.append('Served demand differs. Cost and fuel differences are not like-for-like savings; compare service first.')
    if not terminal_equal: cautions.append('Ending battery SOC differs. Part of the cost difference reflects energy left in storage.')
    if not rm['terminal_reserve_met']: cautions.append('The reactive controller misses the terminal reserve. It has no end-of-day look-ahead.')
    enhanced_rules = g.get('min_up_hours',1)>1 or g.get('min_down_hours',1)>1 or g.get('ramp_kw_per_hour',g['capacity_kw'])<g['capacity_kw'] or 'live_session_id' in snapshot
    if enhanced_rules: cautions.append('The illustrative reactive policy does not implement the live model’s minimum run/cooldown, ramp constraints or carried flexible-job deadlines. This comparison is not like-for-like.')
    result['comparison'] = {'controller': 'Renewables → battery to operating reserve → diesel; flexible work runs as early as possible.',
                            'baseline': reactive, 'optimized_metrics': metrics, 'delta': differences,
                            'like_for_like': service_equal and terminal_equal and rm['terminal_reserve_met'] and not enhanced_rules,
                            'warnings': cautions, 'basis': 'Same frozen inputs; illustrative reactive policy, not measured site operation.'}
    flex_equal = abs(metrics['flexible_unserved_kwh'] - rm['flexible_unserved_kwh']) <= .001
    result['comparison']['flexible_energy_shifted_kwh'] = (sum(abs(a['flexible_load_scheduled'] - b['flexible_load_scheduled']) for a, b in zip(dispatch, reactive['intervals'])) / 2 if flex_equal else None)
    return result
