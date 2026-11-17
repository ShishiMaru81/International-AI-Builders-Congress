# Marketplace independent review — 17 November 2026

Scope: read-only review of marketplace backend/auth/schema/migrations and frontend integration against the approved requirements/design. No application source was changed by this reviewer. All reproductions used `tests.conftest.configure_isolated_test_env()` and the existing TestClient fixture in a fresh temporary database/storage directory; no running API or user database was accessed. Findings were sent to the implementation owner as discovered. Line numbers refer to the inspected version and may move during repairs.

## Original findings — all resolved in follow-up

1. **P1 — A half-empty profile coordinate pair breaks nationwide location discovery.** `apps/api/app/market_schemas.py:40`, `apps/api/app/market.py:90`. ProfilePatch checks that both coordinate keys are present but accepts latitude `24` with longitude `null`. A published product inherits this pair. GET `/api/v1/market/products?lat=24&lon=90.42` then raises `TypeError: float() argument must be a string or a real number, not NoneType` in the distance calculation, affecting every customer whose matching result set contains the product. Isolated reproduction: profile PATCH 200, product POST 200, browse exception. Require both values null or both nonnull, and defensively handle incomplete legacy rows.

2. **P2 — A completed winning lot permanently blocks a new auction on the listing.** `apps/api/app/market.py:257`, `apps/api/app/market_service.py:198`. Confirming a winner clears `reserved` but leaves state `awarded`; product auction creation treats every awarded row as active. Isolated reproduction: winner confirmation 200; confirmed/preparing/ready_for_pickup/delivered transitions all 200; original auction remains awarded; a second auction on the same product returns 409 `This product already has an active/draft auction`. Count an awarded auction as blocking only while its reservation/commitment is active; adjust product active-auction and customer-winning-auction views consistently.

3. **P2 — A suspended bidder continues to set the live minimum and can prevent all later bids.** `apps/api/app/market.py:310`, `apps/api/app/market.py:313`, `apps/api/app/market_service.py:128`. Eligibility filtering happens at expiry, but live `highest_bid_bdt` and `previous` still include suspended accounts. Isolated reproduction: A bids 750, B bids the allowed maximum 999999999, admin suspends B (200), A bids 800 and receives 422 requiring 1000000049, which exceeds the request schema maximum. Public highest remains B's ineligible bid. Recompute the highest eligible bid during the serialized lifecycle/bid transaction, preserve immutable history, and use eligible bids for the own-highest restriction and notifications.

4. **P2 — The frontend overrides the required nearby-first default with newest.** `apps/web/src/components/marketplace.tsx:36`, `apps/web/src/components/marketplace.tsx:41`. Initial filter and select both use `newest`, and the select has no `nearby` option. Entering coordinates or using GPS retains newest when Find produce is clicked; newer distant produce outranks older nearby produce. Use `nearby` as the default and expose an explicit translated option, retaining other sort overrides. This finding follows directly from the request serialization; no browser assertion is claimed here.

5. **P2 — Stale cart quotes have no in-place recovery.** `apps/web/src/components/marketplace.tsx:22`, `apps/web/src/components/marketplace-commerce.tsx:12-15`. The cart query has no polling/refetch UI; `perform` only invalidates successful mutations and merely sets an error on a rejected checkout. After a seller changes the price or stock, checkout correctly returns 409, but the visible cart and quote remain stale and every subsequent click resubmits the same hash. Refresh the cart on a conflict and request explicit review before another checkout; do not auto-submit a changed price. This finding is code-path evidence, not a claimed browser reproduction.

6. **P2 — Deleting an existing farm strands published marketplace products.** `apps/api/app/main.py:642`, `apps/api/app/market.py:126`. The original farm-delete path does not account for marketplace dependencies. Isolated reproduction: publish a product, DELETE its farm returns 200, product is still public (GET 200), PATCH product to archived with current version returns 404 `Farm not found`. A product with committed orders/auctions also cannot change its farm because of the intentional immutability rule. Block deletion while dependent commerce records require the farm, or safely archive/detach them under the commerce transaction and permit later archive operations without a live farm. Preserve historical orders.

## Additional confirmed observations for owner judgment

