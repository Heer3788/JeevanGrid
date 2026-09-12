"""Software-only microgrid plant and supervisory loop. No physical equipment adapter."""
from copy import deepcopy
from datetime import timedelta
import math
import pandas as pd
from django.db import transaction
from django.utils import timezone
from . import models as m, services as svc
from .energy import simulated_weather, solar_power, wind_power
from .forecasting import apply_forecast
from .optimizer import solve
from .validation import fail, number

STRATEGIES = ['lowest_cost', 'balanced', 'lowest_emissions']
EVENTS = ['cloud', 'high_demand', 'generator_outage', 'low_battery', 'restore']


def event(session, message):
    session.events = (session.events+[{'time':session.simulated_at.isoformat(), 'message':message}])[-80:]


def options(data):
    if not isinstance(data,dict): fail('Live options must be an object.')
    if set(data)-{'speed','strategy','conservative','use_ml','carbon_price_inr_per_kg'}: fail('Unknown live option.')
    result = {'speed':30, 'strategy':'balanced', 'conservative':True, 'use_ml':True, 'carbon_price_inr_per_kg':5, **data}
    if result['strategy'] not in STRATEGIES: fail('Unknown dispatch strategy.')
    number(result['speed'],'Clock speed',1,120)
    number(result['carbon_price_inr_per_kg'],'Carbon price INR/kg CO2',0,1000)
    for key in ['conservative','use_ml']:
        if type(result[key]) is not bool: fail(f'{key} must be true or false.')
    return result


def start(site, user, data):
    opts = options(data)
    existing = m.LiveSession.objects.filter(site=site).first()
    if existing and existing.active: fail('Pause the current session before starting a new demonstration.')
    snapshot = svc.prepare_snapshot(site,'simulated')
    start_at = pd.Timestamp.now(tz=site.timezone).normalize()+pd.Timedelta(hours=12)
    weather = simulated_weather(start_at)
    pv = solar_power(weather,snapshot['configuration']['solar'],site.latitude,site.longitude)
    lookup = {pd.Timestamp(r['timestamp']).tz_convert(site.timezone).hour:r for r in snapshot['inputs']}
    snapshot['weather']['intervals'] = weather
    snapshot['inputs'] = [dict(lookup[pd.Timestamp(w['timestamp']).hour],timestamp=w['timestamp'],solar_available=pv[i],
                              wind_available=wind_power(w['wind_speed'],snapshot['configuration']['wind'])) for i,w in enumerate(weather)]
    state = deepcopy(snapshot['state'])
    state.update(generator_kw=snapshot['configuration']['generator']['min_power_kw'] if state['generator_on'] else 0,
        generator_elapsed_hours=24, starts=0, solar_multiplier=1, wind_multiplier=1,
        event_demand_multiplier=1, critical_requested_kwh=0, critical_unserved_kwh=0, fuel_used_l=0,
        cost_inr=0, served_kwh=0, flexible_command={}, flexible_served={}, command_kw=None,
        minimum_soc_pct=state['soc_pct'], elapsed_seconds=0, force_replan=True)
    with transaction.atomic():
        session = m.LiveSession.objects.create(site=site,active=True,created_by=user,
            configuration_version=site.configuration_version,snapshot=snapshot,state=state,options=opts,
            simulated_at=start_at.to_pydatetime(),heartbeat=None,last_plan_at=None,latest_run=None,events=[])
        session.commands.filter(status__in=['proposed','approved']).update(status='superseded')
        event(session, 'Simulation started at local noon. All telemetry and equipment commands are simulated.')
        session.save(update_fields=['events'])
    replan(session.pk,'Initial operating plan')
    return session


@transaction.atomic
def inject(session, kind):
    if kind not in EVENTS: fail('Unknown demonstration event.')
    if not session.active: fail('Start a simulation first.')
    s = session.state
    if kind=='cloud': s['solar_multiplier']=.25
    if kind=='high_demand': s['event_demand_multiplier']=1.5
    if kind=='generator_outage':
        s.update(generator_available=False,generator_on=False,generator_kw=0,command_kw=None,generator_elapsed_hours=0)
    if kind=='low_battery':
        battery=session.snapshot['configuration']['battery']
        s['soc_pct']=max(battery['min_soc'],min(battery['max_soc'],25))
    if kind=='restore': s.update(solar_multiplier=1,event_demand_multiplier=1,generator_available=True)
    s['force_replan']=True
    session.commands.filter(status__in=['proposed','approved']).update(status='superseded')
    event(session, f'{kind.replace("_"," ").title()} event applied; a new plan is required.')
    session.save(update_fields=['state','events'])


