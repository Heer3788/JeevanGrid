# JeevanGrid: five-minute final-round showcase

**Updated landing-first recording guide:** [Landing → login → site creation → complete demo](LANDING_TO_DEMO_VIDEO.md). Start at `/` for the landing page, use `/login` for the existing login, and `/workspace` for the portfolio. The guide below retains the six verified prompts and database evidence commands.

## The story

**An operator must keep a community supplied when renewable availability changes.** Configure the microgrid, plan its energy mix, test a disruption, review the response and inspect the evidence. Chat, ML, maps and exports support that decision; they are not substitutes for the optimizer.

Opening pitch (about 25 seconds):

> Rural microgrids need more than solar panels: operators must decide when to store energy and when diesel backup is genuinely necessary. JeevanGrid combines weather, community demand and equipment limits to plan the next 24 hours. We test disruptions, prioritize essential loads and explain the fuel, cost and emissions consequences—before the operator acts.

## Prepare before recording

1. Open `http://127.0.0.1:5173`, click **Get started**, and sign in as `admin@jeevangrid.local`, using the existing admin password. The unmodified local demo default is `JeevanGridDemo!26`. Do not reset an existing password just for the video. The dashboard is now at `/workspace`.
2. Keep all four services running: React/Vite, Django/ASGI, live simulator/assessment worker and assistant/report worker. If already running, do not start duplicates. Otherwise `python3 backend/dev.py` from the repository root starts them together.
3. Use **JG004 Jehanabad Health 36**, site ID **16** on this laptop. Other installations get different database IDs; the name is stable. It has 36 modelled households, essential clinic loads and a water pump. Equipment: 9.35 kW PV, 30.72 kWh battery and diesel backup; inspect the actual configuration for all values.
4. Have these browser tabs ready: Portfolio, this site's workspace, Data explorer for this site, and (optional) Django admin/SQLite for the database proof. Record at 100% zoom with the API key and terminal secrets hidden.
5. Run the six prompts below once before recording. Fresh chats retain the old evidence in History. Allow the planning checks to finish; train the demo model in advance if recording time is tight.
6. For weather, show the three choices. Historical NASA records are already populated. A live forecast needs network availability. If live retrieval fails, explicitly select **NASA historical replay** or **Demo weather**; never describe that fallback as live weather.
7. For a repeatable 24-hour plan, use **Demo weather** and state that it is simulated. The portfolio's original plans use real regional NASA weather for 15 January 2025. These are two different runs, not conflicting data.
8. Pause any previous replay before starting a fresh one. Keep a short backup screen recording of the already-tested replay and mark it as recorded software simulation if used.
9. Preselect two unchanged NASA-based sites (for example JG001 and JG005) in the Portfolio tab before recording. The detailed comparison action is below the table; pre-open it in a separate tab for the final 15-second shot. You can demonstrate operator-only access in a second browser profile using `jehanabad.ops1@jeevangrid.local` and the newly seeded demo password, without signing the recording's admin session out.

## Earlier dashboard-only reference shots

