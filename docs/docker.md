# Verified local Docker setup

This checkout runs as **agrosphere-congress**, preserving the older **agrosphere-ai** project from `D:/bracu mail/Ai contest 2026`. Its volumes and containers are separate.

Start from this checkout: `docker compose up -d --build`. Open http://127.0.0.1:3100. API reference: http://127.0.0.1:8100/docs. PostgreSQL is bound to 127.0.0.1:55432. All bindings are loopback only.

The Dockerfiles exclude host node_modules, build output, SQLite databases, private local storage and env files from build contexts. The Linux API installs the pinned CPU PyTorch build from its official index, mounts approved model artifacts read-only, applies Alembic migrations and runs as a non-root user. Next.js is packaged with its standalone server and static assets, also running as a non-root user.

Verification on this PC:

- Fresh PostgreSQL initialization and Alembic upgrade succeed; `docker compose exec -T api python -m alembic check` finds no drift.
- Ten backend integration tests pass inside Linux against a dedicated `agrosphere_test` PostgreSQL database. The test suite accepts TEST_DATABASE_URL; it never drops the application database.
- `scripts/docker_verify.py` exercises real image inference, synthetic rain, decimal market comparisons and authenticated virtual-device ingestion. It restarts only this API and verifies that sessions, cases, private images, sensor readings and deduplication persist. It removes its disposable workspace afterward. Results are retained in `docs/docker-verification.json`.
- The Docker website uses its built API address, port 8100, and matching CORS origins. Browser tests can target it through PLAYWRIGHT_BASE_URL and AGROSPHERE_API_URL.

Existing local SQLite workspaces remain in their original database. Docker starts a separate PostgreSQL workspace; it does not migrate or delete the SQLite records. Demo sessions are also scoped by browser origin (port 3100 versus 3000).

Useful checks: `docker compose ps`, `docker compose logs --tail 50 api`, `docker compose logs --tail 50 web`. Stop using `docker compose stop`; restart using `docker compose start`. Do not remove named volumes unless you intend to erase data.

This local container verification does not constitute a production security audit or field validation of the disease model.
