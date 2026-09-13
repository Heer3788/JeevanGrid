"""Resolve targets against current permissions and validate all workflow inputs."""
from copy import deepcopy
from django.shortcuts import get_object_or_404
from .. import models as m, services as svc, validation as v
from ..access import role, admin, sites_for, site_for, run_for
from ..defaults import default_configuration
from .catalog import CATALOG, enabled
from .provider import BASE_KEYS, SITE_KEYS, READING_KEYS

class Clarification(Exception):pass

def need(condition, message):
    if not condition:raise Clarification(message)

def scope(job):
    conversation=job.conversation; user=conversation.owner
    if not user.__class__.objects.filter(pk=user.pk,is_active=True).exists():v.fail('This account is no longer active.')
    if role(user).organization_id!=conversation.organization_id:v.fail('Conversation organization is no longer accessible.')
    if conversation.site_id:site_for(user,conversation.site_id)
    for pk in job.context.get('site_ids',[]):site_for(user,pk)
    return user

def resolve_name(user,name):
    if not isinstance(name,str) or not name.strip():v.fail('A site name is required.')
    rows=list(sites_for(user).filter(name__iexact=name))
    if not rows:rows=list(sites_for(user).filter(name__icontains=name)[:6])
    need(len(rows)==1,'Specify one accessible site. Matches: '+(', '.join(f'{s.name} (#{s.pk})' for s in rows) or 'none'))
    return rows[0].pk

def merge(base, patch):
    result=deepcopy(base)
    for key,value in patch.items():
        if isinstance(value,dict) and isinstance(result.get(key),dict):result[key]=merge(result[key],value)
        else:result[key]=value
    return result

