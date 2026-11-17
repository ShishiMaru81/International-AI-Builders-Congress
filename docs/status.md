# Current implementation status

Last updated: 2026-11-17, Asia/Dhaka. Work is ongoing; do not describe this as a fully validated production product.

| Area | State | Evidence / remaining work |
|---|---|---|
| Premium frontend | DONE for demo | Patched Next.js production image builds on Linux; desktop and 360px Bengali browser journeys pass against Docker |
| Backend / local persistence | DONE for demo | FastAPI + SQLAlchemy, 12 integration tests passed locally and against PostgreSQL |
| Farm area selection | DONE | Worldwide place search, clickable/draggable map pin and manual coordinates on FloodCrop and farm creation. Explicit save consent, persisted location, automatic live-weather refresh and forecast invalidation. Browser tests cover saved search, reload/map clicks and mobile offline fallback |
| PostgreSQL / containers | DONE for local prototype | Isolated agrosphere-congress stack runs on 3100/8100/55432. All containers healthy; Alembic reports no drift; 10 backend tests pass against a separate PostgreSQL test database. Cases, private images, sessions and device readings survive API restart |
| AgroDoctor workflow | DONE for demo | Private upload, validation, quality checks, uncertainty, history, feedback, CSV export/delete tested |
| Real disease classifier | DONE for controlled-image research prototype | 570 leaf-grouped images, 360/90/120 split. Holdout accuracy 95.8%, macro-F1 0.958; exported model parity and real HTTP upload checked. No field validation |
| FloodCrop | DONE for scenario and live weather / PARTIAL official feeds | Live Open-Meteo request returned HTTP 200 with non-simulated provenance. No authorized official flood feed |
| KrishiMarket | DONE for prototype | Atomic private CSV validation/dedup, explicit costs, decimal proceeds comparisons, watch storage. No forecasting or automatic watch delivery |
| Action Center | DONE for demo | Plot-scoped actions update from all three modules; latest desktop/mobile browser regression passed |
| Localization | PARTIAL | English/Bangla navigation, main headings and flagship upload flow. Secondary/help text remains English; no agronomic translation review |
| Hardware contract | DONE for virtual test | Auth, validation, deduplication, persistence and status UI tested; no physical hardware |
| Production security / advisor service | NOT IMPLEMENTED | Local demo sessions only; no independent security review, external advisor delivery or deployment |
| Documentation | DONE for current prototype | Installation, architecture, privacy, sources, model card, hardware, OpenAPI, evidence and demo runbook supplied |
| Netlify + free cloud hosting | PREPARED / ACCOUNT ACCESS PENDING | Netlify monorepo config and free Render blueprint supplied; Netlify-mode build, deployment preflight tests, cloud image/model checksum and memory-limited inference verified locally. No live cloud deployment is claimed; Netlify authorization and Render connection are still required |

Final local checks passed: API tests, frontend unit tests/typecheck/lint/build, desktop/mobile browser journeys, exported-model holdout parity, actual HTTP image inference, live weather connectivity and Alembic upgrade/schema consistency. Docker follow-up verified actual Linux inference, PostgreSQL integration tests and restart persistence. Patched MapLibre and Vitest and pinned the linter's minimatch dependency; npm audit now reports zero known advisories. Advanced field robustness, recent observed rain, market forecasting and full translation are not claimed. The application is functional as a local research prototype, not a fully validated production agricultural service.
