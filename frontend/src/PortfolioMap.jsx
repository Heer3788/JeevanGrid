import React,{useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight,MapPin,Maximize2} from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import land from './data/land.json';
import {fmt,ReliabilityBadge} from './Intelligence';

export default function PortfolioMap({sites}) {
  const node=useRef(null),map=useRef(null),markers=useRef(new Map());
  const [selected,setSelected]=useState(null);
  const valid=sites.filter(s=>Number.isFinite(s.latitude)&&Number.isFinite(s.longitude));
  const active=valid.find(s=>s.id===selected)||valid[0];
  useEffect(()=>{
    if(!node.current)return;
    // Bundled coastlines: panning and zooming never disclose site locations.
    const instance=L.map(node.current,{scrollWheelZoom:false,minZoom:3,maxZoom:10}).setView([23.2,82],4);
    map.current=instance;
    L.geoJSON(land,{interactive:false,style:{color:'#a6c3c5',weight:.8,fillColor:'#f7faf8',fillOpacity:1}}).addTo(instance);
    for(let lat=0;lat<=50;lat+=5)L.polyline([[lat,50],[lat,115]],{color:'#b1cdce',weight:.5,opacity:.3,interactive:false}).addTo(instance);
    for(let lon=55;lon<=110;lon+=5)L.polyline([[-5,lon],[50,lon]],{color:'#b1cdce',weight:.5,opacity:.3,interactive:false}).addTo(instance);
    [['New Delhi',28.61,77.21],['Mumbai',19.08,72.88],['Kolkata',22.57,88.36],['Chennai',13.08,80.27],['Guwahati',26.14,91.74]].forEach(([name,lat,lon])=>{
      L.circleMarker([lat,lon],{radius:2,color:'#729aa4',weight:1,interactive:false}).addTo(instance).bindTooltip(name,{permanent:true,direction:'right',className:'map-place-label'});
    });
    instance.attributionControl.addAttribution('<a href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth</a> · offline coastlines');
    const observer=new ResizeObserver(()=>instance.invalidateSize());observer.observe(node.current);
    return()=>{observer.disconnect();instance.remove();map.current=null;};
  },[]);
  useEffect(()=>{
    if(!map.current)return;
    const groups=new Map(),layer=L.layerGroup().addTo(map.current);
    markers.current.clear();
    valid.forEach(s=>{const key=s.latitude+','+s.longitude;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(s);});
    groups.forEach(group=>{
      const worst=group.some(s=>s.reliability_status==='red')?'red':group.some(s=>s.reliability_status==='amber')?'amber':'green';
      const marker=L.marker([group[0].latitude,group[0].longitude],{
        title:group.map(s=>s.name).join(' · '),keyboard:true,
        icon:L.divIcon({className:'site-marker '+worst,html:'<span>'+group.length+'</span>',iconSize:[32,32],iconAnchor:[16,16]})
      }).addTo(layer);
      const popup=document.createElement('div');
      group.forEach(s=>{
        const button=document.createElement('button');
        button.type='button';button.className='map-popup-site';button.textContent=s.name;
        button.addEventListener('click',()=>setSelected(s.id));popup.appendChild(button);markers.current.set(s.id,marker);
      });
      marker.bindPopup(popup).on('click',()=>setSelected(group[0].id));
    });
    return()=>layer.remove();
  },[sites]);
  function select(s){setSelected(s.id);map.current?.setView([s.latitude,s.longitude],6,{animate:false});markers.current.get(s.id)?.openPopup();}
  function overview(){map.current?.closePopup();map.current?.setView([23.2,82],4,{animate:false});}
  const m=active?.latest_run?.metrics||{};
  return <section className="panel portfolio-map-panel"><div className="section-heading"><div><h2>Network locations</h2><p>Select a location to review supply and the next decision.</p></div><button className="secondary" onClick={overview}><Maximize2 size={14}/>India overview</button></div>
    <div className="map-layout"><div className="map-canvas-wrap"><div ref={node} className="portfolio-map" aria-label="Microgrid site locations"/>
      <div className="map-caption"><span><span className="map-key green"/> Reliable</span><span><span className="map-key amber"/> Review</span><span><span className="map-key red"/> At risk</span><small>Number = sites at that coordinate</small></div>
    </div><div className="map-inspector">
      <label className="field"><span>Inspect site</span><select aria-label="Inspect map site" value={active?.id||''} onChange={e=>{const s=valid.find(s=>s.id===Number(e.target.value));if(s)select(s)}}>{valid.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      {active?<><ReliabilityBadge status={active.reliability_status}/><h3>{active.name}</h3><p><MapPin size={13}/> {active.district}, {active.state}<br/>{active.latitude.toFixed(4)}, {active.longitude.toFixed(4)}</p>
      <div className="summary-row"><span>Critical energy served</span><b>{fmt(m.critical_load_served_pct)}%</b></div><div className="summary-row"><span>Renewable generation</span><b>{fmt(m.renewable_share_pct)}%</b></div>
      <div className="summary-row"><span>Expected shortage</span><b>{fmt(m.unserved_kwh)} kWh</b></div><div className="summary-row"><span>Weather retrieved</span><b>{active.latest_run?.weather_retrieved_at?fmt(Math.max(0,(Date.now()-new Date(active.latest_run.weather_retrieved_at))/3600000))+'h ago':'No run'}</b></div>
      <p className="map-action">{active.latest_run?.next_action?.reason||'Create a plan to assess this site.'}</p><Link className="primary" to={'/sites/'+active.id}>Open site <ArrowUpRight size={15}/></Link></>:<p>Add a site with valid coordinates to see it on the map.</p>}
    </div></div><small>Offline regional coastlines, without administrative boundaries. Demo sites can share approximate coordinates. Locations stay in your browser.</small>
  </section>;
}
