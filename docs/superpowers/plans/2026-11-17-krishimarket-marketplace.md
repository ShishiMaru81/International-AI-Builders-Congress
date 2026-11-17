# KrishiMarket marketplace implementation plan

Spec: docs/superpowers/specs/2026-11-17-krishimarket-marketplace-design.md. User requested implementation of the supplied complete specification; proceed without a redundant approval round. Existing stack and dirty feature branch preserved. Source snapshot: chat work/marketplace-prechange/source (127files).

## Review focus

1. Concurrent checkout/bids/expiry never oversell or duplicate money/stock mutations across processes.
2. Customer/farmer/admin role checks and IDOR protect all private commerce data; public outputs are coarse.
3. Auction reservation, reserve/deadline/claim timeout and direct buy remain independent.
4. Migrations/startup preserve old users/cases/farms; current native/Docker layout still imports and starts.
5. UI role/session/quantity/quote/context changes do not submit stale or wrong-user actions; no dead controls.

## Task1: Identity and non-destructive auth migration

Owner: identity implementer. Files: apps/api/app/db.py,identity.py,market_auth.py,market_admin.py; migrations0002(idempotent fix)/0003(identity); tests/test_market_auth.py. Do not edit main.py or web or market_models.py. Add User email/password_hash/role/is_active, scrypt signup/login farmer/customer, shared require_user/optional_user and safe user_view, operator admin CLI, auth rate limit and role tests. router prefix/api/v1/auth. Root integrates into main after implementation. Tests first RED then GREEN with standalone FastAPI auth router if main integration pending.

## Task2: Commerce persistence and API

Owner: root. Files market_models.py,market_schemas.py,market_service.py,market.py; migration0004; tests/test_marketplace.py. Implement profiles, products/images, cart/quotes, orders/seller fulfillment/payment records, stock/idempotency, auctions/bids/expiry, addresses/favorites/reviews/notifications/reports/audit/policy. Shared tx serializes DB writes. Main includes routers/models before startup, uses shared identity, preserves me/export/deletion and old modules. Test substantive scenarios including threaded SQLite and migration upgrade/preservation. Contract in docs/superpowers/plans/2026-11-17-marketplace-api-contract.md.

## Task3: Frontend marketplace

Owner: frontend implementer, after identity task settles; own marketplace*.tsx/css/types and e2e/marketplace.spec.ts only. Root integrates route whitelist/nav/anonymous bypass and User fields. Build discovery/detail, auth, cart/address/checkout, role dashboards/listing/gallery/orders/auctions/admin operations, honest demo cash status and location controls. Consume the exact contract. Test independent browser paths and responsive locale flow; no silent hardcoded data.

## Task4: Integration and verification

Owner: root + fresh reviewer. Main/session/nav integration; resolve existing duplicate market comparison actions using grouped existing endpoint. Worker/sweep CLI, configuration/OpenAPI/docs/status, migration tests, upload persistence, direct shopping and auction E2E. Full project gates and independent scoped review; fix critical/important findings with regressions. Keep current services3300/8300 and older3000/8000 separated; back up isolated SQLite before upgrade. Report remaining limits and exact running URL. Do not commit unrelated dirty tree or deploy.
