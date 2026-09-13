"""Durable fixed-step executor. A single OS-locked worker processes one step per tick."""
import hashlib
from copy import deepcopy
from datetime import timedelta
import requests
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError
from .. import models as m, services as svc, operations as ops, live, forecasting, reports
from ..optimizer import solve
from ..weather import WeatherUnavailable
from ..access import sites_for, site_for, run_for, admin
from ..validation import fail, PRESETS
from .catalog import CATALOG, enabled
from .inputs import validate, scope, Clarification
from .verify import verify_run, verify_receipt, require, close, VerificationError
from . import provider

TERMINAL={'succeeded','failed','cancelled','unavailable'}
class Waiting(Exception):pass

LABELS={'site':'Site saved','reading':'Readings saved','weather':'Weather retrieved','solve':'Optimization calculated','plan':'Plan saved','checks':'Checks completed','scenario_solve':'Scenario calculated','scenario':'Test saved','compare':'Comparison verified','replay':'Replay started','event':'Event recorded','observe':'Telemetry observed','pause':'Replay paused','review':'Review recorded','command':'Command decision recorded','observe_command':'Command telemetry verified','import':'Demand imported','training':'Training evaluated','model':'Model saved','report':'Evidence frozen','report_ready':'Report ready','answer':'Answer prepared'}


def context_for(job):
    user=scope(job);query=sites_for(user)
    if job.conversation.site_id:query=query.filter(pk=job.conversation.site_id)
    previous=job.conversation.workflows.filter(status='succeeded').exclude(pk=job.pk).order_by('-pk').first()
    return {'previous_result':{'workflow':previous.workflow,'site_ids':previous.context.get('site_ids',[]),'run_id':previous.context.get('run_id')} if previous else None,'site_scope':job.conversation.site_id,'sites':list(query.order_by('id').values('id','name','archived'))[:500],
            'attachments':list(job.conversation.attachments.values('id','name')) if hasattr(job.conversation,'attachments') else list(m.ChatAttachment.objects.filter(conversation=job.conversation).values('id','name'))}


def check_versions(job):
    user=scope(job)
    require(job.workflow in CATALOG and job.version==CATALOG[job.workflow].version,'Unsupported workflow version.')
    if job.workflow in CATALOG and CATALOG[job.workflow].admin:admin(user)
    for pk,version in job.context.get('versions',{}).items():
        if site_for(user,int(pk)).configuration_version!=version:fail('Site settings or readings changed while this workflow was running. Completed steps remain saved; start a new request with current inputs.')
    return user


def file_for(job):
    a=m.ChatAttachment.objects.get(pk=job.inputs['attachment_id'],conversation=job.conversation)
    require(hashlib.sha256(bytes(a.content)).hexdigest()==a.sha256,'Attachment integrity failed.')
    return SimpleUploadedFile(a.name,bytes(a.content),content_type='text/csv')


def prepare(job,key):
    user=check_versions(job);p=job.inputs;c=job.context;site=site_for(user,p['site_id']) if p.get('site_id') else None
    if key=='weather':return svc.prepare_snapshot(site,p['mode'],p.get('date'),persist_weather=False)
    if key=='solve':return solve(c['snapshot'])
    if key=='scenario_solve':
        baseline=run_for(user,p['run_id'])
        require(baseline.mode!='scenario' and baseline.status in ['optimal','feasible'],'A scenario needs a feasible original baseline.')
        verify_run(baseline);snapshot=deepcopy(baseline.snapshot);snapshot['overrides']=p['overrides']
        return {'snapshot':snapshot,'baseline_hash':reports.digest(baseline.snapshot),'result':solve(snapshot,p['overrides'])}
    if key=='training':
        rows=forecasting.parse_csv(file_for(job),site) if p['training_source']=='csv' else forecasting.demo_dataset(site,svc.configuration(site))
        return forecasting.train(site,svc.configuration(site),rows,p['training_source'],persist=False)
    if key=='answer':
        general=p.get('question_kind')=='general';facts=[]
        if not general:
            # Three fixed retrievals at most: site summaries, current plans, requested run evidence.
            query=sites_for(user)
            ids=c.get('site_ids',[])
            if ids:query=query.filter(pk__in=ids)
            selected=list(query.order_by('id')[:12])
            facts=[{'site':svc.site_summary(s),'reliability':svc.reliability(s)} for s in selected]
            if p.get('run_id'):facts.append({'requested_plan':svc.run_summary(run_for(user,p['run_id']),True)})
        if not general:
            from .help import DOCUMENTATION
            facts.append({'documentation':DOCUMENTATION})
        answer=provider.explain(p.get('question',job.message.text),facts,general)
        return {'kind':'answer','text':answer,'evidence':reports.plain(facts),'interpretation':True,'general':general,'retrieval_rounds':0 if general else 3}
    return None


