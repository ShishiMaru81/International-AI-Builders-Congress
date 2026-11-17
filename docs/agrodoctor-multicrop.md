# AgroDoctor multi-crop research screening

Implemented locally on 17 November 2026 after approval of the multi-crop design. This replaces the active three-class tomato-only inference path. Original `ml/artifacts/model.pt`, its card/results and saved case model snapshots are retained. It does not retrain either upstream model or establish field accuracy.

## What the user can do

Choose a crop in AgroDoctor, select a matching owned plot or create one with its farm/name/area, then upload one JPG, PNG or WebP photo (up to 8 MB and 20 million decoded pixels). The same crop catalog is available when adding plots in Farms. Results/history/CSV retain the submitted crop, plot and model version. Existing tomato cases remain readable.

Crop mismatch is rejected before image decoding when the declared crop differs from the plot crop. The multi-crop model scores all 38 labels globally; selecting a crop never inflates its scores by restricting/renormalizing the label set. If the highest scoring label belongs to another crop, the result abstains. Rice uses a dedicated 17-class model: it cannot verify that an arbitrary photo is rice.

The main upload flow and crop names have English/Bangla copy; raw model condition names and some notes/advice remain English. Expert review of agronomic translations is still required.

## Supported crop groups

Only disease-enabled groups are offered. Blueberry, raspberry and soybean have healthy-only labels in the source classifier and are excluded from the screening selector.

| Crop | Model | Classes for this crop | Healthy reference |
|---|---|---:|---|
| Apple | plantvillage | 4 | Yes |
| Cherry | plantvillage | 2 | Yes |
| Maize | plantvillage | 4 | Yes |
| Grape | plantvillage | 4 | Yes |
| Orange | plantvillage | 1 | No |
| Peach | plantvillage | 2 | Yes |
| Bell pepper | plantvillage | 2 | Yes |
| Potato | plantvillage | 3 | Yes |
| Squash | plantvillage | 1 | No |
| Strawberry | plantvillage | 2 | Yes |
| Tomato | plantvillage | 10 | Yes |
| Rice | rice | 17 | Yes |

Orange and squash have no healthy class; the UI discloses that healthy leaves cannot be ruled in or out. A supported crop does not imply coverage of every disease, pest, nutrient problem or local variety.

## Pinned models and provenance

