# ZYNTRIX AgroSphere AI — Hybrid Platform: Codex Implementation Master Plan

**Version:** 1.0  
**Prepared:** 15 November 2026  
**Project type:** Software-first, hardware-ready agricultural decision-support platform  
**Primary market:** Bangladesh; bilingual Bangla/English  
**Core modules:** **AgroDoctor AI (primary)** + **FloodCrop AI** + **KrishiMarket AI**  
**Brand:** ZYNTRIX — *Intelligence Beyond Boundaries*

> **Instructions for Codex:** Treat this file as the project's source-of-truth specification. **Build working software**, not just mockups. Work milestone by milestone, run tests, and leave each milestone usable. The three modules must be part of **one product**, with shared farms, plots, users, weather, event history, notifications, and provenance. All modules must run in a hardware-free demo environment. Define hardware/device adapters now, but physical hardware is a **later phase**. Do not pretend that simulated data, image classification, rainfall, or prices are experimentally verified when they are not.

---

## 0. Executive decision: what we are building

**One-sentence pitch:** *ZYNTRIX AgroSphere AI helps farmers inspect suspicious crop symptoms, prepare for rainfall-related farm threats, and compare selling options—on one understandable, evidence-aware platform.*

A tomato farmer in Gazipur can (1) upload a leaf photo, (2) receive **possible** disease classifications and evidence-aware scouting guidance, (3) review rainfall and flood-related risk context for their farm, and (4) compare recorded tomato prices across markets, including potential transport costs. The product produces a combined **Farm Action Center**; it does not diagnose with certainty, issue official flood warnings, guarantee price forecasts, or prescribe pesticides.

### Relative priorities

| Area | Priority | Approx. effort share | Required at competition MVP? |
|---|---|---:|---|
| **AgroDoctor AI** | **P0 / flagship** | **55%** | **Yes: image upload, meaningful inference, uncertainty, history, recommendations** |
| **FloodCrop AI** | P1 / supporting | 25% | **Yes: map + rainfall alerts + official flood information references; carefully qualified** |
| **KrishiMarket AI** | P1 / supporting | 20% | **Yes: sourced prices/import, comparisons, cost calculator; prediction is optional** |
| Optional IoT sensors | Later | — | **No; only ingest contracts and simulation needed** |
| Pump automation / pesticide dosing / guaranteed diagnoses | Out of scope | — | **Never in MVP** |

**Scope guardrail:** Do **not** spend the first sprint implementing three sophisticated ML models. Make the **AgroDoctor** classifier real and evaluated first. FloodCrop can begin as a transparent weather-and-official-alert decision aid, while KrishiMarket begins as a trustworthy price comparison engine. Add predictive ML only after appropriate training data and baselines exist.

### MVP definitions

- **AgroDoctor:** Tomato-only initial crop; a small, declared label set based on available valid training data (e.g. healthy, early blight, late blight, leaf mold, bacterial spot, *unknown/uncertain*). Choose actual classes from verified dataset labels; do not fabricate coverage. Use a pre-trained image backbone and **properly train/evaluate a classifier**, with a truthful demo-only fallback if model artifacts cannot be obtained.
- **FloodCrop:** Farm coordinates, daily/hourly rainfall outlook, recent rainfall, contextual risk factors, links to official FFWC flood information, and a clearly named **rainfall/waterlogging preparedness indicator**. Distinguish *heavy-rain potential* from *verified river-flood risk* and *farm inundation predictions*.
- **KrishiMarket:** Market records with dates, source, location, commodity, price type (farm-gate/wholesale/retail), units, visible freshness; compare selling choices and estimated net proceeds. No unexplained “AI predicts high prices tomorrow” if trustworthy time series are missing.
- **Unified intelligence:** One farmer profile, farm/plot, crop cycle, action inbox, saved diagnosis cases, flood/rain alerts, price watch, audit history, source labels.

---

## 1. Users, jobs, and product experience

**Primary user:** Smallholder/medium-sized Bangladeshi crop grower using a mobile phone.  
**Secondary:** Agricultural extension worker / agronomist who reviews uncertain cases.  
**Evaluator:** Competition judge who needs to understand source quality, actual models, tests, and demo limitations.

### Main user flow (end-to-end)

1. Open **ZYNTRIX AgroSphere AI**, select Bangla or English.
2. Create a **demo farm** (e.g. Gazipur), add a tomato plot and crop stage. Store coarse farm location only if the user agrees; precise coordinates optional.
3. Upload a photo of a tomato leaf in **AgroDoctor**.
4. Server verifies file type/size, stores securely, checks image quality and known/unknown crop suitability, then runs the selected classification model.
5. Show **top possible conditions**, calibrated probability if available, “insufficient confidence” when appropriate, visual evidence limitations, and next steps (take another photo, check both sides of the leaf, consult an agronomist). Do not mistake confidence for confirmed disease prevalence or diagnosis.
6. **FloodCrop** displays the plot's rainfall outlook and an explanatory *precipitation preparedness* assessment; official FFWC river data is displayed only if sourced appropriately with timestamp, coverage, and attribution.
7. **KrishiMarket** shows tomato price data, selected wholesale/retail markets, last-updated date, price unit, and illustrative **net-return calculator** (price × saleable kilograms − declared transport/handling costs). Explicitly distinguish *reported* prices from *farmer-entered* and *sample* values.
8. **Farm Action Center** combines the three outputs into a prioritized, reasoned summary; no unsafe automated actions.
9. Farmer can save observations, set reminders/notifications within the app, edit or delete data, and export a report.

### Fully labeled demo scenario

**All numbers in this scenario are placeholders, not real 2026 observations.**

- Demo farm: `Gazipur Demo Farm`; crop `tomato`; data source `DEMO`.
- Image: bundled or properly licensed tomato sample image; model returns *possible early blight* / or uncertain. Result must correspond to model output (not a hardcoded classification presented as inference).
- Forecast: demo fixture illustrates a high-rainfall event; label it `scenario_simulated` if not sourced from an actual issued forecast.
- Markets: sample records for two demo markets: e.g. `42 BDT/kg` vs `46 BDT/kg` (synthetic only), 400 kg harvested, shipping estimates entered by user; show the calculation and caveats.
- Combined guidance: *Inspect affected leaves, review rain preparation, compare net selling returns*. No claim that flooding or disease will definitely occur.

---

## 2. Technology stack and project shape

Keep dependencies current and stable **at coding time**; pin them with lockfiles and document versions.

