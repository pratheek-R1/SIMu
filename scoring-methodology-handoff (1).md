# Scoring Methodology — Technical Handoff

*How every number on the scorecard is computed, traced from raw student action to final score. Formulas quoted exactly as implemented in `scorecard()`, not as originally designed — anywhere the two differ, both are shown.*

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

```javascript
const T = {
  prof: 0,       // full company profiles opened
  cmp: 0,        // companies added to the comparison view
  charts: 0,     // DISTINCT charts hovered (not just opened — see note below)
  q: [],         // every search query submitted, in order
  prov: 0,       // 1 if any search matched a "missing data" meta-query
  ghost: 0,      // 1 if any search matched a competitor name absent from the dataset
  cgroup: 0,     // 1 once the Evidence screen has been reached
  minutes: 0,    // currently identical to `prof` — see Known Limitation, Part 4
  W1: null       // snapshot of model weights the instant the Model screen loads
};
```

`T.charts` specifically only increments the **first time** a student hovers a given chart's data points — opening a profile that contains a chart does not, by itself, earn credit. This was a deliberate fix during development after we found the original implementation credited chart engagement just for opening the page a chart lived on.

### 1.2 Ground-truth values

Every one of the 16 binary features in the dataset has a known, generated `lift`:

```javascript
const lift = k => (FA[k][0] / 500) / (FA[k][1] / NF);
```
`FA[k]` = `[count of the 500 winners with feature k, count of the 2,500 failures with feature k]`. `NF` = `2500`.

A `lift` near 1.0 means the feature carries no real signal (a trap). A `lift` well above 1.0 means it's genuinely predictive. Three features are hardcoded as the dataset's real causal signal:

```javascript
const CAUSAL = ['founder_domain_tenure_5y', 'expansion_customer_led', 'usage_based_pricing'];
```

---

## Part 2 — Myelin standard scorecard, dimension by dimension

### 2.1 Strategic Thinking — 20 points

**Question it answers:** taken as a whole, does the student's final model represent one coherent, evidence-aligned point of view — or does it contain self-contradictions (rewarding a variable that predicts failure)?

```javascript
let sNum = 0, sDen = 0;
FK.forEach(k => {
  const w = W[k] || 0;
  if (!w) return;
  sDen += Math.abs(w);
  if (Math.sign(w) === Math.sign(lift(k) - 1)) sNum += Math.abs(w);
});
const strategic = Math.round(20 * (sDen ? sNum/sDen : 0));
```

For every non-zero weight the student set in their final model (`W`), check whether its sign agrees with the direction of true lift (positive weight on a lift-above-1 variable, or negative weight on a lift-below-1 variable). Sum the magnitude of agreeing weights, divide by total weight magnitude, scale to 20.

**Worked example:** a student weights `founder_domain_tenure_5y` at **+3** (true lift 4.08×, correct direction) and `headcount_2x_post_a` at **−2** (true lift 0.62×, correct direction) and nothing else. `sNum = 3+2 = 5`, `sDen = 5`. Score: `20 × (5/5) = 20/20`.

Now suppose they'd instead set `headcount_2x_post_a` to **+2** (wrong direction — this variable predicts failure). `sNum = 3` (only the tenure weight agrees), `sDen = 5`. Score: `20 × (3/5) = 12/20`.

### 2.2 Capital Allocation — 20 points

**Question it answers:** did more capital go behind the picks the student's own model rated highest, or was cheque sizing disconnected from their stated conviction?

Requires the deal-flow capital-allocation mechanic: the student sizes 5 cheques themselves from a fixed ₹415 Cr pool (rather than 5 identical fixed cheques), captured in a `CHEQUE` object keyed by deal index.

