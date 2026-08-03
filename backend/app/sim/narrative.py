"""Founder interviews and board minutes -- the substrate for triangulation.

Open Issue 2 in the handoff was that the Triangulation score claimed to measure
"cross-checked N board minutes against founder narratives" but was implemented
as `min(1, profiles_opened/3) * 15` -- a rescaled copy of "profiles opened".

You cannot fix that scoring formula without first giving students something real
to triangulate. So every company carries two independently-worded accounts of
the same period. For a deterministic subset the two accounts *contradict* each
other on a specific, checkable fact, and the contradiction always points at a
Class A or Class C variable -- never at noise. Catching one is genuine analytic
work; the scoring engine can then measure whether it happened.
"""

from __future__ import annotations

import numpy as np

# Each entry: (interview_claim, minutes_line, contradicts_feature, resolution)
# The minutes line is the *true* account; the founder interview is the flattering
# one. That asymmetry is itself a lesson.
CONTRADICTION_TEMPLATES = [
    (
        "Growth has been almost entirely inbound. Customers bring us their own "
        "teams -- we have never really had to buy the expansion.",
        "Approved incremental FY headcount: 4 enterprise AEs and 2 SDRs, funded "
        "from the Series A proceeds, to drive second-year expansion revenue.",
        "customerLed",
        "The founder describes customer-led expansion. The board approved a "
        "sales team to manufacture it. Expansion here was bought, not earned.",
    ),
    (
        "We moved to usage-based pricing early because it aligned us with the "
        "customer. It has been our pricing model from the start.",
        "Resolved: retain annual seat-based contracts for FY commitments. "
        "Usage-based pilot deferred pending finance review.",
        "usageBased",
        "The founder claims usage-based pricing from inception. The board "
        "deferred it. The pricing flag on this company is aspirational.",
    ),
    (
        "I spent years in this market before starting the company. I knew the "
        "buyer before I knew I was going to sell to them.",
        "Founder background noted for the investor update: two years adjacent "
        "to the category, prior role outside the sector.",
        "founder5yrs",
        "The interview implies deep domain tenure. The minutes record two "
        "adjacent years. Tenure is the single strongest real signal in this "
        "dataset -- and it is being overstated here.",
    ),
    (
        "The press cycle in year one was the turning point. It brought us "
        "inbound demand we are still working through.",
        "Noted: Q3 inbound attributable to press coverage did not convert at "
        "forecast. Pipeline quality below cohort average; CAC up quarter on "
        "quarter.",
        "pressYear1",
        "Press is recorded as a turning point in the interview and as a "
        "CAC problem in the minutes. Coverage is more common among failures "
        "than winners.",
    ),
    (
        "Doubling the team after the A was what let us hold the line on "
        "delivery. We would do it again.",
        "Discussed: FY burn tracking materially above plan following post-A "
        "hiring. Instructed management to model a reduced-headcount scenario.",
        "headcountDoubled",
        "The founder frames post-A doubling as decisive. The board was "
        "modelling how to reverse it.",
    ),
    (
        "Launching across three markets in year two was the right call. It gave "
        "us the surface area we needed.",
        "Second and third market contribution below plan. Agreed to consolidate "
        "go-to-market into the home market for the coming year.",
        "multiGeo",
        "Multi-geo launch is defended in the interview and being unwound in "
        "the minutes.",
    ),
]

# Non-contradictory filler, so that a student who opens two sources on a clean
# company sees a consistent story rather than an obviously blank one.
CLEAN_INTERVIEW = [
    "The first eighteen months were mostly about finding a repeatable motion. "
    "Everything before that was noise.",
    "We were slower than our peers to raise and it turned out to be an "
    "advantage. It forced discipline on the cost side.",
    "The team stayed small for longer than investors were comfortable with.",
    "Our best quarter came from a segment we originally thought was too small "
    "to matter.",
    "We lost a founding engineer in year two. It set us back two quarters and "
    "we rebuilt around it.",
]

CLEAN_MINUTES = [
    "Reviewed FY plan. Management confirmed pipeline coverage of 3.1x against "
    "the revised target. No objections recorded.",
    "Approved the audited accounts. Discussed cash position; no additional "
    "facility required this year.",
    "Noted the departure of a founding engineer. Replacement search approved; "
    "no change to the product roadmap.",
    "Reviewed cohort retention by segment. Agreed to reallocate CS coverage "
    "toward the mid-market cohort.",
    "Discussed the pricing review. Deferred to the next meeting pending "
    "finance analysis.",
]

CONTRADICTION_RATE = 0.35


def build(
    rng: np.random.Generator,
    n: int,
    flags: np.ndarray,
    feature_index: dict[str, int],
) -> dict[str, list]:
    """Generate paired narratives for a population of `n` companies.

    A contradiction is only planted when the company actually carries the flag
    in question -- otherwise the "contradiction" would be a statement about a
    variable the company does not have, which is noise rather than a finding.
    """
    interviews: list[str] = []
    minutes: list[str] = []
    contradicts: list[str | None] = []
    resolutions: list[str | None] = []

    plant = rng.random(n) < CONTRADICTION_RATE
    template_pick = rng.integers(0, len(CONTRADICTION_TEMPLATES), n)
    clean_i = rng.integers(0, len(CLEAN_INTERVIEW), n)
    clean_m = rng.integers(0, len(CLEAN_MINUTES), n)

    for i in range(n):
        placed = False
        if plant[i]:
            # Walk the template list from the drawn offset until we find one
            # whose feature this company actually carries.
            for offset in range(len(CONTRADICTION_TEMPLATES)):
                t = CONTRADICTION_TEMPLATES[
                    (int(template_pick[i]) + offset) % len(CONTRADICTION_TEMPLATES)
                ]
                interview, minute, feature, resolution = t
                if flags[i, feature_index[feature]] == 1:
                    interviews.append(interview)
                    minutes.append(minute)
                    contradicts.append(feature)
                    resolutions.append(resolution)
                    placed = True
                    break
        if not placed:
            interviews.append(CLEAN_INTERVIEW[int(clean_i[i])])
            minutes.append(CLEAN_MINUTES[int(clean_m[i])])
            contradicts.append(None)
            resolutions.append(None)

    return {
        "founder_interview": interviews,
        "board_minutes": minutes,
        "contradicts_feature": contradicts,
        "contradiction_resolution": resolutions,
    }
