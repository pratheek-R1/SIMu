"use client";

import { useEffect, useState } from "react";
import { BarChart, COLORS } from "@/components/Chart";
import { IconArrowRight } from "@/components/Icon";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

interface EvidenceRow {
  feature: string; label: string;
  supporting: number; supporting_pct: number;
  contradicting: number; contradicting_pct: number;
  visible_lift: number;
}

interface EvidenceData {
  rows: EvidenceRow[];
  portfolio_count: number; archive_count: number; combined_count: number;
  share_of_evidence_seen: number;
  thesis_confidence: Record<string, number>;
}

export default function Evidence() {
  const { go, sessionId } = useStore();
  const [data, setData] = useState<EvidenceData | null>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api.get<EvidenceData>(`/sessions/${sessionId}/evidence`).then(setData).catch(() => {});
  }, [sessionId]);

  // The contradicting column arrives on a beat after the supporting column, so
  // the student reads their own number first and then watches it be answered.
  useEffect(() => {
    if (!data) return;
    const id = setTimeout(() => setRevealed(true), 900);
    return () => clearTimeout(id);
  }, [data]);

  if (!data) return <p className="note">Loading the evidence board…</p>;

  return (
    <>
      <div className="eyebrow">Evidence board</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Your claims against the full record</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        Portfolio history and recovered archive, combined.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12, marginBottom: 16 }}>
        <div className="stat"><div className="k">Portfolio (backed)</div><div className="v">{data.portfolio_count}</div></div>
        <div className="stat"><div className="k">Archive (failed)</div><div className="v">{data.archive_count.toLocaleString("en-IN")}</div></div>
        <div className="stat"><div className="k">Combined record</div><div className="v">{data.combined_count.toLocaleString("en-IN")}</div></div>
        <div className="stat">
          <div className="k">You worked from</div>
          <div className="v" style={{ color: "var(--orange)" }}>{data.share_of_evidence_seen}%</div>
        </div>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Record size: what you had vs what existed</div>
        <BarChart
          chartId="evidence.win_rate"
          bars={[
            { label: "Portfolio", value: data.portfolio_count, color: COLORS.GREEN },
            { label: "Archive", value: data.archive_count, color: COLORS.RED },
          ]}
          ariaLabel="Portfolio versus archive record counts"
        />
      </div>

      <div className="card">
        <div style={{ padding: "6px 22px 16px", overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Your variable</th>
                <th className="r">Supporting</th>
                <th className="r">% of portfolio</th>
                {revealed && <th className="r">Contradicting</th>}
                {revealed && <th className="r">% of failures</th>}
                {revealed && <th className="r">Lift</th>}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.feature} className={revealed ? "reveal" : undefined}>
                  <td><strong>{r.label}</strong></td>
                  <td className="r mono">{r.supporting}</td>
                  <td className="r mono">{r.supporting_pct}%</td>
                  {revealed && <td className="r mono">{r.contradicting.toLocaleString("en-IN")}</td>}
                  {revealed && <td className="r mono">{r.contradicting_pct}%</td>}
                  {revealed && (
                    <td
                      className="r mono"
                      style={{ color: r.visible_lift >= 1.5 ? "var(--green)" : r.visible_lift <= 0.9 ? "var(--neg)" : "rgb(var(--ink-rgb) / 0.5)" }}
                    >
                      {r.visible_lift.toFixed(2)}x
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {revealed && (
            <p className="note reveal" style={{ paddingTop: 12, lineHeight: 1.6 }}>
              Lift is how much more often a variable appears in companies that succeeded than
              in companies that failed. A lift near 1.0 means the variable is just as common
              among failures — it was never distinguishing anything.
            </p>
          )}
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <button className="pri" onClick={() => go("model")}>
          Build scoring model <IconArrowRight size={14} />
        </button>
      </div>
    </>
  );
}
