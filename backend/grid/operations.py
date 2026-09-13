"""Validated application operations shared by HTTP and the assistant."""
import csv, io, math
from copy import deepcopy
import pandas as pd
from django.db import transaction
from django.utils import timezone
from . import models as m, services as svc
from .access import role, admin, site_for, run_for
from .defaults import default_configuration
from .validation import fail, validate_site, validate_reading


@transaction.atomic
def save_site(user, data, pk=None):
    admin(user)
    data = deepcopy(data)
    validate_site(data)
    if pk is None:
        if not data.get('name'): fail('Site name is required.')
        config = data.pop('configuration', default_configuration())
        operators = data.pop('operator_ids', [])
        site = m.Site.objects.create(organization=role(user).organization, **data,
            provenance={'site':'operator','note':'User-configured site; template values require verification.'})
        svc.save_configuration(site, config, increment=False)
        assign(site, operators)
    else:
        site = site_for(user, pk)
        if 'operator_ids' in data: assign(site, data.pop('operator_ids'))
        if 'configuration' in data: svc.save_configuration(site, data.pop('configuration'), increment=False)
        for key, value in data.items(): setattr(site, key, value)
        site.configuration_version += 1
        site.save()
    return site


@transaction.atomic
def record_reading(user, pk, data):
    site = site_for(user, pk, writable=True)
    c = svc.configuration(site)
    validate_reading(data, c)
    state = svc.current_state(site,c)
    state.pop('provenance'); state.pop('timestamp')
    state.update(data)
    validate_reading(state,c)
    reading = m.SiteReading.objects.create(site=site, timestamp=timezone.now(), data=state, created_by=user)
    site.configuration_version += 1
    site.save(update_fields=['configuration_version'])
    return reading


@transaction.atomic
def pause_replay(user, pk):
    from . import live
    from django.shortcuts import get_object_or_404
    site = site_for(user, pk, writable=True)
    current = get_object_or_404(m.LiveSession, site=site, active=True)
    current.active = False
    live.event(current, 'Operator paused simulation. No further commands will execute.', 'pause', {'active':False})
    current.save(update_fields=['active','events'])
    current.commands.filter(status__in=['proposed','approved','executing']).update(status='superseded')
    return current

def assign(site, operator_ids):
    if not isinstance(operator_ids, list) or any(type(i) is not int for i in operator_ids): fail('operator_ids must be a list of integers.')
    valid = list(m.UserRole.objects.filter(organization=site.organization, role='operator', user_id__in=operator_ids).values_list('user_id', flat=True))
    if set(valid) != set(operator_ids): fail('Operators must belong to this organization.')
    site.assignments.all().delete()
    m.SiteAssignment.objects.bulk_create([m.SiteAssignment(site=site,user_id=i) for i in valid])


def import_load(user, pk, file):
    admin(user)
    site = site_for(user,pk,writable=True)
    if not file or file.size > 1024*1024: fail('Upload a CSV file under 1 MB.')
    try:
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8-sig')))
        expected = {'timestamp','critical_kw','normal_kw','flexible_kw'}
        if set(reader.fieldnames or []) != expected: fail('CSV columns must be timestamp,critical_kw,normal_kw,flexible_kw; power is in kW.')
        rows = list(reader)
        if len(rows) != 24: fail('Upload exactly 24 consecutive hourly intervals.')
        stamps = [pd.Timestamp(r['timestamp']) for r in rows]
        if any(t.tzinfo is None for t in stamps): fail('Each timestamp needs a UTC offset, e.g. +05:30.')
        stamps = [t.tz_convert('UTC') for t in stamps]
        if len(set(stamps)) != 24: fail('Duplicate timestamps are not allowed.')
        for i in range(1,24):
            if stamps[i]-stamps[i-1] != pd.Timedelta(hours=1): fail('CSV must be sorted with exactly one-hour spacing.')
        parsed = [{k:float(r[k]) for k in expected-{'timestamp'}} for r in rows]
        if any(not math.isfinite(v) or v < 0 for r in parsed for v in r.values()): fail('Load values must be finite and non-negative.')
    except (UnicodeError,ValueError,KeyError,TypeError,csv.Error): fail('Invalid CSV values or timestamps.')
    c = deepcopy(svc.configuration(site))
    total = sum(sum(r.values()) for r in parsed)
    if total <= 0: fail('Daily demand must be greater than zero.')
    flex = sum(r['flexible_kw'] for r in parsed)
    c['demand'] = {'daily_kwh':total,'peak_kw':max(sum(r.values()) for r in parsed),
                   'critical_pct':100*sum(r['critical_kw'] for r in parsed)/total, 'flexible_pct':100*flex/total,'provenance':'csv'}
    oldflex = sum(f['required_kwh'] for f in c['flexible_loads'])
    if flex and not oldflex: fail('Configure a flexible load window before uploading a CSV with flexible demand.')
    for f in c['flexible_loads']: f['required_kwh'] *= flex/oldflex if oldflex else 0
    with transaction.atomic():
        svc.save_configuration(site,c)
        site.load_profile.intervals.all().delete()
        m.LoadInterval.objects.bulk_create([m.LoadInterval(profile=site.load_profile,timestamp=stamps[i],**r) for i,r in enumerate(parsed)])
    return {'detail':'Imported 24 hourly intervals as a daily local-hour demand template.', 'daily_kwh':total,'provenance':'csv'}


def review_plan(user, pk, data):
    run=run_for(user,pk)
    site_for(user,run.site_id,writable=True)
    if run.mode=='scenario' or run.status not in ['optimal','feasible']: fail('Only feasible baseline plans can be confirmed or overridden.')
    if run.configuration_version != run.site.configuration_version: fail('Site inputs changed; generate a new plan before approval.')
    if svc.reliability(run.site)['assessment']=='Forecast is stale; refresh it.': fail('Forecast is stale; refresh and rerun before approval.')
    if run.id != svc.latest_plan(run.site).id: fail('This plan has been superseded; review the latest plan.')
    action=data.get('decision'); reason=data.get('reason','')
    if action not in ['confirm','override'] or not isinstance(reason,str) or len(reason)>2000: fail('Enter confirm/override and a reason up to 2000 characters.')
    if action=='override' and not reason.strip(): fail('An override reason is required.')
    obj=m.OperatorDecision.objects.create(run=run,user=user,decision=action,reason=reason)
    return {'id':obj.id,'decision':action,'reason':reason}