| Layer | Required choice | Why |
|---|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** | Modern responsive app and routing |
| UI | **Tailwind CSS, shadcn/ui, Motion for React, Lucide** | Green premium design and elegant transitions |
| Charts | Recharts | Price charts, forecast panels, model metrics |
| Maps | MapLibre GL or React Leaflet with properly licensed tile provider | Farm area and context maps; no invented flood raster |
| Forms/data | TanStack Query + React Hook Form + Zod | Fetching, caching, validation |
| Localization | next-intl (or similar) with `bn` / `en` | Bengali + English |
| Backend | **Python + FastAPI + Pydantic v2** | Business logic and ML inference |
| Data | **PostgreSQL + SQLAlchemy + Alembic** | Persistent farm/market/case records |
| Images | Local private storage adapter in dev; S3-compatible adapter later | Photos and signed/controlled access |
| ML | PyTorch + torchvision / timm + scikit-learn | Disease classifier; evaluation; baselines |
| Async jobs | Start with bounded background tasks or separate worker; introduce Redis/RQ/Celery only when necessary | Avoid blocking uploads/API workers |
| Weather | Open-Meteo client behind `WeatherProvider` interface | Forecast source can change |
| Market | `MarketPriceProvider` interface + licensed CSV importer | DAM is an official report source, **not an assumed free API** |
| Flood | `FloodSignalProvider` interface | Official FFWC/GloFAS adapters if accessible and licensed |
| Tests | pytest, Vitest/React Testing Library, Playwright | Automated correctness |
| Local ops | Docker Compose, Makefile or scripts, GitHub Actions | Easy start / CI |

### Monorepo

```text
agrosphere-ai/
├── README.md
├── AGENTS.md                         # Codex implementation rules
├── PLAN.md                           # copy of this specification
├── .env.example
├── .gitignore
├── compose.yaml
├── Makefile
├── .github/workflows/ci.yml
├── apps/
│   ├── web/                           # Next.js app
│   │   ├── src/app/[locale]/
│   │   │   ├── (public)/page.tsx
│   │   │   └── (app)/{dashboard,agrodoctor,floodcrop,market,farms,action-center,history,settings}/
│   │   ├── src/components/{ui,charts,maps,layout}/
│   │   ├── src/features/{doctor,flood,market,farms,alerts}/
│   │   ├── src/lib/{api,i18n,auth,formatters}/
│   │   ├── messages/{en,bn}.json
│   │   └── tests/
│   └── api/                           # FastAPI app
│       ├── app/main.py
│       ├── app/api/v1/
│       ├── app/core/{config,security,logging}.py
│       ├── app/db/{models,session,repositories}/
│       ├── app/domain/{farms,doctor,flood,market,actions,devices}/
│       ├── app/providers/{weather,flood,market,image_storage}/
│       ├── app/adapters/{fixtures,historical,esp32}/
│       ├── app/workers/
│       ├── migrations/
│       └── tests/
├── ml/
│   ├── doctor/{data,train,evaluate,infer,configs}/
│   ├── market/{baselines,backtesting}/
│   ├── flood/{baselines,evaluation}/
│   ├── model_cards/
│   └── artifacts/                    # never commit large weights by default
├── contracts/{openapi,examples}/
├── data/{fixtures,imports,licenses}/
├── hardware/esp32-example/           # later: optional reference firmware
├── docs/{architecture,data_sources,model_card,privacy,hardware_integration,demo,testing}/
└── scripts/{seed_demo,import_market,healthcheck}/
```

**Engineering rules:** Use boundaries, not three separate mini-apps. All modules use shared farm/plot IDs, data provenance vocabulary, error patterns, and timestamps. Build adapters so a data source can be swapped without editing page components.

---

## 3. Architectural contract and operating modes

```text
                                     +------------------------+
   Farmer phone/browser ------------>| Next.js Web Application|
                                     | Bangla / English       |
                                     +-----------+------------+
                                                 |
                                     +-----------v------------+
                                     | FastAPI v1 / Auth/RBAC |
                                     +-----------+------------+
                                                 |
                +--------------------------------+--------------------------------+
                |                                |                                |
        +-------v--------+              +--------v-------+             +----------v-------+
        | AgroDoctor     |              | FloodCrop      |             | KrishiMarket     |
        | upload / CV    |              | weather/safety |             | prices / net ROI|
        +-------+--------+              +--------+-------+             +----------+-------+
                |                                |                                |
          ModelRegistry                  FloodSignalProvider                MarketPriceProvider
                |                                |                                |
      image dataset / weights         weather + approved official         approved imports / user data
                |                    flood data / scenarios                      |
                +--------------------------------+--------------------------------+
                                                 |
                                    +------------v-------------+
                                    | Shared Services          |
                                    | farms, actions, alerts   |
                                    | provenance, auditing     |
                                    +------------+-------------+
                                                 |
                                          PostgreSQL +
                                          image storage
                                                 |
                                      DeviceIngestion contract
                                      / future ESP32 adapter
```

### Data modes

- `DEMO`: deterministic, clearly watermarked synthetic fixtures; safe to showcase UI flows offline.
- `LIVE`: real available external data with source/issue time and availability checks; diagnosis model also reports real model version and validation state.
- `HISTORICAL`: sourced historical records, original dates retained; no pretend “current” badge.
- `MIXED`: each card labels its own data source; aggregate action cards disclose mixed sources.

Example `.env`:

```env
APP_ENV=development
DATA_MODE=DEMO
DATABASE_URL=postgresql+psycopg://agrosphere:local_dev_password@localhost:5432/agrosphere
OPEN_METEO_BASE_URL=https://api.open-meteo.com
MODEL_DIR=./ml/artifacts
IMAGE_STORAGE_DRIVER=local
UPLOAD_MAX_MB=8
DEFAULT_LOCALE=bn
ENABLE_MARKET_PREDICTION=false
ENABLE_OFFICIAL_FLOOD_DATA=false
ENABLE_DEVICE_INGESTION=true
```

**Do not bake `DEMO` into API endpoints.** Build a `DataSourceContext` shared by request, farm, prediction and UI. The backend should provide `source_type`, `source_name`, `observed_at`, `issued_at`, `retrieved_at`, `is_simulated`, `quality_flags`, and `license/attribution` where applicable. The frontend must visually disclose this metadata.

---

## 4. Shared platform: foundation and common domain

### Must-have entities

