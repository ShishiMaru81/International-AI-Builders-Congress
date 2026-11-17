"""Phase 1 preference/location regressions (B14, B01, FE-05 server side)."""
from tests.conftest import configure_isolated_test_env

configure_isolated_test_env()

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine
from app.test_guard import safe_reset_test_metadata
import pytest


@pytest.fixture
def client():
    safe_reset_test_metadata(engine, Base.metadata)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session(client):
    result = client.post('/api/v1/auth/demo', json={}).json()
    client.headers['Authorization'] = 'Bearer ' + result['token']
    return result


def test_preferences_partial_patch_preserves_unrelated_fields(client, session):
    full = client.patch('/api/v1/me', json={
        'language': 'bn',
        'theme': 'light',
        'retraining_consent': True,
    }).json()
    assert full['language'] == 'bn'
    assert full['retraining_consent'] is True
    me = client.get('/api/v1/me').json()
    assert me['preferences']['language'] == 'bn'
    assert me['preferences']['retraining_consent'] is True
    patched = client.patch('/api/v1/me', json={'theme': 'dark'}).json()
    assert patched['theme'] == 'dark'
    assert patched['language'] == 'bn'
    assert patched['retraining_consent'] is True


def test_farm_name_only_patch_keeps_coordinates(client, session):
    farm = client.get('/api/v1/farms').json()[0]
    located = client.patch(f"/api/v1/farms/{farm['id']}/location", json={
        'latitude': 24.0,
        'longitude': 90.0,
        'location_consent': True,
        'location_name': 'Gazipur test point',
        'district': 'Gazipur',
        'country': 'Bangladesh',
    }).json()
    assert located['latitude'] == 24.0
    renamed = client.patch(f"/api/v1/farms/{farm['id']}", json={'name': 'Renamed Farm'}).json()
    assert renamed['name'] == 'Renamed Farm'
    assert renamed['latitude'] == 24.0
    assert renamed['longitude'] == 90.0
    assert renamed['location_consent'] is True


def test_generic_farm_coordinate_patch_invalidates_weather(client, session):
    farm = client.get('/api/v1/farms').json()[0]
    plot_id = session['plot_id']
    client.patch(f"/api/v1/farms/{farm['id']}/location", json={
        'latitude': 24.0,
        'longitude': 90.0,
        'location_consent': True,
        'location_name': 'Point A',
        'district': 'Gazipur',
        'country': 'Bangladesh',
    })
    outlook = client.get(f'/api/v1/flood/plots/{plot_id}/outlook').json()
    assert outlook['is_flood_probability'] is False
    center_before = client.get(f'/api/v1/plots/{plot_id}/action-center').json()
    assert center_before['evidence']['weather']
    client.patch(f"/api/v1/farms/{farm['id']}", json={
        'latitude': 25.0,
        'longitude': 91.0,
        'location_consent': True,
        'location_name': 'Point B',
        'district': 'Sylhet',
    })
    center_after = client.get(f'/api/v1/plots/{plot_id}/action-center').json()
    assert center_after['evidence']['weather'] == []
    flood_actions = [a for a in center_after['actions'] if a['topic'] == 'flood' and a['status'] == 'open']
    assert any('Refresh weather' in a['title'] or 'location' in a['reason'].lower() or 'Refresh' in a['title'] for a in flood_actions)
