# Marketplace frontend implementation

Entry point: `Marketplace({locale: 'en'|'bn', path: string})` from `apps/web/src/components/marketplace.tsx`. `path` is the full `marketplace/...` path. Root owns route, shell, session, and API integration.

## Implemented screens

- Public discovery, search, category/unit, ascending/descending price, nearest/newest, optional manual district/context and coordinates, explicitly requested GPS, and an explicitly separate district filter. Nationwide fallback and approximate distance are explained.
- Public product details/gallery, optional minimum/maximum quantities, fixed-price Buy now and Add to cart, optional auction separate from direct shopping, public farmer profiles, and buyer reviews.
- Real registration/login, customer favorites, saved addresses, cart quantity/remove, per-product fulfillment and seller/farm/method delivery fee estimates, server quote hash, and idempotent demo checkout.
- Buyer/seller orders, cancellation, fulfillment transitions, unpaid/unverified cash states, delivered-item reviews, reports, notifications, and profile settings.
- Seller listing create/edit/archive, required owned-farm selection and a create-farm form when none exist, gallery upload/delete, stock, optional auction creation/drafts/publish/cancel, and seller totals.
- Admin bounded lists, user suspension, separate farmer verification, product moderation, report decisions, order cancellation interventions, auction interventions, immutable audit views, analytics, and policies.
- Responsive scoped green styling, dark-mode variables, and English/Bengali core controls. Private images use bearer-authorized fetch with object URL cleanup; public relative image paths resolve to the API origin.

## Verification

- Wrote Playwright tests before implementation. Initial public-route test failed with the expected marketplace 404/missing heading.
- First integrated browser run: public English/Bengali at 360px passed. Direct-purchase and auction tests exposed seller form accessible-label issues and missing `Idempotency-Key` CORS allowance. Labels now use explicit generated IDs, and root added the CORS header.
- Repeated `npm run typecheck` and scoped ESLint checks passed during implementation and alignment with the final live API schemas.
- Desktop (1440px) and Bengali mobile (360px) screenshots were rendered and visually inspected under `work/marketplace-public-*.png`. Layout fits the viewport; no horizontal overflow was observed. Final snapshots were refreshed with the loaded live catalog after fixing anonymous startup caching. Bengali dark mode was also inspected; its accent text and summary controls use a brighter green while primary buttons retain contrasting white text.
- Final integrated run passed: `npx playwright test e2e/marketplace.spec.ts --reporter=line` — **7/7 passed in 37.4 seconds**, using the live 3300 frontend and 8300 API. The direct journey created an owned farm/listing, uploaded a photo through the UI, decoded its public image as the buyer, searched with manual coordinates, rejected a below-MOQ purchase, checked out with a saved address and quote, completed every pickup fulfillment transition, and showed delivery to the buyer. The optional-auction journey confirmed a bid explicitly, polled server state until award, confirmed the winner lot, and showed an unpaid auction order. Four isolated regression tests also passed. Fresh accounts/farm/product/address fixtures are used; server clocks are never altered and files are uploaded only after controls are ready.

## Integration notes and limits

Canonical field names come from live `market_schemas.py`, `market.py`, and `market_service.py`: `seller_name`, `seller_verification`, `auction_reserved`, cart line `total_bdt`, price ascending sort `price`, auction nested `product`, cancellation `cancelled`, and separate admin farmer-verification endpoint. Free stock already excludes auction reservation.

Browser base URL honors `E2E_BASE_URL` or `PLAYWRIGHT_BASE_URL`, default `http://127.0.0.1:3300`. API fixtures honor `E2E_API_URL` or `AGROSPHERE_API_URL`, default `http://127.0.0.1:8300/api/v1`.

All commerce notices describe prototype cash records. No payment gateway, verified payment, yield, savings, or field-validation claim is introduced. Backend policy and role checks remain authoritative. No commits or deployment were performed.

## Review corrections and isolated regressions

- Discovery defaults to `nearby`, exposed in the sort menu. Supplying location coordinates does not silently introduce a district filter or a 20 km exclusion.
- Checkout catches `ApiError.status === 409`, refreshes the current user's marketplace query context, and asks the buyer to review quantities, prices and delivery choices. It never automatically resubmits. A failed cart refresh leaves checkout disabled until the cart loads successfully. A changed quote receives a new idempotency key on the next deliberate submission.
- Historical bids with `eligible === false` stay visible and are labeled “Ineligible bid”; they do not suppress bidding as an eligible highest bid.
- Removed a duplicate product-card title during the static review.

Four isolated browser regressions passed with every API request intercepted. Both initial discovery and stale-quote regressions were observed failing against the previous UI before the corrections. Additional tests cover failed-refresh blocking and ineligible-bid labels. Latest typecheck and scoped ESLint passed. No live API/browser test ran during the root-requested service hold; the complete live suite passed after the root READY signal.

A stronger public regression exposed initial anonymous session cleanup clearing an already mounted catalog observer, leaving it on Loading after HTTP 200. Root corrected SessionProvider initial cleanup and stale identity responses. The strengthened public test now waits for successful catalog responses and verifies loading disappears in both locales; all seven tests passed afterward. Final desktop, Bengali mobile, and Bengali mobile dark screenshots show loaded listings without horizontal overflow.
