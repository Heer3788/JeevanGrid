"""Pure, deterministic 24-hour dispatch model; no database or network calls."""
from copy import deepcopy
import time
import pandas as pd
import pulp as lp


def solve(snapshot, overrides=None):
    started = time.monotonic()
    s = deepcopy(snapshot)
    overrides = overrides or {}
    c = s['configuration']
    b, g, policy = c['battery'], c['generator'], c['policy']
    state = s['state']
    initial = overrides.get('starting_soc', state['soc_pct'])
    failed = lambda message, status='infeasible': {'status': status, 'metrics': {}, 'intervals': [],
                   'diagnostics': [message], 'next_action': {'action': 'REVIEW_CONFIGURATION', 'reason': message},
                   'solve_seconds': time.monotonic()-started}
    if not b['min_soc'] <= initial <= b['max_soc']:
        return failed('Starting SOC lies outside battery safety limits; correct the reading or scenario.')
    rows = s['inputs']
    if len(rows) != 24: return failed('Exactly 24 hourly input intervals are required.', 'failed')
    demand_factor = overrides.get('demand_multiplier', 1) * state.get('demand_multiplier', 1)
    price = state.get('diesel_price', g['diesel_price']) * overrides.get('fuel_price_multiplier', 1)
    critical = [r['critical_kw']*demand_factor for r in rows]
    normal = [r['normal_kw']*demand_factor for r in rows]
    solar = [min(c['solar']['capacity_kw'],r['solar_available']*overrides.get('solar_multiplier', 1)) for r in rows]
    wind = [min(c['wind']['capacity_kw'],r['wind_available']*overrides.get('wind_multiplier', 1)) for r in rows]
    local_times = [pd.Timestamp(r['timestamp']).tz_convert(s['site']['timezone']) for r in rows]
    hours = [t.hour for t in local_times]
    fractional_hours = [t.hour+t.minute/60+t.second/3600 for t in local_times]
    model = lp.LpProblem('JeevanGrid', lp.LpMinimize)
    def var(name, hi=None, binary=False, n=24):
        return lp.LpVariable.dicts(name, range(n), lowBound=0, upBound=hi, cat='Binary' if binary else 'Continuous')
    pv, wt = var('solar'), var('wind')
    ch, dis = var('charge', b['max_charge_kw']), var('discharge', b['max_discharge_kw'])
    energy = var('energy', n=25)
    on, starts, charging = var('diesel_on', binary=True), var('diesel_start', binary=True), var('charging_mode', binary=True)
    diesel, uc, un = var('diesel'), var('critical_unserved'), var('normal_unserved')
    flex_vars, flex_missed = [], []
    for j, f in enumerate(c['flexible_loads']):
        task = var(f'flex_{j}', f['power_kw'])
        missed = lp.LpVariable(f'flex_missed_{j}', lowBound=0)
        for t in range(24):
            if not (f['start_hour'] <= fractional_hours[t] and fractional_hours[t]+1 <= f['end_hour']): model += task[t] == 0
        model += lp.lpSum(task.values()) + missed == f['required_kwh'] * demand_factor
        flex_vars.append(task); flex_missed.append(missed)
    model += energy[0] == initial/100*b['capacity_kwh']
    for t in range(25):
        model += energy[t] >= b['min_soc']/100*b['capacity_kwh']
        model += energy[t] <= b['max_soc']/100*b['capacity_kwh']
    model += energy[24] >= policy['terminal_soc']/100*b['capacity_kwh']
    fuel = []
    for t in range(24):
        model += pv[t] <= solar[t]; model += wt[t] <= wind[t]
        model += ch[t] <= charging[t]*b['max_charge_kw']
        model += dis[t] <= (1-charging[t])*b['max_discharge_kw']
        model += energy[t+1] == energy[t] + ch[t]*b['charge_efficiency'] - dis[t]/b['discharge_efficiency']
        model += diesel[t] >= on[t]*g['min_power_kw']
        model += diesel[t] <= on[t]*g['capacity_kw']
        overlapping_hours = [hours[t]] + ([(hours[t]+1)%24] if fractional_hours[t] % 1 else [])
        outage = any(overrides.get('outage_start', 24) <= h < overrides.get('outage_end', 24) for h in overlapping_hours)
        if not state['generator_available'] or any(h not in policy['allowed_generator_hours'] for h in overlapping_hours) or outage:
            model += on[t] == 0
        previous = on[t-1] if t else int(state.get('generator_on', False))
        model += starts[t] >= on[t]-previous
        model += starts[t] <= on[t]
        model += starts[t] <= 1-previous
        model += uc[t] <= critical[t]; model += un[t] <= normal[t]
        model += pv[t]+wt[t]+dis[t]+diesel[t] == critical[t]-uc[t]+normal[t]-un[t]+lp.lpSum(f[t] for f in flex_vars)+ch[t]
        fuel.append(g['fuel_slope']*diesel[t]+g['fuel_intercept']*on[t])
    model += lp.lpSum(starts.values()) <= policy['max_starts']
    model += lp.lpSum(fuel) <= state['fuel_l']
    renewables = lp.lpSum(pv.values())+lp.lpSum(wt.values())
    shortfall = lp.LpVariable('renewable_shortfall', lowBound=0)
    model += shortfall >= policy['renewable_target_pct']/100*(renewables+lp.lpSum(diesel.values())) - renewables
    wear = b['replacement_cost']/b['lifetime_throughput_kwh']
    cash = lp.lpSum(fuel)*price + lp.lpSum(starts.values())*g['start_cost']
    cost = cash + lp.lpSum(dis.values())*wear
    cost += (sum(solar)+sum(wind)-renewables)*policy['curtailment_penalty'] + shortfall*policy['renewable_shortfall_penalty']
    # Lexicographic solves: no financial weight can buy avoidable critical outages.
    objectives = [lp.lpSum(uc.values()), lp.lpSum(un.values()), lp.lpSum(flex_missed), cost]
    statuses = []
    try:
        for i, objective in enumerate(objectives):
            model.setObjective(objective)
            model.solve(lp.HiGHS(msg=False, timeLimit=1.0, gapRel=.001, threads=1))
            if model.status == lp.LpStatusInfeasible:
                return failed('No feasible plan satisfies battery end reserve, generator/fuel limits and availability. Check terminal SOC, available charging power and outage hours.')
            if model.sol_status not in [lp.LpSolutionOptimal, lp.LpSolutionIntegerFeasible]:
                return failed('Solver could not find a valid plan within the time limit.', 'failed')
            statuses.append(model.sol_status)
            if i < 3: model += objective <= max(0, lp.value(objective) or 0) + 1e-7
    except lp.PulpSolverError as exc:
        return failed(f'HiGHS solver unavailable: {exc}', 'failed')
    value = lambda v: max(0., float(lp.value(v) or 0))
    intervals = []
    for t in range(24):
        d = {'timestamp': rows[t]['timestamp'], 'solar_available': solar[t], 'wind_available': wind[t],
             'solar_used': value(pv[t]), 'wind_used': value(wt[t]), 'battery_charge': value(ch[t]),
             'battery_discharge': value(dis[t]), 'battery_soc': value(energy[t+1])/b['capacity_kwh']*100,
             'soc_start': value(energy[t])/b['capacity_kwh']*100, 'diesel_power': value(diesel[t]),
             'diesel_on': round(value(on[t])), 'diesel_start': round(value(starts[t])),
             'diesel_litres': value(fuel[t]), 'critical_required': critical[t], 'normal_required': normal[t],
             'critical_unserved': value(uc[t]), 'normal_unserved': value(un[t]),
             'flexible_load_scheduled': sum(value(f[t]) for f in flex_vars),
             'flexible_tasks': [{ 'name': f['name'], 'power_kw': value(flex_vars[j][t]) } for j,f in enumerate(c['flexible_loads'])]}
        d['served_load'] = critical[t]-d['critical_unserved']+normal[t]-d['normal_unserved']+d['flexible_load_scheduled']
        d['renewable_curtailment'] = max(0, solar[t]+wind[t]-d['solar_used']-d['wind_used'])
        residual = d['solar_used']+d['wind_used']+d['battery_discharge']+d['diesel_power']-d['served_load']-d['battery_charge']
        if abs(residual) > .001: return failed('Post-solve energy-balance validation failed.', 'failed')
        intervals.append(d)
    total = lambda key: sum(d[key] for d in intervals)
    flex_required = sum(f['required_kwh'] for f in c['flexible_loads'])*demand_factor
    required = sum(critical)+sum(normal)+flex_required
    served = total('served_load')
    renewable = total('solar_used')+total('wind_used')
    primary = renewable+total('diesel_power')
    pct = lambda numerator, denom: 100*numerator/denom if denom > 1e-9 else None
    reserve_hours = sum(d['battery_soc'] >= b['reserve_soc']-1e-5 for d in intervals)
    metrics = {
        'critical_load_served_pct': pct(sum(critical)-total('critical_unserved'), sum(critical)),
        'critical_required_kwh': sum(critical), 'critical_unserved_kwh': total('critical_unserved'),
        'critical_target_pct': policy['critical_target_pct'],
        'critical_target_met': sum(critical)==0 or (sum(critical)-total('critical_unserved'))/sum(critical)*100 >= policy['critical_target_pct']-1e-5,
        'normal_unserved_kwh': total('normal_unserved'), 'flexible_unserved_kwh': sum(value(v) for v in flex_missed),
        'unserved_kwh': max(0, required-served), 'served_kwh': served, 'requested_kwh': required,
        'total_energy_served_pct': pct(served, required), 'renewable_share_pct': pct(renewable, primary),
        'renewable_target_pct': policy['renewable_target_pct'], 'renewable_shortfall_kwh': value(shortfall),
        'reserve_compliance_pct': reserve_hours/24*100, 'minimum_soc_pct': min([initial]+[d['battery_soc'] for d in intervals]),
        'terminal_soc_pct': intervals[-1]['battery_soc'], 'diesel_litres': total('diesel_litres'),
        'fuel_cost_inr': total('diesel_litres')*price, 'generator_start_cost_inr': total('diesel_start')*g['start_cost'],
        'battery_wear_cost_inr': total('battery_discharge')*wear,
        'cash_cost_inr': value(cash), 'dispatch_cost_inr': value(cash)+total('battery_discharge')*wear,
        'penalty_cost_inr': max(0, value(cost)-value(cash)-total('battery_discharge')*wear),
        'objective_value_inr': value(cost), 'generator_starts': total('diesel_start'), 'generator_hours': total('diesel_on'),
        'emissions_kg_co2': total('diesel_litres')*g['emissions_factor'], 'renewable_curtailed_kwh': total('renewable_curtailment'),
        'battery_discharge_kwh': total('battery_discharge'), 'basis': 'projected',
    }
    metrics['diesel_l_per_kwh'] = metrics['diesel_litres']/served if served > 1e-9 else None
    metrics['cost_per_kwh'] = metrics['dispatch_cost_inr']/served if served > 1e-9 else None
    diagnostics = []
    if metrics['critical_unserved_kwh'] > .001: diagnostics.append('Critical demand cannot be fully supplied with the available equipment, fuel and reserve constraints.')
    if metrics['normal_unserved_kwh'] > .001: diagnostics.append(f"Normal demand has {metrics['normal_unserved_kwh']:.2f} kWh unserved. Lower fuel expenditure in this case must not be presented as a like-for-like saving.")
    if metrics['flexible_unserved_kwh'] > .001: diagnostics.append('Some flexible work cannot fit within available energy/power and permitted hours.')
    if reserve_hours < 24: diagnostics.append('Operational reserve is used during this plan; the hard minimum SOC remains protected.')
    if value(shortfall) > .001: diagnostics.append('Renewable target missed to preserve the best achievable service and cost balance.')
    starts_at = next((i for i,d in enumerate(intervals) if d['diesel_start']), None)
    action = {'action': 'USE_RENEWABLES_AND_STORAGE', 'reason': 'Available renewable energy and stored energy cover the recommended plan without a new generator start.'}
    if starts_at is not None:
        end = starts_at+1
        while end < 24 and intervals[end]['diesel_on']: end += 1
        local = lambda stamp: pd.Timestamp(stamp).tz_convert(s['site']['timezone']).isoformat()
        action = {'action': 'START_GENERATOR', 'time': local(intervals[starts_at]['timestamp']),
                  'end_time': local(pd.Timestamp(intervals[0]['timestamp'])+pd.Timedelta(hours=end)),
                  'reason': f'The costed 24-hour plan starts backup here while meeting the best achievable demand service and {policy["terminal_soc"]:g}% end-of-plan SOC. Review the schedule before operating equipment.'}
    elif state.get('generator_on') and not intervals[0]['diesel_on']:
        action = {'action': 'STOP_GENERATOR', 'time': intervals[0]['timestamp'], 'reason': 'The next interval can be supplied without the running generator; review the full storage plan.'}
    if metrics['critical_unserved_kwh'] > .001:
        action = {'action': 'CRITICAL_SHORTAGE', 'reason': diagnostics[0]}
    metrics['reliability_status'] = 'red' if metrics['critical_unserved_kwh'] > .001 else 'amber' if reserve_hours < 24 else 'green'
    return {'status': 'optimal' if all(v==lp.LpSolutionOptimal for v in statuses) else 'feasible', 'metrics': metrics,
            'intervals': intervals, 'next_action': action, 'diagnostics': diagnostics, 'solve_seconds': time.monotonic()-started}
