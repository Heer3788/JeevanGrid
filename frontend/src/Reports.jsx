import React,{useEffect,useRef,useState} from 'react';
import {Download,LoaderCircle} from 'lucide-react';
import {api,downloadArtifact} from './api';
import {ErrorNotice} from './ui';
export default function ExportMenu({selection,label='Export report'}) {
 const [format,setFormat]=useState('pdf'),[job,setJob]=useState(null),[basis,setBasis]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),mounted=useRef(true);
 useEffect(()=>()=>{mounted.current=false},[]);
 useEffect(()=>{setJob(null);setBasis(null)},[JSON.stringify(selection)]);
 useEffect(()=>{if(!job||job.status!=='queued')return;let active=true;const timer=setTimeout(()=>api(`/reports/${job.id}`).then(d=>{if(active)setJob(d)}).catch(e=>{if(active)setError(e.message)}),2000);return()=>{active=false;clearTimeout(timer)}},[job]);
 async function create(){setBusy(true);setError('');try{const d=await api('/reports',{method:'POST',body:{...selection,format,...(basis?{source_artifact_id:basis}:{})}});if(mounted.current){setJob(d);setBasis(id=>id||d.id)}}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <div className="export-menu"><div className="actions"><select aria-label="Report format" value={format} onChange={e=>{setFormat(e.target.value);setJob(null)}} disabled={busy||job?.status==='queued'}><option value="pdf">PDF report</option><option value="csv">CSV + evidence (ZIP)</option><option value="json">JSON evidence</option></select>{job?.status==='ready'?<button className="primary" onClick={()=>downloadArtifact(job.id,job.name).catch(e=>setError(e.message))}><Download size={16}/>Download {job.format.toUpperCase()}</button>:<button className="secondary" disabled={busy||job?.status==='queued'} onClick={create}>{busy||job?.status==='queued'?<LoaderCircle size={16} className="spin"/>:<Download size={16}/>} {busy?'Freezing evidence…':job?.status==='queued'?'Preparing report…':label}</button>}</div>{job?.status==='ready'&&<small>Saved evidence snapshot · report #{job.id}</small>}{job?.status==='failed'&&<ErrorNotice error="Report generation failed. Its source evidence remains saved."/>}<ErrorNotice error={error}/></div>;
}
