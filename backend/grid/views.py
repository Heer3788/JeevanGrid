import csv
import io
import math
from copy import deepcopy
import pandas as pd
import requests
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from . import models as m, services as svc, operations
from .defaults import default_configuration
from .validation import fail, validate_site, validate_reading, PRESETS
from .weather import get_weather


class LoginThrottle(AnonRateThrottle):
    rate = '20/min'


from .access import role, admin, sites_for, site_for, run_for


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
@permission_classes([AllowAny])
def demo_accounts(request):
    from .demo import ACCOUNTS, DEMO_PASSWORD
    if not settings.DEBUG:
        return Response([])
    result = []
    for account in ACCOUNTS:
        user = get_user_model().objects.filter(username=account['email'], is_active=True).first()
        if user and m.UserRole.objects.filter(user=user).exists():
            result.append({**account, 'quick_login': user.check_password(DEMO_PASSWORD)})
    return Response(result)


@api_view(['GET'])
def team(request):
    admin(request.user)
    accounts=m.UserRole.objects.filter(organization=role(request.user).organization).select_related('user')
    return Response([{**account(r.user), 'sites':list(sites_for(request.user).filter(assignments__user=r.user).values('id','name'))} for r in accounts])


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
    from .locations import search
    try:return Response(search(request.query_params.get('q',''),request.query_params.get('state','')))
    except LookupError as e:return Response({'detail':str(e)},status=502)


from .operations import assign


@api_view(['GET','POST'])
def sites(request):
    if request.method == 'GET': return Response([svc.site_summary(s) for s in sites_for(request.user).order_by('id')])
    site = operations.save_site(request.user, dict(request.data))
    return Response(svc.site_summary(site), status=201)


@api_view(['GET','PATCH'])
def site_detail(request, pk):
    site = site_for(request.user, pk)
    if request.method == 'PATCH':
        site = operations.save_site(request.user, dict(request.data), pk)
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
    reading = operations.record_reading(request.user, pk, dict(request.data))
    return Response({'id':reading.pk, 'state':reading.data, 'timestamp':reading.timestamp}, status=201)


@api_view(['POST'])
def load_import(request, pk):
    return Response(operations.import_load(request.user, pk, request.FILES.get('file')))

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


@api_view(['GET'])
def run_detail(request, pk): return Response(svc.run_summary(run_for(request.user,pk),True))


@api_view(['GET'])
def run_analysis(request, pk):
    from .intelligence import analyze_run
    return Response(analyze_run(run_for(request.user, pk)))


@api_view(['GET', 'POST'])
def run_scenarios(request, pk):
    run = run_for(request.user, pk)
    if request.method == 'POST':
        site_for(request.user, run.site_id, writable=True)
        if run.mode == 'scenario' or run.status not in ['optimal', 'feasible']:
            fail('A feasible original plan is required.')
        job, created = m.PlanAssessment.objects.get_or_create(run=run)
        if job.status == 'failed' and request.data.get('retry') is True:
            job.status, job.error = 'pending', ''
            job.save(update_fields=['status', 'error', 'updated_at'])
        return Response({'status': job.status, 'error': job.error}, status=202)
    return Response([svc.run_summary(s.result) for s in run.scenarios.select_related('result', 'result__site').order_by('-result_id')])


@api_view(['GET'])
def run_list(request):
    q=m.OptimizationRun.objects.filter(site__in=sites_for(request.user)).select_related('site')
    if request.query_params.get('site_id'): q=q.filter(site_id=request.query_params['site_id'])
    if request.query_params.get('kind')=='scenario': q=q.filter(mode='scenario')
    if request.query_params.get('kind')=='plan': q=q.exclude(mode__in=['scenario', 'live_simulation'])
    return Response([svc.run_summary(r) for r in q[:100]])


@api_view(['POST'])
def decision(request, pk):
    return Response(operations.review_plan(request.user, pk, request.data), status=201)

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
        baseline=svc.latest_plan(site)
        if not baseline or not svc.reliability(site)['inputs_current'] or baseline.status not in ['optimal','feasible']:
            results.append({'site_id':site.id,'error':'Generate a current feasible baseline first.'}); continue
        for name,overrides in PRESETS.items():
            result=svc.simulate(site,request.user,baseline,name,overrides)
            results.append({'site_id':site.id,'scenario':name,'run_id':result.pk,'status':result.status})
    return Response({'results':results},status=201)
