"""Curated application documentation for read-only answers."""
DOCUMENTATION={
 'workflow':'Portfolio → select a site → Plan → choose weather and Generate plan → Test plan (conditions or Live replay) → Review plan. Saved plans appear in Recent plans and Data explorer.',
 'roles':'Administrators configure sites, assign operators and manage lifecycle. Operators plan, record readings and review decisions for assigned sites. Each site conversation is restricted to that site.',
 'battery':'SOC is stored energy as a percentage of battery capacity. Minimum SOC is a hard modeled safety limit; reserve SOC is an operating target which a plan may use. Reserve margin is minimum planned SOC minus operating reserve, in percentage points.',
 'terminal_reserve':'Terminal SOC is a separate hard constraint on battery charge at the end of the 24-hour plan. Operating reserve is a target buffer during the day; it is not a frequency-control or spinning-reserve service.',
 'weather':'Demo weather is simulated; Open-Meteo is a regional forecast; NASA is historical regional weather requiring a past date. Site demand is a saved profile, not measured electrical telemetry. Changing the selector requires generating a new plan.',
 'cost':'Dispatch cost includes fuel, generator starts and estimated battery wear. Planning penalties and carbon value are not cash expenditure. Per-kWh cost and diesel use supplied energy as their denominator.',
 'replay':'Starts from a selected feasible saved plan. Conditions alter only the simulation. Commands require explicit review. Verification checks simulated generator output and energy balance. Battery balancing happens automatically. Cloud, demand +50%, low battery, outage and restore are available events; restore does not refill fuel or reset battery SOC.',
 'datasets':'Data explorer is in the sidebar. Demand CSV requires timestamp,critical_kw,normal_kw,flexible_kw: exactly 24 sorted consecutive hourly intervals with timezone offsets. Forecast-training CSV requires 30–366 days of hourly observations; the simulated dataset is 90 days.',
 'forecast_training':'Calibration decides model eligibility; a separate test period reports accuracy. Training does not automatically enable ML in standard operating plans or the saved-plan replay.',
 'reports':'PDF is a readable report; CSV is a ZIP of tables plus complete evidence JSON; JSON is the full structured record. All export formats can share a frozen evidence snapshot. Legacy replay history is explicitly marked incomplete.',
 'limits':'Plans are hourly energy-adequacy models, not frequency/voltage/transient analysis or physical control. Six resilience scenarios are finite stress checks, not guarantees. Zero diesel or infeasibility can be valid outcomes.',
}
