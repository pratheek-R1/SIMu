# The Survivors' Illusion

A teaching simulation about survivorship bias in venture capital.

You are a new analyst at Meridian Partners. The firm is raising Fund IV, the partners want an investment thesis before it closes, and Research has handed you the portfolio history: **500 companies the firm backed**. Your job is to work out what distinguishes a company worth backing.

The portfolio history is not a sample. It is 500 winners out of a population of 3,000, and the 2,500 failures are not in it. Every screen in the first half of the simulation is designed so that the obvious way to work — rank the traits that show up most often among the winners — produces a thesis built entirely out of noise. Then you lock that thesis, present it to five partners, and *afterwards* the missing records arrive.

The simulation does not score whether your fund made money. It scores how you reasoned.

---

## The trap, concretely

Sixteen binary traits are generated per company, in four classes. Students only ever see the labels, never the classes.

| Class | What it is | Traits | Realised lift* |
|---|---|---|---|
| **A** | Genuinely predictive | Founder 5+ yrs in domain, Expansion was customer-led, Usage-based pricing | 2.6× – 4.1× |
| **B** | Survivorship traps — *equally* common in winners and failures | Tier-one seed investor, Major startup hub, Pivoted at least once, Elite-school founder, Contrarian thesis, Head of growth pre-A, Second-time founder | ≈ 1.0× |
| **C** | Reverse traps — **more** common among failures | Major press in year one, Doubled headcount post-A, Series A above $20M, Multi-geography by year two | 0.60× – 0.72× |
| **D** | Pure noise | STEM undergraduate, One-word company name | ≈ 1.0× |

\* *at the default seed; every cohort seed produces its own realised lifts.*

The Class B traits are common among winners *because they are common everywhere*. Without the failures you cannot tell them apart from the Class A traits — and by raw frequency among winners, the traps rank higher.

Four continuous metrics (month-6 retention, CAC payback, net revenue retention, gross margin) are all genuinely predictive, and all invisible without a comparison group. They can only be read by cross-plotting two against each other.

**A validation gate enforces the trap on every seed.** A dataset is rejected unless at least **4 of the naive top 5** traits are Class B/C, and the first Class A trait ranks **11th or worse** by frequency among winners. The gate runs at boot, so a bad parameter change surfaces immediately rather than in front of a cohort.

### The second lesson

When "the archive" arrives it contains 2,000 failures, not 2,500. **20% never filed dissolution paperwork** — they were acqui-hired or wound down quietly — and their absence is *not random*: companies with tier-one investors, elite-school founders, major-hub addresses and year-one press are over-represented among the missing. A student who treats the recovered archive as complete repeats the original error one level up. The debrief is where that gets named.

So the thesis is formed on **16.7%** of the evidence, and revised on 83%.

---

## The run

Fourteen screens, gated server-side in order. The state machine lives in `backend/app/service.py`; the client cannot skip ahead, and backwards navigation is always allowed.

```
brief → dashboard → research → thesis → committee → deliberation
      → inbox → evidence → model → dealflow → results → debrief → scorecard → report
                    ▲
            the archive arrives here
```

- **Research** — 500 winners, filterable, with full company profiles, board minutes, founder interviews and a cross-plot.
- **Thesis** — pick up to **4 of 16** traits and state a confidence (10–99%) in each, plus what would disprove you. **This locks irreversibly.** Enforced on the server, because a student who can revise after seeing the archive has not taken the test.
- **Committee** — five partners, answered in order. The free text *is* read, by a fixed keyword rubric. Priya's provenance question lands last, after the other four have pushed you into committing.
- **Deliberation** — a short enforced wait. It stands in for the overnight gap between presenting a thesis and receiving contradicting evidence, so the reveal reads as a correction rather than as part of the same exercise.
- **Evidence** — your own claims against the combined record.
- **Model** — weight all 16 traits from −3 to +3. The pre-revision baseline is snapshotted the first time you open this screen; the delta is what Revision Quality measures. A backtest ranks a held-out 1,000-company pool by your weights.
- **Deal flow** — 40 live deals at a 20% base rate, ranked by *your* model. Pick 5 and size the cheques yourself out of one fixed pool.
- **Debrief** — the only place the A/B/C/D classification, the complete failure counts and the size of the archive withhold are ever disclosed.

---

## Scoring

Two independent scorecards out of 100, both computed from the same session. Nothing anywhere is awarded for free.

**Process detail** — what this simulation measures well:

