"""Marketplace identity contracts exercised without the main application."""
import hashlib
import importlib
import importlib.util
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.db import Base, Token, User, ensure_compat_schema, get_db


@pytest.fixture
def auth(tmp_path):
    # A missing auth router is a missing feature, not a collection failure.
    spec = importlib.util.find_spec('app.market_auth')
    assert spec is not None, 'Marketplace auth router must exist'
    module = importlib.import_module('app.market_auth')
    identity = importlib.import_module('app.identity')
    engine = create_engine('sqlite:///' + str(tmp_path / 'auth.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    application = FastAPI()
    application.include_router(module.router)
    def database():
        with sessions() as db:
            yield db
    application.dependency_overrides[get_db] = database
    @application.get('/private')
    def private(user=Depends(identity.require_user)):
        return identity.user_view(user)
    @application.get('/optional')
    def optional(user=Depends(identity.optional_user)):
        return identity.user_view(user) if user else None
    with TestClient(application) as client:
        yield client, sessions
    engine.dispose()


def register(client, **changes):
    return client.post('/api/v1/auth/register', json={
        'name': 'Test Farmer', 'email': 'farmer@example.com',
        'password': 'strong-password-42', 'role': 'farmer', **changes,
    })


def test_signup_login_hashes_password_and_returns_safe_identity(auth):
    client, sessions = auth
    result = register(client, email=' Farmer@Example.COM ')
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['user']['email'] == 'farmer@example.com'
    assert body['user']['role'] == 'farmer'
    assert body['user']['is_active'] is True
    assert set(body['user']) == {'id', 'name', 'email', 'role', 'preferences', 'is_active'}
    with sessions() as db:
        user = db.get(User, body['user']['id'])
        assert user.password_hash.startswith('scrypt$')
        assert 'strong-password-42' not in user.password_hash
        assert db.get(Token, body['token']) is None
        assert db.get(Token, hashlib.sha256(body['token'].encode()).hexdigest()) is not None
    logged_in = client.post('/api/v1/auth/login', json={'email': 'FARMER@example.com', 'password': 'strong-password-42'})
    assert logged_in.status_code == 200
    assert logged_in.json()['user']['id'] == body['user']['id']
    assert client.get('/private', headers={'Authorization': 'Bearer ' + body['token']}).status_code == 200
    assert client.get('/optional').json() is None
    assert client.get('/optional', headers={'Authorization': 'Bearer forged'}).status_code == 401


@pytest.mark.parametrize('role', ['admin', 'superuser', '', None])
def test_public_signup_cannot_escalate_role(auth, role):
    client, sessions = auth
    assert register(client, role=role).status_code == 422
    with sessions() as db:
        assert list(db.scalars(select(User))) == []


def test_signup_rejects_extra_privilege_fields_and_weak_password(auth):
    client, _ = auth
    assert register(client, is_active=True).status_code == 422
    assert register(client, password='short').status_code == 422
    assert register(client, email='invalid').status_code == 422
    assert register(client, name='   ').status_code == 422


def test_duplicate_email_is_case_insensitive_and_customer_can_register(auth):
    client, _ = auth
    assert register(client, role='customer').json()['user']['role'] == 'customer'
    assert register(client, email='FARMER@EXAMPLE.COM').status_code == 409


def test_invalid_password_inactive_and_expired_tokens_fail(auth):
    client, sessions = auth
    body = register(client).json()
    for email, password in [('farmer@example.com', 'wrong-password'), ('missing@example.com', 'strong-password-42')]:
        assert client.post('/api/v1/auth/login', json={'email': email, 'password': password}).status_code == 401
    headers = {'Authorization': 'Bearer ' + body['token']}
    with sessions() as db:
        user = db.get(User, body['user']['id'])
        user.is_active = False
        db.commit()
    assert client.get('/private', headers=headers).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'farmer@example.com', 'password': 'strong-password-42'}).status_code == 401
    with sessions() as db:
        db.get(User, body['user']['id']).is_active = True
        token = db.get(Token, hashlib.sha256(body['token'].encode()).hexdigest())
        token.expires = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()
    assert client.get('/private', headers=headers).status_code == 401


