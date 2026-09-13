# JeevanGrid frontend — React

The dashboard is a React application. Vite uses Node.js to transform JSX, serve hot updates and build browser JavaScript. All application APIs and simulation logic run in the Django backend.

From this directory, with Node.js 22.12+ installed:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` and `/ws` to Django on port 8000. See [backend setup](../backend/README.md) to start the full app.

`npm run build` creates `dist/`. Built React assets can be hosted as static files; production does not require a Node application server.

This workspace also has an ignored Node binary in `.tools/node` because Node was not installed on the host. It is used directly by `backend/dev.py`, with no Python-to-Node wrapper. To build with that binary: `.tools/node node_modules/vite/bin/vite.js build`.

Browser acceptance scripts live in `tests/`; generated evidence belongs in `test-results/`.

Follow the [step-by-step feature testing guide](../backend/docs/LIVE_WALKTHROUGH.md) for the full dashboard walkthrough, expected outcomes and sample CSV import.

The interface uses deep teal, emerald and lime accents in `src/style.css`. `src/intelligence.css` styles maps and datasets; `src/workspace.css` styles planning, equipment graphics and replay. Source colors are shared through `src/chartTheme.js`. Fonts use the system stack; the logo and favicon are local vectors.

`EnergyVisuals.jsx` separates installed power (kW), planned generation (kWh), and battery storage (kWh). `StressExplorer.jsx` compares saved solver outcomes; `stressInsights.js` distinguishes reserve breaches, existing shortfalls, unavailable schedules, and inapplicable tests. Test the interpretation with `.tools/node tests/stress-insights.test.mjs`.

The local login/portfolio photograph is **Andreas Gücklhorn, [solar arrays](https://unsplash.com/photos/Ilpf2eUPpUE)**, used under the [Unsplash License](https://unsplash.com/license). The downloaded file is `public/solar-farm.jpg`; it was retrieved from the [attributed copy hosted by Ekhi](https://cdn.prod.website-files.com/63fcbddecbc9c739c7e5c6c9/655b2138143fa940d9044371_andreas-gucklhorn-Ilpf2eUPpUE-unsplash.jpg). It depicts renewable infrastructure, not any of the app’s demo sites. No runtime image request goes to a third party.

Visual references reviewed for this redesign: [Enode](https://enode.com/), [Aurora Solar](https://aurorasolar.com/), [Watershed](https://watershed.com/), [Enpal](https://www.enpal.de/) and [sonnen](https://www.sonnen.de/). The implementation uses original layouts and components, drawing on their emphasis on renewable infrastructure, clear actions and visual energy information.
