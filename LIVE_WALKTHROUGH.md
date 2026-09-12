# JeevanGrid: live simulation and forecasting walkthrough

All equipment actions in this release execute in a software microgrid. Weather APIs remain available in the existing Operating plan screen. The Live Control demonstration uses explicitly simulated weather, demand and equipment. The live optimizer is supervisory: it recalculates hourly dispatch every five simulated minutes. It does not model voltage, frequency, protection relays or physical generator communication.

## 1. Update and launch

From the project directory on Linux:

```bash
cd /home/lenovo/jeevangrid
source .venv/bin/activate
python -m pip install -r requirements.txt
python backend/manage.py migrate
python dev.py
```

On Windows, from your project directory:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python backend/manage.py migrate
python dev.py
```

For a fresh database only, run `python backend/manage.py seed_demo` before starting. Do not reseed an existing database simply to test the new features.

Open **http://127.0.0.1:5173**. Demo accounts, if seeded:

| Account | Password | Access |
| --- | --- | --- |
| admin@jeevangrid.local | JeevanGridDemo!26 | All organization sites; engineering configuration and ML training |
| operator@jeevangrid.local | JeevanGridDemo!26 | Assigned sites; simulation, events and command review |

The launcher now starts three processes. A plain Django `runserver` does not supply the new WebSocket stream. To start them separately:

```bash
# Terminal 1, activated environment
cd backend
python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000

# Terminal 2, activated environment, backend directory
python manage.py run_live_worker

