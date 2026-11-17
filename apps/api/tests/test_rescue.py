"""AgroRescue decision and privacy regressions, using isolated shared Records."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import Record, Session
from tests.test_platform import client, session

API = '/api/v1/rescue/plans'


def request_body(session, **overrides):
    body = dict(plot_id=session['plot_id'], harvested_kg='100', ready_to_sell=True,
                cold_storage=False, options=[
                    dict(label='Local quote', price_bdt='42', transport_bdt='300'),
                    dict(label='Distant quote', price_bdt='46', transport_bdt='900'),
                ])
    body.update(overrides)
    return body


def save(client, session, **overrides):
    response = client.post(API, json=request_body(session, **overrides))
    assert response.status_code == 200, response.text
    return response.json()


def record(session, kind, payload, *, plot_id=True):
    with Session() as db:
        row = Record(owner_id=session['user_id'], kind=kind,
                     plot_id=session['plot_id'] if plot_id else None, payload=payload)
        db.add(row)
        db.commit()
        return row.id


def price(session, **changes):
    return record(session, 'price', dict(commodity='tomato', price='42.00',
                  unit='BDT/kg', price_type='wholesale', grade='A',
                  observed_at=datetime.now(timezone.utc).date().isoformat(),
                  meta={'mode': 'LIVE', 'source_name': 'Farmer import', 'is_simulated': False},
                  **changes), plot_id=False)


def test_money_recommendation_and_immutable_saved_snapshot(client, session):
    plan = save(client, session)
    assert plan['status'] == 'ready'
    assert plan['recommended_option_id'] == 'sell-0'
    assert [x['net_bdt'] for x in plan['options']] == ['3900.00', '3700.00']
    assert plan['method'] == 'symbolic_constraint_planner_v1'
    assert plan['assumptions']['harvested_kg'] == '100'
    assert client.get(API + '/' + plan['id']).json()['snapshot_notice']
    assert client.get(API + '?plot_id=' + session['plot_id']).json()[0]['id'] == plan['id']
    assert client.patch(API + '/' + plan['id'], json={}).status_code == 405


def test_unknown_transport_does_not_silently_become_zero_or_allow_winner(client, session):
    plan = save(client, session, options=[
        dict(label='Known', price_bdt='42', transport_bdt='300'),
        dict(label='Unknown', price_bdt='46', transport_bdt=None)])
    assert plan['status'] == 'needs_information'
    assert plan['recommended_option_id'] is None
    assert plan['options'][1]['net_bdt'] is None
    assert 'transport_unknown' in plan['options'][1]['reasons']
    assert any(q['code'] == 'transport_sell-1' for q in plan['questions'])
    question = next(q for q in plan['questions'] if q['code'] == 'transport_sell-1')
    assert question['break_even_transport_bdt'] == '700.00'


def test_demo_scenario_stays_visible_for_entered_quotes(client, session):
    plan = save(client, session, scenario_mode='DEMO')
    assert 'demo_scenario' in plan['warnings']
    assert plan['options'][0]['meta']['is_simulated'] is True
    assert plan['assumptions']['scenario_mode'] == 'DEMO'


@pytest.mark.parametrize('ready', [None, False])
def test_readiness_blocks_selling_advice(client, session, ready):
    body = request_body(session)
    body['ready_to_sell'] = ready
    result = client.post(API, json=body).json()
    assert result['recommended_option_id'] is None
    assert not any(x['feasible'] for x in result['options'])
    assert result['status'] == ('needs_information' if ready is None else 'no_feasible_option')


def test_tie_and_negative_results_do_not_give_positive_recommendations(client, session):
    tied = save(client, session, options=[dict(label='A', price_bdt='40', transport_bdt='100'),
                                        dict(label='B', price_bdt='40', transport_bdt='100')])
    assert tied['recommended_option_id'] is None
    assert 'equal_net_options' in tied['warnings']
    negative = save(client, session, options=[dict(label='A', price_bdt='1', transport_bdt='200')])
    assert negative['status'] == 'no_feasible_option'
    assert negative['recommended_option_id'] is None
    assert negative['options'][0]['net_bdt'] == '-100.00'


def test_hold_is_explicit_hypothetical_and_cannot_replace_sell_now(client, session):
    body = request_body(session, hold_price_bdt='100', hold_loss_pct='10', storage_cost_bdt='300')
    body['cold_storage'] = True
    response = client.post(API, json=body)
    assert response.status_code == 200, response.text
    plan = response.json()
    hold = plan['options'][-1]
    assert hold['id'] == 'hold' and hold['kind'] == 'hold'
    assert hold['net_bdt'] == '8700.00'
    assert hold['saleable_kg'] == '90.000'
    assert hold['meta']['is_hypothetical'] is True
    assert hold['meta']['cost_scope'] == 'total_holding_and_later_selling_costs'
    assert plan['recommended_option_id'] == 'sell-0'


def test_hold_does_not_infer_loss_or_storage_cost(client, session):
    plan = save(client, session, hold_price_bdt='100')
    hold = plan['options'][-1]
    assert hold['net_bdt'] is None and not hold['feasible']
    assert {'hold_loss_unknown', 'storage_cost_unknown', 'storage_not_confirmed'} <= set(hold['reasons'])


@pytest.mark.parametrize('patch', [
    {'harvested_kg': 'NaN'}, {'harvested_kg': 'Infinity'}, {'harvested_kg': '0'},
    {'harvested_kg': '1000001'}, {'unexpected': 1}, {'ready_to_sell': 'yes'},
    {'hold_loss_pct': '101'}, {'storage_cost_bdt': '-1'},
    {'options': []}, {'options': [dict(label='A', price_bdt='1', price_id='also')]},
    {'options': [dict(label='A', price_bdt='-1')]},
    {'options': [dict(label='A', price_bdt='1', handling_bdt=None)]},
    {'options': [dict(label='A', price_bdt='1', transport_bdt='Infinity')]},
])
def test_bounded_finite_and_unambiguous_inputs(client, session, patch):
    body = request_body(session)
    body.update(patch)
    assert client.post(API, json=body).status_code == 422


def test_requires_session_owned_plot_and_owned_prices(client, session):
    assert client.post(API, json=request_body(session), headers={'Authorization': ''}).status_code == 401
    foreign = client.post('/api/v1/auth/demo', json={}).json()
    body = request_body(session)
    body['plot_id'] = foreign['plot_id']
    assert client.post(API, json=body).status_code == 404
    foreign_prices = client.get('/api/v1/market/prices', headers={'Authorization': 'Bearer ' + foreign['token']}).json()
    # Existing private price endpoint wraps items in a paginated response.
    foreign_prices = foreign_prices.get('items', []) if isinstance(foreign_prices, dict) else foreign_prices
    body = request_body(session, options=[dict(label='Foreign', price_id=foreign_prices[0]['id'], transport_bdt='0')])
    assert client.post(API, json=body).status_code == 404
    plan = save(client, session)
    headers = {'Authorization': 'Bearer ' + foreign['token']}
    assert client.get(API + '/' + plan['id'], headers=headers).status_code == 404
    assert client.delete(API + '/' + plan['id'], headers=headers).status_code == 404
    assert client.get(API + '?plot_id=' + session['plot_id'], headers=headers).status_code == 404


@pytest.mark.parametrize('changes', [{'commodity': 'rice'}, {'unit': 'BDT/maund'}])
def test_stored_quote_crop_and_unit_must_match(client, session, changes):
    values = dict(commodity='tomato', price='42', unit='BDT/kg', price_type='wholesale',
                  grade='A', observed_at='2026-11-17', meta={})
    values.update(changes)
    pid = record(session, 'price', values, plot_id=False)
    assert client.post(API, json=request_body(session, options=[dict(label='Quote', price_id=pid, transport_bdt='0')])).status_code == 422


@pytest.mark.parametrize('field,value', [('price_type', 'retail'), ('grade', 'B')])
def test_mixed_price_type_or_grade_is_rejected(client, session, field, value):
    a = price(session)
    with Session() as db:
        row = db.get(Record, a)
        payload = {**row.payload, field: value}
    b = record(session, 'price', payload, plot_id=False)
    options = [dict(label='A', price_id=a, transport_bdt='0'), dict(label='B', price_id=b, transport_bdt='0')]
    assert client.post(API, json=request_body(session, options=options)).status_code == 422


@pytest.mark.parametrize('observed', ['2000-01-01', '2999-01-01', None, 'invalid',
                                       datetime.now(timezone.utc).date().isoformat() + 'invalid'])
def test_old_future_and_unknown_quotes_require_confirmation_even_if_demo(client, session, observed):
    values = dict(commodity='tomato', price='42', unit='BDT/kg', price_type='wholesale',
                  grade='A', observed_at=observed,
                  meta={'mode': 'DEMO', 'is_simulated': True, 'source_name': 'Synthetic fixture'})
    pid = record(session, 'price', values, plot_id=False)
    option = dict(label='A', price_id=pid, transport_bdt='0')
    plan = save(client, session, options=[option])
    assert plan['status'] == 'needs_information' and plan['recommended_option_id'] is None
    assert 'simulated_price' in plan['warnings']
    confirmed = save(client, session, options=[{**option, 'confirmed': True}])
    assert confirmed['status'] == 'ready' and confirmed['recommended_option_id'] == 'sell-0'
    assert confirmed['options'][0]['meta']['is_simulated'] is True


def test_saved_weather_and_uncertain_case_have_visible_limits_no_live_fetch(client, session, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Planner must not fetch live weather')
    monkeypatch.setattr('app.services.OpenMeteoProvider.forecast', forbidden)
    record(session, 'weather', dict(level='low', total_mm=0, horizon_hours=48, hourly=[],
           valid_until=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
           last_refresh_failed_at=datetime.now(timezone.utc).isoformat(),
           meta={'mode': 'DEMO', 'is_simulated': True, 'source_name': 'Fixture'}))
    cid = record(session, 'case', dict(classification={'abstained': True, 'top_label': 'unknown'},
                 status='uncertain', meta={'mode': 'DEMO', 'is_simulated': True}))
    plan = save(client, session)
    assert {'weather_expired', 'weather_refresh_failed', 'simulated_weather', 'inspect_crop_first'} <= set(plan['warnings'])
    assert plan['evidence']['weather']['meta']['freshness'] == 'expired'
    assert plan['evidence']['case']['id'] == cid


def test_missing_weather_is_unknown_and_foreign_case_never_attached(client, session):
    foreign = client.post('/api/v1/auth/demo', json={}).json()
    record(foreign, 'case', {'classification': {'top_label': 'unknown'}})
    plan = save(client, session)
    assert plan['evidence'] == {'weather': None, 'case': None}
    assert 'weather_missing' in plan['warnings']


def test_plan_history_action_replacement_export_delete_and_plot_cascade(client, session):
    first = save(client, session)
    second = save(client, session)
    actions = client.get('/api/v1/actions?plot_id=' + session['plot_id']).json()
    rescue = [a for a in actions if a['topic'] == 'rescue' and a['status'] == 'open']
    assert len(rescue) == 1 and rescue[0]['source_record_id'] == second['id']
    export = client.get('/api/v1/me/export').json()
    assert any(r['id'] == first['id'] and r['kind'] == 'rescue_plan' for r in export['records'])
    assert client.delete(API + '/' + second['id']).status_code == 200
    assert client.get(API + '/' + second['id']).status_code == 404
    assert not [a for a in client.get('/api/v1/actions').json() if a['source_record_id'] == second['id']]
    assert client.delete('/api/v1/plots/' + session['plot_id']).status_code == 200
    with Session() as db:
        assert not list(db.scalars(select(Record).where(Record.kind == 'rescue_plan')))


def test_fractional_quantity_uses_decimal_rounding(client, session):
    plan = save(client, session, harvested_kg='0.125', options=[dict(label='A', price_bdt='10.20', transport_bdt='0')])
    assert plan['options'][0]['gross_bdt'] == '1.28'
    assert plan['options'][0]['net_bdt'] == '1.28'


def test_snapshot_excludes_private_case_material_and_does_not_refresh_sources(client, session):
    cid = record(session, 'case', dict(classification={'top_label': 'unknown', 'abstained': True},
                 image_file='private.jpg', symptoms='Private field note', notes='Private notes',
                 meta={'mode': 'LIVE', 'source_name': 'Research model', 'is_simulated': False}))
    plan = save(client, session)
    evidence = plan['evidence']['case']
    assert evidence['id'] == cid
    assert 'image_file' not in evidence and 'symptoms' not in evidence and 'notes' not in evidence
    with Session() as db:
        row = db.get(Record, cid)
        row.payload = {**row.payload, 'classification': {'top_label': 'healthy', 'abstained': False}}
        db.commit()
    saved = client.get(API + '/' + plan['id']).json()
    assert saved['evidence']['case']['classification']['top_label'] == 'unknown'


def test_live_weather_without_retrieval_and_validity_is_unknown(client, session):
    record(session, 'weather', dict(level='low', total_mm=0, hourly=[],
           meta={'mode': 'LIVE', 'is_simulated': False, 'source_name': 'Missing timestamp'}))
    plan = save(client, session)
    assert 'weather_unknown' in plan['warnings']
    assert plan['evidence']['weather']['meta']['freshness'] == 'unknown'


def test_history_is_limited_to_latest_twenty_and_account_deletion_removes_plans(client, session):
    plan = save(client, session)
    with Session() as db:
        for day in range(1, 23):
            db.add(Record(owner_id=session['user_id'], kind='rescue_plan', plot_id=session['plot_id'],
                          created_at=f'2000-01-{day:02d}T00:00:00+00:00', payload=plan))
        db.commit()
    history = client.get(API + '?plot_id=' + session['plot_id']).json()
    assert len(history) == 20
    assert history[0]['id'] == plan['id']
    assert history[-1]['created_at'] == '2000-01-04T00:00:00+00:00'
    assert client.delete('/api/v1/me').status_code == 200
    with Session() as db:
        assert not list(db.scalars(select(Record).where(Record.kind == 'rescue_plan')))


def test_hold_saleable_quantity_retains_declared_loss_precision(client, session):
    body = request_body(session, harvested_kg='1', hold_price_bdt='100', hold_loss_pct='0.01', storage_cost_bdt='0')
    body['cold_storage'] = True
    result = client.post(API, json=body).json()['options'][-1]
    assert Decimal(result['saleable_kg']) == Decimal('0.9999')
    assert result['gross_bdt'] == '99.99'


@pytest.mark.parametrize('price,transport,gross,net', [('0.01', '0', '0.00', '0.00'),
                                                     ('5', '0.01', '0.01', '0.00')])
def test_cent_rounding_balances_visible_formula_and_zero_net_is_not_recommended(client, session, price, transport, gross, net):
    plan = save(client, session, harvested_kg='0.001', options=[dict(label='A', price_bdt=price, transport_bdt=transport)])
    option = plan['options'][0]
    assert option['gross_bdt'] == gross and option['net_bdt'] == net
    assert Decimal(option['gross_bdt']) - Decimal(option['costs_bdt']) == Decimal(option['net_bdt'])
    assert plan['recommended_option_id'] is None
    assert plan['status'] == 'no_feasible_option'


def test_shared_rescue_action_discloses_simulated_saved_evidence(client, session):
    record(session, 'weather', dict(level='low', total_mm=0, hourly=[],
           meta={'mode': 'DEMO', 'is_simulated': True, 'source_name': 'Synthetic fixture'}))
    plan = save(client, session)
    actions = client.get('/api/v1/actions').json()
    action = next(a for a in actions if a['source_record_id'] == plan['id'])
    assert action['meta']['mode'] == 'MIXED'
    assert action['meta']['is_simulated'] is True
