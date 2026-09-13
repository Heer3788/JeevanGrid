# JeevanGrid — landing page to final-round demonstration

## Your opening sentence

> JeevanGrid helps rural microgrid operators decide how to use solar, wind, batteries and diesel together—protecting essential supply while making fuel, cost and emissions tradeoffs visible.

Keep the optimizer central. The AI assistant makes operations easier; it does not replace the energy model. The digital twin demonstrates changing conditions without claiming physical equipment control.

## 1. Open the product

1. Keep the existing four services running. Do not start duplicate servers. If stopped, run `python3 backend/dev.py` from `/home/lenovo/jeevangrid`.
2. Open **http://127.0.0.1:5173/**. This is now the public landing page, even if a session already exists.
3. Show **Purpose → The workflow → Intelligence → The evidence → Architecture** using the sticky navigation. The right-side scroll indicator follows the current section; mobile has a menu button.
4. Under Intelligence, switch **Record readings / Generate a plan / Export evidence**. Explain that this is an illustration, not a database write. Real actions happen inside the authenticated app.
5. Click **Get started** or **Log in**. Both open the existing login at `/login`. No new public sign-up or account-registration flow has been added.
6. Use the **Agency administrator** demo account, or sign in as `admin@jeevangrid.local` using its existing password. The unmodified local demo password is `JeevanGridDemo!26`; never reset an existing password just for a recording.
7. You arrive at **http://127.0.0.1:5173/workspace**. This is the portfolio/dashboard URL now. Existing `/sites`, `/data`, `/assistant` and site-detail URLs are unchanged.

## 2. Show the network and permissions

1. On **Portfolio**, show the site map, critical service, diesel and cost per kWh. The seed added 108 modelled sites; the total includes existing sites too. Archived sites are excluded from the active count.
2. Open **People & access**. Find `jehanabad.ops1@jeevangrid.local`: it is assigned JG001–JG004.
3. Say: “Admins configure the network and engineering rules. Operators manage readings, plans and reviews only for assigned sites.”
4. Optional stronger proof: use a separate private-browser session to log in as that newly seeded operator with the demo password above. Show its four sites. Do not sign out the admin recording session.

## 3. Create a site — exact values for a rehearsal

This is an **assumed demonstration design**, not a surveyed installation. Record the full setup separately; for a five-minute video show a labelled time-lapse or the final Review/Save step. Do not spend the entire video typing.

### Location

1. **Sites → Add site**.
2. Site name: `Final Round Community Demo` (add a unique suffix if already used).
3. Search location: `Jehanabad`. Select the appropriate Bihar match and verify the filled state/district/coordinates. Geocoding requires internet.
4. For this modelled example, coordinates may be set to **25.21, 84.99**, state **Bihar**, district **Jehanabad**, timezone **Asia/Kolkata**. These are a regional anchor, not a surveyed plant position.
5. Select **jehanabad.ops1@jeevangrid.local** under assigned operators. Click **Continue**.

### Equipment

The starting template is much larger than this example. Replace the values below; do not accidentally leave its 600 kW PV or 3,000 kWh battery.

| Section / field | Enter |
| --- | --- |
| Solar rated capacity | 20 kW |
| Solar tilt / azimuth | 25° / 180° |
| PV derating / inverter efficiency | 0.90 / 0.96 |
| Wind rated capacity | 0 kW; leave the unused curve parameters at their defaults |
| Battery capacity | 40 kWh |
| Minimum / operating reserve / maximum SOC | 20% / 30% / 95% |
| Maximum charge / discharge power | 10 kW / 8 kW |
| Charge / discharge efficiency | 0.95 / 0.95 |
| Diesel rated / minimum stable power | 8 kW / 2 kW |
| Minimum generator run / cooldown | 2 hours / 1 hour |
| Generator ramp limit | 8 kW/hour |

### Demand & loads

1. Daily energy **60 kWh**, reference peak **8 kW**, critical share **40%**, flexible share **10%**. Normal share is therefore **50%**.
2. Rename the existing flexible load to **Drinking-water pump**. Set maximum power **1.5 kW**, required energy **4 kWh/day**, earliest hour **9**, latest hour **16**.
3. Click **Add load**. Name **Community workshop**; maximum power **1 kW**, required energy **2 kWh/day**, earliest hour **11**, latest hour **16**.
4. The tasks total **6 kWh = 10% × 60 kWh**. They are not added on top of that daily demand. Click **Continue**.

### Costs & rules

