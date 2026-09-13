"""One frozen, permission-checked evidence dataset for charts and all exports."""
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime,timedelta
from xml.sax.saxutils import escape
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from . import models as m, services as svc, live
from .access import site_for, sites_for, run_for
from .validation import fail


def plain(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@transaction.atomic
def comparison(user, site_ids=None, run_ids=None):
    ids = run_ids or site_ids
    if not isinstance(ids, list) or not 2 <= len(ids) <= 5 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        fail('Choose 2–5 distinct sites or saved plans.')
    runs = [run_for(user, i) for i in run_ids] if run_ids else [svc.latest_plan(site_for(user, i)) for i in site_ids]
    if any(r is None for r in runs): fail('Generate a plan for each selected site first.')
    from .assistant.verify import verify_run
    for r in runs:verify_run(r)
    details = [svc.run_summary(r, True) for r in runs]
    reasons = []
    scenario_pair=len(runs)==2 and any(r.mode=='scenario' and r.scenario.baseline_id==other.pk for r,other in [(runs[0],runs[1]),(runs[1],runs[0])])
    if not scenario_pair and len({(r.mode, r.snapshot['inputs'][0]['timestamp']) for r in runs}) != 1:
        reasons.append('Weather modes or starting times differ. Select plans with a common horizon for hourly comparisons.')
    if any(r.configuration_version != r.site.configuration_version for r in runs):
        reasons.append('Some plans use earlier site settings.')
    if any(r.status not in ['optimal','feasible'] for r in runs): reasons.append('Some plans have no feasible schedule.')
    for r in runs:
        w=r.snapshot['weather']
        if w['source']=='open_meteo' and timezone.now()-__import__('datetime').datetime.fromisoformat(w['retrieved_at'])>timedelta(hours=6):
            reasons.append('A live forecast is older than six hours.');break
    for d in details:
        metrics=d['metrics'];reserve=d['snapshot']['configuration']['battery']['reserve_soc']
        metrics['reserve_margin_pp']=metrics.get('minimum_soc_pct', reserve)-reserve if metrics else None
        metrics['emissions_per_kwh']=metrics.get('emissions_kg_co2',0)/metrics['served_kwh'] if metrics.get('served_kwh',0)>1e-9 else None
    delta = {}
    if not reasons and len(details)==2:
        for k,v in details[0]['metrics'].items():
            other=details[1]['metrics'].get(k)
            if type(v) in (int,float) and type(other) in (int,float):delta[k]=other-v
    return plain({'kind':'comparison','runs':details,'comparable':not reasons,'limitations':reasons,
                  'delta':delta,'delta_label':'Second selection minus first selection','site_ids':list(dict.fromkeys(r.site_id for r in runs))})


def freeze(user, selection):
    kind=selection.get('kind','plan')
    if kind=='comparison':
        data=comparison(user, selection.get('site_ids'),selection.get('run_ids'))
    elif kind=='plan':
        run=run_for(user, selection.get('run_id'))
        from .assistant.verify import verify_run
        verify_run(run)
        for scenario in run.scenarios.select_related('result'):verify_run(scenario.result)
        data={'kind':'plan','site_ids':[run.site_id],'run':svc.run_summary(run,True),
              'scenarios':[svc.run_summary(s.result,True) for s in run.scenarios.select_related('result','result__site')],
              'history_complete':True}
    elif kind=='replay':
        session=get_object_or_404(m.LiveSession.objects.select_related('site'),pk=selection.get('session_id'),site__in=sites_for(user))
        data={'kind':'replay','site_ids':[session.site_id],'site':session.site.name,'timezone':session.site.timezone,
              'baseline_snapshot':session.snapshot,'session':live.status(session.site,session)['session'],
              'history_complete':session.evidence_version>=2}
        data['session']['samples']=list(session.samples.order_by('timestamp','pk').values_list('data',flat=True))
        data['session']['commands']=list(session.commands.order_by('pk').values('id','run_id','status','proposal','result','reason','created_at','reviewed_at','reviewed_by_id','expires_at'))
        data['session']['events']=list(session.event_records.values('id','timestamp','kind','message','data'))
        if session.evidence_version<2:data['legacy_recent_events']=session.events
        samples=data['session']['samples']
        data['verification']=verify_replay(session,samples)
        data['coverage']={'intervals':len(samples),'recorded_seconds':sum(r.get('interval_seconds',0) for r in samples),
            'elapsed_seconds':session.state.get('elapsed_seconds',0),'start':session.snapshot['inputs'][0]['timestamp'],
            'end':session.simulated_at.isoformat(),'note':'Older event or interval history may be missing.' if session.evidence_version<2 else 'Every simulation interval and event is retained.'}
    else:fail('Choose plan, comparison or replay evidence.')
    data.update(schema_version=1,units={'power':'kW','energy':'kWh','fuel':'L','cost':'INR','battery_soc':'percent','emissions':'kg CO2','timestamps':'ISO 8601 with UTC offset'},exported_at=timezone.now().isoformat(),basis='Projected planning and software simulation; no physical telemetry.')
    return plain(data)


def verify_replay(session,samples):
    from .assistant.verify import require,close
    if session.evidence_version<3:
        return {'passed':None,'checks':[], 'limitation':'Legacy totals are retained as recorded. Complete independent interval verification was not available in that version.'}
    prior=datetime.fromisoformat(session.snapshot['inputs'][0]['timestamp']);seconds=0
    for row in samples:
        start=datetime.fromisoformat(row['interval_start']);end=datetime.fromisoformat(row['timestamp'])
        require(start==prior and end>start,'Replay interval history has a gap or overlap.')
        close((end-start).total_seconds(),row['interval_seconds'],'replay interval duration')
        close(row['solar_kw']+row['wind_kw']+row['generator_kw']+row['battery_discharge_kw'],row['served_kw']+row['battery_charge_kw']+row['curtailed_kw'],'replay power balance')
        require(0<=row['served_kw']<=row['demand_kw']+.001,'Replay supply exceeds requested demand.')
        seconds+=row['interval_seconds'];prior=end
    close(seconds,session.state['elapsed_seconds'],'complete replay duration')
    require(prior==session.simulated_at,'Replay end timestamp mismatch.')
    total=lambda k:sum(row[k] for row in samples)
    energy=lambda k:sum(row[k]*row['interval_seconds']/3600 for row in samples)
    for name,value in [('critical_requested_kwh',energy('critical_requested_kw')),('critical_unserved_kwh',energy('critical_unserved_kw')),('served_kwh',energy('served_kw')),('fuel_used_l',total('diesel_litres')),('cost_inr',total('dispatch_cost_inr'))]:
        close(session.state[name],value,'replay '+name)
    minimum=min([session.snapshot['state']['soc_pct']]+[r['soc_pct'] for r in samples]+[e.data['after']['soc_pct'] for e in session.event_records.filter(kind='low_battery')])
    close(session.state['minimum_soc_pct'],minimum,'minimum replay SOC including test events')
    return {'passed':True,'checks':['Complete consecutive interval coverage','Power balance','Requested and supplied energy','Critical shortage','Fuel and cost totals']}


@transaction.atomic
def create_report(user, selection, format='pdf'):
    if format not in ['pdf','json','csv']:fail('Choose PDF, CSV or JSON.')
    if selection.get('source_artifact_id'):
        original=get_object_or_404(m.ReportArtifact,pk=selection['source_artifact_id'],owner=user)
        if not allowed(user,original):fail('Access to this evidence has changed.')
        from copy import deepcopy
        data=deepcopy(original.basis)
    else:data=freeze(user,selection)
    return m.ReportArtifact.objects.create(owner=user,site_ids=data['site_ids'],format=format,basis=data,
        name=f"jeevangrid-{data['kind']}.{ 'zip' if format=='csv' else format}",content=b'',sha256='')


def allowed(user, artifact):
    return set(artifact.site_ids).issubset(set(sites_for(user).values_list('id',flat=True)))


def csv_bytes(rows):
    buf=io.StringIO();fields=list(dict.fromkeys(k for row in rows for k in row))
    writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
    for row in rows:
        clean={k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()}
        # Spreadsheet applications must not execute user-provided cells.
        clean={k:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for k,v in clean.items()}
        writer.writerow(clean)
    return buf.getvalue().encode('utf-8-sig')


def render(data, format):
    if format=='json':return json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False).encode()
    runs=data.get('runs') or ([data['run']]+data.get('scenarios',[]) if 'run' in data else [])
    if format=='csv':
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('evidence.json',render(data,'json'))
            for r in runs:
                z.writestr(f"plan-{r['id']}-dispatch.csv",csv_bytes(r['intervals']))
                z.writestr(f"plan-{r['id']}-metrics.csv",csv_bytes([r['metrics']]))
                z.writestr(f"plan-{r['id']}-weather.csv",csv_bytes(r['snapshot']['weather']['intervals']))
            if 'session' in data:
                for key in ['samples','commands','events']:z.writestr(key+'.csv',csv_bytes(data['session'][key]))
        return buf.getvalue()
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing,Line,String,PolyLine
    styles=getSampleStyleSheet();buf=io.BytesIO();story=[]
    def text(s,style='BodyText'):story.append(Paragraph(escape(str(s)),styles[style]));story.append(Spacer(1,8))
    def table(rows):
        rows=[[Paragraph(escape(str(v)),styles['BodyText']) for v in r] for r in rows]
        t=Table(rows,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4f1ec')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#087f68'))]));story.append(t);story.append(Spacer(1,12))
    def chart(rows,keys,title,unit):
        if not rows:return
        d=Drawing(460,170)
        maximum=max([float(r.get(k,0) or 0) for r in rows for k,_,_ in keys]+[1]);left,bottom,w,h=38,30,410,110
        for tick in range(5):
            y=bottom+h*tick/4;d.add(Line(left,y,left+w,y,strokeColor=colors.HexColor('#dae4e5')));d.add(String(0,y,str(round(maximum*tick/4,1)),fontSize=8))
        is_state=unit=='%'
        moments=[]
        for row in rows:
            moment=datetime.fromisoformat(row['timestamp'] if is_state else row.get('interval_start',row['timestamp']))
            if is_state and 'interval_seconds' not in row:moment+=timedelta(hours=1)
            moments.append(moment.timestamp())
        end=datetime.fromisoformat(rows[-1]['timestamp'])
        if 'interval_seconds' not in rows[-1]:end+=timedelta(hours=1)
        low=moments[0];high=max(moments[-1],end.timestamp())
        for k,label,color in keys:
            pts=[]
            for i,r in enumerate(rows):
                x=left+w*(moments[i]-low)/max(1,high-low);y=bottom+h*float(r.get(k,0) or 0)/maximum
                if pts and not is_state:pts.extend([x,pts[-1]])
                pts.extend([x,y])
            if not is_state:pts.extend([left+w,pts[-1]])
            if len(pts)>=4:d.add(PolyLine(pts,strokeColor=colors.HexColor(color),strokeWidth=1.5))
        for i in sorted(set([0,len(rows)//2,len(rows)-1])):
            d.add(String(left+w*(moments[i]-low)/max(1,high-low)-10,12,datetime.fromtimestamp(moments[i],tz=__import__('datetime').timezone.utc).strftime('%d %b %H:%M'),fontSize=7))
        story.append(KeepTogether([Paragraph(escape(title+' ('+unit+')'),styles['Heading3']),Spacer(1,8),d,Paragraph(escape('Times shown in UTC. '+ ' · '.join(label for _,label,_ in keys)),styles['BodyText']),Spacer(1,12)]))
    text('JeevanGrid / '+data['kind'].title()+' report','Title');text(data['basis']);text('Exported '+data['exported_at'])
    if data.get('history_complete') is False:text('Incomplete legacy evidence: previously discarded events and intervals cannot be reconstructed.')
    for r in runs:
        text(f"{r['site_name']} / Plan #{r['id']} / {r['status']}",'Heading2')
        text(f"Weather: {r['weather_source']} · Horizon: {r['horizon_start']} · Settings version: {r['configuration_version']}")
        measures=[('critical_load_served_pct','Critical service','%'),('critical_unserved_kwh','Critical shortage','kWh'),('normal_unserved_kwh','Normal shortage','kWh'),('flexible_unserved_kwh','Unfinished flexible work','kWh'),('served_kwh','Energy supplied','kWh'),('dispatch_cost_inr','Dispatch cost','INR'),('fuel_cost_inr','Fuel cost','INR'),('generator_start_cost_inr','Generator starts cost','INR'),('battery_wear_cost_inr','Estimated battery wear','INR'),('diesel_litres','Diesel fuel','L'),('cost_per_kwh','Cost / supplied energy','INR/kWh'),('diesel_l_per_kwh','Diesel / supplied energy','L/kWh'),('renewable_share_pct','Renewable generation','%'),('emissions_kg_co2','Combustion emissions','kg CO2'),('minimum_soc_pct','Minimum battery SOC','%'),('reserve_compliance_pct','Reserve compliance','%'),('renewable_curtailed_kwh','Curtailed renewables','kWh')]
        table([['Measure','Value','Unit']]+[[label,round(r['metrics'][k],4) if type(r['metrics'].get(k)) in (int,float) else 'Unavailable',unit] for k,label,unit in measures])
        chart(r['intervals'],[('served_load','Demand supplied','#087f68'),('diesel_power','Diesel','#d4805c')],'Hourly dispatch','kW')
        chart(r['intervals'],[('battery_soc','Battery SOC','#087f68')],'Battery reserve','%')
        c=r['snapshot']['configuration'];text(f"Equipment: solar {c['solar']['capacity_kw']} kW; wind {c['wind']['capacity_kw']} kW; battery {c['battery']['capacity_kwh']} kWh; diesel {c['generator']['capacity_kw']} kW. Operating reserve {c['battery']['reserve_soc']}%.")
        for diagnostic in r['diagnostics']:text(diagnostic)
        if r.get('overrides'):text('Scenario changes: '+json.dumps(r['overrides']))
        for decision in r.get('decisions',[]):text('Review: '+json.dumps(decision))
    if 'session' in data:
        s=data['session'];text(f"{data['site']} / Replay #{s['id']} / Baseline #{s['baseline_id']}",'Heading2')
        text(f"Recorded intervals: {data['coverage']['intervals']} · Covered duration: {round(data['coverage']['recorded_seconds']/3600,2)} hours · Start: {data['coverage']['start']} · End: {data['coverage']['end']}")
        text(data['coverage']['note'])
        table([['Observed in simulation','Value']]+[[k.replace('_',' '),round(v,4) if type(v) in (int,float) else v] for k,v in s['evidence'].items()])
        chart(s['samples'],[('demand_kw','Demand','#233b44'),('served_kw','Supplied','#087f68')],'Requested and supplied','kW')
        chart(s['samples'],[('soc_pct','Battery SOC','#087f68')],'Stored energy','%')
        text('Verified commands establish simulated generator output and power balance only. Battery balancing is automatic; no physical equipment was controlled.')
        text('Events and reviews','Heading2')
        for e in s['events']:
            if e['kind']!='notice':text(str(e['timestamp'])+' · '+e['message'])
        table([['Command','Status','Reason']]+[[c['id'],c['status'],c['reason']] for c in s['commands']])
    for reason in data.get('limitations',[]):text(reason)
    def page_footer(canvas,doc):
        canvas.saveState();canvas.setFillColor(colors.HexColor('#53756a'));canvas.setFont('Helvetica',8)
        canvas.drawString(40,25,'JeevanGrid / frozen planning and simulation evidence');canvas.drawRightString(doc.pagesize[0]-40,25,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(buf,title='JeevanGrid evidence report',author='JeevanGrid',rightMargin=40,leftMargin=40).build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return buf.getvalue()


def process_report():
    artifact=m.ReportArtifact.objects.filter(sha256='').select_related('owner').order_by('pk').first()
    if not artifact:return False
    if not allowed(artifact.owner,artifact):
        artifact.sha256='denied';artifact.save(update_fields=['sha256']);return True
    try:content=render(artifact.basis,artifact.format)
    except Exception:
        import logging
        logging.exception('Report rendering failed for artifact %s',artifact.pk)
        artifact.sha256='failed';artifact.save(update_fields=['sha256']);return True
    if artifact.format=='pdf' and not content.startswith(b'%PDF-'):raise ValueError('Invalid PDF output')
    artifact.content=content;artifact.sha256=hashlib.sha256(content).hexdigest();artifact.save(update_fields=['content','sha256'])
    return True
