# Engineering portfolio: 108 inspectable microgrids

These are **engineering-modelled examples, not 108 real monitored installations**. They support a truthful optimization demonstration without inventing meter readings, equipment ownership or real operators. Public projects inform the scale and load categories; the actual assumptions are disclosed per site.

## What is seeded

- 108 new sites: nine regional anchors × three household counts (36, 64, 104) × four service types (Household, Market, Agro, Health).
- 27 fictional regional operator accounts, each assigned four sites. All remain inside the existing demo organization. No real people's names or contact details are used.
- Every site has solar, battery and diesel engineering configuration, reliability/cost policies, a current-state reading, 24 hourly load intervals and at least one scheduled water pump.
- Market examples add workshops; agro examples add irrigation and grain milling; health examples add essential clinic lighting and refrigeration. Clinic demand is electrical, not a vaccine-temperature guarantee.
- `--with-runs` calculates and saves a genuine 24-hour MILP result; no hardcoded savings, green badges or successful results.
- `--with-checks` applies the six existing stress scenarios through the same solver. Feasible/infeasible outcomes are retained honestly.
- Existing sites, logins, edited configurations and historical runs are not overwritten. The seed key and index, rather than the editable site name, identify previously seeded records.

The regions are Jehanabad, Lakhimpur Kheri, Gumla, Khunti, Pune-region, Palghar, Nandurbar, Melghat/Amravati and Dandeli/Uttara Kannada. Coordinates are shared regional anchors, **not surveyed village boundaries or plant locations**. The map groups sites at those coordinates.

## Where to see it

1. **Sites**: search `JG`, a region, `Health` or `Agro`.
2. **Configure site → Demand & loads**: load totals and scheduled pumps/business tasks. The **Add load** button is here.
3. **Data explorer → Site**: expand **How this site's demand was calculated**. See appliance counts, watts, duty factors, local-hour schedules, daily energy, priorities and pumping assumptions. This panel is collapsed by default.
4. Choose a **Saved run** to inspect Demand, Weather, Dispatch and Sources; download its hourly CSV.
5. **People & access**: each regional operator's four assignments.
6. **Portfolio**: compare matching horizons, not arbitrary run totals.

The database is `backend/db.sqlite3`. A local Django superuser can also inspect the records at `http://127.0.0.1:8000/admin/`; an application organization-admin account is not automatically a Django superuser.

## How the numbers are constructed

The reproducible source is `grid/portfolio_seed.py`. It uses explicit engineering rules, not an LLM or random sampling.

| Component | Calculation / meaning |
| --- | --- |
| Fixed demand | Appliance count × watts × duty factor for each active hour ÷ 1,000. Sum the actual 24 rows to get daily energy and reference peak. |
| Essential demand | An essential household light, streetlights, controller/communications, plus clinic essentials in Health examples. Priorities are assumptions, not a measured survey. |
| Drinking water | Four people/household × 40 L/person/day; pump energy = ρgVH / (0.45 × 3.6 million) kWh. Region-specific lift heads are assumptions. |
| Flexible work | Daily energy plus allowed window and maximum kW. Its energy is counted once; the optimizer reschedules it rather than adding it again to fixed demand. |
| PV | Coverage × daily demand / (4 assumed equivalent sun-hours × 0.78 nominal yield); round up to 550 W module increments. This is a sizing heuristic, **not** the weather forecast or optimal capital sizing. |
| Battery | Overnight fixed demand, usable 20–95% SOC range and discharge efficiency; round to 5.12 kWh modules. Charge/discharge limits do not exceed 0.5C. |
| Diesel | A size above the fixed peak plus simultaneous flexible motor ratings, with 15% headroom. Two-hour minimum run and one-hour cooldown. |
| Fuel | Assumed litres/hour = 0.03 × rated kW when on + 0.26 × dispatched kW. Price is an explicit scenario input, not a live district quotation. |
| Battery wear | Assumed replacement ₹12,000/kWh divided by 4,000 cycles × 75% usable depth × capacity. Not a vendor quotation or cycle-life guarantee. |
| Cost/emissions | Calculated by the existing optimizer from the resulting fuel, starts, discharged battery energy and configured combustion factor. |

Large Agro examples intentionally model an equipment-constrained expansion: lower PV coverage and less overnight storage. Their purpose is to reveal diesel/reserve tradeoffs, not manufacture a universally successful plan.

Most reference deployments are solar microgrids. Therefore these 108 examples have **zero installed wind** rather than fictitious turbines or resource measurements. Wind remains implemented in the optimizer and existing Leporiang study/hypothetical hybrid examples. Do not claim wind turbines operate at these modelled sites.

## Real weather, modelled demand

The populated historical portfolio uses NASA POWER hourly radiation, temperature and wind for **15 January 2025**, one request per regional coordinate, reused at that same coordinate. It is regional historical weather/reanalysis, **not** current weather or site telemetry. All sites share the same historical horizon for meaningful comparisons. The demand intervals are engineering templates, regardless of the weather source.

Historical API failure stops a requested historical seed; it is never silently replaced with simulation. `--weather simulated` is an explicit offline alternative. A `forecast` run in the app separately requests Open-Meteo's current forecast. Cached live forecasts must satisfy the existing six-hour rule.

## Repeat on another laptop

From the repository root, after installing dependencies and migrating:

```sh
backend/.venv/bin/python backend/manage.py seed_demo
backend/.venv/bin/python backend/manage.py seed_portfolio --with-runs --with-checks --weather historical --date 2025-01-15 --export-dir backend/.local/portfolio
```

On Windows, replace `backend/.venv/bin/python` with `backend\.venv\Scripts\python.exe`. CSV export uses UTF-8 with BOM for Excel. The JSON manifest includes every load interval, source and configuration, but no passwords.

For an offline demo replace `--weather historical --date 2025-01-15` with `--weather simulated`. Re-running skips existing baselines; it does **not** change their weather. Generate a new plan through the UI when you want to change a saved site's source.

Use a single seed process. For fastest bulk setup, stop an idle simulator worker during `--with-checks`, then restart it afterwards. Do not stop an active replay mid-demonstration. Existing accounts are never reset. New demo operator passwords use `JEEVANGRID_DEMO_PASSWORD` or the local-demo default `JeevanGridDemo!26`; do not deploy these accounts publicly.

## References and limitations

- [Gram Oorja microgrid paper](https://gramoorja.in/wp-content/uploads/2024/12/Micro-GridPaper.pdf): Darewadi's published 39 households, 9.36 kWp solar and 28.8 kWh nominal battery, with separate load feeders. Its historical battery system is not the LFP-style assumption used here.
- [Gram Oorja deployment history](https://gramoorja.in/journey/): regional deployment and productive/essential-load context, including pumping, schools and health centres.
- [Greenpeace's Dharnai report](https://www.greenpeace.org/india/en/story/278/dharnai-goes-live-powered-by-greenpeaces-first-solar-microgrid/): the 2014 solar/pumping project; not evidence of present operation.
- [Tata Power solar microgrids](https://www.tatapower.com/renewables/solar-microgrids): rural business, irrigation and microgrid product context.
- [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/): source of the historical weather inputs.

No household metering, distribution power flow, voltage/frequency regulation, motor inrush, measured outages, site surveys or financial lifecycle validation is claimed. The hourly engine schedules aggregate power at the microgrid bus. Replace assumptions with operator/manufacturer data and uploaded measurements before a field deployment.
