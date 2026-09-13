import React,{useEffect,useState} from 'react';
import {ResponsiveContainer,ComposedChart,Bar,Line,XAxis,YAxis,Tooltip,CartesianGrid,ReferenceLine,ReferenceArea} from 'recharts';
import {number as n} from './ui';

import {colors} from './chartTheme';
export {colors} from './chartTheme';
export const hour=(v,tz)=>new Date(v).toLocaleTimeString('en-GB',{timeZone:tz,hour:'2-digit',minute:'2-digit'});
const clean=v=>Math.abs(v||0)<.0001?0:v;

export function ChartKey({items}) {return <div className="chart-key">{items.map(([label,color])=><span key={label}><i style={{background:color}}/>{label}</span>)}</div>}

export default function PlanCharts({run,tz='Asia/Kolkata'}) {
  const [index,setIndex]=useState(0),[view,setView]=useState('supply');
  useEffect(()=>{setIndex(0)},[run.id]);
  if(!run.intervals?.length)return <div className="empty">No feasible hourly schedule is available. Review the plan diagnostics and site limits.</div>;
  const rows=run.intervals.map(r=>({...Object.fromEntries(Object.entries(r).map(([k,v])=>[k,typeof v==='number'?clean(v):v])),hour:hour(r.timestamp,tz),
    requested:r.critical_required+r.normal_required+r.flexible_load_scheduled,shortage:r.critical_unserved+r.normal_unserved,charge:-clean(r.battery_charge)}));
  const r=rows[Math.min(index,rows.length-1)], b=run.snapshot.configuration.battery;
  const sources=[['solar_used','Solar',colors.solar],['wind_used','Wind',colors.wind],['battery_discharge','Battery discharge',colors.battery],['diesel_power','Diesel',colors.diesel]];
  const keys=view==='supply'?[...sources.map(([,l,c])=>[l,c]),['Demand + charging',colors.demand]]:view==='battery'?[['Stored energy',colors.battery],['Operating reserve',colors.reserve],['Safety minimum',colors.shortage]]:[['Critical demand',colors.critical],['Normal demand',colors.wind],['Flexible work',colors.battery]];
  const total=sources.reduce((sum,[k])=>sum+r[k],0);
  return <section className="panel plan-chart-panel">
    <div className="section-heading"><div><h2>Your day, hour by hour</h2><p>One bar = one hour · {tz}. Select an hour to inspect its balance.</p></div><span className="badge">{view==='battery'?'SOC %':'Power · kW'}</span></div>
    <div className="segmented chart-switch">{[['supply','Energy supply'],['battery','Battery reserve'],['loads','Flexible work']].map(([v,l])=><button key={v} aria-pressed={view===v} onClick={()=>setView(v)}>{l}</button>)}</div>
    <ChartKey items={keys}/>
    <div className="readable-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows} margin={{top:14,right:14,left:0,bottom:0}} onClick={e=>{if(e?.activeTooltipIndex!=null)setIndex(Number(e.activeTooltipIndex))}}>
      <CartesianGrid vertical={false} stroke={colors.grid}/><XAxis dataKey="hour" minTickGap={30} tick={{fontSize:12}} tickLine={false} axisLine={false}/>
      <YAxis domain={view==='battery'?[0,100]:[0,'auto']} tick={{fontSize:12}} tickLine={false} axisLine={false}/><Tooltip formatter={(v,name)=>[n(v,2)+(view==='battery'?'%':' kW'),name]}/>
      {view==='supply'&&<>{sources.map(([key,label,color])=><Bar key={key} dataKey={key} name={label} stackId="power" fill={color} maxBarSize={32} isAnimationActive={false}/>)}<Line dataKey={v=>v.served_load+v.battery_charge} name="Demand served + charging" stroke={colors.demand} strokeWidth={2.5} dot={false} type="stepAfter" isAnimationActive={false}/>{rows.some(v=>v.shortage>.001)&&<Line dataKey="shortage" name="Unserved demand" stroke={colors.shortage} strokeWidth={2} dot={false} type="stepAfter"/>}</>}
      {view==='battery'&&<><ReferenceArea y1={0} y2={b.min_soc} fill="#fcf2eb" fillOpacity={1}/><ReferenceLine y={b.min_soc} stroke={colors.shortage} strokeDasharray="4 4"/><ReferenceLine y={b.reserve_soc} stroke={colors.reserve} strokeDasharray="5 4"/><Line dataKey="battery_soc" name="End-of-hour battery SOC" stroke={colors.battery} strokeWidth={3} dot={{r:2}} isAnimationActive={false}/></>}
      {view==='loads'&&<><Bar dataKey="critical_required" name="Critical demand" stackId="loads" fill={colors.critical} isAnimationActive={false}/><Bar dataKey="normal_required" name="Normal demand" stackId="loads" fill={colors.wind} isAnimationActive={false}/><Bar dataKey="flexible_load_scheduled" name="Flexible work" stackId="loads" fill={colors.battery} isAnimationActive={false}/></>}
      <ReferenceLine x={r.hour} stroke={colors.demand} strokeDasharray="3 3"/>
    </ComposedChart></ResponsiveContainer></div>
    {view==='battery'&&<p className="chart-caption">Minimum planned {n(run.metrics.minimum_soc_pct)}% · Operating reserve {b.reserve_soc}% · Safety minimum {b.min_soc}% · Ending target {run.snapshot.configuration.policy.terminal_soc}%</p>}
    <div className="hour-inspector"><label>Inspect {r.hour}<input aria-label="Inspect dispatch hour" type="range" min="0" max={rows.length-1} value={index} onChange={e=>setIndex(Number(e.target.value))}/></label><div className="hour-facts"><span><b>{n(r.served_load)} kW</b> supplied</span><span><b>{n(r.battery_soc)}%</b> battery</span><span><b>{n(r.diesel_power)} kW</b> diesel</span></div></div>
    <div className="energy-balance"><div><h3>Supply at {r.hour}</h3><div className="balance-bar">{sources.filter(([k])=>r[k]>.001).map(([k,l,c])=><span key={k} title={`${l}: ${n(r[k])} kW`} style={{width:`${100*r[k]/Math.max(total,.001)}%`,background:c}}/>)}</div><div className="balance-values">{sources.map(([k,l,c])=><span key={k}><i style={{background:c}}/>{l}<b>{n(r[k])} kW</b></span>)}</div></div><div><h3>Used for</h3><div className="summary-row"><span>Community demand</span><b>{n(r.served_load)} kW</b></div><div className="summary-row"><span>Battery charging</span><b>{n(r.battery_charge)} kW</b></div>{r.shortage>.001&&<div className="error">{n(r.shortage)} kWh unmet in this hour</div>}<small>{n(r.renewable_curtailment)} kW renewable surplus curtailed</small></div></div>
    {view==='loads'&&<div className="task-timeline"><h3>Flexible-load schedule</h3>{run.snapshot.configuration.flexible_loads.map(task=><div className="task-track" key={task.name}><span>{task.name}<small>{task.start_hour}:00–{task.end_hour}:00 · {n(task.required_kwh)} kWh needed</small></span><div>{rows.map((row,i)=>{const power=row.flexible_tasks?.find(t=>t.name===task.name)?.power_kw||0;return <button key={i} aria-label={`${task.name}, ${row.hour}, ${n(power)} kW`} title={`${row.hour}: ${n(power)} kW`} className={power>.001?'scheduled':''} onClick={()=>setIndex(i)} style={{opacity:power>.001?.35+.65*power/task.power_kw:1}}/>})}</div></div>)}</div>}
  </section>;
}

