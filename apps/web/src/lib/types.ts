export type Meta = {
  mode: string;
  source_name: string;
  source_type?: string;
  source_url?: string;
  is_simulated: boolean;
  observed_at?: string | null;
  retrieved_at?: string | null;
  issued_at?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  freshness?: string;
  attribution?: string;
  quality_flags?: string[];
  permission_confirmed?: boolean;
};

export type Preferences = {
  language: 'en' | 'bn';
  theme: 'light' | 'dark';
  retraining_consent: boolean;
  selected_plot_id?: string | null;
};

export type User = {
  id: string;
  name: string;
  role: 'farmer'|'customer'|'admin';
  email?: string|null;
  is_active?: boolean;
  preferences: Preferences;
};

export type Farm = {
  id: string;
  name: string;
  district: string;
  latitude?: number | null;
  longitude?: number | null;
  location_consent: boolean;
  location_name?: string | null;
  country?: string | null;
  meta?: Meta;
};

export type Plot = {
  id: string;
  name: string;
  farm_id: string;
  crop: string;
  area_acres: string;
  stage: string;
  low_lying: boolean;
  sowing_date?: string | null;
  meta?: Meta;
};

export type Action = {
  id: string;
  title: string;
  topic: string;
  reason: string;
  status: 'open' | 'done' | 'snoozed' | string;
  comment?: string;
  snoozed_until?: string | null;
  evidence_fingerprint?: string | null;
  source_record_id?: string | null;
  plot_id?: string | null;
  meta: Meta;
};

export type Feedback = {
  id: string;
  created_at: string;
  case_id: string;
  note: string;
  request_review: boolean;
  advisor_contacted?: boolean;
  review_notice?: string;
};

export type Case = {
  crop: string;
  id: string;
  created_at: string;
  updated_at?: string | null;
  plot_id?: string | null;
  plot_name?: string | null;
  status: string;
  symptoms: string;
  quality_flags: string[];
  classification: {
    top_label: string;
    abstained: boolean;
    score: number | null;
    score_type: string;
    alternatives: {label: string; score: number}[];
    ood_notice?: string | null;
    rejection_reason?: string | null;
  };
  model: Model;
  advice: string[];
  disclaimer: string;
  feedback?: Feedback[];
  image_available?: boolean;
  meta: Meta;
};

export type PaginatedCases = {
  items: Case[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
};

export type Model = {
  model_id?: string;
  source_url?: string;
  revision?: string;
  version: string;
  available: boolean;
  field_validated: boolean;
  artifact_status?: string;
  artifact_error?: string | null;
  labels: string[];
  metrics: Record<string, number> | null;
  limitations: string[];
  source?: string;
  threshold?: number | null;
};

export type CropCapability = {
  id: string;
  name_en: string;
  name_bn: string;
  available: boolean;
  model_id: string;
  model_version: string;
  artifact_status: string;
  has_healthy_class: boolean;
  labels: string[];
  limitations: string[];
};
export type DoctorCapabilities = {
  crops: CropCapability[];
  models: Model[];
  limitations: string[];
  automatic_crop_detection: boolean;
};

export type Price = {
  id: string;
  market: string;
  commodity: string;
  price: string;
  unit: string;
  price_type: string;
  grade: string;
  observed_at: string;
  meta: Meta;
};

export type Weather = {
  hourly: {time: string; rain_mm: number}[];
  meta: Meta;
  total_mm: number;
  level: string;
  horizon_hours: number;
  threshold_mm: number;
  reasons: string[];
  disclaimer: string;
  location: {lat: number; lon: number};
  valid_from?: string | null;
  valid_until?: string | null;
  is_expired?: boolean;
  last_refresh_failed_at?: string | null;
  last_refresh_error?: string | null;
};

export type Device = {
  id: string;
  name: string;
  plot_id: string;
  status: string;
  revoked?: boolean;
  key_version?: number;
  last_heartbeat_at?: string | null;
  last_reading?: {
    source_type: string;
    timestamp?: string;
    measurements: Record<string, number | null>;
    units?: Record<string, string>;
    quality_flags: string[];
    calibration_verified?: boolean;
  } | null;
};

export type Watch = {
  id: string;
  market: string;
  commodity: string;
  price_type: string;
  target_bdt: string;
  monitoring_active: boolean;
  delivery_mode: string;
  notice: string;
};

export type NotificationItem = {
  id: string;
  title: string;
  read: boolean;
  plot_id?: string | null;
  plot_name?: string | null;
  action_id?: string | null;
  target_route?: string | null;
  topic?: string | null;
  created_at?: string;
};

export type ComparisonItem = {
  market: string;
  net_bdt: string;
  gross_bdt: string;
  saleable_kg: string;
  price_id?: string;
  assumptions?: Record<string, unknown>;
  meta: Meta;
};

export type ComparisonScenario = {
  id: string;
  plot_id: string;
  plot_name: string;
  price_type: string;
  cost_mode: string;
  cost_limitation: string;
  assumptions: Record<string, unknown>;
  items: ComparisonItem[];
  best_net_bdt: string;
  best_market: string;
  disclaimer: string;
  meta: Meta;
};

export type ActionCenter = {
  plot_id: string;
  plot_name: string;
  crop: string;
  case_count: number;
  actions: Action[];
  evidence: {
    case: Case[];
    weather: Weather[];
    comparison?: ComparisonScenario[];
  };
  market_evidence: Price[];
  meta: Meta;
};
