"""Chronological backtests and portable JSON XGBoost models, with explicit provenance."""
import base64
import csv
import io
import math
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from .defaults import daily_shape
from .energy import solar_power, simulated_weather
from .models import ForecastModel
from .validation import fail


def demo_dataset(site, config):
    end = pd.Timestamp.now(tz=site.timezone).normalize()
    weather = simulated_weather(end-pd.Timedelta(days=90), 90*24)
    rng = np.random.default_rng(3788)
    for row in weather:
        row['ghi'] *= float(rng.uniform(.35, 1.05))
        row['temperature'] += float(rng.normal(0, 3))
    pv = solar_power(weather, config['solar'], site.latitude, site.longitude)
    shape = daily_shape(config['demand']['daily_kwh'], config['demand']['peak_kw'])
    fixed_share = 1-config['demand']['flexible_pct']/100
    rows = []
    for i, w in enumerate(weather):
        t = pd.Timestamp(w['timestamp']).tz_convert(site.timezone)
        baseline = shape[t.hour]*fixed_share
        load = baseline*(1+.12*(t.dayofweek>=5)+.008*(w['temperature']-24))+rng.normal(0, baseline*.025)
        actual_solar = pv[i]*(.86+.04*math.sin(t.hour/3))+rng.normal(0, pv[i]*.015)
        rows.append(dict(w, baseline_demand_kw=baseline, physics_solar_kw=pv[i],
                         demand_kw=max(0,float(load)), solar_kw=max(0,float(actual_solar))))
    return rows


def parse_csv(file, site):
    if file.size > 5*1024*1024: fail('Training CSV must be under 5 MB.')
    fields = {'timestamp','temperature','baseline_demand_kw','physics_solar_kw','demand_kw','solar_kw'}
    try:
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8-sig')))
        if not fields.issubset(reader.fieldnames or []): fail('Training CSV requires: '+', '.join(sorted(fields)))
        rows = []
        for r in reader:
            t = pd.Timestamp(r['timestamp'])
            if t.tzinfo is None: fail('Training timestamps require a timezone offset.')
            item = {'timestamp': t.isoformat()}
            for k in fields-{'timestamp'}:
                v = float(r[k])
                if not math.isfinite(v) or (k != 'temperature' and v < 0): fail('Invalid training value.')
                item[k] = v
            rows.append(item)
        if not 30*24 <= len(rows) <= 24*366: fail('Provide 30–366 days of hourly training data.')
        stamps = pd.to_datetime([r['timestamp'] for r in rows], utc=True)
        if any(stamps[i]-stamps[i-1] != pd.Timedelta(hours=1) for i in range(1,len(stamps))): fail('Training intervals must be consecutive, sorted and unique.')
        if stamps[-1] >= pd.Timestamp.now(tz='UTC'): fail('Training observations must be in the past.')
        return rows
    except (ValueError, UnicodeError, TypeError): fail('Could not parse training CSV.')


def features(rows, tz):
    return np.asarray([[pd.Timestamp(r['timestamp']).tz_convert(tz).hour,
        pd.Timestamp(r['timestamp']).tz_convert(tz).dayofweek,
        r['temperature'], r['baseline_demand_kw'], r['physics_solar_kw']] for r in rows])


