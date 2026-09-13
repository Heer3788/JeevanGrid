# JeevanGrid assistant: setup and verification

The application remains Django/Python + React. Node is used by Vite to develop and build React. The assistant, reports, optimization and both workers run in Python.

## Start the application

From the repository directory:

```sh
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python backend/manage.py migrate
python3 backend/dev.py
```

Open **http://127.0.0.1:5173**. The launcher starts the API, React, simulator/assessment worker, and separate assistant/report worker. Stop and restart the launcher after changing backend code or environment settings.

To enable natural-language interpretation, copy `backend/.env.example` to the ignored `backend/.env`, enter your own `GROQ_API_KEY` locally, and restart. Do not put the key in React or commit it. The default model is `openai/gpt-oss-120b`. The API adapter uses Groq strict JSON-schema output; it never exposes arbitrary Python tools to the model. There is no paid-model fallback. Provider/account quotas still apply.

`ASSISTANT_ENABLED=0` disables assistant APIs and workflow processing. It does not disable manual report exports. Production defaults to disabled; local development defaults to enabled. `ASSISTANT_WORKFLOWS` accepts a comma-separated allowlist of the IDs below, or `*`. Workflow tests do not need a model key.

## How to use it

1. Sign in with a seeded account. Open **Ask JeevanGrid** at the bottom right.
2. On a site page, the drawer is restricted to that site. From Portfolio, administrators can work across their organization; operators can access assigned sites only.
3. Enter a complete request. For example: “Generate a plan for this site using live weather and export a PDF report.” Weather source is required. Historical NASA planning also requires a date.
4. Questions receive short conversational replies. Existing Markdown replies render as readable text, lists and tables. Actions keep their result cards, with accepted inputs and persisted steps inside **Task details**. Missing inputs produce a question; answer it in the composer. Complete, explicit requests execute without a second confirmation.
5. Open the resulting plan, scenario comparison, or report. Six completed stress tests mean six recorded outcomes; they do not imply every test passed. A valid infeasible result says “Analysis completed: no feasible plan.”
6. Use **History** to show previous chats; the list is collapsed when the assistant first opens. Reopening a conversation retrieves saved workflow steps and rechecks access and evidence. The opening screen contains only a short greeting and the message composer.
7. After a provider/weather availability error, **Retry remaining steps** resumes the same workflow and preserves completed changes.
8. Cancel stops subsequent steps. Completed changes remain saved and linked under **Task details**. It does not roll back a site or plan that was already saved.
9. **New chat** is visible at the top of both the drawer and assistant page. It clears the draft, attached-file selection and conversation context. Prior chats and already-submitted tasks remain in history. Late polling or send responses cannot reopen the old conversation.

The worker publishes **Working** before calling the model. A message still queued after 30 seconds shows a waiting notice rather than silently appearing to think. An empty or truncated provider reply produces an explicit retry/error outcome. Restart `run_assistant_worker` after changing backend prompts; the normal `backend/dev.py` launcher manages all four services together.

Natural-language requests require a configured provider. Without a key, chat reports provider unavailability. It does not pretend to interpret requests locally. Manual controls, detailed comparison, and PDF/CSV/JSON exports still work.

## Registered operations

| ID | Example | Verification |
|---|---|---|
| `site.create` | Create a site with explicit location/configuration, or explicitly accept the demo template | Organization, accepted fields, equipment and assignments read back |
| `site.update` | Change Dharnai’s installed solar capacity to 80 kW | Before/after values and configuration version |
| `site.assign` | Assign operator user IDs 12 and 13 to Dharnai | Same-organization assignments read back |
| `site.archive`, `site.restore` | Archive / restore Dharnai | Persisted lifecycle state |
| `readings.record` | Record battery SOC at 35% and available fuel at 120 L | Saved reading and new version |
| `demand.import` | Import attached CSV #7 as Dharnai’s demand | 24 consecutive hourly intervals, values, totals and CSV provenance |
| `plan.generate` | Generate a simulated-weather plan for Dharnai | Source, frozen inputs, configuration version, 24 intervals, power balance, battery/fuel limits and metrics |
| `scenario.test` | Test plan #729 with solar reduced by 50% | Exact overrides, linked scenario, unchanged baseline and dispatch checks |
| `compare` | Compare Rewana and Bijua | Saved source IDs, compatible horizons, units and supplied-energy denominators |
| `replay.start` | Start a replay of plan #729 at 10× | Saved session, initial transition, fresh simulated telemetry |
| `replay.event` | Apply cloud cover in replay #9 | Durable event revision, worker replan, fresh telemetry and power balance |
| `replay.pause` | Pause replay #9 | Session identity and recorded pause |
| `plan.review` | Confirm plan #729 | Current, feasible, unexpired inputs and saved decision |
| `command.review` | Approve simulated command #17 | Explicit current command, saved review; execution success waits for persisted generator telemetry |
| `forecast.train` | Train Dharnai on 90 simulated days | Saved dataset, provenance, model version and calibration/test report |
| `report.export` | Export plan #729 as PDF | Frozen evidence, source IDs, content hash and valid output |
| `question` | Why is reserve used here? | Authorized read-only evidence; explanatory prose labeled as interpretation |

Site configuration, assignments, lifecycle, imports and training require an administrator. The backend rechecks role and site access before each step, during history retrieval and on downloads. Uploaded CSV contents are parsed as data and are never sent to the model as instructions.

