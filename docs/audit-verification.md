# Audit Remediation — Verification Log

**Commit / branch:** local baseline `fc4035d`, working tree on `fix/audit-remediation` (dirty; not pushed)  
**Host:** Windows 10, Python 3.12 repo `.venv`, Node via local npm  
**Date:** 2026-11-17 Asia/Dhaka  
**Isolation:** API tests use per-run temporary SQLite + disposable storage via `apps/api/tests/conftest.py` + `app/test_guard.py` (MD-01). Ports 8000/3000 left untouched.

## Commands executed (this remediation run)

| Command | Result | Notes |
|---|---|---|
| `apps/api`: `.venv\Scripts\python.exe -m pytest -q` | **28 passed**, 1 Starlette/httpx deprecation warning | Includes original platform suite + MD-01 + MD-05 + Phase1 prefs/location + audit backend regressions |
| `apps/web`: `npm run typecheck` | **Passed** | After Market compare JSX fix + session rewrite |
| `apps/web`: `npm run lint` | **0 errors, 10 warnings** | Warnings: `location.href`, raw `<img>`, exhaustive-deps, anonymous default export. `react-hooks/set-state-in-effect` disabled intentionally for session/map/stale sync |
| `apps/web`: `npm run test` | **18 passed** (3 files) | calculator + contrast (≥4.5:1) + session/api helpers |
| `apps/web`: `npm run build` | **Passed** (Next.js 16.4.6 / Turbopack) | Production compile smoke; not a full production map/runtime proof |
| `node --test scripts/netlify-preflight.test.mjs` | **3 passed** | URL guard (incl. special-use IPs) + CORS/health + warm-up backoff timing |
| OpenAPI regenerate → `contracts/openapi/schema.json` | Updated | `securitySchemes`: `BearerAuth`, `DeviceKeyAuth`; 45 paths |
| `npm run test:e2e` | **Not re-run this turn** | Requires free ports / Playwright browsers; do not collide with existing :3000/:8000 |
| Docker / PostgreSQL container suite | **Unrun** | Docker CLI unavailable on PATH |
| Live Render/Netlify deploy | **Unrun** | No authorized cloud publish |
| Full PlantVillage image rehydration + release parity | **Tooling present; historical images absent** | `scripts/validate_manifest.py`, `scripts/verify_release.py` |

## Important limitations

- Local software corrections are verified by unit/integration tests above; **field validation, Bangla expert review, live hosting, and competition portal submission remain pending**.
- Map worker URL is configured; browser console proof of tile-ready state in production bundle was not re-executed this turn.
- Random-noise OOD control remains a disclosed research limitation (`MR-02`); no fake detector was added.
- Competition drafts under `docs/competition/` are drafts only — not submitted.