1. `users` — user ID, role, language, preferences; password hash or approved auth provider; minimal personal data.
2. `farms` — owner ID, name, district/upazila, optional lat/lon, optional consent flags.
3. `plots` — farm ID, crop ID, acreage/area, crop stage, sowing/planting date, soil context.
4. `crops` / `crop_cycles` — vocabulary and active crop cycle.
5. `data_sources` — provider, terms/link, source kind, last sync, health.
6. `image_assets` — owner, storage URI, MIME, checksum, consent/retention, provenance.
7. `diagnosis_cases` — image ID, plot ID, crop, reported symptoms, model version, status, created time.
8. `diagnosis_predictions` — class ID, scores, confidence/calibration information, unknown/reject status, evidence summary.
9. `weather_forecasts` — farm/plot, variables, time window, forecast issuance/retrieval time.
10. `flood_signals` — `signal_type` (`rainfall_preparedness`, `official_river_warning`, etc.), location, source, threshold/profile, limitations.
11. `market_locations` — market identity, district, optional geolocation, category.
12. `market_prices` — crop/product, quality/grade where known, min/max or point price, `BDT/kg` or explicit unit, market, price type, recorded date, source, provenance, observed/retrieved times.
13. `market_price_imports` — file/source metadata, approved permission/license, import errors, reconciliation status.
14. `market_comparisons` — optional saved assumptions for quantity, market, freight and handling.
15. `action_items` — plot, topic, severity, explanation, next action, origin record, status, created/expiry times.
16. `notifications` — in-app alert, channel, preference, delivered/read status.
17. `device_registry` / `sensor_readings` — optional hardware-ready contracts, not required for MVP results.
18. `model_versions` / `model_evaluations` — metrics, dataset hash, commit SHA, per-class results and constraints.
19. `audit_events` — edits, exports, diagnostic decisions, imports and administrative changes.

### Shared rules

- Store canonical timestamps in UTC and display Bangladesh time (`Asia/Dhaka`) with explicit time-zone formatting.
- Store money in decimal units (BDT); never use binary floating point for currency accounting.
- Preserve *price type*, *commodity grade*, *unit*, *market location*, and *observation date*. Retail versus wholesale are not directly interchangeable.
- Normalize crop names with stable identifiers (`tomato`), and provide Bangla/English display labels.
- Keep predictions immutable; subsequent model runs create new records.
- Provide data delete/export paths and reasonable image retention/consent defaults.
- Provenance/quality should affect product behavior (stale data disables certain claims).

---

## 5. Module A — AgroDoctor AI (FLAGSHIP)

### Goal

Image-assisted crop-health screening for farmers, **not a definitive lab diagnosis**. Treat unknown/unseen conditions honestly.

### Core user interface

- Camera / gallery image upload (mobile-first); drag and drop on desktop.
- Image preview, crop selector (MVP: tomato), optional visible symptoms and growth-stage inputs.
- Photo-taking guidance: natural light, close focus, both sides of affected leaf, multiple leaf examples.
- Processing status, retry and cancellation.
- **Possible conditions** ranked with an uncertainty disclosure. If input appears out of scope, blurred, or below confidence threshold: **“Unable to classify reliably”**.
- Disease info card: observable symptoms, other possible causes, scouting/monitoring steps, when to seek local agronomist.
- **Evidence:** model name/version, supported classes, dataset/source, evaluation summary, confidence limitations. Optional Grad-CAM as *model-attention illustration*; never call it definitive localization proof.
- Download/share case report (PDF optional, HTML/CSV required for MVP), save case history, add follow-up images and confirmation feedback.
- Bangla and English disease descriptions; translation reviewed for understandable agricultural vocabulary.

### Model strategy

**M0 — UI/demo stub**: Non-medical illustrative case **explicitly labeled sample**. Use only while loading data/model; never present stub scores as genuine inference.

**M1 — Working classifier**: Fine-tune a compact, pre-trained image model (e.g., MobileNetV3/EfficientNet family) on a **small selected set of actual tomato classes** from a properly licensed dataset. Generate a reproducible notebook/script and export inference artifact. Confirm class names programmatically from the dataset, don't assume exact class list.

**M2 — Field robustness**: Add approved field photographs with documentation and consent; validate on an external field set and varied lighting/backgrounds. Only then consider broader field-readiness statements.

**M3 — Advanced optional**: Multi-photo cases, image quality classifier, OOD detector, expert-reviewed knowledge base, optional weather context; never assert that weather confirms a visually suspected disease.

### Datasets and safeguards

- Candidate: PlantVillage (controlled leaf images), with published leaf-group-aware splits; inspect license, image provenance, class list and use conditions.
- Research other field-image datasets (such as PlantDoc) **only after verifying access, class labels, license, and suitability**. Do not silently train on ambiguous web-scraped photos.
- Separate original source groups and near-duplicate images before splitting. Reserve a true holdout set. Report in-domain and, if available, out-of-domain results separately.
- Data leakage prevention: same leaf/plant or near-identical image must not cross train/test.
- Evaluation: macro-F1, per-class precision/recall, confusion matrix, accuracy, top-k if appropriate, uncertainty calibration (e.g. ECE), reject/abstain rate, performance by source/background, latency/size.
- Don't invent 95% or 99% accuracy. A model with only laboratory-style images must display **“Not field-validated”**.
- Score thresholds should be set on validation data; softmax alone is not calibrated uncertainty.
- No prescription pesticide concentrations, chemical mixing or guarantees. Provide safe, non-specific inspection steps and escalation to qualified local advisers.

### Suggested API

```http
POST   /api/v1/doctor/cases            # multipart image + crop/plot + optional symptoms
GET    /api/v1/doctor/cases            # paginated list for authenticated user
GET    /api/v1/doctor/cases/{case_id}  # classification, source, reasons, status
POST   /api/v1/doctor/cases/{case_id}/feedback
GET    /api/v1/doctor/conditions       # curated content with sources
GET    /api/v1/doctor/models/current  # metrics, version, limitations
```

**Case response contract example** (illustrative structure, not a claim of model output):

```json
{
  "case_id": "case_demo_001",
  "plot_id": "plot_tomato_001",
  "crop": "tomato",
  "status": "completed",
  "mode": "DEMO",
  "classification": {
    "top_label": "tomato_early_blight",
    "display_as": "possible_condition",
    "score": 0.71,
    "score_type": "uncalibrated_model_score",
    "abstained": false,
    "alternatives": [{"label": "tomato_late_blight", "score": 0.18}]
  },
  "model": {
    "version": "demo-fixture-v1",
    "field_validated": false,
    "source": "synthetic_demo_fixture"
  },
  "advice": ["Check multiple leaves and both sides", "Seek an agronomist if damage progresses"],
  "disclaimer": "AI screening only; not a confirmed diagnosis"
}
```