def train(site, config, rows, provenance):
    n = len(rows); a, b = int(n*.65), int(n*.82)
    x = features(rows, site.timezone)
    artifacts, report = {'dataset': rows}, {'rows': n, 'features': ['hour','weekday','temperature','baseline demand','physics solar'],
        'split': {'training': [rows[0]['timestamp'], rows[a-1]['timestamp']],
                  'calibration': [rows[a]['timestamp'], rows[b-1]['timestamp']],
                  'test': [rows[b]['timestamp'], rows[-1]['timestamp']]},
        'provenance': provenance, 'note': 'Synthetic backtest demonstrates the pipeline; it is not field accuracy.' if provenance=='simulated' else 'Uploaded observations; verify that weather inputs were available at forecast issue time.'}
    for target, base in [('demand','baseline_demand_kw'), ('solar','physics_solar_kw')]:
        actual = np.array([r[target+'_kw'] for r in rows])
        baseline = np.array([r[base] for r in rows])
        model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=.08, n_jobs=1, random_state=3788)
        y = actual-baseline if target=='solar' else actual
        model.fit(x[:a], y[:a])
        pred = model.predict(x)
        if target=='solar': pred += baseline
        pred = np.maximum(0, pred)
        if target=='solar': pred = np.where(baseline>0, np.minimum(config['solar']['capacity_kw'],pred), 0)
        mae = float(np.mean(np.abs(actual[b:]-pred[b:])))
        baseline_mae = float(np.mean(np.abs(actual[b:]-baseline[b:])))
        # Gate on calibration, keeping the final test period untouched for reporting.
        use_ml = np.mean(np.abs(actual[a:b]-pred[a:b])) < np.mean(np.abs(actual[a:b]-baseline[a:b]))*.98
        selected = pred if use_ml else baseline
        residual = actual[a:b]-selected[a:b]
        report[target] = {'ml_mae_kw': mae, 'baseline_mae_kw': baseline_mae, 'active': bool(use_ml),
            'selected_test_mae_kw': float(np.mean(np.abs(actual[b:]-selected[b:]))),
            'lower_residual_kw': float(np.quantile(residual,.1)), 'upper_residual_kw': float(np.quantile(residual,.9)),
            'evaluation': [{'timestamp':rows[i]['timestamp'], 'actual':float(actual[i]), 'baseline':float(baseline[i]), 'forecast':float(selected[i])} for i in range(b,min(n,b+48))]}
        artifacts[target] = base64.b64encode(model.get_booster().save_raw(raw_format='json')).decode()
    return ForecastModel.objects.create(site=site, configuration_version=site.configuration_version,
        provenance=provenance, artifacts=artifacts, report=report)


def apply_forecast(site, snapshot, enabled=True, conservative=True):
    rows = snapshot['inputs']; c = snapshot['configuration']
    weather = snapshot['weather']['intervals']
    data = [dict(timestamp=r['timestamp'], temperature=weather[i]['temperature'],
                 baseline_demand_kw=r['critical_kw']+r['normal_kw'], physics_solar_kw=r['solar_available']) for i,r in enumerate(rows)]
    version = site.forecast_models.filter(configuration_version=site.configuration_version).first() if enabled else None
    # A model trained on synthetic labels may only influence synthetic runs.
    if version and version.provenance=='simulated' and snapshot['weather']['source']!='simulated': version = None
    predictions = {'demand':np.array([r['baseline_demand_kw'] for r in data]), 'solar':np.array([r['physics_solar_kw'] for r in data])}
    if version:
        x = features(data, site.timezone)
        for target in predictions:
            if version.report[target]['active']:
                model = XGBRegressor(); model.load_model(bytearray(base64.b64decode(version.artifacts[target])))
                result = model.predict(x)
                if target=='solar': result += predictions[target]
                predictions[target] = np.maximum(0, result)
    for i,r in enumerate(rows):
        old_total = data[i]['baseline_demand_kw']
        share = r['critical_kw']/old_total if old_total else 0
        mean_demand = float(predictions['demand'][i])
        mean_solar = min(c['solar']['capacity_kw'],float(predictions['solar'][i])) if data[i]['physics_solar_kw']>0 else 0
        lower = max(0, mean_solar + version.report['solar']['lower_residual_kw']) if version else mean_solar*.8
        upper = max(mean_demand,mean_demand + version.report['demand']['upper_residual_kw']) if version else mean_demand*1.1
        lower = min(mean_solar, lower)
        r.update(demand_forecast_kw=mean_demand, solar_forecast_kw=mean_solar, solar_lower_kw=lower, demand_upper_kw=upper)
        chosen = upper if conservative else mean_demand
        r.update(critical_kw=chosen*share, normal_kw=chosen*(1-share), solar_available=lower if conservative else mean_solar)
    snapshot['forecast_model'] = {'id':version.pk if version else None, 'provenance':version.provenance if version else 'physics_and_load_template',
        'conservative':conservative, 'bounds': 'Empirical 10th/90th residual quantiles; not guaranteed coverage.' if version else 'Assumed stress margins: solar −20%, fixed demand +10%; not statistical confidence.',
        'report': version.report if version else None}
    return snapshot
