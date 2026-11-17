# Claims vs evidence register (DRAFT)

Every numeric or capability statement used in demos/submission materials must map to one row.

| Claim | Classification | Evidence pointer | Must not imply |
|---|---|---|---|
| Holdout accuracy 115/120 (0.95833), macro-F1 ≈ 0.95797 | Saved historical research result | `ml/artifacts/evaluation.json`, `docs/model_card.md` | Bangladesh field accuracy |
| Three tomato labels only | Independently confirmed in card/code | `model.json` labels | Support for other crops/diseases |
| Uncalibrated softmax scores | Disclosed limitation | model card + API `score_type` | Diagnostic probability |
| Random RGB noise can score as healthy | Independently reproduced in audit; keep as negative control | Audit MR-02; regression harness pending | Population OOD error rate |
| Rain preparedness threshold 75 mm / 50 mm | Synthetic/heuristic rule | `services.preparedness` | Official flood warning |
| Sample prices ৳42 / ৳46 | Synthetic scenario | demo seed in `/auth/demo` | Real transaction prices |
| Net ৳16200 / ৳17800 for 400 kg example | Calculation example on synthetic quotes | calculator + e2e journey | Guaranteed farmer proceeds |
| Live Open-Meteo connectivity | Historical smoke / optional live check | `docs/smoke-result.json` (historical) | Always-available cloud weather |
| Ownership isolation (404 cross-user) | Independently tested | API pytest | Production RBAC/security audit |
| Free Render 0.1 CPU / 512 MB suitability | Configuration exists; performance **not** established | `render.yaml` + hosting docs | Production SLA |
| Crop-loss reduction % | Proposed target only | `business-impact-plan.md` | Demonstrated impact |
| Farmer adoption / revenue | Unanswered | interview protocol | Traction proof |
| Full Bangla agronomic safety text | Partial UI; expert review pending | `docs/status.md` | Certified translation |

Update this table whenever README, pitch, or portal text changes.
