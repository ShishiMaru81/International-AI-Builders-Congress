# AgroRescue and marketplace photos — 17 November 2026

AgroRescue is implemented in the existing workspace at `/en/agrorescue` and `/bn/agrorescue`, with a farmer marketplace navigation link. It compares up to six selling options with Decimal money, asks for missing transport costs (including break-even thresholds), checks readiness, distinguishes entered/sourced/simulated quotes, and shows owned weather/screening context. Optional holding calculations require explicit assumptions and total holding/later-selling costs. Saved private plans integrate with history, action center, export and deletion. No automatic transaction or trained price/spoilage forecast is claimed. See [usage and limits](agrorescue.md).

Twenty licensed local crop photographs now provide matching EN/BN illustrative fallbacks. Normal seller uploads take priority; absent, broken or unusably tiny uploads fall back without changing uploaded data. Unknown/mixed crops remain neutral. Credits are accessible from the marketplace. See [photo sources and licenses](crop-images.md).

Fresh final checks: **125 API tests, 74 web unit tests and all 28 browser tests passed**. Typecheck and production build passed. ESLint: 0 errors / 9 earlier warnings; new planner/photo modules pass scoped lint without warnings. Full browser verification used separate web/API ports 3400/8400 and an isolated database/storage, then these QA servers were stopped. Final live visual checks: no page errors, no Bengali mobile overflow, and three existing tiny-upload tomato listings loaded `/crops/tomato.jpg` successfully.

Independent review caught and verified fixes for saved `BDT/kg` quotes, missing farm-gate/retail choices, stale quote confirmations, and an existing MapLibre worker initialization defect. The map now uses the installed `setWorkerUrl` API; area selection and canvas clicks pass. Failed live weather refreshes are retained as warnings on cached weather, with no DEMO substitution. Plans invalidate on input edits/plot changes; delayed responses cannot restore stale results. Hold-cost scope, source dates and cent/fractional quantity rounding have regression coverage.

Updated app remains on 3300/API 8300 with its prior database/media and lifecycle worker; SQLite backups were made before API restarts. Original 3000/8000 services and previous working-tree changes were preserved. No commit, push or cloud deployment. Field/economic/food-safety validation, trained forecasting, expert Bangla review and production/cloud/security/load review remain unperformed. Historical status sections below refer to earlier stages.

---

# Marketplace implementation status — 17 November 2026

The requested integrated KrishiMarket marketplace is implemented locally: three backend-enforced roles, fixed-price checkout without bidding, optional MOQ, separate auction reservations, 20 km nearby-first nationwide discovery, safe product media, seller fulfillment, customer tools and admin moderation/policies/audit. Prototype cash records are not real online payments. See [marketplace guide](marketplace.md).

Fresh verification: 80 API tests, 18 web unit tests and 17 browser tests passed; typecheck/build passed; lint 0 errors / 9 existing warnings. Independent review fixes verified. Real admin browser actions passed. Original/crop model hashes are unchanged; the existing market comparison duplication is now corrected and the connected journey passes. Additive migration 0004 and photo/listing persistence across native API restart were verified. Docker is unavailable; container/cloud execution is not claimed.

The app is running on 3300 with API 8300 and a separate expiry worker. Existing original 3000/8000 services and project data were preserved. New registration has local password authentication; identity verification/payment/courier/security/load/accessibility/complete translation review remain production work. Earlier status sections below are historical and their old full-E2E failure is superseded by the checks above.

---

# Current implementation status — 17 November 2026

## AgroDoctor multi-crop update

The approved multi-crop design is implemented locally in this checkout. Active inference now uses two pinned upstream bundles for 12 disease-enabled crop groups. This is genuine local model inference; it is research screening with no independent multi-crop accuracy or field validation. Original tomato artifacts and historical case snapshots are preserved.

- 46 API tests passed, including crop/plot ownership and mismatch, source pinning, corrupt/missing models, single-flight initialization, preprocessing controls, EXIF/transparency/animation and failed-save cleanup.
- 18 frontend unit tests, TypeScript and production build passed. ESLint: 0 errors, 9 warnings (existing navigation/config warnings plus native private/blob image warnings).
- 6 AgroDoctor browser regressions passed: selector/createplot, stale upload/drop/context, older history and plot isolation, private-photo/notes/missing-image detail, unavailable model and delayed plot creation. Initial plot loading now disables photo controls to prevent losing a selection during context initialization. Actual desktop rice inference and 390px Bengali layout inspected; no page errors or horizontal page overflow.
- HTTP smoke tests used one potato, one maize and one rice image, a wrong-crop control, noise and a flat image. Results are in the multi-crop verification handoff, with sources and limitations. They are not an accuracy estimate or proof of unseen-data generalization.
- Independent code review found 3 issues (container path resolution, active-model readiness, delayed plot-create selection); all 3 were reproduced and fixed with regression checks.
- Full connected browser suite still has the pre-existing market/action-center journey failure. Area/manual-coordinate and Bengali journeys pass. The map worker remains an earlier audit item; a passing canvas interaction test does not prove map tiles/worker correctness.
- Docker executable is unavailable in this environment, so updated Compose/hosted Docker configuration is unbuilt here. No cloud deployment, free-tier resource fit or production migration success is claimed.

Current isolated local sessions: frontend http://127.0.0.1:3300/en/agrodoctor and API http://127.0.0.1:8300/docs. Older original checkout services on 3000/8000 were left intact.

See [multi-crop setup and limitations](agrodoctor-multicrop.md). Secondary copy and raw condition names remain partly English; expert agronomic/translation review, genuine field evaluation, calibrated uncertainty and robust OOD detection remain future work. This scoped change does not close the full earlier project audit backlog.

## Historical status recorded before this update

The following earlier claims are retained as history. They are not fresh verification of this checkout or the new upstream models.

# Current implementation status

Last updated: 2026-11-17, Asia/Dhaka (audit remediation in progress on branch `fix/audit-remediation`).

**Honest summary:** local software corrections for the audit backlog are substantially implemented and gated by isolated API/unit/build checks; this is **not** field-validated, competition-submitted, or live-cloud proven. See `docs/audit-remediation.md`, `docs/audit-verification.md`, and `docs/audit-handoff.md`.

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
