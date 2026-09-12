import csv
import io
import math
from copy import deepcopy
import pandas as pd
import requests
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from . import models as m, services as svc
from .defaults import default_configuration
from .validation import fail, validate_site, validate_reading, PRESETS
from .weather import get_weather


class LoginThrottle(AnonRateThrottle):
    rate = '20/min'


def role(user):
    try: return user.grid_role
    except m.UserRole.DoesNotExist: raise PermissionDenied('No JeevanGrid role assigned.')


def admin(user):
    if role(user).role != 'admin': raise PermissionDenied('Admin access required.')


def sites_for(user):
    r = role(user)
    q = m.Site.objects.filter(organization=r.organization)
    return q if r.role == 'admin' else q.filter(assignments__user=user).distinct()


def site_for(user, pk, writable=False):
    site = get_object_or_404(sites_for(user), pk=pk)
    if writable and site.archived: fail('This site is archived. Restore it before running or editing it.')
    return site


def account(user):
    r = role(user)
    return {'id': user.pk, 'email': user.email, 'name': user.first_name or user.email, 'role': r.role,
            'organization': r.organization.name, 'organization_id': r.organization_id}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    email = request.data.get('email', '').strip().lower()
    user = authenticate(username=email, password=request.data.get('password', ''))
    if not user: return Response({'detail': 'Incorrect email or password.'}, status=401)
    data = account(user)
    refresh = RefreshToken.for_user(user)
    return Response({'access': str(refresh.access_token), 'refresh': str(refresh), 'user': data})


@api_view(['GET'])
def me(request): return Response(account(request.user))


@api_view(['POST'])
def logout(request):
    try: RefreshToken(request.data.get('refresh', '')).blacklist()
    except Exception: pass
    return Response({'detail': 'Signed out.'})


@api_view(['GET'])
def members(request):
    admin(request.user)
    return Response(list(m.UserRole.objects.filter(organization=role(request.user).organization, role='operator').values('user_id','user__email')))


@api_view(['GET'])
def defaults(request): return Response(default_configuration())


@api_view(['GET'])
def location_search(request):
    """Resolve an Indian place name without exposing the browser to a third-party API."""
    query = request.query_params.get('q', '').strip()
    state = request.query_params.get('state', '').strip()
    if len(query) < 3: fail('Enter at least three characters of a village, town or district.')
    if len(state) > 100: fail('State or union territory must be at most 100 characters.')
    try:
        response = requests.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': query, 'count': 20, 'language': 'en', 'format': 'json', 'countryCode': 'IN'},
            timeout=10,
        )
        response.raise_for_status()
        raw = response.json().get('results', [])
    except (requests.RequestException, ValueError, AttributeError):
        return Response({'detail': 'Location search is temporarily unavailable. You can still enter coordinates manually.'}, status=502)
    matches = []
    for item in raw:
        # Some Indian GeoNames records omit admin1. Keep the operator-selected
        # state in that case, surface the verification flag, and show district
        # context so the operator can reject a similarly named place.
        admin1 = item.get('admin1')
        if item.get('country_code') != 'IN' or (state and admin1 and admin1.casefold() != state.casefold()):
            continue
        if not all(key in item for key in ('name', 'latitude', 'longitude')):
            continue
        matches.append({
            'id': item.get('id'), 'name': item['name'], 'state': admin1 or state,
            'district': item.get('admin2') or item.get('admin3') or item['name'],
            'latitude': item['latitude'], 'longitude': item['longitude'],
            'timezone': item.get('timezone') or 'Asia/Kolkata',
            'state_verified': bool(admin1),
            'label': ', '.join(filter(None, [item['name'], item.get('admin2'), admin1 or state])),
        })
        if len(matches) == 8: break
    return Response({'results': matches, 'attribution': 'Open-Meteo geocoding; location data based on GeoNames'})


