import React,{useEffect,useRef,useState} from 'react';
import {ArrowRight,ShieldCheck,UserRound} from 'lucide-react';
import {api,tokens} from './api';
import {ErrorNotice,Input} from './ui';
import Brand from './Brand';

export default function Login({onLogin}) {
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState(''),[accounts,setAccounts]=useState([]);
  const form=useRef(null);
  useEffect(()=>{let active=true;api('/auth/demo-accounts').then(r=>{if(active)setAccounts(r)}).catch(()=>{});return()=>{active=false}},[]);
  async function signIn(accountEmail,accountPassword){if(busy)return;setBusy(accountEmail);setError('');try{const d=await api('/auth/login',{method:'POST',body:{email:accountEmail,password:accountPassword}});tokens(d);onLogin(d.user)}catch(e){setError(e.message)}finally{setBusy('')}}
  function demo(a){setEmail(a.email);if(a.quick_login)signIn(a.email,'JeevanGridDemo!26');else{setPassword('');setError('This account uses a custom password. Enter it above.');form.current?.querySelector('input[type="password"]')?.focus()}}
  return <div className="login">
    <aside className="login-story">
      <div className="brand"><Brand/></div>
      <img className="login-photo" src="/solar-farm.jpg" alt="Aerial view of solar arrays surrounded by green fields"/>
      <div className="login-intro"><div className="login-tag"><span/> ENERGY, IN BALANCE</div><h1>A brighter grid.<br/><em>A clearer plan.</em></h1><p>Turn renewable potential into dependable power for your communities.</p></div>
      <div className="login-process"><span><b>01</b>Plan your energy</span><span><b>02</b>Test the conditions</span><span><b>03</b>Review with confidence</span></div>
      <div className="login-story-footer"><span>Renewable energy operations</span><a href="https://unsplash.com/photos/Ilpf2eUPpUE" target="_blank" rel="noreferrer">Photo: Andreas Gücklhorn / Unsplash</a></div>
    </aside>
    <main className="login-form">
      <div className="login-access">
        <div className="eyebrow">JEEVANGRID WORKSPACE</div><h1>Sign in</h1><p>Access your sites and operating plans.</p>
        <form ref={form} onSubmit={e=>{e.preventDefault();signIn(email,password)}}>
          <ErrorNotice error={error}/>
          <Input label="Email address" type="email" autoComplete="username" placeholder="you@organization.com" value={email} onChange={setEmail} required/>
          <Input label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} required/>
          <button className="primary full" disabled={!!busy}>{busy?'Signing in…':'Sign in'}<ArrowRight size={17}/></button>
        </form>
        {accounts.length>0&&<section className="demo-access" aria-label="Demo accounts"><div className="demo-access-heading"><h2>Explore the demo</h2><span className="badge">Sample accounts</span></div><p>Select an account to sign in with its assigned access.</p><div className="quick-login">{accounts.map(a=>{const Icon=a.role==='admin'?ShieldCheck:UserRound;return <button type="button" className={'quick-login-button '+(a.role==='admin'?'demo-admin':'')} key={a.email} disabled={!!busy} onClick={()=>demo(a)}><Icon size={19} aria-hidden="true"/><span><b>{busy===a.email?'Signing in…':a.name}</b><small>{a.description}</small><small className="demo-email">{a.email}</small></span><ArrowRight className="demo-arrow" size={15}/></button>})}</div></section>}
        <p className="login-footnote">Access follows your organization and site assignments.</p>
      </div>
    </main>
  </div>;
}
