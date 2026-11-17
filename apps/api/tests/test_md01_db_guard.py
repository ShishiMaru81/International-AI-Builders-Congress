"""MD-01 regressions: test suite must never drop an application or unmarked DB."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

from app.test_guard import (
    canonical_db_identity,
    ensure_disposable_schema_before_reset,
    validate_test_database_url,
)
from sqlalchemy import create_engine

API_DIR = Path(__file__).resolve().parents[1]


def _create_sentinel_sqlite(db_file: Path) -> None:
    with sqlite3.connect(db_file) as conn:
        conn.execute('CREATE TABLE sentinel_do_not_drop (id INTEGER PRIMARY KEY, secret TEXT NOT NULL)')
        conn.execute("INSERT INTO sentinel_do_not_drop (id, secret) VALUES (1, 'preserve-real-data')")
        conn.execute('CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, preferences TEXT NOT NULL)')
        conn.execute("INSERT INTO users (id, name, preferences) VALUES ('u_real', 'Real Farmer', '{}')")
        conn.commit()


def _assert_sentinel_intact(db_file: Path) -> None:
    with sqlite3.connect(db_file) as conn:
        sentinel = conn.execute('SELECT id, secret FROM sentinel_do_not_drop').fetchall()
        users = conn.execute('SELECT id, name FROM users').fetchall()
    assert sentinel == [(1, 'preserve-real-data')]
    assert users == [('u_real', 'Real Farmer')]


def test_canonical_identity_detects_equivalent_postgres_and_sqlite_targets(tmp_path: Path):
    # Equivalent PostgreSQL loopback forms match despite different drivers/hosts/query strings
    p1 = canonical_db_identity('postgres://agrosphere:pw@localhost:5432/agrosphere')
    p2 = canonical_db_identity('postgresql+psycopg://agrosphere:pw@127.0.0.1/agrosphere')
    assert p1 == p2

    with pytest.raises(RuntimeError, match='protected application database'):
        validate_test_database_url(
            'postgresql+psycopg://agrosphere:pw@127.0.0.1:5432/agrosphere',
            app_urls=['postgres://agrosphere:pw@localhost:5432/agrosphere'],
            api_dir=API_DIR,
        )

    # Distinct disposable PostgreSQL database is allowed by URL check
    accepted = validate_test_database_url(
        'postgresql+psycopg://agrosphere:pw@127.0.0.1:5432/agrosphere_disposable_ci',
        app_urls=['postgres://agrosphere:pw@localhost:5432/agrosphere'],
        api_dir=API_DIR,
    )
    assert accepted.endswith('/agrosphere_disposable_ci')

    # Substring 'test' in a real application DB name does NOT bypass protection
    contest_db = tmp_path / 'contest_test_production.db'
    contest_url = 'sqlite:///' + str(contest_db).replace('\\', '/')
    with pytest.raises(RuntimeError, match='protected application database'):
        validate_test_database_url(
            contest_url,
            app_urls=[contest_url],
            api_dir=API_DIR,
        )


def test_subprocess_rejects_application_database_before_ddl_and_preserves_sentinel(tmp_path: Path):
    sentinel_db = tmp_path / 'farmer_contest_app.db'
    _create_sentinel_sqlite(sentinel_db)

    # Pass relative/alternate form in TEST_DATABASE_URL vs absolute in DATABASE_URL
    abs_url = 'sqlite:///' + str(sentinel_db.resolve()).replace('\\', '/')
    alt_url = 'sqlite:///' + str((tmp_path / '.' / 'farmer_contest_app.db')).replace('\\', '/')

    env = {
        **os.environ,
        'DATABASE_URL': abs_url,
        'TEST_DATABASE_URL': alt_url,
    }
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_platform.py', '-k', 'test_private_sessions_and_farms', '-q'],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode != 0
    combined = proc.stdout + '\n' + proc.stderr
    assert 'Refusing destructive test setup' in combined
    _assert_sentinel_intact(sentinel_db)


def test_preexisting_unmarked_database_is_refused_even_without_app_url_match(tmp_path: Path):
    unmarked_db = tmp_path / 'existing_user_data.db'
    _create_sentinel_sqlite(unmarked_db)
    unmarked_url = 'sqlite:///' + str(unmarked_db).replace('\\', '/')

    eng = create_engine(unmarked_url)
    try:
        with pytest.raises(RuntimeError, match='Refusing destructive drop_all'):
            ensure_disposable_schema_before_reset(eng)
    finally:
        eng.dispose()
    _assert_sentinel_intact(unmarked_db)
