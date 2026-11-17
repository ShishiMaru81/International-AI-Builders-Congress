"""Domain services: provenance, weather, market math/CSV, guarded ML registry, sensors."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any, Protocol
import httpx
from PIL import Image, ImageFilter, ImageStat

MAX_PRICE_BDT_PER_KG = Decimal('100000.00')
MIN_PRICE_BDT_PER_KG = Decimal('0.01')
MAX_HARVEST_KG = Decimal('1000000')
MAX_COST_BDT = Decimal('100000000.00')
REQUIRED_CSV_COLUMNS = ('market', 'commodity', 'price', 'unit', 'price_type', 'grade', 'observed_at')
SUPPORTED_PRICE_TYPES = ('wholesale', 'retail', 'farm-gate')
MEASUREMENT_UNITS = {
    'soil_moisture_adc': 'raw_adc',
    'air_temperature_c': 'degC',
    'relative_humidity_pct': 'pct',
    'rainfall_mm_interval': 'mm',
}
OOD_SCOPE_NOTICE = (
    'Closed-set 3-class controlled tomato-leaf classifier. Non-tomato plants, non-leaf images, '
    'complex field backgrounds, and unsupported tomato diseases are not reliably rejected by '
    'model score alone.'
)


def current_utc() -> datetime:
    """Return current UTC datetime; monkeypatchable in clock-controlled tests."""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return current_utc().isoformat()


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def provenance(
    mode: str = 'DEMO',
    source: str = 'scenario_fixture',
    observed_at: str | None = None,
    *,
    source_url: str | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> dict[str, Any]:
    return dict(
        mode=mode,
        source_type='scenario_simulated' if mode == 'DEMO' else 'user_reported',
        source_name=source,
        source_url=source_url,
        observed_at=observed_at,
        issued_at=None,
        retrieved_at=iso_now(),
        valid_from=valid_from,
        valid_until=valid_until,
        is_simulated=mode == 'DEMO',
        quality_flags=['illustrative_only'] if mode == 'DEMO' else [],
        attribution='ZYNTRIX synthetic fixtures' if mode == 'DEMO' else source,
        freshness='not_applicable' if mode == 'DEMO' else 'unknown',
    )


class WeatherProvider(Protocol):
    def forecast(self, lat: float, lon: float) -> dict[str, Any]: ...


class LocationSearchProvider:
    def search(self, query: str, language: str = 'en') -> dict[str, Any]:
        response = httpx.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': query, 'count': 8, 'language': language, 'format': 'json'},
            timeout=12,
        )
        response.raise_for_status()
        places = []
        for item in response.json().get('results', []):
            lat, lon = float(item['latitude']), float(item['longitude'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            label = ', '.join(
                dict.fromkeys(str(item[k]) for k in ('name', 'admin1', 'country') if item.get(k))
            )
            places.append({
                'id': str(item['id']),
                'name': item['name'],
                'label': label,
                'district': item.get('admin2') or item.get('admin1') or item['name'],
                'country': item.get('country', ''),
                'latitude': lat,
                'longitude': lon,
            })
        return {
            'results': places,
            'source_name': 'Open-Meteo Geocoding / GeoNames',
            'is_simulated': False,
            'retrieved_at': iso_now(),
            'limitations': ['Search results identify named places, not surveyed farm boundaries.'],
        }


class DemoWeatherProvider:
    def forecast(self, lat: float, lon: float) -> dict[str, Any]:
        start = current_utc().replace(minute=0, second=0, microsecond=0)
        hourly = [
            dict(time=(start + timedelta(hours=i)).isoformat(), rain_mm=[0, 0, 1, 2, 5, 7, 3, 1][i % 8])
            for i in range(72)
        ]
        v_from = hourly[0]['time']
        v_until = (start + timedelta(hours=72)).isoformat()
        meta = provenance(valid_from=v_from, valid_until=v_until)
        return dict(
            hourly=hourly,
            meta=meta,
            location={'lat': lat, 'lon': lon},
            valid_from=v_from,
            valid_until=v_until,
        )


class OpenMeteoProvider:
    def forecast(self, lat: float, lon: float) -> dict[str, Any]:
        r = httpx.get(
            'https://api.open-meteo.com/v1/forecast',
            params=dict(
                latitude=lat,
                longitude=lon,
                hourly='precipitation',
                forecast_days=4,
                timezone='UTC',
            ),
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        now_dt = current_utc()
        hourly = [
            dict(time=t + '+00:00' if '+' not in t and not t.endswith('Z') else t, rain_mm=v)
            for t, v in zip(data['hourly']['time'], data['hourly']['precipitation'])
            if datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=timezone.utc) >= now_dt.replace(minute=0, second=0, microsecond=0)
        ]
        if len(hourly) < 72 or any(x['rain_mm'] is None or x['rain_mm'] < 0 for x in hourly[:72]):
            raise ValueError('Incomplete forecast')
        selected = hourly[:72]
        v_from = selected[0]['time']
        last_dt = parse_iso_utc(selected[-1]['time']) or now_dt
        v_until = (last_dt + timedelta(hours=1)).isoformat()
        meta = provenance(
            'LIVE',
            'Open-Meteo',
            source_url='https://open-meteo.com/en/docs',
            valid_from=v_from,
            valid_until=v_until,
        )
        meta.update(
            source_type='forecast',
            freshness='fresh',
            issued_at=None,
            attribution='Open-Meteo · CC BY 4.0',
            quality_flags=['model_issue_time_unavailable'],
        )
        return dict(
            hourly=selected,
            meta=meta,
            location={'lat': lat, 'lon': lon},
            valid_from=v_from,
            valid_until=v_until,
        )


def preparedness(forecast: dict[str, Any], horizon: int = 48, low_lying: bool = False) -> dict[str, Any]:
    if horizon not in (24, 48, 72):
        raise ValueError('Use 24, 48 or 72 hours')
    hourly = forecast['hourly']
    total = round(sum(x['rain_mm'] for x in hourly[:horizon]), 1)
    threshold = 50 if low_lying else 75
    v_from = forecast.get('valid_from') or (hourly[0]['time'] if hourly else None)
    horizon_end_dt = parse_iso_utc(hourly[min(len(hourly), horizon) - 1]['time']) if hourly else None
    full_end_dt = parse_iso_utc(hourly[-1]['time']) if hourly else None
    v_until = (
        forecast.get('valid_until')
        or ((full_end_dt + timedelta(hours=1)).isoformat() if full_end_dt else None)
    )
    meta = dict(forecast.get('meta') or {})
    meta.setdefault('valid_from', v_from)
    meta.setdefault('valid_until', v_until)
    result = dict(forecast)
    result.update(
        meta=meta,
        valid_from=v_from,
        valid_until=v_until,
        horizon_valid_until=(horizon_end_dt + timedelta(hours=1)).isoformat() if horizon_end_dt else v_until,
        total_mm=total,
        horizon_hours=horizon,
        threshold_mm=threshold,
        level='prepare' if total >= threshold else 'monitor',
        signal_type='rainfall_preparedness',
        is_flood_probability=False,
        method='configurable_precipitation_rule',
        reasons=[
            f'{total} mm over {horizon} hours; illustrative threshold {threshold} mm.',
            'Vulnerability is farmer-reported.',
        ],
        disclaimer='Rain preparedness only. Not an official flood warning or farm inundation forecast.',
        official_alert=None,
        official_url='https://ww2.ffwc.gov.bd/',
    )
    return compute_effective_weather(result)


def compute_effective_weather(payload: dict[str, Any], now_dt: datetime | None = None) -> dict[str, Any]:
    """Recompute weather freshness and expiry dynamically at read time (B02, FE-C3)."""
    ref_now = now_dt or current_utc()
    out = dict(payload)
    meta = dict(out.get('meta') or {})
    flags = list(meta.get('quality_flags') or [])
    hourly = list(out.get('hourly') or [])
    horizon = int(out.get('horizon_hours') or 48)

    v_from = out.get('valid_from') or meta.get('valid_from') or (hourly[0]['time'] if hourly else None)
    v_until = out.get('valid_until') or meta.get('valid_until')
    if not v_until and hourly:
        last_dt = parse_iso_utc(hourly[-1]['time'])
        if last_dt is not None:
            v_until = (last_dt + timedelta(hours=1)).isoformat()

    retrieved_dt = parse_iso_utc(meta.get('retrieved_at'))
    until_dt = parse_iso_utc(v_until)

    future_slots = [
        h for h in hourly
        if (dt := parse_iso_utc(h.get('time'))) is not None and (dt + timedelta(hours=1)) > ref_now
    ]

    is_expired = False
    if until_dt is not None and until_dt <= ref_now:
        is_expired = True
    elif hourly and len(future_slots) == 0:
        is_expired = True

    is_sim = bool(meta.get('is_simulated'))
    if is_expired:
        meta['freshness'] = 'expired'
        if 'forecast_window_expired' not in flags:
            flags.append('forecast_window_expired')
    elif is_sim:
        meta['freshness'] = 'not_applicable'
    else:
        age_hours = ((ref_now - retrieved_dt).total_seconds() / 3600.0) if retrieved_dt else 0.0
        if age_hours > 6.0 or len(future_slots) < min(horizon, len(hourly)):
            meta['freshness'] = 'stale'
            if 'forecast_stale_refresh_recommended' not in flags:
                flags.append('forecast_stale_refresh_recommended')
        else:
            meta['freshness'] = 'fresh'

    if out.get('last_refresh_failed_at') and 'live_refresh_failed' not in flags:
        flags.append('live_refresh_failed')

    meta['valid_from'] = v_from
    meta['valid_until'] = v_until
    meta['quality_flags'] = flags
    out['meta'] = meta
    out['valid_from'] = v_from
    out['valid_until'] = v_until
    out['is_expired'] = is_expired
    return out


def compute_effective_price_meta(
    meta: dict[str, Any] | None,
    observed_at: str | None,
    now_dt: datetime | None = None,
) -> dict[str, Any]:
    """Recompute market price freshness dynamically at read time (B02)."""
    ref_now = now_dt or current_utc()
    updated = dict(meta or {})
    flags = list(updated.get('quality_flags') or [])
    if updated.get('is_simulated') or updated.get('mode') == 'DEMO':
        updated['freshness'] = 'not_applicable'
        updated['quality_flags'] = flags
        return updated

    if observed_at:
        try:
            obs_date = datetime.strptime(observed_at[:10], '%Y-%m-%d').date()
            age_days = (ref_now.date() - obs_date).days
            if age_days > 3:
                updated['freshness'] = 'stale'
                if 'historical_price_older_than_3_days' not in flags:
                    flags.append('historical_price_older_than_3_days')
            else:
                updated['freshness'] = 'recent'
                flags = [f for f in flags if f != 'historical_price_older_than_3_days']
        except ValueError:
            updated['freshness'] = 'unknown'
    updated['quality_flags'] = flags
    return updated


def money(value: Decimal | str | int | float) -> str:
    with localcontext() as ctx:
        ctx.prec = 38
        d = Decimal(str(value))
        if not d.is_finite():
            raise ValueError('Non-finite currency value')
        return str(d.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def parse_bounded_decimal(
    raw: Any,
    *,
    field_name: str,
    min_value: Decimal,
    max_value: Decimal,
    max_decimals: int = 2,
    forbid_exponent: bool = False,
) -> Decimal:
    text_val = str(raw).strip()
    if not text_val:
        raise ValueError(f'Missing {field_name}')
    if forbid_exponent and ('e' in text_val.lower()):
        raise ValueError(f'{field_name} must be written as a standard decimal number, not scientific notation')
    with localcontext() as ctx:
        ctx.prec = 38
        try:
            d = Decimal(text_val)
        except InvalidOperation as exc:
            raise ValueError(f'Invalid numeric {field_name}') from exc
        if not d.is_finite():
            raise ValueError(f'{field_name} must be finite')
        if d < min_value or d > max_value:
            raise ValueError(f'{field_name} must be between {min_value} and {max_value}')
        # Check fractional digits after normalizing trailing zeros only if exponent exceeds max_decimals
        exp = d.as_tuple().exponent
        if isinstance(exp, int) and exp < -max_decimals:
            normalized = d.normalize()
            norm_exp = normalized.as_tuple().exponent
            if isinstance(norm_exp, int) and norm_exp < -max_decimals:
                raise ValueError(f'{field_name} supports at most {max_decimals} decimal places')
        return d


def calculate(
    price: Decimal | str | int | float,
    quantity: Decimal | str | int | float,
    loss: Decimal | str | int | float,
    transport: Decimal | str | int | float,
    handling: Decimal | str | int | float,
    fees: Decimal | str | int | float,
) -> dict[str, str]:
    with localcontext() as ctx:
        ctx.prec = 38
        p = parse_bounded_decimal(
            price,
            field_name='price',
            min_value=MIN_PRICE_BDT_PER_KG,
            max_value=MAX_PRICE_BDT_PER_KG,
            max_decimals=2,
        )
        qty = parse_bounded_decimal(
            quantity,
            field_name='harvested_kg',
            min_value=Decimal('0.001'),
            max_value=MAX_HARVEST_KG,
            max_decimals=3,
        )
        loss_dec = parse_bounded_decimal(
            loss,
            field_name='loss_fraction',
            min_value=Decimal('0'),
            max_value=Decimal('0.9999'),
            max_decimals=4,
        )
        t_bdt = parse_bounded_decimal(
            transport,
            field_name='transport_bdt',
            min_value=Decimal('0'),
            max_value=MAX_COST_BDT,
            max_decimals=2,
        )
        h_bdt = parse_bounded_decimal(
            handling,
            field_name='handling_bdt',
            min_value=Decimal('0'),
            max_value=MAX_COST_BDT,
            max_decimals=2,
        )
        f_bdt = parse_bounded_decimal(
            fees,
            field_name='fees_bdt',
            min_value=Decimal('0'),
            max_value=MAX_COST_BDT,
            max_decimals=2,
        )
        saleable = qty * (Decimal('1') - loss_dec)
        gross = saleable * p
        costs = t_bdt + h_bdt + f_bdt
        net = gross - costs
        return dict(
            saleable_kg=money(saleable),
            gross_bdt=money(gross),
            costs_bdt=money(costs),
            net_bdt=money(net),
            formula='kg × (1 − loss) × BDT/kg − transport − handling − fees',
        )


def _collapse_ws(value: str) -> str:
    return ' '.join(value.strip().split())


def canonical_price_import_key(
    *,
    market: str,
    commodity: str,
    price_bdt: str,
    unit: str,
    price_type: str,
    grade: str,
    observed_at: str,
    source_name: str,
) -> str:
    """Compute canonical price identity hash ignoring extra/discarded CSV columns (B05)."""
    canonical = {
        'market': _collapse_ws(market).casefold(),
        'commodity': _collapse_ws(commodity).lower(),
        'price': money(price_bdt),
        'unit': unit.strip(),
        'price_type': price_type.strip().lower(),
        'grade': _collapse_ws(grade).casefold(),
        'observed_at': observed_at.strip(),
        'source_name': _collapse_ws(source_name).casefold(),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode('utf-8')).hexdigest()


def parse_and_validate_market_csv(
    raw_bytes: bytes,
    *,
    source_name: str,
    source_url: str,
    existing_keys: set[str],
    now_dt: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Validate CSV structure, headers, row widths, bounds and canonical dedup (B03–B06)."""
    ref_now = now_dt or current_utc()
    try:
        decoded = raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('CSV must be valid UTF-8 text') from exc

    if not decoded.strip():
        return [], [{'row': 1, 'message': 'Empty CSV file: include required headers and at least one data row.'}], 0

    try:
        reader = csv.reader(io.StringIO(decoded), strict=True)
        all_rows = list(reader)
    except csv.Error as exc:
        return [], [{'row': 1, 'message': f'Malformed CSV syntax: {exc}'}], 0

    # Skip leading completely blank lines? No: CSV header must be row 1; reject blank header row
    if not all_rows or not any(cell.strip() for cell in all_rows[0]):
        return [], [{'row': 1, 'message': 'CSV header row is empty.'}], 0

    raw_headers = [cell.strip() for cell in all_rows[0]]
    if any(h == '' for h in raw_headers):
        return [], [{'row': 1, 'message': 'CSV header contains an empty column name.'}], 0
    if len(raw_headers) != len(set(raw_headers)):
        return [], [{'row': 1, 'message': 'CSV header contains duplicate column names.'}], 0

    missing_cols = [col for col in REQUIRED_CSV_COLUMNS if col not in raw_headers]
    if missing_cols:
        return [], [{'row': 1, 'message': f"Missing required CSV columns: {', '.join(missing_cols)}"}], 0

    data_rows = [(idx, cells) for idx, cells in enumerate(all_rows[1:], start=2) if any(c.strip() for c in cells)]
    if not data_rows:
        return [], [{'row': 1, 'message': 'CSV contains headers only; include at least one price observation row.'}], 0

    errors: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    seen_keys = set(existing_keys)
    duplicates = 0
    expected_width = len(raw_headers)

    for row_num, cells in data_rows:
        if len(cells) != expected_width:
            errors.append({
                'row': row_num,
                'message': f'Row has {len(cells)} cells, expected {expected_width} matching header columns.',
            })
            continue

        row = dict(zip(raw_headers, cells))
        try:
            market_val = _collapse_ws(row.get('market', ''))
            commodity_val = _collapse_ws(row.get('commodity', '')).lower()
            price_raw = row.get('price', '').strip()
            unit_val = row.get('unit', '').strip()
            price_type_val = row.get('price_type', '').strip().lower()
            grade_val = _collapse_ws(row.get('grade', ''))
            obs_raw = row.get('observed_at', '').strip()

            if not all([market_val, commodity_val, price_raw, unit_val, price_type_val, grade_val, obs_raw]):
                raise ValueError('Missing required field')
            if len(market_val) > 120 or len(grade_val) > 60 or len(commodity_val) > 60:
                raise ValueError('Field length exceeds supported limit')
            if not re.fullmatch(r'[a-z0-9_-]+', commodity_val):
                raise ValueError('Commodity must be a simple identifier such as tomato or potato')
            if unit_val != 'BDT/kg' or price_type_val not in SUPPORTED_PRICE_TYPES:
                raise ValueError('Unsupported unit or price type (use BDT/kg and wholesale, retail or farm-gate)')

            parsed_price = parse_bounded_decimal(
                price_raw,
                field_name='price',
                min_value=MIN_PRICE_BDT_PER_KG,
                max_value=MAX_PRICE_BDT_PER_KG,
                max_decimals=2,
                forbid_exponent=True,
            )
            normalized_price = money(parsed_price)

            try:
                obs_date = datetime.strptime(obs_raw, '%Y-%m-%d').date()
            except ValueError as exc:
                raise ValueError('observed_at must use YYYY-MM-DD') from exc
            if obs_date > ref_now.date():
                raise ValueError('Future observation date is not permitted')

            norm_obs = obs_date.isoformat()
            dedup_key = canonical_price_import_key(
                market=market_val,
                commodity=commodity_val,
                price_bdt=normalized_price,
                unit=unit_val,
                price_type=price_type_val,
                grade=grade_val,
                observed_at=norm_obs,
                source_name=source_name,
            )
            if dedup_key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(dedup_key)

            meta = provenance('HISTORICAL', _collapse_ws(source_name), norm_obs, source_url=source_url.strip())
            meta.update(
                source_type='private_import',
                source_url=source_url.strip(),
                permission_confirmed=True,
            )
            meta = compute_effective_price_meta(meta, norm_obs, now_dt=ref_now)
            valid.append(dict(
                market=market_val,
                commodity=commodity_val,
                price=normalized_price,
                unit=unit_val,
                price_type=price_type_val,
                grade=grade_val,
                observed_at=norm_obs,
                import_key=dedup_key,
                meta=meta,
            ))
        except (ValueError, ArithmeticError) as exc:
            errors.append({'row': row_num, 'message': str(exc)})

    return valid, errors, duplicates