def validate(job):
    user=scope(job); name=job.workflow;p=deepcopy(job.inputs)
    if not enabled(name):v.fail('This workflow is not enabled.')
    if CATALOG[name].admin:admin(user)
    allowed={'site_id','site_name','question','question_kind'}
    if name!='command.review':allowed.add('use_previous')
    steps=CATALOG[name].steps
    if 'site' in steps and name not in ['site.archive','site.restore']:allowed|={'site_data','configuration'}
    if name in ['site.create','create_and_plan']:allowed.add('accept_template')
    if 'reading' in steps:allowed.add('readings')
    if 'weather' in steps:allowed|={'mode','date'}
    if 'scenario' in steps:allowed|={'run_id','overrides'}
    if 'compare' in steps:allowed|={'run_ids','site_ids','site_names'}
    if name=='replay.start':allowed|={'run_id','speed'}
    if name in ['replay.pause','replay.event']:allowed.add('session_id')
    if name=='replay.event':allowed.add('event')
    if name=='plan.review':allowed|={'run_id','decision','reason'}
    if name=='command.review':allowed|={'command_id','session_id','decision','reason'}
    if name=='forecast.train':allowed|={'training_source','attachment_id'}
    if name=='demand.import':allowed.add('attachment_id')
    if 'report' in steps:allowed.add('format')
    if name=='report.export':allowed|={'kind','run_id','run_ids','site_ids','site_names','session_id'}
    if name=='question':allowed|={'run_id','site_ids','site_names'}
    if set(p)-allowed:v.fail('These inputs are not used by the selected workflow: '+', '.join(sorted(set(p)-allowed)))
    if p.pop('use_previous',False):
        previous=job.conversation.workflows.filter(status='succeeded').exclude(pk=job.pk).order_by('-pk').first()
        need(previous is not None,'There is no completed result to refer to. Specify the site or plan.')
        scope(previous)
        if previous.result.get('kind')=='comparison' and name in ['compare','compare_and_report','report.export']:
            p.setdefault('run_ids',[r['id'] for r in previous.result['runs']])
        elif name in ['scenario.test','test_and_compare','plan.review','replay.start','report.export'] and previous.context.get('run_id'):
            p.setdefault('run_id',previous.context['run_id'])
        elif len(previous.context.get('site_ids',[]))==1:p.setdefault('site_id',previous.context['site_ids'][0])
        else:raise Clarification('The previous result does not identify one target for this request. Specify the site or plan.')
    for key in ['site_id','run_id','session_id','command_id','attachment_id']:
        if key in p and (type(p[key]) is not int or p[key]<1):v.fail(key+' must be a positive integer.')
    for key in ['site_ids','run_ids']:
        if key in p and (not isinstance(p[key],list) or not 2<=len(p[key])<=5 or any(type(i) is not int or i<1 for i in p[key])):v.fail(key+' requires 2–5 identifiers.')
    if 'site_name' in p:p['site_id']=resolve_name(user,p['site_name'])
    if 'site_names' in p:
        if not isinstance(p['site_names'],list) or not 2<=len(p['site_names'])<=5:v.fail('Choose 2–5 site names.')
        p['site_ids']=[resolve_name(user,n) for n in p['site_names']]
    ids=set(p.get('site_ids',[]));site=None
    for run_id in p.get('run_ids',[])+([p['run_id']] if p.get('run_id') else []):ids.add(run_for(user,run_id).site_id)
    if p.get('session_id'):
        session=get_object_or_404(m.LiveSession,pk=p['session_id'],site__in=sites_for(user));ids.add(session.site_id)
    if p.get('command_id'):
        command=get_object_or_404(m.ControlCommand,pk=p['command_id'],session__site__in=sites_for(user));ids.add(command.session.site_id)
        if p.get('session_id') and p['session_id']!=command.session_id:v.fail('Command belongs to another replay.')
        p['session_id']=command.session_id
    if p.get('site_id'):ids.add(p['site_id'])
    if job.conversation.site_id:
        if ids and ids!={job.conversation.site_id}:v.fail('This conversation is limited to its site. Use an organization conversation for other sites.')
        p['site_id']=job.conversation.site_id;ids.add(p['site_id'])
    if len(ids)==1:p['site_id']=next(iter(ids))
    for pk in ids:site_for(user,pk)
    if p.get('site_id'):site=site_for(user,p['site_id'])
    creating=name in ['site.create','create_and_plan']
    if creating:
        if job.conversation.site_id:v.fail('Create sites from an organization conversation.')
        data=p.get('site_data',{});need(isinstance(data,dict),'Supply the new site configuration.')
        if data.get('name') and data.get('state') and data.get('district') and ('latitude' not in data or 'longitude' not in data):
            from ..locations import search
            try:choices=search(data['district'],data['state'])['results']
            except LookupError:choices=[]
            job.context['location_choices']=choices
            raise Clarification('Choose the correct location below, or provide latitude, longitude and timezone. '+('Source: Open-Meteo / GeoNames.' if choices else 'Location search had no available match.'))
        required=['name','state','district','latitude','longitude','timezone']
        need(all(k in data for k in required),'Provide new site '+', '.join(k for k in required if k not in data)+'. Coordinates must be selected or explicitly supplied.')
        v.validate_site(data)
        if p.get('accept_template') is not True:need('configuration' in p,'Supply the full equipment configuration, or explicitly accept the demo template.')
        p['configuration']=v.validate_configuration(merge(default_configuration(),p.get('configuration',{})) if p.get('accept_template') is True else p['configuration'])
    elif name not in ['question','compare','compare_and_report','report.export']:
        need(site is not None,'Which site should this workflow use?')
    if site and name not in ['question','compare','compare_and_report','report.export','site.restore'] and site.archived:v.fail('Restore this site before changing it.')
    if 'configuration' in p and not isinstance(p['configuration'],dict):v.fail('Configuration must be an object.')
    if 'configuration' in p and not creating:p['configuration']=v.validate_configuration(merge(svc.configuration(site),p['configuration']))
    if name in ['site.update','site.assign']:
        need(bool(p.get('site_data') or p.get('configuration')),'Which site fields should change?')
        v.validate_site(p.get('site_data',{}))
        if name=='site.assign':need('operator_ids' in p.get('site_data',{}),'Provide operator user IDs from People & access.')
    if name in ['readings.record','readings_and_plan']:
        need(bool(p.get('readings')),'Which persistent readings should be recorded? For a replay change, request a replay event.')
        v.validate_reading(p['readings'],svc.configuration(site))
    if 'weather' in CATALOG[name].steps:
        need(p.get('mode') in ['simulated','forecast','historical'],'Choose simulated weather, live weather forecast, or historical NASA weather.')
        if p.get('date') and p['mode']!='historical':v.fail('Explicit dates are supported for NASA historical planning. Live and simulated planning use the next 24 hours.')
        if p['mode']=='historical':need(bool(p.get('date')),'Which historical date (YYYY-MM-DD) should NASA weather use?')
    if 'scenario' in CATALOG[name].steps:
        need(bool(p.get('overrides')),'Specify the condition to test: solar, wind, demand, fuel price, starting SOC or outage hours.')
        v.validate_overrides(p['overrides'])
    if name in ['replay.start','scenario.test','test_and_compare','plan.review'] and not p.get('run_id'):
        baseline=svc.latest_plan(site);need(baseline is not None,'Generate a baseline plan first.');p['run_id']=baseline.pk
    if p.get('run_id') and site and run_for(user,p['run_id']).site_id!=site.pk:v.fail('Plan does not belong to this site.')
    if name in ['replay.event','replay.pause']:
        if not p.get('session_id'):
            session=site.live_sessions.filter(active=True).first();need(session is not None,'Start a replay first.');p['session_id']=session.pk
        current=get_object_or_404(m.LiveSession,pk=p['session_id'],site=site)
        if not current.active:v.fail('This replay is paused. Start a new replay instead.')
    if name=='replay.event':need(p.get('event') in ['cloud','high_demand','low_battery','generator_outage','restore'],'Choose cloud cover, demand +50%, battery at 25%, generator outage, or restore.')
    if name=='command.review':
        need(p.get('command_id') is not None,'Specify the exact current command ID to approve or reject.')
        need(p.get('decision') in ['approve','reject'],'Explicitly approve or reject the selected simulated command.')
    if name=='plan.review':need(p.get('decision') in ['confirm','override'],'Confirm the plan, or override it with a reason.')
    if name in ['compare','compare_and_report']:need(bool(p.get('run_ids') or p.get('site_ids')),'Select 2–5 saved plans or sites to compare.')
    if name=='demand.import' or (name=='forecast.train' and p.get('training_source')=='csv'):
        need(bool(p.get('attachment_id')),'Attach the CSV file to this conversation first.')
        get_object_or_404(m.ChatAttachment,pk=p['attachment_id'],conversation=job.conversation)
    if name=='forecast.train':need(p.get('training_source') in ['csv','simulated'],'Train from an uploaded CSV or explicitly choose 90 simulated days.')
    if 'report' in CATALOG[name].steps:
        need(p.get('format') in ['pdf','csv','json'],'Choose PDF, CSV or JSON export.')
        if name=='report.export':
            need(p.get('kind') in ['plan','replay','comparison'],'Export a plan, replay or comparison?')
            if p['kind']=='plan' and not p.get('run_id'):
                need(site is not None,'Specify a site or saved plan.');r=svc.latest_plan(site);need(r is not None,'Generate a plan first.');p['run_id']=r.pk
            if p['kind']=='replay':need(bool(p.get('session_id')),'Specify the replay session ID to export.')
            if p['kind']=='comparison':need(bool(p.get('site_ids') or p.get('run_ids')),'Select 2–5 sites or plans.')
    p.pop('site_name',None);p.pop('site_names',None)
    return p,{'site_ids':sorted(ids),'versions':{str(pk):site_for(user,pk).configuration_version for pk in ids}}
