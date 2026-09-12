import math
from copy import deepcopy
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework.exceptions import ValidationError
from .defaults import DEFAULTS


def fail(message):
    raise ValidationError({'detail': message})


def number(value, name, low=0, high=1e12):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        fail(f'{name} must be a finite number between {low} and {high}.')
    return value


def hours(value, name):
    if not isinstance(value, list) or any(type(h) is not int or h not in range(24) for h in value) or len(set(value)) != len(value):
        fail(f'{name} must contain unique integer hours from 0 to 23.')


def validate_site(data):
    allowed = {'name', 'state', 'district', 'latitude', 'longitude', 'timezone', 'archived', 'operator_ids', 'configuration'}
    if set(data) - allowed: fail('Unknown site fields.')
    for key in ['name', 'state', 'district']:
        if key in data and (not isinstance(data[key], str) or not 1 <= len(data[key].strip()) <= 160): fail(f'{key} is required and must be at most 160 characters.')
    if 'latitude' in data: number(data['latitude'], 'latitude', -90, 90)
    if 'longitude' in data: number(data['longitude'], 'longitude', -180, 180)
    if 'archived' in data and type(data['archived']) is not bool: fail('archived must be true or false.')
    try:
        ZoneInfo(data.get('timezone', 'Asia/Kolkata'))
    except (ZoneInfoNotFoundError, TypeError, ValueError): fail('Unknown timezone.')


def validate_configuration(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULTS): fail('Provide solar, wind, battery, generator, policy, demand and flexible_loads.')
    c = deepcopy(data)
    for key in ['min_up_hours', 'min_down_hours', 'ramp_kw_per_hour']:
        c['generator'].setdefault(key, DEFAULTS['generator'][key])
    for section in ['solar', 'wind', 'battery', 'generator', 'policy', 'demand']:
        if not isinstance(c[section], dict) or set(c[section]) != set(DEFAULTS[section]): fail(f'{section}: fields do not match the configuration template.')
        for key, val in c[section].items():
            if key == 'provenance':
                if val not in ['study','weather_api','operator','csv','simulated','simulated_from_published_totals']: fail('Unknown provenance.')
            elif key == 'allowed_generator_hours': hours(val, key)
            else: number(val, f'{section}.{key}')
    s, w, b, g, p, d = [c[k] for k in ['solar','wind','battery','generator','policy','demand']]
    number(s['tilt'], 'tilt', 0, 90); number(s['azimuth'], 'azimuth', 0, 360)
    for name in ['derating','inverter_efficiency']: number(s[name], name, .01, 1)
    if not 0 < w['cut_in'] < w['rated_speed'] < w['cut_out']: fail('Wind speeds must satisfy cut-in < rated < cut-out.')
    number(w['hub_height_m'], 'hub height', 10, 300); number(w['shear_exponent'], 'shear exponent', 0, .6)
    if not 0 <= b['min_soc'] < b['max_soc'] <= 100: fail('SOC limits must satisfy 0 <= min < max <= 100.')
    for value in [b['reserve_soc'], p['terminal_soc']]: number(value, 'reserve SOC', b['min_soc'], b['max_soc'])
    number(b['capacity_kwh'], 'battery capacity', .01)
    number(b['lifetime_throughput_kwh'], 'battery lifetime throughput', .01)
    for name in ['charge_efficiency','discharge_efficiency']: number(b[name], name, .01, 1)
    if g['min_power_kw'] > g['capacity_kw']: fail('Generator minimum exceeds rated power.')
    for key in ['min_up_hours', 'min_down_hours']:
        if type(g[key]) is not int or not 1 <= g[key] <= 24: fail(f'{key} must be an integer from 1 to 24.')
    number(g['ramp_kw_per_hour'], 'Generator ramp kW/hour', .01)
    for name in ['critical_target_pct','renewable_target_pct']: number(p[name], name, 0, 100)
    if type(p['max_starts']) is not int or not 0 <= p['max_starts'] <= 24: fail('Maximum starts must be an integer from 0 to 24.')
    number(d['daily_kwh'], 'daily energy', .01)
    if not d['daily_kwh']/24 <= d['peak_kw'] <= d['daily_kwh']: fail('Peak must be between daily kWh / 24 and daily kWh for hourly modelling.')
    if not 0 <= d['critical_pct'] <= 100 or not 0 <= d['flexible_pct'] <= 100 or d['critical_pct'] + d['flexible_pct'] > 100: fail('Critical + flexible percentages must be at most 100.')
    if not isinstance(c['flexible_loads'], list) or len(c['flexible_loads']) > 12: fail('Provide up to 12 flexible loads.')
    for f in c['flexible_loads']:
        if set(f) != set(DEFAULTS['flexible_loads'][0]): fail('Flexible load fields do not match the template.')
        if not isinstance(f['name'], str) or not 1 <= len(f['name']) <= 120: fail('Flexible load needs a name.')
        if f['priority'] != 'flexible': fail('V1 scheduled loads use flexible priority; configure critical load in the fixed profile.')
        if f['provenance'] not in ['operator','simulated','study','csv']: fail('Unknown flexible-load provenance.')
        number(f['power_kw'], 'flexible power', .01); number(f['required_kwh'], 'required energy')
        if type(f['start_hour']) is not int or type(f['end_hour']) is not int or not 0 <= f['start_hour'] < f['end_hour'] <= 24: fail('Flexible window must satisfy 0 <= start < end <= 24.')
        if f['required_kwh'] > f['power_kw'] * (f['end_hour']-f['start_hour']) + 1e-6: fail('Flexible energy cannot fit inside its allowed window.')
    expected = d['daily_kwh'] * d['flexible_pct']/100
    if abs(sum(f['required_kwh'] for f in c['flexible_loads']) - expected) > .001: fail(f'Flexible task energy must total {expected:.3f} kWh (the flexible portion of demand).')
    return c


