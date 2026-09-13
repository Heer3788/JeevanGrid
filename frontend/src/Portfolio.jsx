import React,{lazy,Suspense,useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {Plus,RefreshCw,ArrowUpRight} from 'lucide-react';
import {api} from './api';
import {Metric,ErrorNotice,number as n,timestamp} from './ui';
import {ReliabilityBadge} from './Intelligence';
import ComparisonWindow from './ComparisonWindow';
const PortfolioMap=lazy(()=>import('./PortfolioMap'));

export default function Portfolio() {
  const [data,setData]=useState(null),[error,setError]=useState(''),[filter,setFilter]=useState('all'),[selected,setSelected]=useState([]),[busy,setBusy]=useState(false),[comparisonOpen,setComparisonOpen]=useState(false);
  useEffect(()=>{let active=true,timer;async function poll(){try{const d=await api('/portfolio/reliability');if(active){setData(d);timer=setTimeout(poll,10000)}}catch(e){if(active)setError(e.message)}}poll();return()=>{active=false;clearTimeout(timer)}},[]);
  async function refresh(){setBusy(true);try{setData(await api('/portfolio/reliability'));setError('')}catch(e){setError(e.message)}finally{setBusy(false)}}
  if(!data)return <><ErrorNotice error={error}/><div className="loading">Loading portfolio…</div></>;
  const sites=data.sites,risks=sites.filter(s=>s.reliability_status!=='green'),tested=sites.filter(s=>s.stress_tested);
  const shown=filter==='review'?risks:filter==='tested'?tested:sites;
  const links=list=><div className="metric-links">{list.map(s=><Link key={s.id} to={`/sites/${s.id}`}>{s.name}<ArrowUpRight size={12}/></Link>)}</div>;
  const compare=sites.filter(s=>selected.includes(s.id));

  return <><header className="page-head portfolio-hero"><div><div className="eyebrow">YOUR ENERGY NETWORK</div><h1>Portfolio overview</h1><p>A clear view of your network. A better next decision.</p></div><div className="actions"><button className="secondary" onClick={refresh} disabled={busy}><RefreshCw size={16}/>Refresh overview</button><Link className="primary" to="/sites/new"><Plus size={16}/>Add site</Link></div></header><ErrorNotice error={error}/>
    <div className="stats"><Metric label="Active sites" value={sites.length}>{links(sites)}</Metric><Metric label="Need review" value={risks.length}>{links(risks)}</Metric><Metric label="Stress-tested sites" value={tested.length}>{links(tested)}</Metric><Metric label="Decision horizon" value="24" unit="hours"><p>Solar, wind, battery and diesel are scheduled hourly. Each site has its own dated plan; compare matching horizons.</p></Metric></div>
    <Suspense fallback={<div className="loading">Loading site map…</div>}><PortfolioMap sites={sites}/></Suspense>
    <section className="panel"><div className="section-heading"><div><h2>Site reliability</h2><p>Standard stress checks run automatically after planning. Select 2–5 sites for comparison.</p></div><div className="segmented">{[['all','All sites'],['review','Need review'],['tested','Checked']].map(([k,l])=><button key={k} aria-pressed={filter===k} onClick={()=>setFilter(k)}>{l}</button>)}</div></div><div className="table-scroll"><table><thead><tr><th>Select</th><th>Site</th><th>Assessment</th><th title="Essential energy demand supplied over the next plan">Critical served</th><th title="Solar and wind share of used generation">Renewable</th><th title="Generator fuel over 24 hours">Diesel (L)</th><th title="Dispatch cost divided by energy supplied">INR/kWh</th></tr></thead><tbody>{shown.map(s=><tr key={s.id}><td><input type="checkbox" aria-label={`Compare ${s.name}`} checked={selected.includes(s.id)} disabled={!selected.includes(s.id)&&selected.length===5} onChange={e=>setSelected(e.target.checked?[...selected,s.id]:selected.filter(id=>id!==s.id))}/></td><td><Link className="site-link" to={`/sites/${s.id}`}>{s.name}<ArrowUpRight size={14}/></Link><small>{s.district}, {s.state}</small></td><td><ReliabilityBadge status={s.reliability_status}/><small className="assessment">{s.assessment}</small></td><td>{n(s.latest_run?.metrics.critical_load_served_pct)}%</td><td><div className="table-meter"><b>{n(s.latest_run?.metrics.renewable_share_pct)}%</b><span><i style={{width:`${Math.max(0,Math.min(100,s.latest_run?.metrics.renewable_share_pct||0))}%`}}/></span></div></td><td>{n(s.latest_run?.metrics.diesel_litres)}</td><td>{n(s.latest_run?.metrics.cost_per_kwh,2)}</td></tr>)}</tbody></table></div>{!shown.length&&<p className="empty">No sites match this filter.</p>}</section>
    {compare.length>=2&&<section className="panel comparison-launch"><div><h2>{compare.length} sites selected</h2><p>Compare service, fuel, cost, emissions and battery reserve.</p></div><button className="primary" onClick={()=>setComparisonOpen(true)}>Open detailed comparison <ArrowUpRight size={16}/></button></section>}
    {comparisonOpen&&<ComparisonWindow siteIds={selected} onClose={()=>setComparisonOpen(false)}/>}

  </>;
}
