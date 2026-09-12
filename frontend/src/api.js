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