| Bundle | Upstream / revision | Original SafeTensor SHA256 |
|---|---|---|
| plantvillage | [neghani/plantvillage-mobilenetv2](https://huggingface.co/neghani/plantvillage-mobilenetv2) / `d33601185b32cf05b3942661b8d84ffb86dc48ec` | `f1a98e77629c36b5fe90a0fbed7ba56f097ce419c6dad8456bd135f36ea8d426` |
| rice | [Huyt/rice-leaf-disease-efficientnet-b0](https://huggingface.co/Huyt/rice-leaf-disease-efficientnet-b0) / `a12e09fd765eda2b846836a965e951151a9125f7` | `33e38196b5726796cdaccfdfa906f8db8524b087b4d5e13d87de7a1a5e118023` |

Both upstream model repositories declare Apache 2.0. Dataset attribution/terms remain separate: PlantVillage/PlantDoc and the rice source are described in each pinned SOURCE_README.md; deployment requires respecting those terms. No remote repository code is executed. Known Transformers MobileNetV2 and timm EfficientNet-B0 architectures are instantiated locally, SafeTensor digests and label order checked, then exported to separate TorchScript bundles.

PlantVillage preprocessing: shortest side 256, center crop 224, bilinear, mean/std 0.5. Rice: shortest side 256, center crop 224, bicubic, ImageNet mean/std. Export checks used 3 deterministic tensors per model and reloaded the saved artifact; max absolute logit difference was 0. These are conversion correctness checks, not image-classification accuracy tests.

The runtime checks pinned source metadata, artifact digest, labels, preprocessing, threshold, finite outputs and output shape. A lock prevents duplicate cold model loads. Capabilities expose model readiness, sources and limitations. `/health/ready` returns 503 if an active bundle is absent or corrupt; `/health/live` remains a liveness check. A retired tomato artifact no longer controls active readiness.

## Install / reproduce

From the project root in a terminal with the selected Python environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements.txt
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r ml/doctor/requirements-export.txt
.\.venv\Scripts\python.exe scripts/install_doctor_models.py
```

SafeTensor sources are downloaded from the exact fixed revisions; the generated model.pt/model.json/SOURCE_README.md bundles live in `ml/artifacts/multicrop/{plantvillage,rice}`. Large binaries stay ignored by Git. Optional `--models rice` installs one bundle. `--output` and runtime `MULTICROP_MODEL_DIR` can point to another directory. API inference only needs torch/torchvision; conversion packages are not runtime requirements.

Local Compose mounts `ml/artifacts` at `/models` and sets `MULTICROP_MODEL_DIR=/models/multicrop`. Run the installer before local Compose. The hosted Dockerfile builds both bundles in a separate conversion stage and copies them into its runtime image. This updated hosted image has not been deployed or resource-tested on a free cloud tier.

## Failure and privacy behavior

- Invalid, empty, oversized, animated or undecodable images fail with useful errors. EXIF orientation is applied, transparency composited on white, saved JPEGs remove EXIF metadata.
- Resolution, brightness and blur checks can save an uncertain observation with no model score. Good-quality images with a missing/corrupt model receive 503 and are not saved as a fabricated diagnosis.
- All file entry paths lock while screening. Plot context changes abort/discard old responses and clear preview/result state; delayed plot creation cannot pull the user back to an old selection. An aborted HTTP request may already have saved on the server; inspect history before retrying.
- Cases are paginated by owner/plot. Older-page loading and plot switching do not mix results or cause the former render loop. Images use authenticated fetches with blob cleanup, 410 handling and a separate download control.
- Case notes appear newest first; no old note is silently copied into the new-note box. Review requests are private records only; no advisor is contacted.
- Failed database/storage writes roll back and remove the newly written photo. Private cases/photos remain owner-protected.

## Model limits and competition claims

A 0.85 softmax threshold is an explicit conservative research policy, not calibrated disease confidence. The upstream PlantVillage card reports a poor tiny field/web-photo result, and rice reports rare-class weakness and capture-condition confounding. AgroSphere has not independently reproduced those reported metrics, measured Bangladesh field performance, validated OOD rejection or obtained agronomist approval.

Unknown diseases, non-leaf images, mixed crops/leaves and other out-of-distribution images can still produce high scores. There is no universal crop/leaf detector. Say “possible condition” and present raw scores as uncalibrated. Do not quote the original tomato holdout score as the accuracy of these new models. No chemical treatment or dosing is prescribed.

## Integration evidence

See the feature verification report delivered with this change. Real HTTP smoke inputs were one PlantVillage potato early-blight image, one maize common-rust image, and UCI rice bacterial-leaf-blight DSC_0365.JPG, plus wrong-crop/noise/flat controls. All three leaf photos reached their respective real model; results were possible early blight, common rust and bacterial blight. The wrong-crop result abstained, noise was low-confidence and flat input failed quality. Six handpicked smoke cases cannot estimate accuracy; source overlap with training is unknown.

Photo sources: [PlantVillage author repository](https://github.com/spMohanty/PlantVillage-Dataset) (revision7f7ecc7e1eaca78107e3affe7cb5abd9427e139a; retain CC BY-SA attribution); [Rice Leaf Diseases, Shah/Prajapati/Dabhi, UCI](https://archive.ics.uci.edu/dataset/486/rice+leaf+diseases), DOI10.24432/C5R013, CC BY4.0. Scratch copies and detailed observed results are local test artifacts, not a redistributed benchmark.