def live_snapshot(session):
    snap = deepcopy(session.snapshot); state = session.state
    snap['state'].update({k:state[k] for k in ['soc_pct','fuel_l','generator_available','generator_on','generator_kw','generator_elapsed_hours']})
    snap['state']['provenance']='simulated'
    snap['state']['timestamp']=session.simulated_at.isoformat()
    snap['state']['demand_multiplier']=state.get('demand_multiplier',1)*state['event_demand_multiplier']
    snap['configuration']['policy']['max_starts']=max(0,snap['configuration']['policy']['max_starts']-state['starts'])
    current=pd.Timestamp(session.simulated_at).tz_convert(snap['site']['timezone'])
    original=pd.Timestamp(snap['inputs'][0]['timestamp'])
    offset=int((current-original).total_seconds()//3600)%24
    snap['inputs']=snap['inputs'][offset:]+snap['inputs'][:offset]
    snap['weather']['intervals']=snap['weather']['intervals'][offset:]+snap['weather']['intervals'][:offset]
    for i,r in enumerate(snap['inputs']):
        r['timestamp']=(current+pd.Timedelta(hours=i)).isoformat()
        r['solar_available']*=state['solar_multiplier'];r['wind_available']*=state['wind_multiplier']
        snap['weather']['intervals'][i]['timestamp']=r['timestamp']
    # Daily flexible jobs keep their original deadline and remaining energy across replans.
    for f in snap['configuration']['flexible_loads']:
        f['required_kwh']=max(0,f['required_kwh']-state['flexible_served'].get(f['name'],0))
        f['window_start']=(original.normalize()+pd.Timedelta(hours=f['start_hour'])).isoformat()
        f['window_end']=(original.normalize()+pd.Timedelta(hours=f['end_hour'])).isoformat()
    snap['strategy']=session.options['strategy']
    snap['carbon_price_inr_per_kg']=session.options['carbon_price_inr_per_kg']
    apply_forecast(session.site,snap,session.options['use_ml'],session.options['conservative'])
    snap['live_session_id']=session.pk
    return snap


def replan(pk, reason):
    session=m.LiveSession.objects.select_related('site','created_by').get(pk=pk)
    if not session.active: return
    snapshot=live_snapshot(session)
    result=solve(snapshot)
    with transaction.atomic():
        current=m.LiveSession.objects.get(pk=pk)
        if not current.active or current.state!=session.state or current.options!=session.options: return
        run=svc.persist_run(session.site,session.created_by,'live_simulation',snapshot,result)
        current.latest_run=run;current.last_plan_at=current.simulated_at;current.state['force_replan']=False
        current.commands.filter(status__in=['proposed','approved','executing']).update(status='superseded')
        event(current, f'{reason}: {result["status"]}; dispatch recalculated from current SOC and fuel.')
        if result['intervals']:
            first=result['intervals'][0]
            proposal={'generator_kw':first['diesel_power'],'generator_on':bool(first['diesel_on']),
                'battery_policy':'Balance supply within SOC and power limits',
                'planned_battery_kw':first['battery_discharge']-first['battery_charge'],
                'flexible_tasks':first['flexible_tasks'],
                'reason':f'First-hour setpoint from the {session.options["strategy"].replace("_"," ")} plan. Review projected service and reserve before approval.'}
            m.ControlCommand.objects.create(session=current,run=run,proposal=proposal,
                expires_at=current.simulated_at+timedelta(minutes=5))
        current.save(update_fields=['latest_run','last_plan_at','state','events'])


@transaction.atomic
def review(session, command, user, decision, reason):
    if decision not in ['approve','reject']: fail('Choose approve or reject.')
    if not isinstance(reason,str) or len(reason)>500: fail('Reason must be at most 500 characters.')
    if decision=='reject' and not reason.strip(): fail('Give a reason for rejecting the proposal.')
    if not session.active or command.status!='proposed': fail('This command is no longer awaiting approval.')
    if not session.heartbeat or (timezone.now()-session.heartbeat).total_seconds()>15: fail('Telemetry is stale; wait for the live worker before reviewing commands.')
    if command.expires_at<=session.simulated_at or command.run_id!=session.latest_run_id: fail('Proposal expired; use the newest plan.')
    if session.site.configuration_version!=session.configuration_version: fail('Site configuration changed; restart the simulation.')
    command.status='approved' if decision=='approve' else 'rejected'
    command.reviewed_by=user;command.reviewed_at=timezone.now();command.reason=reason;command.save()


def advance(pk, wall_seconds=2):
    """One worker owns time; browser refreshes never advance the plant."""
    with transaction.atomic():
        session=m.LiveSession.objects.select_related('site').get(pk=pk)
        if not session.active: return
        if session.site.archived or session.configuration_version!=session.site.configuration_version:
            session.active=False;event(session,'Site changed or archived. Simulation paused; restart with current configuration.')
            session.save(update_fields=['active','events']);return
        c=session.snapshot['configuration'];s=session.state;b=c['battery'];g=c['generator']
        seconds=wall_seconds*session.options['speed'];dt=seconds/3600
        t=pd.Timestamp(session.simulated_at).tz_convert(session.site.timezone)
        first=pd.Timestamp(session.snapshot['inputs'][0]['timestamp'])
        index=int((t-first).total_seconds()//3600)%24
        row=session.snapshot['inputs'][index]
        pending=session.commands.filter(status='approved').first()
        verification=None
        if pending:
            p=pending.proposal;want=p['generator_kw'];on=p['generator_on'];old=s['generator_on']
            error=None
            if pending.expires_at<=session.simulated_at or pending.run_id!=session.latest_run_id: error='Stale command.'
            elif on and not s['generator_available']: error='Generator unavailable.'
            elif on!=old and s['generator_elapsed_hours'] < g.get('min_up_hours' if old else 'min_down_hours',1): error='Minimum run/cooldown time has not elapsed.'
            elif on and not old and s['starts']>=c['policy']['max_starts']: error='Maximum starts reached.'
            elif on and t.hour not in c['policy']['allowed_generator_hours']: error='Generator operation is outside allowed hours.'
            if error:
                pending.status='failed';pending.result={'error':error,'provenance':'simulated'};pending.save()
                event(session,error);s['force_replan']=True
            else:
                if on!=old:
                    s['generator_elapsed_hours']=0
                    if on:s['starts']+=1;s['cost_inr']+=g['start_cost']
                s['generator_on']=on;s['command_kw']=want
                # Startup step to minimum stable loading; ongoing changes obey the ramp.
                if on and not old:s['generator_kw']=g['min_power_kw']
                if not on:s['generator_kw']=0
                s['flexible_command']={f['name']:f['power_kw'] for f in p['flexible_tasks']}
                pending.status='executing';pending.result={'executed_at':session.simulated_at.isoformat(),'provenance':'simulated'};pending.save()
                event(session, 'Approved setpoints applied to the simulated plant; awaiting telemetry verification.')
        if s['generator_on']:
            if not s['generator_available'] or s['fuel_l']<=0 or t.hour not in c['policy']['allowed_generator_hours']:
                s.update(generator_on=False,generator_kw=0,command_kw=None,generator_elapsed_hours=0);s['force_replan']=True
            else:
                target=s['command_kw'] if s['command_kw'] is not None else s['generator_kw']
                ramp=g.get('ramp_kw_per_hour',g['capacity_kw'])*dt
                s['generator_kw']=max(g['min_power_kw'],min(g['capacity_kw'],s['generator_kw']+max(-ramp,min(ramp,target-s['generator_kw']))))
        diesel=s['generator_kw'] if s['generator_on'] else 0
        litres=(g['fuel_slope']*diesel+g['fuel_intercept']*s['generator_on'])*dt
        if litres>s['fuel_l']:
            diesel=0;litres=0;s.update(generator_on=False,generator_kw=0,command_kw=None);s['force_replan']=True
        s['fuel_l']=max(0,s['fuel_l']-litres);s['fuel_used_l']+=litres
        solar=row['solar_available']*(.86+.04*math.sin(t.hour/3))*s['solar_multiplier'];wind=row['wind_available']*s['wind_multiplier']
        temperature=session.snapshot['weather']['intervals'][index]['temperature']
        factor=s.get('demand_multiplier',1)*s['event_demand_multiplier']*(1+.12*(t.dayofweek>=5)+.008*(temperature-24))
        critical=row['critical_kw']*factor;normal=row['normal_kw']*factor
        tasks={}
        for f in c['flexible_loads']:
            remaining=max(0,f['required_kwh']-s['flexible_served'].get(f['name'],0))
            tasks[f['name']]=min(s['flexible_command'].get(f['name'],0),f['power_kw'],remaining/dt) if f['start_hour']<=t.hour<f['end_hour'] else 0
        demand=critical+normal+sum(tasks.values())
        energy=s['soc_pct']/100*b['capacity_kwh'];net=solar+wind+diesel-demand
        charge=min(max(0,net),b['max_charge_kw'],max(0,b['max_soc']/100*b['capacity_kwh']-energy)/(dt*b['charge_efficiency']))
        discharge=min(max(0,-net),b['max_discharge_kw'],max(0,energy-b['min_soc']/100*b['capacity_kwh'])*b['discharge_efficiency']/dt)
        supply=max(0,solar+wind+diesel+discharge-charge)
        served_critical=min(critical,supply);remaining=max(0,supply-served_critical)
        served_normal=min(normal,remaining);remaining=max(0,remaining-served_normal)
        for name,power in tasks.items():
            actual=min(power,remaining);remaining-=actual
            s['flexible_served'][name]=s['flexible_served'].get(name,0)+actual*dt
        served=min(demand,supply);curtailed=max(0,supply-served)
        s['soc_pct']=(energy+charge*dt*b['charge_efficiency']-discharge*dt/b['discharge_efficiency'])/b['capacity_kwh']*100
        s['minimum_soc_pct']=min(s['minimum_soc_pct'],s['soc_pct'])
        s['critical_requested_kwh']+=critical*dt;s['critical_unserved_kwh']+=(critical-served_critical)*dt
        s['served_kwh']+=served*dt;s['cost_inr']+=litres*s.get('diesel_price',g['diesel_price'])+discharge*dt*b['replacement_cost']/b['lifetime_throughput_kwh']
        s['generator_elapsed_hours']+=dt;s['elapsed_seconds']+=seconds
        previous=s.get('telemetry',{})
        if previous and (abs(demand-previous['demand_kw'])>max(5,previous['demand_kw']*.2) or abs(solar-previous['solar_kw'])>max(5,previous['solar_kw']*.2)):
            s['force_replan']=True
        session.simulated_at+=timedelta(seconds=seconds);session.heartbeat=timezone.now()
        telemetry={'timestamp':session.simulated_at.isoformat(),'interval_start':t.isoformat(),'interval_seconds':seconds,
            'solar_kw':solar,'wind_kw':wind,'demand_kw':demand,'generator_kw':diesel,'generator_on':s['generator_on'],
            'battery_charge_kw':charge,'battery_discharge_kw':discharge,'soc_pct':s['soc_pct'],'fuel_l':s['fuel_l'],
            'served_kw':served,'critical_unserved_kw':critical-served_critical,'curtailed_kw':curtailed,
            'balance_error_kw':solar+wind+diesel+discharge-charge-served-curtailed,
            'forecast_demand_kw':row['critical_kw']+row['normal_kw'],'forecast_solar_kw':row['solar_available'],'provenance':'simulated'}
        s['telemetry']=telemetry
        for command in session.commands.filter(status='executing'):
            p=command.proposal
            if bool(s['generator_on'])==p['generator_on'] and abs(diesel-p['generator_kw'])<.05:
                command.status='verified';command.result.update(verified_at=session.simulated_at.isoformat(),telemetry=telemetry)
                event(session,'Command verified against fresh simulated generator output and energy balance.')
            elif session.simulated_at>command.expires_at+timedelta(hours=1):
                command.status='failed';command.result['error']='Setpoint verification timed out.'
            command.save(update_fields=['status','result'])
        if s['elapsed_seconds']>=86400:
            session.active=False;event(session,'24-hour demonstration complete. Review the observed simulation metrics.')
        if not session.samples.exists() or (session.simulated_at-session.samples.first().timestamp).total_seconds()>=60:
            m.TelemetrySample.objects.create(session=session,timestamp=session.simulated_at,data=telemetry)
        session.save(update_fields=['state','simulated_at','heartbeat','active','events'])
        due=session.active and (s['force_replan'] or not session.last_plan_at or (session.simulated_at-session.last_plan_at).total_seconds()>=300)
    if due: replan(pk,'Operating conditions changed' if s['force_replan'] else 'Five-minute rolling update')


def status(site):
    session=m.LiveSession.objects.filter(site=site).select_related('latest_run').first()
    version=site.forecast_models.first()
    model={'id':version.pk,'report':version.report,'configuration_version':version.configuration_version} if version else None
    if not session:return {'session':None,'model':model}
    s=session.state
    stale=not session.heartbeat or (timezone.now()-session.heartbeat).total_seconds()>15
    requested=s.get('critical_requested_kwh',0)
    return {'session':{'id':session.pk,'active':session.active,'simulated_at':session.simulated_at.isoformat(),
            'heartbeat':session.heartbeat.isoformat() if session.heartbeat else None,'stale':stale,'options':session.options,
            'telemetry':s.get('telemetry'), 'events':session.events,'last_plan_at':session.last_plan_at,
            'evidence':{'critical_service_pct':100*(1-s['critical_unserved_kwh']/requested) if requested else None,
                'critical_unserved_kwh':s.get('critical_unserved_kwh',0),'diesel_litres':s.get('fuel_used_l',0),
                'emissions_kg':s.get('fuel_used_l',0)*session.snapshot['configuration']['generator']['emissions_factor'],
                'cost_inr':s.get('cost_inr',0),'minimum_soc_pct':s.get('minimum_soc_pct'),
                'verified_commands':session.commands.filter(status='verified').count(),'basis':'Observed in software simulation'},
            'commands':list(session.commands.values('id','status','proposal','result','reason','expires_at','reviewed_at')[:12]),
            'samples':list(reversed(list(session.samples.values_list('data',flat=True)[:120]))),
            'run':svc.run_summary(session.latest_run,details=True) if session.latest_run else None},'model':model}