class ModelBrokenError(RuntimeError):
    """Raised when an installed/required model artifact fails integrity or runtime validation."""


class ModelBusyError(RuntimeError):
    """Raised when bounded concurrent upload/inference capacity is saturated."""


_TORCH_INIT_LOCK = threading.Lock()
_TORCH_THREADS_CONFIGURED = False
_ARTIFACT_CACHE_LOCK = threading.Lock()
_ARTIFACT_CACHE: dict[tuple, dict[str, Any]] = {}
_INFERENCE_SEMAPHORE = threading.BoundedSemaphore(
    max(1, int(os.getenv('AGROSPHERE_MAX_CONCURRENT_UPLOADS', '2')))
)


def _ensure_torch_threads_once(torch_mod) -> None:
    global _TORCH_THREADS_CONFIGURED
    if _TORCH_THREADS_CONFIGURED:
        return
    with _TORCH_INIT_LOCK:
        if not _TORCH_THREADS_CONFIGURED:
            try:
                torch_mod.set_num_threads(max(1, int(os.getenv('AGROSPHERE_TORCH_THREADS', '2'))))
            except RuntimeError:
                # PyTorch raises if set_num_threads is called after parallel work started; safe to ignore
                pass
            _TORCH_THREADS_CONFIGURED = True


def acquire_upload_slot(timeout_sec: float | None = None):
    """Acquire bounded decode+inference slot or raise ModelBusyError (OP-01)."""
    wait = timeout_sec if timeout_sec is not None else float(os.getenv('AGROSPHERE_INFERENCE_QUEUE_TIMEOUT_SEC', '5.0'))
    acquired = _INFERENCE_SEMAPHORE.acquire(timeout=max(0.01, wait))
    if not acquired:
        raise ModelBusyError('Crop screening queue is busy. Please retry your photo in a few seconds.')
    return _INFERENCE_SEMAPHORE