def test_auth_attempts_are_rate_limited(auth):
    client, _ = auth
    responses = [client.post('/api/v1/auth/login', json={'email': 'missing@example.com', 'password': 'wrong-password'}) for _ in range(20)]
    assert responses[0].status_code == 401
    assert responses[-1].status_code == 429
    assert int(responses[-1].headers['Retry-After']) > 0


def test_concurrent_signup_has_one_unique_identity(auth):
    client, sessions = auth
    with ThreadPoolExecutor(max_workers=6) as workers:
        responses = list(workers.map(lambda _: register(client), range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]
    with sessions() as db:
        assert len(list(db.scalars(select(User)))) == 1
        assert len(list(db.scalars(select(Token)))) == 1


def test_operator_admin_creation_has_no_public_equivalent(auth):
    client, sessions = auth
    admin = importlib.import_module('app.market_admin')
    with sessions() as db:
        user = admin.create_admin(db, email='ADMIN@example.com', name='Operator', password='operator-secure-42')
        assert user.role == 'admin'
        assert user.email == 'admin@example.com'
        assert user.password_hash.startswith('scrypt$')
        with pytest.raises(ValueError):
            admin.create_admin(db, email='admin@example.com', name='Operator', password='operator-secure-42')
    login = client.post('/api/v1/auth/login', json={'email': 'admin@example.com', 'password': 'operator-secure-42'})
    assert login.status_code == 200
    assert login.json()['user']['role'] == 'admin'
    assert 'password_hash' not in login.json()['user']


def test_operator_cli_uses_environment_password_without_echoing_it(tmp_path):
    database = tmp_path / 'cli.db'
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database),
           'KRISHIMARKET_ADMIN_PASSWORD': 'private-operator-secret-123'}
    api_dir = Path(__file__).resolve().parents[1]
    command = [sys.executable, '-m', 'app.market_admin', 'create-admin', '--email', 'operator@example.com', '--name', 'Operator']
    first = subprocess.run(command, cwd=api_dir, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert 'private-operator-secret-123' not in first.stdout + first.stderr
    second = subprocess.run(command, cwd=api_dir, env=env, capture_output=True, text=True)
    assert second.returncode != 0
    engine = create_engine(env['DATABASE_URL'])
    with engine.connect() as db:
        assert db.execute(text('SELECT email,role FROM users')).all() == [('operator@example.com', 'admin')]
    engine.dispose()


@pytest.mark.parametrize('use_compat', [False, True])
def test_legacy_compat_and_migrations_preserve_existing_rows(tmp_path, use_compat):
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    def upgrade(revision):
        path = next(versions.glob(revision + '_*.py'))
        spec = importlib.util.spec_from_file_location('migration_' + revision, path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
    upgrade('0001')
    with engine.begin() as db:
        db.execute(text("INSERT INTO users VALUES ('legacy', 'Existing farmer', '{}')"))
        db.execute(text("INSERT INTO records (id,owner_id,kind,plot_id,created_at,payload) VALUES ('farm','legacy','farm',NULL,'2026-01-01','{}')"))
    if use_compat:
        ensure_compat_schema(engine)
        ensure_compat_schema(engine)
    upgrade('0002')
    upgrade('0003')
    # Compat startup after the formal upgrade is also a harmless operation.
    ensure_compat_schema(engine)
    with engine.connect() as db:
        assert {'email', 'password_hash', 'role', 'is_active'} <= {c['name'] for c in inspect(db).get_columns('users')}
        assert db.execute(text("SELECT name, role, is_active FROM users WHERE id='legacy'")).one() == ('Existing farmer', 'farmer', 1)
        assert db.execute(text('SELECT COUNT(*) FROM records')).scalar() == 1
        assert db.execute(text("SELECT role FROM users WHERE id='legacy'")).scalar() == 'farmer'
    engine.dispose()
