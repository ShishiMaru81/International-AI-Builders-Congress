# One-page project summary (DRAFT — not submitted)

**Project:** ZYNTRIX AgroSphere AI  
**Team / owner:** Nabib Azad Jisan (repository owner)  
**Stage framing:** Existing local research prototype suitable for Idea to Unicorn presentation (reconfirm portal eligibility before submit)

## Problem and users

Smallholder tomato growers in Bangladesh need one place to (1) inspect suspicious leaf symptoms without mistaking software output for a lab diagnosis, (2) prepare for heavy rainfall using dated forecasts and official flood references kept separate, and (3) compare recorded market prices after their own transport and handling costs. Extension workers need attributable evidence, not opaque scores.

## Solution (actual current capabilities)

AgroSphere is a bilingual (English/Bangla) web workspace with a FastAPI backend:

1. **AgroDoctor AI (flagship):** private tomato-leaf photo upload, image quality checks, optional approved MobileNetV3 three-class research model (`Early blight`, `Late blight`, `healthy`), uncalibrated scores, abstention, case history, feedback notes, CSV export.
2. **FloodCrop AI:** farm area search/map/manual coordinates with consent, DEMO or LIVE Open-Meteo rainfall outlook, heuristic preparedness thresholds, FFWC link (no official flood feed).
3. **KrishiMarket AI:** labeled sample/imported BDT prices, decimal net-proceeds calculator, private CSV import, saved price targets (storage only; no automatic alerts).
4. **Shared Action Center** over owner-scoped farms/plots with provenance badges.

## AI / data approach (precise roles)

- **ML:** closed-set tomato leaf image classifier on a 570-image PlantVillage research subset (360/90/120). Controlled-image holdout accuracy is a **saved historical research result**, not Bangladesh field accuracy.
- **Rainfall:** rule applied to forecast totals — **not** a flood probability model.
- **Market:** arithmetic on observed/imported quotes and farmer-entered costs — **not** price prediction.

## Localization and ethics

Bangla navigation and core headings exist; full safety-critical translation and expert agronomic wording review remain pending. Photos are private, re-encoded, owner-scoped. Retraining consent defaults off. No chemical dosing or pump automation.

## Measured / demonstrated vs future

| Claim type | Example |
|---|---|
| Independently re-runnable locally | API/UI tests, ownership isolation, decimal calculator, abstaining upload path |
| Saved historical research | 115/120 holdout accuracy / macro-F1 ≈ 0.958 on controlled images |
| Synthetic scenario | Demo rain totals, ৳42/৳46 sample quotes |
| Not yet evidenced | Field disease accuracy, crop-loss reduction, farmer adoption, live cloud durability |

## Next steps

Complete audit remediation (session/plot continuity, CSV/model integrity, Bangla/a11y, reproducible ML gates), finish competition video with failure paths, then seek farmer interviews and locked OOD/field evaluation before stronger claims.
