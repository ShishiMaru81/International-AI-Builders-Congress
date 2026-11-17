---
language:
- en
license: apache-2.0
library_name: transformers
pipeline_tag: image-classification
base_model: google/mobilenet_v2_1.0_224
tags:
- image-classification
- plant-disease
- plantvillage
- agriculture
- mobilenetv2
datasets:
- abdallahalidev/plantvillage-dataset
metrics:
- accuracy
- f1
model-index:
- name: plantvillage-mobilenetv2
  results:
  - task:
      type: image-classification
      name: Image Classification
    dataset:
      name: PlantVillage (color, held-out test split)
      type: plantvillage
    metrics:
    - type: accuracy
      value: 0.9917
      name: Accuracy
    - type: f1
      value: 0.9851
      name: Macro F1
    - type: accuracy
      value: 0.9998
      name: Top-3 accuracy
  - task:
      type: image-classification
      name: Image Classification
    dataset:
      name: 'Real-world set: Cropped-PlantDoc (final split, 25 images)'
      type: real-world-set
    metrics:
    - type: accuracy
      value: 0.16
      name: Top-1 accuracy (reached model)
    - type: accuracy
      value: 0.16
      name: End-to-end pass rate
---

# plantvillage-mobilenetv2

Plant leaf disease classifier for the capstone project **AI-Powered Plant Disease Detection and
Farmer Assistance** (IIIT-H, Group 4). A farmer uploads a photo of a crop leaf; this model returns
the most likely PlantVillage class and a confidence score. A LangGraph agent then explains the
result and suggests treatment from a curated agricultural knowledge base.

