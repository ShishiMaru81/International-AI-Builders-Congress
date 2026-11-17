# Verification record

Executed 2026-11-16 on Windows / Node 24.17 / Python 3.12.10.

- `python -m pytest -q`: **10 passed**, one upstream Starlette/httpx deprecation warning. Covers ownership, consent, invalid/oversize uploads, image storage/history/feedback/CSV/delete, exact decimal arithmetic, missing costs, rain horizons, live-mode coordinate guard, atomic imports/dedup, device auth/dedup/persistence, shared actions and account deletion.
- `npm run test`: **2 passed** (formula presentation and Bangladesh-time formatting).
- `npm run build`: **passed**, Next.js 16.4.6 production compilation and generated routes.
- `npm run typecheck`: **passed**.
- `npm run lint`: **0 errors**, 6 nonblocking framework/style warnings.
- `npm run test:e2e`: **2 passed**, installed Edge: desktop module journey including device simulation, and Bengali mobile navigation at 360px without horizontal overflow.
- Docker engine availability check: **failed**, Docker Desktop Linux daemon pipe missing. Container/PostgreSQL execution is not claimed.
- Interactive CUA browser preview: browser host unavailable. Automated Playwright browser tests did run successfully; interactive visual review remains unverified.

Final regression after model and plot integration: **10 backend, 2 unit and 2 browser tests passed again**. Production build and TypeScript also passed. Alembic upgrade and `alembic check` succeeded against a separate SQLite verification database with no schema drift.

Actual model: 570 official-grouped original tomato images, 360/90/120 split. Held-out accuracy 115/120 (0.95833), macro-F1 0.95797, ECE 0.05202. Scripted export reproduced 115/120; five failure records retained in ml/artifacts/failures.json. This is controlled-image research evidence, never field accuracy. See docs/model_card.md and the saved evaluation JSON.

HTTP smoke test: an actual holdout image uploaded through FastAPI returned a genuine early-blight possibility from mobilenetv3-tomato-20aa688a66 with an uncalibrated model score. Live Open-Meteo returned HTTP 200, source Open-Meteo, is_simulated=false for a public Gazipur test point. The disposable smoke workspace was removed afterward. Details: docs/smoke-result.json.

## Docker follow-up: verified on this PC

Docker Desktop is now running. The previous engine-unavailable limitation is resolved. This checkout uses the isolated **agrosphere-congress** Compose project with website/API/PostgreSQL ports **3100/8100/55432**. The older agrosphere-ai containers and their volumes were preserved.

- Linux production build: **passed** after adapting the patched MapLibre library to named exports. The standalone frontend and CPU PyTorch API images run successfully.
- `docker compose ps`: **all three services healthy**. API and web both run as UID 1000.
- `docker compose exec -T api python -m alembic check`: **no new upgrade operations**, PostgreSQL schema matches models.
- Backend integration suite inside Docker, using a dedicated agrosphere_test PostgreSQL database: **10 passed**. The application database was not dropped or reset.
- `scripts/docker_verify.py`: **passed** actual image inference, rainfall scenario, decimal market comparison, authenticated device reading and deduplication. A deliberate API restart preserved the same session, saved case, private image and sensor reading. The disposable workspace was deleted after verification. Saved evidence: docs/docker-verification.json.
- Frontend unit tests after patching Vitest: **2 passed**. Lint: **0 errors, 6 existing nonblocking warnings**.
- Final Docker browser journeys with PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 and AGROSPHERE_API_URL=http://127.0.0.1:8100/api/v1: **2 passed** (22.8 seconds), including the desktop three-module/device journey and Bengali mobile navigation at 360px.
- Dependency patches: MapLibre 6.18.0, Vitest 5.1.0, and scoped minimatch 11.0.1 override for the linter. `npm audit` and Linux `npm ci` report **0 known npm vulnerabilities**. This is dependency advisory screening, not an independent security audit.

## Area-selection fix — 2026-11-17

The previous map only displayed a fixed pin. FloodCrop and farm creation now support worldwide named-place lookup, map clicks, pin dragging and manual WGS84 coordinates. Saving requires consent and refreshes weather for the selected farm. Old weather records are removed on location change; weather cache keys include coordinates. Zero latitude/longitude are preserved.

- Backend tests: **12 passed locally and 12 passed inside Docker against the isolated PostgreSQL test database**. New coverage includes geocoder normalization, authentication, query validation, offline provider errors, consent, coordinate bounds, ownership, old-forecast invalidation and zero-coordinate provider dispatch.
- Frontend: **TypeScript passed**, lint **0 errors / 6 existing warnings**, **2 unit tests passed**. Linux Docker production build succeeded and the updated API/web were deployed with existing volumes intact.
- Docker browser scenarios: existing desktop module journey and Bengali mobile journey passed. New area-search/save/reload/map-click test passed. The mobile offline/manual-coordinate scenario passed in a targeted rerun after correcting an ambiguous alert selector and allowing for slow demo-account creation. **All four browser scenarios verified**; geocoder/weather responses in these regression tests are explicit fixtures, not live-provider evidence.
- Separate live smoke: actual geocoder HTTP **200**, source **Open-Meteo Geocoding / GeoNames**, selecting Sylhet and persisting the returned coordinates to PostgreSQL succeeded. Disposable workspace removed afterward; result in docs/area-verification.json.

## Netlify/free-demo hosting preparation — 2026-11-17

- Added Netlify monorepo configuration, verified by `netlify build --dry --offline`. Detected base apps/web and root netlify.toml correctly. This is local configuration validation, not a hosted deployment.
- `NETLIFY=true npm run build`: **passed**, including TypeScript. Lint: **0 errors / 6 existing warnings**.
- `node --test scripts/netlify-preflight.test.mjs`: **2 passed**. Deployment rejects localhost/private/plain-HTTP/credential-bearing URLs and verifies backend health and browser CORS origin before publishing.
- Backend regression: **12 passed**, including HTTP 410 for a photo removed from ephemeral storage. Provider-issued PostgreSQL connection strings use the installed psycopg driver.
- Portable cloud Docker image: **built successfully** from root context. The public model release was downloaded and its SHA-256 checked against the committed model card.
- A disposable local instance constrained to **512 MiB** and **0.5 CPU** completed actual held-out-image inference and live weather retrieval. Observed memory after smoke: **337.6 MiB / 512 MiB**, OOMKilled=false. This demonstrates a local memory check, not measured Render performance or a guarantee for large/concurrent uploads. Result: docs/free-cloud-smoke-result.json.
- Cloud deployment remains **unverified/pending account authorization**. No paid resources were provisioned. The supplied Render plans are free; their sleep, ephemeral-photo and 30-day database-expiry limitations are documented and surfaced in the hosted UI.
