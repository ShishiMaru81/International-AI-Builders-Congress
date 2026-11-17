"""Backend regressions for B03–B07, B08, B09, B11–B13, FE-C2."""
from datetime import datetime, timezone, timedelta
from tests.conftest import configure_isolated_test_env

configure_isolated_test_env()

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, Session, Record, Reading
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


def _csv(text: str, client):
    return client.post(
        '/api/v1/market/imports',
        files={'file': ('prices.csv', text.encode('utf-8'))},
        data={
            'source_name': 'Private report',
            'source_url': 'https://example.org/report',
            'permission_confirmed': 'true',
        },
    )


def test_csv_extra_cell_and_empty_header_are_controlled(client, session):
    fields = 'market,commodity,price,unit,price_type,grade,observed_at\n'
    extra = _csv(fields + 'Market,tomato,40,BDT/kg,wholesale,A,2026-11-15,unexpected\n', client)
    assert extra.status_code == 200
    body = extra.json()
    assert body['imported'] == 0
    assert body['status'] == 'rejected'
    assert body['errors']
    empty = _csv('', client)
    assert empty.status_code == 200
    assert empty.json()['imported'] == 0 and empty.json()['errors']
    wrong = _csv('not_the_schema\n', client)
    assert wrong.status_code == 200
    assert wrong.json()['imported'] == 0 and wrong.json()['errors']


def test_csv_large_price_rejected_and_dedup_ignores_extra_columns(client, session):
    fields = 'market,commodity,price,unit,price_type,grade,observed_at\n'
    huge = _csv(fields + 'Market,tomato,1e30,BDT/kg,wholesale,A,2026-11-15\n', client).json()
    assert huge['imported'] == 0 and huge['errors']
    first = _csv(fields + 'Repeat market,tomato,40,BDT/kg,wholesale,A,2026-11-15\n', client).json()
    assert first['imported'] == 1
    second = _csv(
        'market,commodity,price,unit,price_type,grade,observed_at,comment\n'
        'Repeat market,tomato,40,BDT/kg,wholesale,A,2026-11-15,hello\n',
        client,
    ).json()
    assert second['imported'] == 0
    assert second['duplicates'] == 1


def test_case_delete_removes_feedback_and_retires_action(client, session):
    from PIL import Image
    import io

    out = io.BytesIO()
    Image.new('RGB', (250, 250), (40, 110, 40)).save(out, 'JPEG')
    case = client.post(
        '/api/v1/doctor/cases',
        data={'plot_id': session['plot_id']},
        files={'image': ('leaf.jpg', out.getvalue(), 'image/jpeg')},
    ).json()
    note = 'Unique private follow-up note XYZ-991'
    client.post(f"/api/v1/doctor/cases/{case['id']}/feedback", json={'note': note, 'request_review': True})
    assert client.delete(f"/api/v1/doctor/cases/{case['id']}").status_code == 200
    exported = client.get('/api/v1/me/export').json()
    feedback_payloads = [
        r['payload'] for r in exported['records'] if r['kind'] == 'feedback'
    ]
    assert all(note not in str(p) for p in feedback_payloads)
    actions = client.get(f"/api/v1/actions?plot_id={session['plot_id']}").json()
    dangling = [
        a for a in actions
        if a.get('source_record_id') == case['id'] and a['status'] == 'open'
    ]
    assert dangling == []


def test_export_includes_preferences_and_sensor_history(client, session):
    client.patch('/api/v1/me', json={'theme': 'dark', 'language': 'bn', 'retraining_consent': True})
    device = client.post('/api/v1/devices', json={'name': 'Probe', 'plot_id': session['plot_id']}).json()
    ts = datetime.now(timezone.utc).isoformat()
    for i in range(3):
        event = dict(
            schema_version='1.0',
            event_id=f'ev-{i}',
            device_id=device['id'],
            plot_id=session['plot_id'],
            timestamp=ts,
            source_type='simulator',
            measurements={'soil_moisture_adc': 2000 + i},
        )
        assert client.post('/api/v1/device/readings', json=event, headers={'X-Device-Key': device['key']}).status_code == 200
    exported = client.get('/api/v1/me/export').json()
    assert exported['schema_version'] == '2.0'
    assert exported['user']['preferences']['theme'] == 'dark'
    assert exported['user']['preferences']['language'] == 'bn'
    assert len(exported['sensor_readings']) >= 3
    assert 'key_hash' not in str(exported)


