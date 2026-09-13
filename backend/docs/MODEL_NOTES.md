# JeevanGrid

JeevanGrid is an advisory energy-mix optimizer for rural and off-grid microgrids. It combines site equipment, operating rules, weather, demand and current battery/generator state to calculate a 24-hour schedule for solar, wind, battery storage and diesel. The optimization protects critical demand first, then reduces operating cost, diesel consumption and emissions where the configured equipment makes that possible.

The repository also contains a software microgrid simulator. It streams clearly labelled simulated telemetry, triggers a new optimization every five simulated minutes or after a disruption, and executes operator-approved commands inside the simulator. It does not currently communicate with physical meters, inverters, batteries or generators.

## Project status

### Implemented and working

- React dashboard with Django REST APIs, JWT authentication and organization-scoped Admin/Operator permissions.
- Site setup for location, solar, wind, battery, diesel generator, demand classes, flexible loads, costs and operating constraints.
- Open-Meteo forecast retrieval and NASA POWER historical-weather replay, with timestamps, provenance and stale-data handling.
- `pvlib` solar estimation, hub-height wind conversion and a piecewise turbine power curve.
- PuLP/HiGHS mixed-integer optimization over 24 hourly intervals.
- Reliability-first dispatch: critical load, normal load and flexible work are optimized in that order before cost.
- Battery SOC, charge/discharge power, efficiency, reserve, terminal SOC and estimated wear cost.
- Diesel capacity, minimum stable power, fuel curve, fuel availability, allowed hours, maximum starts, minimum run/cooldown and ramp constraints.
- Lowest Cost, Balanced and Lowest Emissions dispatch preferences. Reliability retains priority in every strategy.
- Six preset resilience scenarios, custom what-if inputs and baseline-versus-scenario comparison.
- Multi-site portfolio comparison, plan history, immutable run snapshots, input provenance and CSV/JSON exports.
- Live Control digital twin with WebSocket updates, event injection, automatic rolling replanning and operator approval/rejection.
- Simulated command lifecycle: proposed, approved, executing, verified, rejected, expired/failed or superseded.
- XGBoost demand forecasting and XGBoost solar-residual correction, with chronological train/calibration/test periods and baseline fallback.
- Conservative forecast inputs using calibration residual bounds, or explicit stress margins when no eligible model exists.
- Guided demonstration, observed simulation evidence cards and exportable audit/event records.

### Data and claims

- The Leporiang reference demand and capacities come from a published study and are labelled as study/model values.
- Reference hourly demand is generated from the published daily energy and peak; it is labelled simulated from published totals.
- Open-Meteo and NASA POWER provide regional weather data, not electrical measurements from the site.
- The digital twin provides simulated operating telemetry. Its results demonstrate system behaviour, not measured village uptime or savings.
- Models trained on synthetic data are eligible only for simulated runs. Their held-out scores prove the ML pipeline works on that dataset, not field accuracy.
- Optimization outputs are recommendations. No physical equipment is controlled by this version.

### Yet to be done for a field deployment / Round 3

- Connect authenticated site telemetry from energy meters, inverter, battery BMS and generator controller through an edge gateway.
- Implement and commission vendor-specific read/write adapters such as Modbus or MQTT behind the existing telemetry and command interfaces.
- Add electrical safety interlocks, hardware fail-safe behaviour, manual local control and commissioned operator procedures.
- Collect actual site demand and generation history, preserve the forecast available at issue time, retrain the models and report field backtests.
- Compare planned dispatch with measured dispatch, including command acknowledgement, device alarms and communications failures.
- Add sub-hourly control only after modelling inverter dynamics, voltage, frequency, protection and distribution constraints. The current optimizer is hourly supervisory scheduling.
- Add multi-day fuel-delivery and extended-weather planning if the field use case requires it.
- Move SQLite to PostgreSQL and add a production job/streaming architecture for concurrent sites and durable telemetry ingestion.
- Configure production secrets, TLS, monitoring, backups and deployment infrastructure.

The detailed feature test is in [LIVE_WALKTHROUGH.md](LIVE_WALKTHROUGH.md).

