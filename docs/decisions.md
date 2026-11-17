# Decisions
The requested application is local software; no Sites hosting is used because a Python/PostgreSQL server does not fit its Worker runtime.
PostgreSQL is the deployment database. SQLite is a supported local/test fallback using the same SQLAlchemy schema.
The environment initially contained no PyTorch, dataset or model weights. An abstaining registry was implemented first. A real three-class MobileNetV3 classifier was subsequently trained and evaluated from official leaf-grouped PlantVillage images; the release artifact now runs locally. No synthetic classifier scores are generated.
Open-Meteo documentation and the PlantVillage dataset card were checked on 2026-11-16. The latter declares CC BY-SA 3.0, but image provenance and grouped splits must still be verified before training. No DAM scraping or unofficial flood feed is assumed.
UI components use accessible native controls with Tailwind/custom tokens, rather than importing a full component generator. Locale dictionaries are shared through a small typed bilingual adapter.

The prototype uses relational ownership/session/event tables and typed JSON domain records rather than nineteen normalized tables. The API remains stable for later normalization. Secondary/help content is currently English even on Bangla routes; this is recorded as partial localization.

Docker uses the explicit project name agrosphere-congress and alternate loopback ports 3100/8100/55432 to preserve the older agrosphere-ai checkout on this PC. Persistent PostgreSQL/image volumes are separate. The Linux inference environment uses the official CPU PyTorch distribution; non-root application users and health checks are enabled.

The first Linux npm install reported real advisories. MapLibre and Vitest were upgraded to patched releases. The linter's typescript-estree dependency required a scoped minimatch 11.0.1 override because its existing version range retained a vulnerable glob implementation. Lint, unit tests, Linux build and Docker browser journeys passed afterward; npm audit is clean. MapLibre's patched ESM release requires a namespace import instead of the previous default import.
