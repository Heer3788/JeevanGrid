import {test} from 'node:test';
import assert from 'node:assert/strict';
import {stressFinding,stressMetrics,matches} from '../src/stressInsights.js';

const baseline={status:'optimal',metrics:{diesel_litres:0,minimum_soc_pct:58},snapshot:{configuration:{solar:{capacity_kw:600},wind:{capacity_kw:0},battery:{reserve_soc:30}}}};
const result=(name,metrics={})=>({status:'optimal',scenario_name:name,metrics:{critical_unserved_kwh:0,normal_unserved_kwh:0,flexible_unserved_kwh:0,critical_load_served_pct:100,minimum_soc_pct:50,reserve_compliance_pct:100,diesel_litres:0,...metrics}});
test('zero diesel still exposes a battery reserve breach, including an initial SOC breach',()=>{
  const r=result('low_battery',{minimum_soc_pct:23.2});
  assert.equal(stressFinding(r,baseline).tone,'amber');
  assert.ok(Math.abs(stressMetrics.reserve.value(r.metrics,baseline.snapshot.configuration)+6.8)<1e-9);
});
test('a site without wind does not claim a successful wind resilience test',()=>assert.equal(stressFinding(result('low_wind'),baseline).label,'No wind installed'));
test('no diesel means no fuel-price exposure',()=>assert.equal(stressFinding(result('expensive_fuel'),baseline).tone,'neutral'));
test('essential shortage takes priority over fuel or reserve',()=>assert.equal(stressFinding(result('cloudy',{critical_unserved_kwh:5,minimum_soc_pct:20}),baseline).tone,'red'));
test('infeasible results never look like safe zero-valued plans',()=>assert.equal(stressFinding({status:'infeasible',metrics:{}},baseline).label,'No feasible schedule'));
test('noncritical and flexible shortfalls also require review',()=>assert.equal(stressFinding(result('high_demand',{flexible_unserved_kwh:6}),baseline).tone,'amber'));
test('available backup and storage explain actual changes',()=>{
 assert.equal(stressFinding(result('cloudy',{diesel_litres:32}),baseline).label,'Backup covers the change');
 assert.equal(stressFinding(result('cloudy'),baseline).label,'Storage absorbs the change');
});
test('custom experiments cannot be counted as standard checks',()=>{
 assert.equal(matches({scenario_name:'cloudy',overrides:{solar_multiplier:.5}}),true);
 assert.equal(matches({scenario_name:'cloudy',overrides:{solar_multiplier:.5,demand_multiplier:2}}),false);
});

test('existing baseline reserve shortfalls are distinguished from new ones',()=>{
 const b={...baseline,metrics:{...baseline.metrics,minimum_soc_pct:20}};
 assert.equal(stressFinding(result('high_demand',{minimum_soc_pct:21}),b).label,'Existing reserve shortfall');
 assert.equal(stressFinding(result('high_demand',{minimum_soc_pct:19}),b).label,'Reserve under pressure');
});
