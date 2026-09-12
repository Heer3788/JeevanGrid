# JeevanGrid

A local React + Django application for planning and stress-testing rural microgrid operation. Recommended plans are produced by PuLP/HiGHS; an independent, deterministic reactive controller provides an explicitly labelled comparison. No ML or equipment control is included.

## Quick start

Requirements: Python 3.12+ and Node.js 22.12+ (Node 24 recommended). SQLite is included with Python. Run commands from this directory.

Linux / macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py seed_demo --with-runs
cd frontend
npm ci
cd ..
python3 dev.py
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo --with-runs
cd frontend
npm ci
cd ..
py dev.py
```

Open **http://127.0.0.1:5173**. The Django API listens on port 8000; Vite proxies `/api` requests. Both servers bind to localhost. `Ctrl+C` stops the launcher. For the current workspace a local Node runtime is also installed in `.venv/bin`; `dev.py` finds it automatically.

Demo accounts:

| Role | Email | Default password |
| --- | --- | --- |
| Admin | admin@jeevangrid.local | JeevanGridDemo!26 |
| Operator | operator@jeevangrid.local | JeevanGridDemo!26 |

The operator is assigned the reference and compact sites only. Set `JEEVANGRID_DEMO_PASSWORD` before first seeding to choose another password. Seeding is idempotent and does not reset existing accounts or overwrite sites. This is a local demo, not a production deployment.

## Included workflows

- Organization-scoped admin/operator permissions enforced by Django and JWT login/refresh/logout.
- Site creation, five-step configuration, operator assignment, archival and restoration.
- Searchable Indian state/union-territory and locality fields. A prefix such as `Ahm` suggests Ahmedabad and automatically fills the best match's WGS84 coordinates, district and timezone through Open-Meteo geocoding. Alternative matches can be selected and coordinates remain editable.
- Profiles for solar, wind, battery, generator, demand, flexible tasks and operating policies.
- Manual SOC, fuel, generator status, price and event readings; new readings invalidate prior plans for approval.
- Validated 24-hour interval CSV import. Imported intervals become a repeating local-hour demand template.
- Explicit simulated, Open-Meteo forecast and NASA POWER historical modes. API failures never silently switch to simulated data.
- Deterministic solar modelling with pvlib, wind height adjustment/power curve, and battery losses.
- 24-hour mixed-integer dispatch including generator starts/fuel availability, SOC limits, terminal reserve, allowed generator hours, flexible task windows and renewable target shortfall.
- Six scenario presets plus custom resource/demand/price/SOC sliders and configurable outage hours.
- Baseline-versus-scenario comparisons, immutable input snapshots, plan history, JSON export and confirm/override trail.
- Multi-site reliability table, 2–5 site comparison, normalized costs, critical-energy weighted cohorts and sequential portfolio resilience packs.
- Desktop and mobile layouts, visible provenance, projected metric labels, stale-data and infeasible-plan states.

## Renewable energy intelligence workspace

- **Portfolio:** offline interactive geography, grouped markers for shared coordinates, a site inspector, clear reliability labels, and normalized site comparison.
- **Operating plan:** an operator decision card, recorded SOC/fuel state, an expandable schedule explanation, and direct access to plan review or impact analysis.
- **Hourly exploration:** linked dispatch/SOC charts with safety and reserve lines, shortage bars, a time-range brush, an hour selector, and a source-to-demand energy flow. The compact mobile view retains all source and destination values.
- **Dataset Explorer:** inspect the exact demand, weather, available generation, dispatch and source labels captured for a run. Filter missing weather or supply shortages. Export all columns for the selected hours as a UTF-8 CSV readable in Excel on Windows.
- **Impact analysis:** compare optimized and reactive operation for the same saved inputs. View fuel, cost, emissions, service, generator starts, ending SOC and shifted flexible energy. Negative differences mean optimized minus reactive, not automatically a saving.
- **What if?:** a six-scenario resilience matrix linked to one baseline, alongside custom experiments. Only runs with the exact preset overrides fill the preset matrix; custom variants remain in history. Runs execute sequentially.
- **Data & assumptions:** readable equipment cards, source age, configuration version, missing-weather checks and manual-reading timestamps. Raw JSON remains available under developer details. Historical runs also expose their own Dataset Explorer and Impact analysis.

The comparison controller uses current-hour renewables, then storage down to the configured operating reserve, then diesel. Flexible tasks run at the earliest possible allowed hour; unfinished work is retried within its window. Fuel availability, start limits, generator minimum loading, allowed hours, battery power and efficiency are enforced. It has no weather look-ahead or hard terminal SOC constraint. This is an illustrative policy, not an assertion about how an actual operator behaves.

Cost differences are flagged as not like-for-like when critical/normal/flexible service differs (tolerance 0.001 kWh), terminal SOC differs (0.1 percentage points), or the reactive terminal reserve is missed. Ending storage is shown explicitly; no lifecycle-cost, measured-saving or physical-uptime claim is made. Explanations report observations in the saved solution and configured priorities; they do not claim a causal sensitivity analysis. Analysis is read-only and uses the stored snapshot, with controller version `reactive-v1` included in the response.

The map uses [Leaflet](https://leafletjs.com/) and bundled [Natural Earth public-domain land outlines](https://www.naturalearthdata.com/about/terms-of-use/), sourced from `ne_110m_land.geojson` in the Natural Earth vector repository, subset to the surrounding region and rounded to 3 decimal places. It makes no tile-service requests. Coastlines are for regional orientation, without administrative boundaries; this map is not suitable for navigation or precise surveying.

New authenticated, site-scoped endpoints:

```text
GET /api/optimization-runs/{id}/analysis
GET /api/optimization-runs/{id}/scenarios
```

ML remains deferred until issued forecasts can be checked against later observations. Regional historical weather alone is not site generation telemetry or proof of forecast accuracy.

### Django database administration

The database remains `backend/db.sqlite3`. To browse its records through Django Admin:

```sh
.venv/bin/python backend/manage.py createsuperuser
```

Open `http://127.0.0.1:8000/admin/` while the backend is running. A JeevanGrid application admin role does not automatically grant Django superuser access. Django Admin edits bypass the product's configuration validation and versioning; use it for inspection, and use the JeevanGrid forms for operational changes. Do not edit saved run snapshots or dispatch records.

