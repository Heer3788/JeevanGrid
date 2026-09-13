# JeevanGrid backend — Django

Python runs every API, authentication, optimization, database and simulation worker. There is no Node backend. React uses Vite (Node.js) only for development and building browser assets.

Run from the repository directory, using Python 3.12+ and Node.js 22.12+:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py seed_demo --with-runs
cd frontend
npm ci
cd ..
python3 backend/dev.py
```

Open http://127.0.0.1:5173. Django's ASGI server uses port 8000. Ctrl+C stops both servers, the simulator worker and the assistant/report worker.

The public landing page is at `/`, the unchanged login at `/login`, and the authenticated dashboard at `/workspace`. **Get started** leads through login to the workspace. See the [landing-first video and site-creation walkthrough](docs/LANDING_TO_DEMO_VIDEO.md).

On Windows, replace `backend/.venv/bin/python` with `backend\.venv\Scripts\python.exe`, and `python3` with `py`.

Run the backend separately:

```sh
# Terminal 1, from the repository root:
cd backend
.venv/bin/python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000

# Terminal 2, from the repository root:
cd backend
.venv/bin/python manage.py run_live_worker

# Terminal 3, from the repository root:
cd backend
.venv/bin/python manage.py run_assistant_worker

# Terminal 4, from the repository root (use `npm run dev` when Node is on PATH):
cd frontend
.tools/node node_modules/vite/bin/vite.js --host 127.0.0.1
```

Tests: `backend/.venv/bin/python -m pytest backend/grid/tests -c backend/pytest.ini`.

The database and Python environment stay in this directory. Browser checks and screenshots live in `frontend/tests` and `frontend/test-results`. See the [dashboard walkthrough](docs/LIVE_WALKTHROUGH.md), [modelling notes](docs/MODEL_NOTES.md), and [seed sources](docs/SEED_DATA.md).

Seeding adds missing demo records and does not reset passwords or overwrite user sites. Set `JEEVANGRID_DEMO_PASSWORD` before first seeding to override the local demo password.

See [assistant setup, supported workflows and release checks](docs/ASSISTANT.md) to configure Groq and test verified chat automation.

For the expanded demo, see [108-site portfolio data and provenance](docs/PORTFOLIO_DATA.md) and [the five-minute final-round showcase](docs/FINAL_ROUND_SHOWCASE.md). Add the engineering-modelled portfolio with:

```sh
backend/.venv/bin/python backend/manage.py seed_portfolio --with-runs --with-checks --weather historical --date 2025-01-15 --export-dir backend/.local/portfolio
```

This adds 108 sites and 27 assigned operators without overwriting existing data. The sites use explicit appliance-based demand and disclosed equipment assumptions; NASA weather is regional historical data, not live site telemetry. The Data explorer includes a readable inventory and source references. The optional `verify_showcase --execute` command exercises real chat workflows and records before/after database evidence; it requires the API, both workers and a configured Groq key, and intentionally creates local demo records.
