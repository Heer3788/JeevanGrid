"""Auditable, deterministic engineering examples. NOT surveyed installations.

References constrain the types of community/equipment, not individual meter values.
Every watt, schedule and sizing rule below is an explicit modelling assumption.
"""
import math
from .defaults import default_configuration
from .validation import validate_configuration

SEED_KEY = 'engineering-portfolio-v1'
SOURCES = [
    {'title': 'Gram Oorja / Darewadi microgrid paper',
     'url': 'https://gramoorja.in/wp-content/uploads/2024/12/Micro-GridPaper.pdf',
     'supports': 'Darewadi: 39 households, 9.36 kWp PV, 28.8 kWh nominal battery; separate household, streetlight and commercial feeders. Historical reference, not our LFP design.'},
    {'title': 'Gram Oorja deployment history', 'url': 'https://gramoorja.in/journey/',
     'supports': 'Deployment context in Palghar, Melghat, Nandurbar, Gumla, Khunti and Dandeli forest; schools, health centres and water pumping.'},
    {'title': 'Greenpeace Dharnai project (2014)',
     'url': 'https://www.greenpeace.org/india/en/story/278/dharnai-goes-live-powered-by-greenpeaces-first-solar-microgrid/',
     'supports': '100 kW solar project, including 30 kW for water pumping. Not evidence of present operation.'},
    {'title': 'Tata Power solar microgrids', 'url': 'https://www.tatapower.com/renewables/solar-microgrids',
     'supports': 'Productive-use microgrids, irrigation and rural businesses; offerings starting at 30 kW. Not the equipment register of these examples.'},
]

# Regional anchors only; 12 alternative service clusters share each coordinate.
# No fabricated village names, surveyed plant coordinates or wind measurements.
REGIONS = [
    ('jehanabad', 'Jehanabad', 'Bihar', 25.21, 84.99, 1.00, 25, 94),
    ('lakhimpur', 'Lakhimpur Kheri', 'Uttar Pradesh', 27.95, 80.78, 1.00, 20, 90),
    ('gumla', 'Gumla', 'Jharkhand', 23.04, 84.54, .75, 35, 95),
    ('khunti', 'Khunti', 'Jharkhand', 23.08, 85.28, .75, 35, 95),
    ('pune', 'Pune', 'Maharashtra', 19.12, 73.62, .70, 45, 93),
    ('palghar', 'Palghar', 'Maharashtra', 19.91, 73.23, .90, 35, 94),
    ('nandurbar', 'Nandurbar', 'Maharashtra', 21.37, 74.24, 1.00, 40, 96),
    ('melghat', 'Amravati', 'Maharashtra', 21.40, 77.32, .75, 40, 96),
    ('dandeli', 'Uttara Kannada', 'Karnataka', 15.25, 74.62, .90, 30, 94),
]
USES = ['Household', 'Market', 'Agro', 'Health']


