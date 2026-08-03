"""The single canonical financial model.

Open Issue 1 in the handoff was that three subsystems each re-derived LTV, CAC
and burn independently, so the same company showed 1.7x in the Explorer table
and 0.58x on its own profile page. That is fixed here by construction: every
dollar figure anywhere in the product is produced by this module, once, at
dataset build time, and every consumer reads the stored value. Nothing
downstream is permitted to recompute a financial metric from scratch.

All identities below are the ones quoted in Part 2.6 of the handoff:

    monthly_churn             = 1 - month6_retention ** (1/6)
    avg_customer_lifetime_mo  = 1 / monthly_churn
    ltv_usd                   = arpu_monthly * gross_margin * lifetime_months
    cac_usd                   = arpu_monthly * gross_margin * cac_payback_months
    ltv_cac_ratio             = ltv_usd / cac_usd
    annual_net_burn_usd       = annual_opex_usd - gross_profit_annual_usd
    runway_months             = cash_on_hand_usd / (annual_net_burn_usd / 12)

Note that ltv_cac_ratio reduces exactly to lifetime_months / cac_payback_months.
That is not a coincidence to be papered over -- it is the reason a student with a
spreadsheet cannot catch the dataset contradicting itself.

The balance sheet is assembled in integer cents and equity is *defined* as
assets minus liabilities, so the accounting identity ties to the cent for every
company rather than approximately.
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------
# Operating-model constants
# --------------------------------------------------------------------------
# Tuned so that burn multiple discriminates: lean companies land near 3.5x,
# companies that doubled headcount post-Series A near 6.3x. See
# `validate.burn_multiple_report` for the check that keeps these honest.
REVENUE_PER_HEAD_USD = 19_500.0
FULLY_LOADED_COST_PER_HEAD_USD = 40_000.0
HEADCOUNT_2X_MULTIPLIER = 1.9
NON_PAYROLL_OVERHEAD_FRACTION = 0.12  # of payroll: rent, cloud, G&A
DSO_MONTHS = 1.5
DEFERRED_REVENUE_FRACTION = 0.22
FIXED_ASSETS_PER_HEAD_USD = 1_100.0
BURN_MULTIPLE_CAP = 25.0


def _cents(x: np.ndarray) -> np.ndarray:
    """Round a USD array to whole cents as int64."""
    return np.rint(x * 100.0).astype(np.int64)


def derive(
    rng: np.random.Generator,
    *,
    outcome: np.ndarray,
    month6_retention: np.ndarray,
    gross_margin: np.ndarray,
    cac_payback_months: np.ndarray,
    net_revenue_retention: np.ndarray,
    headcount_2x: np.ndarray,
    expansion_customer_led: np.ndarray,
    usage_based_pricing: np.ndarray,
    series_a_above_20m: np.ndarray,
) -> dict[str, np.ndarray]:
    """Derive every financial figure for a whole population at once.

    Returns a dict of parallel arrays. Callers must not recompute any of these.
    """
    n = outcome.shape[0]

    # ---- Top line -------------------------------------------------------
    # ARR is drawn independently of outcome: it must not become a hidden signal.
    # A winner and a failure of the same size should look the same on revenue.
    arr_usd = np.exp(rng.normal(np.log(1_800_000.0), 0.75, n))
    arr_usd = np.clip(arr_usd, 150_000.0, 12_000_000.0)

    # Usage-based pricing implies smaller, more numerous contracts.
    arpu_monthly = np.exp(rng.normal(np.log(800.0), 0.55, n))
    arpu_monthly = np.where(usage_based_pricing == 1, arpu_monthly * 0.65, arpu_monthly)
    arpu_monthly = np.clip(arpu_monthly, 60.0, 25_000.0)

    customers = np.maximum(np.rint(arr_usd / (arpu_monthly * 12.0)), 5.0)

    # ---- Unit economics -- the quoted identities, in order --------------
    monthly_churn = 1.0 - np.power(month6_retention, 1.0 / 6.0)
    monthly_churn = np.clip(monthly_churn, 1e-4, 0.60)
    avg_customer_lifetime_months = 1.0 / monthly_churn

    ltv_usd = arpu_monthly * gross_margin * avg_customer_lifetime_months
    cac_usd = arpu_monthly * gross_margin * cac_payback_months
    ltv_cac_ratio = ltv_usd / cac_usd

    # ---- Cost structure -------------------------------------------------
    headcount = arr_usd / REVENUE_PER_HEAD_USD
    headcount = np.where(headcount_2x == 1, headcount * HEADCOUNT_2X_MULTIPLIER, headcount)
    headcount = np.clip(np.rint(headcount), 8.0, 900.0)

    annual_payroll_usd = headcount * FULLY_LOADED_COST_PER_HEAD_USD

    # Growth decomposes into expansion (NRR) plus new logos. Customer-led
    # expansion buys new logos more cheaply, which is exactly why it is causal.
    new_logo_rate = rng.uniform(0.18, 0.55, n)
    new_logo_rate = np.where(expansion_customer_led == 1, new_logo_rate * 1.35, new_logo_rate)
    growth_rate = (net_revenue_retention - 1.0) + new_logo_rate

    new_customers_annual = np.maximum(customers * new_logo_rate, 1.0)
    gtm_spend_usd = new_customers_annual * cac_usd
    # Customer-led expansion means less of the pipeline is bought.
    gtm_spend_usd = np.where(
        expansion_customer_led == 1, gtm_spend_usd * 0.70, gtm_spend_usd
    )

    overhead_usd = annual_payroll_usd * NON_PAYROLL_OVERHEAD_FRACTION
    annual_opex_usd = annual_payroll_usd + gtm_spend_usd + overhead_usd

    gross_profit_annual_usd = arr_usd * gross_margin
    annual_net_burn_usd = annual_opex_usd - gross_profit_annual_usd

    net_new_arr_usd = arr_usd * growth_rate

    # Burn multiple is undefined when a company is not adding ARR. Rather than
    # emit a nonsense number, flag it and cap the tail.
    burn_multiple_defined = net_new_arr_usd > (arr_usd * 0.02)
    with np.errstate(divide="ignore", invalid="ignore"):
        burn_multiple = np.where(
            burn_multiple_defined,
            annual_net_burn_usd / np.where(net_new_arr_usd == 0, 1.0, net_new_arr_usd),
            np.nan,
        )
    burn_multiple = np.clip(burn_multiple, -BURN_MULTIPLE_CAP, BURN_MULTIPLE_CAP)

    # ---- Capital and runway --------------------------------------------
    # Scaled to revenue rather than drawn free-standing. An independent draw
    # produced companies with $0.7M of ARR that had raised $12M across a Series
    # B -- arithmetically fine, but a student reads that and stops believing the
    # dataset. The series_a_above_20m flag still does its work as a Class C
    # reverse trap; it now shifts a distribution instead of replacing it.
    raise_multiple = np.where(
        series_a_above_20m == 1,
        rng.uniform(6.0, 14.0, n),
        rng.uniform(3.0, 9.0, n),
    )
    total_raised_usd = arr_usd * raise_multiple
    total_raised_usd = np.where(
        series_a_above_20m == 1,
        np.maximum(total_raised_usd, 20_000_000.0),
        np.clip(total_raised_usd, 2_000_000.0, 20_000_000.0),
    )
    runway_target = rng.uniform(9.0, 30.0, n)
    monthly_burn = annual_net_burn_usd / 12.0
    cash_on_hand_usd = np.where(
        monthly_burn > 0,
        monthly_burn * runway_target,
        total_raised_usd * rng.uniform(0.25, 0.60, n),
    )
    cash_on_hand_usd = np.minimum(cash_on_hand_usd, total_raised_usd * 0.85)
    cash_on_hand_usd = np.maximum(cash_on_hand_usd, 50_000.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        runway_months = np.where(
            monthly_burn > 0, cash_on_hand_usd / monthly_burn, np.inf
        )
    runway_months = np.clip(runway_months, 0.0, 120.0)

    # ---- Balance sheet, in integer cents --------------------------------
    cash_c = _cents(cash_on_hand_usd)
    ar_c = _cents(arr_usd / 12.0 * DSO_MONTHS)
    prepaid_c = _cents(annual_opex_usd / 12.0 * 0.5)
    fixed_c = _cents(headcount * FIXED_ASSETS_PER_HEAD_USD)
    total_assets_c = cash_c + ar_c + prepaid_c + fixed_c

    ap_c = _cents(annual_opex_usd / 12.0 * 0.7)
    accrued_payroll_c = _cents(annual_payroll_usd / 12.0 * 0.5)
    deferred_rev_c = _cents(arr_usd * DEFERRED_REVENUE_FRACTION)
    venture_debt_c = _cents(
        np.where(rng.random(n) < 0.22, total_raised_usd * rng.uniform(0.05, 0.20, n), 0.0)
    )
    total_liabilities_c = ap_c + accrued_payroll_c + deferred_rev_c + venture_debt_c

    # Equity is defined, not drawn. This is what makes the identity exact.
    total_equity_c = total_assets_c - total_liabilities_c
    paid_in_capital_c = _cents(total_raised_usd)
    accumulated_deficit_c = paid_in_capital_c - total_equity_c

    return {
        "arr_usd": arr_usd,
        "arpu_monthly_usd": arpu_monthly,
        "customers": customers,
        "monthly_churn": monthly_churn,
        "avg_customer_lifetime_months": avg_customer_lifetime_months,
        "ltv_usd": ltv_usd,
        "cac_usd": cac_usd,
        "ltv_cac_ratio": ltv_cac_ratio,
        "headcount": headcount,
        "annual_payroll_usd": annual_payroll_usd,
        "gtm_spend_usd": gtm_spend_usd,
        "overhead_usd": overhead_usd,
        "annual_opex_usd": annual_opex_usd,
        "gross_profit_annual_usd": gross_profit_annual_usd,
        "annual_net_burn_usd": annual_net_burn_usd,
        "net_new_arr_usd": net_new_arr_usd,
        "growth_rate": growth_rate,
        "burn_multiple": burn_multiple,
        "total_raised_usd": total_raised_usd,
        "cash_on_hand_usd": cash_on_hand_usd,
        "runway_months": runway_months,
        # Balance sheet (integer cents)
        "bs_cash_c": cash_c,
        "bs_accounts_receivable_c": ar_c,
        "bs_prepaid_c": prepaid_c,
        "bs_fixed_assets_c": fixed_c,
        "bs_total_assets_c": total_assets_c,
        "bs_accounts_payable_c": ap_c,
        "bs_accrued_payroll_c": accrued_payroll_c,
        "bs_deferred_revenue_c": deferred_rev_c,
        "bs_venture_debt_c": venture_debt_c,
        "bs_total_liabilities_c": total_liabilities_c,
        "bs_total_equity_c": total_equity_c,
        "bs_paid_in_capital_c": paid_in_capital_c,
        "bs_accumulated_deficit_c": accumulated_deficit_c,
    }


def check_balance_sheet(fin: dict[str, np.ndarray]) -> tuple[bool, int]:
    """Assert assets == liabilities + equity for every company, to the cent.

    Returns (ok, worst_absolute_discrepancy_in_cents).
    """
    lhs = fin["bs_total_assets_c"]
    rhs = fin["bs_total_liabilities_c"] + fin["bs_total_equity_c"]
    diff = np.abs(lhs - rhs)
    worst = int(diff.max()) if diff.size else 0

    equity_lhs = fin["bs_total_equity_c"]
    equity_rhs = fin["bs_paid_in_capital_c"] - fin["bs_accumulated_deficit_c"]
    equity_diff = np.abs(equity_lhs - equity_rhs)
    worst = max(worst, int(equity_diff.max()) if equity_diff.size else 0)

    return worst == 0, worst
