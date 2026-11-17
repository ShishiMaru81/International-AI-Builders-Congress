"""Typed Pydantic request/response contracts for ZYNTRIX AgroSphere AI (B14, B16)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from .doctor_models import normalize_crop


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any | None = None


class OkResponse(BaseModel):
    ok: bool = True
    deleted_id: str | None = None
    deleted_plots: int | None = None


class ProvenanceMeta(BaseModel):
    model_config = ConfigDict(extra='allow')
    mode: str
    source_type: str | None = None
    source_name: str
    source_url: str | None = None
    observed_at: str | None = None
    issued_at: str | None = None
    retrieved_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    is_simulated: bool
    quality_flags: list[str] = Field(default_factory=list)
    attribution: str | None = None
    freshness: str = 'not_applicable'
    permission_confirmed: bool | None = None


class DemoLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='Demo farmer', min_length=1, max_length=80)


class DemoSessionResponse(BaseModel):
    token: str
    user_id: str
    plot_id: str


class HealthResponse(BaseModel):
    status: str
    version: str
    mode: str
    instance_id: str


class ReadinessResponse(BaseModel):
    status: Literal['ready', 'not_ready']
    version: str
    mode: str
    instance_id: str
    database: str
    storage: str
    model_state: str
    model_version: str
    detail: str | None = None


class PreferencesModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Literal['en', 'bn'] = 'en'
    theme: Literal['light', 'dark'] = 'light'
    retraining_consent: bool = False
    selected_plot_id: str | None = None


class PreferencesPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Literal['en', 'bn'] | None = None
    theme: Literal['light', 'dark'] | None = None
    retraining_consent: bool | None = None
    selected_plot_id: str | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    role: Literal['farmer','customer','admin'] = 'farmer'
    preferences: PreferencesModel


class ValidatedFarm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_consent: bool = False
    location_name: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def check_coordinates_consent(self):
        has_any_coord = self.latitude is not None or self.longitude is not None
        if has_any_coord and (not self.location_consent or self.latitude is None or self.longitude is None):
            raise ValueError('Coordinates require explicit consent and both values')
        if self.location_consent and (self.latitude is None or self.longitude is None):
            raise ValueError('Location consent requires both latitude and longitude')
        return self


class FarmCreate(ValidatedFarm):
    pass


class FarmPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=100)
    district: str | None = Field(default=None, min_length=1, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_consent: bool | None = None
    location_name: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)


class FarmLocationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_consent: Literal[True]
    location_name: str = Field(min_length=1, max_length=200)
    district: str = Field(min_length=1, max_length=80)
    country: str = Field(default='', max_length=100)


class FarmResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    plot_id: str | None = None
    name: str
    district: str
    latitude: float | None = None
    longitude: float | None = None
    location_consent: bool
    location_name: str | None = None
    country: str | None = None
    meta: ProvenanceMeta


class PlaceItem(BaseModel):
    id: str
    name: str
    label: str
    district: str
    country: str
    latitude: float
    longitude: float


class LocationSearchResponse(BaseModel):
    results: list[PlaceItem]
    source_name: str
    is_simulated: bool
    retrieved_at: str
    limitations: list[str]


class PlotCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    farm_id: str
    name: str = Field(min_length=1, max_length=100)
    crop: str = 'tomato'
    area_acres: Decimal = Field(gt=0, le=Decimal('10000'))
    stage: str = Field(default='Vegetative', min_length=1, max_length=60)
    low_lying: bool = False
    sowing_date: str | None = Field(default=None, max_length=20)

    _valid_crop = field_validator('crop')(normalize_crop)


class PlotPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    farm_id: str | None = None
    crop: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    area_acres: Decimal | None = Field(default=None, gt=0, le=Decimal('10000'))
    stage: str | None = Field(default=None, min_length=1, max_length=60)
    low_lying: bool | None = None
    sowing_date: str | None = Field(default=None, max_length=20)

    @model_validator(mode='before')
    @classmethod
    def required_fields_cannot_be_null(cls, data):
        if isinstance(data, dict) and any(data.get(k, 'omitted') is None for k in ('farm_id','crop','name','area_acres','stage','low_lying')):
            raise ValueError('Required plot fields cannot be null')
        return data

    _valid_crop = field_validator('crop')(normalize_crop)


class PlotResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    plot_id: str | None = None
    farm_id: str
    name: str
    crop: str
    area_acres: str
    stage: str
    low_lying: bool
    sowing_date: str | None = None
    meta: ProvenanceMeta


class VulnerabilityInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    low_lying: bool


class AlternativePrediction(BaseModel):
    label: str
    score: float


class ClassificationResult(BaseModel):
    top_label: str
    abstained: bool
    score: float | None = None
    score_type: str
    alternatives: list[AlternativePrediction] = Field(default_factory=list)
    ood_notice: str | None = None
    rejection_reason: str | None = None


class ModelCardResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    version: str
    available: bool
    release_approved: bool = False
    field_validated: bool = False
    artifact_status: str = 'absent'
    artifact_error: str | None = None
    labels: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)
    source: str | None = None
    threshold: float | None = None
    score_type: str | None = None
    artifact_sha256: str | None = None
    manifest_sha256: str | None = None


class ConditionsResponse(BaseModel):
    supported_model_labels: list[str]
    guidance: list[str]
    source: str
    disclaimer: str


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    note: str = Field(min_length=1, max_length=2000)
    request_review: bool = False


class FeedbackResponse(BaseModel):
    id: str
    created_at: str
    plot_id: str | None = None
    case_id: str
    note: str
    request_review: bool
    advisor_contacted: bool = False
    review_notice: str = 'Recorded in your private workspace only. No external advisor has been contacted.'


class CaseResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    plot_id: str | None = None
    plot_name: str | None = None
    crop: str
    crop_confirmed: bool = True
    symptoms: str
    status: str
    quality_flags: list[str]
    classification: ClassificationResult
    model: ModelCardResponse
    advice: list[str]
    disclaimer: str
    checksum: str | None = None
    image_file: str | None = None
    image_available: bool = True
    feedback: list[FeedbackResponse] = Field(default_factory=list)
    meta: ProvenanceMeta


class PaginatedCasesResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class HourlyRainPoint(BaseModel):
    time: str
    rain_mm: float


class WeatherLocation(BaseModel):
    lat: float
    lon: float


class WeatherOutlookResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    hourly: list[HourlyRainPoint]
    meta: ProvenanceMeta
    location: WeatherLocation
    total_mm: float
    horizon_hours: int
    threshold_mm: float
    level: str
    signal_type: str
    is_flood_probability: bool
    method: str
    reasons: list[str]
    disclaimer: str
    official_alert: Any | None = None
    official_url: str
    valid_from: str | None = None
    valid_until: str | None = None
    is_expired: bool = False
    last_refresh_failed_at: str | None = None
    last_refresh_error: str | None = None


class OfficialAlertsResponse(BaseModel):
    alerts: list[Any]
    status: str
    source_url: str
    reason: str


class PriceResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    plot_id: str | None = None
    market: str
    commodity: str
    price: str
    unit: str
    price_type: str
    grade: str
    observed_at: str
    meta: ProvenanceMeta


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    price_id: str
    plot_id: str | None = None
    harvested_kg: Decimal = Field(gt=0, le=Decimal('1000000'))
    loss_fraction: Decimal = Field(default=Decimal('0'), ge=0, lt=1)
    transport_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))
    handling_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))
    fees_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))


class RouteCostOverride(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transport_bdt: Decimal = Field(ge=0, le=Decimal('100000000'))
    handling_bdt: Decimal = Field(ge=0, le=Decimal('100000000'))
    fees_bdt: Decimal = Field(ge=0, le=Decimal('100000000'))


class ComparisonScenarioInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plot_id: str
    price_type: Literal['wholesale', 'retail', 'farm-gate']
    price_ids: list[str] = Field(min_length=1, max_length=50)
    harvested_kg: Decimal = Field(gt=0, le=Decimal('1000000'))
    loss_fraction: Decimal = Field(default=Decimal('0'), ge=0, lt=1)
    transport_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))
    handling_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))
    fees_bdt: Decimal = Field(..., ge=0, le=Decimal('100000000'))
    route_costs: dict[str, RouteCostOverride] | None = None


class ComparisonItemResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str | None = None
    price_id: str | None = None
    plot_id: str | None = None
    market: str
    commodity: str | None = None
    price_type: str | None = None
    grade: str | None = None
    unit_price_bdt: str | None = None
    observed_at: str | None = None
    saleable_kg: str
    gross_bdt: str
    costs_bdt: str
    net_bdt: str
    formula: str
    assumptions: dict[str, Any]
    disclaimer: str
    meta: ProvenanceMeta


class ComparisonScenarioResponse(BaseModel):
    id: str
    created_at: str
    plot_id: str
    plot_name: str
    commodity: str
    price_type: str
    cost_mode: Literal['shared_equal_costs', 'route_specific_costs']
    cost_limitation: str
    assumptions: dict[str, Any]
    items: list[ComparisonItemResponse]
    best_net_bdt: str
    best_market: str
    disclaimer: str
    meta: ProvenanceMeta


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    status: Literal['accepted', 'rejected'] = 'accepted'
    imported: int
    duplicates: int
    errors: list[ImportRowError]
    source_name: str
    source_url: str
    checksum: str


class WatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    market: str = Field(min_length=1, max_length=100)
    commodity: str = Field(default='tomato', min_length=1, max_length=60)
    price_type: Literal['wholesale', 'retail', 'farm-gate'] = 'wholesale'
    target_bdt: Decimal = Field(gt=0, le=Decimal('100000'))


class WatchPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_bdt: Decimal | None = Field(default=None, gt=0, le=Decimal('100000'))
    price_type: Literal['wholesale', 'retail', 'farm-gate'] | None = None


class WatchResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    market: str
    commodity: str = 'tomato'
    price_type: str = 'wholesale'
    target_bdt: str
    latest_observed_bdt: str | None = None
    latest_observed_at: str | None = None
    target_met_in_saved_quotes: bool | None = None
    monitoring_active: bool = False
    delivery_mode: str = 'saved_target_only'
    notice: str = 'Saved price target only. Automatic market monitoring and external alerts are not active.'


class ForecastDisabledResponse(BaseModel):
    enabled: bool = False
    reason: str


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['open', 'done', 'snoozed']
    comment: str = Field(default='', max_length=2000)
    snooze_hours: int | None = Field(default=None, ge=1, le=720)
    snoozed_until: AwareDatetime | None = None


class ActionResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    plot_id: str | None = None
    source_record_id: str | None = None
    topic: str
    title: str
    reason: str
    status: Literal['open', 'done', 'snoozed']
    comment: str = ''
    snoozed_until: str | None = None
    evidence_fingerprint: str | None = None
    meta: ProvenanceMeta


class ActionCenterEvidence(BaseModel):
    case: list[CaseResponse] = Field(default_factory=list)
    weather: list[WeatherOutlookResponse] = Field(default_factory=list)
    comparison: list[ComparisonScenarioResponse] = Field(default_factory=list)


class ActionCenterResponse(BaseModel):
    plot_id: str
    plot_name: str
    crop: str
    case_count: int
    actions: list[ActionResponse]
    evidence: ActionCenterEvidence
    market_evidence: list[PriceResponse]
    meta: ProvenanceMeta


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    plot_id: str | None = None
    plot_name: str | None = None
    action_id: str | None = None
    source_record_id: str | None = None
    topic: str | None = None
    target_route: str | None = None
    title: str
    read: bool


class AuditEventResponse(BaseModel):
    id: str
    created_at: str
    plot_id: str | None = None
    event: str
    record_id: str | None = None


class DeviceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    plot_id: str


class DeviceProvisionResponse(BaseModel):
    id: str
    key: str
    plot_id: str
    key_version: int = 1
    rotated_at: str | None = None


class Measurements(BaseModel):
    model_config = ConfigDict(extra='forbid')
    soil_moisture_adc: int | None = Field(default=None, ge=0, le=65535)
    air_temperature_c: float | None = Field(default=None, ge=-50, le=80)
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    rainfall_mm_interval: float | None = Field(default=None, ge=0, le=2000)

    def has_any_value(self) -> bool:
        return any(
            v is not None
            for v in (
                self.soil_moisture_adc,
                self.air_temperature_c,
                self.relative_humidity_pct,
                self.rainfall_mm_interval,
            )
        )


class SensorInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['1.0']
    event_id: str = Field(min_length=1, max_length=100)
    device_id: str
    plot_id: str
    timestamp: AwareDatetime
    source_type: Literal['simulator', 'esp32', 'historical', 'heartbeat']
    measurements: Measurements = Field(default_factory=Measurements)
    calibration_id: str | None = Field(default=None, max_length=120)


class DeviceReadingPayload(BaseModel):
    model_config = ConfigDict(extra='allow')
    event_id: str
    timestamp: str
    source_type: str
    measurements: dict[str, int | float | None]
    units: dict[str, str] = Field(default_factory=dict)
    calibration_id: str | None = None
    calibration_verified: bool = False
    quality_flags: list[str] = Field(default_factory=list)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    created_at: str
    updated_at: str | None = None
    plot_id: str | None = None
    name: str
    status: str
    revoked: bool = False
    key_version: int = 1
    last_heartbeat_at: str | None = None
    last_reading: DeviceReadingPayload | None = None
    last_historical_reading: DeviceReadingPayload | None = None


class SensorIngestResponse(BaseModel):
    id: str | None = None
    duplicate: bool
    quality_flags: list[str] = Field(default_factory=list)
    stored_as_historical: bool = False
    status: str | None = None


class DeviceReadingHistoryItem(BaseModel):
    id: str
    device_id: str
    plot_id: str | None = None
    event_id: str
    event_timestamp: str | None = None
    source_type: str | None = None
    created_at: str | None = None
    measurements: dict[str, int | float | None]
    units: dict[str, str] = Field(default_factory=dict)
    calibration_id: str | None = None
    calibration_verified: bool = False
    quality_flags: list[str] = Field(default_factory=list)


class ProvidersStatusResponse(BaseModel):
    weather: dict[str, Any]
    flood: dict[str, Any]
    market: dict[str, Any]
    model: ModelCardResponse


class EvaluationsResponse(BaseModel):
    model: ModelCardResponse
    metrics: dict[str, Any] | None = None
    field_validation: str


class ExportedRecord(BaseModel):
    id: str
    kind: str
    plot_id: str | None = None
    farm_id: str | None = None
    source_record_id: str | None = None
    created_at: str
    updated_at: str | None = None
    payload: dict[str, Any]


class WorkspaceExportResponse(BaseModel):
    schema_version: str = '2.0'
    exported_at: str
    timezone: str = 'UTC'
    contains_image_binaries: bool = False
    image_export_note: str
    user: UserResponse
    records_by_kind: dict[str, int]
    records: list[ExportedRecord]
    sensor_readings: list[DeviceReadingHistoryItem]
    relationships: dict[str, str]
