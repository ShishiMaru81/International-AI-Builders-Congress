# ZYNTRIX AgroSphere AI v0.1.0

Software-first Docker prototype with a Next.js frontend, FastAPI backend, PostgreSQL persistence and three integrated agricultural modules.

Verified on the development PC: 10 backend integration tests against PostgreSQL inside Docker, 2 frontend unit tests, 2 desktop/mobile browser journeys against the Docker application, real model inference and persistence across API restart. Source documentation records exact evidence and remaining limitations.

The `model.pt` release asset is the approved local research classifier. Download it into `ml/artifacts/` before starting Docker to enable actual image screening. Its SHA-256 checksum is recorded in `ml/artifacts/model.json`.

Model: MobileNetV3 Small, three actual tomato labels (early blight, late blight, healthy), trained on 360 controlled images with 90 validation and 120 held-out images. Holdout accuracy 115/120 and macro-F1 0.95797. These are small controlled-dataset results, not field accuracy. Model scores are uncalibrated; crop/OOD rejection has not been validated.

Dataset attribution: Mohanty, Hughes and Salathe (2016), Digital Epidemiology Lab, EPFL, DOI 10.3389/fpls.2016.01419. The original author PlantVillage dataset card declares CC BY-SA 3.0; retain attribution and applicable share-alike obligations. See docs/model_card.md and data/plantvillage/dataset.json.

Default weather/market examples are clearly labeled synthetic. Explicit live Open-Meteo weather is available for consented coordinates; no authorized official flood feed or automatic market feed is connected. Full Bangla translation, independent field validation and production security hardening remain unfinished. This is not a confirmed diagnosis, official flood warning or earnings guarantee.

Docker website: http://127.0.0.1:3100. API reference: http://127.0.0.1:8100/docs. See README.md for installation and the optional model download command.