| Dimension | Pts | Measures |
|---|---|---|
| Evidence Depth | 20 | Profiles read, comparisons built, charts studied, metric pairs cross-plotted. Every channel capped, so no single activity carries the dimension. |
| Provenance & Completeness | 25 | Did you ask where the data came from, chase a company that isn't in the set, and question the archive after the reveal — in writing and in behaviour. |
| Triangulation | 15 | Reading *both* accounts of the same company and correctly identifying planted contradictions. Opening profiles alone earns zero. |
| Calibration | 15 | Brier score of stated confidence against realised strength. Confident-and-wrong scores worse than honest-and-uncertain. |
| Revision Quality | 15 | Was weight movement after the reveal in the direction the evidence supports, and did the causal traits survive. |
| Decision Discipline | 10 | Did the cheques land inside your own model's top 10, or did you pick by feel. |

**Standard rubric** — Strategic Thinking (20), Capital Allocation (20), Risk Management (15), Adaptability (25), Long-Term Value Creation (20).

Two further rubric dimensions — Systems Thinking and Leadership — are reported **N/A rather than scored**. This simulation has no mechanic that produces evidence about them, and a number invented to fill the gap would measure appearance rather than behaviour.

Bands: Investigative ≥81, Analytical 61–80, Diligent 36–60, Reflexive <36.

### Fund P&L is worth zero, deliberately

The results screen shows what your five cheques returned. It carries **no weight**, and the debrief shows why: across 20,000 simulated funds, a strategy built on the genuinely causal traits still returns zero winners in roughly **one fund in 169**. Scoring that number would be scoring variance. The simulation is explicit about this rather than quietly ignoring it.

---

## Stack

**Backend** — FastAPI, SQLAlchemy 2 (async), Postgres with a SQLite fallback for local work, optional Redis. NumPy for dataset generation. JWT auth.

**Frontend** — Next.js 15 App Router, React 19, TypeScript. No UI framework and no chart library: all charts are hand-drawn on canvas, all styling is one stylesheet driven by CSS custom properties, with dark and light themes.

The client holds a token, a cached copy of server state, and whatever the student is currently typing. **It holds no simulation truth.** The dataset, the thesis lock, the telemetry and the score all live on the server, and no deal outcome is sent to the client until the fund is deployed.

```
backend/app/
  api/          route modules, one per stage
  sim/          dataset generation, parameters, validation gate, Monte Carlo
  scoring.py    the assessment engine — every formula lives here
  service.py    screen state machine and telemetry recording
frontend/
  app/          routes: landing, login, /terminal, /terminal/history
  components/   screens/ plus Chart, CompanyModal, ProfileMenu, RunPanel
  lib/          typed API client, store, formatters
docs/scoring-methodology.md   dimension-by-dimension derivation
```

### Determinism

A dataset is completely determined by its seed. `build_dataset(seed)` draws the outcome *first*, then every trait conditional on it, which is what makes the ground-truth relationship a property of the generator rather than something recovered afterwards. Randomness exists only at generation; scoring is a pure function of `(dataset, session, telemetry)`.

**Give every cohort its own seed** via `POST /api/v1/admin/cohorts`. Reuse one across semesters and the reveal is common knowledge before the second intake starts.

---

## Running it

No database, no Redis, no secrets. The API falls back to SQLite and an in-process cache.

**Backend** (Python 3.12):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On Python 3.14, install `requirements-py314.txt` instead — it also includes pytest, so it is a complete local environment on its own.

**Frontend**:

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Then open <http://localhost:3000>. API docs at <http://localhost:8000/docs>.

**Tests** — one full integration test drives two analysts (naive and investigative) through the entire flow against the real ASGI app, and asserts what the engine is supposed to distinguish:

```bash
cd backend
python -m pytest tests -q
```

It also asserts the *reverse* — that the investigative analyst outscores the naive one regardless of which fund made money.

---

## For facilitators

Endpoints under `/api/v1/admin` require a user with `role = "facilitator"`.

| Endpoint | What it gives you |
|---|---|
| `POST /admin/cohorts` | Create a cohort with its own seed. Rejects any seed that fails the validation gate. |
| `GET /admin/cohorts/{id}/results` | Every student's thesis, its **A/B/C/D composition**, dimension scores and band. |
| `GET /admin/sessions/{id}/audit` | The complete behavioural log. Every point on a scorecard traces to a row here. |
| `GET /admin/gate?seed=` | Run the validation gate against a candidate seed before adopting it. |

The cohort summary reports how many students built a thesis **entirely out of traps** — usually the single most useful number for the debrief conversation.

Students can review their own runs at `/terminal/history`: milestones in order, what they decided, how their model changed after the reveal, and what it scored.

---

## A note on the rubric

The committee free-text check is a fixed set of keyword and structure patterns, applied identically to every submission. It is therefore auditable, repeatable, and gameable by anyone who knows what it looks for. Every matched phrase is reported on the scorecard so a facilitator can see exactly why a point was awarded.

It is a floor on written reasoning, not a judgement of it. Read the answers.
