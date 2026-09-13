import React,{useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight,ArrowDown,Sun,Wind,Battery,Zap,ShieldCheck,Users,Building2,HeartHandshake,Check,Database,Workflow,BrainCircuit,ChartNoAxesCombined,Layers,Menu,X,ArrowRight,CloudSun,Clock3} from 'lucide-react';
import Brand from './Brand';
import './landing.css';

const SECTIONS=[['overview','Overview'],['purpose','Purpose'],['planning','The workflow'],['intelligence','Intelligence'],['evidence','The evidence'],['architecture','Architecture']];
const ACTIONS=[
  {name:'Record readings',prompt:'Record battery SOC 45%, fuel 20 litres, and generator available and off.',table:'SiteReading',result:'A new operating-state record',detail:'The saved values are read back and checked.'},
  {name:'Generate a plan',prompt:'Generate a 24-hour plan using simulated weather.',table:'OptimizationRun + 24 DispatchIntervals',result:'A calculated, persisted energy schedule',detail:'The solver calculates dispatch. Six stress checks follow.'},
  {name:'Export evidence',prompt:'Export the latest operating plan as a PDF report.',table:'ReportArtifact',result:'A downloadable, evidence-backed PDF',detail:'The completed file and its content hash are verified.'},
];

function SectionTitle({number,kicker,title,children}){
  return <div className="lp-section-title"><div className="lp-kicker"><span>{number}</span>{kicker}</div><h2>{title}</h2>{children&&<p>{children}</p>}</div>;
}

function EnergyPreview(){
  const sun=[0,0,0,0,1,3,8,16,25,34,42,46,44,38,29,21,12,5,0,0,0,0,0,0];
  return <div className="lp-energy-preview">
    <img src="/solar-farm.jpg" alt="Solar arrays surrounded by green fields" width="720" height="760" fetchPriority="high"/>
    <div className="lp-photo-shade"/>
    <div className="lp-preview-top"><span><span className="lp-dot"/> RENEWABLE ENERGY, COORDINATED</span><ArrowUpRight size={22}/></div>
    <div className="lp-resource-orbit"><span><Sun/>Solar</span><span><Wind/>Wind</span><span><Battery/>Storage</span><span><Zap/>Backup</span></div>
    <div className="lp-dispatch-card"><div className="lp-dispatch-title"><span>One grid. One considered plan.</span><ShieldCheck size={20}/></div>
      <div className="lp-mini-chart" role="img" aria-label="Illustrative daily energy mix: solar rises at midday, storage and backup support other hours">
        {sun.map((v,h)=><div key={h} className="lp-chart-column"><i className="lp-bar-diesel" style={{height:h>18&&h<22?'16%':'0%'}}/><i className="lp-bar-battery" style={{height:h<6||h>17?'24%':'5%'}}/><i className="lp-bar-wind" style={{height:'9%'}}/><i className="lp-bar-solar" style={{height:`${v*1.4}%`}}/></div>)}
      </div><div className="lp-chart-axis"><span>00:00</span><span>12:00</span><span>23:00</span></div>
      <div className="lp-chart-legend"><span><i className="lp-solar"/>Solar</span><span><i className="lp-wind"/>Wind</span><span><i className="lp-battery"/>Storage</span><span><i className="lp-diesel"/>Diesel</span></div>
      <p>Illustrative energy mix · not live telemetry</p>
    </div>
  </div>;
}