For the final recording, use the **updated five-minute edit plan** in [Landing to demo](LANDING_TO_DEMO_VIDEO.md#five-minute-edit-plan), which includes the landing page and site creation. The older shots below are retained as supplementary narration, not the current recording order.

| Time | What to click/show | What to say |
| --- | --- | --- |
| 0:00–0:25 | Start on **Portfolio**; show the map and active-site count. | Use the opening pitch above. Add: “This portfolio includes 108 engineering-modelled examples with disclosed assumptions; it is not 108 monitored installations.” |
| 0:25–0:45 | **People & access** → show `jehanabad.ops1@jeevangrid.local` and its four assignments. Return to **Sites**, search `JG004`, open it. | “Agencies compare their network. Operators can plan and review only their assigned sites; engineering configuration is restricted to admins.” |
| 0:45–1:20 | **Configure site** → briefly show Location → Equipment → **Demand & loads**, the water-pump window and **Add load** → Costs & rules. Do not change/save random values for the shot. Return to site. | “A site has equipment capacities, battery safety limits, fuel costs and a demand profile. Essential demand is protected; a water pump can move into its allowed daytime window. Its energy is counted once. These constraints shape the actual schedule.” |
| 1:20–2:05 | **Update readings**: show SOC, fuel and generator availability. Close or save deliberately. In **Plan**, show the Weather source choices, select **Demo weather**, click **Generate plan**. Show recommendation, generation chart and SOC curve. | “Weather becomes available solar through a physics model and wind through a turbine curve. The optimizer balances supply and demand each hour, enforcing battery and generator limits. It returns a 24-hour renewable, battery and diesel schedule—not just a weather chart.” |
| 2:05–2:35 | Show Critical energy served, Diesel required, cost and emissions. Open **Compare with reactive**, then **Review plan** → enter a reason → **Confirm plan**. | “These are projected consequences of this plan. Cost includes fuel, starts and battery wear. The reactive comparison uses the same input conditions; any difference is a modelled benefit, not measured savings. The operator's review is saved.” |
| 2:35–3:05 | **Test plan → Change conditions**. Open a completed **cloudy** check and its side-by-side response. Briefly show the other checks and **Try a custom combination**. | “What if solar falls by half? The same optimizer recomputes the mix. In our tested example, diesel changed from about zero to 1.57 litres while critical service remained at 100%. Reliability can require more diesel on a bad-weather day; we show that tradeoff honestly.” |
| 3:05–3:50 | **Test plan → Live replay** → 30× speed → **Start replay** → **Cloud cover** → watch telemetry/new proposal → **Approve simulated command** → open **Command history & evidence** and show `verified` → **Pause replay**. | “This is our software digital twin. A cloud event changes telemetry and triggers rolling replanning; regular replanning follows the simulated five-minute clock. The operator approves the proposed response, then new telemetry verifies it. This controls the simulator, not physical equipment.” |
| 3:50–4:20 | On the site, click **Ask JeevanGrid → New chat**. Paste the reading prompt below. After success, show **Update readings** or the new SQLite row. Optionally open the previously generated PDF from chat History. | “The assistant invokes authorized application workflows. Here it actually saves an operating reading. Its completion is verified against database records. The optimizer—not the language model—calculates dispatch.” |
| 4:20–4:45 | **Data explorer** → select this site and saved run → Weather/Dispatch → **Download CSV**. Expand **How this site's demand was calculated** and **Demand forecasting & model datasets**. | “Every result exposes its inputs and source. Household and pump loads are traceable calculations; NASA weather is regional historical data. XGBoost demand and solar-residual models have separate held-out evaluations. These demo scores use simulated data, not field validation.” |
| 4:45–5:00 | Return to **Portfolio**; select two unchanged JG sites with the same NASA horizon and show **Open detailed comparison**. Finish on the reliability/cost comparison. | “Agencies can compare critical service, diesel and cost per supplied unit across sites. JeevanGrid's core is a transparent energy decision: protect essential supply, use available renewables and quantify the diesel, cost and emissions tradeoff.” |

Use actual figures on the selected saved run. If a new plan's figures differ, read those figures or show saved example run **1799** and its cloud result **1806**; do not recite old numbers over a different chart. IDs here refer to this laptop's verification on 13 September 2026.

The tested cloudy result is **not** a diesel reduction versus the original sunny case: it is proof that the system responds to reduced renewable supply. Use **Compare with reactive** for a separately computed strategy comparison, and quote savings only if that comparison actually reports them at comparable service.

## Copy-paste chat prompts: verified end to end

Open **Sites → JG004 Jehanabad Health 36 → Ask JeevanGrid → New chat**. This keeps the chat scoped to the new fictional demo site; the tested requests do not send existing organization-wide site names to Groq. Stay signed in as an admin for training; operator permissions apply to every action. Start a new chat before each independent prompt, and wait for completion.

### 1. Add an operating reading — best visible database proof

```text
For JG004 Jehanabad Health 36, record battery SOC 45%, fuel 20 litres, diesel price 94 INR/L, generator available and off. Event: final-round demonstration.
```

Observed: `readings.record` succeeded in about 4 seconds; **+1 SiteReading**. Reopen **Update readings** to see the values. A reading changes current state/configuration version; generate a new plan afterwards. Operator-entered here means a manual demo input, not measured telemetry.

### 2. Create a plan and its hourly rows

```text
Generate a 24-hour plan for JG004 Jehanabad Health 36 using simulated weather.
```

Observed: `plan.generate` succeeded in about 16 seconds including the background checks; **+1 base OptimizationRun +24 DispatchIntervals**, plus **6 ScenarioRuns, 6 scenario OptimizationRuns and 144 scenario DispatchIntervals**. The numerical solve itself is much faster than the complete chat/check workflow.

### 3. Save a lower-solar experiment

```text
For JG004 Jehanabad Health 36, test 50% lower solar availability against its latest plan and compare the results.
```

Observed: `test_and_compare`, about 6 seconds; **+1 ScenarioRun +1 scenario OptimizationRun +24 DispatchIntervals**. Saved site equipment is unchanged.

### 4. Record operator confirmation

```text
Confirm the latest operating plan for JG004 Jehanabad Health 36. Reason: reviewed for the final-round demonstration.
```

Observed: `plan.review`, about 4 seconds; **+1 OperatorDecision**. This is a plan review, not permission to control a real generator.

### 5. Create a downloadable PDF

```text
Export the latest operating plan for JG004 Jehanabad Health 36 as a PDF report.
```

Observed: `report.export`, about 8 seconds; **+1 ReportArtifact** with a completed content hash and PDF bytes. Open the report link in chat. It freezes the selected plan's evidence, not an editable screenshot.

### 6. Train and save the forecast model

```text
Train the demand and solar forecasting models for JG004 Jehanabad Health 36 using simulated training data.
```

Observed: `forecast.train`, about 6 seconds; **+1 ForecastModel**, containing two XGBoost model artifacts and **2,160 simulated hourly training rows**. See **Data explorer → Demand forecasting & model datasets** and download its CSV. These rows are stored inside the model's JSON artifact, not as 2,160 new LoadInterval rows.

The test evidence is `backend/.local/showcase-verification.json`. Groq/model availability, quotas, permissions and running workers are prerequisites—no remote API prompt is guaranteed forever. These six exact prompts were actually exercised, not just suggested. If chat is unavailable, use the equivalent manual controls; do not claim the failed chat action completed.

## Show the database change

From the project directory:

```sh
sqlite3 -readonly backend/db.sqlite3
```

Then run these separately inside SQLite:

```sql
.headers on
.mode column
SELECT id, site_id, timestamp,
       json_extract(data, '$.soc_pct') AS soc_pct,
       json_extract(data, '$.fuel_l') AS fuel_l,
       json_extract(data, '$.event') AS event
FROM grid_sitereading WHERE site_id = 16 ORDER BY id DESC LIMIT 3;

SELECT id, site_id, mode, status FROM grid_optimizationrun
WHERE site_id = 16 ORDER BY id DESC LIMIT 10;

SELECT run_id, COUNT(*) AS hourly_rows FROM grid_dispatchinterval
WHERE run_id IN (SELECT id FROM grid_optimizationrun WHERE site_id = 16)
GROUP BY run_id ORDER BY run_id DESC LIMIT 5;

SELECT id, run_id, decision, reason FROM grid_operatordecision ORDER BY id DESC LIMIT 3;
SELECT id, name, format, length(content) AS bytes FROM grid_reportartifact ORDER BY id DESC LIMIT 3;
SELECT id, site_id, provenance FROM grid_forecastmodel ORDER BY id DESC LIMIT 3;
.quit
```

Use before/after IDs or counts, not only the assistant's text, as proof of a database write. No need to open the SQLite file as a folder. For a GUI use your Django superuser at `/admin/`.

## What you can accurately claim

Implemented and visible: authenticated roles and assignments; site/location wizard; configurable solar/wind/battery/diesel models; aggregate and scheduled loads; manual state and CSV import; Open-Meteo/NASA inputs with explicit failure states; MILP schedules and safety constraints; explanations, normalized portfolio comparison and reactive reference; six automatic stress tests and custom scenarios; software telemetry/WebSocket replay, replanning and approved/verified simulated commands; decisions/history; structured chatbot workflows, new chats/history; CSV/PDF evidence; model training and chronological evaluation.

Important boundary: **the normal Plan screen and current Live replay deliberately use the saved demand profile and physics estimates.** ML training/evaluation exists, and forecast application logic exists in the backend, but do not say the model automatically drives these current UI flows. The replay starts with `use_ml=false` to preserve the selected plan's inputs. Cost/emissions strategy experiments also exist in the backend but have no current dedicated chooser in this minimal UI; do not hunt for a removed tab in the recording.

Not implemented as a field-ready product: physical IoT integration, protection relays, voltage/frequency control, grid synchronization, certified generator dispatch, live measured household telemetry, site-calibrated forecast validation or lifecycle finance. Describe real-time behavior as **software-simulated monitoring and rolling energy scheduling**, with one-hour dispatch intervals and simulated five-minute replanning—not a millisecond power controller.

For a judge who asks about wind, open the existing **Leporiang · study reference** equipment/source notes. Its hybrid capacities are study/model values. The 108 new solar-oriented examples do not invent installed wind resources.

## Technical rehearsal commands

```sh
# Local database/optimizer regressions (isolated test DB)
backend/.venv/bin/python -m pytest backend/grid/tests -c backend/pytest.ini

# Read-only browser check of the populated portfolio
backend/.venv/bin/python frontend/tests/verify_portfolio.py

# Explicitly creates demo records and makes real Groq calls scoped to the seed site
cd backend
.venv/bin/python manage.py verify_showcase --execute
```

Software replay acceptance, from the repository root:

```sh
backend/.venv/bin/python frontend/tests/verify_showcase_replay.py --execute
```

The replay check pauses its session afterwards. Re-running the chat check intentionally creates fresh evidence; re-running the seed does not duplicate its sites. Keep the seeded baseline and test evidence available as a fallback, without presenting recorded results as a new live execution.
