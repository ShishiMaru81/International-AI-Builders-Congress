# ZYNTRIX AGROSPHERE AI — KRISHIMARKET AI MARKETPLACE UPGRADE

> **Purpose:** Complete implementation specification for OpenAI Codex. Extend the **existing** ZYNTRIX AgroSphere AI repository. Do **not** create a separate application or replace working AgroDoctor AI, FloodCrop AI, or existing KrishiMarket market intelligence.

## 1. Role and objective

Act as a senior full-stack software engineer, database architect, application security engineer, and UI/UX designer. Inspect the repository before changing code. Implement a working, tested farmer-to-customer marketplace as part of **KrishiMarket AI**, supporting:

- **Three primary roles:** Admin, Farmer, Customer.
- **Direct fixed-price purchasing as the default**; customers never have to bid.
- **Optional bidding**, enabled per listing by the farmer and used only if the customer chooses.
- **Optional minimum order quantity** (MOQ) set per product by the farmer, with no minimum imposed when the field is unset beyond the product's valid unit increment.
- **20 km nearby-first product discovery** based on customer-selected location, without restricting browsing and purchases from farther away in Bangladesh (subject to delivery/pickup availability).
- Listings, inventory, carts, orders, auctions, notifications, and secure admin operations.

Preserve all existing features, data, database migrations, authentication, and Docker setup. Build actual integrated functionality, not decorative UI placeholders. A zero-bug guarantee is impossible: implement automated tests, run them, fix discovered failures, and report remaining limitations accurately.

## 2. The three roles and permissions

### Admin
- Manage users and review farmer verification.
- Moderate listings, handle reports and disputes, and suspend fraudulent activity.
- Review orders, auctions, marketplace analytics, and audit logs.
- Configure reasonable platform-level policies.

### Farmer
- Create/edit farmer profile, farm and approximate public location.
- Add/edit/archive agricultural product listings and images.
- Set fixed price, stock, units, supported fulfillment areas, and **optional MOQ**.
- **Optionally** enable auctions; define lot size, starting bid, minimum increment, timing, and optional reserve price.
- Process orders, manage fulfillment and stock, view bids and sales.

### Customer
- Register/login; select location manually or optionally allow geolocation.
- Search and browse products from across Bangladesh, with relevant listings inside 20 km shown first.
- Buy immediately at fixed price without bidding; manage cart, checkout, orders, favorites, and addresses.
- **Optionally** bid where a listing has auctions enabled; see bid history, winning status, and notifications.

Enforce role permissions server-side on every protected endpoint; frontend navigation alone is not security. Farmers must never modify other farmers' records; customers cannot place bids/orders on behalf of others.

## 3. Fixed-price shopping: always available on eligible listings

**Direct purchasing is the main customer flow and must not require bidding.**

Example: Farmer lists potatoes at **BDT 45/kg**, with **100 kg in stock**. A customer selects **3 kg** and checks out if quantity and fulfillment rules permit. If farmer configured **MOQ = 5 kg**, the cart rejects 3 kg and clearly asks for at least 5 kg; when MOQ is absent, no extra minimum should be imposed.

Implement:
- Product detail page with clear price, unit, stock, optional MOQ, pickup/delivery options.
- Add to cart and Buy Now.
- Stock/quantity checks in both UI and backend.
- Cart changes, checkout, order confirmation, history and statuses.
- BDT (৳) currency; use decimal-safe money arithmetic (Decimal/NUMERIC or integer minor units), never binary floating point.
- Multi-farmer carts with seller-specific order/fulfillment records and clear totals.

## 4. Optional bidding: farmer opt-in AND customer opt-in

Offer two listing configurations:

1. **Fixed price only** — no bidding interface, immediate purchase available.
2. **Fixed price plus optional auction** — customer may *either* buy at fixed price or place a bid on the designated auction lot. The auction must not block ordinary fixed-price orders.

Farmer-configurable auction fields:
- Enabled/disabled flag; lot quantity; starting bid; minimum increment.
- Start and end time; optional reserve price; rules for eligible bids.
- Explicit states: draft, scheduled, live, ended, awarded, cancelled, unfulfilled.

