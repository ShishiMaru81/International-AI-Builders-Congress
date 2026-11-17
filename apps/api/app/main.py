"""ZYNTRIX AgroSphere AI HTTP API — audit remediation contracts (Phases 1–5)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .identity import require_user, user_view
from .market_privacy import owner_export as market_owner_export, erase_account as erase_market_account
from .market_auth import router as auth_router, AuthLimiter
from .rescue import router as rescue_router
from . import market_models, market_service
from .db import Base, Reading, Record, Token, User, engine, ensure_compat_schema, get_db, now
from .doctor_models import CROPS, DoctorRegistry, normalize_crop
from .schemas import (
    ActionUpdate,
    ComparisonInput,
    ComparisonScenarioInput,
    DemoLogin,
    DeviceInput,
    FarmCreate,
    FarmLocationInput,
    FarmPatch,
    FeedbackInput,
    PlotCreate,
    PlotPatch,
    PreferencesModel,
    PreferencesPatch,
    SensorInput,
    ValidatedFarm,
    VulnerabilityInput,
    WatchInput,
    WatchPatch,
)
from .services import (
    DemoWeatherProvider,
    Esp32HttpAdapter,
    HistoricalSensorAdapter,
    LocationSearchProvider,
    ModelBrokenError,
    ModelBusyError,
    ModelRegistry,
    OpenMeteoProvider,
    SimulatorAdapter,
    acquire_upload_slot,
    calculate,
    compute_effective_price_meta,
    compute_effective_weather,
    iso_now,
    parse_and_validate_market_csv,
    parse_iso_utc,
    preparedness,
    provenance,
)

storage = Path(os.getenv('IMAGE_STORAGE_PATH', 'storage'))
storage.mkdir(parents=True, exist_ok=True)
Image.MAX_IMAGE_PIXELS = 20_000_000
APP_VERSION = '1.0.0'


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_compat_schema(engine)
    app.state.instance_id = uuid4().hex
    app.state.market_auth_limiter = AuthLimiter()
    yield


app = FastAPI(title='ZYNTRIX AgroSphere AI', version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(','),
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type', 'X-Device-Key', 'Idempotency-Key'],
)


@app.middleware('http')
async def request_headers(request: Request, call_next):
    request.state.request_id = uuid4().hex
    response = await call_next(request)
    response.headers.update({
        'X-Request-ID': request.state.request_id,
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'no-store',
    })
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'code': f'HTTP_{exc.status_code}',
            'message': str(exc.detail),
            'request_id': getattr(request.state, 'request_id', None),
        },
    )


@app.exception_handler(ModelBrokenError)
async def model_broken(request: Request, exc: ModelBrokenError):
    return JSONResponse(
        status_code=503,
        content={
            'code': 'MODEL_UNAVAILABLE',
            'message': str(exc),
            'request_id': getattr(request.state, 'request_id', None),
        },
    )


@app.exception_handler(ModelBusyError)
async def model_busy(request: Request, exc: ModelBusyError):
    return JSONResponse(
        status_code=429,
        headers={'Retry-After': '5'},
        content={
            'code': 'MODEL_BUSY',
            'message': str(exc),
            'request_id': getattr(request.state, 'request_id', None),
        },
    )


Db = Annotated[DBSession, Depends(get_db)]


def current_user(db: Db, authorization: Annotated[str | None, Header()] = None) -> User:
    return require_user(db, authorization)


Who = Annotated[User, Depends(current_user)]


def records(db: DBSession, user: User, kind: str, plot: str | None = None) -> list[Record]:
    q = select(Record).where(Record.owner_id == user.id, Record.kind == kind)
    if plot:
        q = q.where(Record.plot_id == plot)
    return list(db.scalars(q.order_by(Record.created_at.desc())))


def owned(db: DBSession, user: User, id: str, kind: str | None = None) -> Record:
    r = db.get(Record, id)
    if not r or r.owner_id != user.id or (kind and r.kind != kind):
        raise HTTPException(404, 'Record not found')
    return r


def view(r: Record, *, include_kind: bool = False, strip_secrets: bool = False) -> dict[str, Any]:
    reserved = {
        'id', 'created_at', 'updated_at', 'plot_id', 'farm_id', 'source_record_id', 'kind', 'owner_id',
    }
    payload = {k: v for k, v in (r.payload or {}).items() if k not in reserved}
    data = dict(
        id=r.id,
        created_at=r.created_at,
        updated_at=r.updated_at,
        plot_id=r.plot_id,
        farm_id=r.farm_id or payload.get('farm_id'),
        source_record_id=r.source_record_id,
        **payload,
    )
    # Prefer relational farm_id column; fall back to payload farm_id for legacy plot records
    if r.farm_id:
        data['farm_id'] = r.farm_id
    elif 'farm_id' in (r.payload or {}):
        data['farm_id'] = r.payload['farm_id']
    if include_kind:
        data['kind'] = r.kind
    if strip_secrets:
        data.pop('key_hash', None)
        data.pop('image_file', None)
    return data


def add(
    db: DBSession,
    user: User,
    kind: str,
    payload: dict[str, Any],
    plot: str | None = None,
    farm_id: str | None = None,
    source_record_id: str | None = None,
) -> Record:
    stamp = now()
    r = Record(
        owner_id=user.id,
        kind=kind,
        payload=payload,
        plot_id=plot,
        farm_id=farm_id,
        source_record_id=source_record_id,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(r)
    db.flush()
    return r


def touch(r: Record) -> None:
    r.updated_at = now()


def audit(db: DBSession, user: User, event: str, record_id: str, plot: str | None = None) -> None:
    add(db, user, 'audit', dict(event=event, record_id=record_id), plot=plot)


def evidence_fingerprint(topic: str, payload: dict[str, Any] | None) -> str:
    base = {'topic': topic, 'payload': payload or {}}
    return hashlib.sha256(json.dumps(base, sort_keys=True, default=str).encode()).hexdigest()


def _snooze_expired(payload: dict[str, Any]) -> bool:
    until = payload.get('snoozed_until')
    if not until:
        return True
    parsed = parse_iso_utc(until)
    if not parsed:
        return True
    return parsed <= datetime.now(timezone.utc)


def upsert_action(
    db: DBSession,
    user: User,
    plot: str,
    topic: str,
    title: str,
    reason: str,
    meta: dict[str, Any],
    *,
    source_record_id: str | None = None,
    fingerprint: str | None = None,
) -> Record:
    """Idempotent action upsert that preserves done/snoozed for identical evidence (B09)."""
    fp = fingerprint or evidence_fingerprint(topic, meta)
    matches = [
        r for r in records(db, user, 'action', plot)
        if r.payload.get('topic') == topic and r.payload.get('evidence_fingerprint') == fp
    ]
    if matches:
        a = matches[0]
        status = a.payload.get('status', 'open')
        if status == 'done':
            a.payload = {**a.payload, 'title': title, 'reason': reason, 'meta': meta}
            touch(a)
            return a
        if status == 'snoozed' and not _snooze_expired(a.payload):
            a.payload = {**a.payload, 'title': title, 'reason': reason, 'meta': meta}
            touch(a)
            return a
        # Identical evidence but open, or snooze expired → refresh without duplicate notification
        a.payload = {
            **a.payload,
            'title': title,
            'reason': reason,
            'status': 'open',
            'meta': meta,
            'evidence_fingerprint': fp,
            'snoozed_until': None,
        }
        a.source_record_id = source_record_id or a.source_record_id
        touch(a)
        return a

    # Different fingerprint: retire prior open action of same topic, then create
    for existing in records(db, user, 'action', plot):
        if existing.payload.get('topic') == topic and existing.payload.get('status') == 'open':
            if existing.payload.get('evidence_fingerprint') != fp:
                existing.payload = {**existing.payload, 'status': 'done', 'reason': existing.payload.get('reason', '') + ' (superseded)'}
                touch(existing)

    a = add(
        db,
        user,
        'action',
        dict(
            topic=topic,
            title=title,
            reason=reason,
            status='open',
            comment='',
            snoozed_until=None,
            evidence_fingerprint=fp,
            meta=meta,
        ),
        plot=plot,
        source_record_id=source_record_id,
    )
    add(
        db,
        user,
        'notification',
        dict(
            title=title,
            read=False,
            action_id=a.id,
            topic=topic,
            source_record_id=source_record_id,
            target_route={'doctor': 'doctor', 'flood': 'flood', 'market': 'market'}.get(topic),
        ),
        plot=plot,
        source_record_id=source_record_id,
    )
    return a


def _location_signature(payload: dict[str, Any]) -> tuple:
    return (
        payload.get('latitude'),
        payload.get('longitude'),
        bool(payload.get('location_consent')),
        payload.get('location_name'),
    )


def apply_farm_location_change(
    db: DBSession,
    user: User,
    farm: Record,
    new_fields: dict[str, Any],
    *,
    reason: str = 'Farm location changed. Retrieve a new outlook before making rain preparations.',
) -> bool:
    """Central location mutation + weather invalidation (B01). Returns True if location changed."""
    before = _location_signature(farm.payload)
    merged = {**farm.payload, **new_fields}
    after = _location_signature(merged)
    farm.payload = merged
    touch(farm)
    if before == after:
        return False
    for p in records(db, user, 'plot'):
        if p.payload.get('farm_id') != farm.id:
            continue
        for old in records(db, user, 'weather', p.id):
            db.delete(old)
        upsert_action(
            db,
            user,
            p.id,
            'flood',
            'Refresh weather for your selected area',
            reason,
            provenance('MIXED', 'farmer_selected_location'),
            fingerprint=evidence_fingerprint('flood', {'event': 'location_invalidated', 'farm_id': farm.id, 'at': iso_now()}),
        )
    return True


def merge_preferences(current: dict[str, Any] | None, patch: PreferencesPatch) -> dict[str, Any]:
    base = PreferencesModel.model_validate(current or {}).model_dump()
    updates = patch.model_dump(exclude_unset=True)
    base.update(updates)
    return PreferencesModel.model_validate(base).model_dump()


def merge_farm(current: dict[str, Any], patch: FarmPatch) -> dict[str, Any]:
    data = {
        'name': current.get('name'),
        'district': current.get('district'),
        'latitude': current.get('latitude'),
        'longitude': current.get('longitude'),
        'location_consent': bool(current.get('location_consent')),
        'location_name': current.get('location_name'),
        'country': current.get('country'),
    }
    data.update(patch.model_dump(exclude_unset=True))
    return ValidatedFarm.model_validate(data).model_dump()


def _prefs(user: User) -> dict[str, Any]:
    return PreferencesModel.model_validate(user.preferences or {}).model_dump()


def _plots_for_farm(db: DBSession, user: User, farm_id: str) -> list[Record]:
    return [p for p in records(db, user, 'plot') if p.payload.get('farm_id') == farm_id]


def _delete_case_artifacts(db: DBSession, user: User, case: Record) -> None:
    image_name = (case.payload or {}).get('image_file')
    if image_name:
        (storage / image_name).unlink(missing_ok=True)
    for fb in list(records(db, user, 'feedback', case.plot_id)):
        if fb.source_record_id == case.id or fb.payload.get('case_id') == case.id:
            db.delete(fb)
    for action_rec in list(records(db, user, 'action', case.plot_id)):
        if action_rec.source_record_id == case.id or (
            action_rec.payload.get('topic') == 'doctor'
            and action_rec.payload.get('evidence_fingerprint') == evidence_fingerprint('doctor', {'case_id': case.id})
        ):
            action_rec.payload = {
                **action_rec.payload,
                'status': 'done',
                'reason': 'Observation deleted; screening evidence retired.',
            }
            touch(action_rec)
    for note in list(records(db, user, 'notification', case.plot_id)):
        if note.source_record_id == case.id or note.payload.get('source_record_id') == case.id:
            db.delete(note)
    db.delete(case)


def _cascade_plot(db: DBSession, user: User, plot: Record) -> None:
    plot_id = plot.id
    for case in list(records(db, user, 'case', plot_id)):
        _delete_case_artifacts(db, user, case)
    for kind in ('weather', 'action', 'notification', 'feedback', 'comparison_scenario', 'comparison', 'rescue_plan'):
        for r in list(records(db, user, kind, plot_id)):
            db.delete(r)
    for device in list(records(db, user, 'device', plot_id)):
        db.execute(delete(Reading).where(Reading.device_id == device.id))
        db.delete(device)
    db.delete(plot)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description='ZYNTRIX AgroSphere AI private farmer workspace API',
    )
    components = schema.setdefault('components', {})
    schemes = components.setdefault('securitySchemes', {})
    schemes['BearerAuth'] = {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'opaque'}
    schemes['DeviceKeyAuth'] = {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-Device-Key',
        'description': 'Device provisioning key returned once at register/rotate',
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# ── Auth & health ────────────────────────────────────────────────────────────

@app.post('/api/v1/auth/demo')
def login(body: DemoLogin, db: Db):
    user = User(
        name=body.name,
        preferences={'language': 'en', 'theme': 'light', 'retraining_consent': False, 'selected_plot_id': None},
    )
    db.add(user)
    db.flush()
    raw = secrets.token_urlsafe(40)
    db.add(Token(
        id=hashlib.sha256(raw.encode()).hexdigest(),
        user_id=user.id,
        expires=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    ))
    farm = add(db, user, 'farm', dict(
        name='Gazipur Demo Farm',
        district='Gazipur',
        latitude=None,
        longitude=None,
        location_consent=False,
        meta=provenance(),
    ))
    plot = add(
        db,
        user,
        'plot',
        dict(farm_id=farm.id, name='Tomato plot · A', crop='tomato', area_acres='1.2', stage='Vegetative', low_lying=False, meta=provenance()),
        farm_id=farm.id,
    )
    for market, price in [('Gazipur demo wholesale', '42.00'), ('Dhaka demo wholesale', '46.00')]:
        add(db, user, 'price', dict(
            market=market,
            commodity='tomato',
            price=price,
            unit='BDT/kg',
            price_type='wholesale',
            grade='unspecified',
            observed_at='2026-11-15',
            meta=provenance(observed_at='2026-11-15'),
        ))
    upsert_action(db, user, plot.id, 'doctor', 'Start your first crop screening', 'Upload a clear tomato leaf photo. Review model evidence and uncertainty.', provenance())
    upsert_action(db, user, plot.id, 'flood', 'Review rain preparedness', 'Explore the clearly labeled simulated rain outlook.', provenance())
    upsert_action(db, user, plot.id, 'market', 'Compare selling options', 'Enter all costs before comparing synthetic market quotes.', provenance())
    user.preferences = {**_prefs(user), 'selected_plot_id': plot.id}
    audit(db, user, 'demo.created', farm.id)
    db.commit()
    return dict(token=raw, user_id=user.id, plot_id=plot.id)


@app.post('/api/v1/auth/logout')
def logout(user: Who, db: Db, authorization: Annotated[str, Header()]):
    db.execute(delete(Token).where(Token.id == hashlib.sha256(authorization[7:].encode()).hexdigest()))
    db.commit()
    return {'ok': True}


def _health_payload(request: Request | None = None) -> dict[str, Any]:
    instance = getattr(getattr(request, 'app', None), 'state', None)
    instance_id = getattr(instance, 'instance_id', None) if instance else None
    if instance_id is None and hasattr(app.state, 'instance_id'):
        instance_id = app.state.instance_id
    return {
        'status': 'ok',
        'version': APP_VERSION,
        'mode': os.getenv('DATA_MODE', 'DEMO'),
        'instance_id': instance_id or 'starting',
    }


@app.get('/api/v1/health')
@app.get('/api/v1/health/live')
def health(request: Request):
    return _health_payload(request)


@app.get('/api/v1/health/ready')
def ready(request: Request, db: Db):
    payload = _health_payload(request)
    db_state = 'ok'
    storage_state = 'ok'
    detail = None
    try:
        db.execute(text('SELECT 1'))
    except Exception as exc:  # noqa: BLE001 — readiness must never 500
        db_state = 'error'
        detail = f'database: {exc}'
    try:
        probe = storage / f'.ready-{uuid4().hex}'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink(missing_ok=True)
    except OSError as exc:
        storage_state = 'error'
        detail = (detail + '; ' if detail else '') + f'storage: {exc}'
    doctor_models = DoctorRegistry().capabilities()['models']
    unavailable = [m for m in doctor_models if not m['available']]
    model_state = ('broken_artifact' if any(m['artifact_status']=='broken_artifact' for m in unavailable)
        else 'absent' if unavailable else 'ready')
    status = 'ready'
    if db_state != 'ok' or storage_state != 'ok' or unavailable:
        status = 'not_ready'
        if unavailable and not detail:
            detail = '; '.join(m['model_id']+': '+(m.get('artifact_error') or m['artifact_status']) for m in unavailable)
    result = {
        **payload,
        'status': status,
        'database': db_state,
        'storage': storage_state,
        'model_state': model_state,
        'model_version': ', '.join(m['version'] for m in doctor_models),
        'doctor_models': doctor_models,
        'detail': detail,
    }
    return JSONResponse(result, status_code=200 if status=='ready' else 503)


@app.get('/api/v1/me')
def me(user: Who):
    return {**user_view(user), 'preferences':_prefs(user)}


@app.patch('/api/v1/me')
def preferences(body: PreferencesPatch, user: Who, db: Db):
    merged = merge_preferences(user.preferences, body)
    if merged.get('selected_plot_id'):
        owned(db, user, merged['selected_plot_id'], 'plot')
    user.preferences = merged
    db.commit()
    return merged


# ── Farms & plots ────────────────────────────────────────────────────────────

@app.get('/api/v1/farms')
def farms(user: Who, db: Db):
    return [view(r) for r in records(db, user, 'farm')]


@app.post('/api/v1/farms')
def create_farm(body: FarmCreate, user: Who, db: Db):
    r = add(db, user, 'farm', dict(**body.model_dump(), meta=provenance('MIXED', 'farmer_entered')))
    audit(db, user, 'farm.created', r.id)
    db.commit()
    return view(r)


@app.patch('/api/v1/farms/{id}')
def edit_farm(id: str, body: FarmPatch, user: Who, db: Db):
    farm = owned(db, user, id, 'farm')
    try:
        merged_fields = merge_farm(farm.payload, body)
    except Exception as exc:  # pydantic ValidationError
        raise HTTPException(422, str(exc)) from exc
    location_keys = {'latitude', 'longitude', 'location_consent', 'location_name', 'district', 'country'}
    supplied = body.model_dump(exclude_unset=True)
    location_touched = bool(location_keys & set(supplied.keys()))
    if location_touched:
        apply_farm_location_change(
            db,
            user,
            farm,
            {**merged_fields, 'meta': provenance('MIXED', 'farmer_entered')},
        )
    else:
        farm.payload = {**farm.payload, **merged_fields, 'meta': provenance('MIXED', 'farmer_entered')}
        touch(farm)
    audit(db, user, 'farm.updated', id)
    db.commit()
    return view(farm)


@app.get('/api/v1/farms/{id}')
def farm(id: str, user: Who, db: Db):
    return view(owned(db, user, id, 'farm'))


@app.delete('/api/v1/farms/{id}')
def delete_farm(id: str, user: Who, db: Db):
    with market_service.transaction() as tx:
        actor = market_service.actor(tx, user)
        farm = owned(tx, actor, id, 'farm')
        if tx.scalar(select(market_models.Product.id).where(market_models.Product.farm_id==id,market_models.Product.status!='archived').limit(1)):
            raise HTTPException(409,"Archive this farm's marketplace listings before deleting it.")
        if tx.scalar(select(market_models.SellerOrder.id).where(market_models.SellerOrder.farm_id==id,market_models.SellerOrder.status.not_in(['delivered','cancelled'])).limit(1)):
            raise HTTPException(409,"Resolve this farm's open marketplace orders before deleting it.")
        for product in tx.scalars(select(market_models.Product).where(market_models.Product.farm_id==id)): product.farm_id=None
        for order in tx.scalars(select(market_models.SellerOrder).where(market_models.SellerOrder.farm_id==id)): order.farm_id=None
        plots = _plots_for_farm(tx, actor, id)
        for plot in plots: _cascade_plot(tx, actor, plot)
        tx.delete(farm)
        if _prefs(actor).get('selected_plot_id') in {plot.id for plot in plots}: actor.preferences={**_prefs(actor),'selected_plot_id':None}
        audit(tx, actor, 'farm.deleted', id)
        return {'ok':True,'deleted_id':id,'deleted_plots':len(plots)}


@app.get('/api/v1/locations/search')
def location_search(
    user: Who,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    language: Literal['en', 'bn'] = 'en',
):
    if len(q.strip()) < 2:
        raise HTTPException(422, 'Enter at least two characters for area search')
    try:
        return LocationSearchProvider().search(q.strip(), language)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Area search is unavailable. Select a map point or enter coordinates instead.')


@app.patch('/api/v1/farms/{id}/location')
def update_location(id: str, body: FarmLocationInput, user: Who, db: Db):
    farm = owned(db, user, id, 'farm')
    apply_farm_location_change(
        db,
        user,
        farm,
        {**body.model_dump(), 'meta': provenance('MIXED', 'farmer_selected_location')},
    )
    audit(db, user, 'farm.location_updated', id)
    db.commit()
    return view(farm)


@app.get('/api/v1/plots')
def plots(user: Who, db: Db):
    return [view(r) for r in records(db, user, 'plot')]


@app.post('/api/v1/plots')
def create_plot(body: PlotCreate, user: Who, db: Db):
    owned(db, user, body.farm_id, 'farm')
    r = add(
        db,
        user,
        'plot',
        dict(**body.model_dump(mode='json'), meta=provenance('MIXED', 'farmer_entered')),
        farm_id=body.farm_id,
    )
    audit(db, user, 'plot.created', r.id)
    db.commit()
    return view(r)


@app.get('/api/v1/plots/{id}')
def plot(id: str, user: Who, db: Db):
    return view(owned(db, user, id, 'plot'))


@app.patch('/api/v1/plots/{id}')
def edit_plot(id: str, body: PlotPatch, user: Who, db: Db):
    p = owned(db, user, id, 'plot')
    updates = body.model_dump(exclude_unset=True, mode='json')
    if 'farm_id' in updates:
        owned(db, user, updates['farm_id'], 'farm')
        p.farm_id = updates['farm_id']
    p.payload = {**p.payload, **updates}
    touch(p)
    audit(db, user, 'plot.updated', id)
    db.commit()
    return view(p)


@app.delete('/api/v1/plots/{id}')
def delete_plot(id: str, user: Who, db: Db):
    p = owned(db, user, id, 'plot')
    _cascade_plot(db, user, p)
    prefs = _prefs(user)
    if prefs.get('selected_plot_id') == id:
        remaining = records(db, user, 'plot')
        user.preferences = {**prefs, 'selected_plot_id': remaining[0].id if remaining else None}
    audit(db, user, 'plot.deleted', id)
    db.commit()
    return {'ok': True, 'deleted_id': id}


# ── AgroDoctor ───────────────────────────────────────────────────────────────

@app.get('/api/v1/doctor/models/current')
def model(crop: str = 'tomato'):
    try:
        return DoctorRegistry().card(crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/v1/doctor/capabilities')
def doctor_capabilities():
    return DoctorRegistry().capabilities()


@app.get('/api/v1/doctor/conditions')
def conditions(crop: str = 'tomato'):
    try:
        crop = normalize_crop(crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    capability = next(c for c in DoctorRegistry().capabilities()['crops'] if c['id'] == crop)
    return {
        'crop': crop,
        'supported_model_labels': capability['labels'],
        'guidance': [
            'Photograph both sides of leaves.',
            'Record when symptoms began.',
            'Seek local agronomic review.',
            'Confirm the selected crop yourself; arbitrary images and unknown diseases can receive high scores.',
        ],
        'source': DoctorRegistry().card(crop)['source_url'],
        'disclaimer': 'Educational guidance. No disease-specific treatment or pesticide prescription.',
        'ood_scope': 'Closed-set research screening; not a validated crop or out-of-distribution detector.',
        'limitations': capability['limitations'],
    }


@app.post('/api/v1/doctor/cases')
def upload(
    user: Who,
    db: Db,
    plot_id: Annotated[str, Form()],
    image: Annotated[UploadFile, File()],
    symptoms: Annotated[str, Form(max_length=2000)] = '',
    crop: Annotated[str | None, Form()] = None,
):
    p = owned(db, user, plot_id, 'plot')
    try:
        plot_crop = normalize_crop(p.payload.get('crop', 'tomato'))
        crop = normalize_crop(crop) if crop is not None else plot_crop
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if crop != plot_crop:
        raise HTTPException(422, 'Selected crop must match the plot crop. Choose or create a matching plot.')
    recent = [r for r in records(db, user, 'case') if r.created_at > (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()]
    if len(recent) >= 6:
        raise HTTPException(429, 'Upload limit: six images per minute')
    if Path(image.filename or '').suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise HTTPException(415, 'Use JPG, PNG or WebP')
    data = image.file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, 'Maximum upload is 8 MB')
    slot = acquire_upload_slot()
    try:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as decoded:
                    if decoded.format not in ('JPEG', 'PNG', 'WEBP') or getattr(decoded, 'n_frames', 1) != 1:
                        raise ValueError('Use a single still photo')
                    if decoded.width * decoded.height > 20_000_000:
                        raise ValueError('Image exceeds pixel limit')
                    decoded.verify()
                with Image.open(io.BytesIO(data)) as decoded:
                    oriented = ImageOps.exif_transpose(decoded)
                    # Composite transparency before RGB conversion; discarded EXIF is never stored.
                    rgba = oriented.convert('RGBA')
                    im = Image.new('RGB', rgba.size, 'white')
                    im.paste(rgba, mask=rgba.getchannel('A'))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(415, 'Invalid image, animated image or excessive dimensions. Use one JPG, PNG or WebP photo.')
        result = DoctorRegistry().infer(im, crop)
    finally:
        slot.release()
    filename = uuid4().hex + '.jpg'
    meta = provenance('MIXED' if result['model'].get('available') else 'DEMO', 'user_upload; ' + result['model']['version'])
    try:
        im.save(storage / filename, 'JPEG', quality=90)
        r = add(db, user, 'case', {**result, 'crop':crop, 'plot_name':p.payload['name'],
            'symptoms':symptoms, 'image_file':filename, 'checksum':hashlib.sha256(data).hexdigest(), 'meta':meta}, plot_id)
        upsert_action(db, user, plot_id, 'doctor', 'Review your leaf screening',
            result['status'] + ': ' + result['advice'][0], meta, source_record_id=r.id,
            fingerprint=evidence_fingerprint('doctor', {'case_id': r.id}))
        audit(db, user, 'diagnosis.created', r.id, plot_id)
        db.commit()
    except Exception:
        db.rollback()
        (storage / filename).unlink(missing_ok=True)
        raise
    return _case_view(r)


def _case_view(c: Record) -> dict:
    data = view(c)
    data.setdefault('crop', 'tomato')  # Pre-multicrop records retain their original tomato snapshot.
    filename = c.payload.get('image_file')
    data['image_available'] = bool(filename and (storage / Path(filename).name).is_file())
    return data


def _case_feedback(db: DBSession, user: User, case_id: str, plot_id: str | None) -> list[dict[str, Any]]:
    items = []
    for fb in records(db, user, 'feedback', plot_id):
        if fb.source_record_id == case_id or fb.payload.get('case_id') == case_id:
            items.append(view(fb))
    return items


@app.get('/api/v1/doctor/cases')
def cases(
    user: Who,
    db: Db,
    offset: int = 0,
    limit: int = 20,
    plot_id: str | None = None,
    paginated: bool = True,
):
    if plot_id:
        owned(db, user, plot_id, 'plot')
    all_cases = records(db, user, 'case', plot_id)
    total = len(all_cases)
    start = max(0, offset)
    size = max(1, min(limit, 100))
    page = [_case_view(r) for r in all_cases[start:start + size]]
    if not paginated:
        return page
    return {
        'items': page,
        'total': total,
        'offset': start,
        'limit': size,
        'has_more': start + size < total,
    }


@app.get('/api/v1/doctor/cases/{id}')
def case(id: str, user: Who, db: Db):
    c = owned(db, user, id, 'case')
    data = _case_view(c)
    data['feedback'] = _case_feedback(db, user, id, c.plot_id)
    return data


@app.get('/api/v1/doctor/cases/{id}/feedback')
def list_feedback(id: str, user: Who, db: Db):
    c = owned(db, user, id, 'case')
    return _case_feedback(db, user, id, c.plot_id)


@app.get('/api/v1/doctor/cases/{id}/image')
def case_image(id: str, user: Who, db: Db):
    filename = owned(db, user, id, 'case').payload.get('image_file')
    image_path = storage / Path(filename).name if filename else None
    if not image_path or not image_path.is_file():
        raise HTTPException(
            410,
            'This image is no longer available. Free demo hosts may clear photo files after a restart; case metadata can still be exported.',
        )
    return Response(image_path.read_bytes(), media_type='image/jpeg')


@app.post('/api/v1/doctor/cases/{id}/feedback')
def feedback(id: str, body: FeedbackInput, user: Who, db: Db):
    c = owned(db, user, id, 'case')
    r = add(
        db,
        user,
        'feedback',
        dict(case_id=id, **body.model_dump(), advisor_contacted=False, notice='Local note only; no advisor was contacted.'),
        c.plot_id,
        source_record_id=id,
    )
    audit(db, user, 'doctor.review_requested' if body.request_review else 'doctor.feedback', id, c.plot_id)
    db.commit()
    return view(r)


@app.get('/api/v1/doctor/cases/{id}/report')
def report(id: str, user: Who, db: Db):
    c = owned(db, user, id, 'case')
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['case_id', 'created_at', 'crop', 'plot_id', 'plot_name', 'status', 'possible_condition', 'model', 'source_revision', 'mode', 'limitations'])
    writer.writerow([
        c.id,
        c.created_at,
        c.payload.get('crop','tomato'),
        c.plot_id,
        c.payload.get('plot_name',''),
        c.payload['status'],
        c.payload['classification']['top_label'],
        c.payload['model']['version'],
        c.payload['model'].get('revision','legacy'),
        c.payload['meta']['mode'],
        c.payload['disclaimer'],
    ])
    audit(db, user, 'case.exported', id, c.plot_id)
    db.commit()
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="agrodoctor-case.csv"'})


@app.delete('/api/v1/doctor/cases/{id}')
def delete_case(id: str, user: Who, db: Db):
    c = owned(db, user, id, 'case')
    plot_id = c.plot_id
    _delete_case_artifacts(db, user, c)
    audit(db, user, 'case.deleted', id, plot_id)
    db.commit()
    return {'ok': True, 'deleted_id': id}


# ── Weather / FloodCrop ──────────────────────────────────────────────────────

@app.get('/api/v1/flood/plots/{plot_id}/outlook')
@app.get('/api/v1/weather/plots/{plot_id}/forecast')
def outlook(
    plot_id: str,
    user: Who,
    db: Db,
    horizon_hours: int = 48,
    mode: Literal['DEMO', 'LIVE'] = 'DEMO',
):
    p = owned(db, user, plot_id, 'plot')
    f = owned(db, user, p.payload['farm_id'], 'farm')
    if horizon_hours not in (24, 48, 72):
        raise HTTPException(422, 'Horizon must be 24, 48 or 72 hours')
    lat, lon = f.payload.get('latitude'), f.payload.get('longitude')
    if mode == 'LIVE' and (lat is None or lon is None):
        raise HTTPException(422, 'Add consented farm coordinates for live weather')
    provider = OpenMeteoProvider() if mode == 'LIVE' else DemoWeatherProvider()
    try:
        data = preparedness(
            provider.forecast(lat if lat is not None else 24.0023, lon if lon is not None else 90.4264),
            horizon_hours,
            p.payload.get('low_lying', False),
        )
    except (httpx.HTTPError, ValueError, KeyError):
        # Preserve the last successful observation but record that a newer
        # refresh failed; downstream planning must not imply it succeeded.
        cached = records(db, user, 'weather', plot_id)
        if cached:
            old = cached[0]
            meta = dict(old.payload.get('meta') or {})
            meta['quality_flags'] = list(dict.fromkeys([*(meta.get('quality_flags') or []), 'live_refresh_failed' if mode == 'LIVE' else 'weather_refresh_failed']))
            old.payload = {**old.payload, 'meta': meta, 'last_refresh_failed_at': iso_now(), 'last_refresh_failed_mode': mode}
            touch(old)
            db.commit()
        raise HTTPException(503, 'Weather unavailable. No simulated data substituted for live data.')
    data['location'] = {'lat': lat if lat is not None else 24.0023, 'lon': lon if lon is not None else 90.4264}
    existing = records(db, user, 'weather', plot_id)
    if existing:
        existing[0].payload = data
        touch(existing[0])
        weather_id = existing[0].id
    else:
        weather_id = add(db, user, 'weather', data, plot_id, farm_id=f.id).id
    effective = compute_effective_weather(data)
    fp = evidence_fingerprint('flood', {
        'location': data.get('location'),
        'valid_until': (effective.get('meta') or {}).get('valid_until') or data.get('meta', {}).get('valid_until'),
        'total_mm': effective.get('total_mm', data.get('total_mm')),
        'level': effective.get('level', data.get('level')),
        'horizon_hours': horizon_hours,
    })
    upsert_action(
        db,
        user,
        plot_id,
        'flood',
        'Review rain preparedness',
        f"{effective.get('total_mm', data['total_mm'])} mm / {horizon_hours} hours. {data['disclaimer']}",
        effective.get('meta', data['meta']),
        source_record_id=weather_id,
        fingerprint=fp,
    )
    audit(db, user, 'rainwatch.updated', plot_id, plot_id)
    db.commit()
    return effective


@app.get('/api/v1/flood/plots/{plot_id}/official-alerts')
def official(plot_id: str, user: Who, db: Db):
    owned(db, user, plot_id, 'plot')
    return {
        'alerts': [],
        'status': 'unavailable',
        'source_url': 'https://ww2.ffwc.gov.bd/',
        'reason': 'No authorized official bulletin feed configured',
    }


@app.post('/api/v1/flood/plots/{plot_id}/vulnerability')
def vulnerability(plot_id: str, body: VulnerabilityInput, user: Who, db: Db):
    p = owned(db, user, plot_id, 'plot')
    p.payload = {**p.payload, **body.model_dump()}
    touch(p)
    audit(db, user, 'plot.vulnerability_updated', plot_id, plot_id)
    db.commit()
    return view(p)


# ── Market ───────────────────────────────────────────────────────────────────

def _price_view(r: Record) -> dict[str, Any]:
    data = view(r)
    meta = compute_effective_price_meta(data.get('meta') or {}, data.get('observed_at'))
    data['meta'] = meta
    return data


@app.get('/api/v1/market/prices')
def prices(
    user: Who,
    db: Db,
    commodity: str = 'tomato',
    price_type: str = 'wholesale',
    market: str | None = None,
):
    return [
        _price_view(r)
        for r in records(db, user, 'price')
        if r.payload['commodity'] == commodity
        and r.payload['price_type'] == price_type
        and (not market or r.payload['market'] == market)
    ]


def _compare_one(
    db: DBSession,
    user: User,
    body: ComparisonInput,
    *,
    write_action: bool,
) -> dict[str, Any]:
    price = owned(db, user, body.price_id, 'price')
    p = price.payload
    try:
        result = calculate(p['price'], body.harvested_kg, body.loss_fraction, body.transport_bdt, body.handling_bdt, body.fees_bdt)
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise HTTPException(422, f'Price or cost values cannot be calculated: {exc}') from exc
    assumptions = body.model_dump(mode='json')
    meta = compute_effective_price_meta(p.get('meta') or {}, p.get('observed_at'))
    result.update(
        market=p['market'],
        commodity=p.get('commodity'),
        price_type=p.get('price_type'),
        grade=p.get('grade'),
        unit_price_bdt=p.get('price'),
        observed_at=p.get('observed_at'),
        price_id=price.id,
        plot_id=body.plot_id,
        meta=meta,
        assumptions=assumptions,
        disclaimer='Illustrative expected proceeds, not a guaranteed sale price or profit.',
    )
    comparison = add(db, user, 'comparison', result, plot=body.plot_id, source_record_id=price.id)
    result['id'] = comparison.id
    if write_action and body.plot_id:
        plot_record = owned(db, user, body.plot_id, 'plot')
        if plot_record.payload.get('crop') != p.get('commodity'):
            raise HTTPException(422, 'Comparison plot crop must match the selected price commodity')
        upsert_action(
            db,
            user,
            body.plot_id,
            'market',
            'Review your net selling comparison',
            f"{plot_record.payload['name']}: {result['market']} · illustrative net BDT {result['net_bdt']} after declared costs.",
            meta,
            source_record_id=comparison.id,
            fingerprint=evidence_fingerprint('market', {
                'comparison_id': comparison.id,
                'price_id': price.id,
                'assumptions': assumptions,
            }),
        )
    return result


@app.post('/api/v1/market/compare')
def compare(body: ComparisonInput, user: Who, db: Db):
    # FE-C2: never fan out actions to every same-crop plot. Action only when plot_id provided.
    result = _compare_one(db, user, body, write_action=bool(body.plot_id))
    audit(db, user, 'market.compared', body.price_id, body.plot_id)
    db.commit()
    return result


@app.post('/api/v1/market/comparisons')
def compare_scenario(body: ComparisonScenarioInput, user: Who, db: Db):
    plot = owned(db, user, body.plot_id, 'plot')
    crop = plot.payload.get('crop', 'tomato')
    items = []
    shared = body.route_costs is None
    for price_id in body.price_ids:
        price = owned(db, user, price_id, 'price')
        if price.payload.get('commodity') != crop:
            raise HTTPException(422, f'Price {price_id} commodity does not match plot crop')
        if price.payload.get('price_type') != body.price_type:
            raise HTTPException(422, f'Price {price_id} type does not match scenario price_type')
        override = (body.route_costs or {}).get(price_id)
        transport = override.transport_bdt if override else body.transport_bdt
        handling = override.handling_bdt if override else body.handling_bdt
        fees = override.fees_bdt if override else body.fees_bdt
        item = _compare_one(
            db,
            user,
            ComparisonInput(
                price_id=price_id,
                plot_id=body.plot_id,
                harvested_kg=body.harvested_kg,
                loss_fraction=body.loss_fraction,
                transport_bdt=transport,
                handling_bdt=handling,
                fees_bdt=fees,
            ),
            write_action=False,
        )
        items.append(item)
    best = max(items, key=lambda x: Decimal(x['net_bdt']))
    assumptions = body.model_dump(mode='json')
    scenario_payload = dict(
        plot_id=body.plot_id,
        plot_name=plot.payload.get('name'),
        commodity=crop,
        price_type=body.price_type,
        cost_mode='shared_equal_costs' if shared else 'route_specific_costs',
        cost_limitation=(
            'All markets share the same declared transport/handling/fees vector.'
            if shared
            else 'Route-specific costs were supplied per selected quote.'
        ),
        assumptions=assumptions,
        items=items,
        best_net_bdt=best['net_bdt'],
        best_market=best['market'],
        disclaimer='Illustrative scenario comparison, not a guaranteed sale price or profit.',
        meta=provenance('MIXED', 'farmer_comparison_scenario'),
    )
    scenario = add(db, user, 'comparison_scenario', scenario_payload, plot=body.plot_id)
    upsert_action(
        db,
        user,
        body.plot_id,
        'market',
        'Review your net selling comparison',
        f"{plot.payload['name']}: scenario best {best['market']} · illustrative net BDT {best['net_bdt']}.",
        scenario_payload['meta'],
        source_record_id=scenario.id,
        fingerprint=evidence_fingerprint('market', {
            'scenario_id': scenario.id,
            'price_ids': body.price_ids,
            'assumptions': assumptions,
        }),
    )
    audit(db, user, 'market.scenario_compared', scenario.id, body.plot_id)
    db.commit()
    return view(scenario)


@app.post('/api/v1/market/imports')
def import_prices(
    user: Who,
    db: Db,
    file: Annotated[UploadFile, File()],
    source_name: Annotated[str, Form()],
    source_url: Annotated[str, Form()],
    permission_confirmed: Annotated[bool, Form()],
):
    if not permission_confirmed:
        raise HTTPException(422, 'Confirm permission to use this private import')
    raw = file.file.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, 'CSV limit is 1 MB')
    existing = {r.payload.get('import_key') for r in records(db, user, 'price') if r.payload.get('import_key')}
    try:
        valid, errors, duplicates = parse_and_validate_market_csv(
            raw,
            source_name=source_name,
            source_url=source_url,
            existing_keys=existing,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    status = 'rejected' if errors else 'accepted'
    if not errors:
        for item in valid:
            add(db, user, 'price', item)
    payload = dict(
        status=status,
        imported=0 if errors else len(valid),
        errors=errors,
        duplicates=duplicates,
        source_name=source_name,
        source_url=source_url,
        checksum=hashlib.sha256(raw).hexdigest(),
    )
    r = add(db, user, 'import', payload)
    audit(db, user, 'market_price.imported', r.id)
    db.commit()
    return view(r)


@app.get('/api/v1/market/imports/{id}')
def imported(id: str, user: Who, db: Db):
    return view(owned(db, user, id, 'import'))


def _watch_enrich(db: DBSession, user: User, watch: Record) -> dict[str, Any]:
    data = view(watch)
    market = data.get('market')
    commodity = data.get('commodity', 'tomato')
    price_type = data.get('price_type', 'wholesale')
    target = Decimal(str(data.get('target_bdt')))
    latest = None
    for price in records(db, user, 'price'):
        p = price.payload
        if p.get('market') == market and p.get('commodity') == commodity and p.get('price_type') == price_type:
            latest = price
            break
    data.update(
        monitoring_active=False,
        delivery_mode='saved_target_only',
        notice='Saved price target only. Automatic market monitoring and external alerts are not active.',
    )
    if latest:
        observed = Decimal(str(latest.payload['price']))
        data['latest_observed_bdt'] = latest.payload['price']
        data['latest_observed_at'] = latest.payload.get('observed_at')
        data['target_met_in_saved_quotes'] = observed >= target
    else:
        data['latest_observed_bdt'] = None
        data['latest_observed_at'] = None
        data['target_met_in_saved_quotes'] = None
    return data


@app.get('/api/v1/market/watchlists')
def watches(user: Who, db: Db):
    return [_watch_enrich(db, user, r) for r in records(db, user, 'watch')]


@app.post('/api/v1/market/watchlists')
def watch(body: WatchInput, user: Who, db: Db):
    payload = body.model_dump(mode='json')
    for existing in records(db, user, 'watch'):
        same = (
            existing.payload.get('market') == payload['market']
            and existing.payload.get('commodity') == payload.get('commodity', 'tomato')
            and existing.payload.get('price_type') == payload.get('price_type', 'wholesale')
        )
        if same:
            existing.payload = {**existing.payload, **payload}
            touch(existing)
            db.commit()
            return _watch_enrich(db, user, existing)
    r = add(db, user, 'watch', payload)
    db.commit()
    return _watch_enrich(db, user, r)


@app.patch('/api/v1/market/watchlists/{id}')
def patch_watch(id: str, body: WatchPatch, user: Who, db: Db):
    w = owned(db, user, id, 'watch')
    updates = body.model_dump(exclude_unset=True, mode='json')
    w.payload = {**w.payload, **updates}
    touch(w)
    db.commit()
    return _watch_enrich(db, user, w)


@app.delete('/api/v1/market/watchlists/{id}')
def delete_watch(id: str, user: Who, db: Db):
    w = owned(db, user, id, 'watch')
    db.delete(w)
    db.commit()
    return {'ok': True, 'deleted_id': id}


@app.get('/api/v1/market/forecast')
def forecast_disabled():
    return {'enabled': False, 'reason': 'No licensed, backtested price time series available'}


# ── Actions / notifications / center ─────────────────────────────────────────

@app.get('/api/v1/actions')
def actions_list(user: Who, db: Db, plot_id: str | None = None):
    if plot_id:
        owned(db, user, plot_id, 'plot')
    return [view(r) for r in records(db, user, 'action', plot_id)]


@app.patch('/api/v1/actions/{id}')
def update_action(id: str, body: ActionUpdate, user: Who, db: Db):
    r = owned(db, user, id, 'action')
    updates = body.model_dump(exclude_unset=True, mode='json')
    if updates.get('status') == 'snoozed':
        if body.snoozed_until is not None:
            updates['snoozed_until'] = body.snoozed_until.astimezone(timezone.utc).isoformat()
        elif body.snooze_hours:
            updates['snoozed_until'] = (datetime.now(timezone.utc) + timedelta(hours=body.snooze_hours)).isoformat()
        else:
            updates['snoozed_until'] = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    if updates.get('status') == 'open':
        updates['snoozed_until'] = None
    r.payload = {**r.payload, **updates}
    touch(r)
    audit(db, user, 'action.acknowledged', id, r.plot_id)
    db.commit()
    return view(r)


@app.get('/api/v1/plots/{id}/action-center')
def center(id: str, user: Who, db: Db):
    plot = owned(db, user, id, 'plot')
    crop = plot.payload.get('crop', 'tomato')
    case_items = [view(r) for r in records(db, user, 'case', id)[:1]]
    weather_items = []
    for w in records(db, user, 'weather', id)[:1]:
        weather_items.append(compute_effective_weather(view(w)))
    comparison_items = [view(r) for r in records(db, user, 'comparison_scenario', id)[:1]]
    market_evidence = [
        _price_view(r)
        for r in records(db, user, 'price')
        if r.payload.get('commodity') == crop
    ][:5]
    return dict(
        plot_id=id,
        plot_name=plot.payload.get('name'),
        crop=crop,
        case_count=len(records(db, user, 'case', id)),
        actions=[view(r) for r in records(db, user, 'action', id)],
        evidence={'case': case_items, 'weather': weather_items, 'comparison': comparison_items},
        market_evidence=market_evidence,
        meta=provenance('MIXED', 'independent module evidence'),
    )


@app.get('/api/v1/notifications')
def notifications(user: Who, db: Db):
    out = []
    for r in records(db, user, 'notification'):
        item = view(r)
        if r.plot_id:
            try:
                p = owned(db, user, r.plot_id, 'plot')
                item['plot_name'] = p.payload.get('name')
            except HTTPException:
                item['plot_name'] = None
        out.append(item)
    return out


@app.patch('/api/v1/notifications/{id}')
def read_notification(id: str, user: Who, db: Db):
    r = owned(db, user, id, 'notification')
    r.payload = {**r.payload, 'read': True}
    touch(r)
    db.commit()
    return view(r)


@app.get('/api/v1/history')
def history(user: Who, db: Db):
    return [view(r) for r in records(db, user, 'audit')[:100]]


# ── Devices ──────────────────────────────────────────────────────────────────

@app.post('/api/v1/devices')
def register_device(body: DeviceInput, user: Who, db: Db):
    owned(db, user, body.plot_id, 'plot')
    key = secrets.token_urlsafe(32)
    r = add(
        db,
        user,
        'device',
        dict(
            name=body.name,
            key_hash=hashlib.sha256(key.encode()).hexdigest(),
            status='NO_LIVE_DEVICE_DATA',
            revoked=False,
            key_version=1,
            last_heartbeat_at=None,
            last_reading=None,
            last_historical_reading=None,
        ),
        body.plot_id,
    )
    audit(db, user, 'device.registered', r.id, body.plot_id)
    db.commit()
    return {'id': r.id, 'key': key, 'plot_id': r.plot_id, 'key_version': 1, 'rotated_at': None}


@app.get('/api/v1/devices')
def devices(user: Who, db: Db):
    return [view(r, strip_secrets=True) for r in records(db, user, 'device')]


@app.delete('/api/v1/devices/{id}')
def revoke_device(id: str, user: Who, db: Db):
    d = owned(db, user, id, 'device')
    d.payload = {**d.payload, 'revoked': True, 'status': 'REVOKED', 'key_hash': hashlib.sha256(uuid4().hex.encode()).hexdigest()}
    touch(d)
    audit(db, user, 'device.revoked', id, d.plot_id)
    db.commit()
    return {'ok': True, 'deleted_id': id}


@app.post('/api/v1/devices/{id}/rotate')
def rotate_device(id: str, user: Who, db: Db):
    d = owned(db, user, id, 'device')
    if d.payload.get('revoked'):
        raise HTTPException(409, 'Device is revoked; register a new device instead')
    key = secrets.token_urlsafe(32)
    version = int(d.payload.get('key_version') or 1) + 1
    rotated_at = iso_now()
    d.payload = {
        **d.payload,
        'key_hash': hashlib.sha256(key.encode()).hexdigest(),
        'key_version': version,
        'rotated_at': rotated_at,
        'revoked': False,
    }
    touch(d)
    audit(db, user, 'device.rotated', id, d.plot_id)
    db.commit()
    return {'id': d.id, 'key': key, 'plot_id': d.plot_id, 'key_version': version, 'rotated_at': rotated_at}


@app.get('/api/v1/devices/{id}/readings')
def device_readings(id: str, user: Who, db: Db):
    d = owned(db, user, id, 'device')
    rows = list(db.scalars(
        select(Reading).where(Reading.device_id == d.id).order_by(Reading.created_at.desc())
    ))
    out = []
    for row in rows:
        payload = row.payload or {}
        out.append(dict(
            id=row.id,
            device_id=d.id,
            plot_id=d.plot_id,
            event_id=row.event_id,
            event_timestamp=row.event_timestamp,
            source_type=row.source_type,
            created_at=row.created_at,
            measurements=payload.get('measurements') or {},
            units=payload.get('units') or {},
            calibration_id=payload.get('calibration_id'),
            calibration_verified=bool(payload.get('calibration_verified')),
            quality_flags=payload.get('quality_flags') or [],
        ))
    return out


@app.post('/api/v1/device/readings')
def ingest(body: SensorInput, db: Db, x_device_key: Annotated[str, Header()]):
    d = db.get(Record, body.device_id)
    if (
        not d
        or d.kind != 'device'
        or d.payload.get('revoked')
        or not secrets.compare_digest(d.payload.get('key_hash', ''), hashlib.sha256(x_device_key.encode()).hexdigest())
    ):
        raise HTTPException(401, 'Invalid device credentials')
    if d.plot_id != body.plot_id:
        raise HTTPException(403, 'Device is not assigned to this plot')
    if body.timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, 'Future sensor timestamp')

    is_heartbeat = body.source_type == 'heartbeat'
    if is_heartbeat:
        if body.measurements.has_any_value():
            raise HTTPException(422, 'Heartbeat events must not include measurement values')
        d.payload = {**d.payload, 'last_heartbeat_at': body.timestamp.astimezone(timezone.utc).isoformat()}
        touch(d)
        # Persist heartbeat as reading for audit without advancing measurement state
        previous = db.scalar(select(Reading).where(Reading.device_id == body.device_id, Reading.event_id == body.event_id))
        if previous:
            return {'id': previous.id, 'duplicate': True, 'quality_flags': [], 'stored_as_historical': False, 'status': d.payload.get('status')}
        payload = body.model_dump(mode='json')
        payload.update(quality_flags=['heartbeat'], calibration_verified=False, units={})
        row = Reading(
            device_id=d.id,
            event_id=body.event_id,
            event_timestamp=body.timestamp.astimezone(timezone.utc).isoformat(),
            source_type='heartbeat',
            created_at=now(),
            payload=payload,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {'duplicate': True, 'quality_flags': [], 'stored_as_historical': False, 'status': d.payload.get('status')}
        return {'id': row.id, 'duplicate': False, 'quality_flags': ['heartbeat'], 'stored_as_historical': False, 'status': d.payload.get('status')}

    if not body.measurements.has_any_value():
        raise HTTPException(422, 'Reading events require at least one supported measurement value')

    previous = db.scalar(select(Reading).where(Reading.device_id == body.device_id, Reading.event_id == body.event_id))
    if previous:
        return {'id': previous.id, 'duplicate': True, 'quality_flags': previous.payload.get('quality_flags', []), 'stored_as_historical': previous.source_type == 'historical', 'status': d.payload.get('status')}

    payload = body.model_dump(mode='json')
    # Invented calibration IDs never verify; scaffold keeps calibration_unverified (B12)
    calibration_verified = False
    if body.source_type == 'simulator':
        adapter = SimulatorAdapter()
        status = 'SIMULATED_DATA'
    elif body.source_type == 'historical':
        adapter = HistoricalSensorAdapter()
        status = d.payload.get('status') or 'DEVICE_DATA_UNVALIDATED'
    else:
        adapter = Esp32HttpAdapter()
        status = 'DEVICE_DATA_UNVALIDATED'
    payload = adapter.normalize(payload, calibration_verified=calibration_verified)
    event_ts = body.timestamp.astimezone(timezone.utc).isoformat()
    row = Reading(
        device_id=d.id,
        event_id=body.event_id,
        event_timestamp=event_ts,
        source_type=body.source_type,
        created_at=now(),
        payload=payload,
    )
    db.add(row)

    stored_as_historical = False
    current_last = (d.payload.get('last_reading') or {}).get('timestamp')
    current_dt = parse_iso_utc(current_last) if current_last else None
    event_dt = body.timestamp.astimezone(timezone.utc)
    if body.source_type == 'historical' or (current_dt and event_dt < current_dt):
        stored_as_historical = True
        d.payload = {
            **d.payload,
            'last_historical_reading': payload,
            'last_heartbeat_at': d.payload.get('last_heartbeat_at'),
        }
    else:
        d.payload = {
            **d.payload,
            'status': status,
            'last_reading': payload,
            'last_heartbeat_at': event_ts,
        }
    touch(d)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {'duplicate': True, 'quality_flags': [], 'stored_as_historical': False, 'status': d.payload.get('status')}
    return {
        'id': row.id,
        'duplicate': False,
        'quality_flags': payload.get('quality_flags', []),
        'stored_as_historical': stored_as_historical,
        'status': d.payload.get('status'),
    }


# ── Providers / export / account ─────────────────────────────────────────────

@app.get('/api/v1/providers/status')
def providers():
    return {
        'weather': {'provider': 'Open-Meteo', 'live_requires': 'consented coordinates; network', 'demo': 'scenario_simulated'},
        'flood': {'status': 'official_feed_unavailable', 'url': 'https://ww2.ffwc.gov.bd/'},
        'market': {'status': 'private_csv_or_demo', 'url': 'https://market.dam.gov.bd/'},
        'model': DoctorRegistry().card(),
        'doctor_models': DoctorRegistry().capabilities()['models'],
    }


@app.get('/api/v1/models/evaluations')
def evaluations(crop: str = 'tomato'):
    card = model(crop)
    return {'model': card, 'metrics': None, 'field_validation': 'not_performed',
        'legacy_model': ModelRegistry().card(),
        'notice': 'Original tomato evaluations belong only to the original model. New upstream models have no independent AgroSphere accuracy evaluation.'}


@app.get('/api/v1/me/export')
def export(user: Who, db: Db):
    all_records = list(db.scalars(select(Record).where(Record.owner_id == user.id)))
    exported = []
    counts: dict[str, int] = {}
    for r in all_records:
        payload = dict(r.payload or {})
        payload.pop('key_hash', None)
        # Keep image_file name out of export; binaries are separate authorized downloads
        payload.pop('image_file', None)
        exported.append(dict(
            id=r.id,
            kind=r.kind,
            plot_id=r.plot_id,
            farm_id=r.farm_id,
            source_record_id=r.source_record_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            payload=payload,
        ))
        counts[r.kind] = counts.get(r.kind, 0) + 1
    device_ids = [r.id for r in all_records if r.kind == 'device']
    sensor_rows = []
    if device_ids:
        for row in db.scalars(select(Reading).where(Reading.device_id.in_(device_ids))):
            payload = row.payload or {}
            sensor_rows.append(dict(
                id=row.id,
                device_id=row.device_id,
                plot_id=next((r.plot_id for r in all_records if r.id == row.device_id), None),
                event_id=row.event_id,
                event_timestamp=row.event_timestamp,
                source_type=row.source_type,
                created_at=row.created_at,
                measurements=payload.get('measurements') or {},
                units=payload.get('units') or {},
                calibration_id=payload.get('calibration_id'),
                calibration_verified=bool(payload.get('calibration_verified')),
                quality_flags=payload.get('quality_flags') or [],
            ))
    audit(db, user, 'account.exported', user.id)
    db.commit()
    return {
        'schema_version': '2.0',
        'exported_at': iso_now(),
        'timezone': 'UTC',
        'contains_image_binaries': False,
        'image_export_note': 'Private case images are available through authorized per-case download endpoints, not this JSON export.',
        'user': {'id': user.id, 'name': user.name, 'role': user.role, 'preferences': _prefs(user)},
        'marketplace': market_owner_export(user),
        'records_by_kind': counts,
        'records': exported,
        'sensor_readings': sensor_rows,
        'relationships': {
            'feedback.source_record_id': 'case.id',
            'action.source_record_id': 'originating case/weather/comparison id',
            'reading.device_id': 'device.id',
        },
    }


@app.delete('/api/v1/me')
def delete_account(user: Who, db: Db):
    return erase_market_account(user, storage)

app.include_router(auth_router)

from .market import router as market_router
app.include_router(market_router)
app.include_router(rescue_router)
