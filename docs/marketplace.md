# KrishiMarket marketplace

Implemented 17 November 2026 as an extension of the existing Next.js/FastAPI/SQLAlchemy application. The request source is retained in docs/superpowers/specs/2026-11-17-krishimarket-marketplace-requirements.md. Existing AgroDoctor/FloodCrop/market-intelligence code and records remain part of the same application.

## Open the current local build

- English: http://127.0.0.1:3300/en/marketplace
- Bangla: http://127.0.0.1:3300/bn/marketplace
- API: http://127.0.0.1:8300/docs

Choose Sign in/Join to register as a Customer or Farmer. A Farmer opens Seller studio, saves the public selling area, creates/selects an owned farm, adds a listing and uploads photos. A Customer browses publicly, optionally chooses manual area/coordinates or explicitly clicks GPS, enters quantity, adds to cart and checks out with pickup/delivery. Direct buying never requires a bid. Test goods/accounts in this local prototype are synthetic QA fixtures, not genuine sale offers.

The current demo uses this chat's isolated work/multicrop-demo.db and work/multicrop-images directory. Source and pre-upgrade database backups are under work/marketplace-prechange and work/pre-marketplace-demo-backup.db. Existing 3000/8000 services and original project database were not reset. No commit, push, external message, payment or cloud deployment was performed.

## Roles and authentication

Public signup accepts only farmer/customer. Passwords use salted scrypt; session tokens are random and stored as SHA256 digests. Every protected marketplace mutation checks current database role/activity and ownership. Suspension invalidates sessions. The last active admin cannot suspend or erase itself. Login/signup have bounded per-process rate limiting; shared proxy/edge limiting is required for a distributed production deployment.

Existing demo accounts retain farmer access. New regular accounts do not inherit another user's farms, orders or addresses. Role-sensitive queries are keyed by account identity; session initialization preserves public catalog loading, and stale identity responses are discarded.

Admin accounts require local operator provisioning, from apps/api:

```powershell
..\..\.venv\Scripts\python.exe -m app.market_admin create-admin --email YOUR_EMAIL --name Operator
```

The CLI prompts for a password twice. Automation may set KRISHIMARKET_ADMIN_PASSWORD in the process environment; no default password or public admin registration exists. Sign in with the provisioned credentials and open Administration. The QA admin used for verification has random scratch-only credentials and is not a shipped default account.

## Buying, stock and quantities

Prices are seller asking prices, BDT per declared unit. Supported units are kg/g/piece/bundle/crate. Quantity precision is three decimal places; kg allows fractional steps, other units use whole increments. Optional MOQ and optional maximum order are separate from stock. With MOQ absent, only a positive valid unit increment is required.

All monetary/quantity calculations use Python Decimal and database NUMERIC. API decimal fields are strings. Each line total rounds half-up to two currency decimals. Orders above BDT 999999999.99 are rejected rather than overflowing the prototype money domain.

Cart insertion does not reserve stock. Checkout revalidates every item, seller, quantity, price/terms quote and fulfillment destination in one serialized transaction, deducts available stock, creates seller/farm/fulfillment groups, stores snapshots and clears the cart. A multi-farmer cart creates independent seller orders. Delivery is charged once per seller/farm group at the maximum selected listing delivery fee; pickup is free. Both client and server display/enforce that rule. Unsupported destination/fulfillment choices fail explicitly.

Checkout, bid and winner-confirm APIs require an Idempotency-Key. The same key/body returns its original result; a reused key with different data returns 409. After a stale checkout 409, the cart is refreshed and the user must review and click again; no changed-price checkout is auto-submitted. A failed refresh disables checkout until retry succeeds.

SQLite BEGIN IMMEDIATE/busy timeout and a PostgreSQL transaction advisory lock serialize marketplace writes across workers. This avoids overselling and race-prone in-memory-only locking, at the cost of throughput. Concurrent purchase and bid tests execute real competing HTTP requests. Stock/term edits require expected_version; unit/step/farm are immutable after committed orders/auctions.

## Optional auctions and expiry

A published eligible product can have a farmer-created draft or live/scheduled auction. Publishing reserves a distinct lot while leaving enough free fixed-price stock for an ordinary valid order. Drafts do not reserve stock. Product pages keep Buy Now/Add to Cart separate from bidding; the customer explicitly confirms a bid.

Server UTC controls starts/ends. First bid must meet starting price; subsequent eligible bids meet highest+increment. Farmers cannot self-bid. Immutable history is retained; suspended bidders are marked ineligible and no longer set the live floor. Accepted bids have transaction-safe rate limits and idempotency. Auction terms can only be edited while draft.

At expiry, the highest eligible active bidder wins only if the private reserve is met and seller/listing remain eligible. No-bid/reserve-not-met lots end and release stock. Winners have 24 hours from end to confirm an unpaid COD/pickup order; otherwise unfulfilled stock releases. Confirmation does not charge a card. A confirmed awarded lot does not block later lots from the same product.

Farmers may cancel before bids; auctions with bids need admin review. A seller cannot evade that rule by pausing/archiving its listing. Admin moderation/suspension retires ineligible active lots. Pending seller orders expire after 48 hours; ready-for-pickup collection reservations expire after 7 days. Cancellation/expiry returns logical stock exactly once. Physical stock and actual collection still require honest farmer reporting.

A lifecycle worker settles timeouts without an open browser. Relevant requests also settle state atomically. From apps/api:

```powershell
..\..\.venv\Scripts\python.exe -m app.market_worker --once
..\..\.venv\Scripts\python.exe -m app.market_worker
```

