"""Printable investment report.

Self-contained HTML so it survives being downloaded, emailed or archived. The
closing analyst note states the share of total evidence the original thesis was
formed on, because that sentence is the whole simulation compressed into one
line.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from .sim import parameters as P


def money(usd: float, rate: float) -> str:
    """Three-tier Indian numbering, matching the client exactly."""
    r = usd * rate
    if r >= 1e7:
        crore = r / 1e7
        return f"Rs {round(crore)} Cr" if crore >= 100 else f"Rs {crore:.1f} Cr"
    if r >= 1e5:
        return f"Rs {r / 1e5:.1f} L"
    return f"Rs {round(r):,}"


def _rows(rows: list[list[str]]) -> str:
    return "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )


def render(
    *,
    user_name: str,
    session: Any,
    scorecard: dict[str, Any],
    debrief: dict[str, Any],
    rate: float,
) -> str:
    e = html.escape
    fund = session.fund_result or {}
    variables = session.thesis_variables or []
    confidence = session.thesis_confidence or {}

    thesis_rows = []
    for row in debrief.get("mirror", []):
        thesis_rows.append(
            [
                e(row["label"]),
                f"{confidence.get(row['feature'], '-')}%",
                f"{row['pct_winners']}%",
                f"{row['pct_failures_complete']}%",
                f"{row['true_lift']}x",
            ]
        )

    weight_rows = [
        [e(P.FEATURE_LABELS[k]), f"{v:+.1f}"]
        for k, v in sorted(
            (session.model_weights or {}).items(), key=lambda kv: -abs(kv[1])
        )
        if v
    ]

    portfolio_rows = [
        [
            e(r["name"]),
            e(r["sector"]),
            money(r["cheque_usd"], rate),
            f"{round(r.get('share_of_fund', 0) * 100)}%",
            e(r["outcome"]),
            money(r["returned_usd"], rate),
        ]
        for r in fund.get("rows", [])
    ]

    dim_rows = [
        [e(d["label"]), f"{d['score']} / {d['max']}", e(d["detail"])]
        for d in scorecard.get("dimensions", [])
    ]

    myelin = scorecard.get("myelin") or {}
    myelin_rows = [
        [e(d["label"]), f"{d['score']} / {d['max']}", e(d["detail"])]
        for d in myelin.get("dimensions", [])
    ]
    # N/A dimensions are printed, not omitted. A facilitator reading this file
    # needs to see that they were considered and deliberately not scored.
    myelin_rows += [
        [e(d["label"]), "N/A", e(d["detail"])] for d in myelin.get("not_applicable", [])
    ]

    portfolio_total = sum(r.get("cheque_usd", 0) for r in fund.get("rows", []))

    share = debrief.get("share_of_evidence_seen", 0)
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Investment report - {e(user_name)}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; color:#1B2A4A;
         background:#F8F6F0; max-width: 860px; margin: 0 auto; padding: 48px 32px; }}
  h1 {{ font-size: 26px; letter-spacing:-.02em; margin:0 0 4px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing:.1em;
        color:rgba(27,42,74,.45); margin: 34px 0 10px; font-family: Helvetica, Arial, sans-serif; }}
  .meta {{ color: rgba(27,42,74,.45); font-size: 13px; margin-bottom: 8px; }}
  table {{ width:100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }}
  th, td {{ text-align:left; padding: 7px 10px 7px 0; border-bottom:1px solid rgba(27,42,74,.09); }}
  th {{ font: 600 10px/1 Helvetica, Arial, sans-serif; text-transform: uppercase;
        letter-spacing:.07em; color: rgba(27,42,74,.4); }}
  .band {{ display:inline-block; padding: 4px 12px; border-radius: 4px;
           background: rgba(232,115,42,.1); color:#E8732A; font: 600 12px Helvetica, Arial, sans-serif; }}
  .total {{ font-size: 36px; font-weight: 700; letter-spacing:-.02em; }}
  blockquote {{ margin: 8px 0; padding: 12px 18px; border-left: 3px solid #E8732A;
                background: rgba(232,115,42,.05); font-size: 14px; line-height:1.6; }}
  .note {{ font-size: 12.5px; color: rgba(27,42,74,.5); line-height:1.65; }}
  @media print {{ body {{ background:#fff; padding: 0; }} }}
</style></head><body>

<h1>Fund IV - analyst file</h1>
<div class="meta">{e(user_name)} &middot; session {e(session.id[:8])} &middot; generated {generated}</div>

<h2>Executive summary</h2>
<p class="note">
  Fund IV deployed {money(fund.get('deployed_usd', 0), rate)} across
  {len(portfolio_rows)} portfolio companies against a thesis built on
  {len(variables)} variable{'s' if len(variables) != 1 else ''}. The fund returned
  {money(fund.get('returned_usd', 0), rate)} for a net of
  {money(fund.get('net_usd', 0), rate)} and a {fund.get('hits', 0)}/{fund.get('cheques', 0)}
  hit rate. Fund P&amp;L carries no weight in the assessment below.
</p>

<h2>Thesis, as submitted and as it turned out</h2>
<table><thead><tr><th>Variable</th><th>Stated confidence</th><th>In winners</th>
<th>In failures</th><th>True lift</th></tr></thead>
<tbody>{_rows(thesis_rows)}</tbody></table>

<h2>What would have changed your mind</h2>
<blockquote>{e(session.falsification or 'No statement recorded.')}</blockquote>

<h2>Scoring model</h2>
<table><thead><tr><th>Variable</th><th>Final weight</th></tr></thead>
<tbody>{_rows(weight_rows) or '<tr><td colspan="2">No weights set.</td></tr>'}</tbody></table>

<h2>Portfolio</h2>
<table><thead><tr><th>Company</th><th>Sector</th><th>Cheque</th><th>Share of fund</th>
<th>Outcome</th><th>Returned</th></tr></thead>
<tbody>{_rows(portfolio_rows)}</tbody></table>
<p class="note">Total deployed {money(portfolio_total, rate)} across
{len(portfolio_rows)} cheques, sized by the analyst.</p>

<h2>Standard scorecard</h2>
<div class="total">{myelin.get('total', 0)} <span style="font-size:16px;color:rgba(27,42,74,.4)">/ {myelin.get('max', 100)}</span></div>
<p><span class="band">{e(myelin.get('band', ''))}</span></p>
<table><thead><tr><th>Dimension</th><th>Score</th><th>Basis</th></tr></thead>
<tbody>{_rows(myelin_rows)}</tbody></table>
<p class="note">
  Two dimensions are marked N/A rather than scored. This simulation has no
  mechanic that produces evidence for them, and a number invented to fill the
  gap would measure appearance rather than behaviour.
</p>

<h2>Process detail</h2>
<div class="total">{scorecard.get('total', 0)} <span style="font-size:16px;color:rgba(27,42,74,.4)">/ {scorecard.get('max', 100)}</span></div>
<p><span class="band">{e(scorecard.get('band', ''))}</span></p>
<table><thead><tr><th>Dimension</th><th>Score</th><th>Basis</th></tr></thead>
<tbody>{_rows(dim_rows)}</tbody></table>

<h2>Closing note</h2>
<p class="note">
  The thesis above was formed on {share}% of the total evidence available. The
  remaining records existed the entire time; they were simply not in the file
  handed over on the first day. The recovered archive was itself incomplete --
  {debrief.get('withheld_count', 0)} further companies never filed dissolution
  paperwork and are absent from it, and their absence is not random.
</p>

</body></html>"""
