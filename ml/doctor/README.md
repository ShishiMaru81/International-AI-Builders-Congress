# Reproducible training and held-out evaluation

The default app abstains. No disease weights or fabricated metrics are bundled.

1. Obtain a permitted dataset. Review original image provenance and license, retain attribution. PlantVillage is a candidate, not a bundled dependency.
2. Identify actual tomato labels programmatically from your dataset directories. Choose a supported subset.
3. Group original leaves/plants and manually reviewed perceptual near-duplicates before assigning groups to train/val/test. Never put variants of one leaf in different splits. Keep field photographs in a separate external evaluation set.
4. Create `manifest.csv` with columns `path,label,group_id,split`, paths relative to the image root, split one of train/val/test.
5. Create `dataset.json` with name, version, url, license, attribution, permission_verified=true, grouping_method. Keep download dates and checksums in that inventory.
6. Install `requirements.txt` in a dedicated environment. Validate first:

```sh
python ml/doctor/pipeline.py --manifest manifest.csv --root /data/images --license dataset.json --validate-only
python ml/doctor/pipeline.py --manifest manifest.csv --root /data/images --license dataset.json --epochs 8
```

The pipeline freezes a pretrained MobileNetV3 backbone, trains its classifier, selects the epoch and abstention threshold on validation data only, and evaluates once on holdout. It reports macro-F1, accuracy, per-class precision/recall, confusion matrix, ECE, abstention, latency, counts and manifest hash. Image preprocessing matches the API.

No field score is emitted. Exact-duplicate and group leakage are rejected; near-duplicate identification requires your reviewed group manifest. Review failure photos, license, class support and split before setting `release_approved` in model.json. The registry ignores unapproved artifacts. PyTorch dependencies must also be installed in the inference environment to run an approved model.

Known limits: not a validated crop/OOD detector; no calibrated confidence; no external field evaluation; no agronomist validation. Do not claim diagnostic certainty.