## Setup and dashboard

See [backend setup](../README.md), the [current walkthrough](LIVE_WALKTHROUGH.md), and [seed data sources](SEED_DATA.md). All application code, documentation and development tools are under `frontend/` or `backend/`.

## How the current system works

```text
Site equipment, costs and operating rules
                  +
Weather forecast and demand profile
                  +
Current SOC, fuel and generator state
                  ↓
pvlib solar model + wind curve + eligible XGBoost corrections
                  ↓
PuLP/HiGHS reliability-first MILP optimization
                  ↓
24-hour renewable, battery, diesel and flexible-load schedule
                  ↓
Plain-language recommendation
                  ↓
Operator confirms/overrides a plan or approves/rejects a simulated command
                  ↓
New simulated telemetry or disruption triggers rolling replanning
```

Open-Meteo supplies weather forecasts; JeevanGrid does not use ML to predict weather. XGBoost estimates demand and can correct the error around the physics-based solar estimate. The optimizer then selects the energy mix while enforcing equipment limits and accounting for fuel price, generator starts, battery wear and diesel emissions.

## Workspace and data inspection

The site workflow has Plan and Test plan views. Source selection is applied by generating a new plan; every saved result retains its original input snapshot. Standard resilience checks run automatically through the Python worker.

Dataset Explorer, demand import and model datasets are accessible from the sidebar. Historical rows and exports are derived from saved snapshots.

Django database administration remains available at `http://127.0.0.1:8000/admin/`; create a Django superuser with `backend/.venv/bin/python backend/manage.py createsuperuser`. An application admin role does not grant Django superuser access. Operational edits should use application forms so validation and versioning remain enforced.

## Demo data and real weather

The reference site uses approximate Leporiang coordinates, `27.2297, 93.3412`. The [2017 original study](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/joe.2017.0447) reports survey-estimated demand of **876.41 kWh/day**, **101 kW peak** and modelled PSC capacities of **600 kW PV, 100 kW wind, 200 kW generator, 400 kW converter and 3,000 kWh batteries**. These are research inputs/results, not verified present-day plant telemetry.

The generated reference load totals exactly 876.41 kWh with an 18:00 hourly peak of 101 kW before flexible load rescheduling. The critical/normal/flexible split is 30/60/10. The two other sites are clearly labelled hypothetical variants for comparing constrained equipment. Fuel curves, efficiencies, SOC limits, critical fractions, replacement costs and flexible-load assignments are declared assumptions.

Fetch real historical weather for the reference site (site ID 1 on a fresh database):

```sh
backend/.venv/bin/python backend/manage.py fetch_history --site 1 --date 2025-01-15
```

The UI's Historical mode also fetches and caches data automatically. A day of NASA POWER data was retrieved during implementation and is cached in this workspace database. A fresh install can retrieve it with the command above. NASA supplies regional satellite/reanalysis weather, not site electrical readings. The [NASA hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) is queried in UTC; hourly irradiance is interpreted as W/m². Historical replay uses realized weather and must not be interpreted as a forecast accuracy test.

