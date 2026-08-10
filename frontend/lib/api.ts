/** Typed REST client.
 *
 * Every call carries a bearer token. There is no client-side simulation state
 * of any consequence: the server owns the dataset, the thesis lock, the
 * telemetry and the score. What lives here is UI state and a cache.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PREFIX = "/api/v1";
const TOKEN_KEY = "meridian.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { silent?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${PREFIX}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? (detail[0]?.msg ?? "Request failed")
          : (detail?.message ?? `Request failed (${res.status})`);
    if (!opts.silent) console.warn(`${method} ${path} -> ${res.status}: ${message}`);
    throw new ApiError(res.status, message, detail);
  }
  return data as T;
}

export const api = {
  get: <T,>(p: string, o?: { silent?: boolean }) => request<T>("GET", p, undefined, o),
  post: <T,>(p: string, b?: unknown, o?: { silent?: boolean }) => request<T>("POST", p, b, o),
  put: <T,>(p: string, b?: unknown, o?: { silent?: boolean }) => request<T>("PUT", p, b, o),
  patch: <T,>(p: string, b?: unknown, o?: { silent?: boolean }) => request<T>("PATCH", p, b, o),
};

export function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
    else sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// -------------------------------------------------------------------------
// Types mirrored from the API
// -------------------------------------------------------------------------
export type ScreenKey =
  | "brief" | "dashboard" | "research" | "thesis" | "committee" | "deliberation"
  | "inbox" | "evidence" | "model" | "dealflow" | "results" | "debrief"
  | "scorecard" | "report";

export interface Variable { key: string; label: string }

export interface AppConfig {
  inr_rate: number;
  deliberation_seconds: number;
  variables: Variable[];
  continuous_metrics: { key: string; label: string; unit: string; lower_is_better: boolean }[];
  screens: { key: ScreenKey; label: string }[];
  max_thesis_variables: number;
  cheques: number;
}

export interface User {
  id: string; email: string; name: string; role: string;
  photo_url: string | null; cohort_id: string | null;
}

export interface CompanyRow {
  id: number; name: string; sector: string; city: string; founded_year: number;
  arr_usd: number; month6_retention: number; headcount: number;
  ltv_cac_ratio: number; burn_multiple: number; flags: string;
}

export interface DeepProfile {
  founded: number; report_year: number; history_years: number;
  customers: number; arpu_monthly_usd: number; cac_usd: number; ltv_usd: number;
  ltv_cac_ratio: number; cac_payback_months: number; monthly_churn: number;
  avg_customer_lifetime_months: number; gross_margin: number;
  net_revenue_retention: number; annual_net_burn_usd: number;
  financial_history: { year: number; revenue_usd: number; headcount: number; net_burn_usd: number }[];
  funding: {
    seed_usd: number; seed_investor: string; seed_year: number;
    series_a_usd: number; series_a_investor: string; series_a_year: number;
    has_series_b: boolean; series_b_usd: number; series_b_investor: string | null;
    series_b_year: number | null; total_raised_usd: number; tier_one_seed: boolean;
  };
  economic_position: {
    customer_equity_usd: number; customer_equity_plus_paid_in_usd: number; ratio: number;
  };
  computed_ratios: {
    deficit_to_arr: number; deferred_revenue_to_arr_pct: number;
    runway_months: number; top10_concentration_pct: number; burn_multiple: number | null;
  };
  gtm: { pricing: string; segment: string; motion: string };
  cohorts: number[][];
  dept_spend: {
    rnd: number; sales_marketing: number; customer_success: number;
    general_admin: number; annual_opex_usd: number;
  };
  cap_table: { founders: number; option_pool: number; seed: number; series_a: number; series_b: number };
  founders: {
    ceo_name: string; ceo_background: string;
    cto_name: string | null; cto_background: string | null;
  };
  press: { headline: string; publication: string; year: number; amount_usd: number }[];
  reviews: { department: string; rating: number; quote: string }[];
  market: {
    your_share_pct: number; segment: string; other_pct: number;
    competitors: { name: string; share_pct: number }[];
  };
  releases: { title: string; quarter: number; year: number }[];
  customer_interviews: { role: string; quote: string }[];
  flavour_minutes: { label: string; text: string }[];
}

export interface CompanyProfile extends CompanyRow {
  flag_map: Record<string, boolean>;
  gross_margin: number; net_revenue_retention: number; cac_payback_months: number;
  arpu_monthly_usd: number; customers: number; monthly_churn: number;
  avg_customer_lifetime_months: number; ltv_usd: number; cac_usd: number;
  annual_payroll_usd: number; gtm_spend_usd: number; overhead_usd: number;
  annual_opex_usd: number; gross_profit_annual_usd: number;
  annual_net_burn_usd: number; net_new_arr_usd: number; growth_rate: number;
  total_raised_usd: number; cash_on_hand_usd: number; runway_months: number;
  balance_sheet: Record<string, number>;
  balance_sheet_ties: boolean;
  competitors: string[];
  deep: DeepProfile;
}

export interface VariableEvidence {
  archive_unlocked: boolean;
  portfolio_count: number;
  archive_count: number | null;
  rows: {
    key: string; label: string;
    count_portfolio: number; pct_portfolio: number;
    win_rate_with: number | null; win_rate_without: number | null; lift: number | null;
  }[];
}

export interface SessionState {
  session_id: string;
  current_screen: ScreenKey;
  furthest_screen: ScreenKey;
  rail: { key: ScreenKey; label: string; state: "done" | "current" | "pending" }[];
  thesis_locked: boolean;
  thesis_variables: string[] | null;
  thesis_confidence: Record<string, number> | null;
  falsification: string | null;
  archive_unlocked: boolean;
  committee_answered: number;
  committee_total: number;
  deliberation_remaining: number;
  model_weights: Record<string, number> | null;
  picks: number[];
  deployed: boolean;
  summary: {
    total_companies: number; median_arr_usd: number; median_retention: number;
    median_ltv_cac: number; archive_unlocked: boolean;
    archive_records?: number; combined_records?: number;
  };
}

export interface Deal extends CompanyRow {
  flag_map: Record<string, boolean>;
  gross_margin: number; net_revenue_retention: number; cac_payback_months: number;
  model_score: number; model_rank: number; outcome?: number;
}

export interface Dimension {
  key: string; label: string; score: number; max: number;
  detail: string; components: Record<string, unknown>;
}

/** A dimension the simulation has no mechanic to evidence. Reported as an
 *  explicit N/A card rather than scored zero or silently dropped. */