The second command runs every 30 seconds. It is currently running for the isolated local demo. A production supervisor should restart a failed worker; Compose config includes one.

## Orders, payments and customer tools

Seller transitions are pending→confirmed→preparing→ready_for_pickup/out_for_delivery→delivered. Customers can cancel pending orders; seller/admin cancellations are restricted before goods leave fulfillment. Later problems use reports/disputes, not a fictitious refund or automatic return-to-stock.

Payment status is separate: demo_unpaid or cash_recorded. Cash received is an explicit unverified seller report at delivery. No payment gateway, card capture, automatic charge, real refund, courier tracking or delivery guarantee is implemented.

Customers have purchases, active/winning bid history, favorites, saved addresses, reviews for delivered purchased items, report submission and in-app notifications. No advisor, SMS or email service is silently contacted.

## Discovery and privacy

The default is nearby-first within 20 km among matching available listings; farther products remain searchable/orderable where delivery/pickup supports them. Sort overrides include nearest, price and newest. An optional district filter is explicitly separate from chosen location context. With no coordinates, the UI gives a nationwide fallback and never calls district names a distance.

Distances use Haversine against coarse seller coordinates rounded to 0.01 degree. They are approximate geographic distance, not road distance or fulfillment feasibility. Exact customer/home coordinates and seller phone are excluded from public responses. Manual district/area/address works without GPS; precise location is optional. This is prototype-scale filtering in application code, not a PostGIS/geography-indexed production search deployment.

Order participants see only authorized contact/fulfillment information. Farmers only see their seller groups. Pickup orders do not reveal the customer's home address. Published product photos are intentionally public; draft/hidden photos require owner/admin or appropriate historical order access.

Images: supported JPG/PNG/WebP, at most 6 per listing, 8 MB each, 20 MP decoded; reject invalid/animated files, apply EXIF orientation, composite alpha, re-encode to metadata-free JPEG, cap display dimensions and clean up failed writes. Files use the existing storage volume under marketplace/. Both metadata and photo bytes survived a native API restart.

Owner workspace exports include marketplace data. Account deletion requires resolving open commitments; afterwards profile/contact/address data is removed, listings archived and closed order/bid/audit history retains an opaque anonymous user ID. Deleting an existing farm requires first archiving dependent listings and resolving orders; closed references detach without destroying history.

## Admin tools

Administration connects to backend data: user suspension, farmer verification, listing visibility moderation, report/dispute resolution, order/auction oversight, database-derived analytics, immutable audit viewing and policy controls. Reports/audit support human fraud review; no automated fraud-prediction model or real identity verification provider is claimed. Turning on require_verified_farmer applies to already published listings and new publication. No UI can promote itself to admin.

## Migrations and Docker

Migrations 0003 (identity) and 0004 (marketplace) are additive. Existing 0001/0002 upgrades now tolerate compatibility-created tables/columns/indexes, preserving existing values. Fresh, legacy/compat-first and repeated upgrade paths were tested. Always back up production data before any migration.

From apps/api, using the intended DATABASE_URL:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m alembic current
```

Compose reuses the PostgreSQL database and existing images volume, adding marketplace-worker; it does not delete volumes or reset data. The volume also stores product images. Docker executable was unavailable here: YAML/service wiring was validated, but no new Linux image/container or live-cloud run is claimed. The free-host setup still has ephemeral-storage/resource limits described in existing deployment docs. A hosted deployment must run the lifecycle worker as a managed process/scheduler and configure durable media storage.

## Verified checks

| Check | Result |
|---|---|
| Full API suite | 80 passed |
| Web unit suite | 18 passed |
| Full browser suite | 17 passed |
| Marketplace browser cases | 7 passed, including 3 live flows and 4 isolated failure/ranking regressions |
| Additional real admin browser check |Login, verification, moderation, report resolution, policy and audit viewing passed; no page errors |
| TypeScript / production build |Passed |
| ESLint | 0 errors; 9 existing warnings in older workspace/Doctor/config code; marketplace modules pass scoped lint |
| Migrations | 0004 head; unversioned/compat-first preservation and repeated upgrade tests passed |
| Concurrency |Simultaneous checkout cannot oversell; concurrent bid ordering preserves eligible highest and reserved quantities |
| Persistence |Listing count and exact product-photo bytes survived API restart |
| Independent follow-up | 34 marketplace/auth/migration API tests and 4 browser regressions passed; all 6 review findings closed |

The former duplicate market comparison action was fixed by using the existing grouped scenario endpoint. The original connected journey now passes, including AgroDoctor upload, FloodCrop area/weather behavior, market math and action center. Original tomato and new multi-crop model digests remain unchanged.

## Files and boundaries

Backend modules: identity.py, market_auth.py, market_admin.py, market_models.py, market_schemas.py, market_service.py, market.py, market_privacy.py, market_worker.py; main/db integration and migrations. Frontend: marketplace*.tsx/css, marketplace-types.ts, session lifecycle, workspace navigation/catch-all route integration. Tests cover auth/roles, commerce, edge cases, migrations and UI journeys. OpenAPI and planning/review ledgers are updated.

Remaining production work: verified customer/seller identity, password recovery/email verification, shared multi-instance edge throttling, payment/courier integration, PostgreSQL/PostGIS load testing, monitored worker operations, object/media retention/backups, independent security/accessibility/agronomic translation review. Core UI is bilingual; some raw statuses/help text remains English. No zero-bug, production-readiness, real trade volume, verified income or field-accuracy claim is made.
