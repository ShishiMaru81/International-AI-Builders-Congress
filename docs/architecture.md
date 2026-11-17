# Architecture

Next.js 16 App Router + React 19/TypeScript frontend communicates directly with FastAPI `/api/v1`. TanStack Query handles invalidation. Forms use native constraints, React Hook Form and Zod where appropriate. Motion respects reduced-motion preferences. MapLibre uses attributed OpenStreetMap tiles; tiles require network access and there is no flood overlay.

SQLAlchemy supports PostgreSQL (deployment) and SQLite (local/test). Alembic migration 0001 creates users, hashed sessions, owner-scoped domain records and deduplicated sensor events. Domain objects are stored in typed JSON documents with relational owner/kind/plot columns, a deliberate prototype simplification from the specification's nineteen separate tables. Routes validate domain shapes with Pydantic. A future migration can normalize domains without changing their API contracts. Production row-level security and RBAC are not implemented.

User ownership is checked for every record lookup. Images are decoded, verified, pixel-limited, re-encoded without original metadata, and stored with generated filenames outside public assets. Model predictions are immutable case documents; feedback is separate. A synchronous bounded worker-thread route handles screening; production requires a dedicated inference worker and stricter global quotas.

WeatherProvider isolates simulated and live Open-Meteo implementations. The live provider validates coverage and units and never silently falls back to simulation. Source metadata follows each case, weather response, quote and action. Doctor upload, forecast review and market comparisons update plot-level actions. Sensor adapters normalize simulator and ESP32 events into the same persisted schema.

Canonical timestamps use UTC ISO strings; the frontend formats Asia/Dhaka explicitly. Prices and cost calculations use Python Decimal; serialized money uses strings. Wholesale, retail and farm-gate records are filtered separately.
