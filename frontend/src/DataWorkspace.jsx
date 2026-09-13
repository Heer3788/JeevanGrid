import React,{useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {api,downloadDataset} from './api';
import {DatasetExplorer,useAnalysis} from './Intelligence';
import {ErrorNotice,number as n} from './ui';

function SiteInventory({site}) {
  const p=site.provenance;
  if(!p?.inventory)return null;
  return <details className="panel"><summary>How this site's demand was calculated · {p.households} households</summary>
    <p>{p.note}</p><div className="table-wrap"><table><thead><tr><th>Load</th><th>Count</th><th>W each</th><th>Duty</th><th>Local hours</th><th>kWh/day</th><th>Priority</th></tr></thead><tbody>{p.inventory.map((r,i)=><tr key={i}><td>{r.name}</td><td>{r.count}</td><td>{r.watts_each}</td><td>{n(r.duty_factor*100)}%</td><td>{r.hours.join(', ')}</td><td>{n(r.daily_kwh,3)}</td><td>{r.priority}</td></tr>)}</tbody></table></div>
    <p>Fixed load = count × watts × duty × hours ÷ 1,000. Pumps and batch tasks are added separately in the saved configuration and scheduled by the optimizer.</p>
    {p.water_calculation&&<p>Drinking water: {n(p.water_calculation.volume_m3_day)} m³/day lifted {p.water_calculation.head_m} m at 45% pump-system efficiency → {n(p.water_calculation.required_kwh_day,3)} kWh/day.</p>}
    <details><summary>Engineering assumptions & reference sources</summary><ul>{p.assumed_fields.map((x,i)=><li key={i}>{x}</li>)}</ul>{p.sources.map(s=><p key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> — {s.supports}</p>)}</details>
  </details>;
}

function ForecastModels({site,user}) {
  return <><SiteInventory site={site}/><ForecastModelPanel site={site} user={user}/></>;
}

function ForecastModelPanel({site,user}) {
  const [model,setModel]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let active=true;api(`/sites/${site.id}/forecast-model`).then(d=>{if(active)setModel(d)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[site.id]);
  async function train(body){setBusy(true);setError('');try{setModel(await api(`/sites/${site.id}/forecast-model`,{method:'POST',body}))}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <details className="panel"><summary>Demand forecasting & model datasets</summary><p>Models learn demand and solar residuals from hourly data. Synthetic models are eligible only for simulated data, with held-out checks before selection.</p><ErrorNotice error={error}/>{user.role==='admin'&&<div className="actions"><button className="secondary" disabled={busy||site.archived} onClick={()=>train({source:'simulated'})}>{busy?'Training…':'Train on simulated data'}</button><label className="secondary">Upload training CSV<input type="file" aria-label="Upload training CSV" accept=".csv" disabled={busy||site.archived} onChange={e=>{if(e.target.files[0]){const form=new FormData();form.append('file',e.target.files[0]);train(form)}}}/></label></div>}{model?.report?<><p>{model.report.rows} records · {model.report.provenance}</p>{['demand','solar'].map(k=><div className="summary-row" key={k}><span>{k} test error</span><b>Baseline {n(model.report[k].baseline_mae_kw,3)} → ML {n(model.report[k].ml_mae_kw,3)} kW</b></div>)}<button className="secondary" onClick={()=>downloadDataset(site.id).catch(e=>setError(e.message))}>Download training data</button></>:<p>No trained model. Planning uses the demand profile and physics estimates.</p>}</details>;
}

export default function DataWorkspace({user}) {
  const [params,setParams]=useSearchParams(),[sites,setSites]=useState([]),[runs,setRuns]=useState([]),[run,setRun]=useState(null),[error,setError]=useState('');
  const siteId=params.get('site')||'',runId=params.get('run')||'';
  const {data:analysis,error:analysisError}=useAnalysis(run?.id);
  useEffect(()=>{api('/sites').then(setSites).catch(e=>setError(e.message))},[]);
  useEffect(()=>{let active=true;setRuns([]);setRun(null);if(siteId)api(`/optimization-runs?site_id=${siteId}`).then(r=>{if(active)setRuns(r)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[siteId]);
  useEffect(()=>{let active=true;setRun(null);if(runId)api(`/optimization-runs/${runId}`).then(r=>{if(active&&String(r.site_id)===siteId)setRun(r)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[runId,siteId]);
  const site=sites.find(s=>String(s.id)===siteId);
  async function importLoad(file){if(!file)return;setError('');try{const body=new FormData();body.append('file',file);await api(`/sites/${siteId}/load-profile/import`,{method:'POST',body});setParams({site:siteId});setRun(null);setError('')}catch(e){setError(e.message)}}
  return <><header className="page-head"><div><div className="eyebrow">DATA WORKSPACE</div><h1>Data explorer</h1><p>Choose a site and saved run to inspect, compare and export its hourly records.</p></div></header><ErrorNotice error={error}/><section className="panel data-selectors"><label className="field"><span>Site</span><select aria-label="Dataset site" value={siteId} onChange={e=>setParams({site:e.target.value})}><option value="">Choose a site</option>{sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label className="field"><span>Saved run</span><select aria-label="Dataset run" value={runId} disabled={!siteId} onChange={e=>setParams({site:siteId,run:e.target.value})}><option value="">Choose a saved run</option>{runs.map(r=><option key={r.id} value={r.id}>#{r.id} · {r.scenario_name||r.mode}</option>)}</select></label>{site&&<Link className="secondary" to={`/sites/${site.id}`}>Open site</Link>}</section>{run?<DatasetExplorer run={run} analysis={analysis} error={analysisError}/>:<div className="empty">Select a saved run to see its weather, demand and dispatch.</div>}{site&&<><ForecastModels key={site.id} site={site} user={user}/>{user.role==='admin'&&<details className="panel"><summary>Import the site’s daily demand profile</summary><p>24 consecutive hourly records with columns: timestamp, critical_kw, normal_kw, flexible_kw. Timestamps need a UTC offset. This changes future plans; saved runs remain unchanged.</p><input aria-label="Import load CSV" type="file" accept=".csv" disabled={site.archived} onChange={e=>importLoad(e.target.files[0])}/></details>}</>}</>;
}

export function TeamWorkspace() {
  const [users,setUsers]=useState([]),[error,setError]=useState('');
  useEffect(()=>{api('/team').then(setUsers).catch(e=>setError(e.message))},[]);
  return <><header className="page-head"><div><div className="eyebrow">WORKSPACE ACCESS</div><h1>People & access</h1><p>Admins configure and compare the portfolio. Operators plan, test and review their assigned sites.</p></div></header><ErrorNotice error={error}/><div className="team-grid">{users.map(u=><section className="panel person-card" key={u.id}><div className="person-avatar">{u.name.slice(0,1)}</div><span className="badge">{u.role}</span><h2>{u.name}</h2><p>{u.email}</p>{u.role==='admin'?<p>Access to all organization sites.</p>:u.sites.map(s=><Link className="assignment-link" key={s.id} to={`/sites/${s.id}`}>{s.name}</Link>)}</section>)}</div><p>Site assignments can be edited under Configure site → Location.</p></>;
}