export default function Landing(){
  const [active,setActive]=useState('overview'),[menu,setMenu]=useState(false),[action,setAction]=useState(0);
  useEffect(()=>{
    document.title='JeevanGrid · Every watt. A wiser decision.';
    const oldScroll=document.documentElement.style.scrollBehavior;
    if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)document.documentElement.style.scrollBehavior='smooth';
    let frame;
    const update=()=>{
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>{
        let selected='overview';
        for(const [id] of SECTIONS){if(document.getElementById(id)?.getBoundingClientRect().top<=190)selected=id;}
        if(window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-5)selected='architecture';
        setActive(selected);
      });
    };
    window.addEventListener('scroll',update,{passive:true});window.addEventListener('resize',update);update();
    return()=>{cancelAnimationFrame(frame);window.removeEventListener('scroll',update);window.removeEventListener('resize',update);document.documentElement.style.scrollBehavior=oldScroll;document.title='JeevanGrid · Microgrid operations';};
  },[]);
  useEffect(()=>{if(!menu)return;const escape=e=>{if(e.key==='Escape')setMenu(false)};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape)},[menu]);
  const selected=ACTIONS[action];
  return <div className="landing">
    <a className="skip-link" href="#overview">Skip to content</a>
    <header className="lp-header"><Link className="brand" to="/" aria-label="JeevanGrid home"><Brand/></Link>
      <nav className={'lp-header-nav '+(menu?'is-open':'')} id="landing-navigation" aria-label="Page sections">
        {SECTIONS.slice(1).map(([id,label])=><a key={id} href={`#${id}`} aria-current={active===id?'location':undefined} onClick={()=>setMenu(false)}>{label}</a>)}
      </nav>
      <div className="lp-header-actions"><Link className="lp-login" to="/login">Log in</Link><Link className="lp-button lp-small" to="/login">Get started <ArrowUpRight size={16}/></Link><button className="lp-menu" aria-label={menu?'Close navigation':'Open navigation'} aria-expanded={menu} aria-controls="landing-navigation" onClick={()=>setMenu(!menu)}>{menu?<X/>:<Menu/>}</button></div>
    </header>
    <nav className="lp-scrollspy" aria-label="Reading progress">{SECTIONS.map(([id,label],i)=><a key={id} href={`#${id}`} aria-label={label} aria-current={active===id?'location':undefined}><span>{String(i+1).padStart(2,'0')}</span><b>{label}</b><i/></a>)}</nav>
    <main>
      <section id="overview" className="lp-hero lp-container">
        <div className="lp-hero-copy"><div className="lp-kicker"><span className="lp-dot"/> MICROGRID ENERGY INTELLIGENCE</div><h1>Every watt.<br/>A wiser <em>decision.</em></h1>
          <p>Solar. Wind. Storage. Diesel.<br/>One intelligent plan for communities that need dependable power.</p>
          <div className="lp-hero-actions"><Link className="lp-button" to="/login">Get started <ArrowUpRight size={19}/></Link><a className="lp-text-link" href="#planning">See how it works <ArrowDown size={16}/></a></div>
          <div className="lp-hero-proof"><ShieldCheck size={17}/><span>Essential loads first. Every decision explained.</span></div>
        </div><EnergyPreview/>
      </section>
      <div className="lp-proof-strip lp-container"><div><b>24<span>h</span></b><span>Energy planning horizon</span></div><div><b>108</b><span>Engineering-modelled demo sites</span></div><div><b>6</b><span>Standard disruption checks</span></div><div><b>1</b><span>Traceable decision workflow</span></div></div>

      <section id="purpose" className="lp-section lp-container">
        <SectionTitle number="01" kicker="THE REASON WE BUILT IT" title={<>Reliable energy.<br/>Real everyday stakes.</>}>Uncertain weather and costly diesel make every operating decision matter. Plan for the clinic, the evening lights and the water pump—not just the next kilowatt.</SectionTitle>
        <div className="lp-audience-grid">{[[Users,'Microgrid operators','Know what to run, when to store and why backup is needed.'],[Building2,'Electrification agencies','Compare critical service, fuel and cost across assigned sites.'],[HeartHandshake,'NGOs & communities','Make priorities explicit and see the assumptions behind the plan.']].map(([Icon,title,text])=><article key={title}><Icon size={26}/><h3>{title}</h3><p>{text}</p></article>)}</div>
        <div className="lp-outcomes"><span><Sun size={18}/>Use renewable potential</span><span><ShieldCheck size={18}/>Protect essential supply</span><span><ChartNoAxesCombined size={18}/>Understand cost & emissions</span></div>
      </section>

      <section id="planning" className="lp-dark-section"><div className="lp-container">
        <SectionTitle number="02" kicker="FROM CONDITIONS TO CONFIDENCE" title={<>A plan for the day.<br/>A response when it changes.</>}>One optimization engine connects planning, what-if tests and rolling software replay.</SectionTitle>
        <div className="lp-step-grid">{[[MapIcon,'01','Configure','Equipment, priorities, fuel costs and flexible work.'],[CloudSun,'02','Plan','Weather + demand + battery state → a 24-hour dispatch.'],[Workflow,'03','Stress-test','Clouds, outages, demand spikes and low reserves.'],[ShieldCheck,'04','Review & verify','Approve a response. Inspect its saved evidence.']].map(([Icon,num,title,text])=><article key={num}><div><span>{num}</span><Icon size={23}/></div><h3>{title}</h3><p>{text}</p></article>)}</div>
        <div className="lp-replay-line"><span className="lp-pulse"><Clock3 size={20}/></span><div><strong>Conditions change. The plan responds.</strong><p>WebSocket telemetry, simulated five-minute replanning and operator-approved commands.</p></div><span className="lp-outline-tag">Software digital twin · no physical control</span></div>
      </div></section>

      <section id="intelligence" className="lp-section lp-container">
        <SectionTitle number="03" kicker="INTELLIGENCE WITH A JOB TO DO" title={<>AI that does the work.<br/>Math that makes the decision.</>}>A scoped assistant turns requests into verified application actions. It does not invent the energy schedule.</SectionTitle>
        <div className="lp-agent-layout"><div className="lp-agent-copy"><span className="lp-pill"><BrainCircuit size={15}/>Agentic, with guardrails</span><h3>From a message<br/>to a saved result.</h3><p>Groq-hosted GPT-OSS interprets the request. Django checks access and inputs, executes the registered workflow, then verifies persisted records.</p><ol>{['Understand the request','Check site access & valid inputs','Execute the application workflow','Read back & verify the result'].map((s,i)=><li key={s}><span>{i+1}</span>{s}</li>)}</ol></div>
          <div className="lp-agent-demo"><div className="lp-demo-head"><span><Workflow size={17}/>Inside a verified workflow</span><span>ILLUSTRATION</span></div><div className="lp-action-tabs" role="group" aria-label="Example assistant workflows">{ACTIONS.map((a,i)=><button key={a.name} aria-pressed={action===i} onClick={()=>setAction(i)}>{a.name}</button>)}</div><div className="lp-demo-prompt">“{selected.prompt}”</div><div className="lp-demo-connector"><ArrowDown size={20}/><span>Authorize → execute → check</span></div><div className="lp-demo-result" aria-live="polite"><span><Database size={20}/>{selected.result}</span><code>{selected.table}</code><p><Check size={15}/>{selected.detail}</p></div><small>Workflow illustration only. No records are written on this page. These actions run after login.</small></div>
        </div>
        <div className="lp-model-heading"><h3>Under the hood, each model has a purpose.</h3><span>Prediction ≠ optimization</span></div>
        <div className="lp-model-grid">{[
          ['ML / DEMAND','XGBoost regressor','Learns demand patterns from time, temperature and the load baseline.','Chronological hold-out evaluation'],
          ['ML / SOLAR','XGBoost residual model','Learns the gap between observed solar output and the physics estimate.','Correction, not a replacement for physics'],
          ['PHYSICS / RENEWABLES','pvlib + wind curve','Converts irradiance, temperature and wind into available generation.','Weather becomes usable power'],
          ['DECISIONS / DISPATCH','MILP · PuLP + HiGHS','Schedules generation and storage within energy, SOC and generator constraints.','Reliability priorities before cost tradeoffs'],
        ].map(([tag,title,text,caption])=><article key={title}><span>{tag}</span><h3>{title}</h3><p>{text}</p><small>{caption}</small></article>)}</div>
        <p className="lp-honesty-note"><ShieldCheck size={17}/><span>ML training and evaluation are implemented. Current standard plans and replay use saved demand and physics estimates; ML is not automatically enabled in those screens. Simulated training scores are not field validation.</span></p>
      </section>

      <section id="evidence" className="lp-evidence-section"><div className="lp-container">
        <SectionTitle number="04" kicker="GROUNDED INPUTS. VISIBLE EVIDENCE." title={<>Trust the reasoning.<br/>Inspect the records.</>}>No mystery dataset. Weather, study references, engineering assumptions and operator inputs are labelled separately.</SectionTitle>
        <div className="lp-evidence-grid"><article className="lp-case-study"><span className="lp-kicker">A SAVED DEMONSTRATION · JG004</span><h3>Less solar.<br/>Essential demand still served.</h3><div className="lp-case-stat">100<span>%</span></div><p>Critical energy served in the tested baseline and 50%-lower-solar scenario.</p><div className="lp-case-change"><span>Diesel required</span><b>~0 L <ArrowRight size={18}/> 1.57 L</b></div><small>Recorded demo: 13 Sep 2026. Modelled community and simulated weather. Backup increased to preserve supply; this is not a measured savings claim.</small></article>
          <div className="lp-source-cards">{[
            ['01','Real regional weather','NASA POWER historical data and Open-Meteo forecasts, with source and retrieval time.','https://power.larc.nasa.gov/docs/services/api/temporal/hourly/','NASA POWER'],
            ['02','Published Indian references','Leporiang and village microgrid studies inform the reference configurations—not claims of live installations.','https://gramoorja.in/wp-content/uploads/2024/12/Micro-GridPaper.pdf','Village microgrid reference'],
            ['03','Auditable engineering data','108 modelled sites. Appliance counts, watts, schedules, pump energy and equipment assumptions you can inspect.',null,null],
          ].map(([num,title,text,url,label])=><article key={num}><span>{num}</span><div><h3>{title}</h3><p>{text}</p>{url&&<a href={url} target="_blank" rel="noreferrer">{label}<ArrowUpRight size={14}/></a>}</div></article>)}</div></div>
        <div className="lp-evidence-footer"><Database size={18}/><span>Saved inputs → hourly dispatch → operator decisions → CSV & PDF evidence.</span><strong>Traceable by design.</strong></div>
      </div></section>

      <section id="architecture" className="lp-section lp-container">
        <SectionTitle number="05" kicker="ONE CONNECTED SYSTEM" title={<>Built to explain.<br/>Designed to be inspected.</>}/>
        <div className="lp-architecture" aria-label="System architecture">
          <div className="lp-arch-node"><Layers/><span>OPERATOR EXPERIENCE</span><h3>React dashboard</h3><p>Sites · plans · comparisons · assistant</p></div><ArrowRight className="lp-arch-arrow"/>
          <div className="lp-arch-node lp-arch-core"><Workflow/><span>PERMISSIONED APPLICATION</span><h3>Django REST API</h3><p>Access · validation · workflow orchestration</p></div><ArrowRight className="lp-arch-arrow"/>
          <div className="lp-arch-node"><BrainCircuit/><span>ENERGY & INTELLIGENCE</span><h3>Python engine</h3><p>pvlib · XGBoost · PuLP / HiGHS</p></div>
        </div><div className="lp-architecture-base"><span><Database size={19}/><b>SQLite</b> · configurations, snapshots & evidence</span><span><Workflow size={19}/><b>Python workers</b> · assistant, reports & replay</span></div>
        <div className="lp-final-cta"><div><span className="lp-kicker">TURN ENERGY DATA INTO A DECISION</span><h2>Meet your next<br/>operating plan.</h2><p>Explore the tools. Follow the evidence. Keep the operator in control.</p></div><div><Link className="lp-button" to="/login">Explore JeevanGrid <ArrowUpRight size={20}/></Link><small>Organization-managed access · demo accounts available</small></div></div>
      </section>
    </main>
    <footer className="lp-footer lp-container"><Link to="/" className="brand"><Brand/></Link><p>Renewable energy intelligence.<br/>Advisory planning & software simulation.</p><div><a href="#overview">Back to top ↑</a><a href="https://unsplash.com/photos/Ilpf2eUPpUE" target="_blank" rel="noreferrer">Photo: Andreas Gücklhorn / Unsplash</a></div></footer>
  </div>;
}

function MapIcon(props){return <Building2 {...props}/>;}