Customer actions:
- View current highest eligible bid and countdown.
- Submit and confirm bid only if opted in.
- View bid history and outbid/winner status; receive notifications.

**Illustration:** 20 kg of tomatoes auctioned as one lot; starting bid BDT 700, increment BDT 50. Customers bid BDT 750, 850, 900. Once the auction closes, award the lot only according to the documented validation and reserve rules. Do not automatically charge customers without an authorized, implemented payment flow.

**Critical consistency requirements:**
- Server time determines auction deadlines.
- Authenticate and authorize all bid requests; no farmer self-bidding on their own listing.
- Reject late, below-minimum, invalid or duplicate bids.
- Maintain immutable bid history and audit trail.
- Use database transactions, locking or equivalent concurrency control for simultaneous bids.
- Implement idempotent APIs where applicable and rate limits for abuse prevention.
- Reserve distinct quantities for fixed-price stock and active auction lots; prevent double-selling.
- Define safe cancellation, winner confirmation, payment/collection timeout, and stock release rules.

## 5. Optional minimum order quantity (MOQ)

Farmers can optionally set **minimum order quantity** per listing. This is separate from total available stock, maximum order quantity, auction reserve price and bid increment.

Examples:
- 100 kg potatoes, MOQ unset: customer may buy any valid supported increment up to stock.
- 100 kg potatoes, MOQ 5 kg: customer must select at least 5 kg.

Support kilograms, grams, pieces, bundles and crates; specify each listing's unit and quantity step. Validate precision and unit conversion consistently in frontend/backend. Always display an active MOQ clearly. Never silently make bidding mandatory or force a default bulk quantity.

## 6. Location-first discovery: prioritize within 20 km, allow nationwide purchasing

**Rule:** Within relevant available product search results, products from farmers within **20 km** of the customer's chosen location appear first by default. Products farther away remain discoverable, searchable, and purchasable if pickup or delivery supports the destination.

For example, customer in Dhaka searches for tomatoes: matching nearby farms first, then matching farms elsewhere in Bangladesh. User can change sorting to price, nearest, newest, etc.

Implement:
- Manual address/area/district selection and optional geolocation with explicit consent.
- Farmer farm locations, customer preferred/delivery location, geo coordinates.
- Geodesic/geographic distance calculation, ideally PostgreSQL/PostGIS geography query and index.
- `nearby <= 20km` flag and approximate distance on cards; do not treat district names as distance.
- Configurable radius defaulted to 20 km if useful, but **do not restrict results by radius**.
- Search relevance and stock/availability filtering before geographic priority.
- Clear fallback when customer has not selected a location.
- Never require precise GPS to shop; protect private exact farm/home coordinates and show approximate area publicly.

**Distance is geographic distance**, not a promise about road travel time or delivery feasibility. Fulfillment eligibility is separately validated at checkout.

## 7. Farmer product listing system

Fields:
- Name, category, description, safe image uploads/gallery.
- Price, currency, unit, quantity step, in-stock quantity.
- Optional MOQ and optional maximum order quantity.
- Harvest/availability information where known.
- Farm reference and approximate public location.
- Delivery/pickup configuration and service areas.
- Fixed-price listing status, auction opt-in and optional auction configuration.
- Draft, published, paused, out-of-stock, archived lifecycle.

Initial categories: vegetables, fruits, rice/grains, pulses, other permitted produce. Validate file size/type/content and use authorized, durable storage. Implement moderation and owner checks.

## 8. Customer marketplace experience

Build real, responsive pages and flows:

**Marketplace discovery:** search, categories, location selector, nearby-first results, filters, relevant market-price context with date/source, active auctions panel.

**Product cards:** photo, name, farmer, price/unit, stock, approximate distance, nearby label, optional MOQ label, direct Buy action, optional auction tag.

**Product detail:** gallery, farmer profile, price, available quantities, direct Buy Now, Add to Cart, auction box *only if enabled*, delivery/pickup options.

**Cart and checkout:** multi-seller support, quantity editing, inventory validation, order totals, correct delivery charges, supported destination check, confirmation screen.

**Customer dashboard:** purchases, bid history, winning bids, favorites, notifications, saved locations.

## 9. Order, payment and fulfillment lifecycle