Recipes: `create_and_plan`, `readings_and_plan`, `plan_and_report`, `test_and_compare`, `compare_and_report`. Other combinations require a new registered recipe. Creating a site does not infer equipment from its name or location; select a resolved location or provide coordinates, and supply full configuration or explicitly accept the demo template. Persistent readings and replay events are different operations; vague requests such as “battery at 25%” need clarification.

## Comparisons, replay and reports

Select 2–5 sites in Portfolio and open **Detailed comparison**. Compare service, shortages, supplied energy, dispatch cost, diesel, renewable share, emissions, minimum SOC, and reserve margin. Cost/diesel/emissions per kWh use **supplied** energy. Zero supplied energy yields an unavailable denominator, not a fabricated zero. Incompatible sources/horizons and stale settings are identified; hourly differences are disabled when inappropriate.

Replay power is drawn across its actual recorded interval. Accelerated ticks split at source-hour/local-hour boundaries and at the end of the day. Shaded gaps show unmet demand. Event markers identify condition changes. Unfinished flexible work is displayed separately from critical shortage. Starting a replay never approves its proposed commands. Verification covers the simulated generator output and power balance; it does not claim a physical device or battery setpoint was verified.

New replays retain every interval and durable event. The screen displays the most recent 120 samples and 12 commands; exports include all saved samples, commands and events. Legacy sessions are marked incomplete; discarded history is never reconstructed.

Choose PDF, CSV or JSON in an export control. The first export freezes evidence. Switching format in that same control reuses the frozen evidence, even if a replay advances. PDF is a readable report; CSV is a ZIP containing dispatch/weather/metric or replay tables plus full `evidence.json`; JSON contains the complete structured record. Reports are rendered by the separate Python worker using ReportLab.

## Execution contract

Each workflow has a version and fixed step sequence. Inputs and names are validated against current authorized records. Long-running weather/model/solver preparation happens outside the mutation transaction. A mutation and its step receipt commit together. A unique conversation/request key prevents duplicate delivery; a unique workflow/step key prevents duplicate resumed mutations. The single assistant worker holds an OS lock. Restart resumes saved steps, checking prior receipts first.

Transient weather/provider failures allow two retries and honor provider backoff. Validation errors and verification mismatches stop the workflow. External worker verification waits are bounded. No fallback changes weather source, demand, battery limits or equipment to force a feasible result. Cancellation cannot interrupt an already-running solver call but prevents its subsequent mutation from committing.

Questions have a separate read-only route with at most three evidence retrieval groups. General answers have no application mutation capability. Their prose is not a workflow completion receipt. Model interpretation can still be wrong; strict schema compliance does not prove semantic correctness.

## Release checks

```sh
backend/.venv/bin/python -m pytest backend/grid/tests -q
frontend/.tools/node frontend/node_modules/vite/bin/vite.js build frontend
backend/.venv/bin/python frontend/tests/verify_workspace.py --assistant-only
backend/.venv/bin/python frontend/tests/verify_workspace.py --metrics-only
backend/.venv/bin/python frontend/tests/verify_chat.py
```

`verify_chat.py` uses browser API fixtures and makes no model calls or site changes. It covers readable/safe Markdown, fresh-chat races with delayed GET and POST responses, cleared drafts and attachments, preserved history, restored drawer conversations and mobile controls. It is not a model-accuracy evaluation.

The chat update was checked with 52 backend chat/assistant tests, a successful frontend build, the browser regression above, and one live Groq question through the running UI. The live SOC reply was 81 words and New chat opened a clean conversation while keeping history. This focused check does not establish the full interpretation accuracy gate below.

The assistant browser check creates one labeled simulated plan-and-report workflow for Dharnai and, if no replay is already active there, starts and pauses a short software replay. It also checks comparison measures, downloads, scope, history restoration, keyboard focus, and mobile layout. Reports and screenshots are written under ignored `frontend/test-results`.

Run the live interpretation benchmark after configuring the key:

```sh
backend/.venv/bin/python backend/manage.py evaluate_assistant
# Evaluate the smaller candidate separately, with its own result file:
backend/.venv/bin/python backend/manage.py evaluate_assistant --model openai/gpt-oss-20b --output backend/.local/eval-20b.jsonl
```

The benchmark performs no application mutations. It persists results after each case and resumes after quota exhaustion. It requires at least **98% exact workflow/input matches** on unambiguous cases plus all included negation/ambiguity/unsupported-action cases. A limited or interrupted run does not pass the release gate. Use a fresh output file after changing the interpreter or fixing a failed case. Deterministic authorization and completion tests are a separate required gate.

**The live model accuracy gate has not been established without a configured key.** Do not present mocked provider tests as proof of 98% accuracy. Keep the production assistant disabled until the live evaluation and deployment checks pass.

Scheduled monitoring, autonomous approvals, equipment-sizing experiments, voice and physical control are outside this release.

## Validation recorded for this implementation

- Full Django suite: **120 passed** with local socket support, including existing manual API/optimizer/WebSocket coverage.
- React production build: passed.
- Browser acceptance: detailed comparison, a real plan-and-report workflow, PDF download, restored history, scoped drawer, keyboard navigation, and mobile fit passed.
- Short software replay: cloud and low-battery events, interval start/end chart coordinates, paused state, full JSON evidence and independently checked totals passed.
- Existing KPI-dialog regression checks passed on portfolio, site and configuration pages.
- Live Groq interpretation evaluation: **not run** because the key is not configured. The 98% language interpretation release gate remains pending.