export interface NotApplicableDimension {
  key: string; label: string; score: null; max: null; detail: string;
}

export interface MyelinScorecard {
  dimensions: Dimension[];
  not_applicable: NotApplicableDimension[];
  total: number; max: number; band: string;
}

export interface ScorecardData {
  dimensions: Dimension[];
  total: number; max: number; band: string;
  myelin: MyelinScorecard;
  committee_analysis: {
    per_answer: { signals: string[]; matches: Record<string, string> }[];
    falsification: { signals: string[]; matches: Record<string, string> };
    aggregate_signals: string[];
  };
  fund: FundResult | null;
  telemetry: Record<string, unknown>;
}

export interface FundResult {
  rows: {
    id: number; name: string; sector: string; cheque_usd: number;
    share_of_fund?: number; outcome: string; returned_usd: number;
  }[];
  deployed_usd: number; returned_usd: number; net_usd: number;
  hits: number; cheques: number;
  missed_winners: { id: number; name: string; sector: string }[];
  scored: boolean; note: string;
}

export interface TruthRow {
  feature: string; label: string; class: string;
  pct_winners: number; pct_failures_visible: number; pct_failures_complete: number;
  visible_lift: number; true_lift: number; rank_by_frequency: number;
  stated_confidence?: number;
}

export interface DebriefData {
  mirror: TruthRow[];
  falsification: string | null;
  causal_variables: TruthRow[];
  continuous_truth: {
    key: string; label: string; unit: string; lower_is_better: boolean;
    win_mean: number; win_median: number; fail_mean: number; fail_median: number;
  }[];
  naive_top5: TruthRow[];
  full_truth: TruthRow[];
  fund: FundResult;
  fund_distribution: {
    strategy: string; mean_wins: number; p_zero_wins: number;
    p_three_plus: number; distribution: number[];
  }[];
  portfolio_count: number; archive_visible: number; archive_complete: number;
  withheld_count: number; share_of_evidence_seen: number; withhold_note: string;
}
