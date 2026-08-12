"""The six-dimension assessment engine.

Weights are unchanged from the handoff (20 / 25 / 15 / 15 / 15 / 10). What
changed is what three of them actually measure. Taking the open issues in turn:

Open Issue 2 -- Triangulation did not measure triangulation. `T.minutes` was
    incremented on the same line as `T.prof`, so the dimension was arithmetically
    `min(1, profiles_opened/3) * 15` while the UI claimed it measured
    "cross-checked N board minutes against founder narratives". A student who
    opened three profiles and read nothing scored full marks. It now requires
    opening both sources on the same company and correctly identifying a planted
    contradiction; opening profiles alone earns zero.

Open Issue 3 -- Comparison-group credit fired unconditionally on entering the
    Evidence screen, so every student collected it by walking forward through a
    linear flow. It now requires explicitly asking for the comparison group
    BEFORE the archive arrives, which is the behaviour the point was meant to
    reward.

Open Issue 4 -- The committee free-text was never read. It is now scored by a
    deterministic, fully-auditable rubric. The rubric is keyword- and
    structure-based and therefore gameable by a student who knows it; that is a
    deliberate trade against the design goal of no ML at runtime, and the
    matched phrases are reported on the scorecard so a facilitator can see
    exactly why a point was awarded.

The prototype awarded 10 of 25 Provenance points for no provenance-seeking
behaviour at all. Under this implementation, zero points anywhere are free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .sim import parameters as P
from .sim.generator import Dataset

# --------------------------------------------------------------------------
# Telemetry aggregation
# --------------------------------------------------------------------------
EVENT_KINDS = {
    "profile_opened",
    "comparison_added",
    "chart_viewed",
    "board_minutes_opened",
    "founder_interview_opened",
    "contradiction_flagged",
    "provenance_query",
    "ghost_query",
    "comparison_group_requested",
    "archive_completeness_questioned",
    "committee_answer",
    "metric_pair_explored",
}

# The four continuous metrics are the only genuinely causal evidence that cannot
# be read off a single company -- seeing them requires putting two axes against
# each other. Every unordered pair of distinct metrics, canonicalised so that
# (retention, margin) and (margin, retention) are one pair rather than two.
VALID_METRIC_PAIRS = {
    "|".join(sorted((a, b)))
    for a in P.CONTINUOUS_KEYS
    for b in P.CONTINUOUS_KEYS
    if a != b
}

# Charts the client is allowed to report engagement with. An unknown id is
# dropped rather than scored, which bounds what a hand-crafted POST can earn.
VALID_CHART_IDS = {
    "dashboard.sector",
    "dashboard.retention_arr",
    "dashboard.win_by_retention",
    "dashboard.ltv_distribution",
    "research.crossplot",
    "evidence.win_rate",
    "evidence.crossplot",
    "model.accuracy",
    "results.outcomes",
    "debrief.fund_distribution",
}

# Screens that count as "before the reveal" for provenance purposes.
PRE_REVEAL_SCREENS = {"brief", "dashboard", "research", "thesis", "committee", "deliberation"}


@dataclass
class Telemetry:
    profiles: set[int] = field(default_factory=set)
    comparisons: int = 0
    charts: set[str] = field(default_factory=set)
    minutes_opened: set[int] = field(default_factory=set)
    interviews_opened: set[int] = field(default_factory=set)
    contradictions_correct: set[int] = field(default_factory=set)
    contradictions_incorrect: int = 0
    provenance_query_pre_reveal: bool = False
    ghost_query: bool = False
    comparison_group_pre_reveal: bool = False
    archive_questioned_post_reveal: bool = False
    committee_signals: list[dict[str, Any]] = field(default_factory=list)
    metric_pairs: set[str] = field(default_factory=set)

    @property
    def cross_source_companies(self) -> set[int]:
        """Companies where the student read BOTH accounts of the same period."""
        return self.minutes_opened & self.interviews_opened

    @property
    def metrics_examined(self) -> set[str]:
        """Distinct continuous metrics the student put on an axis."""
        out: set[str] = set()
        for pair in self.metric_pairs:
            out.update(pair.split("|"))
        return out


def aggregate(events: Iterable[Any]) -> Telemetry:
    t = Telemetry()
    for e in events:
        kind = e.kind
        subject = e.subject
        screen = e.screen or ""
        payload = e.payload or {}

        if kind == "profile_opened" and subject:
            t.profiles.add(int(subject))
        elif kind == "comparison_added":
            t.comparisons += 1
        elif kind == "chart_viewed" and subject in VALID_CHART_IDS:
            t.charts.add(subject)
        elif kind == "board_minutes_opened" and subject:
            t.minutes_opened.add(int(subject))
        elif kind == "founder_interview_opened" and subject:
            t.interviews_opened.add(int(subject))
        elif kind == "contradiction_flagged" and subject:
            if payload.get("correct"):
                t.contradictions_correct.add(int(subject))
            else:
                t.contradictions_incorrect += 1
        elif kind == "provenance_query":
            if screen in PRE_REVEAL_SCREENS:
                t.provenance_query_pre_reveal = True
        elif kind == "ghost_query":
            t.ghost_query = True
        elif kind == "comparison_group_requested":
            if screen in PRE_REVEAL_SCREENS:
                t.comparison_group_pre_reveal = True
        elif kind == "archive_completeness_questioned":
            if screen not in PRE_REVEAL_SCREENS:
                t.archive_questioned_post_reveal = True
        elif kind == "committee_answer":
            t.committee_signals.append(payload)
        elif kind == "metric_pair_explored" and subject in VALID_METRIC_PAIRS:
            t.metric_pairs.add(subject)
    return t


# --------------------------------------------------------------------------
# Committee free-text rubric (Open Issue 4)
# --------------------------------------------------------------------------
RUBRIC = {
    "missing_data": (
        r"\b(missing|absent|incomplete|only winners?|survivor\w*|didn'?t (?:see|get)|"
        r"not (?:in|included)|left out|excluded|failed compan|companies that failed|"
        r"passed on|wrote? off|dead|shut down)\b"
    ),
    "comparison_group": (
        r"\b(compar\w+ group|control group|base ?rate|denominator|counterfactual|"
        r"against failures?|versus failures?|both groups?|the other half)\b"
    ),
    "quantified": r"\d+(?:\.\d+)?\s*(?:%|percent|x\b|months?|Cr\b)",
    "falsifiable": (
        r"\b(would (?:change|unwind|reverse)|if .{0,40}(?:below|above|under|over|less|more)|"
        r"threshold|cut ?off|i'?d pass if|disprove|falsif\w+|refute)\b"
    ),
}


def analyse_free_text(text: str | None) -> dict[str, Any]:
    """Deterministic. Returns which rubric signals fired and the matched span.

    Reported verbatim on the scorecard so a facilitator can audit every point.
    """
    if not text or not text.strip():
        return {"signals": [], "matches": {}, "length": 0}
    signals, matches = [], {}
    for name, pattern in RUBRIC.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            signals.append(name)
            matches[name] = m.group(0)
    return {"signals": signals, "matches": matches, "length": len(text.strip())}


# --------------------------------------------------------------------------
# Lift helpers
# --------------------------------------------------------------------------
def _lift(ds: Dataset, key: str) -> float:
    """Realised lift against the COMPLETE failure population.

    Calibration judges a student against what was actually true, not against
    the partial archive they were handed -- the gap between those two is the
    second lesson, and it is taught in the debrief rather than scored here.
    """
    value = ds.sample_lift(key)
    return min(value, 12.0)  # clamp the tail so a rare zero-denominator cannot dominate


def _true_strength(lift: float) -> float:
    """Map lift onto a 0-1 'how real is this variable' scale."""
    return max(0.0, min(1.0, (lift - 1.0) / 3.0))


# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------
# Every channel into this dimension is capped, because none of the three is
# evidence of the other two and each is individually cheap to manufacture.
#
# Chart engagement is the one signal the client self-reports (the server cannot
# observe a hover). It was already capped, after a live session scored 18.0/20
# from nine chart hovers with zero profiles opened and zero comparisons built.
#
# Comparisons were NOT capped, and at 4 points each that left a wider hole than
# the one the chart cap closed: five bare POSTs to /compare -- which needs only
# two company ids and opens nothing -- scored a full 20/20 with no profile ever
# read. Verified against a running server. Comparisons are the most meaningful of
# the three signals, so they keep the highest per-unit value; they just can no
# longer stand in for the whole dimension.
# The fourth channel is the cross-plot. The four continuous metrics are all
# genuinely causal -- and were previously worth nothing at all, in any dimension,
# despite being the only evidence in the simulation that cannot be misread off a
# single winner's profile. Reading them requires putting two against each other,
# so the unit here is a distinct metric PAIR rather than a page view.
PROFILE_POINTS_PER = 0.6
PROFILE_POINTS_CAP = 8.0
COMPARISON_POINTS_PER = 2.0
COMPARISON_POINTS_CAP = 6.0
CHART_POINTS_PER = 1.0
CHART_POINTS_CAP = 4.0
METRIC_PAIR_POINTS_PER = 0.5
METRIC_PAIR_POINTS_CAP = 2.0


def evidence_depth(t: Telemetry) -> dict[str, Any]:
    pairs = len(t.metric_pairs)
    profile_points = min(PROFILE_POINTS_CAP, len(t.profiles) * PROFILE_POINTS_PER)
    comparison_points = min(COMPARISON_POINTS_CAP, t.comparisons * COMPARISON_POINTS_PER)
    chart_points = min(CHART_POINTS_CAP, len(t.charts) * CHART_POINTS_PER)
    metric_points = min(METRIC_PAIR_POINTS_CAP, pairs * METRIC_PAIR_POINTS_PER)
    score = min(
        20.0,
        round(profile_points + comparison_points + chart_points + metric_points, 1),
    )

    at_cap = [
        name
        for name, points, cap in (
            ("profiles", profile_points, PROFILE_POINTS_CAP),
            ("comparisons", comparison_points, COMPARISON_POINTS_CAP),
            ("charts", chart_points, CHART_POINTS_CAP),
            ("metric pairs", metric_points, METRIC_PAIR_POINTS_CAP),
        )
        if points >= cap
    ]

    return {
        "key": "evidence_depth",
        "label": "Evidence Depth",
        "score": score,
        "max": 20,
        "detail": (
            f"{len(t.profiles)} profile{'' if len(t.profiles) == 1 else 's'} opened, "
            f"{t.comparisons} comparison{'' if t.comparisons == 1 else 's'} built, "
            f"{len(t.charts)} distinct chart{'' if len(t.charts) == 1 else 's'} "
            f"engaged with, {pairs} metric pair{'' if pairs == 1 else 's'} "
            "cross-plotted."
            + (
                " No single kind of activity can carry this dimension on its own: "
                f"{'; '.join(at_cap)} {'is' if len(at_cap) == 1 else 'are'} at "
                "the per-channel cap, and the remaining points need the others."
                if at_cap and score < 20.0
                else ""
            )
        ),
        "components": {
            "profiles": len(t.profiles),
            "comparisons": t.comparisons,
            "charts": len(t.charts),
            "metric_pairs": sorted(t.metric_pairs),
            "metrics_examined": sorted(t.metrics_examined),
            "profile_points": round(profile_points, 1),
            "comparison_points": round(comparison_points, 1),
            "chart_points": round(chart_points, 1),
            "metric_points": round(metric_points, 1),
            "at_cap": at_cap,
            # Retained: previously the only cap, so keep the key readable.
            "chart_points_capped": chart_points >= CHART_POINTS_CAP,
        },
    }


# Points for the written-reasoning signals the rubric already extracts.
#
# `analyse_free_text` has always produced four signals, and the scorecard screen
# has always listed all four back to the student ("asked for a comparison group",
# "gave a number", "stated a falsifiable threshold"). Only `missing_data` was
# ever worth anything, so the other three were advertised credit that did not
# exist -- a student could write five careful answers and score exactly what a
# single search query scores. These three now carry a point each.
#
# The 25 is unchanged, so the process total stays 100: one point each comes off
# the three secondary behavioural terms. The flagship 10-point term for naming
# the missing data is deliberately untouched -- it is the core lesson. Retuning
# is a matter of editing these two dicts and nothing else.
WRITTEN_SIGNAL_POINTS = {
    # Asking for a comparison group in writing is now the only way to be credited
    # for asking at all -- the button that used to earn it behaviourally is gone
    # (it read as a control that would reveal withheld failure data), so its
    # weight moved here. The thinking is still measured; only the channel changed.
    "comparison_group": 3,
    "quantified": 1,
    "falsifiable": 1,
}
WRITTEN_SIGNAL_PHRASES = {
    "comparison_group": "asked in writing for a comparison group or base rate",
    "quantified": "quantified a claim rather than asserting it",
    "falsifiable": "stated a threshold that would change their mind",
}


def provenance(t: Telemetry, committee: dict[str, Any]) -> dict[str, Any]:
    signals = set(committee.get("aggregate_signals", []))
    asked_in_committee = "missing_data" in signals

    plain_language = t.provenance_query_pre_reveal or asked_in_committee
    # The former `requested_a_comparison_group_before_the_reveal` term is gone
    # with the control that produced it; its 4 points were redistributed across
    # the ghost search, the post-reveal question and the written comparison-group
    # signal, so this dimension still totals 25 and is still reachable in full.
    parts = {
        "asked_where_the_data_came_from": 10 if plain_language else 0,
        "searched_for_a_company_not_in_the_set": 5 if t.ghost_query else 0,
        "questioned_the_archive_after_the_reveal": (
            5 if t.archive_questioned_post_reveal else 0
        ),
    }
    for name, points in WRITTEN_SIGNAL_POINTS.items():
        parts[f"written_{name}"] = points if name in signals else 0

    score = float(sum(parts.values()))

    earned: list[str] = []
    if t.provenance_query_pre_reveal:
        earned.append("asked in plain language what data was missing")
    if asked_in_committee:
        earned.append("raised the missing-data problem with the committee")
    if t.ghost_query:
        earned.append("searched for a company absent from the winners set")
    if t.archive_questioned_post_reveal:
        earned.append("questioned whether the recovered archive was itself complete")
    for name in WRITTEN_SIGNAL_POINTS:
        if name in signals:
            earned.append(WRITTEN_SIGNAL_PHRASES[name])

    return {
        "key": "provenance",
        "label": "Provenance and Completeness",
        "score": score,
        "max": 25,
        "detail": (
            "; ".join(earned).capitalize()
            if earned
            else "No provenance-seeking behaviour recorded. The 500 companies were "
            "taken as the whole population."
        ),
        "components": parts,
    }


def triangulation(t: Telemetry) -> dict[str, Any]:
    found = len(t.contradictions_correct)
    cross = len(t.cross_source_companies)

    finding = min(1.0, found / 3.0) * 10.0
    breadth = min(1.0, cross / 5.0) * 5.0
    score = round(finding + breadth, 1)

    return {
        "key": "triangulation",
        "label": "Triangulation",
        "score": score,
        "max": 15,
        "detail": (
            f"Read both the board minutes and the founder interview on {cross} "
            f"{'company' if cross == 1 else 'companies'}; correctly identified "
            f"{found} {'contradiction' if found == 1 else 'contradictions'} between "
            f"the two accounts."
        ),
        "components": {
            "cross_source_companies": cross,
            "contradictions_found": found,
            "false_flags": t.contradictions_incorrect,
        },
    }


def calibration(
    ds: Dataset, variables: list[str], confidence: dict[str, int]
) -> dict[str, Any]:
    if not variables:
        return {
            "key": "calibration",
            "label": "Calibration",
            "score": 0.0,
            "max": 15,
            "detail": "No thesis variables were submitted.",
            "components": {"rows": []},
        }

    rows, brier_total = [], 0.0
    for key in variables:
        lift = _lift(ds, key)
        strength = _true_strength(lift)
        stated = confidence.get(key, 50) / 100.0
        error = (stated - strength) ** 2
        brier_total += error
        rows.append(
            {
                "feature": key,
                "label": P.FEATURE_LABELS[key],
                "stated_confidence": round(stated * 100),
                "true_lift": round(lift, 2),
                "true_strength": round(strength, 3),
                "squared_error": round(error, 4),
            }
        )

    mean_brier = brier_total / len(variables)
    score = round(15.0 * (1.0 - mean_brier), 1)
    score = max(0.0, score)

    return {
        "key": "calibration",
        "label": "Calibration",
        "score": score,
        "max": 15,
        "detail": (
            f"Mean squared error between stated confidence and true strength: "
            f"{mean_brier:.3f}."
        ),
        "components": {"rows": rows, "mean_brier": round(mean_brier, 4)},
    }


def revision_quality(
    ds: Dataset,
    w1: dict[str, float] | None,
    weights: dict[str, float] | None,
) -> dict[str, Any]:
    w1 = w1 or {}
    weights = weights or {}

    numerator = denominator = 0.0
    moves = []
    for key in P.FEATURE_KEYS:
        delta = float(weights.get(key, 0.0)) - float(w1.get(key, 0.0))
        if delta == 0:
            continue
        lift = _lift(ds, key)
        correct_direction = (delta > 0) == (lift > 1.0)
        denominator += abs(delta)
        if correct_direction:
            numerator += abs(delta)
        moves.append(
            {
                "feature": key,
                "label": P.FEATURE_LABELS[key],
                "delta": round(delta, 2),
                "true_lift": round(lift, 2),
                "correct_direction": correct_direction,
            }
        )

    direction_score = (10.0 * numerator / denominator) if denominator else 0.0
    kept = sum(1 for k in P.CAUSAL_FEATURES if float(weights.get(k, 0.0)) > 0)
    retention_score = 5.0 * kept / len(P.CAUSAL_FEATURES)
    score = round(direction_score + retention_score, 1)

    return {
        "key": "revision_quality",
        "label": "Revision Quality",
        "score": score,
        "max": 15,
        "detail": (
            f"{round(numerator / denominator * 100) if denominator else 0}% of weight "
            f"movement was in the correct direction; {kept} of "
            f"{len(P.CAUSAL_FEATURES)} genuinely causal variables carry positive "
            f"weight at the end."
        ),
        "components": {
            "moves": moves,
            "causal_kept": kept,
            "total_movement": round(denominator, 2),
        },
    }


def model_score(flags: str, weights: dict[str, float]) -> float:
    return sum(
        weights.get(k, 0.0) for i, k in enumerate(P.FEATURE_KEYS) if flags[i] == "1"
    )


def decision_discipline(
    ds: Dataset, picks: list[int] | None, weights: dict[str, float] | None
) -> dict[str, Any]:
    picks = picks or []
    weights = weights or {}
    if not picks:
        return {
            "key": "decision_discipline",
            "label": "Decision Discipline",
            "score": 0.0,
            "max": 10,
            "detail": "No cheques were written.",
            "components": {"in_top_10": 0},
        }

    ranked = sorted(ds.deals, key=lambda d: -model_score(d["flags"], weights))
    top10 = {d["id"] for d in ranked[:10]}
    hits = sum(1 for p in picks if p in top10)
    score = round(10.0 * hits / P.N_CHEQUES, 1)

    return {
        "key": "decision_discipline",
        "label": "Decision Discipline",
        "score": score,
        "max": 10,
        "detail": (
            f"{hits} of {len(picks)} cheques landed inside your own model's top 10. "
            "Building a model and then picking by feel scores low here."
        ),
        "components": {"in_top_10": hits, "picks": len(picks)},
    }


# --------------------------------------------------------------------------
# Myelin standard scorecard
# --------------------------------------------------------------------------
# The platform-wide rubric, scored out of 100 from the same session the
# process-detail dimensions above are scored from. Two of the seven standard
# dimensions have no mechanic in this simulation and are reported N/A rather
# than given a fabricated number -- see `NOT_APPLICABLE` below.
#
# Three of these five (Strategic Thinking, Long-Term Value, Adaptability) read
# the same weight vector as each other and as Revision Quality. They ask
# genuinely different questions of it -- final-state coherence, final-state
# durability, and correctness of the change over time -- but they are
# correlated, not independent, and should not be presented as orthogonal axes.


def strategic_thinking(ds: Dataset, weights: dict[str, float] | None) -> dict[str, Any]:
    """Does the final model hold one coherent, evidence-aligned view?

    Every non-zero weight is checked against the direction of true lift. A model
    that rewards a variable which predicts failure contradicts itself, and the
    contradiction costs in proportion to how much conviction sits on it.
    """
    weights = weights or {}
    agreeing = total = 0.0
    conflicts = []
    for key in P.FEATURE_KEYS:
        w = float(weights.get(key, 0.0))
        if not w:
            continue
        lift = _lift(ds, key)
        total += abs(w)
        if (w > 0) == (lift > 1.0):
            agreeing += abs(w)
        else:
            conflicts.append(
                {
                    "feature": key,
                    "label": P.FEATURE_LABELS[key],
                    "weight": round(w, 2),
                    "true_lift": round(lift, 2),
                }
            )

    ratio = agreeing / total if total else 0.0
    score = round(20.0 * ratio, 1)
    return {
        "key": "strategic_thinking",
        "label": "Strategic Thinking",
        "score": score,
        "max": 20,
        "detail": (
            f"{round(ratio * 100)}% of the conviction in your final model points the "
            "same way the evidence does."
            + (
                f" {len(conflicts)} variable{'s' if len(conflicts) != 1 else ''} "
                "carried weight against the evidence."
                if conflicts
                else ""
            )
            if total
            else "No weights were set, so the model states no view to be coherent about."
        ),
        "components": {"aligned_weight": round(agreeing, 2), "total_weight": round(total, 2), "conflicts": conflicts},
    }


def capital_allocation(
    ds: Dataset,
    picks: list[int] | None,
    weights: dict[str, float] | None,
    cheque_sizes: dict[str, int] | None,
) -> dict[str, Any]:
    """Did more capital go behind the picks the student's own model rated highest?

    A concordance over every pair of picks. Ties on either axis leave the pair
    out of the denominator, so a student who sized every cheque identically
    expressed no ordering and scores a neutral 0.5 -- neither rewarded nor
    punished for information they never gave.
    """
    picks = picks or []
    weights = weights or {}
    sizes = cheque_sizes or {}
    by_id = {d["id"]: d for d in ds.deals}

    if len(picks) < 2:
        return {
            "key": "capital_allocation",
            "label": "Capital Allocation",
            "score": 10.0,
            "max": 20,
            "detail": "Too few cheques to compare sizing against conviction.",
            "components": {
                "pairs": 0,
                "concordant": 0,
                "neutral": True,
                "neutral_reason": "too_few_picks",
            },
        }

    scored = [
        (
            model_score(by_id[p]["flags"], weights) if p in by_id else 0.0,
            float(sizes.get(str(p), 0)),
        )
        for p in picks
    ]

    concordant = pairs = 0
    for a in range(len(scored)):
        for b in range(a + 1, len(scored)):
            score_delta = scored[a][0] - scored[b][0]
            size_delta = scored[a][1] - scored[b][1]
            if score_delta == 0 or size_delta == 0:
                continue
            pairs += 1
            if (score_delta > 0) == (size_delta > 0):
                concordant += 1

    neutral = pairs == 0
    ratio = 0.5 if neutral else concordant / pairs
    score = round(20.0 * ratio, 1)

    # `pairs == 0` has two quite different causes and the scorecard used to
    # report both of them as "every cheque was the same size", which is simply
    # false in the second case: a student can size five cheques deliberately and
    # still land here because their own model rates all five picks identically,
    # and every pair then ties on the score axis instead of the size axis. The
    # neutral score is right either way -- there is no ordering to agree with --
    # but telling someone they sized uniformly when they did not is a bug in the
    # feedback, and it hides the thing they actually need to know.
    uniform_sizing = len({s for _, s in scored}) <= 1
    model_cannot_rank = len({m for m, _ in scored}) <= 1

    if not neutral:
        neutral_reason = None
        detail = (
            f"{concordant} of {pairs} pairs of picks were sized in the same order "
            "your model ranked them."
        )
    elif uniform_sizing and model_cannot_rank:
        neutral_reason = "uniform_sizing_and_flat_model"
        detail = (
            "Every cheque was the same size, and your model scores all of these "
            "picks identically, so neither the allocation nor the model expressed "
            "a ranking. Scored neutrally rather than as a mistake."
        )
    elif uniform_sizing:
        neutral_reason = "uniform_sizing"
        detail = (
            "Every cheque was the same size, so the allocation expressed no ranking. "
            "Scored neutrally rather than as a mistake."
        )
    elif model_cannot_rank:
        neutral_reason = "flat_model"
        detail = (
            "You sized these cheques differently, but your model scores every one of "
            "these picks identically, so there is no ranking for the sizing to agree "
            "or disagree with. Scored neutrally: the flat ranking is a property of "
            "the model, not of the allocation."
        )
    else:
        neutral_reason = "all_pairs_tied"
        detail = (
            "Every pair of picks tied on either conviction or cheque size, so no "
            "ordering could be compared. Scored neutrally rather than as a mistake."
        )

    return {
        "key": "capital_allocation",
        "label": "Capital Allocation",
        "score": score,
        "max": 20,
        "detail": detail,
        "components": {
            "pairs": pairs,
            "concordant": concordant,
            "neutral": neutral,
            "neutral_reason": neutral_reason,
            "uniform_sizing": uniform_sizing,
            "model_cannot_rank": model_cannot_rank,
        },
    }


def risk_management(
    ds: Dataset, picks: list[int] | None, cheque_sizes: dict[str, int] | None
) -> dict[str, Any]:
    """Is the portfolio diversified, or one correlated bet in five envelopes?"""
    picks = picks or []
    sizes = cheque_sizes or {}
    by_id = {d["id"]: d for d in ds.deals}

    if not picks:
        return {
            "key": "risk_management",
            "label": "Risk Management",
            "score": 0.0,
            "max": 15,
            "detail": "No cheques were written.",
            "components": {},
        }

    sectors = {by_id[p]["sector"] for p in picks if p in by_id}
    diversity = len(sectors) / max(1, len(picks))

    total = sum(sizes.values()) or P.FUND_POOL_USD
    max_share = max((sizes.get(str(p), 0) for p in picks), default=0) / total
    free = P.CONCENTRATION_FREE_SHARE
    penalty = max(0.0, min(1.0, (max_share - free) / (1.0 - free)))

    score = round(15.0 * (0.5 * diversity + 0.5 * (1.0 - penalty)), 1)

    return {
        "key": "risk_management",
        "label": "Risk Management",
        "score": score,
        "max": 15,
        "detail": (
            f"{len(sectors)} distinct sector{'s' if len(sectors) != 1 else ''} across "
            f"{len(picks)} positions; largest single position is {round(max_share * 100)}% "
            f"of the fund."
            + (
                f" Concentration above {round(free * 100)}% costs points."
                if penalty > 0
                else ""
            )
        ),
        "components": {
            "sectors": sorted(sectors),
            "diversity": round(diversity, 3),
            "max_share": round(max_share, 4),
            "concentration_penalty": round(penalty, 3),
        },
    }


def adaptability(revision: dict[str, Any]) -> dict[str, Any]:
    """The same measurement as Revision Quality, on the standard rubric's scale.

    Deliberately not recomputed: two dimensions that claim to measure the same
    behaviour must not be able to drift apart.
    """
    score = round(revision["score"] * (25.0 / 15.0), 1)
    return {
        "key": "adaptability",
        "label": "Adaptability",
        "score": score,
        "max": 25,
        "detail": revision["detail"],
        "components": {**revision["components"], "rescaled_from": "revision_quality"},
    }


def long_term_value(ds: Dataset, weights: dict[str, float] | None) -> dict[str, Any]:
    """Does conviction sit on durable causal signal, or on variables that merely
    look strong once the failures are hidden?

    Measured over POSITIVE conviction, plus any conviction pointed AGAINST a
    causal variable.

    This previously summed abs(w) over every non-zero weight into the
    denominator. That put correctly-placed negative weight somewhere it could
    never reach the numerator, so an analyst who correctly marked the
    reverse-trap variables (realised lift < 1.0, i.e. they predict failure) as
    negative predictors scored strictly LOWER than one who left them at zero --
    penalising the better-informed model, and directly contradicting Strategic
    Thinking, which credits that same behaviour. Marking a variable down is not
    conviction placed on it.

    Betting against a genuinely causal variable is still a real cost to
    durability, so that alone stays in the denominator.
    """
    weights = weights or {}
    causal_positive = positive_total = against_causal = 0.0
    misplaced: list[dict[str, Any]] = []
    discounted: list[str] = []

    for key in P.FEATURE_KEYS:
        w = float(weights.get(key, 0.0))
        if not w:
            continue
        is_causal = key in P.CAUSAL_FEATURES
        if w > 0:
            positive_total += w
            if is_causal:
                causal_positive += w
            else:
                misplaced.append(
                    {
                        "feature": key,
                        "label": P.FEATURE_LABELS[key],
                        "weight": round(w, 2),
                        "true_lift": round(_lift(ds, key), 2),
                    }
                )
        elif is_causal:
            against_causal += abs(w)
        else:
            discounted.append(key)

    denominator = positive_total + against_causal
    ratio = causal_positive / denominator if denominator else 0.0
    score = round(20.0 * ratio, 1)

    if not denominator:
        detail = "No positive conviction was expressed, so there is nothing to place."
    else:
        detail = (
            f"{round(ratio * 100)}% of the conviction you expressed sits on the "
            f"{len(P.CAUSAL_FEATURES)} variables that genuinely predict success."
        )
        if misplaced:
            detail += (
                f" {len(misplaced)} variable{'s' if len(misplaced) != 1 else ''} "
                "carried positive weight without durable signal behind it."
            )
        if against_causal:
            detail += " Weight was also placed against a genuinely causal variable."
        if discounted:
            detail += (
                f" Marking {len(discounted)} non-causal "
                f"variable{'s' if len(discounted) != 1 else ''} down cost nothing."
            )

    return {
        "key": "long_term_value",
        "label": "Long-Term Value Creation",
        "score": score,
        "max": 20,
        "detail": detail,
        "components": {
            # Retained under their original names: `causal_weight` is still the
            # numerator and `total_weight` still the denominator, so anything
            # reading these keeps reading the same two roles.
            "causal_weight": round(causal_positive, 2),
            "total_weight": round(denominator, 2),
            "positive_weight": round(positive_total, 2),
            "weight_against_causal": round(against_causal, 2),
            "misplaced_conviction": misplaced,
            "non_causal_discounted": discounted,
        },
    }


# Reported as explicit N/A cards. Forcing a number for a dimension with no
# underlying mechanic would score appearance rather than behaviour -- the exact
# failure this engine exists to avoid. A platform dashboard aggregating across
# simulations should source these from one that actually tests them.
NOT_APPLICABLE = [
    {
        "key": "systems_thinking",
        "label": "Systems Thinking",
        "score": None,
        "max": None,
        "detail": (
            "This simulation is a single-analyst research exercise -- no decision "
            "here has cross-functional or organisational ripple effects to observe. "
            "Not testable on this simulation; would require a scenario built around "
            "organisational interdependency."
        ),
    },
    {
        "key": "leadership",
        "label": "Leadership & People Management",
        "score": None,
        "max": None,
        "detail": (
            "You never manage, hire, or delegate to anyone in this simulation. Not "
            "testable here -- reserved for a simulation built around team leadership."
        ),
    },
]


def build_myelin(
    ds: Dataset, session: Any, revision: dict[str, Any]
) -> dict[str, Any]:
    weights = session.model_weights
    dimensions = [
        strategic_thinking(ds, weights),
        capital_allocation(ds, session.picks, weights, session.cheque_sizes),
        risk_management(ds, session.picks, session.cheque_sizes),
        adaptability(revision),
        long_term_value(ds, weights),
    ]
    total = round(sum(d["score"] for d in dimensions), 1)
    return {
        "dimensions": dimensions,
        "not_applicable": NOT_APPLICABLE,
        "total": total,
        "max": sum(d["max"] for d in dimensions),
        "band": band_for(total),
    }


# --------------------------------------------------------------------------
# Fund result (zero weight, displayed anyway)
# --------------------------------------------------------------------------
def resolve_fund(
    ds: Dataset, picks: list[int], cheque_sizes: dict[str, int] | None = None
) -> dict[str, Any]:
    """Settle the fund at the student's own cheque sizes.

    Sizing matters to the P&L as well as to the score: backing a conviction
    heavily and being right returns more than spreading evenly. That P&L is
    still worth zero points -- but it has to be arithmetically honest, or the
    results screen contradicts the allocation the student just made.
    """
    sizes = cheque_sizes or {}
    rows, returned, wins, deployed = [], 0.0, 0, 0.0
    by_id = {d["id"]: d for d in ds.deals}

    for pid in picks:
        deal = by_id.get(pid)
        if deal is None:
            continue
        cheque = float(sizes.get(str(pid), P.CHEQUE_USD))
        won = deal["outcome"] == 1
        value = cheque * (P.WIN_MULTIPLE if won else P.LOSS_MULTIPLE)
        returned += value
        deployed += cheque
        wins += int(won)
        rows.append(
            {
                "id": pid,
                "name": deal["name"],
                "sector": deal["sector"],
                "cheque_usd": cheque,
                "share_of_fund": round(cheque / P.FUND_POOL_USD, 4),
                "outcome": "Success" if won else "Write-off",
                "returned_usd": value,
            }
        )

    missed = [
        {"id": d["id"], "name": d["name"], "sector": d["sector"]}
        for d in ds.deals
        if d["outcome"] == 1 and d["id"] not in set(picks)
    ]

    return {
        "rows": rows,
        "deployed_usd": deployed,
        "returned_usd": returned,
        "net_usd": returned - deployed,
        "hits": wins,
        "cheques": len(rows),
        "missed_winners": missed,
        "scored": False,
        "note": (
            "Fund P&L carries zero weight. Across 20,000 simulated funds, a "
            "strategy built on the genuinely causal variables still returns zero "
            "winners in roughly one fund in 169. Scoring this number would be "
            "scoring variance, not skill."
        ),
    }


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------
BANDS = ((81, "Investigative"), (61, "Analytical"), (36, "Diligent"), (0, "Reflexive"))


def band_for(total: float) -> str:
    for threshold, name in BANDS:
        if total >= threshold:
            return name
    return "Reflexive"


def build_scorecard(ds: Dataset, session: Any, events: Iterable[Any]) -> dict[str, Any]:
    t = aggregate(events)

    committee_texts = [
        a.get("answer", "") for a in (session.committee_answers or [])
    ]
    per_answer = [analyse_free_text(x) for x in committee_texts]
    falsification = analyse_free_text(session.falsification)
    aggregate_signals = sorted(
        {s for a in per_answer for s in a["signals"]} | set(falsification["signals"])
    )
    committee = {
        "per_answer": per_answer,
        "falsification": falsification,
        "aggregate_signals": aggregate_signals,
    }

    variables = session.thesis_variables or []
    confidence = session.thesis_confidence or {}

    revision = revision_quality(ds, session.w1_snapshot, session.model_weights)
    dimensions = [
        evidence_depth(t),
        provenance(t, committee),
        triangulation(t),
        calibration(ds, variables, confidence),
        revision,
        decision_discipline(ds, session.picks, session.model_weights),
    ]

    total = round(sum(d["score"] for d in dimensions), 1)

    return {
        "dimensions": dimensions,
        "total": total,
        "max": sum(d["max"] for d in dimensions),
        "band": band_for(total),
        # The platform-wide rubric, from the same session. Adaptability is the
        # rescaled Revision Quality object above rather than a second
        # computation of it.
        "myelin": build_myelin(ds, session, revision),
        "committee_analysis": committee,
        "fund": session.fund_result,
        "telemetry": {
            "profiles_opened": len(t.profiles),
            "comparisons": t.comparisons,
            "charts": sorted(t.charts),
            "board_minutes_opened": len(t.minutes_opened),
            "founder_interviews_opened": len(t.interviews_opened),
            "cross_source_companies": len(t.cross_source_companies),
            "contradictions_found": len(t.contradictions_correct),
        },
    }
