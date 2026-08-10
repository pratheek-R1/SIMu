"""Full-session integration test.

Plays two students through the entire flow against the real API:

  * a NAIVE analyst, who does what the simulation is designed to seduce them
    into doing -- ranks variables by frequency among the winners, builds a
    thesis entirely out of traps, and never asks where the data came from;

  * an INVESTIGATIVE analyst, who asks about missing data, chases a competitor
    name that is not in the portfolio, reads both accounts of the same period,
    catches contradictions, and revises weights toward the truth after the
    reveal.

The test asserts what the assessment engine is supposed to distinguish, which
is not whether their funds made money -- it asserts the reverse of that too.

Run: python -m pytest tests -q   (or: python tests/test_playthrough.py)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_playthrough.db")
os.environ.setdefault("DELIBERATION_SECONDS", "0")

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.registry import get_dataset  # noqa: E402
from app.sim import parameters as P  # noqa: E402

API = settings.api_prefix
settings.deliberation_seconds = 0


class Client:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.token: str | None = None
        self.session_id: str | None = None

    @property
    def h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def call(self, method: str, path: str, **kw) -> httpx.Response:
        return await self.http.request(method, f"{API}{path}", headers=self.h, **kw)

    async def ok(self, method: str, path: str, **kw):
        r = await self.call(method, path, **kw)
        assert r.status_code < 400, f"{method} {path} -> {r.status_code}: {r.text[:400]}"
        return r.json()

    async def register(self, email: str, name: str):
        data = await self.ok(
            "POST", "/auth/register",
            json={"email": email, "password": "correct-horse-battery", "name": name},
        )
        self.token = data["access_token"]

    async def new_session(self):
        data = await self.ok("POST", "/sessions", json={})
        self.session_id = data["id"]
        return data

    async def screen(self, name: str):
        return await self.ok(
            "POST", f"/sessions/{self.session_id}/screen", json={"screen": name}
        )

    def s(self, path: str) -> str:
        return f"/sessions/{self.session_id}{path}"


async def naive_run(http: httpx.AsyncClient) -> dict:
    """Ranks by frequency, walks forward, asks nothing."""
    c = Client(http)
    await c.register("naive@meridianpartners.com", "Naive Analyst")
    await c.new_session()
    ds = get_dataset(settings.default_cohort_seed)

    await c.screen("dashboard")
    await c.screen("research")

    # Open a handful of profiles, read nothing on them.
    for cid in ds.winner_ids[:6]:
        await c.ok("GET", c.s(f"/companies/{cid}"))

    # The naive procedure: rank the visible variables by how common they are
    # among the winners and take the top four.
    rows = await c.ok("GET", c.s("/companies"), params={"limit": 1})
    assert rows["stats"]["matching"] == P.N_WINNERS

    ranking = ds.naive_ranking()
    top4 = [k for k, _, _ in ranking[:4]]

    await c.screen("thesis")
    await c.ok(
        "POST", c.s("/thesis"),
        json={
            "variables": top4,
            "confidence": {k: 80 for k in top4},
            "falsification": "If these variables stopped showing up in winners.",
        },
    )

    await c.screen("committee")
    committee = await c.ok("GET", c.s("/committee"))
    for p in committee["partners"]:
        await c.ok(
            "POST", c.s("/committee/answer"),
            json={"partner_index": p["index"], "answer": "It is the strongest one in the data."},
        )

    await c.screen("deliberation")
    await c.ok("POST", c.s("/deliberation/start"))
    await c.screen("inbox")
    await c.ok("POST", c.s("/archive/unlock"))
    await c.screen("evidence")
    await c.ok("GET", c.s("/evidence"))

    await c.screen("model")
    await c.ok("GET", c.s("/model"))  # captures w1, never revises

    await c.screen("dealflow")
    deals = await c.ok("GET", c.s("/dealflow"))
    picks = [d["id"] for d in deals["deals"][:5]]
    await c.ok("PUT", c.s("/picks"), json={"picks": picks})
    await c.ok("POST", c.s("/deploy"))

    await c.screen("results")
    await c.screen("debrief")
    await c.screen("scorecard")
    card = await c.ok("GET", c.s("/scorecard"))
    return {"client": c, "card": card, "thesis": top4}


async def investigative_run(http: httpx.AsyncClient) -> dict:
    """Asks where the data came from, triangulates, revises."""
    c = Client(http)
    await c.register("investigative@meridianpartners.com", "Investigative Analyst")
    await c.new_session()
    ds = get_dataset(settings.default_cohort_seed)

    await c.screen("dashboard")
    for chart in ("dashboard.sector", "dashboard.win_by_retention", "dashboard.ltv_distribution"):
        await c.ok("POST", c.s("/telemetry/chart"), json={"chart_id": chart})

    await c.screen("research")

    # Asks in plain language what is missing, before being told.
    notice = await c.ok("POST", c.s("/search"), json={"query": "where are the companies that failed"})
    assert notice["notice"] is not None

    # Asks for a comparison group while it is still locked.
    denied = await c.ok("POST", c.s("/request-comparison-group"))
    assert denied["granted"] is False

    # Reads profiles properly: both accounts, on the same companies.
    contradictions_found = 0
    cross_read = 0
    for cid in ds.winner_ids[:25]:
        profile = await c.ok("GET", c.s(f"/companies/{cid}"))
        await c.ok("GET", c.s(f"/companies/{cid}/board-minutes"))
        await c.ok("GET", c.s(f"/companies/{cid}/founder-interview"))
        cross_read += 1

        company = ds.by_id(cid)
        if company and company["contradicts_feature"] and contradictions_found < 4:
            flagged = await c.ok(
                "POST", c.s(f"/companies/{cid}/flag-contradiction"),
                json={"company_id": cid, "feature": company["contradicts_feature"]},
            )
            assert flagged["correct"] is True
            contradictions_found += 1

        # Chases a competitor named on the profile that is nowhere in the set.
        if profile["competitors"] and cross_read == 1:
            ghost = await c.ok("POST", c.s("/search"), json={"query": profile["competitors"][0]})
            assert ghost["notice"] is not None, "ghost query should be detected"

    await c.ok("POST", c.s("/compare"), json={"company_ids": ds.winner_ids[:3]})
    await c.ok("POST", c.s("/compare"), json={"company_ids": ds.winner_ids[3:6]})
    await c.ok("POST", c.s("/telemetry/chart"), json={"chart_id": "research.crossplot"})

    # Builds a thesis on the genuinely causal variables, with honest confidence.
    causal = list(P.CAUSAL_FEATURES)
    await c.screen("thesis")
    await c.ok(
        "POST", c.s("/thesis"),
        json={
            "variables": causal,
            "confidence": {causal[0]: 85, causal[1]: 80, causal[2]: 65},
            "falsification": (
                "If founder domain tenure showed up at the same rate below 40% in "
                "companies that failed, the variable is not doing any work."
            ),
        },
    )

    await c.screen("committee")
    committee = await c.ok("GET", c.s("/committee"))
    answers = [
        "Domain tenure, because it is the one that survives a comparison.",
        "Below 5 years of domain tenure I would pass; that is the threshold.",
        "The most likely way I am wrong is that I only ever saw companies we backed.",
        "I would hold them to a CAC payback under 18 months.",
        (
            "It came from our own portfolio history, which is only companies we "
            "funded. The failures and the ones we passed on are missing entirely, "
            "so I have no base rate and no comparison group."
        ),
    ]
    for p in committee["partners"]:
        await c.ok(
            "POST", c.s("/committee/answer"),
            json={"partner_index": p["index"], "answer": answers[p["index"]]},
        )

    await c.screen("deliberation")
    await c.ok("POST", c.s("/deliberation/start"))
    await c.screen("inbox")
    await c.ok("POST", c.s("/archive/unlock"))
    await c.screen("evidence")
    await c.ok("GET", c.s("/evidence"))
    await c.ok("POST", c.s("/telemetry/chart"), json={"chart_id": "evidence.win_rate"})

    # Questions whether the recovered archive is itself complete.
    await c.ok("POST", c.s("/search"), json={"query": "is the archive complete or is something missing"})

    await c.screen("model")
    await c.ok("GET", c.s("/model"))

    # Revises toward the truth: up on causal, down on the traps.
    weights = {k: 0.0 for k in P.FEATURE_KEYS}
    for k in P.CAUSAL_FEATURES:
        weights[k] = 3.0
    for k in P.FEATURE_KEYS:
        if P.feature_class(k) == "C":
            weights[k] = -2.0
    await c.ok("PUT", c.s("/model/weights"), json={"weights": weights})
    backtest = await c.ok("GET", c.s("/model/backtest"))

    await c.screen("dealflow")
    deals = await c.ok("GET", c.s("/dealflow"))
    picks = [d["id"] for d in deals["deals"][:5]]

    # Sizes the cheques in the same order the model ranks them -- the behaviour
    # Capital Allocation exists to detect. Totals the pool exactly.
    sizes = dict(zip((str(p) for p in picks), (16, 12, 10, 7, 5)))
    sizes = {k: v * 1_000_000 for k, v in sizes.items()}
    assert sum(sizes.values()) == P.FUND_POOL_USD

    # An allocation that does not total the pool must be refused at deploy.
    await c.ok("PUT", c.s("/picks"), json={"picks": picks})
    short = dict(sizes)
    short[str(picks[0])] -= 3_000_000
    r = await c.call("PUT", c.s("/picks"), json={"picks": picks, "cheque_sizes": short})
    assert r.status_code < 400, "a partial allocation should be storable while sizing"
    r = await c.call("POST", c.s("/deploy"))
    assert r.status_code == 400, "deploy accepted an allocation short of the pool"

    await c.ok("PUT", c.s("/picks"), json={"picks": picks, "cheque_sizes": sizes})
    await c.ok("POST", c.s("/deploy"))

    await c.screen("results")
    await c.screen("debrief")
    debrief = await c.ok("GET", c.s("/debrief"))
    await c.screen("scorecard")
    card = await c.ok("GET", c.s("/scorecard"))
    report = await c.ok("POST", c.s("/report"))

    return {
        "client": c,
        "card": card,
        "backtest": backtest,
        "debrief": debrief,
        "report": report,
    }


async def leakage_probes(http: httpx.AsyncClient) -> None:
    """The outcome must never reach the client before it is earned."""
    c = Client(http)
    await c.register("leak@meridianpartners.com", "Leak Probe")
    await c.new_session()
    ds = get_dataset(settings.default_cohort_seed)

    await c.screen("dashboard")
    await c.screen("research")

    # A winner profile carries no outcome field.
    profile = await c.ok("GET", c.s(f"/companies/{ds.winner_ids[0]}"))
    assert "outcome" not in profile, "profile leaked the outcome"
    assert "contradicts_feature" not in profile, "profile leaked the contradiction key"

    # A failure is a 404 before the archive is unlocked -- and the response must
    # not reveal that the id exists.
    r = await c.call("GET", c.s(f"/companies/{ds.visible_failure_ids[0]}"))
    assert r.status_code == 404, "archive record readable before the reveal"

    # A withheld failure is a 404 forever.
    r = await c.call("GET", c.s(f"/companies/{ds.withheld_ids[0]}"))
    assert r.status_code == 404, "withheld company was readable"

    # The thesis cannot be revised once locked.
    await c.screen("thesis")
    body = {
        "variables": ["majorHub"],
        "confidence": {"majorHub": 60},
        "falsification": "x",
    }
    await c.ok("POST", c.s("/thesis"), json=body)
    r = await c.call("POST", c.s("/thesis"), json=body)
    assert r.status_code == 409, "thesis was re-lockable"

    # Screens cannot be skipped.
    r = await c.call("POST", c.s("/screen"), json={"screen": "dealflow"})
    assert r.status_code == 409, "screen order was not enforced"

    print("  leakage probes: outcome hidden, archive gated, withhold hidden, "
          "thesis immutable, screen order enforced")


async def main() -> int:
    db_file = Path("./test_playthrough.db")
    if db_file.exists():
        db_file.unlink()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        # Trigger lifespan so the dataset builds and the gate runs.
        async with app.router.lifespan_context(app):
            print("\nLEAKAGE PROBES")
            print("-" * 74)
            await leakage_probes(http)

            print("\nNAIVE ANALYST")
            print("-" * 74)
            naive = await naive_run(http)
            n_card = naive["card"]
            n_classes = [P.feature_class(v) for v in naive["thesis"]]
            print(f"  thesis: {naive['thesis']}")
            print(f"  variable classes: {n_classes}")
            for d in n_card["dimensions"]:
                print(f"    {d['label']:<32}{d['score']:>6} / {d['max']}")
            print(f"  TOTAL {n_card['total']} / {n_card['max']}  ({n_card['band']})")
            print(f"  fund: {n_card['fund']['hits']}/5 hits")

            print("\nINVESTIGATIVE ANALYST")
            print("-" * 74)
            inv = await investigative_run(http)
            i_card = inv["card"]
            for d in i_card["dimensions"]:
                print(f"    {d['label']:<32}{d['score']:>6} / {d['max']}")
            print(f"  TOTAL {i_card['total']} / {i_card['max']}  ({i_card['band']})")
            print(f"  fund: {i_card['fund']['hits']}/5 hits")

            print("\n  MYELIN STANDARD SCORECARD")
            for label, card in (("naive", n_card), ("investigative", i_card)):
                m = card["myelin"]
                print(f"    -- {label} --")
                for d in m["dimensions"]:
                    print(f"      {d['label']:<30}{d['score']:>6} / {d['max']}")
                print(f"      {'TOTAL':<30}{m['total']:>6} / {m['max']}  ({m['band']})")
            for na in i_card["myelin"]["not_applicable"]:
                print(f"      {na['label']:<30}{'N/A':>6}")
            print(
                f"  model backtest: top-50 success {inv['backtest']['success_rate']}% "
                f"vs {inv['backtest']['baseline_rate']}% random"
            )
            print(f"  report generated: {len(inv['report']['html']):,} bytes")

            # ---- Assertions ------------------------------------------------
            assert all(c in ("B", "C") for c in n_classes), (
                "the naive procedure should produce a thesis made entirely of traps"
            )
            assert i_card["total"] > n_card["total"], (
                "the investigative analyst must outscore the naive one"
            )

            n_by = {d["key"]: d["score"] for d in n_card["dimensions"]}
            i_by = {d["key"]: d["score"] for d in i_card["dimensions"]}

            # Open Issue 2: opening profiles must no longer buy Triangulation.
            assert n_by["triangulation"] == 0, (
                f"naive analyst scored {n_by['triangulation']} on Triangulation "
                "despite never opening a second source"
            )
            assert i_by["triangulation"] > 10, "genuine triangulation was not credited"

            # Open Issue 3 + the free 10 points: walking forward earns nothing.
            assert n_by["provenance"] == 0, (
                f"naive analyst collected {n_by['provenance']} provenance points "
                "without asking a single question"
            )
            assert i_by["provenance"] >= 20, "provenance-seeking was under-credited"

            # Calibration must punish 80% confidence in variables with lift ~1.
            assert n_by["calibration"] < i_by["calibration"], (
                "confident-and-wrong should calibrate worse than honest-and-right"
            )

            assert inv["backtest"]["success_rate"] > inv["backtest"]["baseline_rate"], (
                "a model built on the causal variables should beat random"
            )

            # ---- Myelin standard scorecard ---------------------------------
            n_m, i_m = n_card["myelin"], i_card["myelin"]
            assert n_m["max"] == i_m["max"] == 100, "the standard rubric is out of 100"
            assert i_m["total"] > n_m["total"], (
                "the investigative analyst must outscore the naive one on the "
                "standard rubric too"
            )

            n_mby = {d["key"]: d["score"] for d in n_m["dimensions"]}
            i_mby = {d["key"]: d["score"] for d in i_m["dimensions"]}

            # A thesis made entirely of traps cannot be internally coherent, and
            # carries no durable signal.
            assert i_mby["strategic_thinking"] > n_mby["strategic_thinking"]
            assert i_mby["long_term_value"] > n_mby["long_term_value"]

            # Sizing in model order is what Capital Allocation measures; the
            # naive analyst never sized, so the even split scores neutral.
            assert i_mby["capital_allocation"] == 20.0, (
                f"perfectly monotonic sizing scored {i_mby['capital_allocation']}/20"
            )
            assert n_mby["capital_allocation"] == 10.0, (
                "an even split should score a neutral half, not zero"
            )

            # Adaptability must stay a pure rescale of Revision Quality.
            assert i_mby["adaptability"] == round(i_by["revision_quality"] * 25 / 15, 1)

            # Two dimensions have no mechanic here and must say so.
            na_keys = {d["key"] for d in i_m["not_applicable"]}
            assert na_keys == {"systems_thinking", "leadership"}
            assert all(d["score"] is None for d in i_m["not_applicable"]), (
                "an untestable dimension must be N/A, never a fabricated number"
            )

            # The fund settled at the student's own cheque sizes.
            i_fund = i_card["fund"]
            assert i_fund["deployed_usd"] == P.FUND_POOL_USD, (
                f"deployed {i_fund['deployed_usd']} against a pool of {P.FUND_POOL_USD}"
            )
            assert len({r["cheque_usd"] for r in i_fund["rows"]}) > 1, (
                "cheque sizes did not vary despite being sized individually"
            )

            # The reveal arithmetic.
            d = inv["debrief"]
            assert d["portfolio_count"] == P.N_WINNERS
            assert d["archive_complete"] == P.N_FAILURES
            assert d["withheld_count"] == int(P.N_FAILURES * P.ARCHIVE_WITHHOLD_RATE)
            print(
                f"\n  reveal: thesis formed on {d['share_of_evidence_seen']}% of the "
                f"evidence; {d['withheld_count']} failures still missing from the archive"
            )

    print("\n" + "=" * 74)
    print("ALL CHECKS PASSED")
    return 0


def test_full_playthrough() -> None:
    """Pytest entrypoint.

    The body of this suite is one long ordered session per analyst -- every step
    depends on the one before it, so it is a single test rather than a suite of
    independent ones. `main()` raises on the first failed assertion.
    """
    assert asyncio.run(main()) == 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
