"""Explainable selling scenarios using declared constraints and saved evidence only.

This module performs Decimal arithmetic, not a learned forecast. It never treats
seller listings as buyer demand, estimates spoilage from rain, or places orders.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Record, User, get_db, now
from .identity import require_user
from .services import compute_effective_weather, parse_iso_utc


router = APIRouter(prefix='/api/v1/rescue', tags=['AgroRescue'])
Db = Annotated[Session, Depends(get_db)]
Who = Annotated[User, Depends(require_user)]
Cost = Annotated[Decimal, Field(ge=0, le=1000000000, max_digits=15, decimal_places=2, allow_inf_nan=False)]
Price = Annotated[Decimal, Field(gt=0, le=1000000000, max_digits=15, decimal_places=2, allow_inf_nan=False)]
Quantity = Annotated[Decimal, Field(gt=0, le=1000000, max_digits=12, decimal_places=3, allow_inf_nan=False)]
Loss = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)]

DISCLAIMER = (
    'Illustrative proceeds after declared costs, not guaranteed profit or a buyer commitment. '
    'Symbolic constraint planning; no trained price, flood or spoilage prediction. '
    'Check crop readiness, actual quotes, access and local expert advice before acting. '
    'No automatic harvesting, selling or chemical dosing.'
)
SNAPSHOT_NOTICE = 'Saved decision snapshot. Sources and assumptions are not refreshed; create a new plan for current evidence.'


class RescueOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=120)
    price_id: str | None = Field(default=None, min_length=1, max_length=128)
    price_bdt: Price | None = None
    transport_bdt: Cost | None = None
    handling_bdt: Cost = Decimal('0')
    fees_bdt: Cost = Decimal('0')
    confirmed: StrictBool = False

    @field_validator('label')
    @classmethod
    def clean_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Provide an option label')
        return value

    @model_validator(mode='after')
    def exactly_one_price_source(self):
        if (self.price_id is None) == (self.price_bdt is None):
            raise ValueError('Provide exactly one owned price_id or farmer-entered price_bdt')
        return self


class RescueInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plot_id: str = Field(min_length=1, max_length=128)
    harvested_kg: Quantity
    ready_to_sell: StrictBool | None = None
    cold_storage: StrictBool | None = None
    hold_price_bdt: Price | None = None
    hold_loss_pct: Loss | None = None
    storage_cost_bdt: Cost | None = None
    scenario_mode: Literal['USER', 'DEMO'] = 'USER'
    options: list[RescueOption] = Field(min_length=1, max_length=6)


def _owned(db: Session, user: User, record_id: str, kind: str) -> Record:
    row = db.get(Record, record_id)
    if row is None or row.owner_id != user.id or row.kind != kind:
        raise HTTPException(404, 'Record not found')
    return row


def _rows(db: Session, user: User, kind: str, plot_id: str | None = None):
    query = select(Record).where(Record.owner_id == user.id, Record.kind == kind)
    if plot_id is not None:
        query = query.where(Record.plot_id == plot_id)
    return db.scalars(query.order_by(Record.created_at.desc(), Record.id.desc()))


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def _quantity(value: Decimal) -> str:
    # Quantity (3 places) × loss percentage (2 places / 100) needs 7 places.
    # Preserve that precision while retaining at least 3 places for display.
    whole, fractional = format(value, '.7f').split('.')
    return whole + '.' + fractional.rstrip('0').ljust(3, '0')


def _view(row: Record) -> dict:
    return {**row.payload, 'id': row.id, 'plot_id': row.plot_id, 'created_at': row.created_at,
            'snapshot_notice': SNAPSHOT_NOTICE}


def _entered_meta(demo: bool) -> dict:
    return dict(mode='DEMO' if demo else 'USER', source_type='scenario_simulated' if demo else 'user_reported',
                source_name='Synthetic example assumptions' if demo else 'Farmer-entered quote and costs',
                is_simulated=demo, freshness='user_confirmation_required', quality_flags=[],
                is_hypothetical=False)


def _price_value(raw) -> Decimal:
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or not 0 < value <= Decimal('1000000000'):
            raise ValueError('Out of bounds')
        return value
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(422, 'Stored quote has no usable finite positive unit price') from exc


def _quote_date_reason(raw) -> str | None:
    try:
        # Dates and timestamps retain their original observation date.
        if not isinstance(raw, str):
            observed = None
        elif len(raw) == 10:
            observed = date.fromisoformat(raw)
        else:
            observed = datetime.fromisoformat(raw.replace('Z', '+00:00')).date()
    except ValueError:
        observed = None
    if observed is None:
        return 'quote_date_unknown'
    age = (datetime.now(timezone.utc).date() - observed).days
    if age < 0:
        return 'quote_future'
    return 'quote_stale' if age > 3 else None


def _evidence(db: Session, user: User, plot_id: str, warnings: list[str]) -> dict:
    """Save narrow summaries, excluding photos, personal notes and symptom text."""
    weather_row = next(iter(_rows(db, user, 'weather', plot_id)), None)
    weather = None
    if weather_row:
        effective = compute_effective_weather(weather_row.payload)
        meta = dict(effective.get('meta') or {})
        if not meta.get('is_simulated') and meta.get('freshness') == 'fresh':
            retrieved = parse_iso_utc(meta.get('retrieved_at'))
            expires = parse_iso_utc(effective.get('valid_until'))
            if not retrieved or not expires or retrieved > datetime.now(timezone.utc):
                meta['freshness'] = 'unknown'
        freshness = meta.get('freshness', 'unknown')
        if freshness in ('stale', 'expired', 'unknown'):
            warnings.append('weather_' + freshness)
        if meta.get('is_simulated') or meta.get('mode') == 'DEMO':
            warnings.append('simulated_weather')
        if effective.get('last_refresh_failed_at') or 'live_refresh_failed' in meta.get('quality_flags', []):
            warnings.append('weather_refresh_failed')
        weather = dict(id=weather_row.id, created_at=weather_row.created_at, meta=meta,
                       **{key: effective.get(key) for key in ('level', 'total_mm', 'horizon_hours', 'valid_from', 'valid_until', 'is_expired')},
                       notice='Saved rain preparedness context only. Not inundation, crop-loss or safe-travel evidence.')
    else:
        warnings.append('weather_missing')

    case_row = next(iter(_rows(db, user, 'case', plot_id)), None)
    case = None
    if case_row:
        data = case_row.payload
        classification = data.get('classification') or {}
        case = dict(id=case_row.id, created_at=case_row.created_at, status=data.get('status'),
                    classification={key: classification.get(key) for key in ('abstained', 'top_label')},
                    meta=dict(data.get('meta') or {}),
                    notice='Research screening context only, not a diagnosis, food-safety assessment or estimate of harvest loss.')
        if classification.get('abstained') or classification.get('top_label') in (None, 'unknown', 'uncertain') or data.get('status') in ('uncertain', 'rejected', 'needs_review'):
            warnings.append('inspect_crop_first')
        if case['meta'].get('is_simulated') or case['meta'].get('mode') == 'DEMO':
            warnings.append('simulated_case')
    return dict(weather=weather, case=case)


def _plan(db: Session, user: User, plot: Record, body: RescueInput) -> dict:
    warnings: list[str] = []
    questions: list[dict] = []
    options: list[dict] = []
    crop = plot.payload.get('crop')
    if not isinstance(crop, str) or not crop.strip():
        raise HTTPException(422, 'Plot requires a known crop before a selling comparison')
    demo = body.scenario_mode == 'DEMO'
    if demo:
        warnings.append('demo_scenario')
    if body.ready_to_sell is None:
        questions.append(dict(code='ready_to_sell', text='Is this harvested crop ready and suitable for sale? Confirm with a local expert when uncertain.'))
    price_basis = None
    pending = body.ready_to_sell is None
    for index, option in enumerate(body.options):
        oid = f'sell-{index}'
        reasons: list[str] = []
        meta = _entered_meta(demo)
        if option.price_id:
            row = _owned(db, user, option.price_id, 'price')
            quote = row.payload
            if quote.get('commodity') != crop:
                raise HTTPException(422, 'Stored quote commodity must match plot crop')
            if str(quote.get('unit', '')).strip().casefold() not in ('bdt/kg', 'kg'):
                raise HTTPException(422, 'Stored quote must use kilograms (BDT/kg)')
            basis = tuple(str(quote.get(key) or 'unspecified').strip().casefold() for key in ('price_type', 'grade'))
            if price_basis is not None and basis != price_basis:
                raise HTTPException(422, 'Stored quotes must share one price_type and grade comparison basis')
            price_basis = basis
            unit_price = _price_value(quote.get('price'))
            # Keep real quote attribution intact even inside an example scenario.
            meta = {**dict(quote.get('meta') or {}), 'price_id': row.id,
                    **{key: quote.get(key) for key in ('market', 'price_type', 'grade', 'unit', 'observed_at')}}
            if demo:
                meta['scenario_mode'] = 'DEMO'
            date_reason = _quote_date_reason(quote.get('observed_at'))
            meta['freshness'] = {'quote_stale': 'stale', 'quote_future': 'future', 'quote_date_unknown': 'unknown'}.get(date_reason, 'recent')
            if date_reason:
                reasons.append(date_reason)
                warnings.append(date_reason)
                if not option.confirmed:
                    reasons.append('quote_confirmation_required')
                    pending = True
                    questions.append(dict(code=f'confirm_{oid}', text=f'Confirm an actual usable quote for {option.label}; the saved quote date is stale, future or unknown.'))
        else:
            unit_price = option.price_bdt
        meta['confirmed_by_farmer'] = option.confirmed
        meta['unit_price_bdt'] = _money(unit_price)
        if meta.get('is_simulated') or meta.get('mode') == 'DEMO':
            warnings.append('simulated_price')
        if not option.confirmed:
            warnings.append('unconfirmed_quote')
        if body.ready_to_sell is not True:
            reasons.append('ready_unknown' if body.ready_to_sell is None else 'not_ready')
        # Round proceeds once to payable currency before subtracting cent costs;
        # the displayed gross - costs must equal the displayed net.
        gross = Decimal(_money(body.harvested_kg * unit_price))
        costs = None if option.transport_bdt is None else option.transport_bdt + option.handling_bdt + option.fees_bdt
        net = gross - costs if costs is not None else None
        if costs is None:
            reasons.append('transport_unknown')
            pending = True
        if net is not None and net <= 0:
            reasons.append('nonpositive_net')
            warnings.append('nonpositive_net')
        feasible = body.ready_to_sell is True and costs is not None and 'quote_confirmation_required' not in reasons and net > 0
        options.append(dict(id=oid, label=option.label, kind='sell_now', feasible=feasible,
                            net_bdt=_money(net) if net is not None else None,
                            gross_bdt=_money(gross), costs_bdt=_money(costs) if costs is not None else None,
                            saleable_kg=_quantity(body.harvested_kg), reasons=reasons, meta=meta))

    # Ask the next consequential question, including the competing known outcome.
    known_nets = [Decimal(item['net_bdt']) for item in options if item['feasible']]
    best_known = max(known_nets) if known_nets else None
    for index, item in enumerate(options):
        if 'transport_unknown' in item['reasons']:
            option = body.options[index]
            text = f'What is the total transport cost in BDT for {option.label}? Enter 0 explicitly if there is no cost.'
            question = dict(code=f'transport_{item["id"]}', text=text)
            if best_known is not None:
                gross = Decimal(item['gross_bdt'])
                limit = gross - option.handling_bdt - option.fees_bdt - best_known
                question['break_even_transport_bdt'] = _money(limit)
                question['text'] += f' Transport below BDT {_money(limit)} would beat the best complete option under these same assumptions.' if limit > 0 else ' This option cannot beat the best complete option even with zero transport under these assumptions.'
            questions.append(question)

    candidates = [item for item in options if item['feasible']]
    recommended = None
    if body.ready_to_sell is False:
        status = 'no_feasible_option'
    elif pending:
        status = 'needs_information'
    elif not candidates:
        status = 'no_feasible_option'
    else:
        status = 'ready'
        best = max(Decimal(item['net_bdt']) for item in candidates)
        winners = [item for item in candidates if Decimal(item['net_bdt']) == best]
        if len(winners) == 1:
            recommended = winners[0]['id']
        else:
            warnings.append('equal_net_options')

    if any(value is not None for value in (body.hold_price_bdt, body.hold_loss_pct, body.storage_cost_bdt)):
        reasons = ['hypothetical_hold']
        for field, code, text in (
            ('hold_price_bdt', 'hold_price_unknown', 'Enter an explicit hypothetical future BDT/kg price; this is not a forecast.'),
            ('hold_loss_pct', 'hold_loss_unknown', 'Enter an assumed percentage of quantity loss while holding; no loss is predicted.'),
            ('storage_cost_bdt', 'storage_cost_unknown', 'Enter total holding and later selling costs in BDT: storage, later transport, handling and fees; enter zero explicitly if appropriate.'),
        ):
            if getattr(body, field) is None:
                reasons.append(code)
                questions.append(dict(code=field, text=text))
        if body.cold_storage is not True:
            reasons.append('storage_not_confirmed')
            questions.append(dict(code='cold_storage', text='Confirm suitable storage is available before considering this hypothetical hold scenario.'))
        complete = len(reasons) == 1
        saleable = body.harvested_kg * (1 - body.hold_loss_pct / 100) if complete else None
        gross = Decimal(_money(saleable * body.hold_price_bdt)) if complete else None
        net = gross - body.storage_cost_bdt if complete else None
        options.append(dict(id='hold', label='Hypothetical hold scenario', kind='hold',
                            feasible=bool(complete and body.ready_to_sell is True and net > 0),
                            net_bdt=_money(net) if net is not None else None,
                            gross_bdt=_money(gross) if gross is not None else None,
                            costs_bdt=_money(body.storage_cost_bdt) if complete else None,
                            saleable_kg=_quantity(saleable) if complete else None,
                            reasons=reasons, meta={**_entered_meta(demo), 'is_hypothetical': True,
                            'cost_scope': 'total_holding_and_later_selling_costs',
                            'notice': 'storage_cost_bdt includes total storage, later transport, handling and selling fees. Quantity loss and future price are farmer assumptions, not forecasts.'}))
        warnings.append('hold_hypothetical')

    evidence = _evidence(db, user, plot.id, warnings)
    modes = {item['meta'].get('mode', 'unknown') for item in options}
    modes.update(source['meta'].get('mode', 'unknown') for source in evidence.values() if source)
    if len(modes) > 1:
        warnings.append('mixed_sources')
    return dict(commodity=crop, method='symbolic_constraint_planner_v1', status=status,
                recommended_option_id=recommended, options=options, questions=questions,
                warnings=list(dict.fromkeys(warnings)), evidence=evidence,
                assumptions=body.model_dump(mode='json'), disclaimer=DISCLAIMER)


@router.post('/plans')
def create_plan(body: RescueInput, user: Who, db: Db):
    plot = _owned(db, user, body.plot_id, 'plot')
    with localcontext() as context:
        context.prec = 38
        payload = _plan(db, user, plot, body)
    stamp = now()
    plan = Record(owner_id=user.id, kind='rescue_plan', plot_id=plot.id, farm_id=plot.farm_id,
                  payload=payload, created_at=stamp, updated_at=stamp)
    db.add(plan)
    db.flush()
    existing = [row for row in _rows(db, user, 'action', plot.id) if row.payload.get('topic') == 'rescue']
    action_meta = _entered_meta(body.scenario_mode == 'DEMO')
    source_metas = [item['meta'] for item in payload['options']]
    source_metas.extend(item['meta'] for item in payload['evidence'].values() if item)
    action_meta['is_simulated'] = body.scenario_mode == 'DEMO' or any(
        meta.get('is_simulated') or meta.get('mode') == 'DEMO' for meta in source_metas)
    action_meta['source_name'] = 'AgroRescue declared assumptions and saved evidence'
    action_meta['quality_flags'] = payload['warnings']
    if 'mixed_sources' in payload['warnings']:
        action_meta['mode'] = 'MIXED'
        action_meta['source_type'] = 'mixed_sources'
    action_payload = dict(topic='rescue', title='Review your crop selling plan',
                          reason=f'Declared-cost comparison: {payload["status"]}. Review source limits and unanswered questions.',
                          status='open', priority='normal', severity='info', comment='', snoozed_until=None,
                          meta=action_meta, evidence_fingerprint=plan.id, plan_id=plan.id)
    if existing:
        action = existing[0]
        action.payload = action_payload
        action.source_record_id = plan.id
        action.updated_at = stamp
        for duplicate in existing[1:]:
            db.delete(duplicate)
    else:
        db.add(Record(owner_id=user.id, kind='action', plot_id=plot.id, farm_id=plot.farm_id,
                      source_record_id=plan.id, payload=action_payload))
    db.add(Record(owner_id=user.id, kind='audit', plot_id=plot.id,
                  payload=dict(event='rescue_plan.created', record_id=plan.id)))
    db.commit()
    return _view(plan)


@router.get('/plans')
def list_plans(user: Who, db: Db, plot_id: str | None = None):
    if plot_id is not None:
        _owned(db, user, plot_id, 'plot')
    # Apply SQL limit before materializing history, including across all plots.
    query = select(Record).where(Record.owner_id == user.id, Record.kind == 'rescue_plan')
    if plot_id is not None:
        query = query.where(Record.plot_id == plot_id)
    rows = db.scalars(query.order_by(Record.created_at.desc(), Record.id.desc()).limit(20))
    return [_view(row) for row in rows]


@router.get('/plans/{plan_id}')
def get_plan(plan_id: str, user: Who, db: Db):
    return _view(_owned(db, user, plan_id, 'rescue_plan'))


@router.delete('/plans/{plan_id}')
def delete_plan(plan_id: str, user: Who, db: Db):
    plan = _owned(db, user, plan_id, 'rescue_plan')
    for action in list(_rows(db, user, 'action', plan.plot_id)):
        if action.source_record_id == plan.id or action.payload.get('plan_id') == plan.id:
            db.delete(action)
    db.add(Record(owner_id=user.id, kind='audit', plot_id=plan.plot_id,
                  payload=dict(event='rescue_plan.deleted', record_id=plan.id)))
    db.delete(plan)
    db.commit()
    return {'ok': True, 'deleted_id': plan_id}