class ModelRegistry:
    """Validated, SHA256-verified, worker-cached model registry (MD-02, MD-04, OP-01)."""

    def __init__(self, model_dir: str | Path | None = None):
        self.path = Path(model_dir if model_dir is not None else os.getenv('MODEL_DIR', '../../ml/artifacts'))
        self.require_approved = os.getenv('REQUIRE_APPROVED_MODEL', '').strip().lower() in ('1', 'true', 'yes')

    def _abstaining_card(self, *, status: str = 'absent', error: str | None = None, source: str | None = None) -> dict[str, Any]:
        return dict(
            version='abstaining-demo-v1',
            available=False,
            release_approved=False,
            field_validated=False,
            artifact_status=status,
            artifact_error=error,
            labels=[],
            metrics=None,
            source=source or ('Model artifact failed integrity verification' if status == 'broken_artifact' else 'No verified trained artifact installed'),
            limitations=[
                'No disease inference in demo mode.' if status == 'absent' else f'Model unavailable: {error}',
                'Not field-validated.',
                'Image quality checks do not identify crops or diseases.',
            ],
        )

    def _validate_card_dict(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return 'Model card root must be a JSON object'
        if not isinstance(data.get('version'), str) or not data['version'].strip():
            return 'Model card missing non-empty version'
        labels = data.get('labels')
        if not isinstance(labels, list) or len(labels) < 2 or not all(isinstance(x, str) and x.strip() for x in labels):
            return 'Model card must declare at least two string labels'
        threshold = data.get('threshold')
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not (0.0 < float(threshold) <= 1.0):
            return 'Model card threshold must be a number in (0, 1]'
        if not isinstance(data.get('metrics'), dict) or not data['metrics']:
            return 'Model card missing evaluation metrics object'
        if not isinstance(data.get('dataset'), dict) or not data['dataset']:
            return 'Model card missing dataset provenance object'
        digest = data.get('artifact_sha256')
        if data.get('release_approved') is True:
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest.lower()):
                return 'Approved model card missing valid 64-hex artifact_sha256'
        return None

    def _inspect_and_load(self) -> dict[str, Any]:
        resolved_dir = self.path.resolve(strict=False)
        card_file = resolved_dir / 'model.json'
        pt_file = resolved_dir / 'model.pt'

        card_exists = card_file.is_file()
        pt_exists = pt_file.is_file()

        if not card_exists and not pt_exists:
            if self.require_approved:
                return {'state': 'broken_artifact', 'error': 'Required approved model directory has no model.json or model.pt', 'card': self._abstaining_card(status='broken_artifact', error='Required model missing')}
            return {'state': 'absent', 'error': None, 'card': self._abstaining_card(status='absent')}

        if pt_exists and not card_exists:
            err = 'model.pt present without accompanying model.json metadata'
            return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}

        # card_exists is True here
        try:
            card_stat = card_file.stat()
            raw_card_bytes = card_file.read_bytes()
            card_data = json.loads(raw_card_bytes.decode('utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            err = f'Malformed model.json: {exc}'
            return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}

        schema_err = self._validate_card_dict(card_data)
        if schema_err:
            return {'state': 'broken_artifact', 'error': schema_err, 'card': self._abstaining_card(status='broken_artifact', error=schema_err)}

        if card_data.get('release_approved') is not True:
            if self.require_approved:
                err = 'Installed model.json is not release_approved'
                return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            return {'state': 'absent', 'error': None, 'card': self._abstaining_card(status='absent', source='Unapproved artifact ignored')}

        if not pt_exists:
            if self.require_approved:
                err = 'Approved model.json present but model.pt binary is missing'
                return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            return {'state': 'absent', 'error': None, 'card': self._abstaining_card(status='absent')}

        if not (importlib.util.find_spec('torch') and importlib.util.find_spec('torchvision')):
            if self.require_approved:
                err = 'PyTorch/torchvision runtime missing for required model'
                return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            return {'state': 'absent', 'error': None, 'card': self._abstaining_card(status='absent', source='PyTorch runtime not installed')}

        try:
            pt_stat = pt_file.stat()
        except OSError as exc:
            err = f'Cannot stat model.pt: {exc}'
            return {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}

        cache_key = (
            str(resolved_dir),
            card_stat.st_mtime_ns,
            card_stat.st_size,
            pt_stat.st_mtime_ns,
            pt_stat.st_size,
            self.require_approved,
        )
        with _ARTIFACT_CACHE_LOCK:
            cached = _ARTIFACT_CACHE.get(cache_key)
            if cached is not None:
                return cached

        # Compute SHA-256 and validate TorchScript load + output shape once
        try:
            h = hashlib.sha256()
            with pt_file.open('rb') as fh:
                while chunk := fh.read(1024 * 1024):
                    h.update(chunk)
            actual_sha = h.hexdigest()
        except OSError as exc:
            err = f'Cannot read model.pt: {exc}'
            entry = {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            with _ARTIFACT_CACHE_LOCK:
                _ARTIFACT_CACHE[cache_key] = entry
            return entry

        expected_sha = str(card_data['artifact_sha256']).lower()
        if actual_sha.lower() != expected_sha:
            err = f'Model artifact SHA-256 mismatch (expected {expected_sha[:12]}..., got {actual_sha[:12]}...)'
            entry = {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            with _ARTIFACT_CACHE_LOCK:
                _ARTIFACT_CACHE[cache_key] = entry
            return entry

        try:
            import torch
            from torchvision import transforms

            _ensure_torch_threads_once(torch)
            loaded_model = torch.jit.load(str(pt_file), map_location='cpu').eval()
            with torch.inference_mode():
                dummy_out = loaded_model(torch.zeros(1, 3, 224, 224))
            if not hasattr(dummy_out, 'ndim') or dummy_out.ndim != 2 or int(dummy_out.shape[0]) != 1 or int(dummy_out.shape[1]) != len(card_data['labels']):
                actual_shape = tuple(dummy_out.shape) if hasattr(dummy_out, 'shape') else type(dummy_out).__name__
                err = f"Model output shape {actual_shape} does not match {len(card_data['labels'])} declared labels"
                entry = {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
                with _ARTIFACT_CACHE_LOCK:
                    _ARTIFACT_CACHE[cache_key] = entry
                return entry

            eval_transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
        except Exception as exc:  # TorchScript RuntimeError, zip archive corruption, etc.
            err = f'Failed to initialize TorchScript artifact: {exc}'
            entry = {'state': 'broken_artifact', 'error': err, 'card': self._abstaining_card(status='broken_artifact', error=err)}
            with _ARTIFACT_CACHE_LOCK:
                _ARTIFACT_CACHE[cache_key] = entry
            return entry

        public_card = {
            **card_data,
            'available': True,
            'artifact_status': 'ready',
            'artifact_error': None,
        }
        entry = {
            'state': 'ready',
            'error': None,
            'card': public_card,
            'model': loaded_model,
            'transform': eval_transform,
            'sha256': actual_sha,
        }
        with _ARTIFACT_CACHE_LOCK:
            _ARTIFACT_CACHE[cache_key] = entry
        return entry

    def readiness(self) -> dict[str, Any]:
        bundle = self._inspect_and_load()
        state = bundle['state']
        card = bundle['card']
        return {
            'ready': state in ('ready', 'absent'),
            'state': state,
            'error': bundle['error'],
            'version': card['version'],
            'available': bool(card.get('available')),
        }

    def card(self) -> dict[str, Any]:
        return dict(self._inspect_and_load()['card'])

    def infer(self, image: Image.Image) -> dict[str, Any]:
        bundle = self._inspect_and_load()
        if bundle['state'] == 'broken_artifact':
            raise ModelBrokenError(bundle['error'] or 'Approved model artifact failed integrity verification')

        gray = image.convert('L')
        stats = ImageStat.Stat(gray)
        quality: list[str] = []
        if min(image.size) < 160:
            quality.append('low_resolution')
        if stats.mean[0] < 35:
            quality.append('underexposed')
        if stats.mean[0] > 235:
            quality.append('overexposed')
        inner = gray.crop((2, 2, max(3, gray.width - 2), max(3, gray.height - 2))) if min(gray.size) > 6 else gray
        if stats.var[0] < 8 or ImageStat.Stat(inner.filter(ImageFilter.FIND_EDGES)).var[0] < 80:
            quality.append('possibly_blurred')

        card = dict(bundle['card'])
        base: dict[str, Any] = dict(
            top_label='unknown',
            abstained=True,
            score=None,
            score_type='not_available',
            alternatives=[],
            ood_notice=OOD_SCOPE_NOTICE,
        )
        if bundle['state'] == 'ready' and not quality:
            try:
                import torch
                model = bundle['model']
                transform = bundle['transform']
                with torch.inference_mode():
                    probs = model(transform(image).unsqueeze(0)).softmax(1)[0]
                indices = probs.argsort(descending=True)[:3].tolist()
                score = float(probs[indices[0]])
                abstained = score < float(card['threshold'])
                base.update(
                    top_label='unknown' if abstained else card['labels'][indices[0]],
                    abstained=abstained,
                    score=score,
                    score_type='uncalibrated_model_score',
                    alternatives=[
                        {'label': card['labels'][i], 'score': float(probs[i])}
                        for i in indices
                    ],
                )
            except Exception as exc:
                raise ModelBrokenError(f'Model inference failed safely: {exc}') from exc

        return dict(
            classification=base,
            model=card,
            quality_flags=quality,
            status='unable_to_classify' if base['abstained'] else 'completed',
            advice=[
                'Confirm the photo shows a single tomato leaf in natural light before relying on screening.',
                'Take sharp photographs of both sides of several affected leaves and monitor neighbouring plants.',
                'Consult a qualified local agronomist or DAE extension officer if symptoms spread.',
            ],
            disclaimer='Image-assisted research screening only; not a confirmed diagnosis or crop/OOD detector.',
        )


class SensorIngestionAdapter(Protocol):
    def normalize(self, payload: dict[str, Any], *, calibration_verified: bool = False) -> dict[str, Any]: ...


def _calibration_flags(
    base_flags: list[str],
    calibration_id: str | None,
    calibration_verified: bool,
) -> list[str]:
    flags = list(base_flags)
    if not calibration_verified:
        flags.append('uncalibrated')
        if calibration_id:
            flags.append('calibration_unverified')
    return flags


class SimulatorAdapter:
    def normalize(self, payload: dict[str, Any], *, calibration_verified: bool = False) -> dict[str, Any]:
        cal_id = payload.get('calibration_id')
        flags = _calibration_flags(['simulated'], cal_id, calibration_verified)
        return {
            **payload,
            'units': dict(MEASUREMENT_UNITS),
            'calibration_verified': calibration_verified,
            'quality_flags': flags,
        }


class Esp32HttpAdapter:
    def normalize(self, payload: dict[str, Any], *, calibration_verified: bool = False) -> dict[str, Any]:
        cal_id = payload.get('calibration_id')
        flags = _calibration_flags([], cal_id, calibration_verified)
        return {
            **payload,
            'units': dict(MEASUREMENT_UNITS),
            'calibration_verified': calibration_verified,
            'quality_flags': flags,
        }


class HistoricalSensorAdapter(Esp32HttpAdapter):
    def normalize(self, payload: dict[str, Any], *, calibration_verified: bool = False) -> dict[str, Any]:
        cal_id = payload.get('calibration_id')
        flags = _calibration_flags(['historical'], cal_id, calibration_verified)
        return {
            **payload,
            'units': dict(MEASUREMENT_UNITS),
            'calibration_verified': calibration_verified,
            'quality_flags': flags,
        }