def run_receipt(run):return {'kind':'run','id':run.pk,'snapshot_hash':reports.digest(run.snapshot)}

def execute(job,key,prepared):
    user=check_versions(job);p=job.inputs;c=job.context;site=site_for(user,p['site_id']) if p.get('site_id') else None
    receipt={'kind':'checkpoint','key':key};result={}
    if key=='site':
        creating=job.workflow in ['site.create','create_and_plan'];data=deepcopy(p.get('site_data',{}))
        if p.get('configuration'):data['configuration']=p['configuration']
        if job.workflow in ['site.archive','site.restore']:data={'archived':job.workflow=='site.archive'}
        site=ops.save_site(user,data,None if creating else site.pk);p['site_id']=site.pk
        c['site_ids']=[site.pk];c['versions']={str(site.pk):site.configuration_version}
        expected=deepcopy(data)
        receipt={'kind':'site','id':site.pk,'organization_id':site.organization_id,'version':site.configuration_version,'expected':expected}
        result={'kind':'site','site':svc.site_summary(site),'before':c.get('before',{}),'after':expected,'template_used':p.get('accept_template',False)}
    elif key=='reading':
        before=svc.current_state(site,svc.configuration(site));r=ops.record_reading(user,site.pk,p['readings']);site.refresh_from_db();c['versions'][str(site.pk)]=site.configuration_version
        receipt={'kind':'reading','id':r.pk,'expected':r.data};result={'kind':'reading','site_id':site.pk,'before':before,'after':r.data,'version':site.configuration_version}
    elif key=='import':
        import csv,io
        from datetime import datetime
        accepted=[{'timestamp':datetime.fromisoformat(r['timestamp']),'critical_kw':float(r['critical_kw']),'normal_kw':float(r['normal_kw']),'flexible_kw':float(r['flexible_kw'])} for r in csv.DictReader(io.StringIO(file_for(job).read().decode('utf-8-sig')))]
        info=ops.import_load(user,site.pk,file_for(job));site.refresh_from_db();c['versions'][str(site.pk)]=site.configuration_version
        rows=list(site.load_profile.intervals.values('timestamp','critical_kw','normal_kw','flexible_kw'))
        require(len(rows)==len(accepted) and all(a['timestamp']==b['timestamp'] and all(a[k]==b[k] for k in ['critical_kw','normal_kw','flexible_kw']) for a,b in zip(rows,accepted)),'Imported intervals differ from the CSV.')
        receipt={'kind':'import','site_id':site.pk,'version':site.configuration_version,'rows_hash':reports.digest(rows)}
        result={'kind':'import','site_id':site.pk,'intervals':24,**info}
    elif key=='weather':
        expected={'simulated':'simulated','forecast':'open_meteo','historical':'nasa_power'}[p['mode']]
        require(prepared['weather']['source']==expected and len(prepared['inputs'])==24,'Weather source or horizon mismatch.')
        c['snapshot']=prepared;receipt.update(source=expected,snapshot_hash=reports.digest(prepared),cached=prepared['weather']['cached'])
        if expected!='simulated' and not prepared['weather']['cached']:
            m.WeatherInterval.objects.bulk_create([m.WeatherInterval(site=site,timestamp=r['timestamp'],retrieved_at=prepared['weather']['retrieved_at'],source=expected,data=r) for r in prepared['weather']['intervals']])
    elif key=='solve':c['solved']=prepared;receipt.update(outcome=prepared['status'])
    elif key=='plan':
        run=svc.persist_run(site,user,p['mode'],c['snapshot'],c['solved']);receipt=run_receipt(run);c['run_id']=run.pk
        result={'kind':'plan','run':svc.run_summary(run,True),'outcome':run.status}
    elif key=='checks':
        from ..assessment import preset_results
        run=run_for(user,c['run_id']);verify_run(run,c['snapshot'] and reports.digest(c['snapshot']))
        if run.status not in ['optimal','feasible']:receipt.update(outcome='not_applicable',reason='No feasible baseline to stress-test.')
        else:
            assessment=m.PlanAssessment.objects.get(run=run)
            if assessment.status=='failed':raise VerificationError('Stress checks failed: '+assessment.error)
            scenarios=preset_results(run)
            if len(scenarios)!=6:raise Waiting('Waiting for the six persisted stress tests.')
            checks=[]
            for name,scenario in scenarios.items():
                require(scenario.overrides==PRESETS[name] and scenario.baseline_id==run.pk,'Stress scenario link mismatch.')
                expected=deepcopy(run.snapshot);expected['overrides']=PRESETS[name]
                verify_run(scenario.result,reports.digest(expected));checks.append({'name':name,'run_id':scenario.result_id,'baseline_id':run.pk,'snapshot_hash':reports.digest(expected),'outcome':scenario.result.status,'metrics':scenario.result.metrics})
            receipt.update(checks=checks);result={'assessment':svc.reliability(site),'checks':checks}
    elif key=='scenario_solve':c.update(prepared);receipt.update(baseline_id=p['run_id'],baseline_hash=prepared['baseline_hash'])
    elif key=='scenario':
        baseline=run_for(user,p['run_id']);require(reports.digest(baseline.snapshot)==c['baseline_hash'],'Baseline inputs changed.')
        run=svc.persist_run(site,user,'scenario',c['snapshot'],c['result']);scenario=m.ScenarioRun.objects.create(baseline=baseline,result=run,name='Chat condition test',overrides=p['overrides'])
        require(scenario.overrides==p['overrides'],'Scenario overrides mismatch.')
        c['run_id']=run.pk;receipt=run_receipt(run);receipt.update(baseline_id=baseline.pk,baseline_hash=c['baseline_hash'],overrides=p['overrides'])
        result={'kind':'plan','run':svc.run_summary(run,True),'outcome':run.status}
    elif key=='compare':
        ids=[p['run_id'],c['run_id']] if job.workflow=='test_and_compare' else p.get('run_ids')
        data=reports.comparison(user,p.get('site_ids'),ids)
        c['comparison']=data;result=data;receipt.update(evidence_hash=reports.digest(data),run_receipts=[run_receipt(run_for(user,r['id'])) for r in data['runs']])
    elif key=='replay':
        baseline=run_for(user,p['run_id']);verify_run(baseline)
        s=live.start(site,user,{'speed':p.get('speed',30),'use_ml':False,'conservative':False},baseline,replan_now=False)
        c['session_id']=s.pk;receipt={'kind':'session','id':s.pk,'active':True,'snapshot_hash':reports.digest(s.snapshot),'event_id':s.event_records.order_by('-pk').first().pk};result={'kind':'replay','session_id':s.pk,'site_id':site.pk,'state':'started'}
    elif key=='event':
        s=m.LiveSession.objects.get(pk=p['session_id'],site=site)
        require(s.active,'Replay is no longer active.');e=live.inject(s,p['event']);c['session_id']=s.pk;c['event_revision']=e.data['revision']
        receipt={'kind':'event','id':e.pk,'session_id':s.pk,'data_hash':reports.digest(e.data)};result={'kind':'replay','session_id':s.pk,'site_id':site.pk,'event':p['event']}
    elif key=='observe':
        s=m.LiveSession.objects.get(pk=c['session_id'],site=site);sample=s.samples.first();revision=c.get('event_revision',0)
        if not sample or not s.heartbeat or (timezone.now()-s.heartbeat).total_seconds()>15 or sample.data.get('event_revision',0)<revision:raise Waiting('Waiting for fresh replay telemetry.')
        if not s.latest_run_id or s.latest_run.snapshot.get('event_revision',0)<revision:raise Waiting('Waiting for the worker to replan with this event.')
        close(sample.data['balance_error_kw'],0,'replay energy balance')
        receipt={'kind':'telemetry','id':sample.pk,'data_hash':reports.digest(sample.data)}
        result={'kind':'replay','session_id':s.pk,'site_id':site.pk,'telemetry':sample.data,'modifiers':live.status(site,s)['session']['modifiers'],'verification_scope':('The event was followed by a newer event before observation. ' if sample.data.get('event_revision',0)>revision else '')+'Event revision observed; power balance checked in software telemetry. No physical equipment controlled.'}
    elif key=='pause':
        s=m.LiveSession.objects.get(pk=p['session_id'],site=site)
        require(s.active,'This replay is already paused.');current=ops.pause_replay(user,site.pk);require(current.pk==s.pk,'Replay identity changed.')
        receipt={'kind':'session','id':s.pk,'active':False,'snapshot_hash':reports.digest(s.snapshot),'event_id':s.event_records.order_by('-pk').first().pk};result={'kind':'replay','session_id':s.pk,'site_id':site.pk,'state':'paused'}
    elif key=='review':
        data=ops.review_plan(user,p['run_id'],{'decision':p['decision'],'reason':p.get('reason','')})
        receipt={'kind':'decision','run_id':p['run_id'],**data};result={'kind':'review',**data,'run_id':p['run_id']}
    elif key=='command':
        command=m.ControlCommand.objects.get(pk=p['command_id'],session__site=site);live.review(command.session,command,user,p['decision'],p.get('reason',''))
        receipt={'kind':'command','id':command.pk,'decision':p['decision'],'reviewed_by':user.pk,'reason':p.get('reason','')}
        result={'kind':'command','command_id':command.pk,'decision':p['decision'],'state':command.status}
    elif key=='observe_command':
        command=m.ControlCommand.objects.get(pk=p['command_id'],session__site=site)
        if p['decision']=='reject':receipt.update(outcome='rejected',execution='Not requested')
        else:
            if command.status in ['failed','superseded','expired','rejected']:raise VerificationError('Command '+command.status+'. Approval was saved, but execution was not verified.')
            if command.status!='verified':raise Waiting('Approval recorded; waiting for simulated generator telemetry.')
            t=command.result.get('telemetry',{});require(t,'Command has no verification telemetry.')
            close(t['generator_kw'],command.proposal['generator_kw'],'generator setpoint',.05);close(t['balance_error_kw'],0,'command energy balance')
            require(t['generator_on']==command.proposal['generator_on'],'Generator state mismatch.')
            require(command.session.samples.filter(data=t).exists(),'Command telemetry was not persisted.')
            receipt={'kind':'command','id':command.pk,'decision':'approve','reviewed_by':user.pk,'reason':p.get('reason',''),'verified':True}
            result={'kind':'command','command_id':command.pk,'state':'verified','telemetry':t,'verification_scope':'Simulated generator output and power balance only. Battery balancing is automatic; it is not a verified battery setpoint.'}
    elif key=='training':c['training']=prepared;receipt.update(dataset_hash=reports.digest(prepared['artifacts']['dataset']),provenance=prepared['provenance'])
    elif key=='model':
        t=c['training'];model=m.ForecastModel.objects.create(site=site,configuration_version=site.configuration_version,**t)
        receipt={'kind':'model','id':model.pk,'report_hash':reports.digest(model.report),'dataset_hash':reports.digest(model.artifacts['dataset'])}
        result={'kind':'model','model_id':model.pk,'site_id':site.pk,'report':model.report,'usage':'Saved and evaluated. Standard operating plans and saved-plan replay use physics/load inputs; this model is not automatically enabled there.'}
    elif key=='report':
        selection={'kind':'comparison', 'run_ids':[r['id'] for r in c['comparison']['runs']]} if c.get('comparison') else {'kind':'plan','run_id':c['run_id']} if c.get('run_id') else p
        a=reports.create_report(user,selection,p['format']);c['artifact_id']=a.pk;receipt={'kind':'report','id':a.pk,'basis_hash':reports.digest(a.basis)}
        result={'artifact_id':a.pk,'format':a.format}
    elif key=='report_ready':
        a=m.ReportArtifact.objects.get(pk=c['artifact_id']);require(reports.allowed(user,a),'Report access has been revoked.')
        if not a.sha256:raise Waiting('Rendering the frozen evidence report.')
        require(len(a.sha256)==64 and hashlib.sha256(bytes(a.content)).hexdigest()==a.sha256,'Report failed integrity verification.')
        if a.format=='pdf':require(bytes(a.content).startswith(b'%PDF-'),'Invalid PDF output.')
        receipt={'kind':'report','id':a.pk,'basis_hash':reports.digest(a.basis),'content_hash':a.sha256};result={'artifact_id':a.pk,'format':a.format,'download':f'/api/reports/{a.pk}/download'}
    elif key=='answer':result=prepared;receipt.update(retrieval_rounds=prepared['retrieval_rounds'])
    else:raise VerificationError('Unregistered workflow step.')
    return reports.plain(receipt),reports.plain(result)


