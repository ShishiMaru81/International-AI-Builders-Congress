"""Public-router integration and shared workspace lifecycle for AgroRescue."""
from tests.test_platform import client, session


def example(plot_id):
    return {
        'plot_id': plot_id, 'harvested_kg': '100', 'ready_to_sell': True,
        'cold_storage': False,
        'options': [
            {'label': 'Nearby buyer', 'price_bdt': '40', 'transport_bdt': '100'},
            {'label': 'Distant buyer', 'price_bdt': '45', 'transport_bdt': '800'},
        ],
    }


def test_rescue_route_export_and_plot_lifecycle(client, session):
    r = client.post('/api/v1/rescue/plans', json=example(session['plot_id']))
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan['recommended_option_id'] == 'sell-0'
    assert [x['net_bdt'] for x in plan['options'] if x['kind'] == 'sell_now'] == ['3900.00', '3700.00']
    exported = client.get('/api/v1/me/export').json()
    assert any(x['kind'] == 'rescue_plan' and x['id'] == plan['id'] for x in exported['records'])
    assert client.delete('/api/v1/plots/' + session['plot_id']).status_code == 200
    assert client.get('/api/v1/rescue/plans/' + plan['id']).status_code == 404


def test_rescue_endpoint_requires_session(client):
    assert client.post('/api/v1/rescue/plans', json=example('not-owned')).status_code == 401


def test_failed_live_weather_refresh_is_visible_in_next_plan(client, session, monkeypatch):
    import httpx
    from app.db import Session, Record

    assert client.get('/api/v1/flood/plots/' + session['plot_id'] + '/outlook?mode=DEMO').status_code == 200
    with Session() as db:
        plot = db.get(Record, session['plot_id'])
        farm = db.get(Record, plot.payload['farm_id'])
        farm.payload = {**farm.payload, 'latitude': 24.0, 'longitude': 90.0, 'location_consent': True}
        db.commit()

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError('Forecast service unavailable')

    monkeypatch.setattr('app.services.OpenMeteoProvider.forecast', unavailable)
    assert client.get('/api/v1/flood/plots/' + session['plot_id'] + '/outlook?mode=LIVE').status_code == 503
    result = client.post('/api/v1/rescue/plans', json=example(session['plot_id']))
    assert result.status_code == 200, result.text
    assert 'weather_refresh_failed' in result.json()['warnings']