export function ComparisonChart({baseline,changed,tz='Asia/Kolkata',baselineLabel,changedLabel}) {
  const [metric,setMetric]=useState('battery_soc');
  const unit=metric==='battery_soc'?'%':metric==='unserved'?'kWh':'kW';
  const value=r=>metric==='unserved'?(r?.critical_unserved||0)+(r?.normal_unserved||0):clean(r?.[metric]);
  const rows=baseline.intervals.map((r,i)=>({hour:hour(r.timestamp,tz),baseline:value(r),changed:value(changed.intervals?.[i])}));
  const same=rows.every(r=>Math.abs(r.baseline-r.changed)<.001);
  return <><div className="segmented chart-switch" aria-label="Hourly comparison metric">{[['battery_soc','Battery charge'],['diesel_power','Diesel output'],['served_load','Demand served'],['unserved','Unserved demand']].map(([k,l])=><button key={k} aria-pressed={metric===k} onClick={()=>setMetric(k)}>{l}</button>)}</div><ChartKey items={[[baselineLabel||`Original #${baseline.id}`,colors.reference],[changedLabel||`Test #${changed.id}`,colors.battery]]}/><div className="readable-chart compact"><ResponsiveContainer><ComposedChart data={rows}><CartesianGrid vertical={false} stroke={colors.grid}/><XAxis dataKey="hour" minTickGap={30}/><YAxis domain={metric==='battery_soc'?[0,100]:[0,max=>Math.max(1,max)]}/><Tooltip formatter={v=>n(v)+' '+unit}/>{metric==='battery_soc'&&<ReferenceLine y={baseline.snapshot.configuration.battery.reserve_soc} stroke={colors.reserve} strokeDasharray="5 4"/>}<Line dataKey="baseline" name={baselineLabel||"Original plan"} stroke={colors.reference} strokeWidth={3} strokeDasharray="5 4" dot={false} isAnimationActive={false}/><Line dataKey="changed" name={changedLabel||"Changed conditions"} stroke={colors.battery} strokeWidth={2.5} dot={false} isAnimationActive={false}/></ComposedChart></ResponsiveContainer></div>{same&&<p className="chart-caption">These hourly values overlap. Choose another measure to inspect how the scenario affects the plan.</p>}</>;
}
