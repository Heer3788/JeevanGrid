# JeevanGrid: step-by-step feature testing

Open **http://127.0.0.1:5173/**. If the app is stopped, run `python3 backend/dev.py` from the repository directory. This starts Django, React/Vite and the Python simulation/assessment worker. Keep that terminal running.

Use **Agency administrator** first and **Dharnai · village demo** for the main walkthrough. This site has a useful combination of solar, storage and diesel. Exact results change with the starting hour and inputs, so compare the displayed run IDs and values instead of expecting fixed numbers.

The usual journey is **Portfolio → Site → Plan → Test plan → Review**. Data explorer supports inspection; People & access supports site assignments.

## 1. Login and account access

1. Click **Agency administrator** under **Explore the demo**.
2. Expect **Portfolio overview** and five navigation destinations: Portfolio, Sites, Data explorer, People & access, Account.
3. Open **Account**. Check the email, organization and Admin role.
4. Sign out, then test manual login using `admin@jeevangrid.local` and the seeded password `JeevanGridDemo!26`, unless you previously changed it.
5. An incorrect password should display an error and keep you on the login page.

The sample buttons use the default demo password only for accounts that still have it. An account with a changed password asks you to type that password. These are local demo identities.

## 2. Portfolio KPIs, filtering and map

1. Hover over **Active sites**, or focus its button using Tab. Read its definition.
2. Click the KPI. A separate popup dialog should show its value, definition and underlying site links. The card must keep its original size. Close with ×, Escape, or by clicking the dimmed backdrop.
3. Repeat for **Need review**, **Stress-tested sites** and **Decision horizon**.
4. In **Network locations**, choose Dharnai using **Inspect site**. The map should zoom and the adjacent details should change.
5. Click another marker; a marker can represent several sites at the same coordinates. Choose a site from its popup.
6. Click **India overview** to reset the map view.
7. In **Site reliability**, switch between **All sites**, **Need review** and **Checked**.
8. Select two site checkboxes. Comparable plans show a chart. Plans from different weather modes or starting hours show an explanation instead. Select at most five.

A completed stress assessment can still need review. “Checked” means the six tests finished, not that every scenario passed. Weather freshness, reserve risks and shortages can also affect portfolio status. The overview refreshes periodically; **Refresh overview** updates it immediately.

## 3. Open the site workspace

1. Open **Sites** and choose **Dharnai · village demo**, or use **Open site** on the map.
2. Confirm that the page identifies the site and district.
3. The only main tabs are **Plan** and **Test plan**.
4. **Update readings** records changing operating conditions. **Configure site** edits equipment and policy as an administrator.

## 4. Generate a plan and check the weather source

1. Under **Plan inputs**, choose **Demo weather**.
2. Click **Generate plan**.
3. Expect a new run ID, a named weather source, a dated 24-hour horizon and updated results.
4. Change the source to **Live weather forecast** without generating. Expect a notice that the selection has not been applied; the old result keeps its old ID and source.
5. Click **Generate plan**. The result should identify **Open-Meteo forecast**.
6. Choose **NASA historical replay**, enter `2025-01-15`, and generate again. Expect **NASA historical weather** on the saved result.
7. Return to **Demo weather** and generate a baseline for the remaining tests.

Forecast and historical requests require internet access. A failed request should show an error rather than silently claim simulated data is real weather. Changing weather does not change installed equipment or the saved demand profile; similar dispatch can be valid even when weather values differ.

## 5. Understand the recommendation and KPIs

1. Read **Next operator decision**. For example, it may recommend scheduling diesel backup.
2. Check **Starting state used in this plan**. These are the readings frozen into this saved plan.
3. Click each KPI to open its details dialog:
   - **Critical energy served:** percentage of essential energy demand supplied; inspect unserved kWh.
   - **Dispatch cost:** fuel, generator starts and estimated battery wear.
   - **Diesel required:** fuel, starts and combustion emissions.
   - **Renewable generation:** solar/wind share and related battery/curtailment details.
4. Expand **Costs, emissions & explanation** below the graphs and reconcile its components with the cost KPI.

Zero diesel can be correct for an oversized renewable/storage reference. The village demos normally demonstrate mixed supply. No displayed outcome should be interpreted as a measured field saving.

## 6. Inspect the hourly graphs