def assign(site, operator_ids):
    if not isinstance(operator_ids, list) or any(type(i) is not int for i in operator_ids): fail('operator_ids must be a list of integers.')
    valid = list(m.UserRole.objects.filter(organization=site.organization, role='operator', user_id__in=operator_ids).values_list('user_id', flat=True))
    if set(valid) != set(operator_ids): fail('Operators must belong to this organization.')
    site.assignments.all().delete()
    m.SiteAssignment.objects.bulk_create([m.SiteAssignment(site=site,user_id=i) for i in valid])


@api_view(['GET','POST'])
def sites(request):
    if request.method == 'GET': return Response([svc.site_summary(s) for s in sites_for(request.user).order_by('id')])
    admin(request.user)
    data = dict(request.data); validate_site(data)
    if not data.get('name'): fail('Site name is required.')
    config = data.pop('configuration', default_configuration())
    operators = data.pop('operator_ids', [])
    with transaction.atomic():
        site = m.Site.objects.create(organization=role(request.user).organization, **data, provenance={'site': 'operator', 'note': 'User-configured site; template values require verification.'})
        svc.save_configuration(site, config, increment=False)
        assign(site, operators)
    return Response(svc.site_summary(site), status=201)


@api_view(['GET','PATCH'])
def site_detail(request, pk):
    site = site_for(request.user, pk)
    if request.method == 'PATCH':
        admin(request.user)
        data = dict(request.data); validate_site(data)
        with transaction.atomic():
            if 'operator_ids' in data: assign(site, data.pop('operator_ids'))
            if 'configuration' in data: svc.save_configuration(site, data.pop('configuration'), increment=False)
            for key,val in data.items(): setattr(site,key,val)
            site.configuration_version += 1
            site.save()
    data = svc.site_summary(site)
    data.update({'configuration': svc.configuration(site), 'current_state': svc.current_state(site, svc.configuration(site)), 'reliability': svc.reliability(site)})
    return Response(data)


@api_view(['GET','PUT'])
def configuration(request, pk):
    site = site_for(request.user, pk, writable=request.method=='PUT')
    if request.method == 'PUT':
        admin(request.user)
        svc.save_configuration(site, request.data)
        site.refresh_from_db()
    return Response({'configuration': svc.configuration(site), 'version': site.configuration_version})


@api_view(['POST'])
def readings(request, pk):
    site = site_for(request.user, pk, writable=True)
    c = svc.configuration(site)
    validate_reading(request.data, c)
    state = svc.current_state(site,c)
    state.pop('provenance'); state.pop('timestamp')
    state.update(request.data)
    validate_reading(state,c)
    reading = m.SiteReading.objects.create(site=site, timestamp=timezone.now(), data=state, created_by=request.user)
    # New state invalidates the current comparison until replanning.
    site.configuration_version += 1
    site.save(update_fields=['configuration_version'])
    return Response({'id':reading.pk, 'state':state, 'timestamp':reading.timestamp}, status=201)


@api_view(['POST'])
def load_import(request, pk):
    admin(request.user)
    site = site_for(request.user,pk,writable=True)
    file = request.FILES.get('file')
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
    return Response({'detail':'Imported 24 hourly intervals as a daily local-hour demand template.', 'daily_kwh':total,'provenance':'csv'})


@api_view(['POST'])
def forecast_refresh(request, pk):
    site=site_for(request.user,pk,writable=True)
    data=get_weather(site,request.data.get('mode','forecast'),request.data.get('date'))
    return Response(data)


@api_view(['POST'])
def optimization_runs(request, pk):
    site=site_for(request.user,pk,writable=True)
    run=svc.optimize(site,request.user,request.data.get('mode','simulated'),request.data.get('date'))
    return Response(svc.run_summary(run,True),status=201)


def run_for(user, pk):
    return get_object_or_404(m.OptimizationRun.objects.filter(site__in=sites_for(user)),pk=pk)


@api_view(['GET'])
def run_detail(request, pk): return Response(svc.run_summary(run_for(request.user,pk),True))


