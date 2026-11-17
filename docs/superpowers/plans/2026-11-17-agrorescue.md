# AgroRescue Implementation Plan

> Use superpowers:subagent-driven-development for bounded independent components, with integration and final review in this session.

**Goal:** Add useful, honest farm selling decision support and matching marketplace crop images.
**Architecture:** FastAPI symbolic planner stored in shared owned Records; Next.js bilingual client; local crop image fallbacks preserving uploads.
**Tech Stack:** Existing FastAPI/Pydantic/SQLAlchemy, React/Next.js, pytest/Vitest/Playwright.
**Spec:** docs/superpowers/specs/2026-11-17-agrorescue-design.md

## Constraints and review focus
- Preserve all existing uncommitted project work, private ownership, original models and original services.
- No invented buyers/prices/model metrics or automatic selling. Declare deterministic planning and assumed outcomes.
- Unknown cost/readiness must block premature recommendations; simulated and stale source evidence stays visible.
- Mixed price basis and foreign-plot evidence must be rejected.
- Edit/plot/account changes must clear stale results; uploaded pictures always take priority.

## Tasks
- [x] Backend: failing API tests in apps/api/tests/test_rescue.py; implement apps/api/app/rescue.py and router wiring, owned persistence/history/delete/action/source validation. Verify focused tests.
- [x] Images: failing crop matching tests; 20 locally licensed photos, bilingual matching, shared ProductImage fallback and illustrative label. Verify tests and actual visual matching, including existing tiny uploads.
- [x] Frontend: apps/web/src/components/agrorescue.tsx and CSS/types; integrate workspace/route; accessible bilingual form, source refresh, questions, costs, snapshots and history. Add browser regression tests.
- [x] Integration/review: 125 API, 74 UI unit, 28 browser tests passed; production build/typecheck passed; lint 0 errors/9 existing warnings. Review fixes and limits in docs/status.md and docs/agrorescue.md.

Ruling: Work in the current fix/audit-remediation checkout because the requested existing marketplace and multicrop features are uncommitted here; creating a fresh checkout from HEAD would omit them. The user's explicit acceptance authorizes this feature without a second design approval.

Final review: fixed source unit/type filtering and confirmation invalidation. Full browser run initially exposed the existing MapLibre worker namespace assignment bug; reproduced with deterministic tiles, replaced with setWorkerUrl, then all 28 tests passed. Full commerce tests ran against an isolated database with separate Next build directory to preserve the user's workspace. QA servers stopped afterwards; app remains at 3300/8300.