1. Select **Energy supply**. Hover over a bar to read one hour's solar, wind, battery discharge and diesel.
2. The dark line represents served demand plus battery charging. An unmet-demand line appears when relevant.
3. Move **Inspect dispatch hour**, or click a chart hour. Expect the time, battery reading, diesel output and supply/use breakdown to change together.
4. Select **Battery reserve**. Compare battery SOC against operating reserve and the safety minimum.
5. Select **Flexible work**. Inspect critical, normal and scheduled flexible loads.
6. Click an active slot in a flexible task's timeline; the selected hour should update.

Each bar covers one hour. Power is in kW; battery SOC is in percent. Unserved energy over an interval is in kWh.

## 7. Review or override a plan

1. Click **Review plan**.
2. Inspect critical service and minimum battery reserve.
3. Enter `Demo review: checked service, fuel and reserve.` and click **Confirm plan**.
4. Expect a success message and a saved review entry.
5. Open the review again. **Record override** stays disabled until a reason is entered. Use a clearly labelled demo reason when testing it.
6. A stale or infeasible plan must be regenerated before it can be reviewed.

Confirming a plan records a review. Simulated equipment commands have a separate approval step in Live replay.

## 8. Compare against reactive operation

1. Click **Compare with reactive**.
2. Read the **Reactive → Planned** values for diesel, cost, critical service and ending battery.
3. Use the hourly comparison selector to inspect battery charge, diesel output, demand served and unserved demand. The initial view is battery charge.
4. Read any comparison qualifications. A zero difference is a valid result, not necessarily a broken comparison.
5. Close with the close button or Escape. Focus should return to the trigger.

Both schedules use the saved inputs. Different constraints or ending storage can limit direct savings claims.

## 9. Explore the plan’s stress limits

1. Find **How much headroom do you have?** on Plan or Test plan.
2. Wait for **6 scenarios evaluated**. The chart starts with **Reserve margin**, measured in percentage points above or below the operating reserve. Negative bars mean the reserve is breached; the dashed line is the original plan.
3. Switch to **Diesel**, **Cost**, and **Unserved energy** to compare actual saved outcomes in the correct units.
4. Use **Inspect a scenario** or click a bar. The explanation, lowest battery charge, essential service and extra fuel should follow that scenario.
5. At a site without wind, the wind scenario should say **No wind installed**. A fuel-price test with zero diesel in both plans says **No fuel-price exposure**. These are excluded from the number needing attention.
6. **Existing reserve shortfall** means the baseline already goes below reserve. It should not be described as a new shortfall caused by the scenario.
7. Click **Inspect hourly response**. Switch among battery charge, diesel, supplied demand and shortages. Zero diesel does not hide changing battery charge.
8. Refresh the page. Completed checks are reused. Generate another plan to get a new assessment tied to its saved inputs.

The worker solves one scenario per iteration. A failed job shows its error and **Retry checks**. An infeasible schedule shows no fabricated numerical outcome. The checks describe modeled energy adequacy for these six conditions, not all possible failures.

## 10. Combine your own test conditions

1. Open **Test plan → Change conditions**.
2. Expand **Try a custom combination**.
3. Set solar availability to **0.5×**, demand to **1.5×**, and starting battery to **25%**.
4. Optionally enable **Include a generator outage**, from **18** to **24**.
5. Click **Compare with original plan**.
6. Expect a saved experiment and changed fuel, reserve, cost or service results. A sufficiently severe case may be infeasible.
7. Open **Saved result** to inspect its record and link back to the original plan.
8. Return to Plan; the original site's equipment and readings should remain unchanged.

Try changing one condition at a time first, then combine them. A wind change has no effect on a site with no installed wind equipment.

## 11. Replay the selected plan

1. Open **Test plan → Live replay**.
2. Choose **30×** speed for a readable demonstration. Five simulated minutes take about ten real seconds. Use **120×** for a faster check.
3. Click **Start replay**. If another plan's replay is active, pause it first.
4. Expect a connected stream, advancing simulated time, supply/battery charts and a proposed command.
5. Click **Approve simulated command**. Inspect **Command history & evidence** for approved/executing/verified progress; some intermediate states may pass quickly.
6. Wait for the simulated equipment to reach its setpoint. Generator ramps can delay verification.
7. Switch the chart from **Supply** to **Battery**.
8. Apply **Cloud cover**, then inspect the new proposal and original-versus-rolling-plan values.
9. Try **Demand +50%**, **Battery at 25%** or **Generator outage**, one at a time, approving the response when appropriate.
10. To test rejection, enter a **Command review reason** and click **Reject** on a pending proposal.
11. **Restore weather & generator** clears the weather/demand event multipliers and restores generator availability. It does not refill the battery or fuel.
12. Click **Pause replay**. Time and equipment should stop advancing.
13. Expand **Command history & evidence** and click **Export replay evidence**. Expect a JSON file.

