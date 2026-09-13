"""Read-back postconditions. These never call a language model."""
import math
from datetime import datetime, timedelta
from .. import models as m, services as svc
from ..reports import digest

from rest_framework.exceptions import APIException

class VerificationError(APIException):
    status_code=409
    default_code='evidence_verification_failed'

def require(condition, message):
    if not condition: raise VerificationError(message)

def close(actual, expected, name, tolerance=.001):
    require(type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=tolerance,
            f'Verification failed: {name}.')

def verify_run(run, expected_hash=None):
    run.refresh_from_db()
    if expected_hash:require(digest(run.snapshot)==expected_hash,'Saved plan inputs differ from the frozen request.')
    rows=list(run.intervals.values_list('data',flat=True))
    if run.status in ['infeasible','failed']:
        require(not rows and not run.metrics and bool(run.diagnostics),'Invalid unsuccessful solver result.')
        return {'passed':True,'outcome':run.status,'checks':['Frozen inputs','Saved solver diagnostic']}
    require(run.status in ['optimal','feasible'],'Unknown solver outcome.')
    require(len(rows)==24,'A feasible plan must have 24 hourly intervals.')
    c=run.snapshot['configuration'];b=c['battery'];g=c['generator'];metrics=run.metrics
    start=datetime.fromisoformat(run.snapshot['inputs'][0]['timestamp'])
    initial=run.snapshot.get('overrides',{}).get('starting_soc',run.snapshot['state']['soc_pct'])
    previous=initial
    for i,r in enumerate(rows):
        require(datetime.fromisoformat(r['timestamp'])==start+timedelta(hours=i),'Invalid dispatch horizon.')
        for key,value in r.items():
            if type(value) in (float,int):require(math.isfinite(value) and value>=-.001,'Non-finite or negative dispatch value: '+key)
        raw=run.snapshot['inputs'][i];o=run.snapshot.get('overrides',{});factor=run.snapshot['state'].get('demand_multiplier',1)*o.get('demand_multiplier',1)
        close(r['critical_required'],raw['critical_kw']*factor,'critical demand input')
        close(r['normal_required'],raw['normal_kw']*factor,'normal demand input')
        close(r['solar_available'],min(c['solar']['capacity_kw'],raw['solar_available']*o.get('solar_multiplier',1)),'solar input')
        close(r['wind_available'],min(c['wind']['capacity_kw'],raw['wind_available']*o.get('wind_multiplier',1)),'wind input')
        require(r['critical_unserved']<=r['critical_required']+.001 and r['normal_unserved']<=r['normal_required']+.001,'Shortage exceeds demand.')
        close(r['solar_used']+r['wind_used']+r['battery_discharge']+r['diesel_power'],r['served_load']+r['battery_charge'],'energy balance')
        close(r['soc_start'],previous,'battery continuity')
        expected=r['soc_start']+(r['battery_charge']*b['charge_efficiency']-r['battery_discharge']/b['discharge_efficiency'])/b['capacity_kwh']*100
        close(r['battery_soc'],expected,'battery energy')
        require(b['min_soc']-.001<=r['battery_soc']<=b['max_soc']+.001,'Battery outside physical limits.')
        require(r['battery_charge']<=b['max_charge_kw']+.001 and r['battery_discharge']<=b['max_discharge_kw']+.001,'Battery power outside limits.')
        require(min(r['battery_charge'],r['battery_discharge'])<.001,'Simultaneous charge and discharge.')
        require(r['solar_used']<=r['solar_available']+.001 and r['wind_used']<=r['wind_available']+.001,'Generation exceeds availability.')
        require(r['diesel_on'] in (0,1) and r['diesel_start'] in (0,1),'Generator flags must be binary.')
        require(g['min_power_kw']*r['diesel_on']-.001<=r['diesel_power']<=g['capacity_kw']*r['diesel_on']+.001,'Generator outside on/off power limits.')
        if not run.snapshot['state']['generator_available']:require(r['diesel_on']==0,'Unavailable generator is running.')
        close(r['diesel_litres'],g['fuel_slope']*r['diesel_power']+g['fuel_intercept']*r['diesel_on'],'fuel use')
        close(r['served_load'],r['critical_required']-r['critical_unserved']+r['normal_required']-r['normal_unserved']+r['flexible_load_scheduled'],'served demand')
        previous=r['battery_soc']
    total=lambda k:sum(r[k] for r in rows)
    for metric,key in [('diesel_litres','diesel_litres'),('served_kwh','served_load'),('critical_unserved_kwh','critical_unserved'),('normal_unserved_kwh','normal_unserved')]:close(metrics[metric],total(key),metric)
    close(metrics['minimum_soc_pct'],min([initial]+[r['battery_soc'] for r in rows]),'minimum battery')
    close(metrics['emissions_kg_co2'],total('diesel_litres')*g['emissions_factor'],'emissions')
    close(metrics['dispatch_cost_inr'],metrics['fuel_cost_inr']+metrics['generator_start_cost_inr']+metrics['battery_wear_cost_inr'],'dispatch cost')
    price=run.snapshot['state']['diesel_price']*run.snapshot.get('overrides',{}).get('fuel_price_multiplier',1)
    close(metrics['fuel_cost_inr'],total('diesel_litres')*price,'fuel cost')
    close(metrics['unserved_kwh'],max(0,metrics['requested_kwh']-metrics['served_kwh']),'unserved energy')
    factor=run.snapshot['state'].get('demand_multiplier',1)*run.snapshot.get('overrides',{}).get('demand_multiplier',1)
    flex_required=sum(f['required_kwh']*(1 if 'window_start' in f else factor) for f in c['flexible_loads'])
    requested=total('critical_required')+total('normal_required')+flex_required
    renewable=total('solar_used')+total('wind_used');primary=renewable+total('diesel_power')
    for metric,value in {
        'critical_required_kwh':total('critical_required'),'requested_kwh':requested,
        'flexible_unserved_kwh':max(0,flex_required-total('flexible_load_scheduled')),
        'generator_start_cost_inr':total('diesel_start')*g['start_cost'],
        'battery_wear_cost_inr':total('battery_discharge')*b['replacement_cost']/b['lifetime_throughput_kwh'],
        'generator_starts':total('diesel_start'),'generator_hours':total('diesel_on'),
        'terminal_soc_pct':rows[-1]['battery_soc'],'renewable_curtailed_kwh':total('renewable_curtailment'),
        'reserve_compliance_pct':100*sum(r['battery_soc']>=b['reserve_soc']-1e-5 for r in rows)/24,
    }.items():close(metrics[metric],value,metric)
    for metric,numerator,denominator in [
        ('critical_load_served_pct',100*(total('critical_required')-total('critical_unserved')),total('critical_required')),
        ('total_energy_served_pct',100*total('served_load'),requested),('renewable_share_pct',100*renewable,primary),
        ('diesel_l_per_kwh',total('diesel_litres'),total('served_load')),('cost_per_kwh',metrics['dispatch_cost_inr'],total('served_load')),
    ]:
        if denominator>1e-9:close(metrics[metric],numerator/denominator,metric)
        else:require(metrics[metric] is None,'Undefined denominator must not be displayed as zero.')
    require(total('diesel_litres')<=run.snapshot['state']['fuel_l']+.001,'Fuel availability exceeded.')
    require(rows[-1]['battery_soc']>=c['policy']['terminal_soc']-.001,'Ending battery target violated.')
    return {'passed':True,'outcome':run.status,'checks':['Frozen inputs','24 hourly intervals','Energy balance','Battery limits and continuity','Fuel and metrics'],
            'findings':run.diagnostics}