@api_view(['GET'])
def run_list(request):
    q=m.OptimizationRun.objects.filter(site__in=sites_for(request.user)).select_related('site')
    if request.query_params.get('site_id'): q=q.filter(site_id=request.query_params['site_id'])
    if request.query_params.get('kind')=='scenario': q=q.filter(mode='scenario')
    return Response([svc.run_summary(r) for r in q[:100]])


@api_view(['POST'])
def decision(request, pk):
    run=run_for(request.user,pk)
    site_for(request.user,run.site_id,writable=True)
    if run.mode=='scenario' or run.status not in ['optimal','feasible']: fail('Only feasible baseline plans can be confirmed or overridden.')
    if run.configuration_version != run.site.configuration_version: fail('Site inputs changed; generate a new plan before approval.')
    if svc.reliability(run.site)['assessment']=='Forecast is stale; refresh it.': fail('Forecast is stale; refresh and rerun before approval.')
    if run.id != run.site.runs.exclude(mode='scenario').first().id: fail('This plan has been superseded; review the latest plan.')
    action=request.data.get('decision'); reason=request.data.get('reason','')
    if action not in ['confirm','override'] or not isinstance(reason,str) or len(reason)>2000: fail('Enter confirm/override and a reason up to 2000 characters.')
    if action=='override' and not reason.strip(): fail('An override reason is required.')
    obj=m.OperatorDecision.objects.create(run=run,user=request.user,decision=action,reason=reason)
    return Response({'id':obj.id,'decision':action,'reason':reason},status=201)


@api_view(['POST'])
def scenarios(request, pk):
    site=site_for(request.user,pk,writable=True)
    baseline=run_for(request.user,request.data.get('baseline_id'))
    preset=request.data.get('preset')
    if preset and preset not in PRESETS: fail('Unknown scenario preset.')
    overrides=deepcopy(PRESETS.get(preset,{}))
    custom=request.data.get('overrides',{})
    if not isinstance(custom,dict): fail('Scenario overrides must be an object.')
    overrides.update(custom)
    name=request.data.get('name') or preset or 'Custom scenario'
    if not isinstance(name,str): fail('Scenario name must be text.')
    result=svc.simulate(site,request.user,baseline,name,overrides)
    return Response(svc.run_summary(result,True),status=201)


@api_view(['GET'])
def portfolio(request):
    admin(request.user)
    data=[svc.reliability(s) for s in sites_for(request.user).filter(archived=False).order_by('id')]
    # Different modes/horizons are separate cohorts: never average incomparable plans.
    groups={}
    for item in data:
        run=item['latest_run']
        if not run or not item['inputs_current'] or run['status'] not in ['optimal','feasible']: continue
        key=f"{run['mode']}|{run['horizon_start']}"
        group=groups.setdefault(key,{'mode':run['mode'],'horizon_start':run['horizon_start'],'site_ids':[], 'critical_kwh':0,'critical_unserved_kwh':0})
        group['site_ids'].append(item['id']); group['critical_kwh']+=run['metrics']['critical_required_kwh']; group['critical_unserved_kwh']+=run['metrics']['critical_unserved_kwh']
    for g in groups.values(): g['weighted_critical_service_pct']=100*(1-g['critical_unserved_kwh']/g['critical_kwh']) if g['critical_kwh'] else None
    return Response({'sites':data,'cohorts':list(groups.values()),'basis':'projected; no measured uptime claims'})


@api_view(['POST'])
def resilience(request):
    admin(request.user)
    results=[]
    for site in sites_for(request.user).filter(archived=False).order_by('id'):
        baseline=site.runs.exclude(mode='scenario').first()
        if not baseline or not svc.reliability(site)['inputs_current'] or baseline.status not in ['optimal','feasible']:
            results.append({'site_id':site.id,'error':'Generate a current feasible baseline first.'}); continue
        for name,overrides in PRESETS.items():
            result=svc.simulate(site,request.user,baseline,name,overrides)
            results.append({'site_id':site.id,'scenario':name,'run_id':result.pk,'status':result.status})
    return Response({'results':results},status=201)
