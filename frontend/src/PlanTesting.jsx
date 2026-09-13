import React,{useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowRight} from 'lucide-react';
import {api} from './api';
import {number as n,ErrorNotice,Input} from './ui';
import {ComparisonChart} from './PlanCharts';
import LiveControl from './LiveControl';

export {default as AutomaticChecks} from './StressExplorer';
import AutomaticChecks from './StressExplorer';
import {feasible,stressFinding} from './stressInsights';

export function ScenarioResult({baseline,result}) {
  const finding=stressFinding(result,baseline);
  return <section className="panel scenario-result"><div className="section-heading"><div><div className="eyebrow">ORIGINAL PLAN → CHANGED CONDITIONS</div><h2>{result.scenario_name?.replaceAll('_',' ')||'Scenario result'}</h2></div><Link className="secondary" to={`/runs/${result.id}`}>Saved result <ArrowRight size={15}/></Link></div>
    <p className={"notice "+(finding.tone==='amber'||finding.tone==='red'?'amber':'')}>{finding.label}. {finding.detail}</p><div className="comparison-metrics">{[['diesel_litres','Diesel','L'],['dispatch_cost_inr','Cost','INR'],['critical_load_served_pct','Critical served','%'],['minimum_soc_pct','Minimum battery','%']].map(([k,l,u])=><div key={k}><span>{l}</span><strong>{n(baseline.metrics[k])} <ArrowRight size={14}/> {feasible(result)?n(result.metrics[k]):'—'}<small>{u}</small></strong><small>{feasible(result)?`${n(result.metrics[k]-baseline.metrics[k])} ${u==='%'?'percentage points':u} change`:'No feasible schedule'}</small></div>)}</div>
    {result.diagnostics?.map((d,i)=><p className="notice amber" key={i}>{d}</p>)}
    {result.intervals?.length?<><h3>Hourly response</h3><ComparisonChart baseline={baseline} changed={result} tz={baseline.snapshot.site.timezone}/></>:<p className="notice amber">No feasible dispatch under these conditions. The constraints cannot all be met.</p>}
    {feasible(result)&&Math.abs((result.metrics.diesel_litres||0)-(baseline.metrics.diesel_litres||0))<.01&&<p className="chart-caption">Diesel use is unchanged in this test. Check demand served and battery reserve to see whether the same fuel use provides the same service.</p>}
  </section>;
}

export default function PlanTesting({site,baseline,user}) {
  const [view,setView]=useState('conditions'),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const initial={solar_multiplier:1,wind_multiplier:1,demand_multiplier:1,fuel_price_multiplier:1,starting_soc:baseline.snapshot.state.soc_pct};
  const [values,setValues]=useState(initial),[outage,setOutage]=useState(false),[hours,setHours]=useState({outage_start:18,outage_end:24});
  async function select(run){setBusy(true);setError('');try{setResult(await api(`/optimization-runs/${run.id}`))}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function test(e){e.preventDefault();setBusy(true);setError('');try{setResult(await api(`/sites/${site.id}/scenario-runs`,{method:'POST',body:{baseline_id:baseline.id,name:'Custom conditions',overrides:{...values,...(outage?hours:{})}}}))}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <><div className="test-intro"><div><h2>Test plan #{baseline.id}</h2><p>Change conditions and compare the result with this saved plan.</p></div><div className="segmented">{[['conditions','Change conditions'],['live','Live replay']].map(([k,l])=><button key={k} aria-pressed={view===k} onClick={()=>setView(k)}>{l}</button>)}</div></div>
    {view==='live'?<LiveControl site={site} baseline={baseline} user={user}/>:<><AutomaticChecks baseline={baseline} site={site} onSelect={select}/><ErrorNotice error={error}/><details className="panel custom-test"><summary>Try a custom combination</summary><p>Combine weather, demand, fuel price, battery and outage changes. Only the experiment changes.</p><form onSubmit={test}><div className="slider-grid">{[['solar_multiplier','Solar availability',0,3,.05],['wind_multiplier','Wind availability',0,3,.05],['demand_multiplier','Demand',.1,3,.05],['fuel_price_multiplier','Diesel price',.1,3,.05],['starting_soc','Starting battery',0,100,1]].map(([k,l,min,max,step])=><label key={k}><span>{l}<b>{n(values[k])}{k==='starting_soc'?'%':'×'}</b></span><input aria-label={l} type="range" min={min} max={max} step={step} value={values[k]} onChange={e=>setValues({...values,[k]:Number(e.target.value)})}/></label>)}</div><label className="check"><input type="checkbox" checked={outage} onChange={e=>setOutage(e.target.checked)}/>Include a generator outage</label>{outage&&<div className="form-grid"><Input label="Outage starts (local hour)" value={hours.outage_start} min={0} max={23} required onChange={v=>setHours({...hours,outage_start:v})}/><Input label="Outage ends (local hour)" value={hours.outage_end} min={1} max={24} required onChange={v=>setHours({...hours,outage_end:v})}/></div>}<button className="primary" disabled={busy||site.archived||!['optimal','feasible'].includes(baseline.status)}>{busy?'Testing…':'Compare with original plan'}</button></form></details>{busy&&<p role="status">Preparing comparison…</p>}{result&&<ScenarioResult baseline={baseline} result={result}/>}</>}
  </>;
}

export function PlanImpact({run,analysis,error}) {
  if(!analysis)return <ErrorNotice error={error||'Preparing comparison…'}/>;
  const c=analysis.comparison;if(!c)return <p>A feasible schedule is needed for this comparison.</p>;

  return <div className="plan-impact"><p>The reactive rule uses renewables first, then storage down to its reserve, then diesel. Both schedules use this plan’s saved inputs.</p><div className="comparison-metrics">{[['diesel_litres','Diesel','L'],['dispatch_cost_inr','Dispatch cost','INR'],['critical_load_served_pct','Critical service','%'],['terminal_soc_pct','Ending battery','%']].map(([k,l,u])=><div key={k}><span>{l}</span><strong>{n(c.baseline.metrics[k])} → {n(run.metrics[k])}<small>{u}</small></strong><small>Reactive → Planned</small></div>)}</div>{c.warnings.map((w,i)=><p className="notice amber" key={i}>{w}</p>)}{Math.abs(c.delta.diesel_litres||0)<.01&&<p className="notice">Both schedules need the same diesel for these inputs. This comparison does not show fuel savings.</p>}<ComparisonChart baseline={{...run,id:"reactive",intervals:c.baseline.intervals}} changed={run} tz={run.snapshot.site.timezone} baselineLabel="Reactive rule" changedLabel="Optimized plan"/><p className="small">{n(c.flexible_energy_shifted_kwh)} kWh of flexible work shifted. Model comparison; projected differences are not measured savings.</p></div>;
}
