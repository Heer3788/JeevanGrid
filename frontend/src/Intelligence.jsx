import React, {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import {Activity, ArrowRight, ArrowUpRight, Battery, CheckCircle2, ChevronDown, Database, Download, Fuel, Info, ShieldCheck, Sun, Wind, Zap, AlertTriangle} from 'lucide-react';
import {ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ReferenceArea, Bar, Brush} from 'recharts';
import {api} from './api';

export const fmt = (v, digits=1) => typeof v === 'number' && Number.isFinite(v) ? (Math.abs(v)<.5/10**digits?0:v).toLocaleString('en-IN', {maximumFractionDigits:digits}) : '—';
export const time = (v, tz='Asia/Kolkata') => v ? new Date(v).toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit', timeZone:tz}) : '—';
const dateTime = (v, tz='Asia/Kolkata') => v ? new Date(v).toLocaleString('en-IN', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:tz}) : 'No reading recorded';
const friendly = v => String(v || 'Not available').replaceAll('_',' ');
const COLORS = {solar:'#d7a526', wind:'#2996c7', battery:'#168b76', diesel:'#d27749'};
const actions = {START_GENERATOR:'Start diesel backup', STOP_GENERATOR:'Stop the generator', USE_RENEWABLES_AND_STORAGE:'Use renewables and storage', CRITICAL_SHORTAGE:'Critical supply needs attention', REVIEW_CONFIGURATION:'Review this configuration'};

export function useAnalysis(runId) {
  const [result,setResult] = useState({id:null,data:null,error:''});
  useEffect(() => {
    let active=true;
    if(runId) api('/optimization-runs/'+runId+'/analysis').then(data=>{if(active)setResult({id:runId,data,error:''})}).catch(e=>{if(active)setResult({id:runId,data:null,error:e.message})});
    return()=>{active=false};
  },[runId]);
  return result.id === runId ? result : {data:null,error:''};
}

export function AnalysisState({error}) {
  return <div className={error?'error':'loading'} role={error?'alert':'status'}>{error||'Preparing saved-run analysis…'}</div>;
}

export function ReliabilityBadge({status}) {
  const label={green:'Reliable',amber:'Needs review',red:'At risk'}[status]||'Not assessed';
  return <span className={'badge '+(status||'neutral')}>{status==='green'?<CheckCircle2 size={13}/>:<AlertTriangle size={13}/>} {label}</span>;
}

export function CommandCentre({run,site,analysis,onCompare}) {
  const action=run.next_action, state=site.current_state, c=run.snapshot?.configuration;
  const valid=['optimal','feasible'].includes(run.status);
  return <section className={'command-centre '+(!valid||run.metrics.critical_unserved_kwh>.001?'command-risk':'')}>
    <div className="command-top"><span className="eyebrow"><Zap size={14}/> NEXT OPERATOR DECISION</span><span className="command-tag">Projected · Run #{run.id}</span></div>
    <div className="command-body"><div><h2>{actions[action.action]||friendly(action.action)}</h2>
      {action.time&&<div className="action-time">{dateTime(action.time,site.timezone)}{action.end_time&&' – '+time(action.end_time,site.timezone)}</div>}
      <p>{action.reason}</p>
      <div className="actions"><a className="command-link" href="#operator-review">Review this plan <ArrowRight size={16}/></a><button className="compare-action" onClick={onCompare}>Compare with reactive operation</button></div>
    </div><div className="state-capsule"><span>Latest entered state</span><strong><Battery size={23}/>{fmt(state.soc_pct)}<small>% SOC</small></strong><p>{state.generator_available?(state.generator_on?'Generator running':'Generator available'):'Generator unavailable'} · {fmt(state.fuel_l)} L fuel</p><small>{state.timestamp?dateTime(state.timestamp,site.timezone):'Demo assumption · no measured reading'}</small></div></div>
    <details className="reason-details"><summary>Why this schedule? <ChevronDown size={15}/></summary>
      {analysis?.explanation?.length?analysis.explanation.map((text,i)=><p key={i}>{text}</p>):<p>Inspect the generation chart and saved inputs below. {c&&'The battery safety floor is '+c.battery.min_soc+'%, with an ending target of '+c.policy.terminal_soc+'%.'}</p>}
    </details>
  </section>;
}