| Field | Enter |
| --- | --- |
| Fuel slope / no-load fuel | 0.26 L/kWh / 0.24 L/hour |
| Generator start cost | ₹0 per start |
| Diesel price / default fuel stock | ₹94/L / 30 L |
| Emissions factor | 2.68 kg CO₂/L |
| Battery replacement cost | ₹480,000 |
| Lifetime discharge throughput | 120,000 kWh |
| Critical-service / renewable target | 100% / 70% |
| End-of-plan SOC reserve | 30% |
| Maximum generator starts | 4 |
| Allowed generator hours | All 24 hours selected |
| Advanced penalties | Keep the existing defaults |

These prices and efficiencies are declared assumptions, not current vendor quotations. Battery wear is ₹480,000 / 120,000 = **₹4 per discharged kWh**.

### Review, save and plan

1. **Continue → Review**. Confirm solar/wind **20/0 kW**, battery **40 kWh**, diesel **8 kW**, daily demand **60 kWh**.
2. Click **Save site configuration**. This creates a Site, its configuration records, assignment and scheduled loads.
3. On its workspace click **Update readings**: SOC **60%**, fuel **30 L**, diesel price **94**, demand multiplier **1**, generator available **checked**, generator running **unchecked**. Event: `Assumed final-round demo inputs`. Click **Save readings**.
4. Set Weather source to **Demo weather** and click **Generate plan**. Explain that demand and weather here are simulated; no sensors were used.
5. Inspect the 24-hour charts and any warnings. A feasible plan is not necessarily a proved optimum; keep the actual solver label visible.

## 4. Use the prepared, verified demonstration site

For the remaining recorded shots, use **Sites → search `JG004` → JG004 Jehanabad Health 36**. Explain: “Now I’ll use our prepared reference example to demonstrate the operating workflow.” This is site **16** on the current laptop; use the name on other installations.

It represents 36 modelled households, essential clinic demand and a water pump. The seed includes real regional NASA weather; its household readings are not real telemetry. A saved test using simulated weather preserved 100% critical service when solar was reduced by half, with diesel increasing from approximately 0 to 1.57 L. Those figures belong to saved plan **1799** and scenario **1806**, not every future run.

### Plan

1. Open **Plan**. Show the Weather source choices: **Demo weather**, **Live weather forecast**, **NASA historical replay**.
2. To show real historical weather select NASA and date **2025-01-15**; generate a plan. For a predictable offline recording explicitly select Demo weather instead. Never rename the fallback “live.”
3. Show **Critical energy served**, **Dispatch cost**, **Diesel required**, **Renewable generation**, then the generation and SOC charts.
4. Expand **Costs, emissions & explanation**. Explain fuel + starts + battery wear; emissions follow diesel litres and the configured factor.
5. Open **Compare with reactive**. Compare like-for-like service and input conditions. These are modelled strategy differences, not measured field savings.
6. **Review plan** → reason `Reviewed for the final-round demo` → **Confirm plan**. Show the saved review. Overrides require a reason too.

### Test and replay

1. **Test plan → Change conditions**: inspect the six automatic checks (cloudy, low wind, high demand, expensive fuel, generator outage, low battery).
2. Open the cloudy result to show baseline-versus-scenario fuel, service and SOC.
3. Expand **Try a custom combination**. Change solar to **0.5×**; click **Compare with original plan**. The saved equipment is unchanged.
4. **Live replay → Clock speed 30× → Start replay**. Wait for fresh telemetry/connection.
5. Click **Cloud cover**. Show solar availability changing and the rolling plan responding.
6. Enter a command review reason and click **Approve simulated command**. Wait until **Command history & evidence** visibly reports a verified command.
7. Show the new proposal/evidence and click **Pause replay**. A command can correctly keep the generator off now while proposing diesel later—do not promise an immediate generator start for every event.
8. Say clearly: “This is software control of a simulated microgrid, not physical hardware control.” Regular replanning follows the simulated five-minute clock; dispatch intervals remain hourly.

### Agentic assistant and database proof

1. On JG004 click **Ask JeevanGrid → New chat**. This scopes requests to the demo site.
2. Paste:

```text
For JG004 Jehanabad Health 36, record battery SOC 45%, fuel 20 litres, diesel price 94 INR/L, generator available and off. Event: final-round demonstration.
```

3. Wait for success. Close chat and reopen **Update readings**; show the changed values. This creates a real `grid_sitereading` row. It does not immediately replace the previous plan.
4. Optional next prompt:

```text
Generate a 24-hour plan for JG004 Jehanabad Health 36 using simulated weather.
```

5. This creates an OptimizationRun and 24 hourly DispatchIntervals, plus the six background scenario checks. Allow roughly 15–25 seconds for the whole workflow, not just the solve.
6. Optional export prompt:

```text
Export the latest operating plan for JG004 Jehanabad Health 36 as a PDF report.
```

7. Open the report link or use chat History to show the already generated PDF. All six tested prompts and SQLite inspection commands are in [the detailed prompt/evidence guide](FINAL_ROUND_SHOWCASE.md).

