import React,{useEffect,useState} from 'react';
import {Play,Pause} from 'lucide-react';
import {api,accessToken} from './api';
import {ErrorNotice,number as n} from './ui';
import {hour} from './PlanCharts';

import ReplayChart from './ReplayChart';
import ExportMenu from './Reports';

export default function LiveControl({site,baseline}) {
  const [data,setData]=useState(null),[connection,setConnection]=useState('Connecting'),[busy,setBusy]=useState(''),[error,setError]=useState(''),[reason,setReason]=useState('');
  const [speed,setSpeed]=useState(10),[chart,setChart]=useState('supply');
  useEffect(()=>{
    let active=true,socket,timer;
    async function connect(){try{
      const value=await api(`/sites/${site.id}/live`);if(!active)return;setData(value);
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/sites/${site.id}/live`);
      socket.onopen=()=>socket.send(JSON.stringify({access:accessToken()}));
      socket.onmessage=e=>{if(active){setData(JSON.parse(e.data));setConnection('Connected')}};
      socket.onclose=()=>{if(active){setConnection('Reconnecting');timer=setTimeout(connect,3000)}};
      socket.onerror=()=>socket.close();
    }catch(e){if(active){setError(e.message);timer=setTimeout(connect,5000)}}}
    connect();return()=>{active=false;clearTimeout(timer);socket?.close()};
  },[site.id]);
  const latest=data?.session,session=latest?.baseline_id===baseline.id?latest:null,t=session?.telemetry;
  const pending=session?.commands.find(c=>c.status==='proposed'),run=session?.run;
  async function post(path,body){return api(`/sites/${site.id}${path}`,{method:'POST',body})}
  async function task(name,fn){setBusy(name);setError('');try{await fn();setData(await api(`/sites/${site.id}/live`))}catch(e){setError(e.message)}finally{setBusy('')}}
  const start=()=>task('session',()=>post('/live',latest?.active?{action:'pause'}:{action:'start',baseline_id:baseline.id,options:{speed,strategy:baseline.snapshot.strategy||'lowest_cost',use_ml:false,conservative:false,carbon_price_inr_per_kg:baseline.snapshot.carbon_price_inr_per_kg||0}}));

  return <div className="live-replay"><section className="panel replay-controls"><div><div className="eyebrow">SIMULATED PLAN REPLAY</div><h2>Watch plan #{baseline.id} respond</h2><p>Starts with this plan’s weather, demand and readings. Change conditions, inspect a new proposal, then approve it in the simulator.</p></div><div className="actions"><label className="source-field">Clock speed<select aria-label="Clock speed" disabled={latest?.active} value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={10}>10× · 5 min in 30 sec</option><option value={30}>30× · 5 min in 10 sec</option><option value={120}>120× · fast replay</option></select></label><button className="primary" disabled={!!busy||site.archived||!['optimal','feasible'].includes(baseline.status)} onClick={start}>{latest?.active?<Pause size={16}/>:<Play size={16}/>} {busy==='session'?'Updating…':latest?.active?'Pause replay':'Start replay'}</button></div></section>
    <ErrorNotice error={error}/>{latest&&!session&&<p className="notice amber">{latest.active?'A replay from another plan is running. Pause it before starting this plan.':'Start to replay this plan; earlier session evidence stays saved.'}</p>}
    {session&&<><div className="replay-status"><span><i className={session.active?'live-dot':''}/>{session.active?'Running':'Paused'} · {hour(session.simulated_at,site.timezone)} · {session.options.speed}×</span><span>{connection}{session.stale&&session.active?' · Readings delayed':''}</span></div>
      <div className="replay-events">{[['cloud','Cloud cover'],['high_demand','Demand +50%'],['low_battery','Battery at 25%'],['generator_outage','Generator outage'],['restore','Restore weather & generator']].map(([event,label])=><button key={event} className="secondary" disabled={!!busy||!session.active||session.stale} onClick={()=>task(event,()=>post('/live/events',{event}))}>{label}</button>)}</div>
      <div className="modifier-chips"><span>Solar {n((session.modifiers?.solar_multiplier??1)*100)}%</span><span>Demand {n(session.modifiers?.demand_multiplier??session.modifiers?.event_demand_multiplier??1)}×</span><span>Generator {session.modifiers?.generator_available?'available':'unavailable'}</span><span>{n(session.flexible_remaining_kwh)} kWh flexible work unfinished</span></div>{session.history_complete===false&&<p className="notice amber">Legacy replay: some older events or intervals were not retained. Reports identify this gap.</p>}
      {t&&<section className="panel"><div className="section-heading"><div><h2>Is demand being supplied?</h2><p>Observed in this software simulation. Diesel {n(t.generator_kw)} kW · solar {n(t.solar_kw)} kW · wind {n(t.wind_kw)} kW.</p></div><div className="segmented"><button aria-pressed={chart==='supply'} onClick={()=>setChart('supply')}>Supply</button><button aria-pressed={chart==='battery'} onClick={()=>setChart('battery')}>Battery</button></div></div><ReplayChart session={session} baseline={baseline} chart={chart} tz={site.timezone}/><div className="hour-facts"><span><b>{n(t.served_kw)}/{n(t.demand_kw)} kW</b> supplied / requested</span><span><b>{n(t.soc_pct)}%</b> battery</span><span><b>{n(session.evidence.diesel_litres)} L</b> diesel used so far</span><span><b>{n(session.evidence.critical_unserved_kwh,3)} kWh</b> critical shortage so far</span></div></section>}
      <section className="panel replay-decision"><div><div className="eyebrow">REVIEW THE RESPONSE</div><h2>{pending?`Command #${pending.id} needs approval`:'No command awaiting review'}</h2>{pending?<><p>{pending.proposal.generator_on?`Run diesel at ${n(pending.proposal.generator_kw)} kW.`:'Keep diesel off.'} Battery setpoint: {n(pending.proposal.planned_battery_kw)} kW (positive = discharge).</p><label className="field"><span>Review reason</span><input aria-label="Command review reason" placeholder="Required for rejection" value={reason} onChange={e=>setReason(e.target.value)} maxLength={500}/></label><div className="actions"><button className="primary" disabled={!!busy||session.stale||!session.active} onClick={()=>task('approve',()=>post(`/live/commands/${pending.id}`,{decision:'approve',reason}))}>Approve simulated command</button><button className="secondary" disabled={!!busy||!reason.trim()||session.stale||!session.active} onClick={()=>task('reject',()=>post(`/live/commands/${pending.id}`,{decision:'reject',reason}))}>Reject</button></div></>:<p>Approved commands run on the next tick. Verified checks simulated generator output and power balance; the battery balances automatically.</p>}</div>{run&&<div className="replay-diffs"><h3>Original day → latest rolling plan</h3><p className="small">The new horizon starts at {hour(run.horizon_start,site.timezone)}. These are updated projections, not elapsed savings.</p>{[['diesel_litres','Diesel','L'],['critical_load_served_pct','Critical served','%'],['minimum_soc_pct','Min battery','%']].map(([k,l,u])=><div className="summary-row" key={k}><span>{l}</span><b>{n(baseline.metrics[k])} → {n(run.metrics[k])} {u}</b></div>)}{run.diagnostics?.map((d,i)=><p className="notice amber" key={i}>{d}</p>)}</div>}</section>
      <details className="panel"><summary>Command history & evidence ({session.evidence.verified_commands} verified)</summary>{session.commands.map(c=><div className="summary-row" key={c.id}><span>Command #{c.id} · diesel {n(c.proposal.generator_kw)} kW</span><b>{c.status}</b></div>)}{[...session.events].reverse().slice(0,8).map((e,i)=><p key={i}>{hour(e.time,site.timezone)} · {e.message}</p>)}<ExportMenu label="Export replay evidence" selection={{kind:"replay",session_id:session.id}}/></details>
    </>}
  </div>;
}