function DispatchTooltip({active,payload,label}) {
  if(!active||!payload?.length)return null;
  const d=payload[0].payload;
  return <div className="energy-tooltip"><b>{label} · planned interval</b>
    <p>Demand served: {fmt(d.served_load)} kW<br/>Battery charging: {fmt(d.battery_charge)} kW<br/>Ending SOC: {fmt(d.battery_soc)}%<br/>Critical shortage: {fmt(d.critical_unserved,3)} kWh</p>
    <small>{d.diesel_on?'Backup runs during this hour.':d.battery_discharge>.001?'Storage supports supply during this hour.':'Renewables supply the scheduled demand.'}</small></div>;
}

export function EnergyFlow({row,configuration}) {
  const [selected,setSelected]=useState('solar');
  if(!row)return null;
  const sources=[
    {id:'solar',name:'Solar',value:row.solar_used,color:COLORS.solar,detail:fmt(row.solar_available)+' kW available · '+fmt(configuration.solar.capacity_kw)+' kW installed. Unused renewables are curtailed.'},
    {id:'wind',name:'Wind',value:row.wind_used,color:COLORS.wind,detail:fmt(row.wind_available)+' kW available · '+fmt(configuration.wind.capacity_kw)+' kW installed.'},
    {id:'battery',name:'Battery discharge',value:row.battery_discharge,color:COLORS.battery,detail:fmt(row.soc_start)+'% → '+fmt(row.battery_soc)+'% SOC. Charge/discharge efficiencies and safety limits apply.'},
    {id:'diesel',name:'Diesel backup',value:row.diesel_power,color:COLORS.diesel,detail:fmt(row.diesel_litres,2)+' L used · '+fmt(configuration.generator.capacity_kw)+' kW installed. '+(row.diesel_start?'Generator starts in this hour.':'No new start in this hour.')}
  ];
  const destinations=[
    {name:'Demand served',value:row.served_load,color:'#234557',y:46},
    {name:'Battery charging',value:row.battery_charge,color:COLORS.battery,y:142}
  ];
  const total=sources.reduce((s,x)=>s+x.value,0);
  const width=v=>v>.001?Math.max(2,12*v/Math.max(1,total)):1;
  const info=sources.find(s=>s.id===selected);
  return <section className="panel flow-panel"><div className="section-heading"><div><h2>Where the energy goes</h2><p>Selected hour · {row.hour} · modelled power, kW</p></div><Activity size={20}/></div>
    <div className="flow-mobile"><div className="mobile-sources">{sources.map(s=><div key={s.id}><span style={{color:s.color}}>{s.name}</span><b>{fmt(s.value)} kW</b></div>)}</div><div className="mobile-bus"><ArrowRight size={18}/> Common AC bus · {fmt(total)} kW</div>{destinations.map(d=><div className="mobile-destination" key={d.name}><span>{d.name}</span><b>{fmt(d.value)} kW</b></div>)}<small>Curtailed: {fmt(row.renewable_curtailment)} kW · Unserved: {fmt(row.critical_unserved+row.normal_unserved)} kWh</small></div>
    <svg viewBox="0 0 800 286" role="img" aria-label="Planned source power flows to demand and battery charging. Select a source below for details." className="flow-svg">
      {sources.map((s,i)=><path key={s.id} d={'M 178 '+(36+i*64)+' C 292 '+(36+i*64)+', 286 134, 390 134'} fill="none" stroke={s.color} strokeWidth={width(s.value)} opacity={s.value>.001?.7:.15}/>)}
      {destinations.map(s=><path key={s.name} d={'M 410 134 C 514 134, 526 '+(s.y+18)+', 606 '+(s.y+18)} fill="none" stroke={s.color} strokeWidth={width(s.value)} opacity={s.value>.001?.7:.15}/>)}
      <circle cx="400" cy="134" r="30" fill="#102e3d"/><text x="400" y="130" textAnchor="middle" fill="#fff" fontSize="11">AC BUS</text><text x="400" y="148" textAnchor="middle" fill="#8ee4cd" fontSize="13">{fmt(total)}</text>
      {sources.map((s,i)=><g key={s.id}><rect x="0" y={8+i*64} width="178" height="53" rx="10" fill="#f5f8fa" stroke={selected===s.id?s.color:'#e0e8ec'}/><circle cx="16" cy={27+i*64} r="4" fill={s.color}/><text x="29" y={30+i*64} fill="#425967" fontSize="12">{s.name}</text><text x="16" y={49+i*64} fill="#19394a" fontSize="16" fontWeight="600">{fmt(s.value)} kW</text></g>)}
      {destinations.map(s=><g key={s.name}><rect x="606" y={s.y} width="190" height="58" rx="10" fill="#f5f8fa" stroke="#e0e8ec"/><text x="623" y={s.y+21} fill="#425967" fontSize="12">{s.name}</text><text x="623" y={s.y+44} fill="#19394a" fontSize="16" fontWeight="600">{fmt(s.value)} kW</text></g>)}
      <text x="606" y="239" fill="#647885" fontSize="12">Curtailed: {fmt(row.renewable_curtailment)} kW</text>
      <text x="606" y="260" fill={row.critical_unserved>.001?'#ad442e':'#647885'} fontSize="12">Unserved: {fmt(row.critical_unserved+row.normal_unserved)} kWh</text>
    </svg>
    <div className="source-select">{sources.map(s=><button key={s.id} aria-pressed={selected===s.id} onClick={()=>setSelected(s.id)}><span style={{background:s.color}}/>{s.name}</button>)}</div>
    <p className="flow-detail"><Info size={15}/><span><b>{info.name}:</b> {info.detail}</span></p>
  </section>;
}