def validate_reading(data, config):
    if not isinstance(data, dict) or set(data) - {'soc_pct','fuel_l','generator_available','generator_on','event','demand_multiplier','diesel_price'}: fail('Unknown current-state field.')
    if 'soc_pct' in data: number(data['soc_pct'], 'SOC', config['battery']['min_soc'], config['battery']['max_soc'])
    if 'fuel_l' in data: number(data['fuel_l'], 'fuel litres')
    if 'diesel_price' in data: number(data['diesel_price'], 'diesel price', .01)
    if 'demand_multiplier' in data: number(data['demand_multiplier'], 'demand multiplier', .1, 5)
    for key in ['generator_available','generator_on']:
        if key in data and type(data[key]) is not bool: fail(f'{key} must be true or false.')
    if 'event' in data and (not isinstance(data['event'], str) or len(data['event']) > 500): fail('Event must be text up to 500 characters.')
    return data


PRESETS = {
    'cloudy': {'solar_multiplier': .5}, 'low_wind': {'wind_multiplier': .5},
    'high_demand': {'demand_multiplier': 1.25}, 'expensive_fuel': {'fuel_price_multiplier': 1.25},
    'generator_outage': {'outage_start': 18, 'outage_end': 24}, 'low_battery': {'starting_soc': 25},
}


def validate_overrides(data):
    allowed = {'solar_multiplier','wind_multiplier','demand_multiplier','fuel_price_multiplier','starting_soc','outage_start','outage_end'}
    if not isinstance(data, dict) or set(data) - allowed: fail('Unknown scenario override.')
    for key, val in data.items():
        if key.endswith('multiplier'): number(val, key, 0 if key in ['solar_multiplier','wind_multiplier'] else .1, 3)
        elif key == 'starting_soc': number(val, key, 0, 100)
        elif type(val) is not int or not 0 <= val <= 24: fail('Outage hours must be integers between 0 and 24.')
    if ('outage_start' in data) != ('outage_end' in data): fail('Both outage hours are required.')
    if 'outage_start' in data and data['outage_start'] >= data['outage_end']: fail('Outage start must precede end, within one day.')
    return data
