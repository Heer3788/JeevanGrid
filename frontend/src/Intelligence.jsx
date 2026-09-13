import React, {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight, Battery, CheckCircle2, Database, Download, Fuel, Info, ShieldCheck, Sun, Wind, AlertTriangle} from 'lucide-react';
import {ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend} from 'recharts';
import {api} from './api';

export const fmt = (v, digits=1) => typeof v === 'number' && Number.isFinite(v) ? (Math.abs(v)<.5/10**digits?0:v).toLocaleString('en-IN', {maximumFractionDigits:digits}) : '—';
export const time = (v, tz='Asia/Kolkata') => v ? new Date(v).toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit', timeZone:tz}) : '—';
const dateTime = (v, tz='Asia/Kolkata') => v ? new Date(v).toLocaleString('en-IN', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:tz}) : 'No reading recorded';
const friendly = v => String(v || 'Not available').replaceAll('_',' ');
import {colors as COLORS} from './chartTheme';

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
  return <><details className="panel data-provenance"><summary>Input sources & data quality <span className="badge">{analysis.trust.row_count} / 24 hours</span></summary><TrustPanel run={run} analysis={analysis}/></details><section className="panel">
    <div className="section-heading"><div><h2>Dataset Explorer</h2><p>Run #{run.id} · hourly inputs and outputs · {tz}</p></div><button className="secondary" disabled={!rows.length} onClick={()=>downloadCsv(rows,'jeevangrid-run-'+run.id+'-dataset.csv')}><Download size={15}/>Download CSV</button></div>
    <div className="explorer-controls"><div className="segmented">{['demand','weather','dispatch','sources'].map(g=><button key={g} aria-pressed={group===g} onClick={()=>setGroup(g)}>{friendly(g)}</button>)}</div><label>Rows <select aria-label="Filter dataset rows" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All hours</option><option value="missing">Missing weather</option><option value="shortage">Supply shortages</option></select></label></div>
    {group!=='sources'&&<div className="dataset-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows.map(r=>({...r,hour:time(r.timestamp,tz)}))}><CartesianGrid vertical={false} stroke={COLORS.grid}/><XAxis dataKey="hour" minTickGap={28}/><YAxis/><Tooltip/><Legend/>
      {(group==='demand'?[['critical_required','Critical (kW)',COLORS.critical],['normal_required','Normal (kW)',COLORS.wind],['flexible_load_scheduled','Flexible served (kW)',COLORS.battery]]:group==='weather'?[['solar_available','Solar available (kW)',COLORS.solar],['wind_available','Wind available (kW)',COLORS.wind]]:[['solar_used','Solar (kW)',COLORS.solar],['wind_used','Wind (kW)',COLORS.wind],['diesel_power','Diesel (kW)',COLORS.diesel]]).map(([key,name,color])=><Line key={key} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} isAnimationActive={false}/>)}
    </ComposedChart></ResponsiveContainer></div>}
    <div className="table-scroll"><table><thead><tr>{keys.map(k=><th key={k}>{COLUMNS.find(c=>c[0]===k)[1]}</th>)}<th>Quality</th></tr></thead><tbody>{rows.map(r=><tr key={r.timestamp}>{keys.map(k=><td key={k}>{k==='timestamp'?dateTime(r[k],tz):typeof r[k]==='number'?fmt(r[k],2):friendly(r[k])}</td>)}<td>{r.missing_fields.length?'Missing: '+r.missing_fields.join(', '):'Weather complete'}{!r.dispatch_available?' · No dispatch':''}</td></tr>)}</tbody></table></div>
    {!rows.length&&<p className="empty">No hours match this filter.</p>}<small>{rows.length} of {analysis.dataset.length} rows · CSV includes all columns for the filtered hours. Flexible work is scheduled energy, not a measured hourly demand stream.</small>
    <Link className="text-link" to={'/runs/'+run.id}>Open the saved run <ArrowUpRight size={14}/></Link>
  </section></>;
}

export {EquipmentOverview as ConfigurationCards} from './EnergyVisuals';
