import React,{useMemo} from 'react';
import {ResponsiveContainer,ComposedChart,Area,Line,XAxis,YAxis,Tooltip,CartesianGrid,ReferenceLine} from 'recharts';
import {number as n} from './ui';
import {ChartKey,hour,colors} from './PlanCharts';
export function intervalPoints(samples,battery=false) {
 if(battery)return samples.map(r=>({...r,time:new Date(r.timestamp).getTime()}));
 const data=samples.map(r=>({...r,time:new Date(r.interval_start||r.timestamp).getTime(),shortage:[r.served_kw,r.demand_kw]}));
 const last=samples.at(-1);if(last)data.push({...data.at(-1),time:new Date(last.timestamp).getTime()});
 return data;
}
export default function ReplayChart({session,baseline,chart,tz}) {
 const data=useMemo(()=>{
  const points=intervalPoints(session.samples,chart==='battery');
  if(chart==='battery')for(const event of session.event_records||[]){const time=new Date(event.timestamp).getTime();if(event.kind==='low_battery'&&time>=new Date(session.samples[0]?.interval_start).getTime()&&time<=points.at(-1)?.time){points.push({time,soc_pct:event.data.before.soc_pct},{time,soc_pct:event.data.after.soc_pct})}}
  return points.sort((a,b)=>a.time-b.time);
 },[session.samples,session.event_records,chart]);
 const events=(session.event_records||[]).filter(e=>new Date(e.timestamp).getTime()>=data[0]?.time&&new Date(e.timestamp).getTime()<=data.at(-1)?.time);
 const shortWindow=(data.at(-1)?.time-data[0]?.time)<300000;
 const timeLabel=value=>shortWindow?new Date(value).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZone:tz}):hour(value,tz);
 const markers=Object.entries(events.slice(-12).reduce((groups,event,index)=>{const time=new Date(event.timestamp).getTime();(groups[time]??=[]).push(index+1);return groups},{}));
 return <><ChartKey items={chart==='supply'?[['Demand',colors.demand],['Supplied',colors.battery],['Shortage','#d17a64']]:[['Stored energy',colors.battery]]}/><div className="readable-chart compact"><ResponsiveContainer><ComposedChart data={data}><CartesianGrid vertical={false} stroke="#e7eef0"/><XAxis dataKey="time" type="number" domain={['dataMin','dataMax']} tickFormatter={timeLabel} minTickGap={55}/><YAxis domain={chart==='battery'?[0,100]:[0,'auto']}/><Tooltip labelFormatter={timeLabel} formatter={(v,name)=>[Array.isArray(v)?`${n(v[1]-v[0])} kW`:`${n(v)}${chart==='battery'?'%':' kW'}`,name]}/>{chart==='supply'?<><Area type="stepAfter" dataKey="shortage" name="Unserved power" stroke="none" fill="#d17a64" fillOpacity={.16} isAnimationActive={false}/><Line type="stepAfter" dataKey="demand_kw" name="Demand" stroke={colors.demand} strokeWidth={2} dot={false} isAnimationActive={false}/><Line type="stepAfter" dataKey="served_kw" name="Supplied" stroke={colors.battery} strokeWidth={2.5} dot={false} strokeDasharray="5 3" isAnimationActive={false}/></>:<><Line type="linear" dataKey="soc_pct" name="Battery SOC" stroke={colors.battery} strokeWidth={2.5} dot={false} isAnimationActive={false}/><ReferenceLine y={baseline.snapshot.configuration.battery.reserve_soc} stroke={colors.reserve} strokeDasharray="4 4"/></>}{markers.map(([time,numbers])=><ReferenceLine key={time} x={Number(time)} stroke="#7c8e94" strokeDasharray="2 5" label={{value:numbers.join(', '),position:'insideTopRight',fill:'#61747c',fontSize:11}}/>)}</ComposedChart></ResponsiveContainer></div><p className="chart-caption">{chart==='supply'?'Power is held across each recorded interval; shaded gaps are unsupplied demand.':'Battery readings are recorded at each interval’s end.'} Showing {session.samples.length} of {session.sample_count||session.samples.length} intervals. Reports include the full saved history.</p>{events.length>0&&<details className="replay-event-key"><summary>Events on this chart</summary><ol>{events.slice(-12).map(e=><li key={e.id}>{timeLabel(e.timestamp)} · {e.message}</li>)}</ol></details>}</>;
}
