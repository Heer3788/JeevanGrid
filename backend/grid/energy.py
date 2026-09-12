import math
import pandas as pd
import pvlib


def solar_power(weather, config, latitude, longitude):
    # Hourly irradiance is an interval average: use midpoint for solar geometry.
    idx = pd.to_datetime([w['timestamp'] for w in weather], utc=True) + pd.Timedelta(minutes=30)
    location = pvlib.location.Location(latitude, longitude)
    pos = location.get_solarposition(idx)
    ghi = pd.Series([w['ghi'] for w in weather], index=idx).clip(lower=0)
    radiation = pvlib.irradiance.erbs(ghi, pos['zenith'], idx)
    poa = pvlib.irradiance.get_total_irradiance(config['tilt'], config['azimuth'], pos['zenith'], pos['azimuth'],
                                             radiation['dni'], ghi, radiation['dhi'])['poa_global'].fillna(0).clip(lower=0)
    temp = pvlib.temperature.faiman(poa, pd.Series([w['temperature'] for w in weather], index=idx),
                                   pd.Series([w['wind_speed'] for w in weather], index=idx))
    dc = pvlib.pvsystem.pvwatts_dc(poa, temp, config['capacity_kw'] * 1000, -.004)
    ac = dc * config['derating'] * config['inverter_efficiency']/1000
    return [round(float(max(0, min(config['capacity_kw'], v))), 6) if z < 90 else 0.0 for v, z in zip(ac, pos['zenith'])]


def wind_power(speed_10m, c):
    speed = speed_10m * (c['hub_height_m']/10)**c['shear_exponent']
    if speed < c['cut_in'] or speed >= c['cut_out']: return 0.0
    if speed >= c['rated_speed']: return c['capacity_kw']
    return c['capacity_kw'] * (speed-c['cut_in'])/(c['rated_speed']-c['cut_in'])


def simulated_weather(start, count=24):
    rows = []
    for i in range(count):
        t = start + pd.Timedelta(hours=i)
        local = t.tz_convert('Asia/Kolkata')
        h = local.hour + local.minute/60 + .5
        daylight = max(0, math.sin(math.pi*(h-6)/12)) if 6 <= h <= 18 else 0
        rows.append({'timestamp': t.isoformat(), 'ghi': 750*daylight, 'temperature': 19+9*daylight,
                     'wind_speed': 2.6 + .7*math.sin(i*.7), 'source': 'simulated'})
    return rows