- Base model: [`google/mobilenet_v2_1.0_224`](https://huggingface.co/google/mobilenet_v2_1.0_224), fine-tuned end to end
- Classes: 38 (14 crops)
- Trained: 2026-10-11 · Hub id: `neghani/plantvillage-mobilenetv2`

## Intended use

- Input: a single RGB photo of one leaf, roughly centred, taken in daylight.
- Output: PlantVillage class name (for example `Tomato___Early_blight`) plus softmax probability.
- Treat a top-1 probability below **0.5** as "not sure" and ask for a clearer
  photo or expert confirmation (see threshold sweep below).
- Not a substitute for a plant pathologist. Treatment decisions must be confirmed with a local
  agricultural extension officer.

## Training data

- [PlantVillage](https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset) `color`
  images, stratified per-class split with seed 42:
  train 43445 · validation 5430 · test 5430.
- Stage 2 (tag `v1.1` and later) also uses [Cropped-PlantDoc](https://github.com/pratikkayal/PlantDoc-Dataset)
  (Singh et al. 2020, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)): 27 of 38 classes;
  the other 11 stay lab-only. See `run_info.json` for the PlantDoc commit and data manifest.
- Augmentation (phone-photo robustness): random resized crop (70-100% PlantVillage, 50-100% PlantDoc),
  horizontal and vertical flip, rotation up to 180°, brightness/contrast/saturation jitter, random Gaussian blur.
- Evaluation preprocessing: resize shortest edge, centre crop 224, normalise (same as the bundled
  `preprocessor_config.json`).

## Results on the held-out PlantVillage test split

| Metric | Value |
|---|---|
| Accuracy | 99.17% |
| Macro precision | 98.79% |
| Macro recall | 98.36% |
| Macro F1 | 98.51% |
| Top-3 accuracy | 99.98% |
| Test images | 5430 |

Confusion matrix: [`reports/confusion_matrix.png`](reports/confusion_matrix.png) ·
Full per-class report: [`reports/classification_report.txt`](reports/classification_report.txt)

### Per-class precision / recall / F1

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `Apple___Apple_scab` | 100.00% | 100.00% | 100.00% | 63 |
| `Apple___Black_rot` | 100.00% | 100.00% | 100.00% | 62 |
| `Apple___Cedar_apple_rust` | 100.00% | 100.00% | 100.00% | 28 |
| `Apple___healthy` | 99.39% | 100.00% | 99.70% | 164 |
| `Blueberry___healthy` | 100.00% | 100.00% | 100.00% | 150 |
| `Cherry_(including_sour)___Powdery_mildew` | 100.00% | 100.00% | 100.00% | 105 |
| `Cherry_(including_sour)___healthy` | 98.82% | 98.82% | 98.82% | 85 |
| `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | 84.21% | 94.12% | 88.89% | 51 |
| `Corn_(maize)___Common_rust_` | 99.15% | 97.48% | 98.31% | 119 |
| `Corn_(maize)___Northern_Leaf_Blight` | 96.84% | 93.88% | 95.34% | 98 |
| `Corn_(maize)___healthy` | 99.15% | 100.00% | 99.57% | 116 |
| `Grape___Black_rot` | 100.00% | 100.00% | 100.00% | 118 |
| `Grape___Esca_(Black_Measles)` | 100.00% | 100.00% | 100.00% | 138 |
| `Grape___Leaf_blight_(Isariopsis_Leaf_Spot)` | 100.00% | 100.00% | 100.00% | 108 |
| `Grape___healthy` | 100.00% | 100.00% | 100.00% | 42 |
| `Orange___Haunglongbing_(Citrus_greening)` | 100.00% | 100.00% | 100.00% | 551 |
| `Peach___Bacterial_spot` | 100.00% | 99.13% | 99.56% | 230 |
| `Peach___healthy` | 97.22% | 97.22% | 97.22% | 36 |
| `Pepper,_bell___Bacterial_spot` | 99.00% | 99.00% | 99.00% | 100 |
| `Pepper,_bell___healthy` | 98.00% | 99.32% | 98.66% | 148 |
| `Potato___Early_blight` | 100.00% | 100.00% | 100.00% | 100 |
| `Potato___Late_blight` | 100.00% | 96.00% | 97.96% | 100 |
| `Potato___healthy` | 100.00% | 73.33% | 84.62% | 15 |
| `Raspberry___healthy` | 100.00% | 100.00% | 100.00% | 37 |
| `Soybean___healthy` | 99.41% | 99.80% | 99.61% | 509 |
| `Squash___Powdery_mildew` | 100.00% | 100.00% | 100.00% | 184 |
| `Strawberry___Leaf_scorch` | 100.00% | 100.00% | 100.00% | 111 |
| `Strawberry___healthy` | 100.00% | 100.00% | 100.00% | 46 |
| `Tomato___Bacterial_spot` | 100.00% | 99.53% | 99.76% | 213 |
| `Tomato___Early_blight` | 94.34% | 100.00% | 97.09% | 100 |
| `Tomato___Late_blight` | 97.38% | 97.38% | 97.38% | 191 |
| `Tomato___Leaf_Mold` | 100.00% | 100.00% | 100.00% | 95 |
| `Tomato___Septoria_leaf_spot` | 100.00% | 96.05% | 97.98% | 177 |
| `Tomato___Spider_mites Two-spotted_spider_mite` | 98.81% | 98.81% | 98.81% | 168 |
| `Tomato___Target_Spot` | 98.56% | 97.86% | 98.21% | 140 |
| `Tomato___Tomato_Yellow_Leaf_Curl_Virus` | 99.44% | 100.00% | 99.72% | 536 |
| `Tomato___Tomato_mosaic_virus` | 94.87% | 100.00% | 97.37% | 37 |
| `Tomato___healthy` | 99.38% | 100.00% | 99.69% | 159 |

### Confidence threshold sweep

Coverage is the share of test images with top-1 probability at or above the threshold; the
remaining images would be answered with "not sure". Recommended `CONFIDENCE_THRESHOLD` for the API:
**0.5** (lowest threshold whose accuracy on covered images is at least 97% with coverage of at least 50%).

| Threshold | Coverage | Accuracy on covered | Accuracy (abstain = wrong) |
|---|---|---|---|
| 0.50 | 99.91% | 99.24% | 99.15% |
| 0.55 | 99.71% | 99.35% | 99.06% |
| 0.60 | 99.54% | 99.43% | 98.97% |
| 0.65 | 99.30% | 99.59% | 98.90% |
| 0.70 | 99.19% | 99.59% | 98.78% |
| 0.75 | 99.01% | 99.63% | 98.64% |
| 0.80 | 98.73% | 99.68% | 98.42% |
| 0.85 | 98.32% | 99.74% | 98.07% |
| 0.90 | 97.75% | 99.89% | 97.64% |
| 0.95 | 96.92% | 99.90% | 96.83% |

<!-- REAL_WORLD_START -->
## Real-world images (field and web photos)

### How to read the numbers

PlantVillage photos are taken under controlled conditions: one leaf, plain background. Accuracy on
the held-out PlantVillage split above is therefore an **upper bound**, not what a farmer should
expect from a phone photo. Images of the same leaf can appear in both the training and test splits,
which inflates it further. The real-world figures below are the more honest ones.

### Result

Test set: 25 images from Cropped-PlantDoc, spanning 25 classes that map to
PlantVillage labels. Split evaluated: **final**. Evaluated on 2026-10-12 with the same chain as
the live app (shared quality gate, crop strategy **B**, then this model on the 256×256
crop). The strategy and threshold were chosen on the tune split with `model/eval_strategies.py`.

| Metric | Value |
|---|---|
| Rejected by the quality gate (retake photo) | 0 of 25 |
| Top-1 on images that reached the model | 16.0% (95% CI 6.4% to 34.7%) |
| Top-3 on images that reached the model | 32.0% |
| "Not sure" answers | 16 of 25 |
| **End-to-end pass rate** (correct and confident, out of all images) | **16.0%** (95% CI 6.4% to 34.7%) |

Project target for the end-to-end pass rate: 50.0%. The point estimate is below the
target. With few images the confidence interval is wide, so treat the figure as indicative.
Stage 2 (`v1.1`) quotes the one-shot final test in `model/final_report.md` (284 images); that
file is the only source of real-photo numbers. Do not mix it with a 25-image `eval_real_world_set`
run.

Confidence threshold used: 0.85. It was fixed on the tuning split only; the final split
is reported once.

Most common mistakes:

| True | Predicted | Count |
|---|---|---|
| `Apple___Apple_scab` | `Tomato___healthy` | 1 |
| `Apple___healthy` | `Tomato___Late_blight` | 1 |
| `Pepper,_bell___healthy` | `Tomato___healthy` | 1 |
| `Blueberry___healthy` | `Strawberry___Leaf_scorch` | 1 |
| `Cherry_(including_sour)___healthy` | `Squash___Powdery_mildew` | 1 |
| `Corn_(maize)___Northern_Leaf_Blight` | `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | 1 |
| `Corn_(maize)___Common_rust_` | `Tomato___Early_blight` | 1 |
| `Peach___healthy` | `Blueberry___healthy` | 1 |

Per-image results, the per-class table and `run.json` (what was tested):
[`reports/real_world_set/`](reports/real_world_set/). Image list, labels and sources:
[`real_world_set/`](real_world_set/) (images are not redistributed here).
Set fingerprint `65f860f5c078` · model weights `f1a98e77629c`

The section is regenerated by the Colab notebook whenever the set, the weights or the threshold
change.



### Reproducing

```bash
python model/eval_real_world_set.py --set_dir model/data/real_world_set --split final \
  --predictor app_predictor:diagnose --strategy B --threshold 0.85
```
<!-- REAL_WORLD_END -->

## Limitations

- PlantVillage images are lab-style photos on plain backgrounds; accuracy on field photos is lower.
  The real-world section above reports the gap.
- Only the 38 PlantVillage classes are known. Other crops, other diseases, nutrient
  deficiencies and pest damage will be forced into the nearest known class; rely on the threshold
  and the "not sure" path.
- One leaf per photo. Mixed infections and whole-plant shots are out of scope.
- Confidence is a softmax probability. Stage 2 ships a fitted temperature in `calibration.json`
  (NLL on PlantDoc validation). Treat remaining overconfidence as a limitation.
- PlantDoc and the 50-image real-world set are web photos; they overstate phone-photo performance.
  The one-shot comparison is `final_report_v1_1.md` (not used for any choice).

## Training details

- base_model: `google/mobilenet_v2_1.0_224`
- init_from: `google/mobilenet_v2_1.0_224`
- plantdoc_commit: ``
- code_commit: `01d9caf11d17ffbc918d6eb27ef4af90ef627da3`
- code_dirty: `False`
- label_smoothing_factor: `0.0`
- train_rows: `43445`
- num_labels: `38`
- epochs: `5.0`
- learning_rate: `0.0005`
- per_device_train_batch_size: `64`
- weight_decay: `0.01`
- warmup_steps: `0.05`
- lr_scheduler_type: `SchedulerType.COSINE`
- fp16: `True`
- seed: `42`
- wall_time_sec: `381.5`
- device: `cuda:0`

## Use in the API (Phase 5)

```python
from transformers import pipeline

clf = pipeline("image-classification", model="neghani/plantvillage-mobilenetv2", revision="v1.0")
preds = clf("leaf.jpg", top_k=3)
# [{'label': 'Tomato___Early_blight', 'score': 0.93}, ...]
top = preds[0]
if top["score"] < 0.5:
    print("Not sure - please retake the photo or consult an expert")
```

Class names match the keys of `api/data/knowledge/diseases.json` in the project repository, so
the prediction can be looked up directly for symptoms and treatment guidance.

Project repository: https://github.com/neghani/iiith-group4-capstone-plat-leaf-decease-detection

## Disclaimer

Treatment suggestions produced from this model's output are general guidance only and must be
validated with local agricultural experts before critical action.