```javascript
function capitalConcordance() {
  const p = [...picks];
  if (p.length < 2) return 0.5;
  const scores = p.map(i => mscore(DF[i][6]));   // model score per pick
  const sizes = p.map(i => CHEQUE[i] || 0);        // cheque size per pick
  let conc = 0, pairs = 0;
  for (let a = 0; a < p.length; a++)
    for (let b = a+1; b < p.length; b++) {
      const sd = scores[a] - scores[b], zd = sizes[a] - sizes[b];
      if (sd === 0 || zd === 0) continue;
      pairs++;
      if (Math.sign(sd) === Math.sign(zd)) conc++;
    }
  return pairs ? conc/pairs : 0.5;
}
const capital = Math.round(20 * capitalConcordance());
```

This is a **concordance measure over every pair of the 5 picks** (10 pairs total): for each pair, does the one with the higher model score also get the larger cheque? Count agreeing pairs, divide by total comparable pairs. Ties on either axis are excluded from the denominator. If a student sizes every cheque identically (no differentiation at all), the function returns a neutral **0.5** rather than 0 or 1 — no information was expressed, so no judgment is made either way.

**Worked example:** 5 picks with model scores `[8, 6, 5, 3, 1]` and cheque sizes `[150, 120, 80, 40, 25]` (in ₹Cr) — perfectly monotonic. All 10 pairs agree. `capital = 20 × 1.0 = 20/20`.

If instead the lowest-scored pick got the largest cheque (sizes `[25, 120, 80, 40, 150]`), several pairs would disagree, and the score would fall proportionally — e.g. 6 of 10 pairs agreeing gives `20 × 0.6 = 12/20`.

### 2.3 Risk Management — 15 points

**Question it answers:** is the portfolio diversified, or is it a concentrated, correlated bet dressed up as five separate decisions?

```javascript
function riskParts() {
  const p = [...picks];
  const sectors = new Set(p.map(i => DF[i][1]));
  const diversity = sectors.size / Math.max(1, p.length);
  const total = Object.values(CHEQUE).reduce((a,b) => a+b, 0) || 1;
  const maxShare = p.length ? Math.max(...p.map(i => CHEQUE[i]||0)) / total : 0;
  const concentrationPenalty = Math.max(0, Math.min(1, (maxShare - 0.30) / 0.70));
  return { diversity, concentrationPenalty };
}
const { diversity, concentrationPenalty } = riskParts();
const risk = Math.round(15 * (0.5*diversity + 0.5*(1-concentrationPenalty)));
```

Two components, weighted equally:
- **Sector diversity** — unique sectors among the 5 picks, divided by 5. All-different sectors = 1.0. All-same sector = 0.2.
- **Concentration penalty** — triggers only if any single cheque exceeds 30% of the total fund. Below that threshold, no penalty. At 100% concentration (one company gets the entire fund), the penalty reaches its maximum of 1.0.

**Worked example:** 5 picks across 5 different sectors (`diversity = 1.0`), largest single cheque is ₹150 Cr of ₹415 Cr total (`maxShare = 0.361`). `concentrationPenalty = (0.361-0.30)/0.70 = 0.088`. `risk = 15 × (0.5×1.0 + 0.5×0.912) = 15 × 0.956 = 14/15`.

### 2.4 Adaptability — 25 points

**Question it answers:** after the archive arrived, did the student's model update in the right direction, keeping what was right and discarding what wasn't — without overcorrecting on the parts that were actually correct?

This dimension is a direct, rescaled reuse of the Process-detail "Revision Quality" formula (Part 3.5). The underlying calculation is identical; only the point scale changes, from 15 to 25.

```javascript
// den/num computed once, shared with the Process-detail Revision Quality score:
let num = 0, den = 0;
FK.forEach(k => {
  const d = (W[k]||0) - (T.W1[k]||0);   // change from thesis-seeded weight to final weight
  if (!d) return;
  den += Math.abs(d);
  if (Math.sign(d) === Math.sign(lift(k) - 1)) num += Math.abs(d);
});
const kept = CAUSAL.filter(k => (W[k]||0) > 0).length;
const adaptRaw = (den ? 10*num/den : 0) + 5*(kept/3);   // out of 15
const adapt = Math.round(adaptRaw * (25/15));             // rescaled to 25
```