Replay uses the selected plan's frozen inputs and is always a software simulation. Its rolling horizon shifts with time; comparisons to the original day are updated projections. Starting again creates a new replay rather than resuming the paused session.

## 12. Inspect history and export a saved run

1. Return to Plan and expand **Recent plans**.
2. Open a previous run. Expect its own immutable inputs, charts and results.
3. Expand **Review trail** to see recorded confirmations/overrides.
4. Click **Export run** for the run JSON.
5. Click **Inspect dataset** to open Data explorer with that site and run already selected.

Recent plans shows the latest eight entries. Data explorer's saved-run selector includes older runs and experiments.

## 13. Explore data and download CSV

1. Open **Data explorer** from the sidebar.
2. Select a site and saved run.
3. Expand **Input sources & data quality**, then read **Data behind this decision** for weather, demand and state provenance.
4. Switch between **Demand**, **Weather**, **Dispatch** and **Sources**.
5. Try **Rows → Supply shortages** and **Missing weather**. An empty result is valid when there are no matching hours.
6. Choose **All hours** and click **Download CSV**.
7. Check that the CSV contains the selected run's records. Filters also apply to the export.
8. Change the saved run and confirm its ID and data change together.

## 14. Try model training and CSV uploads

As Admin, select a site in Data explorer and expand **Demand forecasting & model datasets**.

1. Click **Train on simulated data**.
2. Expect a record count/provenance and demand/solar test errors for the baseline and model.
3. Click **Download training data**.
4. Use **Upload training CSV** to test a dataset with the required columns:
   `timestamp,temperature,baseline_demand_kw,physics_solar_kw,demand_kw,solar_kw`.
5. Training data must contain 30–366 days of consecutive hourly, timezone-aware, past observations and be under 5 MB. Missing columns should produce an error.

This section evaluates models. The current Plan action uses the demand profile and physics model, and the simplified replay starts with ML disabled. Training alone does not change those displayed dispatch results.

To test **Import the site's daily demand profile**, use a separate QA site from step 16. Import [the sample CSV](../../frontend/tests/fixtures/demo-load-profile.csv), then generate a new plan and inspect its demand. It must have exactly 24 consecutive hourly rows, the four documented columns and nonnegative power. Removing one row should cause validation to reject it. The import changes the site's future planning inputs, while saved snapshots remain intact.

## 15. Update changing site readings

Use a QA site if you want to preserve the existing demonstration.

1. Open **Update readings** and record the existing values.
2. Set battery charge to **25%**, reduce fuel, and add `Manual acceptance test` as local context.
3. Save. Expect a message asking you to generate a new plan.
4. Generate and inspect **Starting state used in this plan** and the new metrics.
5. Restore the earlier readings, then generate again.
6. Try an invalid battery percentage; saving must show validation feedback.

Reading changes are persistent site inputs. Custom scenarios from step 10 are the better place for temporary experiments.

## 16. Create and configure a QA site

1. As Admin, open **Sites → Add site**.
2. Name it `QA walkthrough`.
3. Search a location with at least three characters and verify the state, district, coordinates and timezone.
4. Assign the **Microgrid operator**.
5. Continue through **Equipment**, **Demand & loads**, **Costs & rules**, and **Review**.
6. Inspect solar/wind capacities, battery SOC/power limits, generator constraints, flexible task windows, prices, renewable targets and allowed generator hours.
7. Keep a valid configuration and click **Save site configuration**.
8. Generate a plan on the new site.
9. Open **Configure site**, make a small labelled change, save and generate again. Old runs must retain their original settings.
10. Required fields, SOC ordering, invalid task windows and inconsistent energy totals should produce validation feedback.

Use **Add load** and **Remove load** to test flexible-task editing. Task energy must remain consistent with the configured flexible demand share.

## 17. Check people, assignments and restricted access

