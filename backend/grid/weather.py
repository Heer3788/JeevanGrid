from datetime import timedelta
import math
import pandas as pd
import requests
from django.utils import timezone
from .models import WeatherInterval
from .energy import simulated_weather
from .validation import fail


def horizon_start(site_timezone='UTC'):
    return pd.Timestamp.now(tz=site_timezone).ceil('h').tz_convert('UTC')


def store_weather(site, rows, source):
    now = timezone.now()
    WeatherInterval.objects.bulk_create([WeatherInterval(site=site, timestamp=r['timestamp'], retrieved_at=now,
                                             source=source, data=r) for r in rows])
    return {'source': source, 'retrieved_at': now.isoformat(), 'cached': False, 'intervals': rows}


def valid_rows(rows):
    return len(rows) == 24 and all(all(isinstance(r[k], (int,float)) and math.isfinite(r[k]) for k in ['ghi','temperature','wind_speed'])
                                   and r['ghi'] >= 0 and r['wind_speed'] >= 0 for r in rows)


def forecast(site):
    start = horizon_start(site.timezone)
    try:
        response = requests.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': site.latitude, 'longitude': site.longitude, 'timezone': site.timezone, 'forecast_days': 3,
            'hourly': 'shortwave_radiation,temperature_2m,wind_speed_10m', 'wind_speed_unit': 'ms'}, timeout=12)
        response.raise_for_status()
        h = response.json()['hourly']
        rows = []
        for i, stamp in enumerate(h['time']):
            # Open-Meteo radiation is preceding-hour mean. Shift it to interval start.
            t = pd.Timestamp(stamp, tz=site.timezone).tz_convert('UTC') - pd.Timedelta(hours=1)
            if start <= t < start + pd.Timedelta(hours=24):
                rows.append({'timestamp': t.isoformat(), 'ghi': h['shortwave_radiation'][i],
                             'temperature': h['temperature_2m'][i], 'wind_speed': h['wind_speed_10m'][i], 'source': 'weather_api'})
        if not valid_rows(rows): raise ValueError('Incomplete weather data')
        return store_weather(site, rows, 'open_meteo')
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        latest = site.weather.filter(source='open_meteo', retrieved_at__gte=timezone.now()-timedelta(hours=6)).order_by('-retrieved_at').first()
        if latest:
            cached = list(site.weather.filter(source='open_meteo', retrieved_at=latest.retrieved_at,
                          timestamp__gte=start.to_pydatetime(), timestamp__lt=(start+pd.Timedelta(hours=24)).to_pydatetime()))
            if len(cached) == 24:
                return {'source': 'open_meteo', 'retrieved_at': latest.retrieved_at.isoformat(), 'cached': True,
                        'intervals': [w.data for w in cached]}
        fail('Forecast unavailable, incomplete or older than six hours. Choose simulated or historical mode explicitly.')


def historical(site, date):
    try:
        start = pd.Timestamp(date, tz='UTC').normalize()
    except (ValueError, TypeError): fail('Historical date must use YYYY-MM-DD.')
    if start >= pd.Timestamp.now(tz='UTC').normalize(): fail('Historical date must be in the past.')
    cached = list(site.weather.filter(source='nasa_power', timestamp__gte=start.to_pydatetime(),
                  timestamp__lt=(start+pd.Timedelta(days=1)).to_pydatetime()).order_by('-retrieved_at')[:24])
    if len(cached) == 24:
        return {'source': 'nasa_power', 'retrieved_at': cached[0].retrieved_at.isoformat(), 'cached': True,
                'intervals': sorted([r.data for r in cached], key=lambda r:r['timestamp'])}
    try:
        response = requests.get('https://power.larc.nasa.gov/api/temporal/hourly/point', params={
            'parameters': 'ALLSKY_SFC_SW_DWN,T2M,WS10M', 'community': 'RE', 'latitude': site.latitude,
            'longitude': site.longitude, 'start': start.strftime('%Y%m%d'), 'end': start.strftime('%Y%m%d'),
            'format': 'JSON', 'time-standard': 'UTC'}, timeout=25)
        response.raise_for_status()
        params = response.json()['properties']['parameter']
        rows = [{'timestamp': pd.to_datetime(k, format='%Y%m%d%H', utc=True).isoformat(), 'ghi': v,
                 'temperature': params['T2M'][k], 'wind_speed': params['WS10M'][k], 'source': 'weather_api'}
                for k, v in sorted(params['ALLSKY_SFC_SW_DWN'].items())]
        if not valid_rows(rows) or any(r['temperature'] < -100 for r in rows): raise ValueError('Missing NASA values')
        return store_weather(site, rows, 'nasa_power')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        fail('NASA POWER historical data could not be retrieved. Choose simulated mode or retry.')


def get_weather(site, mode, date=None):
    if mode == 'forecast': return forecast(site)
    if mode == 'historical': return historical(site, date or '2025-01-15')
    if mode == 'simulated':
        return {'source': 'simulated', 'retrieved_at': timezone.now().isoformat(), 'cached': False,
                'intervals': simulated_weather(horizon_start(site.timezone))}
    fail('Choose forecast, historical or simulated mode.')