**AgroDoctor definition of done:** User photo -> backend upload -> actual model inference (or explicitly labeled demo fixture) -> credible uncertainty -> report/history -> expert-safe advice; repeatable evaluation documented. The demo must make it clear when it uses a real model versus a sample case.

---

## 6. Module B — FloodCrop AI (weather-aware resilience)

### Important scientific boundary

**Rainfall forecast ≠ confirmed flood forecast ≠ farm inundation map.** A high rain total can motivate preparedness, but a farm's flood probability or depth requires validated hydrological information, local exposure, terrain/drainage, gauge data and appropriate evaluation. FloodCrop MVP should be described as **rainfall/waterlogging preparedness and official flood-information aggregation**; do not label its heuristic as calibrated flood probability.

### MVP features

- Farm-location page with district/upazila selector and optional map pin/coordinates.
- 24h, 48h and 72h rain outlook, forecast issue time, chart, warnings for unusually heavy **forecast rainfall** (thresholds configurable and labeled heuristic).
- Recent rainfall and persistence view (when reliable data available).
- “Preparedness score” with **rule-based explanation and sensitivity**; label whether based on forecast, history, or DEMO.
- Link or integrate **official flood bulletins/status from BWDB FFWC** with original issue date and source attribution, if an accessible authorized feed/import is available; do not silently scrape inaccessible dynamic data.
- Manual farm vulnerability factors (low-lying plot, prior waterlogging, soil/drainage, crop growth stage), clearly marked **farmer-reported**.
- Crop action suggestions: inspect drainage, secure seedlings, check official alerts, prepare harvesting/storage plan if appropriate; do not issue evacuation instructions as the app's own prediction.
- Map with farm pin and relevant forecast/official reference overlays only when their geographic precision supports it.
- In-app alert, details, sources and uncertainty.

### Optional validated upgrades

- GloFAS: available global river-flow forecast products, but **not a local flash-flood, coastal flood or inundation-depth forecast**. Confirm access, geographic coverage, licensing, timestamp and mapping limits before integrating. Never claim parcel-level flood depth from GloFAS river forecasts.
- FFWC/BWDB official river level or warning data, if permitted and available in machine-readable form.
- Historical flood-event dataset and elevation/landcover data for an evaluated **local exposure** model, with independent events for test periods.
- Hydrology review with domain expert before strong flood-risk claims.

### Baseline decision rules

1. Fetch and cache issued forecast for farm coordinates.
2. Verify valid time and source health; when stale, show `data_unavailable`.
3. Compute anticipated rainfall totals for chosen time windows, respecting time zones.
4. Compare to **configurable demonstration threshold(s)** and optionally user-provided drainage vulnerability; do not call resulting classification a proven probability.
5. Pull approved official warnings if available; display separately, never silently mix into fabricated levels.
6. Generate an action card with `signal_type`, explanation, horizon, provenance and limitations.

### FloodCrop API

```http
GET    /api/v1/flood/plots/{plot_id}/outlook?horizon_hours=48
GET    /api/v1/flood/plots/{plot_id}/official-alerts
GET    /api/v1/flood/sources
POST   /api/v1/flood/plots/{plot_id}/vulnerability
GET    /api/v1/weather/plots/{plot_id}/forecast
```

**Response sketch:**

```json
{
  "plot_id": "plot_tomato_001",
  "horizon_hours": 48,
  "signal_type": "rainfall_preparedness",
  "level": "watch",
  "is_flood_probability": false,
  "method": "configurable_precipitation_rule",
  "reasons": ["Illustrative 48-hour rainfall total exceeds demo threshold"],
  "official_alert": null,
  "source": {"name": "DEMO WEATHER", "issued_at": "2026-11-15T06:00:00+06:00", "is_simulated": true},
  "disclaimer": "Not an official or parcel-level flood forecast"
}
```

**FloodCrop definition of done:** View forecast and location, explain a **rain-preparedness** signal, preserve issued time/source, show official source separately when available, and never fabricate flood alerts or live inundation polygons.

---

## 7. Module C — KrishiMarket AI (prices and better selling decisions)

### Goal

Help farmers **compare actual reported prices and estimated net selling returns**, not promise a profitable time to sell based on unsupported data.

### MVP features

- Commodity selector (MVP `tomato`, expandable to potato/rice/eggplant/etc.).
- Market selector (district/market); show source and local time.
- Choose **farmer/grower, wholesale, retail** as available—never combine them without an explicit explanation.
- Date/source freshness, units, range vs point-estimate distinction, unavailable/stale badges.
- Table + historical chart if enough authentic records exist.
- User-supplied quantity, harvest grade, expected loss, transport, handling/storage costs.
- **Compare net expected proceeds**, but distinguish assumptions from observed market transactions.
- Saved watchlist and optional in-app price threshold notification.
- CSV upload/import tool with field mapping, preview, validation, permission checks, deduplication, error report.
- Recorded market location on map only if verified coordinates are available; no invented distances/transport costs.

### Price calculations

For a *single* comparable observation, with values entered/verified:

```text
saleable_kg = harvested_kg * (1 - assumed_loss_fraction)
gross_BDT = saleable_kg * chosen_observed_price_BDT_per_kg
net_BDT = gross_BDT - stated_transport_BDT - stated_handling_BDT - stated_fees_BDT
```

If market reports a **price range**, show a net range or ask the farmer to select a conservative/central/optimistic point, clearly labeled. Don't silently use the upper bound. Optional costs must default to **unknown**, not zero unless explicitly chosen.

### Official Bangladesh source plan

The Bangladesh **Department of Agricultural Marketing (DAM)** publishes daily and commodity-wise online price reports, including markets and price type. **Do not assume DAM offers a documented, public JSON API** or that automated scraping is authorized. Implement a `DamCsvImportAdapter` / manually downloaded report workflow first, with source attribution. Use direct automated integration **only after validating permission/terms, a stable export/feed, field coverage and refresh cadence**. Provide a demo fixture if no approved price file is available.

### Optional market ML (P2, only after data readiness)