export function DispatchCharts({run,tz='Asia/Kolkata'}) {
  const [index,setIndex]=useState(0);
  useEffect(()=>setIndex(0),[run?.id]);
  if(!run?.intervals?.length)return null;
  const rows=run.intervals.map((r,i)=>({...r,index:i,hour:time(r.timestamp,tz),shortage:r.critical_unserved,scheduled_demand:r.critical_required+r.normal_required+r.flexible_load_scheduled,bus_demand:r.served_load+r.battery_charge}));
  const c=run.snapshot.configuration,b=c.battery;
  const selected=rows[Math.min(index,rows.length-1)];
  const current=rows.find(r=>Date.now()>=new Date(r.timestamp).getTime()&&Date.now()<new Date(r.timestamp).getTime()+3600000);
  return <><section className="panel dispatch-panel"><div className="section-heading"><div><h2>24-hour energy plan</h2><p>{dateTime(rows[0].timestamp,tz)} · {tz} · select an hour to inspect</p></div><span className="unit-label">POWER · kW</span></div>
    <div className="chart dispatch-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows} syncId={'run-'+run.id} onClick={e=>{if(e?.activeTooltipIndex!=null)setIndex(Number(e.activeTooltipIndex))}}>
      <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e5edf1"/><XAxis dataKey="hour" minTickGap={28}/><YAxis/><Tooltip content={<DispatchTooltip/>}/><Legend/>
      <Area type="stepAfter" dataKey="solar_used" name="Solar" stackId="supply" fill={COLORS.solar} stroke={COLORS.solar} fillOpacity={.72} isAnimationActive={false}/>
      <Area type="stepAfter" dataKey="wind_used" name="Wind" stackId="supply" fill={COLORS.wind} stroke={COLORS.wind} fillOpacity={.65} isAnimationActive={false}/>
      <Area type="stepAfter" dataKey="battery_discharge" name="Battery" stackId="supply" fill={COLORS.battery} stroke={COLORS.battery} fillOpacity={.8} isAnimationActive={false}/>
      <Area type="stepAfter" dataKey="diesel_power" name="Diesel" stackId="supply" fill={COLORS.diesel} stroke={COLORS.diesel} fillOpacity={.7} isAnimationActive={false}/>
      <Line type="stepAfter" dataKey="scheduled_demand" name="Requested demand*" stroke="#19394a" strokeWidth={2} dot={false} isAnimationActive={false}/>
      <Line type="stepAfter" dataKey="bus_demand" name="Served + charging" stroke="#617685" strokeDasharray="5 4" dot={false} isAnimationActive={false}/>
      <Bar dataKey="shortage" name="Critical shortage (kWh)" fill="#c74e45" isAnimationActive={false}/>
      {current&&<ReferenceLine x={current.hour} stroke="#243f50" strokeDasharray="3 3" label="Now"/>}<ReferenceLine x={selected.hour} stroke="#129681"/>
      <Brush dataKey="hour" height={22} stroke="#b9d3d1" travellerWidth={8}/>
    </ComposedChart></ResponsiveContainer></div>
    <small>*Critical + normal demand + flexible work scheduled for that hour. Unfinished flexible work is reported separately. Intervals are one hour; shortage bars show kWh.</small>
    <div className="hour-picker"><label htmlFor={'hour-'+run.id}>Inspect hour <b>{selected.hour}</b></label><input id={'hour-'+run.id} aria-label="Inspect dispatch hour" type="range" min="0" max={rows.length-1} value={index} onChange={e=>setIndex(Number(e.target.value))}/></div>
    <div className="soc-heading"><h3><Battery size={16}/> Battery reserve</h3><small>End of each hour · SOC %</small></div>
    <div className="soc-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows} syncId={'run-'+run.id}>
      <CartesianGrid vertical={false} stroke="#e5edf1"/><XAxis dataKey="hour" minTickGap={28}/><YAxis domain={[0,100]}/><Tooltip formatter={v=>fmt(v)+'%'}/>
      <ReferenceArea y1={0} y2={b.min_soc} fill="#fbe5e1" fillOpacity={.6}/><ReferenceLine y={b.min_soc} stroke="#b34939" strokeDasharray="3 3" label={{value:'Safety '+b.min_soc+'%',position:'insideTopRight',fontSize:10}}/>
      <ReferenceLine y={b.reserve_soc} stroke="#a58029" strokeDasharray="5 4" label={{value:'Reserve '+b.reserve_soc+'%',position:'insideTopLeft',fontSize:10}}/>
      <Line dataKey="battery_soc" name="End-of-hour SOC" stroke={COLORS.battery} strokeWidth={2.5} dot={false} isAnimationActive={false}/><ReferenceLine x={selected.hour} stroke="#129681"/>
    </ComposedChart></ResponsiveContainer></div>
    <div className="interval-summary"><span>Hour {selected.hour}</span><b>{fmt(selected.served_load)} kW served</b><b>{fmt(selected.battery_soc)}% ending SOC</b><span>{selected.diesel_on?'Backup scheduled':'Backup off'}</span></div>
  </section><EnergyFlow row={selected} configuration={c}/></>;
}

