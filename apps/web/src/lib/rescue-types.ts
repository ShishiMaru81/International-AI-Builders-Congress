import type {Meta} from './types';

/** Decimal quantities and BDT amounts remain strings all the way to the API. */
export type RescueOptionInput = {
 label: string;
 price_id?: string;
 price_bdt?: string;
 transport_bdt: string | null;
 handling_bdt: string;
 fees_bdt: string;
 confirmed: boolean;
};
export type RescueInput = {
 plot_id: string;
 harvested_kg: string;
 ready_to_sell: boolean | null;
 cold_storage: boolean | null;
 scenario_mode: 'USER' | 'DEMO';
 hold_price_bdt?: string | null;
 hold_loss_pct?: string | null;
 storage_cost_bdt?: string | null;
 options: RescueOptionInput[];
};
export type RescueSource = Partial<Meta> & {source_name?: string};
export type RescueWeather = {
 id?: string;
 meta?: RescueSource;
 level?: string;
 total_mm?: number | string;
 horizon_hours?: number;
 valid_from?: string | null;
 valid_until?: string | null;
 is_expired?: boolean;
 last_refresh_failed_at?: string | null;
 last_refresh_error?: string | null;
 notice?: string;
};
export type RescueCase = {
 id: string;
 created_at?: string;
 status?: string;
 classification?: {abstained?: boolean; top_label?: string};
 meta?: RescueSource;
 notice?: string;
};
export type RescuePlan = {
 id: string;
 plot_id: string;
 created_at: string;
 commodity: string;
 method: 'symbolic_constraint_planner_v1';
 status: 'ready' | 'needs_information' | 'no_feasible_option';
 recommended_option_id: string | null;
 options: {
  id: string;
  label: string;
  kind: 'sell_now' | 'hold';
  feasible: boolean;
  net_bdt: string | null;
  gross_bdt: string | null;
  costs_bdt: string | null;
  saleable_kg: string | null;
  reasons: string[];
  meta: RescueSource;
 }[];
 questions: {code: string; text: string; break_even_transport_bdt?: string | null}[];
 warnings: string[];
 evidence: {weather: RescueWeather | null; case: RescueCase | null};
 assumptions: RescueInput;
 disclaimer: string;
 snapshot_notice?: string;
};
