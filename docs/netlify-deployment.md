# Netlify frontend + free Render demo backend

The project remains Next.js + FastAPI/PyTorch + PostgreSQL. Netlify hosts the frontend with its Next.js adapter. The existing Python process runs separately; Netlify Server currently supports JavaScript/TypeScript on Node.js.

## Prepared configuration

- Root `netlify.toml`: base directory `apps/web`, publish `.next`, Node 24. The build checks backend configuration before invoking Next.js. The Next config retains standalone output for Docker and lets Netlify's adapter manage its own output when NETLIFY=true.
- `render.yaml`: **free** Docker web service and **free** PostgreSQL database, with no paid disk. Build uses root-context `deploy/api.Dockerfile`, downloads the public model release, verifies its SHA-256 and includes the model in the image. Uploaded user data is excluded from build context.
- Render's `postgres://` / `postgresql://` connection strings are normalized to the installed psycopg driver. The cloud server binds the provider's PORT.

## Deploy order

1. Connect the GitHub repository to a new Netlify project. Keep the backend build variable unset until step 4; an early build will intentionally stop with an actionable message rather than publish a broken localhost connection. Record the assigned HTTPS Netlify URL.
2. Sign in to Render and create a Blueprint from https://github.com/Nabib-Azad-Jisan/zyntrix-agrosphere-ai using `render.yaml`. Review that both resources say **Free**. Supply `CORS_ORIGINS` as the exact Netlify origin (for example `https://your-project.netlify.app`, without a trailing slash). Preview deploy origins must be added individually if used.
3. Wait for the Python service and database to become healthy. Its `/api/v1/health` endpoint must return `{ "status": "ok", ... }`. The `/api/v1/doctor/models/current` endpoint should show the approved research model as available.
4. In Netlify, set **build** environment variable `NEXT_PUBLIC_API_URL` to the actual Python URL plus `/api/v1`, for example `https://your-api.onrender.com/api/v1`. This is a public service address, not a secret. Never put database passwords or provider tokens in NEXT_PUBLIC variables.
5. Redeploy Netlify. The preflight verifies HTTPS, public addressing, actual API health and CORS for the current site origin. Free backends can take around a minute to wake; preflight retries are bounded.
6. Test a fresh workspace, image upload, saved history, area search, rainfall, market costs and device simulation through the deployed website.

## Free-tier limits

Render's free web service sleeps after inactivity, has limited memory/CPU and can lose photo files when it sleeps/restarts/redeploys. Free Render Postgres expires **30 days after creation**. Its quota may allow only one free database per account. This setup is a temporary competition demo, not durable production storage. Export important records; do not rely on free-host photos as the only copy. Missing photo files return HTTP 410 with an explanation, rather than an internal server error. A hosted-demo notice is shown in the frontend.

Stay on the Free resource plans. No paid resources are selected in the supplied blueprint. If free hosting is not offered for the account, stop and choose an available free option instead of accepting an upgrade. Long-term operation needs durable object storage/database and production identity/security work.

## Current deployment state

Configuration is prepared; deployment is not yet verified. Netlify account authorization and Render account setup are required. Local Docker running on the PC is not a public backend and cannot be used as a permanent Netlify API URL.

References checked 2026-11-17: https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/, https://docs.netlify.com/build/server/get-started/, https://render.com/docs/free, https://render.com/docs/blueprint-spec.
