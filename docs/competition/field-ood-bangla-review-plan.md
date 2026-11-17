# Field / OOD / Bangla review plan (external evidence)

## OOD / field evaluation harness (software ready; data pending)

Build/retain a locked evaluation set with separate folders:

- non-leaf controls (wall, soil, sky, random noise seed42)
- non-tomato leaves
- unsupported tomato diseases
- blur / extreme lighting
- eventual Bangladesh field photos with consent + license

Metrics to report separately from PlantVillage holdout: rejection rate, false-accept rate, accepted-error rate by source. **Raising softmax threshold is not validated OOD detection.**

## Bangla agronomic review queue

| ID | English string context | Current BN | Reviewer | Status |
|---|---|---|---|---|
| BN-01 | Uncertainty disclaimer on AgroDoctor result | Partial/EN | TBD agronomist+translator | Pending |
| BN-02 | Rain ≠ flood probability disclaimer | Partial/EN | TBD | Pending |
| BN-03 | Market “illustrative proceeds” disclaimer | Partial/EN | TBD | Pending |
| BN-04 | Retraining consent language | EN | TBD privacy reviewer | Pending |
| BN-05 | Disease label display names | EN technical labels | TBD | Pending |

Do **not** mark FE-10 or MR-02 fully verified until this queue has qualified human sign-off and locked evaluation results exist.
