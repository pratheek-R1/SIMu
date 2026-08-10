"""Deep company profiles.

Ported from `getDeepData` in the original single-file prototype (removed once
the port was complete), with one structural
change: nothing here draws a financial figure. Every number is read from the
canonical model in finance.py, or derived from it arithmetically. The client
version drew its own -- `cac = srI(s+5020, 3000, 180000)` independent of the
LTV/CAC already on the row, `grossMargin` by sector, `nrr` uniform on 88..148 --
which meant three things went wrong at once:

  * the balance sheet did not tie (total assets and liabilities+equity were
    computed from unrelated draws);
  * CAC payback contradicted the LTV/CAC shown one row above it;
  * gross margin and NRR carried no signal at all, even though both are Class A
    causal variables in the design.

The second structural rule: every narrative element must AGREE with the
company's flags. If a company does not carry `pressYear1` it gets no year-one
press. If it carries `usageBased` its pricing model says usage-based. This is
not decoration -- the Triangulation dimension measures whether a student can
find the planted contradiction between the board minutes and the founder
interview, and that measurement is worthless if the profile is riddled with
accidental contradictions the generator never intended.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import parameters as P

# --------------------------------------------------------------------------
# Content pools -- taken from the client file
# --------------------------------------------------------------------------
FOUNDER_FIRST = (
    "Sarah", "Arjun", "Priya", "Rohan", "Meera", "Karan", "Ananya", "Vikram",
    "Neha", "Aditya", "Ishaan", "Diya", "Kabir", "Tara", "Aryan", "Riya",
    "Dev", "Simran", "Nikhil", "Pooja", "Rahul", "Aisha", "Varun", "Leela",
)
FOUNDER_LAST = (
    "Whitfield", "Raghavan", "Mehta", "Kapoor", "Iyer", "Bose", "Chandra",
    "Nair", "Rao", "Sharma", "Verma", "Malhotra", "Reddy", "Joshi", "Sinha",
    "Bhatt", "Desai", "Menon", "Pillai", "Gupta",
)

# Split by whether the founder actually has domain tenure. The `founder5yrs`
# flag is the single strongest real signal in the dataset, so its background
# copy must never contradict it.
CEO_BG_TENURED = (
    "Spent seven years inside this category before starting the company.",
    "Ran the function they now sell into for most of a decade.",
    "Was a practitioner in this market long before there was a product.",
)
CEO_BG_UNTENURED = (
    "Built the first version alone before hiring anyone.",
    "Started the company right out of college.",
    "Left a stable enterprise job to chase this idea.",
    "Spent three years in consulting before switching to founding.",
)
CTO_BG = (
    "Previously engineering lead at a logistics startup.",
    "Shipped infra at a major consumer internet company.",
    "Was the third engineer at a well-known SaaS company.",
    "Came from an ML research background.",
    "Built and sold a small dev-tools company before this.",
)

TIER_ONE_SEED = ("Blume Ventures", "Titan Capital", "India Quotient", "Sequoia Surge", "Accel Atoms")
OTHER_SEED = ("Ninefold", "Antler", "Prime Venture Partners", "3one4 Capital", "Better Capital")
SERIES_A_INVESTORS = (
    "Vanterra", "Accel", "Lightspeed", "Matrix Partners",
    "Nexus Venture Partners", "Kalaari Capital", "Norwest Venture Partners",
)
SERIES_B_INVESTORS = (
    "Benchmark", "Tiger Global", "SoftBank Vision Fund",
    "General Atlantic", "Insight Partners", "Steadview Capital",
)
PUBLICATIONS = (
    "TechCrunch", "The Ken", "YourStory", "Entrackr",
    "Inc42", "The Information", "Mint", "Moneycontrol",
)
SEGMENTS = ("SMB", "Mid-market", "Enterprise", "Prosumer")

# Motion copy is selected by the `customerLed` flag, not drawn freely.
MOTION_CUSTOMER_LED = (
    "Inbound and existing-account expansion; no outbound SDR team.",
    "Product-led growth; expansion comes from teams inside existing accounts.",
)
MOTION_SALES_LED = (
    "Outbound-led for new logos, expansion handled by a dedicated sales team.",
    "Channel and partner-led distribution with a direct enterprise sales team.",
)

PRODUCT_TEMPLATES = (
    "General availability", "Consumption billing and usage dashboard",
    "Workflow automation and API v2", "Reporting module — requested by customers",
    "SSO and enterprise security", "Marketplace integrations", "Mobile app launch",
    "AI-assisted onboarding", "Bulk data import/export", "Custom roles and permissions",
)

REVIEW_TEMPLATES: dict[str, tuple[str, ...]] = {
    "Engineering": (
        "Roadmap comes from actual customer calls, which is rarer than it should be. Shipping cadence is steady.",
        "On-call rotation is heavy but the codebase is in decent shape.",
        "Fast-moving team but tech debt is starting to show.",
    ),
    "Sales": (
        "Small team, clear targets. Quota is achievable.",
        "Comp plan changed twice this year, which hurt trust.",
        "Good product-market fit makes this an easy sell.",
    ),
    "Operations": (
        "Salaries are competitive but the burn conversation never stops.",
        "Process is lightweight, sometimes too lightweight.",
        "Leadership is transparent about the numbers, for better or worse.",
    ),
}

CUSTOMER_INTERVIEWS = (
    {"role": "Head of Ops, logistics customer",
     "quote": "We asked them to build the reporting module. Six weeks later it shipped, and we tripled our seat count off the back of it."},
    {"role": "VP Finance, enterprise customer",
     "quote": "Two years in and usage keeps climbing. Renewal was a formality."},
    {"role": "Founder, SMB customer",
     "quote": "Support answers in minutes, not days. That alone justified the price."},
    {"role": "Director of Growth, mid-market customer",
     "quote": "We evaluated three vendors. This was the only one that didn't need a services team to implement."},
)


def _pick(rng: np.random.Generator, pool: tuple) -> Any:
    return pool[int(rng.integers(0, len(pool)))]


def build(
    company: dict[str, Any],
    seed: int,
    competitor_names: list[str],
) -> dict[str, Any]:
    """Deterministic deep profile for one company.

    `competitor_names` are drawn from the failure population by the registry --
    they are the thread a student can pull, because searching for one returns
    nothing from a research set that contains only winners.
    """
    rng = np.random.default_rng(seed * 1_000_003 + company["id"])
    flags = {k: company["flags"][i] == "1" for i, k in enumerate(P.FEATURE_KEYS)}

    founded = company["founded_year"]
    history_years = int(rng.integers(3, 6))
    report_year = founded + history_years

    # ---- Everything financial comes from the canonical model ------------
    arr = company["arr_usd"]
    customers = int(company["customers"])
    arpu = company["arpu_monthly_usd"]
    cac = company["cac_usd"]
    ltv = company["ltv_usd"]
    ltv_cac = company["ltv_cac_ratio"]
    cac_payback = company["cac_payback_months"]
    monthly_churn = company["monthly_churn"]
    gross_margin = company["gross_margin"]
    nrr = company["net_revenue_retention"]
    net_burn = company["annual_net_burn_usd"]
    opex = company["annual_opex_usd"]
    headcount = int(company["headcount"])
    growth = company["growth_rate"]
    total_raised = company["total_raised_usd"]

    # ---- Financial history: back-cast from today ------------------------
    # Revenue is walked backwards along the company's own growth rate, so the
    # last row of the history equals the ARR shown on the profile header.
    rev, head, burn = [arr], [headcount], [net_burn]
    for _ in range(history_years - 1):
        divisor = 1.0 + max(0.15, growth) * float(rng.uniform(0.75, 1.25))
        rev.append(rev[-1] / divisor)
        head.append(max(3, int(round(head[-1] / float(rng.uniform(1.2, 1.9))))))
        burn.append(burn[-1] / float(rng.uniform(1.1, 1.7)))
    rev.reverse(); head.reverse(); burn.reverse()
    financial_history = [
        {
            "year": founded + 1 + i,
            "revenue_usd": round(rev[i], 2),
            "headcount": head[i],
            "net_burn_usd": round(burn[i], 2),
        }
        for i in range(history_years)
    ]

    # ---- Funding: must sum to the canonical total raised ----------------
    # The `seriesA20` flag already drove total_raised in finance.py, so the
    # split below is a decomposition of a number that already exists rather
    # than a fresh draw that could contradict it.
    seed_share = float(rng.uniform(0.06, 0.14))
    # A Series B needs a company big enough to have plausibly raised one. Gating
    # only on a coin flip put Benchmark-led Series Bs into companies with under
    # $1M of ARR.
    has_series_b = total_raised > 22_000_000 or (arr > 2_000_000 and bool(rng.random() < 0.45))
    if has_series_b:
        a_share = float(rng.uniform(0.28, 0.40))
        b_share = 1.0 - seed_share - a_share
    else:
        a_share = 1.0 - seed_share
        b_share = 0.0

    seed_investor = _pick(rng, TIER_ONE_SEED if flags["tierOneInvestor"] else OTHER_SEED)
    series_a_investor = _pick(rng, SERIES_A_INVESTORS)
    series_b_investor = _pick(rng, SERIES_B_INVESTORS) if has_series_b else None

    # The last round absorbs the rounding remainder, so the displayed rounds sum
    # to the displayed total exactly. Rounding each share independently left a
    # cent adrift, which is precisely the kind of thing a student building a
    # spreadsheet finds and then distrusts everything else over.
    seed_usd = round(total_raised * seed_share, 2)
    if has_series_b:
        series_a_usd = round(total_raised * a_share, 2)
        series_b_usd = round(total_raised - seed_usd - series_a_usd, 2)
    else:
        series_a_usd = round(total_raised - seed_usd, 2)
        series_b_usd = 0.0

    funding = {
        "seed_usd": seed_usd,
        "seed_investor": seed_investor,
        "seed_year": founded,
        "series_a_usd": series_a_usd,
        "series_a_investor": series_a_investor,
        "series_a_year": founded + 1,
        "has_series_b": has_series_b,
        "series_b_usd": series_b_usd,
        "series_b_investor": series_b_investor,
        "series_b_year": founded + 2 if has_series_b else None,
        "total_raised_usd": round(total_raised, 2),
        # Stated so a student can check the arithmetic and find it correct.
        "tier_one_seed": flags["tierOneInvestor"],
    }

    # ---- Economic position ----------------------------------------------
    customer_equity = ltv * customers
    eco_ratio = customer_equity / total_raised if total_raised else 0.0

    deferred_rev = company["bs_deferred_revenue_c"] / 100.0
    accumulated_deficit = company["bs_accumulated_deficit_c"] / 100.0

    computed_ratios = {
        "deficit_to_arr": round(accumulated_deficit / arr, 2) if arr else 0.0,
        "deferred_revenue_to_arr_pct": round(deferred_rev / arr * 100, 1) if arr else 0.0,
        "runway_months": round(company["runway_months"], 1),
        "top10_concentration_pct": int(rng.integers(10, 46)),
        "burn_multiple": (
            round(company["burn_multiple"], 2)
            if company["burn_multiple"] == company["burn_multiple"] and company["burn_multiple"] > 0
            else None
        ),
    }

    # ---- Go-to-market: driven by the flags, never drawn against them ----
    pricing = "Usage-based" if flags["usageBased"] else _pick(
        rng, ("Seat-based", "Tiered flat-rate", "Hybrid usage + seat")
    )
    segment = _pick(rng, SEGMENTS)
    motion = _pick(rng, MOTION_CUSTOMER_LED if flags["customerLed"] else MOTION_SALES_LED)

    # ---- Cohort curves: an expression of NRR ----------------------------
    # Four quarterly cohorts, indexed to 100 at acquisition and drifting toward
    # the company's actual net revenue retention over twelve months. A student
    # who reads this chart is reading a Class A causal variable directly, which
    # is exactly what it is there for.
    cohorts = []
    for _ in range(4):
        target = nrr * float(rng.uniform(0.94, 1.06))
        curve = []
        for m in range(13):
            base = 100.0 * (target ** (m / 12.0))
            curve.append(round(float(np.clip(base + rng.normal(0, 1.4), 55, 190)), 1))
        curve[0] = 100.0
        cohorts.append(curve)

    # ---- Departmental spend ---------------------------------------------
    # Sales & marketing is heavier when growth is bought rather than earned.
    sales_mkt = int(rng.integers(18, 30)) if flags["customerLed"] else int(rng.integers(30, 45))
    rnd = int(rng.integers(22, 42))
    csucc = int(rng.integers(8, 22))
    ga = max(6, 100 - rnd - sales_mkt - csucc)
    total_pct = rnd + sales_mkt + csucc + ga
    dept_spend = {
        "rnd": round(rnd / total_pct * 100),
        "sales_marketing": round(sales_mkt / total_pct * 100),
        "customer_success": round(csucc / total_pct * 100),
        "general_admin": 100 - round(rnd / total_pct * 100) - round(sales_mkt / total_pct * 100) - round(csucc / total_pct * 100),
        "annual_opex_usd": opex,
    }

    # ---- Cap table -------------------------------------------------------
    founders_pct = int(rng.integers(35, 61))
    option_pool = int(rng.integers(8, 17))
    remaining = 100 - founders_pct - option_pool
    if has_series_b:
        seed_pct = round(remaining * 0.18)
        a_pct = round(remaining * 0.35)
        b_pct = remaining - seed_pct - a_pct
    else:
        seed_pct = round(remaining * 0.35)
        a_pct = remaining - seed_pct
        b_pct = 0
    cap = {
        "founders": founders_pct, "option_pool": option_pool,
        "seed": seed_pct, "series_a": a_pct, "series_b": b_pct,
    }

    # ---- Founding team ---------------------------------------------------
    ceo_name = f"{_pick(rng, FOUNDER_FIRST)} {_pick(rng, FOUNDER_LAST)}"
    ceo_bg = _pick(rng, CEO_BG_TENURED if flags["founder5yrs"] else CEO_BG_UNTENURED)
    if flags["secondTime"]:
        ceo_bg += " This is their second company."
    if flags["eliteSchool"]:
        ceo_bg += " Graduated from a top-tier institution."
    has_cto = bool(rng.random() < 0.62)
    cto_name = f"{_pick(rng, FOUNDER_FIRST)} {_pick(rng, FOUNDER_LAST)}" if has_cto else None
    cto_bg = _pick(rng, CTO_BG) if has_cto else None

    # ---- Press: only if the company actually got press -------------------
    press = []
    if flags["pressYear1"]:
        headline_amount = funding["series_a_usd"]
        press.append({
            "headline": (
                f"{company['sector']} startup raises capital to rethink how "
                f"{segment.lower()} teams handle their workflows"
            ),
            "publication": _pick(rng, PUBLICATIONS),
            "year": founded + 1,
            "amount_usd": headline_amount,
        })
        press.append({
            "headline": f"{series_a_investor} leads a new round in {company['name']}",
            "publication": _pick(rng, PUBLICATIONS),
            "year": founded + 1,
            "amount_usd": headline_amount,
        })

    # ---- Employee reviews -------------------------------------------------
    reviews = []
    for dept, pool in REVIEW_TEMPLATES.items():
        # Operations sentiment tracks burn, which is a real thing to notice.
        if dept == "Operations" and flags["headcountDoubled"]:
            rating = int(rng.integers(2, 4))
        else:
            rating = int(rng.integers(3, 6))
        reviews.append({"department": dept, "rating": rating, "quote": _pick(rng, pool)})

    # ---- Market position --------------------------------------------------
    your_share = round(float(rng.uniform(1.5, 14.0)), 1)
    comps = []
    remaining_share = 100.0 - your_share
    weights = [float(rng.uniform(0.5, 2.5)) for _ in competitor_names]
    wsum = sum(weights) or 1.0
    for name, w in zip(competitor_names, weights):
        comps.append({"name": name, "share_pct": round(remaining_share * w / wsum * 0.75, 1)})
    used = your_share + sum(c["share_pct"] for c in comps)
    market = {
        "your_share_pct": your_share,
        "competitors": comps,
        "other_pct": round(100.0 - used, 1),
        "segment": segment,
    }

    # ---- Product releases -------------------------------------------------
    n_releases = int(rng.integers(4, 8))
    pool = list(PRODUCT_TEMPLATES[1:])
    rng.shuffle(pool)
    releases = [{"title": "General availability", "quarter": 1, "year": founded + 1}]
    for i in range(n_releases - 1):
        releases.append({
            "title": pool[i % len(pool)],
            "quarter": (i % 4) + 1,
            "year": founded + 1 + (i + 1) // 3,
        })

    # ---- Customer interviews ----------------------------------------------
    idx = int(rng.integers(0, len(CUSTOMER_INTERVIEWS)))
    interviews = [
        CUSTOMER_INTERVIEWS[idx],
        CUSTOMER_INTERVIEWS[(idx + 1 + int(rng.integers(0, 2))) % len(CUSTOMER_INTERVIEWS)],
    ]

    # ---- Flavour board minutes -------------------------------------------
    # These are DISTINCT from the triangulation minutes in narrative.py. Those
    # carry the planted contradiction and are served only when the student
    # explicitly opens that section; these are ambient colour and must stay
    # consistent with the flags.
    flavour_minutes = [
        {
            "label": f"Q{int(rng.integers(1, 5))} {founded + 2}",
            "text": (
                f"Approved {'Series B' if has_series_b else 'Series A'} terms from "
                f"{series_b_investor if has_series_b else series_a_investor}. "
                "Discussion on dilution; founders retain control."
            ),
        },
        {
            "label": f"Q{int(rng.integers(1, 5))} {report_year - 1}",
            "text": (
                "Reviewed net retention improvement; approved reinvestment into "
                "existing accounts over new logo acquisition."
                if nrr >= 1.0 else
                "Flagged retention softness; approved investment in customer "
                "success headcount."
            ),
        },
    ]

    return {
        "founded": founded,
        "report_year": report_year,
        "history_years": history_years,
        "customers": customers,
        "arpu_monthly_usd": arpu,
        "cac_usd": cac,
        "ltv_usd": ltv,
        "ltv_cac_ratio": ltv_cac,
        "cac_payback_months": cac_payback,
        "monthly_churn": monthly_churn,
        "avg_customer_lifetime_months": company["avg_customer_lifetime_months"],
        "gross_margin": gross_margin,
        "net_revenue_retention": nrr,
        "annual_net_burn_usd": net_burn,
        "financial_history": financial_history,
        "funding": funding,
        "economic_position": {
            "customer_equity_usd": round(customer_equity, 2),
            "customer_equity_plus_paid_in_usd": round(customer_equity + total_raised, 2),
            "ratio": round(eco_ratio, 2),
        },
        "computed_ratios": computed_ratios,
        "gtm": {"pricing": pricing, "segment": segment, "motion": motion},
        "cohorts": cohorts,
        "dept_spend": dept_spend,
        "cap_table": cap,
        "founders": {
            "ceo_name": ceo_name, "ceo_background": ceo_bg,
            "cto_name": cto_name, "cto_background": cto_bg,
        },
        "press": press,
        "reviews": reviews,
        "market": market,
        "releases": releases,
        "customer_interviews": interviews,
        "flavour_minutes": flavour_minutes,
    }
