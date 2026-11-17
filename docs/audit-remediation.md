# ZYNTRIX AgroSphere AI — Audit Remediation Ledger (51 Findings)

**Repository root (local workspace):** `d:\AI_Congress\zyntrix-agrosphere-ai-main\zyntrix-agrosphere-ai-main`  
**Audit baseline commit (source snapshot):** `edd6b34e6da027d277e3e1de4cd7b2880c643154`  
**Local git baseline:** `fc4035d` · branch `fix/audit-remediation`  
**Last ledger update:** 2026-11-17 (Asia/Dhaka)

## Ordered Implementation Plan

1. Phase 1 — Safe tests, session, plot context, preferences (`MD-01`, `FE-01`, `FE-C1`, `FE-05`, `B14`)
2. Phase 2 — AgroDoctor lifecycle / model integrity (`FE-02`, `FE-06`, `FE-07`, `B07`, `B08`, `MD-02`, `OP-01`, `MR-02` software)
3. Phase 3 — Map, location invalidation, freshness, actions/evidence (`MAP-01`, `B01`, `B02`, `B09`, `FE-C3`, `FE-08`, `FE-09`, `FE-13`, `B10`)
4. Phase 4 — Market CSV/compare/watches (`FE-03`, `FE-04`, `FE-C2`, `FE-11`, `B03`–`B06`, market `B10`/`B15`)
5. Phase 5 — Farm/plot/device lifecycle + OpenAPI (`B11`–`B13`, `B15`, `B16`)
6. Phase 6 — Bangla, a11y, routes, contrast (`FE-10`, `FE-12`, `FE-14`)
7. Phase 7 — ML verification & ops (`MD-03`–`MD-06`, `MR-01`, `MR-03`, `OP-02`–`OP-05`)
8. Phase 8 — Competition drafts (`C-01`–`C-03`)

---

## Complete 51-ID Remediation Ledger

Allowed statuses: `not started`, `reproduced`, `in progress`, `implemented; verification pending`, `verified`, `already resolved; verified`, `needs external evidence`.

