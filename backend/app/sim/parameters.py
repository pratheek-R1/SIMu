"""Ground truth for The Survivors' Illusion.

This module is the ONLY place in the codebase allowed to assert what causes
startup success. Everything downstream -- the generator, the evidence board,
the scoring engine, the debrief -- reads causality from here and never invents
its own.

Numbers are quoted from the technical handoff, Part 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FeatureClass = Literal["A", "B", "C", "D"]

# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------
# A dataset is fully determined by its seed. Re-running the pipeline with a new
# seed produces a fresh cohort whose reveal is not common knowledge. See
# `DatasetRegistry` for how seeds are bound to cohorts.
DEFAULT_SEED = 20260729

# --------------------------------------------------------------------------
# Population
# --------------------------------------------------------------------------
N_WINNERS = 500
N_FAILURES = 2500

# 20% of failures never surface even after "the archive" arrives, and the
# missingness is not random -- it correlates with pedigree. A student who treats
# the archive as complete repeats the original error one level up.
ARCHIVE_WITHHOLD_RATE = 0.20
ARCHIVE_WITHHOLD_PEDIGREE_SKEW = 6.0

# Traits that make a company more likely to be quietly acqui-hired than to
# formally file dissolution paperwork -- i.e. more likely to be missing from the
# archive.
PEDIGREE_FEATURES = (
    "tierOneInvestor",
    "eliteSchool",
    "majorHub",
    "pressYear1",
)

# --------------------------------------------------------------------------
# Deal flow
# --------------------------------------------------------------------------
N_DEALS = 40
DEAL_BASE_RATE = 0.20  # calibrated: 10% lets luck dominate, 30% makes it trivial
N_CHEQUES = 5
CHEQUE_USD = 10_000_000.0  # 10M USD == Rs 83 Cr at INR_RATE
WIN_MULTIPLE = 4.5  # a win returns 4.5x the cheque
LOSS_MULTIPLE = 0.15  # a write-off returns 15% of the cheque

# --------------------------------------------------------------------------
# Capital allocation
# --------------------------------------------------------------------------
# The student sizes five cheques themselves out of one fixed pool rather than
# writing five identical ones. Without this, Capital Allocation has nothing to
# measure -- five equal cheques express no conviction ordering at all -- and the
# Risk Management concentration term is constant for every student.
#
# All amounts are WHOLE USD held as ints. The handoff's Part 5 warns that a
# rounding error here silently corrupts both the capital and risk dimensions;
# integer cents-free arithmetic plus an exact-equality check on the total is the
# cheapest way to make that class of bug impossible rather than unlikely.
FUND_POOL_USD = int(CHEQUE_USD) * N_CHEQUES  # 50M USD == Rs 415 Cr

# Sizing granularity. 1M USD steps give 50 units to distribute across 5 cheques
# -- coarse enough to slide without fiddling, fine enough to express a real
# ordering.
CHEQUE_STEP_USD = 1_000_000

# Every pick must actually be funded: a zero cheque is a pick the student did
# not make. The ceiling stops the whole fund landing on one company, which the
# Risk Management dimension would score at zero anyway.
CHEQUE_MIN_USD = 2_000_000
CHEQUE_MAX_USD = 30_000_000

# Concentration above this share of the fund starts costing Risk Management
# points. Below it, no penalty.
CONCENTRATION_FREE_SHARE = 0.30

# --------------------------------------------------------------------------
# Binary features
# --------------------------------------------------------------------------
# Tuple format: (P(feature | succeeds), P(feature | fails), class)
#
#   A -- causal.       Real signal, deliberately low-prevalence so that ranking
#                      features by raw frequency among winners misses it.
#   B -- survivorship. Identical prevalence in winners and failures. Looks
#                      strong only because failures are invisible.
#   C -- reverse trap. MORE common in failures, but frequent enough among
#                      winners (38-51%) to still look causal when failures are
#                      hidden. A naive analyst bets on the opposite of truth.
#   D -- noise.        No relationship either direction. Diagnostic only: a
#                      thesis weighted here indicates overfitting, which is a
#                      different failure mode from survivorship bias.
# Keys, labels and display order are taken verbatim from TAG_DEFS in the
# original single-file prototype (removed once the port was complete) so that
# the client and the kernel share one vocabulary. What that file could NOT
# supply is the second number: it gave each
# variable a single `prob` and drew it independently of the outcome
# (`tags[t.key] = sr(...) < t.prob`), which makes every variable's true lift
# exactly 1.0. With no conditional structure there is no trap to fall into and
# nothing for the debrief to reveal -- the entire exercise collapses. The
# conditional pairs below are what restore it.
#
# Ordering below is the file's own, which already groups the taxonomy: seven
# survivorship traps, four reverse traps, three causal, two noise.
BINARY_FEATURES: dict[str, tuple[float, float, FeatureClass]] = {
    # Class B -- survivorship traps (identical win/fail rate)
    "tierOneInvestor": (0.68, 0.68, "B"),
    "majorHub": (0.75, 0.75, "B"),
    "pivoted": (0.72, 0.72, "B"),
    "eliteSchool": (0.61, 0.61, "B"),
    "contrarian": (0.55, 0.55, "B"),
    "growthPreA": (0.58, 0.58, "B"),
    "secondTime": (0.52, 0.52, "B"),
    # Class C -- reverse traps (worse in winners than in failures)
    "pressYear1": (0.51, 0.74, "C"),
    "headcountDoubled": (0.47, 0.71, "C"),
    "seriesA20": (0.42, 0.66, "C"),
    "multiGeo": (0.38, 0.62, "C"),
    # Class A -- causal, deliberately low-prevalence
    "founder5yrs": (0.44, 0.11, "A"),
    "customerLed": (0.39, 0.09, "A"),
    "usageBased": (0.36, 0.14, "A"),
    # Class D -- noise, diagnostic only
    "stemUndergrad": (0.50, 0.50, "D"),
    "oneWordName": (0.45, 0.45, "D"),
}

# Bit position in every company's flag bitstring. Order is frozen: changing it
# invalidates every stored session.
FEATURE_KEYS: tuple[str, ...] = tuple(BINARY_FEATURES.keys())

# The three Class A binaries, named explicitly because the scoring engine's
# Revision Quality dimension awards credit for retaining positive weight on them.
CAUSAL_FEATURES: tuple[str, ...] = tuple(
    k for k, (_, _, cls) in BINARY_FEATURES.items() if cls == "A"
)

# Human-readable labels, verbatim from TAG_DEFS. Kept server-side so the wording
# of a variable and its ground truth can never drift apart.
FEATURE_LABELS: dict[str, str] = {
    "tierOneInvestor": "Tier-one seed investor",
    "majorHub": "Major startup hub",
    "pivoted": "Pivoted at least once",
    "eliteSchool": "Elite-school founder",
    "contrarian": "Contrarian thesis",
    "growthPreA": "Head of growth pre-A",
    "secondTime": "Second-time founder",
    "pressYear1": "Major press in year one",
    "headcountDoubled": "Doubled headcount post-A",
    "seriesA20": "Series A above $20M",
    "multiGeo": "Multi-geography by year two",
    "founder5yrs": "Founder 5+ yrs in domain",
    "customerLed": "Expansion was customer-led",
    "usageBased": "Usage-based pricing",
    "stemUndergrad": "STEM undergraduate",
    "oneWordName": "One-word company name",
}

# --------------------------------------------------------------------------
# Continuous features
# --------------------------------------------------------------------------
# All Class A. These are the "invisible without a comparison group" variables:
# individually meaningless numbers until you can compare a winner's figure to a
# failure's. Format: (mean|win, sd|win, mean|fail, sd|fail, clip_lo, clip_hi)


@dataclass(frozen=True)
class ContinuousSpec:
    mean_win: float
    sd_win: float
    mean_fail: float
    sd_fail: float
    clip_lo: float
    clip_hi: float
    label: str
    unit: str
    # True when a LOWER value is better -- the evidence board needs this to
    # render lift in the right direction.
    lower_is_better: bool = False


CONTINUOUS_FEATURES: dict[str, ContinuousSpec] = {
    # The upper clip on retention matters more than it looks. Customer lifetime
    # is 1 / (1 - retention ** (1/6)), which explodes as retention approaches 1:
    # at 0.99 the implied lifetime is ~600 months and LTV/CAC lands near 40x.
    # No student believes a 50-year customer, and a figure that implausible
    # invites them to distrust the whole dataset. Clipped at 0.94.
    "month6_retention": ContinuousSpec(
        0.71, 0.09, 0.42, 0.12, 0.10, 0.94, "Month-6 retention", "pct"
    ),
    # Likewise a floor on payback: sub-3-month payback is not a thing at this
    # stage, and it is the other half of the same runaway ratio.
    "cac_payback_months": ContinuousSpec(
        13.0, 3.5, 27.0, 8.0, 3.0, 60.0, "CAC payback", "months", lower_is_better=True
    ),
    "net_revenue_retention": ContinuousSpec(
        1.18, 0.13, 0.87, 0.15, 0.30, 2.00, "Net revenue retention", "pct"
    ),
    "gross_margin": ContinuousSpec(
        0.74, 0.08, 0.58, 0.13, 0.10, 0.95, "Gross margin", "pct"
    ),
}

CONTINUOUS_KEYS: tuple[str, ...] = tuple(CONTINUOUS_FEATURES.keys())

# --------------------------------------------------------------------------
# Descriptive attributes (no relationship to outcome, purely for texture)
# --------------------------------------------------------------------------
SECTORS = ("SaaS", "Fintech", "D2C", "Healthtech", "Edtech")
CITIES = ("Mumbai", "Bangalore", "Delhi", "Hyderabad", "Chennai", "Pune")
HUB_CITIES = ("Mumbai", "Bangalore", "Delhi")  # consistent with majorHub
FOUNDED_YEARS = tuple(range(2012, 2021))

# --------------------------------------------------------------------------
# Currency
# --------------------------------------------------------------------------
# Single source of truth. The prototype buried this constant in profile.js; it
# lives in config here so a deployment can override it without a code change.
DEFAULT_INR_RATE = 83.0

# --------------------------------------------------------------------------
# Validation gate thresholds
# --------------------------------------------------------------------------
GATE_MIN_TRAPS_IN_TOP5 = 4
GATE_MIN_RANK_FIRST_CAUSAL = 11  # first Class A feature must rank 11th or worse


def feature_class(key: str) -> FeatureClass:
    return BINARY_FEATURES[key][2]


def true_lift(key: str) -> float:
    """Ground-truth lift: P(feature | win) / P(feature | fail).

    This is the parameter-level lift, not the sample lift. The scoring engine
    uses the *sample* lift computed from the realised dataset so that a student's
    calibration is judged against the evidence they could actually have seen.
    """
    p_win, p_fail, _ = BINARY_FEATURES[key]
    return p_win / p_fail
