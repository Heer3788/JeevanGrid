import csv
import io
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import live, models as m, services as svc, forecasting
from .views import site_for, admin, run_for
from .validation import fail


@api_view(['GET','POST'])
def session(request,pk):
    site=site_for(request.user,pk,writable=request.method=='POST')
    if request.method=='POST':
        action=request.data.get('action','start')
        if action=='start':
            baseline = run_for(request.user, request.data['baseline_id']) if request.data.get('baseline_id') else None
            live.start(site,request.user,request.data.get('options',{}),baseline=baseline)
        elif action=='pause':
            from .operations import pause_replay
            pause_replay(request.user, pk)
        else:fail('Choose start or pause.')
    return Response(live.status(site))


@api_view(['POST'])
def event(request,pk):
    site=site_for(request.user,pk,writable=True)
    with transaction.atomic():
        current=get_object_or_404(m.LiveSession,site=site,active=True)
        live.inject(current,request.data.get('event'))
    return Response(live.status(site))


@api_view(['POST'])
def decision(request,pk,command_id):
    site=site_for(request.user,pk,writable=True)
    with transaction.atomic():
        current=get_object_or_404(m.LiveSession,site=site,active=True)
        command=get_object_or_404(m.ControlCommand,pk=command_id,session=current)
        live.review(current,command,request.user,request.data.get('decision'),request.data.get('reason',''))
    return Response(live.status(site))


@api_view(['GET','POST'])
def models(request,pk):
    site=site_for(request.user,pk,writable=request.method=='POST')
    if request.method=='POST':
        admin(request.user)
        config=svc.configuration(site)
        if request.FILES.get('file'):
            rows=forecasting.parse_csv(request.FILES['file'],site);source='csv'
        else:
            if request.data.get('source')!='simulated':fail('Choose simulated training explicitly or upload a CSV.')
            rows=forecasting.demo_dataset(site,config);source='simulated'
        version=forecasting.train(site,config,rows,source)
        with transaction.atomic():
            current=m.LiveSession.objects.filter(site=site,active=True).first()
            if current:current.state['force_replan']=True;current.save(update_fields=['state'])
    else:version=site.forecast_models.first()
    return Response({'id':version.pk,'report':version.report} if version else {'id':None})


@api_view(['GET'])
def dataset(request,pk):
    site=site_for(request.user,pk)
    version=site.forecast_models.first()
    if not version:fail('Train a model first to download its source dataset.')
    output=io.StringIO()
    fields=['timestamp','temperature','baseline_demand_kw','physics_solar_kw','demand_kw','solar_kw']
    writer=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(version.artifacts['dataset'])
    response=HttpResponse(output.getvalue(),content_type='text/csv')
    response['Content-Disposition']=f'attachment; filename="site-{pk}-{version.provenance}-training.csv"'
    return response


@api_view(['POST'])
def strategies(request,pk):
    site=site_for(request.user,pk,writable=True)
    session=m.LiveSession.objects.filter(site=site).first()
    snapshot=live.live_snapshot(session) if session else svc.prepare_snapshot(site,'simulated')
    from .optimizer import solve
    results=[]
    for strategy in live.STRATEGIES:
        snapshot['strategy']=strategy
        result=solve(snapshot)
        results.append({'strategy':strategy,'status':result['status'],'metrics':result['metrics'],'diagnostics':result['diagnostics']})
    return Response({'basis':'Same input snapshot and service priorities; all metrics are projected.', 'results':results})