Suggested order states: pending, confirmed, preparing, ready_for_pickup, shipped/out_for_delivery, delivered, cancelled; refunded only when supported.

Separate `order_status` from `payment_status`. Begin with honest demo checkout, cash-on-delivery/pickup where operationally supported, or a properly integrated legitimate provider. **Never mark mock payments as real or store raw card credentials.** When real payments are integrated, use verified provider callbacks, authorization and idempotency.

Farmers configure pickup, local delivery, delivery areas, charges and whether nationwide shipping is available. Customers may browse nationwide; checkout must reject unsupported fulfillment options clearly. Support independent seller fulfillment for multi-farmer purchases.

## 10. Dashboards

**Farmer:** listed products, available stock, orders, fulfillment queue, sales, active auctions, bid management, notifications and settings.

**Customer:** recommended nearby products, search, cart, orders, active/winning bids, addresses, saved products and notifications.

**Admin:** users, farmer verification, products, reports, order/auction oversight, moderation, fraud signals, platform analytics and audit logs.

## 11. Database schema and migrations

Inspect existing schema before changing it. Extend with migrations rather than destructive reinitialization. Suggested entities (reuse existing equivalents):

```text
users
roles
farmer_profiles
customer_profiles
farms
addresses
products
product_images
inventory
auctions
bids
carts
cart_items
orders
seller_orders
order_items
payments
delivery_options
shipments
notifications
reviews
audit_logs
```

Requirements: foreign keys, relevant unique constraints, indexes, decimal-safe money/quantity, geographical indexes, timestamps with timezones, soft-delete/archive where appropriate, inventory reservations and robust transactions. Preserve bid and payment audit history. Backfill safely if new required fields affect existing records.

## 12. APIs (adapt to existing repository conventions)

```http
GET    /api/v1/market/products
POST   /api/v1/market/products
GET    /api/v1/market/products/{id}
PATCH  /api/v1/market/products/{id}
GET    /api/v1/market/nearby
GET    /api/v1/market/farmers/{id}
POST   /api/v1/market/cart/items
GET    /api/v1/market/cart
PATCH  /api/v1/market/cart/items/{id}
POST   /api/v1/market/orders
GET    /api/v1/market/orders
GET    /api/v1/market/orders/{id}
POST   /api/v1/market/auctions
GET    /api/v1/market/auctions
GET    /api/v1/market/auctions/{id}
POST   /api/v1/market/auctions/{id}/bids
GET    /api/v1/market/farmer/dashboard
GET    /api/v1/market/customer/dashboard
GET    /api/v1/admin/market/dashboard
```

All endpoints require appropriate validation, authorization, consistent errors, pagination, rate limiting where relevant, and OpenAPI/docs updates. Use secure and atomic order creation, bid submission and inventory updates.

## 13. Premium green UI/UX

Retain existing ZYNTRIX AgroSphere AI branding and design system. Suggested palette:

| Usage | Color |
| --- | --- |
| Deep forest green | `#103D2E` |
| Primary green | `#168B5D` |
| Emerald | `#10B981` |
| Soft lime | `#B8E66A` |
| Pale mint | `#ECF7F0` |
| Warm off-white | `#F7FAF6` |
| Dark text | `#172A22` |

Use elegant product cards, accessible contrast, modern typography, beautiful forms and checkout, farmer/admin dashboards, polished hover states, smooth route transitions, reduced-motion support, mobile responsiveness, light/dark themes and Bengali/English support. Use existing frontend technology; do not migrate frameworks solely for appearance. Ensure every visible interactive control actually works.

## 14. Integrate with existing platform

**Do not remove or break:**
- AgroDoctor AI and crop image upload/disease analysis.
- FloodCrop AI and weather/flood-risk features.
- Existing KrishiMarket market-price intelligence, trends and forecasts.
- Authentication, dashboards, established APIs, database records, Docker configuration.

Show historic/current market price context next to seller asking prices only when clearly labeled with source and last-updated time; never imply a model forecast is a guaranteed sale price. Marketplace should be a new, integrated capability of KrishiMarket, not a replacement for its existing AI component.

## 15. Security and privacy

