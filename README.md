# ZYNTRIX AgroSphere AI

A software-first agricultural workspace: AgroDoctor leaf screening, FloodCrop rainfall preparedness, KrishiMarket net selling comparisons, shared farms, actions and future sensor ingestion.

For a public website, see [Netlify + free backend deployment](docs/netlify-deployment.md). The root `netlify.toml` configures the frontend and `render.yaml` prepares the separate free Python/PostgreSQL demo backend. Cloud deployment requires account authorization and the real HTTPS backend URL; localhost Docker URLs cannot serve Netlify visitors.

## GitHub checkout with the trained model

This version is maintained in the public repository `Nabib-Azad-Jisan/zyntrix-agrosphere-ai`. Model weights are distributed as an attributed research artifact in release `v0.1.0`, separate from Git history. With GitHub CLI installed:

```powershell
git clone https://github.com/Nabib-Azad-Jisan/zyntrix-agrosphere-ai.git
cd zyntrix-agrosphere-ai
gh release download v0.1.0 --repo Nabib-Azad-Jisan/zyntrix-agrosphere-ai --pattern model.pt --dir ml/artifacts
docker compose up -d --build
```

Open http://127.0.0.1:3100. The model card includes the artifact SHA-256 checksum. Without the optional model download, the application remains usable and explicitly abstains from disease classification. Source attribution, evaluation and limitations are committed alongside the training scripts. Private uploaded photos, local databases, credentials and installed dependencies are excluded from Git.

## Run locally (Windows, without Docker)

From this directory, create a Python environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r apps/api/requirements.txt
cd apps/api
..\..\.venv\Scripts\python -m alembic upgrade head
..\..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

Open http://127.0.0.1:3000/en or /bn and choose **Explore a demo farm**. The initial session is private and expires in seven days. This is local demo authentication, not a production identity provider.

To choose your area, open **FloodCrop AI**, search a place or click/drag the map pin, then consent and press **Save area & use live weather**. The same picker is available when creating a farm. Manual coordinates work when search is unavailable. See [area selection](docs/area-selection.md).

For the current workspace, a Python environment has already been installed **one directory above** this repository (`../.venv`). Use `../../../.venv/Scripts/python.exe` from `apps/api` with that environment.

## PostgreSQL / Docker

Start Docker Desktop first, then run `docker compose up -d --build` from this repository. It starts PostgreSQL, migrations, FastAPI with CPU model inference, and the Next.js standalone server. This checkout uses the Compose project name **agrosphere-congress**, separate from the older `agrosphere-ai` project on this PC.

- Website: http://127.0.0.1:3100
- API / interactive reference: http://127.0.0.1:8100/docs
- PostgreSQL (local tools): 127.0.0.1:55432

`WEB_PORT`, `API_PORT` and `DB_PORT` can override these defaults. Rebuild the web image after changing API_PORT because its browser-facing API address is set at build time. CORS includes the chosen local website origins. Ports bind only to localhost. Demo credentials are local development values; replace them for deployment. Images and PostgreSQL use separate persistent named volumes. Existing local SQLite records are not automatically migrated into the fresh PostgreSQL workspace.

```powershell
docker compose ps
docker compose logs --tail 50 api
docker compose stop
docker compose start
```

Stopping containers preserves records. Avoid `down -v` unless you intend to destroy the Docker database and image storage. The API and web containers run as non-root users. The first build downloads Linux dependencies and can take several minutes.

To repeat integration checks with the parent-directory environment used in this workspace:

```powershell
..\.venv\Scripts\python scripts/docker_verify.py
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:3100'
$env:AGROSPHERE_API_URL='http://127.0.0.1:8100/api/v1'
cd apps/web
npm run test:e2e
```

`docker_verify.py` creates a disposable test workspace, tests actual model inference and all modules, restarts only this stack's API, verifies persisted records and device deduplication, then removes the disposable workspace.

For standalone PostgreSQL, set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/agrosphere`, then run migrations and the API. Environment variables must be set in your terminal or service configuration; `.env.example` is a reference, not automatically loaded by every command.

## Models and data

See [training instructions](ml/doctor/README.md) and [model card](docs/model_card.md). This workspace now contains a real three-class MobileNetV3 research model trained on 570 leaf-grouped PlantVillage images and evaluated on 120 held-out images. Install `apps/api/requirements-ml.txt` in the API environment to enable inference. The installed parent-directory environment already includes these libraries. Weights are intentionally ignored by Git; regenerate them using the documented preparation/training/release scripts when cloning source elsewhere.

The app only enables an installed model after evaluation and an explicit artifact release flag. Without one it abstains and never generates sample disease scores. No model has been field-validated. Rainfall thresholds are illustrative heuristics, not flood probabilities. Initial market prices are synthetic examples, not reported transactions. Official FFWC and DAM links are references; no scraping is performed.

## Quality gates

```powershell
# API directory, using your chosen virtual environment
python -m pytest -q
# Web directory
npm run typecheck
npm run lint
npm run test
npm run build
# Run API and frontend first; installed Microsoft Edge is used on Windows
npm run test:e2e
```

For Linux CI, `PLAYWRIGHT_CHANNEL=chromium` uses Playwright's installed Chromium instead of Edge. Production uses `npm run build` and the standalone server; the provided Dockerfile packages static assets alongside it.

API reference: http://127.0.0.1:8000/docs. All personal routes require a Bearer session token. Device ingestion uses a separate `X-Device-Key` header. See [hardware contract](docs/hardware_integration.md), [architecture](docs/architecture.md), [evidence](docs/evidence.md) and [status](docs/status.md).

## GitHub Actions template

The complete CI definition is supplied as [docs/ci-workflow.yml](docs/ci-workflow.yml). The current GitHub login can upload repositories and releases but lacks the additional `workflow` permission required to create active Actions files. No account permissions were changed. To enable CI later, use an authorized GitHub login, copy the template to `.github/workflows/ci.yml`, and explicitly add that file (it is currently ignored to keep uploads compatible with this login). Automated GitHub Actions execution is not claimed; the documented local and Docker checks have been run.