# Terminal 3, frontend directory
npm run dev
```

If port 8000 or 5173 is occupied, stop the previous JeevanGrid server using Ctrl+C in its terminal, then start the launcher. Do not stop unrelated services. If the page says the stream is disconnected, check the ASGI server; if the stream connects but telemetry is stale, check the worker.

## 2. Open the live workspace

1. Sign in as admin, open **Sites**, then select a site.
2. Select **Live Control**, next to Operating plan.
3. Confirm the connection reads **Live stream connected**.
4. Leave **Clock speed = 10×**, **Dispatch preference = Balanced**, and both forecast options enabled.

A fresh session starts at local noon, using the saved equipment configuration and starting reading. At 10×, five simulated minutes take approximately 30 wall-clock seconds. The clock pauses while the worker is busy calculating; it is a demonstration clock, not a hard real-time timing guarantee. Use 1× for approximately real elapsed-time playback or 120× for a quick full-day replay.

## 3. Test demand ML and solar correction

1. Click **Train on 90 simulated days**.
2. Wait for the training report. It contains 2,160 hourly records.
3. Inspect the two rows: Demand and Solar residual correction.
4. Compare **Baseline test error** and **ML test error**. Both are MAE in kW: average absolute prediction error. Lower is better.
5. Open **Evaluation dates and held-out forecast graph**. Training uses the first 65% of timestamps, calibration the next 17%, and testing the final 18%. No random train/test shuffle is used.
6. Click **Download training dataset CSV** to see the actual records used.

The demand model learns from hour, weekday, temperature, the demand template and physics PV estimate. The solar model learns the residual: observed solar minus the physics estimate. A model is selected only if it reduces calibration MAE by at least 2%. The untouched test period reports its performance. If a model fails this check, its baseline remains active.

Synthetic backtest improvement demonstrates that the software works; it does not establish accuracy for an Indian village. Models trained on simulated observations are only eligible for simulated runs. Site configuration changes invalidate model eligibility until retraining.

**Optional real observations:** upload 30–366 days of consecutive hourly CSV records, under 5 MB, with columns:

```csv
timestamp,temperature,baseline_demand_kw,physics_solar_kw,demand_kw,solar_kw
```

Use timestamps with timezone offsets. Demand here is fixed critical + normal load; scheduled flexible jobs are handled separately. `physics_solar_kw` is the uncorrected PV forecast and `solar_kw` is observed generation. For an operational forecast backtest, input weather must be the weather forecast available when the prediction was issued. Hindsight weather is not evidence of real forecasting performance.

## 4. Test simulator and live telemetry

1. Click **Start simulation**.
2. Wait for the first fresh sample, normally within a few seconds.
3. Watch the clock, solar, wind, demand, battery SOC, generator power and fuel values.
4. Read battery charging/discharging power and the energy balance residual below the cards.
5. Open a second browser tab on the same site's Live Control page. Both tabs observe the same session; opening another page does not advance the clock twice.

The worker advances the plant, independent of browser connections. Battery changes include charging and discharging efficiency, power limits and minimum/maximum SOC. Diesel consumes fuel through the configured fuel curve. If supply is insufficient, the simulator supplies critical demand first and reports the shortage. Historical samples are stored at approximately one simulated minute or longer; the live stream updates every two seconds.

## 5. Test five-minute replanning

1. Note the plan number in **Projected next 24 hours**.
2. Wait for five simulated minutes: about 30 seconds at 10×, plus solve time.
3. The plan number and **last plan** time should update without clicking Optimize.
4. Open **Command audit and event timeline**. Look for **Five-minute rolling update**.
5. Click **Cloud cover −75%**. On the next worker tick, generation drops and an event-triggered plan is created.

Each replan uses current simulated SOC, remaining fuel, generator state, generator run time and remaining flexible-job energy. Completed flexible work is not scheduled again; the original deadline is retained. All runs save their input snapshot and can be opened from the live panel or Plan history.

## 6. Test proposal → approval → execution → verification

1. Inspect **Review proposed setpoints**. It shows the generator setpoint, battery balancing policy and scheduled flexible work.
2. Click **Approve simulated command** before the proposal's displayed expiry time.
3. Open **Command audit and event timeline**.
4. Expect `approved`, then `executing`, then `verified` when a new telemetry sample confirms the generator setpoint. A running generator may take time to reach a new output because of its ramp limit.
5. On a later proposal, enter a reason and click **Reject**. Its status becomes `rejected`; the proposal is not applied.

Proposals expire after five simulated minutes and new plans supersede unapproved proposals. Stale telemetry, changed configuration, unassigned sites and invalid command transitions are rejected by the backend. The initial command may correctly request zero diesel when solar is sufficient. To see a diesel start recommendation, introduce clouds and low battery, or test an appropriately sized site with an evening deficit. A recommendation for a future generator start is not a reason to switch it on immediately.

The simulated battery balances supply within its bounds between operator decisions. Approval applies a generator setpoint and flexible-load setpoints; the displayed planned battery power is advisory within that balancing policy. Physical hardware commands are not implemented.

## 7. Test generator operational rules

1. Pause the simulation and click **Configure** for the site.
2. On Equipment and engineering limits, inspect:
   - Minimum generator run (hours).
   - Minimum cooldown (hours).
   - Generator ramp limit (kW/hour).
3. For a dedicated test site, use minimum run **2 hours**, cooldown **1 hour**, and a ramp limit appropriate to its rated power.
4. Save and start a new session. Configuration changes cause an existing session to pause; old runs retain their settings.
5. Inspect the saved plan's hourly dispatch and the command audit. Start/stop proposals must respect the remaining minimum run/cooldown. Output changes during operation follow the ramp.

The hourly optimizer allows startup/shutdown to step through minimum stable power, in addition to the ramp allowance. The simulator ramps operating output at its smaller timestep. A forced generator fault can stop equipment immediately; an approved command can fail if current operational constraints prevent it. These failures are shown in the audit. Maximum starts and allowed operating hours continue to apply. Near the 24-hour planning boundary, minimum-run obligations beyond the horizon are carried by the next replan's current operating state rather than a 48-hour model.

## 8. Test conservative forecasting

1. With a trained model, inspect the forecast-bounds explanation in the projected-plan card.
2. **Conservative forecast** uses a lower solar estimate and upper fixed-demand estimate.
3. Pause, disable the checkbox, then start a fresh session using the same starting reading.
4. Compare the initial saved snapshots and forecasts. With conservative planning enabled, planned solar cannot exceed the central estimate and fixed demand cannot fall below it.

Bounds use empirical 10th/90th percentiles of calibration residuals when a model is eligible. Without one, they use explicit stress assumptions: solar −20%, demand +10%. These are not guaranteed probabilities or protection against every outage. Plans may use more diesel or retain more energy, but that outcome depends on the site.

## 9. Test cost versus emissions

1. Click **Compare strategies**.
2. Compare Lowest cost, Balanced and Lowest emissions in the resulting table.
3. Every row uses the same snapshot, constraints and critical-service priority.
4. To operate the simulator with a chosen strategy, pause, choose **Dispatch preference**, then start a new session.

Lowest cost minimizes the existing operating objective. Balanced adds diesel CO₂ multiplied by the configured carbon value (default INR 5/kg); carbon valuation is shown separately from dispatch cash and battery wear. Lowest emissions minimizes diesel emissions after protecting achievable critical, normal and flexible service, then breaks ties by cost. Some sites will produce identical plans because diesel cost and emissions already point in the same direction. The interface does not manufacture a trade-off.

## 10. Test outages, evidence and guided demonstration

1. Start a session and approve an initial proposal.
2. Apply **Cloud cover −75%**, then **Battery at 25%**.
3. Inspect the new plan and approve a current proposal if appropriate.
4. Apply **Generator outage**. Verify generator output becomes zero and a new plan appears.
5. Inspect **Observed in this software simulation**: critical service, unserved energy, diesel, cost, CO₂ and verified commands.
6. Click **Restore conditions** to clear clouds, elevated event demand and the generator outage. It does not refill fuel, recharge the battery or erase accumulated shortages.
7. Pause and click **Export evidence**. The JSON includes site, session, metric basis and event timeline.
8. Open the built-in **Guided demonstration · five steps** for the short presentation sequence.

The projected plan is what the optimizer expects. Evidence cards are what the simulated plant actually delivered during the session. A large battery may sustain all critical service through a short outage. A constrained site may lose supply. Both are valid and must be reported honestly. No diesel saving or 100% critical-service result is hard-coded. A session ends after 24 simulated hours; starting again creates a new record and retains the old database history.

## 11. Database and API inspection

The actual local database remains `backend/db.sqlite3`. New tables:

```text
grid_livesession
grid_telemetrysample
grid_controlcommand
grid_forecastmodel
```

Existing `grid_optimizationrun` and `grid_dispatchinterval` hold live plans with mode `live_simulation`. New records are also registered read-only in Django admin at **http://127.0.0.1:8000/admin/**. A Django superuser account is separate from the seeded product admin role.

Authenticated endpoints:

| Endpoint | Purpose |
| --- | --- |
| GET/POST `/api/sites/{id}/live` | Read state, start or pause a session |
| POST `/api/sites/{id}/live/events` | Inject a supported simulated event |
| POST `/api/sites/{id}/live/commands/{command_id}` | Approve/reject a proposal |
| POST `/api/sites/{id}/live/strategies` | Compare all three objectives |
| GET/POST `/api/sites/{id}/forecast-model` | Inspect/train models; admin required for training |
| GET `/api/sites/{id}/forecast-model/dataset` | Download training data |
| WS `/ws/sites/{id}/live` | Authenticated, read-only live stream |

The WebSocket expects an access token in the first JSON frame (`{"access":"..."}`), never in its URL. Commands go through authenticated HTTP APIs. Organization/site permissions are checked for both transports. The stream reconnects after access-token refresh. One worker process is enforced using an OS file lock; SQLite remains appropriate for this single-worker local demo.

## 12. Automated verification

```bash
cd backend
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
```

From `frontend`, run `npm run build`.

`verify_live.py` is a browser acceptance script for an **isolated copy** of the app/database, served on frontend 5183 with backend 8011. Set `JG_TEST_URL` to change the frontend URL and `CHROME_PATH` for the browser executable. It trains a model and creates simulation records, so do not point it at a shared production database. It tests live connection, training download, command verification, events, strategy comparison, evidence download and mobile overflow.

Implementation references: [Django Channels security](https://channels.readthedocs.io/en/stable/topics/security.html), [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html), and [time-aware model evaluation](https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html).