def save_job(job, update_fields=None):
    with transaction.atomic():
        current=m.WorkflowRun.objects.select_for_update().get(pk=job.pk)
        if current.status=='cancelled':return False
        job.context=reports.plain(job.context);job.result=reports.plain(job.result);job.inputs=reports.plain(job.inputs)
        job.save(update_fields=update_fields)
        return True


def tick(job):
    if job.status in TERMINAL or job.status=='clarification':return
    try:
        scope(job)
        if not job.workflow:
            # Publish that the worker has claimed the request before the network call.
            job.status='running';job.error=''
            if not save_job(job,update_fields=['status','error','updated_at']):return
            messages=list(job.conversation.messages.filter(pk__in=[job.message_id]+job.context.get('clarification_ids',[])).order_by('pk'))
            text='\n'.join(m.text for m in messages)
            intent=provider.interpret(text,context_for(job))
            job.workflow=intent['workflow'];job.inputs=intent['inputs'];job.inputs['question']=job.message.text;job.inputs['question_kind']=intent['question_kind']
            job.context['interpretation']={'workflow':job.workflow,'arguments':intent['arguments']}
            if job.workflow in ['clarify','unsupported']:
                job.workflow='';job.status='clarification';job.question=intent['question'] or 'Choose one of the available workflows and supply its site and inputs.';save_job(job);return
            if not save_job(job):return
        if not job.context.get('validated'):
            p,context=validate(job);job.inputs=p;job.context.update(context,validated=True)
            if p.get('site_id'):
                selected_site=site_for(job.conversation.owner,p['site_id'])
                job.context['before']={**svc.site_summary(selected_site),'configuration':svc.configuration(selected_site)}
            job.status='running';job.question='';save_job(job)
            return
        if not enabled(job.workflow):fail('Workflow was disabled before execution.')
        check_versions(job)
        completed=list(job.steps.all())
        for step in completed:verify_receipt(step.receipt)
        if completed and completed[-1].receipt.get('result_hash'):require(reports.digest(job.result)==completed[-1].receipt['result_hash'],'Workflow result differs from verified evidence.')
        key=next((key for key in CATALOG[job.workflow].steps if key not in {s.key for s in completed}),None)
        if key is None:
            job.status='succeeded';job.error='';save_job(job,update_fields=['status','error','updated_at']);return
        prepared=prepare(job,key)
        with transaction.atomic():
            current=m.WorkflowRun.objects.select_for_update().get(pk=job.pk)
            if current.status=='cancelled':return
            # Reconcile after network/solver work before any mutation.
            if current.steps.filter(key=key).exists():return
            check_versions(job)
            receipt,result=execute(job,key,prepared);verification=verify_receipt(receipt)
            job.result.update(result);receipt['result_hash']=reports.digest(job.result)
            m.WorkflowStep.objects.create(run=job,key=key,label=LABELS[key],inputs=job.inputs,receipt=receipt,verification=verification)
            job.status='running';job.attempts=0;job.error='';job.next_attempt_at=None;save_job(job)
    except Clarification as e:
        job.status='clarification';job.question=str(e);save_job(job,update_fields=['status','question','context','updated_at'])
    except Waiting as e:
        # Bound external-worker waits without losing completed mutations.
        waits=job.context.get('waits',0)+1;job.context['waits']=waits
        job.status='failed' if waits>300 else 'waiting';job.error=str(e) if waits<=300 else 'The worker did not verify this operation within ten minutes. Completed changes remain saved.'
        job.next_attempt_at=timezone.now()+timedelta(seconds=2);save_job(job,update_fields=['context','status','error','next_attempt_at','updated_at'])
    except (provider.ProviderUnavailable,requests.RequestException,WeatherUnavailable) as e:
        delay=getattr(e,'retry_after',5);job.attempts+=1
        job.status='retrying' if delay and job.attempts<=(CATALOG[job.workflow].transient_retries if job.workflow in CATALOG else 2) else 'unavailable';job.error=str(e);job.next_attempt_at=timezone.now()+timedelta(seconds=delay or 2)
        save_job(job,update_fields=['attempts','status','error','next_attempt_at','updated_at'])
    except Exception as e:
        # Validation and verification errors are never retried or rewritten as success.
        job.status='failed';job.error=(' '.join(str(v) for v in e.detail.values()) if isinstance(e,ValidationError) and isinstance(e.detail,dict) else str(e))[:1500];save_job(job,update_fields=['status','error','updated_at'])


def process_next():
    job=m.WorkflowRun.objects.filter(status__in=['queued','running','waiting','retrying']).filter(Q(next_attempt_at__isnull=True)|Q(next_attempt_at__lte=timezone.now())).select_related('conversation__owner','message').order_by('updated_at','pk').first()
    if not job:return False
    tick(job);return True
