export const checks=[['cloudy','Cloud cover','Solar −50%'],['low_wind','Low wind','Wind −50%'],['high_demand','Demand peak','Demand +25%'],['expensive_fuel','Fuel price','Price +25%'],['generator_outage','Generator outage','18:00–24:00'],['low_battery','Low battery','Starting SOC 25%']];
const expected={cloudy:{solar_multiplier:.5},low_wind:{wind_multiplier:.5},high_demand:{demand_multiplier:1.25},expensive_fuel:{fuel_price_multiplier:1.25},generator_outage:{outage_start:18,outage_end:24},low_battery:{starting_soc:25}};
export const matches=r=>expected[r.scenario_name]&&Object.keys(r.overrides||{}).length===Object.keys(expected[r.scenario_name]).length&&Object.entries(expected[r.scenario_name]).every(([k,v])=>r.overrides[k]===v);
export const feasible=r=>r&&['optimal','feasible'].includes(r.status);
export function stressFinding(run,baseline) {
  if(!run)return {tone:'pending',label:'Computing',detail:'Waiting for a saved solver result.'};
  if(!feasible(run))return {tone:'red',label:'No feasible schedule',detail:'The solver could not meet the configured limits. Open the result to inspect diagnostics.'};
  const m=run.metrics,b=baseline.metrics,c=baseline.snapshot.configuration;
  if(run.scenario_name==='low_wind'&&!c.wind.capacity_kw)return {tone:'neutral',label:'No wind installed',detail:'This site has no wind turbine. This scenario repeats the original plan, including any existing reserve shortfall.'};
  if(run.scenario_name==='cloudy'&&!c.solar.capacity_kw)return {tone:'neutral',label:'No solar installed',detail:'This site has no solar capacity. This scenario repeats the original plan, including any existing reserve shortfall.'};
  if(run.scenario_name==='expensive_fuel'&&m.diesel_litres<.01&&b.diesel_litres<.01)return {tone:'neutral',label:'No fuel-price exposure',detail:'Neither plan burns diesel. Fuel price therefore has no effect on dispatch cost.'};
  const shortage=(m.critical_unserved_kwh||0)+(m.normal_unserved_kwh||0);
  if(m.critical_unserved_kwh>.001)return {tone:'red',label:'Critical supply gap',detail:'Some essential demand is unserved. Review backup capacity and load priorities.'};
  if(m.minimum_soc_pct<c.battery.reserve_soc-.001||m.reserve_compliance_pct<99.999){
    const inherited=b.minimum_soc_pct<c.battery.reserve_soc-.001&&m.minimum_soc_pct>=b.minimum_soc_pct-.01;
    return {tone:'amber',label:inherited?'Existing reserve shortfall':'Reserve under pressure',detail:inherited?'The original plan already dips below reserve. This scenario still uses that reserve; compare the hourly trace to see when.':'Battery charge falls below the operating reserve. Review stored energy and backup availability.'};
  }
  if(shortage>.001||m.flexible_unserved_kwh>.001)return {tone:'amber',label:'Some demand deferred',detail:'Essential service is preserved, but some normal demand or flexible work is unfinished.'};
  if(m.diesel_litres-b.diesel_litres>.1)return {tone:'green',label:'Backup covers the change',detail:'Additional diesel preserves service and the battery operating reserve.'};
  if(b.minimum_soc_pct-m.minimum_soc_pct>.05)return {tone:'green',label:'Storage absorbs the change',detail:'The battery works harder while essential demand and the operating reserve are preserved.'};
  return {tone:'green',label:'Within operating limits',detail:'Essential demand and the operating reserve remain covered under these conditions.'};
}
export const stressMetrics={
  reserve:{label:'Reserve margin',unit:'pp',value:(m,c)=>m.minimum_soc_pct-c.battery.reserve_soc,caption:'Lowest charge minus the operating reserve. Below zero means the reserve is breached.'},
  fuel:{label:'Diesel',unit:'L',value:m=>m.diesel_litres,caption:'Total generator fuel in each 24-hour scenario. Zero means the plan needs no diesel.'},
  cost:{label:'Cost',unit:'INR',value:m=>m.dispatch_cost_inr,caption:'Fuel, generator starts and estimated battery wear. Planning penalties are excluded.'},
  shortage:{label:'Unserved energy',unit:'kWh',value:m=>(m.critical_unserved_kwh||0)+(m.normal_unserved_kwh||0)+(m.flexible_unserved_kwh||0),caption:'Unserved critical and normal energy plus unfinished flexible work across the day.'},
};