Narration: “The LLM interprets the request. Django checks permissions and values. Registered workflows execute the actions, and persisted records are independently verified. Dispatch comes from the mathematical solver.”

### Data and ML

1. **Data explorer** → choose JG004 and a saved run.
2. Switch **Demand / Weather / Dispatch / Sources** and click **Download CSV**.
3. Expand **How this site's demand was calculated**: show appliance counts, watts, hours, priorities and pump-energy calculation. Expand its source/assumption section.
4. Expand **Demand forecasting & model datasets**. Show the existing baseline-versus-ML error values and **Download training data**.
5. To train again: **Train on simulated data**. This saves a model artifact containing 90 days × 24 hours = **2,160 synthetic training rows**. A CSV can replace synthetic training data.
6. Explain **XGBoost demand prediction**, **XGBoost solar-residual correction**, **pvlib solar physics** and **PuLP/HiGHS MILP optimization**. Prediction estimates conditions; optimization chooses decisions within constraints.
7. Be precise: current standard Plan/replay screens use saved demand and physics. ML training/evaluation is implemented, but not automatically enabled in those screens. Synthetic test performance is not real-world forecasting accuracy.

### Portfolio and history

1. Return to **Portfolio** at `/workspace`.
2. Select **JG001 Jehanabad Household 36** and **JG005 Jehanabad Household 64**—leave their original NASA plans unchanged for a comparable horizon.
3. Click **Open detailed comparison** below the table. Prepare this modal before recording to avoid scrolling through 100+ sites on camera.
4. Show critical service and normalized cost/diesel metrics, not just absolute totals for differently sized communities.
5. Saved runs remain accessible through **Recent plans**, Data explorer and report exports. Changes to the current configuration do not rewrite historical snapshots.

## Five-minute edit plan

| Time | Shot | Narration focus |
| --- | --- | --- |
| 0:00–0:30 | Landing hero → scroll-spy Intelligence → architecture | Introduce the rural/off-grid problem. “One energy decision, with optimization, transparent inputs and verified AI workflows.” |
| 0:30–0:45 | Get started → existing login → Portfolio | “Built for operators and agencies, with role-based site access.” |
| 0:45–1:25 | Condensed site creation: Location → Equipment → Add load → Review/Save | “Capacities, safety limits, fuel costs and load priorities become constraints.” Label setup time-lapse/edits. |
| 1:25–2:05 | Open prepared JG004 → weather choices → plan charts | “Weather becomes available generation; the optimizer schedules the next 24 hours.” |
| 2:05–2:30 | Critical service, diesel, emissions → reactive comparison → review | “Every recommendation exposes its cost and reliability consequences.” |
| 2:30–3:00 | Cloudy test and custom sliders | “Less solar changes the mix. We show the backup required to preserve essential demand.” |
| 3:00–3:45 | Live replay → cloud event → approve → visible verification → pause | “Our software twin tests changing conditions and operator-approved responses.” |
| 3:45–4:15 | Scoped chat → reading prompt → saved state/database row | “AI invokes a real authorized workflow. This is a database change, not merely generated text.” |
| 4:15–4:40 | Inventory, source labels, CSV and ML evaluation | “The assumptions are inspectable; prediction models have a defined, evaluated role.” |
| 4:40–5:00 | Prepared portfolio comparison + brief People & access shot | “Protect essential supply, use renewable potential and quantify the diesel, cost and emissions tradeoff—across the network.” |

## Last-minute checklist

- Keep the core energy charts on screen longer than the chatbot.
- Prepare two-site comparison, dataset and PDF tabs before recording.
- Record full setup separately and label any sped-up footage.
- Do not expose API keys or real passwords in the recording.
- Fresh weather needs network; simulated mode must remain visibly labelled.
- Pause replays after the take. Never claim voltage/frequency or physical-generator control.
- Read metrics from the displayed run. Do not overlay “savings” if the calculation does not support it.
- The public landing has no database-writing buttons or registration endpoint. Its workflow card is clearly an illustration.

## Verified implementation routes

| URL | Purpose |
| --- | --- |
| `/` | Public landing page |
| `/login` | Existing login; signed-in users continue to the workspace |
| `/workspace` | Admin portfolio / operator assigned sites |
| `/sites/new` | Admin site-creation wizard |
| `/sites/16` | Prepared JG004 demonstration on this laptop |
| `/data` | Data explorer and model evaluation |
| `/team` | Organization roles and assignments |
| `/assistant` | Chat workspace and history |

The mobile and desktop landing, scroll spy, login hand-off, signed-in routing and logout are covered by `frontend/tests/verify_landing.py` using API fixtures. The existing real-data portfolio and chat regression checks remain separate.
