# AI tools, data and contribution declaration (DRAFT)

## Human ownership

- Product owner / implementer of the original prototype: **Nabib Azad Jisan** (GitHub repository owner).
- This remediation pass was assisted by a **Cursor coding agent** operating locally on the owner's machine. The agent is **not** a repository collaborator and was not added to GitHub permissions.

## AI assistance disclosure

| Activity | Tool / agent | Human review |
|---|---|---|
| Original product build (pre-audit) | Per owner workflow / prior sessions | Owner |
| Audit remediation coding, tests, docs | Cursor agent (this session) | Owner must review diffs before push/submit |
| Competition draft text | Cursor agent | Owner must edit for voice/accuracy |
| Disease labels / agronomic advice | Not AI-certified | Qualified human review still pending |

## Datasets and weights

- PlantVillage selected tomato color subset (570 images inventory; images downloaded separately). Dataset card declares CC BY-SA 3.0. Attribution: Mohanty, Hughes and Salathé (2016), EPFL. No independent legal review.
- Released research weights `model.pt` (SHA-256 in `ml/artifacts/model.json`), MobileNetV3 Small with torchvision ImageNet-pretrained backbone — consult torchvision/ImageNet terms for redistribution.
- Synthetic DEMO weather and market fixtures authored for the prototype.

## External APIs

- Open-Meteo forecast + geocoding (attribution required; check commercial terms before commercial deploy).
- OpenStreetMap raster tiles (tile usage policy applies).
- FFWC and DAM are **linked references only** — no scraping.

## What was generated vs verified

Generated/assisted: remediation code, tests, competition drafts, documentation updates.  
Verified locally in this workspace: MD-01 guard tests, baseline pytest/typecheck/lint/build after guard, model release checksum download.  
**Not verified here:** live Netlify/Render deploy, Docker engine runs, farmer interviews, field disease accuracy, final video recording, portal submission.