1. Open **People & access**. Inspect the actual accounts and assigned sites.
2. Change an operator assignment under **Configure site → Location** and save.
3. Sign out and use **Bihar demo operator**. By default, it should see only Dharnai, plus Data explorer and Account.
4. Test **Maharashtra demo operator** for Darewadi and **Uttar Pradesh demo operator** for Rewana/Bijua.
5. An operator must not gain Admin portfolio/team/configuration access by typing URLs.
6. If you changed QA assignments, restore them after testing.

## 18. Archive and restore the QA site

1. As Admin, expand **Site equipment & source notes** on the QA site.
2. Click **Archive site**.
3. Expect the archived notice and disabled planning controls. Saved runs remain readable; the site is excluded from the active portfolio.
4. Click **Restore site** to make it active again.

## 19. Check keyboard and small-screen behavior

1. Use Tab and Shift+Tab through login, navigation, KPI controls and inputs. A visible focus outline should follow you.
2. Use Enter/Space to activate KPI controls. The separate dialog should trap Tab focus, close with Escape, and return focus to the KPI. Also test × and clicking the dimmed backdrop. Cards must not change size.
3. Reload a signed-in page and use the **Skip to workspace** link at the start of keyboard navigation.
4. Try a phone-sized viewport. Navigation and wide tables may scroll within their own areas; the page itself should not overflow horizontally.
5. On a phone, sign out through **Account → Sign out of this account**.

## If something looks stuck

- No screen at port 5173: restart `python3 backend/dev.py`.
- Login/API errors: check the Django terminal on port 8000.
- Weather errors: check internet connectivity; Demo weather is available locally.
- Resilience checks stay pending or replay time does not move: check the Python worker output.
- Old results after changing a source or reading: generate a new plan and verify its ID.
- Unexpected zero differences: compare actual inputs, installed sources, service and battery values before assuming a rendering problem.

## Automated acceptance

With the local app running:

```sh
backend/.venv/bin/python frontend/tests/verify_workspace.py
```

This checks demo login, KPI interaction, all three weather providers, plan charts and dialogs, custom scenarios, replay approval/events, CSV export, role restrictions and mobile overflow. It creates additional plans and a paused replay on seeded Dharnai. Browser evidence is saved in `frontend/test-results/`.

To capture the current login, portfolio, sites, data, people, account, configuration, charts, dialogs and replay at multiple widths without creating new plans:

```sh
backend/.venv/bin/python frontend/tests/verify_workspace.py --visual-only
```

This reports page errors and horizontal overflow alongside 49 screen captures. It also opens existing site pages, which can queue any missing standard assessments.

To check KPI popup dialogs without creating plans or saving configuration:

```sh
backend/.venv/bin/python frontend/tests/verify_workspace.py --metrics-only
```

This checks all four portfolio KPIs on desktop and mobile, site-plan KPIs, the configuration-review KPI, navigation from a dialog, unchanged card dimensions, focus trapping/restoration, and all three closing methods.

Backend regression command:

```sh
backend/.venv/bin/python -m pytest backend/grid/tests -c backend/pytest.ini -q
```

See [setup](../README.md), [seed-data assumptions](SEED_DATA.md) and [model details](MODEL_NOTES.md) for reference.

## 20. Inspect equipment and generation visually

1. On a site’s Plan, expand **Site equipment & source notes**.
2. In **Capacity**, inspect the solar, wind and diesel shares of nameplate power. Hover a doughnut segment or select its legend item to inspect its value in **kW**.
3. Switch to **24-hour energy**. The chart now sums used solar, wind and diesel over the saved plan’s hourly intervals in **kWh**. Its proportions can differ from installed capacity.
4. Inspect the separate battery graphic: total storage, safe operating range, reserve and starting stored energy. Battery discharge is not counted a second time as generation.
5. In **Configure site → Equipment**, the same capacity chart updates as you edit equipment. The battery graphic shows its operating window; it does not claim a current reading when no plan is selected.
6. In **Demand & loads**, the daily energy bar updates with critical, normal and flexible shares. Use a QA site to save configuration changes.
7. On **Sites**, search by name, district or state. Compare renewable-share bars and fuel/service figures from each site’s latest plan. **Include archived** reveals archived sites.


## Assistant, detailed comparison and reports

The [assistant walkthrough](ASSISTANT.md) covers the new chat drawer, scoped conversations, fixed workflows, PDF/CSV/JSON reports, and the model evaluation gate. Portfolio comparisons now open a separate detailed window. Replay exports include full persisted evidence and mark incomplete legacy sessions.
