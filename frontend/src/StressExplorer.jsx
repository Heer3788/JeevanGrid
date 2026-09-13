import React,{useEffect,useState} from 'react';
import {ArrowUpRight,RefreshCw,ShieldCheck,AlertTriangle} from 'lucide-react';
import {ResponsiveContainer,BarChart,Bar,Cell,XAxis,YAxis,CartesianGrid,Tooltip,ReferenceLine} from 'recharts';
import {api} from './api';
import {number as n,ErrorNotice} from './ui';
import {colors} from './chartTheme';
import {checks,matches,feasible,stressFinding,stressMetrics} from './stressInsights';

export default function StressExplorer({baseline,site,compact=false,onSelect}) {
  const [runs,setRuns]=useState([]),[state,setState]=useState('pending'),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  const [metric,setMetric]=useState('reserve'),[selected,setSelected]=useState(null);
  useEffect(()=>{
    let active=true,timer;
    setRuns([]);setSelected(null);setError('');setState('pending');
    if(!feasible(baseline)){setState('unavailable');return}
    async function poll(){try{
      const all=await api(`/optimization-runs/${baseline.id}/scenarios`);
      if(!active)return;
      const found=checks.map(([k])=>all.find(r=>r.scenario_name===k&&matches(r))).filter(Boolean);setRuns(found);
      if(found.length===6){setState('complete');return}
      if(site.archived){setState('archived');return}
      const job=await api(`/optimization-runs/${baseline.id}/scenarios`,{method:'POST',body:{retry:attempt>0}});
      if(!active)return;setState(job.status);if(job.error){setError(job.error);return}
      timer=setTimeout(poll,4000);
    }catch(e){if(active){setError(e.message);setState('failed')}}}
    poll();return()=>{active=false;clearTimeout(timer)};
  },[baseline?.id,site.archived,attempt]);
  if(state==='unavailable')return <section className="panel stress-explorer"><h2>Plan stress tests</h2><p>Generate a feasible plan before comparing stress scenarios.</p></section>;
  const c=baseline.snapshot.configuration,measure=stressMetrics[metric];
  const rows=checks.map(([key,name,change])=>{const run=runs.find(r=>r.scenario_name===key),finding=stressFinding(run,baseline);return {key,name,change,run,...finding,value:feasible(run)?measure.value(run.metrics,c):null}});
  const resolved=rows.filter(r=>r.run),risks=resolved.filter(r=>['red','amber'].includes(r.tone));
  const ranked=[...resolved].sort((a,b)=>({red:0,amber:1,green:2,neutral:3}[a.tone]-{red:0,amber:1,green:2,neutral:3}[b.tone])||((a.run.metrics.minimum_soc_pct??100)-(b.run.metrics.minimum_soc_pct??100)));
  const current=rows.find(r=>r.key===(selected||ranked[0]?.key)),baseValue=measure.value(baseline.metrics,c);
  const palette={green:colors.battery,amber:colors.reserve,red:colors.shortage,neutral:colors.reference};
  return <section className={'panel stress-explorer '+(compact?'compact':'')}>
    <div className="section-heading"><div><div className="eyebrow">PLAN STRESS TESTS</div><h2>How much headroom do you have?</h2><p role="status">{state==='complete'?`6 scenarios evaluated · ${risks.length?`${risks.length} need attention`:'no applicable stress failures'}${resolved.some(r=>r.tone==='neutral')?` · ${resolved.filter(r=>r.tone==='neutral').length} not applicable`:''}`:state==='unavailable'?'Generate a feasible plan to evaluate stress conditions.':state==='archived'?'Archived site · showing saved results':state==='failed'?'Assessment interrupted':`Evaluating conditions · ${runs.length} of 6 complete`}</p></div><span className={'stress-status '+(risks.length?'amber':'')}>{state==='complete'?(risks.length?<AlertTriangle size={18}/>:<ShieldCheck size={18}/>):<RefreshCw size={18} className={['pending','running'].includes(state)?'spin':''}/>}<span>Plan #{baseline.id}</span></span></div>
    <ErrorNotice error={error}/>{error&&<button className="secondary" onClick={()=>setAttempt(v=>v+1)}>Retry checks</button>}
    <div className="stress-toolbar"><div className="segmented" aria-label="Stress comparison metric">{Object.entries(stressMetrics).map(([k,m])=><button key={k} aria-pressed={metric===k} onClick={()=>setMetric(k)}>{m.label}</button>)}</div><span className="small">Original plan <b>{n(baseValue)} {measure.unit}</b></span></div>
    <div className="stress-layout"><div><div className="stress-chart" role="img" aria-label={`${measure.label} by scenario, ${measure.unit}. ${rows.map(r=>`${r.name}: ${r.value==null?'pending or unavailable':n(r.value)}`).join('; ')}`}><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{top:12,right:20,bottom:4,left:0}} onClick={e=>{if(e?.activeTooltipIndex!=null)setSelected(rows[Number(e.activeTooltipIndex)]?.key)}}><CartesianGrid horizontal={false} strokeDasharray="3 5"/><XAxis type="number" tickLine={false} axisLine={false} domain={[min=>Math.min(0,min),max=>Math.max(0,max)]} tickFormatter={v=>Math.abs(v)>=1000?`${n(v/1000)}k`:n(v)}/><YAxis type="category" dataKey="name" width={112} tickLine={false} axisLine={false}/><Tooltip formatter={v=>`${n(v,2)} ${measure.unit}`} cursor={{fill:colors.grid}}/><ReferenceLine x={0} stroke={colors.reference}/><ReferenceLine x={baseValue} stroke={colors.demand} strokeDasharray="4 4"/><Bar dataKey="value" name={measure.label} barSize={18} radius={[0,4,4,0]} isAnimationActive={false}>{rows.map(r=><Cell key={r.key} fill={palette[r.tone]||colors.grid} opacity={current&&current.key!==r.key?0.5:1}/>)}</Bar></BarChart></ResponsiveContainer></div><p className="chart-caption">{measure.caption} Dashed line = original plan.</p></div>
      <div className="stress-insight"><label className="source-field">Inspect a scenario<select aria-label="Inspect stress scenario" value={current?.key||''} onChange={e=>setSelected(e.target.value)}><option value="" disabled>Choose a completed scenario</option>{rows.map(r=><option key={r.key} value={r.key} disabled={!r.run}>{r.name}{!r.run?' · pending':''}</option>)}</select></label>{current?<><span className={'badge '+current.tone}>{current.label}</span><h3>{current.change}</h3><p>{current.detail}</p>{feasible(current.run)?<><div className="stress-main-value"><strong>{n(current.run.metrics.minimum_soc_pct)}<small>%</small></strong><span>lowest battery charge<br/><b>{n(Math.abs(current.run.metrics.minimum_soc_pct-c.battery.reserve_soc))} pp</b> {current.run.metrics.minimum_soc_pct<c.battery.reserve_soc?'below':'above'} reserve</span></div><div className="stress-mini-metrics"><div><small>Critical served</small><b>{n(current.run.metrics.critical_load_served_pct)}%</b></div><div><small>Diesel change</small><b>{n(current.run.metrics.diesel_litres-baseline.metrics.diesel_litres)} L</b></div></div></>:<p className="notice amber">No schedule available; numeric comparisons are unavailable.</p>}<button className="secondary full" onClick={()=>onSelect?.(current.run)}>Inspect hourly response<ArrowUpRight size={15}/></button></>:<div className="stress-pending"><RefreshCw className="spin" size={24}/><p>The worker is solving real scenarios against the same saved inputs.</p><progress max={6} value={runs.length}/></div>}</div>
    </div>
  </section>;
}