def test_snoozed_action_not_recreated_by_identical_forecast(client, session):
    plot_id = session['plot_id']
    client.get(f'/api/v1/flood/plots/{plot_id}/outlook')
    actions = client.get(f'/api/v1/actions?plot_id={plot_id}').json()
    flood = next(a for a in actions if a['topic'] == 'flood' and a['status'] == 'open')
    client.patch(f"/api/v1/actions/{flood['id']}", json={'status': 'snoozed', 'comment': 'Until tomorrow', 'snooze_hours': 24})
    before = client.get(f'/api/v1/actions?plot_id={plot_id}').json()
    open_before = [a for a in before if a['topic'] == 'flood' and a['status'] == 'open']
    client.get(f'/api/v1/flood/plots/{plot_id}/outlook')
    after = client.get(f'/api/v1/actions?plot_id={plot_id}').json()
    open_after = [a for a in after if a['topic'] == 'flood' and a['status'] == 'open']
    assert len(open_after) == len(open_before) == 0
    snoozed = [a for a in after if a['topic'] == 'flood' and a['status'] == 'snoozed']
    assert snoozed


def test_compare_without_plot_does_not_contaminate_second_plot(client, session):
    farm = client.get('/api/v1/farms').json()[0]
    second = client.post('/api/v1/plots', json={
        'farm_id': farm['id'],
        'name': 'Tomato plot · B',
        'crop': 'tomato',
        'area_acres': '1.0',
        'stage': 'Vegetative',
        'low_lying': False,
    }).json()
    price = client.get('/api/v1/market/prices').json()[0]
    r = client.post('/api/v1/market/compare', json={
        'price_id': price['id'],
        'harvested_kg': 400,
        'loss_fraction': 0,
        'transport_bdt': 500,
        'handling_bdt': 0,
        'fees_bdt': 0,
    })
    assert r.status_code == 200
    b_actions = client.get(f"/api/v1/actions?plot_id={second['id']}").json()
    market_open = [a for a in b_actions if a['topic'] == 'market' and 'illustrative net' in a.get('reason', '').lower()]
    # Demo seeds a generic market action; ensure no comparison-specific contamination from unscoped compare
    assert not any(price['market'] in a.get('reason', '') for a in b_actions if a['topic'] == 'market')


def test_historical_sensor_does_not_overwrite_current_and_empty_rejected(client, session):
    device = client.post('/api/v1/devices', json={'name': 'ESP', 'plot_id': session['plot_id']}).json()
    key = {'X-Device-Key': device['key']}
    now_ts = datetime.now(timezone.utc).isoformat()
    recent = dict(
        schema_version='1.0',
        event_id='recent-1',
        device_id=device['id'],
        plot_id=session['plot_id'],
        timestamp=now_ts,
        source_type='esp32',
        measurements={'soil_moisture_adc': 2150},
    )
    assert client.post('/api/v1/device/readings', json=recent, headers=key).status_code == 200
    old = dict(
        schema_version='1.0',
        event_id='old-1',
        device_id=device['id'],
        plot_id=session['plot_id'],
        timestamp='2000-01-01T00:00:00+00:00',
        source_type='historical',
        measurements={'soil_moisture_adc': 100},
    )
    old_resp = client.post('/api/v1/device/readings', json=old, headers=key).json()
    assert old_resp['stored_as_historical'] is True
    devices = client.get('/api/v1/devices').json()
    current = devices[0]['last_reading']
    assert current['measurements']['soil_moisture_adc'] == 2150
    invented = dict(recent, event_id='cal-1', calibration_id='invented')
    flags = client.post('/api/v1/device/readings', json=invented, headers=key).json()['quality_flags']
    assert 'uncalibrated' in flags or 'calibration_unverified' in flags
    empty = dict(recent, event_id='empty-1', measurements={})
    assert client.post('/api/v1/device/readings', json=empty, headers=key).status_code == 422


def test_device_revoke_rejects_key(client, session):
    device = client.post('/api/v1/devices', json={'name': 'ESP', 'plot_id': session['plot_id']}).json()
    assert client.delete(f"/api/v1/devices/{device['id']}").status_code == 200
    event = dict(
        schema_version='1.0',
        event_id='after-revoke',
        device_id=device['id'],
        plot_id=session['plot_id'],
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_type='esp32',
        measurements={'soil_moisture_adc': 2100},
    )
    assert client.post('/api/v1/device/readings', json=event, headers={'X-Device-Key': device['key']}).status_code == 401