`T.W1` is captured the instant the Model screen first loads — this is the thesis-seeded starting point, before any manual adjustment. `num/den` measures what fraction of every weight *change* moved in the direction the evidence actually supports. The `kept` term adds a flat bonus for how many of the 3 genuinely causal variables still carry positive weight at the end — this specifically catches the failure mode of a student who panics after the archive and zeroes out everything, including the parts of their thesis that were right.

**Worked example:** a student who starts with a thesis-seeded model (`T.W1`), moves 8 units of total weight, of which 6 units' worth of changes align with true lift direction, and finishes with all 3 `CAUSAL` variables positively weighted: `adaptRaw = 10×(6/8) + 5×(3/3) = 7.5 + 5 = 12.5/15` → `adapt = round(12.5 × 25/15) = round(20.8) = 21/25`.

### 2.5 Long-Term Value Creation — 20 points

**Question it answers:** does the final model's conviction sit on durable, causal signal, or on variables that look strong in the short term but carry no real predictive weight?

```javascript
let ltvNum = 0, ltvDen = 0;
FK.forEach(k => {
  const w = W[k] || 0;
  if (!w) return;
  ltvDen += Math.abs(w);
  if (CAUSAL.includes(k) && w > 0) ltvNum += w;
});
const ltv = Math.round(20 * (ltvDen ? ltvNum/ltvDen : 0));
```

Of all the conviction the student expressed (sum of absolute weight across every non-zero variable), what fraction sits specifically on the 3 hardcoded `CAUSAL` variables, and only counts if weighted positively (a `CAUSAL` variable weighted negatively earns nothing here — that would be a different, separate error).