- A chosen commodity, price category, market and unit with consistently dated history.
- Time-aware rolling-window backtests versus naive last-observation and seasonal/rolling-median baselines.
- Metrics: MAE, sMAPE or WAPE (handle zero prices carefully), error bands, interval coverage if forecasting intervals.
- Never fabricate 7-day price predictions; hide/disclaim forecasting if data sparse, discontinuous, unlicensed, or not representative.
- Do not imply a quoted wholesale price is the amount the farm will actually receive.

### KrishiMarket API

```http
GET    /api/v1/market/commodities
GET    /api/v1/market/locations
GET    /api/v1/market/prices?commodity=tomato&market_id=...&price_type=wholesale
POST   /api/v1/market/imports           # admin/private permitted CSV
GET    /api/v1/market/imports/{id}
POST   /api/v1/market/compare
GET    /api/v1/market/watchlists
POST   /api/v1/market/watchlists
GET    /api/v1/market/forecast          # optional, feature-gated
```

**KrishiMarket definition of done:** Credible price ingestion or visible DEMO fixture; filter, compare, calculate, save, export; source/price type/dates visible; predictions disabled until supported.

---

## 8. Unified Farm Action Center (the hybrid differentiator)

This is the distinctive experience tying the three modules together. It is **not** a fourth opaque AI model.

### Rules

- Gather latest accepted Doctor case, FloodCrop signals, and available KrishiMarket observations for the same plot/crop.
- Display **three independent evidence cards** with their **own date, data mode, reliability and links**.
- A conservative policy engine produces a prioritized checklist with reasons, uncertainties, and user acknowledgement.
- No complex cross-domain numerical “total risk 92%” unless independently justified and validated.
- Low-quality/no-source results must display **Information incomplete** and must not drive strong action advice.
- One-click drill-down into module; mark actions done, snooze, comment, save to history.

**Example action center (DEMO):**

| Priority | Trigger | Suggested action | Source label |
|---|---|---|---|
| 1 | New suspicious tomato leaf image | Inspect more leaves; request expert review if spreading | Model demo/validated version |
| 2 | 48-hour high-rain demo scenario | Inspect drainage and consult official FFWC updates | Scenario / issued forecast |
| 3 | Market A vs B price samples | Compare net expected BDT after transport and losses | Demo / sourced price report |

### Integration event design

Domain events (`diagnosis.created`, `doctor.review_requested`, `rainwatch.updated`, `market_price.imported`, `action.acknowledged`) update the action feed through an application service. Keep module-specific outputs separable and auditable. Events must be idempotent and versioned; basic synchronous orchestration is fine initially—no Kafka needed.

---

## 9. UI / UX brand specification (non-negotiable)

**Desired look:** A premium, memorable, modern **green agricultural AI operating system**—more polished than a standard student dashboard. Fast, accessible, and mobile-first; beautiful, but never deceptive.

### Theme tokens

| Purpose | Light | Dark |
|---|---|---|
| Forest navigation | `#103D2E` | `#091F18` |
| Primary emerald | `#168B5D` | `#1EB47D` |
| Bright accent | `#B8E66A` | `#A3D65C` |
| Mint surface | `#EDF8F0` | `#163B2D` |
| Main canvas | `#F7FAF6` | `#0C1813` |
| Text | `#172A22` | `#E6F4EB` |
| Muted text | `#64776B` | `#A2BBAA` |
| Risk amber | `#D39124` | theme-adjusted accessible |
| High risk | `#C74845` | theme-adjusted accessible |

Use **Plus Jakarta Sans/Inter** for Latin; an attractive legible Bengali font (e.g. Hind Siliguri or Noto Sans Bengali). Maintain WCAG AA contrast for critical text. Prefer gradients only in hero/background accents, not every card.

### Animations

- Framer Motion / Motion for React route transitions: refined fade + slight movement; 180–300 ms typical, not cinematic delays.
- Staggered metric card reveals, hover lifts, animated progress/empty/loading states, calm chart transitions.
- Respect `prefers-reduced-motion`; no scroll-jacking, excessive parallax, seizure triggers, or blocked navigation.
- Distinctive but restrained visuals: leaf-line motifs, soft topo contours, subtle green glow, elegant rounded chart tooltips.

### Required pages

1. **Landing** — striking hero; three connected pillars; product story; sample demo CTA; hardware-later roadmap; credible disclaimers.
2. **Onboarding** — language, create farm, location, plot crop, choose `DEMO` or `LIVE` (live requires verified sources).
3. **Overview Dashboard** — farm health workflow, latest diagnosis, rain/weather panel, market panel, action list, source/data freshness chips.
4. **AgroDoctor Studio** — hero upload area, camera UX, results, optional attention illustration, crop condition pages, case history.
5. **Doctor Case Detail** — result, differential, version, limitations, notes, expert escalation/feedback.
6. **FloodCrop Center** — map, rainfall outlook, source labels, preparedness rule explanations, official-warning links.
7. **KrishiMarket Center** — commodity and market filters, prices, trend charts, cost calculator, watchlist/import admin.
8. **Farm Action Center** — cross-module checklist, evidence links, unread/complete, prioritization rationale.
9. **Farms & Plots** — profile, cropping, location, crop stage.
10. **Notifications & History** — actionable timeline and filters.
11. **Data & Model Transparency** — dataset provenance, model cards, evaluation dashboard, source health.
12. **Devices (Future IoT)** — disabled/available hardware mode with virtual devices, device registration and calibration UI; **do not pretend sensors are connected**.
13. **Settings** — Bangla/English, theme, consent/privacy, notification preferences, units.

### Design quality gates

- Every button works, or is disabled with an explanation.
- No hardcoded unsourced “live” KPI numbers in React.
- User always sees `DEMO`, `HISTORICAL`, `LIVE`, or mixed-source badges appropriately.
- Desktop, tablet, mobile (including 360 px wide); keyboard navigation and focus rings.
- Beautiful skeletons, empty/loading/error states; image upload progress; responsive data tables.
- Use illustrations/icons responsibly: no fake visualizations labeled as actual farm imagery.

---

## 10. API conventions and contracts

- Prefix: `/api/v1`.
- Authentication: safe local demo auth or an established auth solution; roles `farmer`, `advisor`, `admin` where needed.
- Farm/plot access by ownership/permission checks, not client-supplied IDs alone.
- Validate all input with Pydantic. `POST /doctor/cases` enforces image MIME via sniffing, extension allowlist, max size/pixels, decompression safety, storage isolation, rate limits, and malware/security precautions appropriate to the environment.
- Long model inference: task ID + poll state if needed; request timeout should never hang.
- Pagination/filtering on cases, alerts and prices.
- Error format: `code`, `message`, `details?`, `request_id`.
- Standard data-envelope metadata:

```json
{
  "data": {"...": "..."},
  "meta": {
    "mode": "DEMO",
    "source_name": "scenario_fixture",
    "is_simulated": true,
    "observed_at": null,
    "issued_at": null,
    "retrieved_at": "2026-11-15T12:00:00Z",
    "freshness": "not_applicable",
    "limitations": ["Illustrative only"]
  }
}
```

- Use OpenAPI generation from FastAPI; optionally generate frontend TypeScript types from OpenAPI to prevent divergence. Create `contracts/examples/` payloads and API integration tests.
- Coordinates use WGS84, BDT with correct units, rainfall in millimeters, area in selected unit with canonical conversion; ISO 8601 timestamps with offsets.

### Minimum shared APIs

```http
GET    /api/v1/health
GET    /api/v1/me
GET    /api/v1/farms
POST   /api/v1/farms
GET    /api/v1/farms/{farm_id}
GET    /api/v1/plots
POST   /api/v1/plots
GET    /api/v1/plots/{plot_id}
GET    /api/v1/plots/{plot_id}/action-center
GET    /api/v1/actions
PATCH  /api/v1/actions/{id}
GET    /api/v1/notifications
GET    /api/v1/providers/status
GET    /api/v1/models/evaluations
POST   /api/v1/device/readings          # authenticated future ingestion
```

---

## 11. Future hardware support (build interfaces now; devices later)

The first complete version must require **no ESP32, no Arduino, no physical sensors**. Nevertheless, it must be possible to add local temperature, rainfall, humidity and soil-moisture inputs later.

### Pattern: sensor adapters

Define:

```python
class SensorIngestionAdapter(Protocol):
    def normalize(self, payload: dict) -> "CanonicalSensorReading": ...

class SimulatorAdapter: ...
class HistoricalSensorAdapter: ...
class Esp32HttpAdapter: ...
```

Maintain a unified canonical reading with `schema_version`, `device_id`, `plot_id`, `event_id`, `timestamp`, `source_type`, `raw` fields, optional `calibrated` fields, units, `calibration_id`, and `quality_flags`. Device authentication required for `esp32`; transport supports HTTPS first (MQTT later if necessary). Preserve raw ADC values. Do **not** label arbitrary raw values as `moisture_percent` or true volumetric water content without soil-specific calibration. Hardware presence may enrich FloodCrop environmental observations and AgroDoctor context but **does not replace image diagnosis or validate all models automatically**.

### Example future payload

```json
{
  "schema_version": "1.0",
  "event_id": "dev001-00000004",
  "device_id": "esp32-001",
  "plot_id": "plot-tomato-001",
  "timestamp": "2026-11-15T11:30:00+06:00",
  "source_type": "esp32",
  "measurements": {
    "soil_moisture_adc": 2150,
    "soil_moisture_vwc_m3m3": null,
    "air_temperature_c": 29.1,
    "relative_humidity_pct": 76.2,
    "rainfall_mm_interval": null
  },
  "calibration_id": null
}
```

### Acceptance test BEFORE hardware purchase

1. Send a virtual device payload through the authenticated **same** endpoint intended for ESP32.
2. Verify schema validation, authorization, deduplication, database persistence and status UI.
3. Flip a source flag from simulation to device stream for a test plot and verify **no changes** are needed in UI page components or domain logic.
4. Missing hardware -> `NO_LIVE_DEVICE_DATA`; never silently fill real metrics from synthetic values.
5. Document which future activities remain: physical wiring, device provisioning, soil calibration, connectivity and field validation.

### Later (not MVP)

Optional devices: ESP32 with capacitive moisture sensor, temperature/humidity sensor, local rain gauge; electrical conductivity later. Separate device credentials, bounded upload frequency, offline buffering, TLS, enclosure/power and security review.

---

## 12. Data sourcing and compliance plan

| Data type | Candidate official/source | Actual integration plan | Important caveat |
|---|---|---|---|
| Tomato leaf images | PlantVillage dataset | License check -> documented download -> train/holdout; use generated fixture or approved photos in demo | Controlled backgrounds; **not field-proven** |
| Additional field photos | Consenting farms / permitted dataset | Reviewed and labeled, external test set | Seek agronomist input; prevent leakage |
| Weather | Open-Meteo forecast docs | Official forecast API adapter + cache + time metadata | Grid forecast not local flood sensor; check API use terms |
| Bangladesh official flood information | BWDB FFWC | Link to original bulletins / approved import; machine integration only if available and authorized | Coverage and timestamps matter; **not farm inundation** |
| Global river warning context | Copernicus GloFAS | Optional later with exact spatial and licensing controls | River forecasts, not urban flash/coastal flood depths |
| Market prices | Bangladesh DAM daily / commodity-wise reports | CSV/manual report import, source/price type/date/units; API only if confirmed | Site reports ≠ documented, authorized free API |
| Plot characteristics | Farmer-entered | Form + provenance (`user_reported`) | May be inaccurate |
| Simulation data | Test fixture generator | Deterministic seeded fixtures | Never use as proof of field model accuracy |

### Data governance

- Record dataset name, version, URL, license, allowed uses, attribution, download date, transformation and checksum.
- A legitimate API integration must honor published terms, rate limits and caching rules; no CAPTCHA bypass or unauthorized scraping.
- Keep images out of public storage by default; require consent for use in retraining, and protect file access.
- Avoid storing precise farm coordinates unless necessary and consented; allow district-level location.
- Market price imports need an audit trail and import QA; provide “data unavailable” for gaps.
- Use provider-specific fixtures to enable offline demos and test reproducibility.

---

## 13. Evaluation plan (judge-facing proof, not inflated claims)

### AgroDoctor

- Dataset provenance + class counts + train/val/test split method.
- Macro-F1, per-class recall, confusion matrix, top-1 accuracy, calibrated confidence if supported, abstention rate.
- Test on **unseen field-style photos** when possible; clearly separate these scores from controlled-image results.
- Record failure examples (blur, light, unseen diseases, non-tomato photos).
- Expert review of a small set if practical, with agreement metrics and limitations.

### FloodCrop

