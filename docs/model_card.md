# Active multi-crop research models

AgroDoctor uses two pinned upstream models: PlantVillage MobileNetV2 (38 global labels, 11 disease-enabled crop groups) and rice EfficientNet-B0 (17 classes). Both run locally from verified TorchScript exports. They have no independent AgroSphere accuracy evaluation or field validation. A 0.85 threshold is a research policy, not calibrated diagnostic certainty. See [sources, preprocessing, coverage and installation](agrodoctor-multicrop.md).

No publisher metric is displayed as an AgroSphere result. The original tomato evaluation below is retained for historical reproducibility and saved-case readback; it does not describe the active multi-crop models.

## Historical three-class tomato model

MobileNetV3 Small, pretrained ImageNet backbone frozen, classifier trained for 10 epochs with seed 42. Artifact and measured evaluation are in `ml/artifacts/`; source inventory and reproducible grouped manifest are in `data/plantvillage/`.

Actual selected labels: Tomato___Early_blight, Tomato___Late_blight, Tomato___healthy. All other conditions are unsupported by this historical artifact. The historical model screens user-declared tomato images only; it does not have a validated crop detector or out-of-distribution detector.

570 original color images: 360 training, 90 validation, 120 holdout (40 per class). One image per unambiguous official physical-leaf group. Original test membership preserved; validation groups taken only from original training split. Exact checksum and conservative dHash duplicate screening found no duplicate selected images. Other near-duplicates may still exist; this is not an independent dataset audit.

Holdout accuracy 0.95833; macro-F1 0.95797; ECE 0.05202; score-threshold abstention rate 0.00833. Early-blight recall 0.90, late-blight recall 1.00, healthy recall 0.975. Threshold 0.50 selected on validation only; softmax scores remain uncalibrated. Holdout timing approximately 0.0134 seconds/image in batched CPU evaluation; this is not HTTP end-to-end latency. Image-quality rejection is additional and not included in those metrics. Exported TorchScript parity and failure records are checked by scripts/release_model.py.

These are small controlled-image dataset results, NOT Bangladesh field accuracy or confirmed diagnoses. There are no field test photographs, crop/OOD rejection benchmarks, agronomist validation or reviewed Bangla disease translations. Output is a possible condition with safe scouting steps. No pesticide dosing is prescribed. Novel diseases and non-leaf images can produce misleadingly strong scores; do not use this prototype for treatment decisions.

Attribution: Mohanty, Hughes and Salathé, 2016, Digital Epidemiology Lab, EPFL. DOI 10.3389/fpls.2016.01419. Original author dataset card declares CC BY-SA 3.0. Preserve applicable attribution/share-alike terms. Pretrained backbone weights are obtained through torchvision's official model distribution; consult torchvision documentation and ImageNet terms for intended deployment.
