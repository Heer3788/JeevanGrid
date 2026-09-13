let access = sessionStorage.getItem('jg-access');
let refresh = sessionStorage.getItem('jg-refresh');
let refreshing;
export function tokens(value) {
  access=value?.access; refresh=value?.refresh;
  if (value) {sessionStorage.setItem('jg-access',access); sessionStorage.setItem('jg-refresh',refresh);}
  else {sessionStorage.removeItem('jg-access'); sessionStorage.removeItem('jg-refresh');}
}
export const hasSession=()=>!!refresh;
export const refreshToken=()=>refresh;
export const accessToken=()=>access;
export async function downloadDataset(siteId) {
  await api('/auth/me');
  const res=await fetch(`/api/sites/${siteId}/forecast-model/dataset`,{headers:{Authorization:`Bearer ${access}`}});
  if(!res.ok)throw Error('Could not download training data.');
  const url=URL.createObjectURL(await res.blob());const a=document.createElement('a');
  a.href=url;a.download=`site-${siteId}-training.csv`;a.click();URL.revokeObjectURL(url);
}
function message(body) {
  if (typeof body==='string') return body;
  if (Array.isArray(body)) return body.map(message).join(' ');
  return Object.entries(body||{}).map(([k,v])=>`${k==='detail'?'':k+': '}${message(v)}`).join(' ');
}
export async function api(path, options={}, retry=true) {
  const form=options.body instanceof FormData;
  const res=await fetch('/api'+path,{...options,headers:{...(!form?{'Content-Type':'application/json'}:{}),...(access?{'Authorization':`Bearer ${access}`}:{})},body:options.body ? form?options.body:JSON.stringify(options.body):undefined});
  if(res.status===401 && retry && refresh && path!='/auth/login') {
    if(!refreshing) refreshing=fetch('/api/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh})}).then(async r=>{if(!r.ok) throw Error('Session expired. Please sign in.');tokens(await r.json());}).catch(e=>{tokens(null);window.dispatchEvent(new Event('session-expired'));throw e;}).finally(()=>{refreshing=null;});
    await refreshing; return api(path,options,false);
  }
  const body=await res.json().catch(()=>({detail:`Request failed (${res.status}).`}));
  if(!res.ok) throw Error(message(body));
  return body;
}

export async function downloadArtifact(id,name='jeevangrid-report.pdf') {
  await api('/auth/me');
  const response=await fetch(`/api/reports/${id}/download`,{headers:{Authorization:`Bearer ${access}`}});
  if(!response.ok)throw Error('Report is unavailable or access has changed.');
  const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');
  a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
