import React,{useState} from 'react';
import {PieChart,Pie,Cell,ResponsiveContainer,Tooltip} from 'recharts';
import {Battery,Sun,Wind,Fuel} from 'lucide-react';
import {number as n} from './ui';
import {colors} from './chartTheme';

const clamp=v=>Math.min(100,Math.max(0,Number(v)||0));
export function EnergyRing({items,unit,label}) {
  const [active,setActive]=useState(null);
  const total=items.reduce((sum,r)=>sum+Math.max(0,r.value||0),0);
  const selected=items.find(r=>r.name===active);
  return <div className="energy-ring-layout">
    <div className="energy-ring" role="img" aria-label={`${label}: ${items.map(r=>`${r.name} ${n(r.value)} ${unit}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={total?items:[{name:'No capacity',value:1,color:colors.grid}]} dataKey="value" nameKey="name" innerRadius="72%" outerRadius="94%" startAngle={90} endAngle={-270} paddingAngle={total?3:0} stroke="none" onMouseEnter={r=>setActive(r.name)} onMouseLeave={()=>setActive(null)} isAnimationActive={false}>{(total?items:[{name:'No capacity',color:colors.grid}]).map(r=><Cell key={r.name} fill={r.color} opacity={selected&&selected.name!==r.name?0.45:1}/>)}</Pie><Tooltip formatter={v=>`${n(v)} ${unit}`}/></PieChart></ResponsiveContainer>
      <div className="ring-center" aria-hidden="true"><small>{selected?selected.name:label}</small><strong>{n(selected?selected.value:total,0)}</strong><span>{unit}</span></div>
    </div>
    <div className="ring-legend">{items.map(r=><button type="button" key={r.name} aria-pressed={active===r.name} onClick={()=>setActive(r.name)} onFocus={()=>setActive(r.name)} onBlur={()=>setActive(null)}><i style={{background:r.color}}/><span>{r.name}<small>{total?n(100*r.value/total,1):'0'}% of total</small></span><b>{n(r.value)}<small>{unit}</small></b></button>)}</div>
  </div>;
}

export function EquipmentOverview({configuration,run}) {
  const [view,setView]=useState('capacity');
  if(!configuration)return null;
  const energy=view==='energy'&&run?.intervals?.length;
  const c=energy?run.snapshot.configuration:configuration;
  // Intervals are one hour. kW × 1 hour gives kWh; storage is not generation.
  const items=[['Solar',c.solar.capacity_kw,'solar_used',colors.solar],['Wind',c.wind.capacity_kw,'wind_used',colors.wind],['Diesel',c.generator.capacity_kw,'diesel_power',colors.diesel]].map(([name,value,key,color])=>({name,color,value:energy?run.intervals.reduce((s,r)=>s+Math.max(0,r[key]||0),0):value}));
  const b=c.battery,initial=energy?run.snapshot.state.soc_pct:null;
  const stored=initial==null?null:b.capacity_kwh*initial/100;
  const usable=b.capacity_kwh*Math.max(0,b.max_soc-b.min_soc)/100;
  const icons={Solar:Sun,Wind:Wind,Diesel:Fuel};
  return <div className="equipment-overview">
    <div className="equipment-mix"><div className="section-heading"><div><div className="eyebrow">GENERATION MIX</div><h2>{energy?'Energy in this plan':'Installed power'}</h2></div>{run?.intervals?.length>0&&<div className="segmented"><button type="button" aria-pressed={!energy} onClick={()=>setView('capacity')}>Capacity</button><button type="button" aria-pressed={!!energy} onClick={()=>setView('energy')}>24-hour energy</button></div>}</div><EnergyRing items={items} unit={energy?'kWh':'kW'} label={energy?'Used generation':'Total capacity'}/><p className="chart-caption">{energy?'Used solar + wind + diesel across 24 hourly intervals. Battery discharge transfers stored energy and is excluded from this generation total.':'Nameplate power by source. This shows installed equipment, not how much energy it will produce.'}</p></div>
    <div className="storage-visual"><div className="storage-heading"><span className="source-icon"><Battery size={21}/></span><div><small>ENERGY STORAGE</small><h3>Battery capacity</h3></div></div><div className="storage-value">{n(b.capacity_kwh,0)}<span>kWh</span></div><div className="battery-vessel" role="img" aria-label={`Battery capacity ${n(b.capacity_kwh)} kWh. Safe operating range ${b.min_soc} to ${b.max_soc} percent.${initial!=null?` Starting charge ${initial} percent.`:''}`}><div className="battery-safe" style={{left:`${clamp(b.min_soc)}%`,width:`${clamp(b.max_soc)-clamp(b.min_soc)}%`}}/><div className="battery-fill" style={{width:`${clamp(initial??0)}%`}}/>{[b.min_soc,b.reserve_soc,b.max_soc].map((v,i)=><i key={i} style={{left:`${clamp(v)}%`}}/>)}</div><div className="battery-scale"><span>0%</span><span>Reserve {b.reserve_soc}%</span><span>100%</span></div><div className="storage-details"><div><span>Usable operating window</span><b>{n(usable)} kWh</b></div><div><span>{stored==null?'Maximum discharge power':'Stored at plan start'}</span><b>{stored==null?`${n(b.max_discharge_kw)} kW`:`${n(stored)} kWh · ${n(initial)}%`}</b></div></div><p>Storage capacity is measured in kWh. It stays separate from the generation capacity chart.</p></div>
    <div className="equipment-specs">{items.map(r=>{const Icon=icons[r.name];return <div key={r.name}><Icon size={17} style={{color:r.color}}/><span>{r.name}</span><b>{n(r.name==='Solar'?c.solar.capacity_kw:r.name==='Wind'?c.wind.capacity_kw:c.generator.capacity_kw)} kW</b><small>{r.name==='Solar'?`${c.solar.tilt}° tilt · ${c.solar.azimuth}° azimuth`:r.name==='Wind'?`${c.wind.hub_height_m} m hub · ${c.wind.rated_speed} m/s rated`:`${c.generator.min_power_kw} kW minimum · INR ${c.generator.diesel_price}/L`}</small></div>})}</div>
  </div>;
}

export function DemandMix({demand:d}) {
  return <div className="demand-visual"><div><span className="eyebrow">DAILY ENERGY BUDGET</span><h2>{n(d.daily_kwh)} <small>kWh / day</small></h2><p>{n(d.peak_kw)} kW reference peak</p></div><div className="demand-distribution"><div className="balance-bar">{[[d.critical_pct,colors.critical],[100-d.critical_pct-d.flexible_pct,colors.wind],[d.flexible_pct,colors.battery]].map(([v,c],i)=><span key={i} style={{width:`${clamp(v)}%`,background:c}}/>)}</div><div className="demand-labels">{[['Critical',d.critical_pct,colors.critical],['Normal',100-d.critical_pct-d.flexible_pct,colors.wind],['Flexible',d.flexible_pct,colors.battery]].map(([l,v,c])=><span key={l}><i style={{background:c}}/>{l}<b>{n(d.daily_kwh*v/100)} kWh</b></span>)}</div></div></div>;
}