### Checking these workflows

```sh
.venv/bin/python -m pytest backend/grid/tests -c backend/pytest.ini
.venv/bin/python verify_intelligence.py
```

The intelligence browser check uses the existing compact demo site (ID 2), creates one optimization and six stress-test records, checks CSV content and mobile layout, and saves screenshots under ignored `test-results/`. It does not modify equipment configuration. Backend coverage includes reactive energy balance across varied resources, hand-calculated fuel costs, service/storage comparison warnings, immutable snapshot use, and access restrictions.

## Demo data and real weather

The reference site uses approximate Leporiang coordinates, `27.2297, 93.3412`. The [2017 original study](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/joe.2017.0447) reports survey-estimated demand of **876.41 kWh/day**, **101 kW peak** and modelled PSC capacities of **600 kW PV, 100 kW wind, 200 kW generator, 400 kW converter and 3,000 kWh batteries**. These are research inputs/results, not verified present-day plant telemetry.

The generated reference load totals exactly 876.41 kWh with an 18:00 hourly peak of 101 kW before flexible load rescheduling. The critical/normal/flexible split is 30/60/10. The two other sites are clearly labelled hypothetical variants for comparing constrained equipment. Fuel curves, efficiencies, SOC limits, critical fractions, replacement costs and flexible-load assignments are declared assumptions.

Fetch real historical weather for the reference site (site ID 1 on a fresh database):

```sh
.venv/bin/python backend/manage.py fetch_history --site 1 --date 2025-01-15
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

Forecasts have a six-hour freshness gate. Manual readings include age/provenance but are operator-entered assumptions, not continuous telemetry. Confirmation records a human review only. A changed or superseded plan cannot be approved.

## Verification

Verified on this laptop: 57 backend tests passed; Django system/migration checks and the production frontend build passed. Chrome checks covered admin/operator workflows, searchable location lookup with automatic coordinates, and mobile layout. Real Open-Meteo forecasts and NASA POWER historical data each produced 24-hour plans. The three demo baseline solves took approximately 0.2–1.0 seconds, and the portfolio pack completed 18 scenario runs. These are local measurements, not a guarantee for arbitrary configurations or hardware.

```sh
cd backend
../.venv/bin/python -m pytest -q
../.venv/bin/python manage.py check
../.venv/bin/python manage.py makemigrations --check --dry-run
cd ../frontend
npm run build
```

The browser smoke test needs both services running, Playwright (`pip install playwright`) and Chrome. Set `CHROME_PATH` for your OS if needed; default is Linux Chrome at `/opt/google/chrome/chrome`.

`requirements-tested.txt` records the exact Python versions used during verification; `frontend/package-lock.json` locks the Node dependencies.

```sh
.venv/bin/python browser_check.py
```

It exercises admin login, optimization, review, simulation, wizard creation, readings, archival, resilience assessment and operator mobile access. It creates and archives one clearly named test site. Screenshots are under `test-results/` and ignored by git.

`verify_demo.py` additionally checks the compiled frontend at port 4173 and both live weather integrations. Start it with `npm run preview -- --host 127.0.0.1` from `frontend` after building, while the Django backend is running. The verification script creates new baseline/scenario history for the three seeded sites and writes `test-results/verification.json`.

## Structure and API

`backend/grid/optimizer.py` is a pure solver accepting a frozen input snapshot. Weather and PV modelling prepare that input; Django persists output. Scenario runs use the same solver with a copied snapshot and scoped overrides. `backend/grid/models.py` contains explicit ORM entities; equipment fields live in validated JSON objects. `frontend/src/main.jsx` contains the React views and charts.

API routes follow the plan without trailing slashes. Additional endpoints: `/api/auth/refresh`, `/api/auth/logout`, `/api/members`, `/api/defaults`, `/api/locations/search`, and `GET /api/optimization-runs` with optional `site_id` or `kind=scenario`. A baseline run returns status, explanatory action, metrics, intervals, version, source metadata, review trail and snapshot. Scenario responses add baseline metrics, overrides and deltas. All site/run lookups are scoped to organization and assignment.

SQLite is intended for the local demo. Move to PostgreSQL and a job queue for concurrent multi-user deployment; the Django ORM and migrations preserve that path. Before deploying, provide a real `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0`, configure allowed hosts, TLS, credential management and remove demo account defaults. No external deployment is performed by this project.
