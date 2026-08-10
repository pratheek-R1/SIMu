# Scoring Methodology — Technical Handoff

*How every number on the scorecard is computed, traced from raw student action to final score.*

> **Status — implemented.** This document originally described a JavaScript prototype whose scoring ran in the browser. The engine now lives server-side in [`backend/app/scoring.py`](backend/app/scoring.py) and every dimension below is implemented there. Where the prototype and the implementation differ, **the implementation is authoritative** and this document has been updated to match it. The prototype's JS is quoted only where it explains why something changed.
>
> Three defects listed in the original Part 4 as known limitations have been fixed and are documented at [Part 4](#part-4--defects-from-the-prototype-and-how-they-were-fixed). Telemetry is now derived from API calls the student's actions actually required, rather than from a browser-side counter object the client could inflate at will.

---

## The one rule everything else follows

**Score the process. Report the outcome. Never let the outcome influence the score.**

Concretely: the fund's actual profit and loss is computed, displayed prominently, and contributes **zero points** to any dimension. This was validated, not assumed — a Monte Carlo simulation of 20,000 funds showed a genuinely well-reasoned strategy still returns nothing in roughly 1 fund in 60, purely from variance. If P&L drove the score, we would be grading dice rolls. Every formula below is built from *behavior*, not from whether the student's picks happened to win.

---

## Two scorecards, not one

The engine produces two separate reports from the same underlying student session:

1. **Myelin standard scorecard** — 5 dimensions, 100 points, matches the platform-wide rubric. Two additional dimensions (Systems Thinking, Leadership & People Management) are explicitly marked **N/A** rather than assigned a fabricated number, because this simulation has no mechanic that generates evidence for them (see Part 3).
2. **Process detail** — this simulation's own 6-dimension diagnostic breakdown (Evidence Depth, Provenance, Triangulation, Calibration, Revision Quality, Decision Discipline), kept alongside the Myelin scorecard because it's more granular and some of it feeds directly into the Myelin dimensions above it.

---

## Part 1 — Where the raw data comes from

Every score is a function of two things: a live **telemetry object** that accumulates as the student acts, and a set of **ground-truth values** baked into the dataset at generation time.

### 1.1 The telemetry object

Telemetry is no longer a browser-side counter. Events are written server-side in response to the API calls a student's actions actually require — opening a profile **is** a `GET` on the profile endpoint — and the scorecard is computed by replaying them. A client cannot POST itself a score it did not earn.

`Telemetry` in [`scoring.py`](backend/app/scoring.py) aggregates these event kinds:

```python
profiles: set[int]                     # distinct companies whose profile was opened
comparisons: int                       # comparison views built
charts: set[str]                       # distinct charts hovered, allowlisted server-side
minutes_opened: set[int]               # companies whose board minutes were opened
interviews_opened: set[int]            # companies whose founder interview was opened
contradictions_correct: set[int]       # correctly flagged contradictions
provenance_query_pre_reveal: bool      # asked what was missing BEFORE the archive
ghost_query: bool                      # searched a company absent from the set
comparison_group_pre_reveal: bool      # asked for a comparison group BEFORE the archive
archive_questioned_post_reveal: bool   # questioned whether the archive was itself complete
```

Two properties of this matter for scoring integrity:

- **`charts` is allowlisted.** A hover is the one signal the server cannot observe, so the client reports it. `VALID_CHART_IDS` bounds what a hand-crafted POST can earn, and the set deduplicates. Its contribution to Evidence Depth is additionally capped — see [3.1](#31-evidence-depth--20-points).
- **`cross_source_companies`** is `minutes_opened & interviews_opened` — companies where the student read *both* accounts of the same period. This is what Triangulation measures, and it replaces the prototype's `T.minutes`.

### 1.2 Ground-truth values

Every one of the 16 binary features has a known lift, computed from the realised dataset rather than the parameters, so a student is judged against evidence they could actually have seen:

```python
def _lift(ds: Dataset, key: str) -> float:
    return min(ds.sample_lift(key), 12.0)  # clamped so a near-zero denominator cannot dominate
```

A `lift` near 1.0 means the feature carries no real signal (a trap). Well above 1.0 means genuinely predictive. The three causal features are declared once, in [`parameters.py`](backend/app/sim/parameters.py), and every consumer reads them from there:

```python
CAUSAL_FEATURES = ("founder5yrs", "customerLed", "usageBased")
```

---

## Part 2 — Myelin standard scorecard, dimension by dimension

Implemented in `build_myelin()`. Returned on the scorecard payload under `myelin`, alongside the process detail of [Part 3](#part-3--process-detail-this-simulations-own-diagnostic-layer).

### 2.1 Strategic Thinking — 20 points

**Question it answers:** taken as a whole, does the student's final model represent one coherent, evidence-aligned point of view — or does it contain self-contradictions (rewarding a variable that predicts failure)?

```python
agreeing = total = 0.0
for key in P.FEATURE_KEYS:
    w = float(weights.get(key, 0.0))
    if not w:
        continue
    total += abs(w)
    if (w > 0) == (_lift(ds, key) > 1.0):
        agreeing += abs(w)
score = round(20.0 * (agreeing / total if total else 0.0), 1)
```

For every non-zero weight in the final model, check whether its sign agrees with the direction of true lift (positive weight on a lift-above-1 variable, or negative weight on a lift-below-1 variable). Sum the magnitude of agreeing weights, divide by total weight magnitude, scale to 20. Conflicting variables are itemised in `components.conflicts` so a facilitator can see exactly which weight cost what.

**Worked example:** a student weights `founder_domain_tenure_5y` at **+3** (true lift 4.08×, correct direction) and `headcount_2x_post_a` at **−2** (true lift 0.62×, correct direction) and nothing else. `sNum = 3+2 = 5`, `sDen = 5`. Score: `20 × (5/5) = 20/20`.

Now suppose they'd instead set `headcount_2x_post_a` to **+2** (wrong direction — this variable predicts failure). `sNum = 3` (only the tenure weight agrees), `sDen = 5`. Score: `20 × (3/5) = 12/20`.

### 2.2 Capital Allocation — 20 points

**Question it answers:** did more capital go behind the picks the student's own model rated highest, or was cheque sizing disconnected from their stated conviction?

**The capital-allocation mechanic is implemented.** The student sizes 5 cheques themselves from a fixed pool of `FUND_POOL_USD` (50M USD == ₹415 Cr) on the deal-flow screen, in `CHEQUE_STEP_USD` (1M USD) increments, each cheque bounded by `CHEQUE_MIN_USD`/`CHEQUE_MAX_USD`. Sizes are stored on the session as `cheque_sizes`, keyed by deal id.

Amounts are **whole-USD integers** and the total is checked for exact equality with the pool before deploy is allowed. Part 5 of the original handoff warned that a rounding error here silently corrupts both this dimension and Risk Management; integer arithmetic plus exact equality makes that class of bug impossible rather than unlikely.

```python
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

ratio = 0.5 if pairs == 0 else concordant / pairs
score = round(20.0 * ratio, 1)
```

This is a **concordance measure over every pair of the 5 picks** (10 pairs total): for each pair, does the one with the higher model score also get the larger cheque? Count agreeing pairs, divide by total comparable pairs. Ties on either axis are excluded from the denominator. If a student sizes every cheque identically (no differentiation at all), the function returns a neutral **0.5** rather than 0 or 1 — no information was expressed, so no judgment is made either way.

**Worked example:** 5 picks with model scores `[8, 6, 5, 3, 1]` and cheque sizes `[150, 120, 80, 40, 25]` (in ₹Cr) — perfectly monotonic. All 10 pairs agree. `capital = 20 × 1.0 = 20/20`.

If instead the lowest-scored pick got the largest cheque (sizes `[25, 120, 80, 40, 150]`), several pairs would disagree, and the score would fall proportionally — e.g. 6 of 10 pairs agreeing gives `20 × 0.6 = 12/20`.

### 2.3 Risk Management — 15 points

**Question it answers:** is the portfolio diversified, or is it a concentrated, correlated bet dressed up as five separate decisions?

```python
sectors = {by_id[p]["sector"] for p in picks if p in by_id}
diversity = len(sectors) / max(1, len(picks))

total = sum(sizes.values()) or P.FUND_POOL_USD
max_share = max((sizes.get(str(p), 0) for p in picks), default=0) / total
free = P.CONCENTRATION_FREE_SHARE  # 0.30
penalty = max(0.0, min(1.0, (max_share - free) / (1.0 - free)))

score = round(15.0 * (0.5 * diversity + 0.5 * (1.0 - penalty)), 1)
```

Two components, weighted equally:
- **Sector diversity** — unique sectors among the 5 picks, divided by 5. All-different sectors = 1.0. All-same sector = 0.2.
- **Concentration penalty** — triggers only if any single cheque exceeds `CONCENTRATION_FREE_SHARE` (30%) of the fund. Below that threshold, no penalty. At 100% concentration the penalty reaches its maximum of 1.0. In practice `CHEQUE_MAX_USD` caps a single position at 60% of the pool, so the penalty tops out around 0.43.

**Worked example:** 5 picks across 5 different sectors (`diversity = 1.0`), largest single cheque is ₹150 Cr of ₹415 Cr total (`maxShare = 0.361`). `concentrationPenalty = (0.361-0.30)/0.70 = 0.088`. `risk = 15 × (0.5×1.0 + 0.5×0.912) = 15 × 0.956 = 14/15`.

### 2.4 Adaptability — 25 points

**Question it answers:** after the archive arrived, did the student's model update in the right direction, keeping what was right and discarding what wasn't — without overcorrecting on the parts that were actually correct?

This dimension is a direct, rescaled reuse of the Process-detail "Revision Quality" score (Part 3.5). It is **not recomputed** — `adaptability()` takes the already-built Revision Quality result and rescales it, so two dimensions claiming to measure the same behaviour cannot drift apart:

```python
def adaptability(revision: dict[str, Any]) -> dict[str, Any]:
    score = round(revision["score"] * (25.0 / 15.0), 1)
```

The underlying Revision Quality calculation:

```python
numerator = denominator = 0.0
for key in P.FEATURE_KEYS:
    delta = float(weights.get(key, 0.0)) - float(w1.get(key, 0.0))
    if delta == 0:
        continue
    denominator += abs(delta)
    if (delta > 0) == (_lift(ds, key) > 1.0):
        numerator += abs(delta)

direction_score = (10.0 * numerator / denominator) if denominator else 0.0
kept = sum(1 for k in P.CAUSAL_FEATURES if float(weights.get(k, 0.0)) > 0)
score = round(direction_score + 5.0 * kept / len(P.CAUSAL_FEATURES), 1)
```

`w1_snapshot` is captured the instant the Model screen first loads — this is the thesis-seeded starting point, before any manual adjustment. `num/den` measures what fraction of every weight *change* moved in the direction the evidence actually supports. The `kept` term adds a flat bonus for how many of the 3 genuinely causal variables still carry positive weight at the end — this specifically catches the failure mode of a student who panics after the archive and zeroes out everything, including the parts of their thesis that were right.

**Worked example:** a student who starts with a thesis-seeded model (`w1_snapshot`), moves 8 units of total weight, of which 6 units' worth of changes align with true lift direction, and finishes with all 3 `CAUSAL` variables positively weighted: `adaptRaw = 10×(6/8) + 5×(3/3) = 7.5 + 5 = 12.5/15` → `adapt = round(12.5 × 25/15) = round(20.8) = 21/25`.

### 2.5 Long-Term Value Creation — 20 points

**Question it answers:** does the final model's conviction sit on durable, causal signal, or on variables that look strong in the short term but carry no real predictive weight?

```python
causal_weight = total = 0.0
for key in P.FEATURE_KEYS:
    w = float(weights.get(key, 0.0))
    if not w:
        continue
    total += abs(w)
    if key in P.CAUSAL_FEATURES and w > 0:
        causal_weight += w

score = round(20.0 * (causal_weight / total if total else 0.0), 1)
```

Of all the conviction the student expressed (sum of absolute weight across every non-zero variable), what fraction sits specifically on the 3 hardcoded `CAUSAL` variables, and only counts if weighted positively (a `CAUSAL` variable weighted negatively earns nothing here — that would be a different, separate error).

**Worked example:** final model has `founder_domain_tenure_5y: +3`, `usage_based_pricing: +3`, `headcount_2x_post_a: -2`, `series_a_above_20m: -2`. `ltvDen = 3+3+2+2 = 10`. `ltvNum = 3+3 = 6` (only the two positive-causal weights count; the two negative-trap weights are correct reasoning but don't count toward *this* dimension, since they're not durable positive signal — they're the absence of a trap, a different form of quality captured elsewhere). `ltv = round(20 × 6/10) = 12/20`.

### 2.6 Total and the two N/A dimensions

```python
total = round(sum(d["score"] for d in dimensions), 1)   # out of 100
```

**Systems Thinking** and **Leadership & People Management** are returned in a separate `not_applicable` list with `score: None`, and rendered as explicit **N/A** cards on both the scorecard screen and the printable report — not scored zero and not omitted silently:

> *Systems Thinking — "This simulation is a single-analyst research exercise — no decision here has cross-functional or organizational ripple effects to observe. Not testable on this simulation; would require a different Myelin scenario built around organizational interdependency."*
>
> *Leadership & People Management — "You never manage, hire, or delegate to anyone in this simulation. Not testable here — reserved for a Myelin simulation built around team leadership."*

**This is a deliberate design decision, not a gap to be filled by a proxy metric.** Forcing a number for a dimension with no underlying mechanic would mean scoring appearance rather than behavior — the exact failure mode this entire engine exists to avoid. If Myelin's platform dashboard aggregates scores across multiple simulations, these two dimensions should be sourced from whichever simulation actually tests them, not backfilled here.

---

## Part 3 — Process detail (this simulation's own diagnostic layer)

Kept as a secondary section beneath the Myelin scorecard. More granular, and several of its components (`num`, `den`, `kept`, `lift`) are the literal inputs to the Myelin dimensions above.

### 3.1 Evidence Depth — 20 points
```python
profile_points = len(t.profiles) * 0.6
comparison_points = t.comparisons * 4
chart_points = min(CHART_POINTS_CAP, len(t.charts) * 2)   # CHART_POINTS_CAP = 8.0
score = min(20.0, round(profile_points + comparison_points + chart_points, 1))
```
Profiles opened, weighted lightly (0.6 each, since opening is a low-effort action); comparisons run, weighted heavily (4 each); distinct charts genuinely hovered, weighted moderately (2 each). Capped at 20.

**Changed from the prototype:** chart engagement is now capped at 8 of the 20 points. Chart hovers are the one signal the client self-reports and the cheapest of the three to produce; uncapped, they stood in for research they do not evidence. A real session scored **18.0/20 here from nine chart hovers with zero profiles opened and zero comparisons built** — the same behaviour now scores 8.0. Reading companies and building comparisons carry the remaining 12.

### 3.2 Provenance and Completeness — 25 points
```python
parts = {
    "asked_where_the_data_came_from": 10 if plain_language else 0,
    "searched_for_a_company_not_in_the_set": 5 if t.ghost_query else 0,
    "requested_a_comparison_group_before_the_reveal": 5 if t.comparison_group_pre_reveal else 0,
    "questioned_the_archive_after_the_reveal": 5 if t.archive_questioned_post_reveal else 0,
}
```
10 points for asking in plain language what data was missing **before the reveal**, or raising it with the committee; 5 for searching a company absent from the winners set; 5 for explicitly requesting a comparison group **before the archive arrives**; 5 for questioning whether the recovered archive was itself complete, **after** the reveal.

**Changed from the prototype:** every one of these now requires a specific behaviour. The prototype awarded 10 points for no provenance-seeking behaviour at all, and 5 more for simply reaching the Evidence screen. Under this implementation a student who walks forward through the flow without asking anything scores **0/25**.

### 3.3 Triangulation — 15 points
```python
finding = min(1.0, len(t.contradictions_correct) / 3.0) * 10.0
breadth = min(1.0, len(t.cross_source_companies) / 5.0) * 5.0
score = round(finding + breadth, 1)
```
Requires reading **both** the board minutes and the founder interview on the same company (`cross_source_companies`), and correctly identifying planted contradictions between the two accounts. Opening profiles alone earns zero — see [Part 4](#part-4--defects-from-the-prototype-and-how-they-were-fixed).

### 3.4 Calibration — 15 points
```python
for key in variables:
    strength = _true_strength(_lift(ds, key))   # clamp((lift - 1) / 3, 0, 1)
    stated = confidence.get(key, 50) / 100.0
    brier_total += (stated - strength) ** 2

score = max(0.0, round(15.0 * (1.0 - brier_total / len(variables)), 1))
```
Brier-score style: for each thesis variable, map true lift to a 0–1 "true strength," square the gap against the student's stated confidence, average across variables, invert. Rewards honest uncertainty over confident wrongness.

### 3.5 Revision Quality — 15 points
The native 15-point scale of the calculation quoted in [2.4](#24-adaptability--25-points). Adaptability is this object rescaled, not a second computation.

### 3.6 Decision Discipline — 10 points
```python
ranked = sorted(ds.deals, key=lambda d: -model_score(d["flags"], weights))
top10 = {d["id"] for d in ranked[:10]}
score = round(10.0 * sum(1 for p in picks if p in top10) / P.N_CHEQUES, 1)
```
Of the 5 actual cheques written, what fraction went to companies inside the model's own top-10 ranking.

### 3.7 Band
```python
BANDS = ((81, "Investigative"), (61, "Analytical"), (36, "Diligent"), (0, "Reflexive"))
```
Applied to both scorecards independently — each is out of 100.

---

## Part 4 — Defects from the prototype, and how they were fixed

### Fixed — `T.minutes` did not measure triangulation

It was incremented on the identical line as `T.prof`, unconditionally, every time a profile opened:
```javascript
function openWin(id) { ... T.prof++; T.minutes++; ... }   // prototype
```
Triangulation was therefore arithmetically `min(1, profiles_opened / 3) * 15` while the UI claimed it measured "cross-checked board minutes against founder narratives." A student who opened three profiles and read nothing scored full marks, and the same flaw leaked 5 of the 25 Provenance points.

**Now:** option (a) from the original recommendation. `board_minutes_opened` and `founder_interview_opened` are separate telemetry events, emitted server-side when those endpoints are called. Triangulation requires opening both sources on the *same* company and correctly flagging a planted contradiction. Opening profiles alone earns zero. Verified by the integration test, which asserts the naive analyst scores exactly 0 here.

### Fixed — comparison-group credit fired automatically

`T.cgroup` was set on reaching the Evidence screen, which every student does by walking forward through a linear flow.

**Now:** the point requires an explicit request for a comparison group, and only counts if made *before* the archive arrives — the behaviour it was always meant to reward. Screen context is recorded on every telemetry event, so "before the reveal" is checkable rather than assumed.

### Fixed — the committee free-text was never read

**Now:** scored by a deterministic keyword-and-structure rubric (`analyse_free_text`) covering four signals — naming the missing data, asking for a comparison group, quantifying a claim, and stating a falsifiable threshold. The matched span for each is reported on the scorecard so a facilitator can audit exactly why a point was awarded.

This rubric is gameable by a student who knows it. That is a deliberate trade against the design goal of no ML in the scoring loop: every dimension stays deterministic and auditable from recorded events. It is a floor on written reasoning, not a judgement of it, and the UI says so.

### Fixed — Evidence Depth could be maxed by chart hovers alone

See [3.1](#31-evidence-depth--20-points). Capped at 8 of 20.

### Fixed — duplicate reports made a session's report unreadable

`reports` had no unique constraint on `session_id`, so a second `POST /report` inserted a duplicate row and every subsequent read raised `MultipleResultsFound` — a 500 that permanently cost the student access to their own report. The constraint now exists, and the endpoint collapses any duplicates a pre-existing database already contains.

### Open — the weight-derived dimensions are correlated, not independent

**Strategic Thinking, Long-Term Value Creation, and Revision Quality/Adaptability** all derive from the same weights/lift/causal inputs, asking different but related questions of one weight vector (final-state coherence, final-state durability, change-over-time correctness). Defensible as three genuinely different questions, but they are **not orthogonal axes** and should not be presented as such. This is documented in the code rather than fixed, because the alternative — dropping one — loses information a facilitator legitimately wants.

---

## Part 5 — Verification status

| # | Original requirement | Status |
|---|---|---|
| 1 | `T.minutes` fixed to measure real cross-checking, or Triangulation relabelled | **Done.** Fixed, not relabelled — see Part 4. Asserted in the integration test. |
| 2 | Capital-allocation UI enforces the pool total exactly before enabling deploy | **Done.** Whole-USD integers, exact-equality check server-side at `PUT /picks` and again at `POST /deploy`; deploy is refused with a 400 naming the shortfall. The client button stays disabled until the allocation balances. |
| 3 | Re-run validation after any change to `parameters.py`/`generator.py` | **Automated.** `run_gate()` executes at application startup and logs `VALIDATION GATE FAILED` loudly rather than failing quietly in front of a cohort. Also exposed at `GET /admin/gate`. |

### Running the checks

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest tests -q
```

The integration test plays a naive and an investigative analyst through the entire flow and asserts what the engine is supposed to distinguish — including that the naive analyst scores 0 on Triangulation and 0 on Provenance, that perfectly monotonic cheque sizing scores 20/20 on Capital Allocation while an even split scores a neutral 10/20, that Adaptability stays an exact rescale of Revision Quality, and that the two N/A dimensions are never given a number.

It also asserts the reverse of the outcome rule: the investigative analyst must outscore the naive one on **both** scorecards, regardless of which fund happened to make money.

### One thing still worth a human decision

`CHEQUE_MAX_USD` is 30M of a 50M pool, so a single position can reach 60% of the fund. The Risk Management concentration penalty therefore tops out around 0.43 rather than 1.0 — the maximum penalty described in [2.3](#23-risk-management--15-points) is unreachable by construction. That is arguably correct (the UI already prevents the most reckless allocation) but it means the dimension's full range is never used. Lowering the cap or rescaling the penalty against the reachable maximum are both defensible; neither was chosen unilaterally.