| ID | Severity | Status | Affected Feature | Implementation Reference | Verification Evidence | Outstanding Human / External Dependency |
|---|---|---|---|---|---|---|
| `C-01` | Competition | `implemented; verification pending` | One-page summary, 3-min script, AI/provenance drafts | `docs/competition/*` | Drafts present; not submitted | Owner must record video & upload to portal |
| `C-02` | Competition | `implemented; verification pending` | Tomato-farmer story reliability framing | Phases 1–6 software + competition README | Local software path improved; no field loss study | Do not claim crop-loss reduction without study |
| `C-03` | Competition | `implemented; verification pending` | Claims register, business/pilot protocols | `docs/competition/claims-evidence-register.md`, `business-impact-plan.md` | Draft hypotheses only | Farmer interviews / pilot execution by owner |
| `MAP-01` | P1 | `implemented; verification pending` | MapLibre worker URL + async error fallback | `apps/web/src/components/farm-map.tsx` | Code + build pass; browser tile-ready console proof not re-run this turn | Confirm worker in prod browser console |
| `FE-01` | P1 | `implemented; verification pending` | `/me` session validation, 401 clear, local logout | `apps/web/src/lib/session.tsx`, `api.ts` | Unit helpers + typecheck; E2E expired-token journey not re-run | Production IdP before non-demo public use |
| `FE-02` | P1 | `implemented; verification pending` | Freeze upload/camera while busy | `workspace.tsx` Doctor controls `disabled={busy}` | Typecheck; delayed A/B E2E pending | None |
| `FE-03` | P1 | `verified` (unit/UI wiring) | Stale comparison flag + assumption snapshot | `workspace.tsx` Market | Typecheck; stale banner wired | Browser 400→800 kg confirmation recommended |
| `FE-04` | P1 | `implemented; verification pending` | No wholesale fallback under retail/farm-gate | `workspace.tsx` filtered prices + loading/error | Typecheck | Fail/delay category E2E pending |
| `FE-05` | P2 | `verified` (API) / FE wiring present | Preferences load/restore | `GET/PATCH /me`, SessionProvider, Settings | API Phase1 tests pass | Browser dark+consent reload recommended |
| `FE-06` | P2 | `implemented; verification pending` | Paginated cases + truthful total + load-more | `GET /doctor/cases` → `{items,total,...}`; Doctor load-more UI | Typecheck after pagination wiring; seed-25 E2E pending | Playwright seed-25 journey |
| `FE-07` | P2 | `implemented; verification pending` | Case image blob, alternatives, feedback read-back | Case detail + `GET .../feedback` | API includes feedback on case GET | Browser image/note reload recommended |
| `FE-08` | P2 | `implemented; verification pending` | Action Center / overview from plot records | `GET /plots/{id}/action-center` crop-filtered | API tests for center after location change | Dashboard card FE still partially static — continue |
| `FE-09` | P2 | `implemented; verification pending` | Provenance fields + source_url in types/API | `types.ts`, price/weather meta | Types include `source_url` | UI disclosure polish remaining in some cards |
| `FE-10` | P2 | `in progress` | Bangla catalog + `lang=bn` | Locale layout + starter `apps/web/src/lib/messages.ts` | Catalog scaffold present; not fully wired through all modules | Qualified Bangla/agronomic review; expand catalog usage |
| `FE-11` | P2 | `implemented; verification pending` | Watch CRUD + storage-only notice | API watch PATCH/DELETE/dedup; FE still write-heavy | API present | FE watch list/edit UI incomplete |
| `FE-12` | P3 | `verified` (route module) | Invalid locale/page → `notFound()` | `apps/web/src/app/[locale]/[[...page]]/page.tsx` | Code review + build | Optional not-found page styling |
| `FE-13` | P3 | `implemented; verification pending` | Unread badge from notification query | Header uses `unreadCount` | Typecheck | Mark-all-read E2E pending |
| `FE-14` | P2 | `verified` (computed contrast) | WCAG AA tokens | `globals.css` muted `#55665a`, primary `#0f6a47`; `tests/contrast.test.ts` | **18** web tests incl. contrast ≥4.5:1 | Manual screen-reader / multi-device audit |
| `FE-C1` | P1 | `implemented; verification pending` | Persisted selected plot + preference sync | SessionProvider + `selected_plot_id` PATCH | Typecheck | Multi-plot navigation E2E pending |
| `FE-C2` | P1 | `verified` (API) | Plot-scoped compare; no all-plot fan-out | `POST /market/compare` action only if `plot_id`; scenario endpoint | `test_compare_without_plot_does_not_contaminate_second_plot` | FE always sends `plot_id` when plot selected |
| `FE-C3` | P2 | `implemented; verification pending` | Effective weather freshness at read | `compute_effective_weather` | Used by outlook + action-center | Fake-clock UI expiry E2E pending |
| `B01` | P1 | `verified` | Central location invalidation | `apply_farm_location_change` on farm PATCH + `/location` | `test_generic_farm_coordinate_patch_invalidates_weather` | None |
| `B02` | P1 | `verified` (API) | Read-time freshness for weather/prices | `compute_effective_weather`, `compute_effective_price_meta` | Exercised via outlook/prices/center | Clock-controlled stale badge UI pending |
| `B03` | P2 | `verified` | Extra CSV cell → controlled error | `parse_and_validate_market_csv` | `test_csv_extra_cell_and_empty_header_are_controlled` | None |
| `B04` | P2 | `verified` | Huge/exponent prices rejected | Bounded decimal parse | `test_csv_large_price_rejected_and_dedup_ignores_extra_columns` | None |
| `B05` | P2 | `verified` | Canonical dedup ignores extra cols | `canonical_price_import_key` | Same test as B04 | None |
| `B06` | P2 | `verified` | Empty/wrong-header CSV rejected | Manifest of required headers | Same CSV controlled-error test | None |
| `B07` | P1 | `verified` | Case delete cascades feedback/actions | `_delete_case_artifacts` | `test_case_delete_removes_feedback_and_retires_action` | None |
| `B08` | P2 | `verified` | Export v2 prefs + readings + kinds | `GET /me/export` schema 2.0 | `test_export_includes_preferences_and_sensor_history` | Optional private image archive still separate |
| `B09` | P2 | `verified` | Snooze preserved on identical forecast | `upsert_action` fingerprint | `test_snoozed_action_not_recreated_by_identical_forecast` | None |
| `B10` | P2 | `verified` (API) | Crop-matched market evidence | Action-center filters by plot crop | API center response | Multi-crop browser check pending |
| `B11` | P2 | `verified` | Historical events don’t overwrite current | Sensor ingest chronology | `test_historical_sensor_does_not_overwrite_current_and_empty_rejected` | Physical ESP32 future |
| `B12` | P2 | `verified` (scaffold) | Invented calibration keeps warning | `calibration_unverified` flags | Same device test | Real calibration registry future |
| `B13` | P2 | `verified` | Empty measurements rejected; heartbeat separate | SensorInput validation | Same device test (422 on `{}`) | None |
| `B14` | P2 | `verified` | Partial PATCH preferences & farms | `PreferencesPatch`, `FarmPatch`, `exclude_unset` | `test_preferences_partial_patch_*`, `test_farm_name_only_patch_*` | None |
| `B15` | P2 | `verified` (API) | Farm/plot DELETE, device revoke/rotate, watch DELETE | `main.py` lifecycle routes | Device revoke test + routes present | FE editors for farm/plot still thin |
| `B16` | P3 | `implemented; verification pending` | OpenAPI security schemes + schemas module | `schemas.py`, custom `openapi()`, regenerated `contracts/openapi/schema.json` | Schemes present; many routes still loosely typed in OpenAPI responses | Generated client regen optional |
| `MD-01` | P1 | `verified` | Test DB guard refuses app DB | `test_guard.py`, `test_md01_db_guard.py` | Guard tests pass; 28-test suite isolated | PostgreSQL disposable target needs Docker |
| `MD-02` | P2 | `verified` (unit path) | Artifact digest/schema/shape + safe fail | `ModelRegistry` | MD-05 tests + registry code; broken-artifact HTTP 503 handler | Injected corrupt artifact CI job pending |
| `MD-03` | P2 | `verified` | Preflight backoff / deadline | `scripts/netlify-preflight.mjs` | Warm-up retry test passes (3 preflight tests) | Live Render wake smoke needs account |
| `MD-04` | P2 | `verified` (code) | `/health/live` + `/health/ready` | `main.py` readiness probes DB/storage/model | Ready endpoint implemented | Cloud health gate wiring pending |
| `MD-05` | P2 | `verified` (tooling) | Strict manifest validator | `scripts/validate_manifest.py`, `test_md05_manifest.py` | Unit tests pass | Full 570-image download for live hash verify |
| `MD-06` | P2 | `implemented; verification pending` | Non-mutating release verifier | `scripts/verify_release.py` | Script present; not run against missing native checkpoint | Native checkpoint + source images |
| `MR-01` | P2 | `in progress` | Pinned rehydration / run identity | Validator + docs notes | Tooling partial | Historical training log / pinned HF rehydrate |
| `MR-02` | P1 / Disclosed | `needs external evidence` | OOD/field validity | Research framing + ood_notice retained; no fake detector | Random-noise limitation preserved | Locked field/OOD labelled set |
| `MR-03` | P2 | `implemented; verification pending` | Prediction/threshold evidence tooling | verify/validate scripts | Needs source images | Recompute held-out tables when images available |
| `OP-01` | P2 | `verified` (code) | Model cache + inference semaphore | `ModelRegistry` cache, `acquire_upload_slot` → 429 | Upload path uses slot; platform upload tests pass | Hosted concurrency load test |
| `OP-02` | P2 | `needs external evidence` | Active CI | Template/docs only; no `.github/workflows` push | — | Owner GitHub `workflow` permission |
| `OP-03` | P2 | `implemented; verification pending` | Smoke/docker_verify binding notes | Scripts retained; docs updated in verification | Docker unrun | Install Docker Desktop / CI runner |
| `OP-04` | P3 | `verified` | Special-use IP rejection in preflight | `netlify-preflight.mjs` | Preflight URL tests include link-local/CGNAT/ULA | DNS-resolve-to-private optional hardening |
| `OP-05` | P3 | `in progress` | Portable setup + licence inventory | Repo `.venv` used; competition/licensing notes | README still needs final portable wording pass | Owner licence choice |

### Count check

- **51 IDs listed:** C-01..C-03 (3) + MAP-01 (1) + FE-01..FE-14 (14) + FE-C1..FE-C3 (3) + B01..B16 (16) + MD-01..MD-06 (6) + MR-01..MR-03 (3) + OP-01..OP-05 (5) = **51**.