- Enforce RBAC and ownership checks server-side.
- Sanitize/validate inputs; protect file uploads.
- Prevent IDOR, unsafe status transitions, duplicate order submission and auction manipulation.
- Use server-side timestamp checks, rate limits, idempotency, transactions and audit logs.
- Keep secrets in environment configuration; do not hardcode credentials.
- Only expose coarse/approximate farm locations publicly.
- Avoid exposing protected customer addresses/contacts across roles.
- Handle payment statuses honestly; no fabricated success.

## 16. Required automated tests

**Roles:** Admin/Farmer/Customer permissions and cross-account access denial.

**Direct shopping:** checkout succeeds without bidding; auction-disabled listings remain buyable; MOQ only enforced when configured; correct quantities and totals; no overselling under concurrent purchases; fulfillment checks.

**Bidding:** auction-disabled bid rejection; minimum increment enforcement; deadline enforcement; no self-bidding; duplicate/replayed requests safe; concurrency and lot reservations; winner and cancellation rules.

**Geography:** inside-20-km prioritization; outside-20-km products remain visible and purchasable when fulfillable; manual location works without GPS; sorting override; accurate distance formula; privacy-safe outputs.

**Regression:** AgroDoctor image upload and inference, FloodCrop features, current KrishiMarket price intelligence, existing auth and navigation still function.

**End-to-end:** farmer creates fixed-price product → customer selects location → sees nearby items first → adds product to cart → checks out without bidding → farmer fulfills. A separate optional auction journey must also work.

Run tests/build/lint/migrations and report actual results. Fix failures where feasible; don't fabricate passed tests.

## 17. Implementation milestones

1. **Inspect repository and prepare migration-safe implementation checklist.** Identify actual stack, existing code, database, auth, market module, tests and Docker configuration.
2. **Roles and farmer/customer profiles.** Extend existing auth and server-side RBAC without breaking current users.
3. **Farmer listings and stock.** Images, pricing, units, optional MOQ, location, delivery configuration.
4. **Customer browse/search and proximity ranking.** 20 km priority, nationwide discovery, manual location fallback.
5. **Cart, checkout and orders.** Direct fixed-price purchases first, multi-seller handling, transactional inventory.
6. **Optional auctions.** Bid logic, notifications, lot reservation, concurrency tests.
7. **Role dashboards and admin tools.** Integrate and polish green UX.
8. **Regression and container verification.** Test AgroDoctor, FloodCrop and market intelligence; update Docker/docs; repair issues.

At each milestone, complete functional code, run available checks and update documentation before continuing. Don't stop after writing a plan or UI mockup.

## 18. Docker and local development

Inspect existing Docker Compose setup and reuse it where possible. Adjust services, database migrations, media storage and environment variables safely. Do not delete Docker volumes or reset existing data. Document exact startup and test commands for Windows/Docker Desktop and for non-Docker development where appropriate.

## 19. Definition of done

- Three secure roles: Admin, Farmer, Customer.
- Working farmer listings, prices, inventory, photos, and optional MOQ.
- Direct customer purchase works **without any bidding**.
- Bidding is **optional for farmer and customer** and has secure lifecycle handling.
- Relevant available products within 20 km rank ahead of other matching results by default.
- Products farther away are still searchable and orderable where fulfillment is available.
- GPS permission is optional; manual location is supported.
- Cart, checkout, orders, inventory and notifications function.
- Farmer, customer and admin dashboards are connected to real backend endpoints.
- Existing AgroDoctor, FloodCrop and KrishiMarket intelligence continue functioning.
- UI retains premium green branding with responsive layout and animations.
- Migrations, Docker configuration and automated tests run successfully, or exact blockers are documented.
- README and developer docs explain configuration, deployment, test commands and limitations.

## 20. Instruction to Codex

**Inspect the existing ZYNTRIX AgroSphere AI repository first, then implement this KrishiMarket marketplace upgrade end-to-end. Do not create a new application.** Protect existing functionality, data and architecture. Prioritize the fixed-price customer journey, then add optional auctions. Respect the **20 km nearby-first ranking rather than a geographic restriction**. Keep minimum order quantities optional. Run tests, repair discovered failures, maintain a progress checklist, and report only verified completion. Start implementing now.