export function TrustPanel({run,analysis,site}) {
  const snapshot=run.snapshot;
  const age=run.weather_retrieved_at?Math.max(0,(Date.now()-new Date(run.weather_retrieved_at))/3600000):null;
  const source=run.weather_source;
  const freshness=source==='open_meteo'?(age!==null&&age<=6?'Fresh forecast':'Stale forecast'):source==='nasa_power'?'Historical replay':'Simulated weather';
  return <section className="panel trust-panel"><div className="section-heading"><div><h2>Data behind this decision</h2><p>Saved with run #{run.id}. Every displayed outcome is a projection.</p></div><ShieldCheck size={21}/></div>
    <div className="trust-grid">
      <div><span>Weather</span><b>{friendly(source)}</b><small>{freshness} · retrieved {age===null?'—':fmt(age)+'h ago'}</small></div>
      <div><span>Community demand</span><b>{friendly(run.demand_source)}</b><small>{snapshot.demand_note}</small></div>
      <div><span>Starting state</span><b>{friendly(run.state_source)}</b><small>{dateTime(snapshot.state.timestamp,snapshot.site.timezone)}</small></div>
      <div><span>Configuration</span><b>Version {run.configuration_version}</b><small>{site&&site.configuration_version!==run.configuration_version?'Changed since this run':'Frozen input snapshot'}</small></div>
      <div><span>Data coverage</span><b>{analysis?analysis.trust.row_count+' / 24 hours':'Checking…'}</b><small>{analysis?analysis.trust.missing_weather_rows+' rows missing weather fields':'Checking completeness'}</small></div>
      <div><span>Solver result</span><b>{friendly(run.status)}</b><small>{fmt(run.solve_seconds,3)} seconds · priorities before cost</small></div>
    </div>
    {analysis?.trust.warnings.map((s,i)=><p className="trust-note" key={i}><Info size={14}/>{s}</p>)}
    <small>Weather APIs estimate regional conditions. Forecast freshness is not a measured accuracy score.</small>
  </section>;
}

