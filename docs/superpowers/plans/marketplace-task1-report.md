# Marketplace Task 1: Identity implementation

Implemented only the assigned identity scope; existing dirty changes were retained. No main.py, schemas.py, commerce model, or frontend changes were made by this implementer. No live database was reset, migrated, or opened for testing. No commit was created.

## Contracts

- `User` gains nullable unique email, nullable scrypt password hash, role (server/default farmer), and active status (server/default true). Legacy demo users retain their identity and become active farmers.
- `identity.require_user` and `optional_user` validate existing SHA256-hashed opaque sessions, expiry, user presence, and active status. Anonymous optional access returns null; malformed or invalid supplied credentials return401. `user_view` exposes only id/name/email/role/preferences/is_active.
- `market_auth.router` prefix `/api/v1/auth`: register and login return200, matching the agreed integration contract. Both return `{token,user}`. Emails are trimmed/lowercased, signup allows only farmer/customer, unknown fields are rejected, passwords require10–1024characters, and no public admin creation exists.
- Registration has a database unique constraint/index and translates insert/commit uniqueness races into409. Password hashes use random16-byte salt and scrypt N16384/r8/p1 with timing-safe digest comparison; nonexistent-account login also performs scrypt work. Token values are never stored raw.
- Auth attempts share a thread-safe limiter per application:12 attempts/minute per IP+email, plus60/minute per IP; memory is bounded to4096keys. It deliberately ignores forwarded headers. Multi-process/distributed deployment needs a trusted shared edge limiter: counters are currently per process.
- Operator provisioning: from `apps/api`, `python -m app.market_admin create-admin --email operator@example.com --name Operator`. Password is prompted twice, or supplied by `KRISHIMARKET_ADMIN_PASSWORD`; no password command argument or default credential exists. Existing accounts are rejected without changing their role. CLI emits only email/id.
- `ensure_compat_schema` adds identity columns and unique email index without deleting rows. Migration0003 is additive and tolerates compatibility-created columns. Migration0002 now skips existing columns/indexes and preserves existing non-null relational values during payload backfill.

## Verification

The first test run preceded implementation and demonstrated missing auth router/identity columns (one failed test plus10 setup failures on the absent router). Subsequent focused run:14 passed, then14 passed after adding operator login assertion.

Covered signup/login and safe responses, raw-token absence in database, forbidden role escalation, extra privilege fields, malformed/weak inputs, case-insensitive duplicate registration, wrong password/unknown account, inactive users/sessions, expired tokens, optional authentication, bounded auth response, concurrent same-email registration (six requests:one200 and five409, one user/session), admin creation/login, executable environment-password CLI and duplicate rejection, and fresh/compat-first legacy migration preservation.

Commands from repository root:

```
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_market_auth.py -q
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
```

Full API run at the current parallel integration stage:60 passed,5 errors,1 PyTorch deprecation warning. All5errors are new marketplace tests receiving404for `/auth/register` because main integration is still owned by root:

- `test_direct_purchase_without_bid_and_replay`
- `test_moq_optional_precision_units_and_fulfillment`
- `test_nearby_prioritizes_without_hiding_far_and_public_privacy`
- `test_auction_opt_in_reserved_stock_increment_and_deadline`
- `test_simultaneous_orders_cannot_oversell`

Register was aligned to200 at root's request and the focused14tests passed again after that change. Root remains responsible for replacing main's current_user with shared identity, including the auth router, preserving demo/logout, and running combined API/UI/build/E2E checks after integration.
