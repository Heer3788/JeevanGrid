import React,{useEffect,useState} from 'react';
import {Link,useParams} from 'react-router-dom';
import {ArrowLeft} from 'lucide-react';
import {api} from './api';
import {ErrorNotice,number as n,timestamp} from './ui';
import ExportMenu from './Reports';
import PlanCharts from './PlanCharts';
import {useAnalysis} from './Intelligence';
import {PlanImpact} from './PlanTesting';

export default function SavedRun() {
  const {id}=useParams(),[run,setRun]=useState(null),[error,setError]=useState('');
  useEffect(()=>{let active=true;setRun(null);api(`/optimization-runs/${id}`).then(r=>{if(active)setRun(r)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[id]);
  const {data:analysis,error:analysisError}=useAnalysis(run?.id);
  if(!run)return <><ErrorNotice error={error}/><div className="loading">Loading saved plan…</div></>;

  return <><Link className="back" to={`/sites/${run.site_id}`}><ArrowLeft size={15}/>Back to site</Link><header className="page-head"><div><div className="eyebrow">SAVED {run.mode==='scenario'?'EXPERIMENT':'PLAN'}</div><h1>#{run.id} · {run.site_name}</h1><p>{run.scenario_name||run.mode} · {timestamp(run.created_at)} · {run.status}</p></div><div className="actions"><Link className="secondary" to={`/data?site=${run.site_id}&run=${run.id}`}>Inspect dataset</Link><ExportMenu label="Export run" selection={{kind:"plan",run_id:run.id}}/></div></header>{run.baseline_id&&<p><Link to={`/runs/${run.baseline_id}`}>Original plan #{run.baseline_id}</Link></p>}<section className="panel"><h2>{run.next_action.reason}</h2><p>{n(run.metrics.critical_load_served_pct)}% critical served · {n(run.metrics.diesel_litres)} L diesel · INR {n(run.metrics.dispatch_cost_inr)}</p>{run.diagnostics.map((d,i)=><p className="notice amber" key={i}>{d}</p>)}</section><PlanCharts run={run} tz={run.snapshot.site.timezone}/><details className="panel"><summary>Compare with reactive operation</summary><PlanImpact run={run} analysis={analysis} error={analysisError}/></details><details className="panel"><summary>Review trail</summary>{run.decisions.length?run.decisions.map((d,i)=><p key={i}>{d.decision} · {d.reason||'Reviewed'} · {d.user__email} · {timestamp(d.created_at)}</p>):<p>No operator review recorded.</p>}</details></>;
}
