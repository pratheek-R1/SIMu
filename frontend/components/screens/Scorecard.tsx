"use client";

import { useEffect, useState } from "react";
import { api, type ScorecardData } from "@/lib/api";
import { useStore } from "@/lib/store";

const SIGNAL_LABELS: Record<string, string> = {
  missing_data: "named the missing data",
  comparison_group: "asked for a comparison group",
  quantified: "gave a number",
  falsifiable: "stated a falsifiable threshold",
};

export default function Scorecard() {
  const { go, sessionId } = useStore();
  const [card, setCard] = useState<ScorecardData | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api.get<ScorecardData>(`/sessions/${sessionId}/scorecard`).then(setCard).catch(() => {});
  }, [sessionId]);

  if (!card) return <p className="note">Scoring your run…</p>;

  return (
    <>
      <div className="eyebrow">Analyst review</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Scorecard</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        Measured from how you worked, not from what your fund returned.
      </p>

      <div className="card pad" style={{ marginBottom: 16, display: "flex", alignItems: "baseline", gap: 18, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 4 }}>Total</div>
          <div className="count" style={{ fontSize: 44 }}>
            {card.myelin.total}
            <span style={{ fontSize: 18, color: "var(--ink-4)" }}> / {card.myelin.max}</span>
          </div>
        </div>
        <div>
          <div className="eyebrow" style={{ marginBottom: 4 }}>Band</div>
          <div
            className="tag"
            style={{ background: "rgba(232,115,42,.1)", color: "var(--orange)", fontSize: 14, padding: "6px 14px" }}
          >
            {card.myelin.band}
          </div>
        </div>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        {card.myelin.dimensions.map((d) => (
          <div className="dim" key={d.key}>
            <div className="dim-head">
              <span className="dim-label">{d.label}</span>
              <span className="dim-score">{d.score} / {d.max}</span>
            </div>
            <div className={`bar${d.score >= d.max ? " full" : ""}`}>
              <div style={{ width: `${Math.min(100, (d.score / d.max) * 100)}%` }} />
            </div>
            <p className="note" style={{ lineHeight: 1.6 }}>{d.detail}</p>
          </div>
        ))}

        {card.myelin.not_applicable.map((d) => (
          <div className="dim" key={d.key} style={{ opacity: 0.62 }}>
            <div className="dim-head">
              <span className="dim-label">{d.label}</span>
              <span className="dim-score" style={{ color: "var(--ink-4)" }}>N/A</span>
            </div>
            <div className="bar" aria-hidden>
              <div style={{ width: 0 }} />
            </div>
            <p className="note" style={{ lineHeight: 1.6 }}>{d.detail}</p>
          </div>
        ))}

        <p className="note" style={{ lineHeight: 1.6, marginTop: 4 }}>
          Those two are not scored zero — they are not scored at all. Nothing you do in
          this simulation produces evidence about them, and a number invented to fill the
          gap would measure appearance rather than behaviour.
        </p>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 0 }}>Process detail</div>
          <span className="mono" style={{ fontSize: 12.5 }}>
            {card.total}
            <span style={{ color: "var(--ink-4)" }}> / {card.max} · {card.band}</span>
          </span>
        </div>
        <p className="note" style={{ lineHeight: 1.6, marginBottom: 14 }}>
          The finer-grained diagnostic this simulation scores itself on. Several of these
          feed the dimensions above — Adaptability is Revision Quality on a different
          scale, not a second opinion about it.
        </p>
        {card.dimensions.map((d) => (
          <div className="dim" key={d.key}>
            <div className="dim-head">
              <span className="dim-label">{d.label}</span>
              <span className="dim-score">{d.score} / {d.max}</span>
            </div>
            <div className={`bar${d.score >= d.max ? " full" : ""}`}>
              <div style={{ width: `${Math.min(100, (d.score / d.max) * 100)}%` }} />
            </div>
            <p className="note" style={{ lineHeight: 1.6 }}>{d.detail}</p>
          </div>
        ))}
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>How your written answers were read</div>
        {card.committee_analysis.aggregate_signals.length ? (
          <>
            <p style={{ fontSize: 13.5, marginBottom: 8 }}>
              Across your committee answers and your falsification statement, the review picked
              up that you:
            </p>
            <ul style={{ fontSize: 13.5, lineHeight: 1.8, paddingLeft: 20 }}>
              {card.committee_analysis.aggregate_signals.map((s) => (
                <li key={s}>{SIGNAL_LABELS[s] ?? s}</li>
              ))}
            </ul>
          </>
        ) : (
          <p style={{ fontSize: 13.5 }}>
            Your written answers did not name the missing data, ask for a comparison group,
            quantify a claim, or state a falsifiable threshold.
          </p>
        )}
        <p className="note" style={{ marginTop: 10, lineHeight: 1.6 }}>
          This check is a fixed set of patterns applied identically to every submission, so it
          is auditable and repeatable — and gameable by anyone who knows what it looks for.
          It is a floor on written reasoning, not a judgement of it.
        </p>
      </div>

      {card.fund && (
        <div className="card pad" style={{ marginBottom: 16, background: "rgba(27,42,74,.03)" }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Fund result — not scored</div>
          <p style={{ fontSize: 14 }}>
            {card.fund.hits} of {card.fund.cheques} investments succeeded.
          </p>
          <p className="note" style={{ marginTop: 8, lineHeight: 1.6 }}>{card.fund.note}</p>
        </div>
      )}

      <button className="pri" onClick={() => go("report")}>Generate investment report</button>
    </>
  );
}
