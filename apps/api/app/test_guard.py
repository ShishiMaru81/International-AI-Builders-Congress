"""Safe test-database resolution and destructive-DDL protection (MD-01).

Prevents test suites from opening or dropping an application database or any
pre-existing unmarked database when ``TEST_DATABASE_URL`` is supplied.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

TEST_MARKER_TABLE = '_agrosphere_disposable_test_db'
LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '::1', '[::1]'}


def normalize_db_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith('postgres://'):
        return 'postgresql+psycopg://' + value[len('postgres://'):]
    if value.startswith('postgresql://'):
        return 'postgresql+psycopg://' + value[len('postgresql://'):]
    return value


def _canonical_sqlite_path(db_field: str | None, base_dir: Path) -> str:
    if not db_field or db_field == ':memory:' or 'mode=memory' in db_field:
        return ':memory:'
    candidate = Path(db_field)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    resolved = candidate.resolve(strict=False)
    return os.path.normcase(str(resolved))


def canonical_db_identity(raw_url: str, base_dir: Path | None = None) -> tuple:
    """Return a normalized identity tuple for comparing two database targets."""
    anchor = (base_dir or Path.cwd()).resolve()
    u: URL = make_url(normalize_db_url(raw_url))
    backend = u.get_backend_name()
    if backend == 'sqlite':
        if u.query.get('mode') == 'memory':
            return ('sqlite', ':memory:')
        return ('sqlite', _canonical_sqlite_path(u.database, anchor))
    host = (u.host or 'localhost').strip().lower()
    if host in LOOPBACK_HOSTS:
        host = '127.0.0.1'
    port = u.port or (5432 if backend == 'postgresql' else 0)
    dbname = (u.database or '').strip()
    options = u.query.get('options', '')
    schema = u.query.get('currentSchema') or u.query.get('schema') or ''
    if isinstance(options, tuple):
        options = ' '.join(options)
    if 'search_path=' in str(options) and not schema:
        schema = str(options).split('search_path=', 1)[1].split()[0].strip(',')
    return (backend, host, int(port), dbname, str(schema or 'public'))


def _read_dotenv_database_urls(paths: Iterable[Path]) -> list[str]:
    found: list[str] = []
    for env_path in paths:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            key, val = stripped.split('=', 1)
            if key.strip() in ('DATABASE_URL', 'APP_DATABASE_URL'):
                cleaned = val.strip().strip('"').strip("'")
                if cleaned:
                    found.append(cleaned)
    return found


def protected_application_identities(
    explicit_app_urls: Iterable[str] = (),
    api_dir: Path | None = None,
) -> set[tuple]:
    """Collect canonical identities of application databases that tests must never touch."""
    api_root = (api_dir or Path(__file__).resolve().parents[1]).resolve()
    repo_root = api_root.parent.parent
    protected: set[tuple] = set()

    # Default local SQLite locations relative to apps/api and repo root
    for base in (api_root, repo_root, Path.cwd().resolve()):
        protected.add(canonical_db_identity('sqlite:///./agrosphere.db', base))

    # Default Docker Compose PostgreSQL databases (never treat main app DB as test target)
    protected.add(('postgresql', '127.0.0.1', 55432, 'agrosphere', 'public'))
    protected.add(('postgresql', '127.0.0.1', 5432, 'agrosphere', 'public'))
    protected.add(('postgresql', 'db', 5432, 'agrosphere', 'public'))

    dotenv_urls = _read_dotenv_database_urls([
        api_root / '.env',
        repo_root / '.env',
    ])
    for raw in [*explicit_app_urls, *dotenv_urls]:
        if not raw:
            continue
        for base in (Path.cwd().resolve(), api_root, repo_root):
            protected.add(canonical_db_identity(raw, base))
    return protected


def validate_test_database_url(
    test_url: str,
    *,
    app_urls: Iterable[str] = (),
    api_dir: Path | None = None,
) -> str:
    """Validate ``test_url`` before engine creation; raise RuntimeError if unsafe."""
    if not test_url or not test_url.strip():
        raise RuntimeError('Refusing empty TEST_DATABASE_URL.')
    normalized = normalize_db_url(test_url)
    api_root = (api_dir or Path(__file__).resolve().parents[1]).resolve()
    repo_root = api_root.parent.parent

    candidate_identities = {
        canonical_db_identity(normalized, Path.cwd().resolve()),
        canonical_db_identity(normalized, api_root),
    }
    protected = protected_application_identities(app_urls, api_dir=api_root)

    overlap = candidate_identities & protected
    if overlap:
        raise RuntimeError(
            f'Refusing destructive test setup: TEST_DATABASE_URL resolves to protected '
            f'application database identity {sorted(overlap)[0]!r}. '
            f'Supply a dedicated empty test database (for example a temporary SQLite file '
            f'or a separate disposable PostgreSQL database/schema).'
        )

    u = make_url(normalized)
    backend = u.get_backend_name()
    if backend == 'sqlite':
        ident = canonical_db_identity(normalized, Path.cwd().resolve())
        if ident[1] != ':memory:':
            db_path = Path(ident[1])
            # Also check os.path.samefile against any existing app SQLite file for symlinks/junctions
            for prot in protected:
                if prot[0] == 'sqlite' and prot[1] != ':memory:':
                    prot_path = Path(prot[1])
                    if db_path.exists() and prot_path.exists():
                        try:
                            if os.path.samefile(db_path, prot_path):
                                raise RuntimeError(
                                    f'Refusing destructive test setup: {db_path} points to the same '
                                    f'underlying file as protected database {prot_path}.'
                                )
                        except OSError:
                            pass
    elif backend == 'postgresql':
        dbname = (u.database or '').strip()
        if not dbname:
            raise RuntimeError('Refusing PostgreSQL TEST_DATABASE_URL without an explicit database name.')
    else:
        raise RuntimeError(f'Unsupported test database backend {backend!r}; expected sqlite or postgresql.')

    return normalized


def ensure_disposable_schema_before_reset(engine) -> None:
    """Verify target has no unmarked pre-existing tables before running drop_all().

    An empty database receives ``_agrosphere_disposable_test_db`` so subsequent
    test resets in the same disposable database succeed, while any pre-populated
    application/user database lacking the marker is rejected before any DDL.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        with engine.begin() as conn:
            conn.execute(text(
                f'CREATE TABLE IF NOT EXISTS {TEST_MARKER_TABLE} '
                f'(created_by VARCHAR(64) NOT NULL)'
            ))
            conn.execute(
                text(f'INSERT INTO {TEST_MARKER_TABLE} (created_by) VALUES (:v)'),
                {'v': 'agrosphere-pytest'},
            )
        return

    if TEST_MARKER_TABLE not in existing_tables:
        raise RuntimeError(
            f'Refusing destructive drop_all() on pre-existing database without '
            f'{TEST_MARKER_TABLE} marker. Found tables: {sorted(existing_tables)}. '
            f'Point TEST_DATABASE_URL at a fresh disposable database instead.'
        )


def safe_reset_test_metadata(engine, metadata) -> None:
    """Safely reset ORM tables while preserving the disposable-test marker table."""
    ensure_disposable_schema_before_reset(engine)
    metadata.drop_all(engine)
    metadata.create_all(engine)