def verify_receipt(receipt):
    kind=receipt['kind']
    if kind=='run':
        run=m.OptimizationRun.objects.get(pk=receipt['id'])
        if receipt.get('baseline_id'):
            require(run.scenario.baseline_id==receipt['baseline_id'] and run.scenario.overrides==receipt['overrides'],'Scenario linkage or overrides changed.')
            verify_run(run.scenario.baseline,receipt['baseline_hash'])
        return verify_run(run,receipt['snapshot_hash'])
    if kind=='site':
        site=m.Site.objects.get(pk=receipt['id'])
        require(site.organization_id==receipt['organization_id'],'Site organization mismatch.')
        # Later explicit changes are allowed; the receipt was checked at the saved version.
        if site.configuration_version==receipt['version']:
            for key,value in receipt['expected'].items():
                current=svc.configuration(site) if key=='configuration' else sorted(site.assignments.values_list('user_id',flat=True)) if key=='operator_ids' else getattr(site,key)
                require(current==(sorted(value) if key=='operator_ids' else value),'Site read-back mismatch: '+key)
        return {'passed':True,'checks':['Organization','Accepted fields read back'],'version':receipt['version']}
    if kind=='reading':
        reading=m.SiteReading.objects.get(pk=receipt['id']);require(reading.data==receipt['expected'],'Reading read-back mismatch.')
    elif kind=='import':
        site=m.Site.objects.get(pk=receipt['site_id'])
        if site.configuration_version==receipt['version']:
            rows=list(site.load_profile.intervals.values('timestamp','critical_kw','normal_kw','flexible_kw'))
            require(len(rows)==24 and digest(rows)==receipt['rows_hash'],'Imported rows differ from accepted CSV.')
    elif kind=='decision':
        d=m.OperatorDecision.objects.get(pk=receipt['id']);require(d.decision==receipt['decision'] and d.reason==receipt['reason'] and d.run_id==receipt['run_id'],'Review read-back mismatch.')
    elif kind=='model':
        model=m.ForecastModel.objects.get(pk=receipt['id']);require(digest(model.report)==receipt['report_hash'] and digest(model.artifacts['dataset'])==receipt['dataset_hash'],'Training result mismatch.')
    elif kind=='event':
        e=m.ReplayEvent.objects.get(pk=receipt['id']);require(e.session_id==receipt['session_id'] and digest(e.data)==receipt['data_hash'],'Replay event mismatch.')
    elif kind=='session':
        session=m.LiveSession.objects.get(pk=receipt['id'])
        require(digest(session.snapshot)==receipt['snapshot_hash'],'Replay baseline mismatch.')
        require(session.event_records.filter(pk=receipt['event_id'],data__active=receipt['active']).exists(),'Replay transition was not recorded.')
    elif kind=='telemetry':
        sample=m.TelemetrySample.objects.get(pk=receipt['id'])
        require(digest(sample.data)==receipt['data_hash'],'Telemetry read-back mismatch.')
        close(sample.data['balance_error_kw'],0,'telemetry balance')
    elif kind=='command':
        command=m.ControlCommand.objects.get(pk=receipt['id'])
        require(command.reviewed_by_id==receipt['reviewed_by'] and command.reason==receipt['reason'] and command.reviewed_at is not None,'Command decision mismatch.')
        if receipt.get('verified'):require(command.status=='verified' and bool(command.result.get('telemetry')),'Command execution is unverified.')
    elif kind=='checkpoint':
        require(receipt['key'] in ['weather','solve','checks','scenario_solve','compare','training','observe_command','answer'],'Unknown checkpoint.')
        if receipt['key']=='checks':
            for check in receipt.get('checks',[]):
                run=m.OptimizationRun.objects.get(pk=check['run_id'])
                require(run.scenario.baseline_id==check['baseline_id'],'Stress-test baseline link changed.')
                verify_run(run,check['snapshot_hash'])
        if receipt['key']=='compare':
            for check in receipt.get('run_receipts',[]):verify_receipt(check)
    elif kind=='report':
        a=m.ReportArtifact.objects.get(pk=receipt['id']);require(digest(a.basis)==receipt['basis_hash'],'Report basis mismatch.')
        if receipt.get('content_hash'):
            import hashlib
            require(hashlib.sha256(bytes(a.content)).hexdigest()==receipt['content_hash'],'Report bytes differ from the verified artifact.')
    else:raise VerificationError('Unknown receipt kind.')
    return {'passed':True,'checks':['Persisted result read back']}