- Weather API freshness/availability, issuance time handling, unit checks, 24/48/72-hour rainfall calculation tests.
- Compare rainfall outlook with later observed rain where feasible; measure MAE/other forecast quality on held-out issued forecasts.
- If an evaluated flood classifier is eventually introduced, require independent ground-truth flood events, event-based time splits, sensitivity/false-alarm rate and spatial generalization. **Do not conflate heuristic rain thresholds with flood forecasting accuracy.**
- Usability: do farmers understand rain preparedness vs official river-flood warning?

### KrishiMarket

- Import success/error rate, duplicate detection, unit/grade/price-type consistency, staleness, source attribution.
- Calculator property tests for BDT arithmetic and net-return logic.
- For future ML: rolling-origin backtests, MAE/WAPE, baseline comparisons and prediction-interval coverage.
- Demo values do **not** justify claims of actual profits or market prediction accuracy.

### Combined product

- End-to-end task completion, time to view doctor result, clarity of alerts, translation quality, mobile usability, accessibility.
- Test when all external APIs are offline; show correct sources/fallbacks rather than invented “live” data.
- Record what was **verified** vs **demonstrated using simulation** in a `docs/evidence.md` report.

---

## 14. Build order, milestones and acceptance gates

**Suggested:** 8 sprints (can be adapted to deadlines). Every sprint ends with running software, not screenshots.

| Sprint | Primary build | Deliverable | Acceptance gate |
|---|---|---|---|
| **0** | Review spec, repository, source/terms feasibility, domain definitions, prototype design | `AGENTS.md`, architecture note, issue checklist, design tokens | Scope and data-provider limitations explicit |
| **1** | Monorepo, auth/demo mode, Postgres, migrations, i18n, farms/plots, base layout | Working local app and health checks | UI and API start with documented commands; tests pass |
| **2** | AgroDoctor upload/history and curated condition pages | Case workflow with transparent demo fixture | File validation, safe storage, result history and source badges work |
| **3** | Train/evaluate actual tomato disease model; inference service | Versioned model, evaluation, API integration | True model results, metrics, abstention, honest model card |
| **4** | FloodCrop Open-Meteo + rain preparedness + map + approved official-source links | Weather charts and source-aware alerts | No false inundation claims; stale/failed API handled |
| **5** | KrishiMarket import + filter + trend + net calculator | Working market analysis with sourced data or labeled demo fixtures | Unit/type/date checks, import audit and calculations tested |
| **6** | Action Center, notifications, transitions, analytics, Bangla/English, complete responsiveness | Fully unified premium experience | Three modules affect one plot-level action center |
| **7** | Device ingestion scaffold, tests, CI, deployment, reports, demo script | Hardware-ready software MVP | Test virtual ESP32 event; frontend/ML no rewrite; demo runbook passes |

**Fallback if time is limited:** Complete Sprint 0–3 (real AgroDoctor ML) plus simple FloodCrop rain screen, KrishiMarket **sourced/DEMO** price comparison and Action Center. Never replace core function with three superficial “AI” dashboards.

### Suggested two concurrent workstreams (for Codex or two collaborators)

**Workstream A — Backend, data and AI:** database, disease model, image ingestion, providers, rain logic, price import, unified action service, security, tests.

**Workstream B — Frontend and user journey:** design system, routes, transitions, upload UX, maps, charts, bilingual UI, responsive flows, demo polish, end-to-end tests.

Their handoff is the OpenAPI specification, canonical status/provenance types, model/price payloads, and seed data. If Codex runs sequentially, implement both tracks per sprint; don't build all frontend against disconnected fake values.

---

## 15. Codex execution instructions — paste this section when starting the repo

> **You are implementing `PLAN.md` for ZYNTRIX AgroSphere AI.** AgroDoctor AI is the flagship; FloodCrop AI and KrishiMarket AI are integrated supporting modules. Read the entire file before coding. The product must be software-first and future-hardware-ready, with a premium emerald-green Next.js UI, beautiful restrained page transitions, Bangla/English translation, FastAPI/Python backend, PostgreSQL, and real, testable end-to-end flows. Do not ask to buy sensors. Do not stop after a scaffold or hardcoded dashboard. Build sprint by sprint, keep a `TASKS.md` checkbox plan, run tests, fix failures, and update docs. First, inspect current files and propose any justified deviation from the spec in `docs/decisions.md`, then implement Sprint 0 and Sprint 1 immediately. Continue through the remaining sprints as capacity allows. Preserve running code at each checkpoint. Verify external dataset licenses and API availability instead of assuming they exist. Distinguish synthetic/demo/historical/live data in every relevant API response and UI. Disease labels are possibilities, not confirmed diagnoses; rain outlook is not parcel-level flood probability; market trends are not guaranteed earnings. A later ESP32 device must connect through an already-existing, authenticated ingestion contract without rewriting UI/business logic. End each sprint with executable commands, test results, working pages and remaining items. If constraints prevent training or fetching real model/data, leave an explicitly labeled demo mode, explain the blocker, and preserve real-model interfaces and evaluation scripts instead of faking results.

**Repository starting order:**

```text
1. Create README.md, AGENTS.md, TASKS.md, .env.example, compose.yaml.
2. Implement apps/api skeleton, PostgreSQL migrations, farms/plots.
3. Implement apps/web shell, theme, localization and routing.
4. Implement shared metadata/provenance contracts and deterministic seed fixtures.
5. Add AgroDoctor case endpoints and safe photo upload.
6. Train/evaluate and integrate the tomato classifier.
7. Add rainfall/weather-aware FloodCrop module.
8. Add sourced/importable KrishiMarket price module and net-return calculator.
9. Add plot-level Action Center, notifications and premium UX finishing.
10. Add future sensor ingestion interfaces and tested virtual device flow.
11. Run backend/frontend/ML/E2E tests; document evidence and demo limitations.
```

**Verification commands expected (adapt to actual repo):**

```bash
cp .env.example .env
# edit required local config as documented
docker compose up -d db
# run migrations, backend tests and web setup as documented
# backend: pytest
# frontend: lint + typecheck + build + unit tests
# e2e: playwright test using seeded demo data
```

**Never announce "complete" until the acceptance criteria are met.** Keep an honest `docs/status.md` with `DONE / PARTIAL / BLOCKED`, exact test execution and external data restrictions.

---

## 16. Definition of done (software-first competition prototype)