def spec(index):
    """Return one complete site: appliance inventory -> hourly load -> equipment."""
    if not 0 <= index < 108:
        raise ValueError('Index must be 0–107.')
    region, variant = divmod(index, 12)
    size, use_index = divmod(variant, 4)
    slug, district, state, lat, lon, fan_factor, head_m, price = REGIONS[region]
    households = [36, 64, 104][size]
    use = USES[use_index]
    inventory, tasks = [], []
    critical, normal = [0.0]*24, [0.0]*24

    def appliance(name, count, watts, active_hours, duty=1.0, priority='normal'):
        profile = [round(count*watts*duty/1000, 6) if h in active_hours else 0 for h in range(24)]
        inventory.append({'name': name, 'count': count, 'watts_each': watts, 'duty_factor': duty,
                          'hours': list(active_hours), 'priority': priority,
                          'daily_kwh': round(sum(profile), 6)})
        target = critical if priority == 'critical' else normal
        for h in range(24): target[h] += profile[h]

    appliance('Essential household LED', households, 9, [5, 6, 18, 19, 20, 21], priority='critical')
    appliance('Additional household LEDs', households*2, 9, [18, 19, 20, 21, 22], .8)
    appliance('Phone charging', households, 6, [18, 19, 20], .8)
    appliance('Ceiling fans', round(households*.7), 35, list(range(0, 7))+list(range(12, 24)), .65*fan_factor)
    appliance('Televisions', round(households*.35), 45, [18, 19, 20, 21], .85)
    appliance('Streetlights', max(4, households//8), 15, list(range(0, 6))+list(range(18, 24)), priority='critical')
    appliance('Microgrid controller and communications', 1, 35, range(24), priority='critical')
    appliance('School lights, fans and computer', max(1, households//40), 250, range(9, 15), .6)
    if use in ['Market', 'Agro', 'Health']:
        shops = [4, 8, 12][size]
        appliance('Shops: lights, fan and phone charging', shops, 90, range(9, 22), .7)
        appliance('Shop refrigerators', max(1, shops//4), 150, range(24), .35)
    if use == 'Health':
        appliance('Clinic vaccine refrigerator', 1, 120, range(24), .45, 'critical')
        appliance('Clinic lights and essential fan', 1, 150, range(24), .5, 'critical')
        appliance('Clinic computer and examination equipment', 1, 400, range(8, 18), .4)

    # 4 people/household, 40 litres/person/day lifted through the assumed head.
    # Electrical energy = rho*g*volume*head/(wire-to-water efficiency*3.6e6).
    water_m3 = households*4*40/1000
    water_kwh = round(1000*9.81*water_m3*head_m/(.45*3.6e6), 6)
    tasks.append({'name': 'Drinking-water pump', 'power_kw': [.75, 1.1, 1.5][size],
                  'required_kwh': water_kwh, 'start_hour': 9, 'end_hour': 16,
                  'priority': 'flexible', 'provenance': 'simulated'})
    if use == 'Agro':
        tasks.append({'name': 'Irrigation pump', 'power_kw': [1.5, 2.2, 3.7][size],
                      'required_kwh': [4.5, 8.8, 14.8][size], 'start_hour': 8, 'end_hour': 17,
                      'priority': 'flexible', 'provenance': 'simulated'})
        tasks.append({'name': 'Grain mill', 'power_kw': [2.2, 3.7, 5.5][size],
                      'required_kwh': [4.4, 7.4, 11][size], 'start_hour': 10, 'end_hour': 16,
                      'priority': 'flexible', 'provenance': 'simulated'})
    if use == 'Market':
        tasks.append({'name': 'Workshop batch tools', 'power_kw': [1.1, 2.2, 3.7][size],
                      'required_kwh': [2.2, 4.4, 7.4][size], 'start_hour': 10, 'end_hour': 17,
                      'priority': 'flexible', 'provenance': 'simulated'})
    # Reference flexible profile is energy-accounting only. The solver re-schedules
    # each task; its energy must NOT be added again to normal demand.
    flexible = [sum(t['required_kwh']/(t['end_hour']-t['start_hour']) for t in tasks
                    if t['start_hour'] <= h < t['end_hour']) for h in range(24)]
    rows = [{'hour': h, 'critical_kw': round(critical[h], 6), 'normal_kw': round(normal[h], 6),
             'flexible_kw': round(flexible[h], 6)} for h in range(24)]
    total = sum(sum(r[k] for k in ['critical_kw','normal_kw','flexible_kw']) for r in rows)
    critical_kwh, flex_kwh = sum(r['critical_kw'] for r in rows), sum(t['required_kwh'] for t in tasks)
    peak = max(sum(r[k] for k in ['critical_kw','normal_kw','flexible_kw']) for r in rows)
    evening = sum(critical[h]+normal[h] for h in list(range(18,24))+list(range(0,7)))
    # Deliberately constrained agro expansion cases reveal reserve/diesel tradeoffs.
    constrained = use == 'Agro' and size == 2
    pv_kw = round(math.ceil(total*(.65 if constrained else .95)/(4*.78)/.55)*.55, 2)
    battery_kwh = round(math.ceil(evening*(.65 if constrained else 1.15)/(.75*.95)/5.12)*5.12, 2)
    coincident = max(critical[h]+normal[h] for h in range(24))+sum(t['power_kw'] for t in tasks)
    generator_kw = next(k for k in [5, 8, 12, 16, 20, 25, 30, 40, 60, 80, 100] if k >= coincident*1.15)
    fuel_l = round(total*.32*2, 1)  # Two diesel-only energy-equivalent days; assumed stock, not a sensor.
    c = default_configuration()
    for section in ['solar','wind','battery','generator','policy','demand']: c[section]['provenance'] = 'simulated'
    c['solar'].update(capacity_kw=pv_kw, tilt=round(lat), derating=.90, inverter_efficiency=.96)
    c['wind']['capacity_kw'] = 0  # No unsupported installed-wind/resource claims.
    c['battery'].update(capacity_kwh=battery_kwh, min_soc=20, max_soc=95, reserve_soc=30,
                        max_charge_kw=round(min(pv_kw, battery_kwh*.5), 2),
                        max_discharge_kw=round(min(coincident, battery_kwh*.5), 2),
                        replacement_cost=round(battery_kwh*12000, 2),
                        lifetime_throughput_kwh=round(battery_kwh*.75*4000, 2))
    c['generator'].update(capacity_kw=generator_kw, min_power_kw=round(generator_kw*.25, 2),
                          fuel_slope=.26, fuel_intercept=round(generator_kw*.03, 3),
                          start_cost=0, diesel_price=price, available_fuel_l=fuel_l,
                          min_up_hours=2, min_down_hours=1, ramp_kw_per_hour=generator_kw)
    c['policy'].update(terminal_soc=30, max_starts=4, renewable_target_pct=70)
    c['demand'].update(daily_kwh=total, peak_kw=peak, critical_pct=critical_kwh/total*100,
                       flexible_pct=flex_kwh/total*100)
    c['flexible_loads'] = tasks
    validate_configuration(c)
    return {'name': f'JG{index+1:03d} {slug.title()} {use} {households}',
            'state': state, 'district': district, 'latitude': lat, 'longitude': lon,
            'operator_email': f'{slug}.ops{size+1}@jeevangrid.local',
            'operator_name': f'{slug.title()} demo operator {size+1}', 'configuration': c,
            'intervals': rows, 'reading': {'soc_pct': 40 if constrained else 60, 'fuel_l': fuel_l,
                'generator_available': True, 'generator_on': False, 'demand_multiplier': 1,
                'diesel_price': price, 'event': 'Modelled starting state; no physical telemetry.'},
            'provenance': {'site': 'simulated', 'seed_key': SEED_KEY, 'seed_index': index,
                'source_url': SOURCES[0]['url'], 'sources': SOURCES, 'households': households,
                'service_type': use, 'inventory': inventory,
                'note': 'Engineering-modelled service cluster, NOT a surveyed or operating installation. '
                        'Regional reference coordinates are shared, not exact plant locations. '
                        'Hourly demand is calculated from the disclosed appliance inventory; no meter data or ML-generated numbers. '
                        + ('Constrained agro expansion: reduced PV and battery budget, not an optimally sized design.' if constrained else ''),
                'study_fields': ['Published projects inform load categories and equipment scale only; none of this site’s readings are measured.'],
                'assumed_fields': ['Household/appliance counts, wattages, duty factors and schedules',
                    'LFP-style battery model: 20–95% SOC, 0.5C limits, 95% one-way efficiencies',
                    'PV sizing: daily demand × coverage / (4 assumed sun-hours × 0.78 system yield), rounded to 550 W modules',
                    'Battery sizing: overnight fixed demand / usable SOC and discharge efficiency, rounded to 5.12 kWh modules',
                    'Diesel sizing: 15% above fixed peak + simultaneous motor loads; fuel = 0.03 × rated kW per on-hour + 0.26 L/kWh',
                    'Diesel price is a scenario assumption, NOT a current local quote',
                    'Battery replacement ₹12,000/kWh; throughput 4,000 cycles at 75% depth; not a vendor warranty',
                    'No installed wind assumed without a measured wind-resource assessment',
                    'Energy balance at the microgrid bus; distribution losses and motor starting transients not modelled'],
                'water_calculation': {'people_per_household':4, 'litres_per_person_day':40,
                    'volume_m3_day':water_m3,'head_m':head_m,'wire_to_water_efficiency':.45,'required_kwh_day':water_kwh}}}