The [Open-Meteo forecast](https://open-meteo.com/en/docs) supplies irradiance, air temperature and wind speed. Its preceding-hour radiation is aligned to interval start; solar geometry uses interval midpoint. Cache fallback requires a complete matching 24-hour horizon and retrieval age under six hours. UI displays source and retrieval time. No calibrated ML confidence percentage is invented.

CSV format (exact column names, 24 consecutive rows, average power in kW):

```csv
timestamp,critical_kw,normal_kw,flexible_kw
2025-01-15T00:00:00+05:30,5,10,1
2025-01-15T01:00:00+05:30,5,9,1
```

Each timestamp needs an explicit UTC offset. Missing, duplicate, unordered, nonfinite or negative values are rejected. Flexible daily energy scales existing flexible tasks; if it cannot fit their windows, the import is rejected with a validation message.

## Model decisions and interpretation

The engine performs ordered solves: minimize critical energy unserved, then normal energy unserved, then unfinished flexible energy, then operating cost plus planning penalties. This prevents a finite monetary penalty from sacrificing service just to improve the renewable target. Physical bounds and terminal SOC remain hard constraints. If those make a solution impossible, the result is explicitly infeasible.

Simulated and forecast runs begin on the next site-local hour. Historical data retains its original UTC intervals; tasks are scheduled only when an entire interval fits inside their local operating window. An outage overlapping any part of an interval disables the generator for that whole interval. The hourly model is intentionally conservative at partial-hour boundaries.

Fuel per hour = `fuel_slope × diesel_kW + fuel_intercept × generator_on`. Cash cost is fuel expenditure plus start cost. Battery wear is discharged kWh multiplied by replacement cost / lifetime discharge throughput. Dispatch cost is cash plus estimated wear. Curtailment/target penalties appear separately and are not described as actual payments. This is wear-aware dispatch, not a capital-sizing or full LCOE calculation.

The battery is modelled at the common AC bus, with all conversion losses incorporated in effective charge/discharge efficiencies. V1 does not solve power flow, voltage, frequency, inverter transient limits or distribution faults. The reference study's shared converter rating is documented but not modelled separately; battery power limits are explicit.

Flexible tasks use divisible energy within a daily window (for example variable-speed pumping), not binary appliance controls. In an impossible scenario unfinished flexible work is reported instead of hiding it. Fixed critical loads are always prioritized. A lower configured critical service target changes target reporting, not the preference for serving all feasible critical demand.

Renewable share means used solar+wind divided by used solar+wind+diesel generation, including energy sent to storage. Battery discharge is excluded from primary generation so stored energy is not counted twice. This is a generation share, not a renewable share of delivered load with storage-origin tracking.

Reliability is projected energy adequacy over hourly intervals, not measured uptime or a probabilistic outage guarantee. Base critical shortages, stale forecasts or changed configurations are red. An unassessed resilience pack or reserve risk is amber; green requires evaluated scenarios with critical service and operating reserve preserved. Portfolio cohorts only combine identical modes and horizon starts; costs and fuel are normalized by served energy. Zero denominators appear as unavailable.

Forecasts have a six-hour freshness gate. Readings in Update readings are manual operator inputs. Live Control uses continuous simulated telemetry from the digital twin. Confirmation records human review of an advisory plan; Live Control approval applies a command only to the simulated plant. Changed, expired or superseded commands cannot execute.

## Verification

Backend physics, authorization, import, weather, forecasting, live lifecycle and automatic assessment checks are in `backend/grid/tests`. The current browser acceptance script is `frontend/tests/verify_workspace.py`; see the walkthrough for its scope and setup.

`backend/requirements-tested.txt` records the Python verification environment and `frontend/package-lock.json` locks frontend packages.

## Structure and API

`backend/grid/optimizer.py` is a pure solver accepting a frozen input snapshot. Weather and PV modelling prepare that input; Django persists output. Scenario runs and Live Control replans use the same optimizer. `backend/grid/live.py` contains the software plant and supervisory loop; `backend/grid/forecasting.py` contains model training, evaluation, eligibility and inference. `backend/grid/models.py` contains the ORM entities. `frontend/src/main.jsx` contains the app shell and site configuration. Separate React modules contain Portfolio, SiteWorkspace, PlanTesting, PlanCharts, DataWorkspace and LiveControl.

API routes follow the plan without trailing slashes. Additional endpoints: `/api/auth/refresh`, `/api/auth/logout`, `/api/members`, `/api/defaults`, `/api/locations/search`, and `GET /api/optimization-runs` with optional `site_id` or `kind=scenario`. A baseline run returns status, explanatory action, metrics, intervals, version, source metadata, review trail and snapshot. Scenario responses add baseline metrics, overrides and deltas. All site/run lookups are scoped to organization and assignment.

SQLite is intended for the local demo. Move to PostgreSQL and a production worker/streaming architecture for concurrent sites; the Django ORM and migrations preserve that path. Before deployment, provide a real `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0`, configure allowed hosts, TLS, credential management and remove demo account defaults.