const COLUMNS=[
  ['timestamp','Timestamp (ISO)'],['critical_required','Critical demand (kW)'],['normal_required','Normal demand (kW)'],
  ['flexible_load_scheduled','Flexible served (kW)'],['ghi','Irradiance (W/m²)'],['temperature','Temperature (°C)'],
  ['wind_speed','Wind at 10m (m/s)'],['solar_available','Solar available (kW)'],['wind_available','Wind available (kW)'],
  ['solar_used','Solar used (kW)'],['wind_used','Wind used (kW)'],['battery_charge','Charge (kW)'],
  ['battery_discharge','Discharge (kW)'],['diesel_power','Diesel (kW)'],['battery_soc','Ending SOC (%)'],
  ['critical_unserved','Critical unserved (kWh)'],['normal_unserved','Normal unserved (kWh)'],['weather_source','Weather source'],['demand_source','Demand source']
];
function downloadCsv(rows, name) {
  const cell=v=>{
    let s=String(v??'');
    if(typeof v==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;
    return '"'+s.replaceAll('"','""')+'"';
  };
  const text='\uFEFF'+[COLUMNS.map(x=>cell(x[1])).join(','),...rows.map(r=>COLUMNS.map(([k])=>cell(r[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8;'}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function DatasetExplorer({run,analysis,error}) {
  const [group,setGroup]=useState('demand'),[filter,setFilter]=useState('all');
  if(!run)return <div className="empty"><Database size={28}/><h2>No saved dataset yet</h2><p>Generate a plan to inspect its hourly inputs and dispatch.</p></div>;
  if(!analysis)return <AnalysisState error={error}/>;
  const keys={demand:['timestamp','critical_required','normal_required','flexible_load_scheduled','critical_unserved','normal_unserved'],
    weather:['timestamp','ghi','temperature','wind_speed','solar_available','wind_available','weather_source'],
    dispatch:['timestamp','solar_used','wind_used','battery_charge','battery_discharge','diesel_power','battery_soc'],
    sources:['timestamp','weather_source','demand_source']}[group];
  const rows=analysis.dataset.filter(r=>filter==='all'||filter==='missing'&&r.missing_fields.length||filter==='shortage'&&((r.critical_unserved||0)+(r.normal_unserved||0)>.001));
  const tz=run.snapshot.site.timezone;
  return <><TrustPanel run={run} analysis={analysis}/><section className="panel">
    <div className="section-heading"><div><h2>Dataset Explorer</h2><p>Run #{run.id} · hourly inputs and outputs · {tz}</p></div><button className="secondary" disabled={!rows.length} onClick={()=>downloadCsv(rows,'jeevangrid-run-'+run.id+'-dataset.csv')}><Download size={15}/>Download CSV</button></div>
    <div className="explorer-controls"><div className="segmented">{['demand','weather','dispatch','sources'].map(g=><button key={g} aria-pressed={group===g} onClick={()=>setGroup(g)}>{friendly(g)}</button>)}</div><label>Rows <select aria-label="Filter dataset rows" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All hours</option><option value="missing">Missing weather</option><option value="shortage">Supply shortages</option></select></label></div>
    {group!=='sources'&&<div className="dataset-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows.map(r=>({...r,hour:time(r.timestamp,tz)}))}><CartesianGrid vertical={false} stroke="#e5edf1"/><XAxis dataKey="hour" minTickGap={28}/><YAxis/><Tooltip/><Legend/>
      {(group==='demand'?[['critical_required','Critical (kW)','#bc6250'],['normal_required','Normal (kW)','#2996c7'],['flexible_load_scheduled','Flexible served (kW)','#168b76']]:group==='weather'?[['solar_available','Solar available (kW)',COLORS.solar],['wind_available','Wind available (kW)',COLORS.wind]]:[['solar_used','Solar (kW)',COLORS.solar],['wind_used','Wind (kW)',COLORS.wind],['diesel_power','Diesel (kW)',COLORS.diesel]]).map(([key,name,color])=><Line key={key} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} isAnimationActive={false}/>)}
    </ComposedChart></ResponsiveContainer></div>}
    <div className="table-scroll"><table><thead><tr>{keys.map(k=><th key={k}>{COLUMNS.find(c=>c[0]===k)[1]}</th>)}<th>Quality</th></tr></thead><tbody>{rows.map(r=><tr key={r.timestamp}>{keys.map(k=><td key={k}>{k==='timestamp'?dateTime(r[k],tz):typeof r[k]==='number'?fmt(r[k],2):friendly(r[k])}</td>)}<td>{r.missing_fields.length?'Missing: '+r.missing_fields.join(', '):'Weather complete'}{!r.dispatch_available?' · No dispatch':''}</td></tr>)}</tbody></table></div>
    {!rows.length&&<p className="empty">No hours match this filter.</p>}<small>{rows.length} of {analysis.dataset.length} rows · CSV includes all columns for the filtered hours. Flexible work is scheduled energy, not a measured hourly demand stream.</small>
    <Link className="text-link" to={'/runs/'+run.id}>Open the saved run <ArrowUpRight size={14}/></Link>
  </section></>;
}

export function ImpactAnalysis({run,analysis,error}) {
  if(!analysis)return <AnalysisState error={error}/>;
  const comparison=analysis.comparison;
  if(!comparison)return <div className="empty">Impact comparison needs a feasible operating plan.</div>;
  const baseline=comparison.baseline.metrics, optimized=run.metrics;
  const metrics=[['critical_load_served_pct','Critical energy served','%'],['normal_unserved_kwh','Normal energy unserved','kWh'],['flexible_unserved_kwh','Flexible work unfinished','kWh'],['dispatch_cost_inr','Dispatch cost','INR'],['diesel_litres','Diesel required','L'],['emissions_kg_co2','Combustion emissions','kg CO₂'],['generator_starts','Generator starts','starts'],['renewable_share_pct','Renewable generation','%'],['minimum_soc_pct','Minimum SOC','%'],['terminal_soc_pct','Ending SOC','%']];
  const rows=run.intervals.map((r,i)=>({hour:time(r.timestamp,run.snapshot.site.timezone),optimized:r.diesel_power,reactive:comparison.baseline.intervals[i].diesel_power}));
  return <><section className="panel"><div className="section-heading"><div><h2>What does planning ahead change?</h2><p>Forecast-aware optimization versus an illustrative reactive controller.</p></div><span className="badge">Model comparison</span></div>
    <div className="baseline-rule"><Fuel size={20}/><div><b>Reactive operating rule</b><p>{comparison.controller}</p></div></div>
    <div className="impact-cards">{[['diesel_litres','Diesel difference','L'],['dispatch_cost_inr','Dispatch cost difference','INR'],['critical_unserved_kwh','Critical shortage difference','kWh']].map(([k,l,u])=>{const delta=comparison.delta[k];return <div key={k}><span>{l}</span><strong>{delta>0?'+':''}{fmt(delta)} <small>{u}</small></strong><small>Optimized minus reactive</small></div>})}</div>
    {comparison.warnings.map((s,i)=><div className="notice amber" key={i}><Info size={16}/>{s}</div>)}
    <p className="trust-note"><Activity size={15}/>{comparison.flexible_energy_shifted_kwh==null?'Flexible energy served differs; a like-for-like shift amount is unavailable.':fmt(comparison.flexible_energy_shifted_kwh,2)+' kWh of flexible work occurs in different hours from the reactive schedule (same total flexible energy served).'}</p>
    {comparison.like_for_like&&<p className="notice"><CheckCircle2 size={16}/>Served demand and ending SOC match within tolerance. Cost and fuel changes can be compared directly for this modelled day.</p>}
    <div className="dataset-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows}><CartesianGrid vertical={false} stroke="#e5edf1"/><XAxis dataKey="hour" minTickGap={28}/><YAxis/><Tooltip formatter={v=>fmt(v)+' kW'}/><Legend/><Line dataKey="reactive" name="Reactive diesel" stroke="#9aa8b2" strokeDasharray="5 4" dot={false} type="stepAfter" isAnimationActive={false}/><Line dataKey="optimized" name="Optimized diesel" stroke={COLORS.diesel} strokeWidth={2} dot={false} type="stepAfter" isAnimationActive={false}/></ComposedChart></ResponsiveContainer></div>
    <div className="table-scroll"><table><thead><tr><th>Same 24-hour inputs</th><th>Reactive rule</th><th>Optimized plan</th><th>Change</th></tr></thead><tbody>{metrics.map(([k,l,u])=><tr key={k}><td>{l}</td><td>{fmt(baseline[k],2)} {u}</td><td>{fmt(optimized[k],2)} {u}</td><td>{comparison.delta[k]>0?'+':''}{fmt(comparison.delta[k],2)} {u==='%'?'pp':u}</td></tr>)}</tbody></table></div>
    <small>{comparison.basis} Controller version: {analysis.analysis_version}. The reactive controller preserves physical limits but does not plan its terminal SOC. Differences are not measured savings.</small>
    <details><summary>Inspect the reactive schedule</summary><div className="table-scroll"><table><thead><tr><th>Hour</th><th>Diesel kW</th><th>SOC %</th><th>Critical unserved kWh</th><th>Flexible kW</th></tr></thead><tbody>{comparison.baseline.intervals.map(r=><tr key={r.timestamp}><td>{time(r.timestamp,run.snapshot.site.timezone)}</td><td>{fmt(r.diesel_power)}</td><td>{fmt(r.battery_soc)}</td><td>{fmt(r.critical_unserved)}</td><td>{fmt(r.flexible_load_scheduled)}</td></tr>)}</tbody></table></div></details>
  </section></>;
}

const PRESETS=[['cloudy','Cloudy day','Solar −50%'],['low_wind','Low wind','Wind −50%'],['high_demand','High demand','Demand +25%'],['expensive_fuel','Expensive fuel','Price +25%'],['generator_outage','Generator outage','18:00–24:00'],['low_battery','Low battery','Starting SOC 25%']];
const PRESET_OVERRIDES={cloudy:{solar_multiplier:.5},low_wind:{wind_multiplier:.5},high_demand:{demand_multiplier:1.25},expensive_fuel:{fuel_price_multiplier:1.25},generator_outage:{outage_start:18,outage_end:24},low_battery:{starting_soc:25}};
export function ResilienceMatrix({baseline,site,onSaved,refreshKey}) {
  const [runs,setRuns]=useState([]),[busy,setBusy]=useState(false),[progress,setProgress]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let active=true;setRuns([]);if(baseline)api('/optimization-runs/'+baseline.id+'/scenarios').then(r=>{if(active)setRuns(r)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[baseline?.id,refreshKey]);
  if(!baseline)return null;
  async function assess() {
    setBusy(true);setError('');
    try {
      for(let i=0;i<PRESETS.length;i++) {
        setProgress('Testing '+PRESETS[i][1]+' · '+(i+1)+' / '+PRESETS.length);
        const r=await api('/sites/'+site.id+'/scenario-runs',{method:'POST',body:{baseline_id:baseline.id,preset:PRESETS[i][0]}});
        setRuns(prev=>[r,...prev]);
      }
      setProgress('Six scenarios saved.');onSaved?.();
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  const status=r=>!r||!['optimal','feasible'].includes(r.status)||r.metrics.critical_unserved_kwh>.001?'red':r.metrics.reserve_compliance_pct<99.999?'amber':'green';
  const latest=PRESETS.map(([key,name,change])=>({key,name,change,run:runs.find(r=>r.scenario_name===key&&Object.keys(r.overrides||{}).length===Object.keys(PRESET_OVERRIDES[key]).length&&Object.entries(PRESET_OVERRIDES[key]).every(([k,v])=>r.overrides[k]===v))}));
  return <section className="panel"><div className="section-heading"><div><h2>Resilience matrix</h2><p>Stress tests linked to baseline #{baseline.id}. Each row uses the same optimizer.</p></div><button className="secondary" onClick={assess} disabled={busy||site.archived||!['optimal','feasible'].includes(baseline.status)}><ShieldCheck size={16}/>{busy?'Testing scenarios…':'Test six scenarios'}</button></div>
    {progress&&<p role="status">{progress}</p>}{error&&<p className="error" role="alert">{error}</p>}
    <div className="table-scroll"><table><thead><tr><th>Scenario</th><th>Critical served</th><th>Min SOC</th><th>Diesel</th><th>Assessment</th><th>Result</th></tr></thead><tbody>
      {[{key:'base',name:'Original plan',change:'Saved inputs',run:baseline},...latest].map(({key,name,change,run:r})=><tr key={key}><td><b>{name}</b><small>{change}</small></td><td>{fmt(r?.metrics.critical_load_served_pct)}%</td><td>{fmt(r?.metrics.minimum_soc_pct)}%</td><td>{fmt(r?.metrics.diesel_litres)} L</td><td>{r?<ReliabilityBadge status={status(r)}/>:<span className="badge">Not tested</span>}</td><td>{r&&<Link to={'/runs/'+r.id}>Open #{r.id}</Link>}</td></tr>)}
    </tbody></table></div><small>Reliable = critical energy served and operating reserve preserved in that test. This is an hourly energy adequacy assessment, not a guarantee of physical uptime.</small>
  </section>;
}

export function ConfigurationCards({configuration:c}) {
  if(!c)return null;
  const cards=[
    [Sun,'Solar',fmt(c.solar.capacity_kw)+' kW',[['Panel tilt',c.solar.tilt+'°'],['Azimuth',c.solar.azimuth+'°'],['Provenance',friendly(c.solar.provenance)]]],
    [Wind,'Wind',fmt(c.wind.capacity_kw)+' kW',[['Hub height',c.wind.hub_height_m+' m'],['Rated wind',c.wind.rated_speed+' m/s'],['Provenance',friendly(c.wind.provenance)]]],
    [Battery,'Battery',fmt(c.battery.capacity_kwh)+' kWh',[['Safe SOC',c.battery.min_soc+'–'+c.battery.max_soc+'%'],['Operating reserve',c.battery.reserve_soc+'%'],['End target',c.policy.terminal_soc+'%']]],
    [Fuel,'Diesel',fmt(c.generator.capacity_kw)+' kW',[['Minimum output',c.generator.min_power_kw+' kW'],['Default price','INR '+c.generator.diesel_price+'/L'],['Start limit',c.policy.max_starts+' / day']]]
  ];
  return <div className="config-cards">{cards.map(([Icon,name,value,rows])=><div className="config-card" key={name}><Icon size={22}/><span>{name}</span><strong>{value}</strong>{rows.map(([k,v])=><div className="summary-row" key={k}><span>{k}</span><b>{v}</b></div>)}</div>)}</div>;
}