- [ ] `docker compose` or documented local commands start backend, database and frontend.
- [ ] Demo account/farm can be created; tomato plot usable from mobile.
- [ ] AgroDoctor uploads a user image securely, runs a genuine available model **or clearly identifies a demo fixture**, saves result/history, supports uncertainty and feedback.
- [ ] Disease model has reproducible training/evaluation artifacts, documented labels, split, limitations and version; no fabricated metrics.
- [ ] FloodCrop shows forecast rainfall/context with appropriate timestamps, explanatory preparedness status, original sources and official flood references where available.
- [ ] FloodCrop does not claim computed flood depth/probability from rainfall alone.
- [ ] KrishiMarket imports suitable reports or uses clearly labeled examples; displays dates/units/price types and accurate net comparisons.
- [ ] No hidden price prediction based on fabricated data.
- [ ] Shared Farm Action Center combines all three modules at plot/crop level with provenance.
- [ ] Premium green UI has functional navigation, smooth reduced-motion-aware transitions, readable charts, dark/light themes and Bangla/English support.
- [ ] No fake “live” information, no misleading or unsafe pesticide/flood advice.
- [ ] Quality gates: typecheck, lint, API tests, UI tests, critical Playwright e2e tests, data-quality tests.
- [ ] Full documentation: installation, architecture, API, datasets/licenses, model card, privacy, risks, evaluation, demo video/storyboard.
- [ ] Hardware-ready API accepts simulated ESP32 readings securely, persists them and can change sources without rewriting UI/domain logic.
- [ ] All unimplemented or unvalidated components are labeled in `docs/status.md` and on the relevant UI.

---

## 17. Three-minute judge demonstration storyboard

| Time | What to show | Proof point |
|---|---|---|
| **0:00–0:25** | Bangladeshi tomato farmer story, one unified interface | Real, important problem |
| **0:25–1:15** | Upload leaf photo and see AgroDoctor output + uncertainty | Actual core AI, transparent limits |
| **1:15–1:55** | Open FloodCrop: forecast rain, source, official references, precautions | Weather-aware resilience without fake flood predictions |
| **1:55–2:30** | Compare sourced/DEMO tomato prices across two markets; enter delivery costs | Practical economic decision support |
| **2:30–2:50** | Unified Farm Action Center and bilingual mobile view | Why three modules together are useful |
| **2:50–3:00** | Model metrics, verified vs demo evidence, hardware roadmap | Credibility and scale-up readiness |

### Questions to prepare

1. What does AgroDoctor really diagnose? How are unseen diseases handled?
2. Is the image model tested on actual field photos, or only controlled images?
3. What is the difference between your rainfall-preparedness indicator and an official flood forecast?
4. Are market prices actually wholesale/farm-gate values, and how recent are they?
5. How does the hybrid Action Center improve decisions compared with three disconnected websites?
6. How can you add hardware without rebuilding the application?
7. What is validated, what is simulated, and what is still future research?

---

## 18. Dependencies, risks and mitigations

| Risk | Mitigation |
|---|---|
| PlantVillage accuracy overstates real-field performance | Separate controlled and field evaluation; visible field-not-validated disclaimer; abstain when uncertain |
| Insufficient disease images or unsupported labels | Reduce classes; document supported labels; add collected field photos only with consent/review |
| Flood-risk model without flood labels | Only advertise rainfall preparedness, and show official warnings separately |
| Official flood source inaccessible or stale | Links/manual imports, timestamps, explicit unavailable state; no fabricated alerts |
| DAM prices lack public stable machine API | Permission-aware CSV import, manual upload, fixtures, explicit source/date |
| Retail/wholesale confusion | Mandatory price-type, product grade and unit in schema and UI |
| Missing deployment budget | Local Docker-first, open-source dependencies, optional hosting |
| Hardware added much later | Stable ingestion schema, adapter, security, virtual ESP32 tests |
| UI too elaborate compared with functional value | Feature gates; test complete flows before fancy motion |
| Reliance on external APIs | Cache, retries, limits, error/offline state, fixtures for demos |
| Risky agricultural advice | Explain limitations, human review/escalation, no chemical dosing or pump autonomy |
| User privacy | Limit image retention, access controls, consent, deletion/export |

---

## 19. Research / API reference URLs (checked 15 November 2026)

These are candidate references **not proof that all APIs, datasets or automated downloads will be available in your environment**. Confirm usage rights, terms, geospatial resolution and data format before integrating.

1. **PlantVillage / original dataset:** https://github.com/spMohanty/PlantVillage-Dataset  
   Hugging Face dataset and split information: https://huggingface.co/datasets/mohanty/PlantVillage  
   *Controlled leaf images; confirm dataset license and image usage.*
2. **Open-Meteo API docs:** https://open-meteo.com/en/docs  
   *Hourly forecasts include precipitation and weather variables; check use limits and commercial terms.*
3. **Bangladesh Water Development Board Flood Forecasting & Warning Centre (FFWC):** https://ww2.ffwc.gov.bd/  
   About official service: https://ffwc.gov.bd/app/about/about-us  
   *Treat these as authoritative information channels, not automatically authorized scrape endpoints.*
4. **Copernicus GloFAS:** https://global-flood.emergency.copernicus.eu/general-information/about-glofas/  
   *Mainly river forecasts; does not predict farm-level flash flood, coastal flood or inundated area.*
5. **Bangladesh Department of Agricultural Marketing (DAM):** https://market.dam.gov.bd/  
   Daily prices: https://market.dam.gov.bd/market_daily_price_report  
   Commodity-wise records: https://market.dam.gov.bd/commodity_wise_report/damweb/PublicPortal/  
   *Verify whether a permissible export/automated API exists; otherwise support licensed manual imports.*
6. **Google Flood Hub API access info:** https://support.google.com/flood-hub/answer/16364306?hl=en  
   *API access may require pilot approval; do not make it a hard dependency.*

---

## 20. Final instruction to Codex

**Build the hybrid product as one coherent system.** AgroDoctor AI should be the deepest, best-tested feature. FloodCrop and KrishiMarket must be genuinely useful supporting services rather than three disconnected demo cards. The interface should be visually premium and primarily green with unique yet restrained transitions. Make the product functional before spending time on motion polish. Implement real models only when legitimate data supports them; retain honest, well-labeled fallback modes. Build standardized device ingest capability now, so future ESP32/sensor integration becomes a **configuration, wiring, calibration and testing task**—not a software rewrite. Document every unverified claim and incomplete integration. Start from Sprint 0 and proceed to tested milestones.
