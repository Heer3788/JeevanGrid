"""Demo identities and sourced places. Operational values are modelling assumptions."""
DEMO_PASSWORD = 'JeevanGridDemo!26'
ACCOUNTS = [
    {'email': 'admin@jeevangrid.local', 'name': 'Agency administrator', 'role': 'admin', 'description': 'All sites, team and configuration'},
    {'email': 'operator@jeevangrid.local', 'name': 'Microgrid operator', 'role': 'operator', 'description': 'Assigned sites, plans and testing'},
    {'email': 'bihar.operator@jeevangrid.local', 'name': 'Bihar demo operator', 'role': 'operator', 'description': 'Dharnai village demo', 'state': 'Bihar'},
    {'email': 'maharashtra.operator@jeevangrid.local', 'name': 'Maharashtra demo operator', 'role': 'operator', 'description': 'Darewadi village demo', 'state': 'Maharashtra'},
    {'email': 'up.operator@jeevangrid.local', 'name': 'Uttar Pradesh demo operator', 'role': 'operator', 'description': 'Rewana and Bijua village demos', 'state': 'Uttar Pradesh'},
]

PLACES = [
    dict(name='Dharnai · village demo', state='Bihar', district='Jehanabad', latitude=25.08, longitude=84.98,
         solar=100, battery=180, generator=75, daily=680, peak=74, fuel=220,
         source='https://www.greenpeace.org/india/en/story/278/dharnai-goes-live-powered-by-greenpeaces-first-solar-microgrid/',
         facts=['Greenpeace reported a 100 kW solar microgrid in 2014, including 30 kW for water pumping.'],
         note='A growth-demand demonstration based on the historically reported solar size. Battery size, diesel backup and demand below are hypothetical; current installation status is not asserted.'),
    dict(name='Darewadi · village demo', state='Maharashtra', district='Pune', latitude=19.12, longitude=73.62,
         solar=9.36, battery=28.8, generator=8, daily=68, peak=8, fuel=35,
         source='https://gramoorja.in/wp-content/uploads/2024/12/Micro-GridPaper.pdf',
         facts=['Gram Oorja describes a 9.36 kWp microgrid for 39 families and a 28.8 kWh battery bank.'],
         note='Published PV and nominal battery sizes with assumed increased demand and a hypothetical diesel backup. The demo uses its declared battery policy, not the original lead-acid operating policy.'),
    dict(name='Rewana · village demo', state='Uttar Pradesh', district='Lakhimpur Kheri', latitude=27.80, longitude=80.38,
         solar=30, battery=55, generator=28, daily=240, peak=28, fuel=100,
         source='https://www.tatapower.com/content/dam/tatapoweraemsitesprogram/tatapower/pdf-root/company-financials/annual-reports/103AnnualReport-2021-22.pdf',
         facts=['Tata Power reports a microgrid serving over 100 customers in Rewana in its FY2021–22 report.'],
         note='Plant capacities are assumed. The 30 kW PV model follows the entry size in Tata Power’s general microgrid offering, not a published Rewana equipment inventory.'),
    dict(name='Bijua · enterprise demo', state='Uttar Pradesh', district='Lakhimpur Kheri', latitude=28.15, longitude=80.69,
         solar=45, battery=80, generator=40, daily=380, peak=43, fuel=120,
         source='https://www.tatapower.com/content/dam/tatapoweraemsitesprogram/tatapower/pdf-root/company-financials/annual-reports/103AnnualReport-2021-22.pdf',
         facts=['Tata Power’s FY2021–22 report identifies microgrid supply in Bijua village, Lakhimpur.'],
         note='All capacities and productive-use demand are assumed to demonstrate a mixed renewable/diesel operating day.'),
]


def place_configuration(place):
    from .defaults import default_configuration
    c = default_configuration()
    for key in ['solar', 'wind', 'battery', 'generator', 'policy']:
        c[key]['provenance'] = 'simulated'
    c['solar'].update(capacity_kw=place['solar'], tilt=round(place['latitude']))
    c['wind'].update(capacity_kw=0)
    c['battery'].update(capacity_kwh=place['battery'], max_charge_kw=place['solar']*.5,
                        max_discharge_kw=place['generator']*.7, replacement_cost=place['battery']*10000,
                        lifetime_throughput_kwh=place['battery']*3000)
    c['generator'].update(capacity_kw=place['generator'], min_power_kw=place['generator']*.2,
                         fuel_intercept=place['generator']*.04, start_cost=place['generator']*1.5,
                         available_fuel_l=place['fuel'], ramp_kw_per_hour=place['generator'])
    c['demand'].update(daily_kwh=place['daily'], peak_kw=place['peak'], critical_pct=35,
                       flexible_pct=15, provenance='simulated')
    c['flexible_loads']=[dict(name='Water pumping', power_kw=place['peak']*.35,
                            required_kwh=place['daily']*.1, start_hour=7, end_hour=17,
                            priority='flexible', provenance='simulated'),
                         dict(name='Productive work', power_kw=place['peak']*.2,
                            required_kwh=place['daily']*.05, start_hour=9, end_hour=18,
                            priority='flexible', provenance='simulated')]
    return c