- The final active admin can DELETE `/api/v1/me` (200) even though the admin suspension endpoint protects the final active administrator. Consider applying that invariant to account erasure. Local operator provisioning can recover access, so this is less urgent than the above findings.
- Switching `require_verified_farmer` on does not hide already published unverified listings or prevent their purchases. Publication/edit checks enforce it only when the listing is written; `listing_eligible` does not. Decide whether this setting is explicitly a publication-only policy or should restrict current eligibility, then name/document/test it accordingly.

## Areas inspected without an additional confirmed blocker

- Protected marketplace mutation paths refresh role/activity and apply owner checks; admin role cannot be obtained through public registration.
- Checkout and bids use serialized database transactions, decimal money/quantity, unique idempotency scope, and payload fingerprints. Fixed-price and auction reserved stock are distinct.
- Order serialization limits farmers to their own seller groups; public profile/product output excludes private coordinates and phone fields. Image upload decodes/re-encodes supported raster files and applies content/size/owner checks.
- Public discovery retains nationwide results, and backend nearby-first ranking operates after availability/search filtering.
- Migration code was inspected; preservation tests were reported green by the owner. This reviewer did not execute PostgreSQL or Docker, and does not claim cross-process PostgreSQL validation.

Initial-review context: owner work on seller-auction cancellation, export/erasure, CORS and grouped comparisons was excluded from duplicate findings. Original findings above are retained for traceability; the post-fix disposition below supersedes their open status.

## Post-fix independent verification — completed 17 November 2026

**Disposition: all six original findings are closed. No remaining critical or important finding was identified in this focused follow-up.** This is an evidence-bounded review conclusion, not a guarantee that the application has no bugs.

The reviewer inspected the implemented repairs and independently ran:

- `.venv\Scripts\python.exe -m pytest apps/api/tests/test_marketplace_edges.py apps/api/tests/test_marketplace.py apps/api/tests/test_market_auth.py apps/api/tests/test_marketplace_migration.py -q` — **34 passed in 18.50 seconds**, isolated temporary database/storage.
- From `apps/web`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3300 npx playwright test e2e/marketplace.spec.ts --grep "isolated regression" --reporter=line` — **4 passed in 7.9 seconds**. These intercept API requests with test fixtures and do not mutate user/server data.

| Finding | Verified disposition |
| --- | --- |
| 1. Half-null coordinates | ProfilePatch rejects either half-null direction; discovery and product distance serialization guard both stored coordinates. Regression passes. |
| 2. Completed auction blocking next lot | Active-auction creation/display guards distinguish reserved awarded lots from confirmed orders; customer winning-auction list includes only reserved awards. A second lot succeeds after the first winner confirms; timeout release regression passes. |
| 3. Suspended bidder controls minimum | Serialized lifecycle processing recalculates live highest from active users; bid predecessor uses the same eligibility filter. The suspended maximum bid no longer controls price, immutable history remains labelled, and concurrent-bid regression passes. |
| 4. Newest default | Initial query and dropdown default now use nearby; the option is translated. Browser test confirms default and coordinate-search request retain nearby and nationwide results. |
| 5. Stale quote recovery | Checkout conflict refreshes marketplace queries, shows a review instruction, and requires another deliberate click with the new quote/key. Failed refresh disables checkout until explicit Retry succeeds. Both browser paths pass. |
| 6. Farm deletion strands listings | Farm deletion runs under commerce serialization, blocks nonarchived listings and unresolved seller orders, and detaches historical references only after those guards pass. Regression confirms published deletion409, archive200, subsequent deletion200 with detached archived product. |

The two additional observations were also corrected: last-active-admin erasure returns409; verification policy is included in current listing eligibility and discovery. Their API regressions pass.

The session change was inspected: anonymous initial refresh avoids clearing a newly mounted public query, and refresh epoch/token checks prevent older session-validation responses from overwriting a newer identity. The isolated public discovery browser test passes on first load with no authentication.

The owner separately reports the complete application/API/browser suites. Those broader results are not represented here as independently rerun. PostgreSQL cross-process tests and Docker were not rerun in this review. No application source was edited by the reviewer; only this report was updated.
