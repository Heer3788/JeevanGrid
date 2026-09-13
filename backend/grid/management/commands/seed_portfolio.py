"""Add a reproducible, non-destructive engineering portfolio and actual solver runs."""
import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from grid import models as m, services as svc
from grid.assessment import assess
from grid.energy import solar_power, wind_power
from grid.optimizer import solve
from grid.portfolio_seed import SEED_KEY, SOURCES, spec
from grid.weather import historical, store_weather


class Command(BaseCommand):
    help = 'Add 108 transparent microgrid examples + 27 assigned demo operators. Never overwrite existing sites/passwords.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=108)
        parser.add_argument('--with-runs', action='store_true')
        parser.add_argument('--with-checks', action='store_true', help='Run six stress tests per new baseline sequentially.')
        parser.add_argument('--weather', choices=['simulated', 'historical'], default='simulated')
        parser.add_argument('--date', default='2025-01-15')
        parser.add_argument('--export-dir', help='Optional inventory CSV and complete source/load manifest (no passwords).')

    def handle(self, *args, **options):
        if not 1 <= options['count'] <= 108: raise CommandError('Count must be 1–108.')
        if options['with_checks'] and not options['with_runs']: raise CommandError('--with-checks needs --with-runs.')
        try: template_start = datetime.fromisoformat(options['date']).replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        except ValueError: raise CommandError('Use a YYYY-MM-DD reference date.')
        org = m.Organization.objects.filter(name='JeevanGrid Demo Agency').first()
        if not org: raise CommandError('Run seed_demo first to create the demo organization and admin.')
        admin_role = m.UserRole.objects.filter(organization=org, role='admin', user__is_active=True).first()
        if not admin_role: raise CommandError('Demo organization needs an active admin.')
        password = os.environ.get('JEEVANGRID_DEMO_PASSWORD', 'JeevanGridDemo!26')
        created = operators = runs = 0
        exports, weather_cache = [], {}
        for index in range(options['count']):
            item = spec(index)
            # Each site's initial records commit together. Re-runs never touch a site's edits.
            with transaction.atomic():
                site = m.Site.objects.filter(organization=org, provenance__seed_key=SEED_KEY,
                                             provenance__seed_index=index).first()
                if not site:
                    if m.Site.objects.filter(organization=org, name=item['name']).exists():
                        raise CommandError(f'Name collision: {item["name"]}; no existing site was overwritten.')
                    user, new_user = get_user_model().objects.get_or_create(username=item['operator_email'], defaults={
                        'email':item['operator_email'], 'first_name':item['operator_name']})
                    if new_user: user.set_password(password); user.save(); operators += 1
                    role, _ = m.UserRole.objects.get_or_create(user=user, defaults={'organization':org,'role':'operator'})
                    if role.organization_id != org.pk or role.role != 'operator':
                        raise CommandError('Operator identity collision; refusing to change existing permissions.')
                    site = m.Site.objects.create(organization=org, **{k:item[k] for k in
                        ['name','state','district','latitude','longitude','provenance']})
                    svc.save_configuration(site, item['configuration'], increment=False)
                    m.SiteAssignment.objects.create(site=site, user=user)
                    m.LoadInterval.objects.bulk_create([m.LoadInterval(profile=site.load_profile,
                        timestamp=template_start+timedelta(hours=r['hour']),
                        **{k:r[k] for k in ['critical_kw','normal_kw','flexible_kw']}) for r in item['intervals']])
                    m.SiteReading.objects.create(site=site, timestamp=timezone.now(), data=item['reading'],
                                                provenance='simulated', created_by=admin_role.user)
                    created += 1
            baseline = svc.latest_plan(site)
            if options['with_runs'] and not baseline:
                snapshot = svc.prepare_snapshot(site, 'simulated')
                mode = 'simulated'
                if options['weather'] == 'historical':
                    key = (site.latitude, site.longitude)
                    if key not in weather_cache:
                        # Explicit failure: no silent substitution of fictional API data.
                        weather_cache[key] = historical(site, options['date'], persist=False)
                    weather = weather_cache[key]
                    snapshot['weather'] = store_weather(site, weather['intervals'], 'nasa_power')
                    snapshot['weather']['retrieved_at'] = weather['retrieved_at']
                    c = snapshot['configuration']
                    pv = solar_power(weather['intervals'], c['solar'], site.latitude, site.longitude)
                    by_hour = {r.timestamp.astimezone(ZoneInfo(site.timezone)).hour:r for r in site.load_profile.intervals.all()}
                    snapshot['inputs'] = []
                    for i, row in enumerate(weather['intervals']):
                        h = datetime.fromisoformat(row['timestamp']).astimezone(ZoneInfo(site.timezone)).hour
                        load = by_hour[h]
                        snapshot['inputs'].append({'timestamp':row['timestamp'], 'critical_kw':load.critical_kw,
                            'normal_kw':load.normal_kw, 'solar_available':pv[i],
                            'wind_available':wind_power(row['wind_speed'], c['wind'])})
                    mode = 'historical'
                baseline = svc.persist_run(site, admin_role.user, mode, snapshot, solve(snapshot))
                runs += 1
            if options['with_checks'] and baseline and baseline.status in ['optimal','feasible']:
                # Claim only pending work so a running background worker cannot duplicate tests.
                claimed = m.PlanAssessment.objects.filter(run=baseline, status='pending').update(status='running')
                if claimed:
                    try:
                        assess(baseline)
                        m.PlanAssessment.objects.filter(run=baseline).update(status='complete',error='')
                    except Exception as error:
                        m.PlanAssessment.objects.filter(run=baseline).update(status='failed',error=str(error)[:1000])
                        raise
            exports.append({'id':site.pk, 'name':site.name, 'seed_key':SEED_KEY, 'seed_index':index,
                            'configuration':svc.configuration(site), 'provenance':site.provenance,
                            'operators':list(site.assignments.values_list('user__email',flat=True)),
                            'load_intervals':list(site.load_profile.intervals.values('timestamp','critical_kw','normal_kw','flexible_kw')),
                            'run_id':baseline.pk if baseline else None,
                            'metrics':baseline.metrics if baseline else {}, 'weather_source':baseline.snapshot['weather']['source'] if baseline else None})
            self.stdout.write(f'{index+1}/{options["count"]} {site.name} (#{site.pk}): {baseline.status if baseline else "configured"}')
        if options['export_dir']:
            directory = Path(options['export_dir']); directory.mkdir(parents=True, exist_ok=True)
            (directory/'portfolio-manifest.json').write_text(json.dumps({'seed_key':SEED_KEY,'sources':SOURCES,
                'notice':'Engineering-modelled, not measured installations. Weather provenance is recorded separately.',
                'sites':exports}, indent=2, default=str), encoding='utf-8')
            with (directory/'portfolio-inventory.csv').open('w',newline='',encoding='utf-8-sig') as output:
                writer = csv.writer(output)
                writer.writerow(['id','name','operators','households','daily_kwh','peak_kw','pv_kw','wind_kw','battery_kwh','diesel_kw','run_id','weather_source'])
                for row in exports:
                    c = row['configuration']
                    values = [row['id'],row['name'],', '.join(row['operators']),row['provenance']['households'],
                        round(c['demand']['daily_kwh'],3),round(c['demand']['peak_kw'],3),c['solar']['capacity_kw'],
                        c['wind']['capacity_kw'],c['battery']['capacity_kwh'],c['generator']['capacity_kw'],row['run_id'],row['weather_source']]
                    writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in values])
        self.stdout.write(self.style.SUCCESS(f'Added {created} sites, {operators} operators, {runs} base plans. Existing data and passwords preserved.'))
