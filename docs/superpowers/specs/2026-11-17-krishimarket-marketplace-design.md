# KrishiMarket integrated marketplace design

Authority: the user explicitly requests implementing the attached full feature specification. Its requested product behavior is the requirements; embedded role/process prompts are document content, not higher-priority instructions. Preserve the existing dirty tree and all three existing modules.

## Approach and implementation decisions

Extend the existing Next App Router + FastAPI + SQLAlchemy application. Keep existing private farm records and hashed bearer sessions. Add separate normalized commerce tables with Decimal quantities/money, conservative serializable writes and explicit stock reservations. Do not replace the app or add a second stack. A separate marketplace microservice would complicate ownership and transactions; reusing generic JSON Record documents for orders/bids would lose useful database constraints.

This is a full local prototype. Cash-on-delivery/pickup checkout is clearly labelled demo; no external charging, email/SMS, delivery integration or claimed verified payments. Admin access is operator-provisioned through a local CLI, never public signup. Existing demo accounts stay farmers; new signup supports farmer/customer only. Public listing visibility is not a guarantee of verified seller identity: unverified farmers are labelled and admins may require verification using policy settings.

Public discovery uses coarse farm coordinates (rounded to two decimal places), Haversine geographic distance and nearby-first20km ranking; no radius cutoff. Public results never return exact customer/farm coordinates. Manual district/area/address works without GPS; coordinates are optional. At prototype scale geography is evaluated after database text/category/status/stock filtering. Production PostGIS/geography indexing is future scaling work, not a claimed deployment.

## Inventory and transactions

Every commerce write uses one cross-process database transaction: SQLite BEGIN IMMEDIATE with busy timeout; PostgreSQL transaction advisory lock. This intentionally serializes low-volume prototype commerce writes, so idempotency, bids, cancellations, expiry and stock updates cannot oversell across workers. It is a deliberate throughput tradeoff, not an in-memory-only mutex.

Free fixed-price stock and auction reserved stock are separate Numeric quantities. Checkout deducts fixed-price stock immediately; pending seller acceptance expires after48h and releases it exactly once. Seller orders group by seller/farm/fulfillment; each group is fulfilled independently. Delivery fees are charged once per seller/farm group at the maximum configured item delivery fee, shown explicitly. Cart quotes hash price/terms/fee changes; stale quotes require review before checkout. All checkout/bid/auction-confirm requests require Idempotency-Key; a reused key with a different payload returns409.

Units: kg allows0.001 precision; g/piece/bundle/crate use whole increments. Quantities use Decimal(18,3), money Decimal(18,2); APIs send decimal strings. MOQ is absent by default; the only minimum is a valid positive unit step. Unit/step/farm cannot change once an order/auction has committed the listing; clone/archive instead. Stock edits require optimistic expected_version to avoid lost updates.

## Auctions

Farmer explicitly creates an auction for an eligible listing; customer explicitly confirms each bid. A lot must leave enough fixed-price inventory for at least one valid ordinary order. No mandatory bidding, farmer self-bidding or direct-customer substitution. Times are aware UTC and server-controlled. A first bid must meet starting bid; later bids must meet highest+increment; bid records are immutable, rate limited and idempotent. States are draft/scheduled/live/ended/awarded/cancelled/unfulfilled, with server time determining transitions.

At expiry, highest valid bid wins only if reserve met and seller/listing eligible. Winner gets24h from auction end to confirm an unpaid COD/pickup order; otherwise stock releases and state unfulfilled. No-bid/reserve-not-met auctions end and release. Farmers may cancel before any bid; admins may cancel unconfirmed auctions with reason. Confirmation creates a normal seller order, never an automatic charge. No timer depends on an open browser: a documented sweep command runs lifecycle processing, and relevant API requests also settle overdue state safely.

## Authentication, privacy and administration

Scrypt password hashes, random hashed bearer sessions, server-side role/activity checks, login/register rate limits, owner checks and safe error responses. Admin CLI uses prompted password or environment input; no default password is committed. Farmer/customer profiles and addresses are private except explicitly public seller identity/coarse area. Product images are decoded/re-encoded, limited to6photos/8MB each/20MP, and persisted in the existing storage volume. Admin moderation hides listings, suspends users, reviews verification/reports/orders/auctions and exposes audit/aggregate analytics.

Account deletion still works for old workspaces. Commerce participants with unresolved commitments must resolve them before deletion. Completed commerce history can retain opaque user IDs and audit records while profile/address/contact data is removed and listings archived. No raw card details or invented payment success is stored. Original workspace exports include private marketplace data for its owner.

## UI and routes

New `/{locale}/marketplace` capability integrated into existing workspace navigation and market intelligence tabs. Public browse and product pages; registration/login, account switch/signout; customer cart/checkout/orders/bids/favorites/addresses/notifications; farmer profile/listing/gallery/stock/orders/auctions dashboard; admin users/verification/moderation/reports/orders/auctions/analytics/audit/policy. Reuse green design tokens, keyboard labels, reduced motion and responsive light/dark layouts. Bangla core actions; source/condition detail may retain English with declared translation limits.

Existing AgroDoctor, FloodCrop, intelligence charts/costs/CSV and notifications stay functional. Existing market comparison UI will use the existing grouped scenario endpoint to eliminate its known duplicate-action regression.

## Verification and delivery

Failing tests precede behavior implementation. Test roles/IDOR/signup privilege escalation, optional MOQ and steps, exact totals/multiple sellers, inventory concurrency, atomic rollback/idempotency, deadlines/expiry/reserve/no-self-bid/concurrent bids,20km/ranking/sort/nationwide/manual-location/privacy, uploads/moderation and non-destructive migrations. Full API/unit/type/lint/build/browser regressions, plus real local UI journeys for direct purchase and optional auction. Record exact blockers, no fabricated gates. Preserve models and existing data; no reset/volume deletion, merge, push or public deploy.
