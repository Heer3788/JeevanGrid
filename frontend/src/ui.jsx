import React, {useLayoutEffect, useId, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Info, ArrowUpRight, X, AlertTriangle,MapPin,ShieldCheck,Clock,HeartPulse,IndianRupee,Fuel,Sun,Activity} from 'lucide-react';

export const number=(v,d=1)=>v==null?'—':(Math.abs(Number(v))<.5/10**d?0:Number(v)).toLocaleString('en-IN',{maximumFractionDigits:d});
export const timestamp=v=>v?new Date(v).toLocaleString('en-IN',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'Not recorded';
export const helpText={
  'Active sites':'Unarchived microgrids accessible to this organization. Open details to see the sites.',
  'Need review':'Sites with missing, outdated or incomplete plans, supply shortages, or reserve risks.',
  'Stress-tested sites':'Sites whose latest plan has all six standard stress checks: cloud, wind, demand, fuel price, outage and low battery.',
  'Decision horizon':'Every plan schedules 24 one-hour intervals. This is a planning window, not a prediction of electrical stability.',
  'Critical energy served':'Percentage of essential energy demand supplied over the plan. 100% means no projected shortage for critical loads.',
  'Dispatch cost':'Fuel cost, generator starts and estimated battery wear over 24 hours. Planning penalties are excluded.',
  'Diesel required':'Litres of fuel needed by the planned generator schedule. Zero is possible when other sources cover demand.',
  'Renewable generation':'Used solar and wind divided by solar, wind and diesel generation. Battery discharge is not counted twice.',
};

export function Metric({label,value,unit,help,children,icon:Icon}) {
  const [open,setOpen]=useState(false), id=useId();
  const description=help||helpText[label]||`${label} for the selected plan and site.`;
  const Symbol=Icon||({'Active sites':MapPin,'Need review':AlertTriangle,'Stress-tested sites':ShieldCheck,'Decision horizon':Clock,'Critical energy served':HeartPulse,'Dispatch cost':IndianRupee,'Diesel required':Fuel,'Renewable generation':Sun}[label])||Activity;
  return <><div className="stat metric">
    <button type="button" className="metric-toggle" aria-haspopup="dialog" aria-describedby={id+'-tip'} onClick={()=>setOpen(true)}>
      <span className="metric-label"><span className="metric-symbol"><Symbol size={18} aria-hidden="true"/></span>{label}<Info size={14} aria-hidden="true"/></span>
      <strong>{value}<small>{unit}</small></strong><span className="metric-more">View details <ArrowUpRight size={13}/></span>
      <span role="tooltip" id={id+'-tip'} className="metric-tooltip">{description}</span>
    </button>
  </div>{open&&createPortal(<Dialog title={label} className="metric-dialog" onClose={()=>setOpen(false)}>
    <div className="metric-dialog-value"><span className="metric-symbol"><Symbol size={23} aria-hidden="true"/></span><strong>{value}<small>{unit}</small></strong></div>
    <p>{description}</p>
    {children&&<div className="metric-dialog-details">{children}</div>}
  </Dialog>,document.body)}</>;
}

export function Dialog({title,children,onClose,className=''}) {
  const ref=useRef(), id=useId();
  useLayoutEffect(()=>{
    const node=ref.current,trigger=document.activeElement;
    node.showModal();
    return()=>{
      node.close();
      if(trigger instanceof HTMLElement&&trigger.isConnected)trigger.focus({preventScroll:true});
    };
  },[]);
  function keepFocus(event) {
    if(event.key!=='Tab')return;
    const controls=[...ref.current.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
      .filter(node=>!node.matches(':disabled')&&node.tabIndex>=0&&node.getClientRects().length);
    const first=controls[0],last=controls.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }
  return <dialog ref={ref} className={'workspace-dialog '+className} aria-labelledby={id} onCancel={onClose} onKeyDown={keepFocus} onClick={e=>{if(e.target===ref.current)onClose()}}>
    <div className="dialog-heading"><h2 id={id}>{title}</h2><button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}><X/></button></div>
    <div className="dialog-content">{children}</div>
  </dialog>;
}

export function ErrorNotice({error}) {return error?<div className="error" role="alert"><AlertTriangle size={17}/>{error}</div>:null}
export function Input({label,value,onChange,type='number',...props}) {
  return <label className="field"><span>{label}</span><input aria-label={label} type={type} value={value??''} onChange={e=>onChange(type==='number'?(e.target.value===''?'':Number(e.target.value)):e.target.value)} {...props}/></label>;
}