**Worked example:** final model has `founder_domain_tenure_5y: +3`, `usage_based_pricing: +3`, `headcount_2x_post_a: -2`, `series_a_above_20m: -2`. `ltvDen = 3+3+2+2 = 10`. `ltvNum = 3+3 = 6` (only the two positive-causal weights count; the two negative-trap weights are correct reasoning but don't count toward *this* dimension, since they're not durable positive signal — they're the absence of a trap, a different form of quality captured elsewhere). `ltv = round(20 × 6/10) = 12/20`.

### 2.6 Total and the two N/A dimensions

```javascript
const myelinTot = strategic + capital + risk + adapt + ltv;   // out of 100
```

**Systems Thinking** and **Leadership & People Management** are rendered as explicit **N/A** cards, not scored zero and not omitted silently:

> *Systems Thinking — "This simulation is a single-analyst research exercise — no decision here has cross-functional or organizational ripple effects to observe. Not testable on this simulation; would require a different Myelin scenario built around organizational interdependency."*
>
> *Leadership & People Management — "You never manage, hire, or delegate to anyone in this simulation. Not testable here — reserved for a Myelin simulation built around team leadership."*

**This is a deliberate design decision, not a gap to be filled by a proxy metric.** Forcing a number for a dimension with no underlying mechanic would mean scoring appearance rather than behavior — the exact failure mode this entire engine exists to avoid. If Myelin's platform dashboard aggregates scores across multiple simulations, these two dimensions should be sourced from whichever simulation actually tests them, not backfilled here.

---

## Part 3 — Process detail (this simulation's own diagnostic layer)

Kept as a secondary section beneath the Myelin scorecard. More granular, and several of its components (`num`, `den`, `kept`, `lift`) are the literal inputs to the Myelin dimensions above.

### 3.1 Evidence Depth — 20 points
```javascript
const depth = Math.min(20, Math.round(T.prof*0.6 + T.cmp*4 + T.charts*2));
```
Profiles opened, weighted lightly (0.6 each, since opening is a low-effort action); comparisons run, weighted heavily (4 each); distinct charts genuinely hovered, weighted moderately (2 each). Capped at 20.

### 3.2 Provenance and Completeness — 25 points
```javascript
const prov = (T.prov?10:0) + (T.ghost?5:0) + (T.cgroup?5:0) + (T.minutes?5:0);
```
10 points for querying missing data in plain language; 5 for searching a competitor name absent from the dataset; 5 for reaching the Evidence screen; 5 tied to `T.minutes` (see Known Limitation below — this last 5 points is not currently earning what its label implies).

### 3.3 Triangulation — 15 points
```javascript
const tri = Math.round(15 * (T.minutes ? Math.min(1, T.minutes/3) : 0));
```

### 3.4 Calibration — 15 points
```javascript
let br = 0;
vars.forEach(k => {
  const s = Math.max(0, Math.min(1, (lift(k)-1)/3));
  br += Math.pow(CONF[k]/100 - s, 2);
});
const calib = Math.round(15 * (1 - br / Math.max(1, vars.length)));
```
Brier-score style: for each thesis variable, map true lift to a 0–1 "true strength," square the gap against the student's stated confidence, average across variables, invert. Rewards honest uncertainty over confident wrongness.

### 3.5 Revision Quality — 15 points
```javascript
const revis = Math.round((den ? 10*num/den : 0) + 5*(kept/3));
```
The un-rescaled version of Adaptability (2.4) — same `num`/`den`/`kept` inputs, native 15-point scale.

### 3.6 Decision Discipline — 10 points
```javascript
const ranked = DF.map((d,i)=>i).sort((a,b) => mscore(DF[b][6]) - mscore(DF[a][6]));
const disc = Math.round(10 * (picks.filter(i => ranked.indexOf(i) < 10).length / 5));
```
Of the 5 actual cheques written, what fraction went to companies inside the model's own top-10 ranking.

### 3.7 Band
```javascript
const tot = depth + prov + tri + calib + revis + disc;
const band = tot>=81 ? 'Investigative' : tot>=61 ? 'Analytical' : tot>=36 ? 'Diligent' : 'Reflexive';
```

---

## Part 4 — Known limitations, stated plainly

**`T.minutes` does not measure triangulation.** It is incremented in the identical line as `T.prof`, unconditionally, every time a profile opens:
```javascript
function openWin(id) { ... T.prof++; T.minutes++; ... }
```
The UI copy for Triangulation claims to measure "cross-checked board minutes against founder narratives," but the underlying signal is mathematically a rescaled copy of "profiles opened." It cannot currently distinguish a student who read carefully from one who opened three tabs and read nothing. The same flaw leaks 5 of the 25 Provenance points (`T.minutes` contributes there too).

**Fixing this requires either:** (a) a genuine new interaction event — tracking expansion of the specific "Board minutes" or "Founder interview" accordion sections as separate telemetry from the general profile-open event, or (b) a classification pass on the student's free-text committee response, which is a larger architectural change since every other dimension in this engine is deterministic and auditable from UI events alone, with no ML in the scoring loop.

**Strategic Thinking, Long-Term Value Creation, and Revision Quality/Adaptability are correlated, not independent.** All four are derived from the same `W`/`lift`/`CAUSAL` inputs, asking different but related questions of the same underlying weight vector (final-state coherence, final-state durability, and change-over-time correctness, respectively). Defensible as three genuinely different questions, but worth knowing if these are ever displayed side-by-side as if fully orthogonal.

**`T.cgroup` fires automatically**, not behaviorally — every student who simply advances through the linear flow reaches the Evidence screen and earns this credit regardless of any search or investigation they performed.

---

## Part 5 — What the tech team should verify before this goes to a real cohort

1. Confirm `T.minutes` is either fixed to measure real cross-checking behavior, or the Triangulation dimension and the affected 5 Provenance points are relabeled/reweighted to reflect what's actually being measured.
2. Confirm the capital-allocation UI (`CHEQUE` object, sizing panel) enforces the ₹415 Cr total exactly before enabling deploy — a rounding error here would silently corrupt both `capital` and `risk` scores.
3. Re-run validation after any change to `parameters.py`/`generator.py` — every formula above depends on `lift()`, which depends entirely on the generated dataset staying calibrated the way it was validated.
