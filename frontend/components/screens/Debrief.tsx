"use client";

import { useEffect, useState } from "react";
import { BarChart, COLORS } from "@/components/Chart";
import { api, type DebriefData } from "@/lib/api";
import { useStore } from "@/lib/store";

const CLASS_NAMES: Record<string, string> = {
  A: "Genuinely causal",
  B: "Survivorship trap — equally common in failures",
  C: "Reverse trap — more common in failures",
  D: "Noise — unrelated to outcome",
};

const CLASS_COLOR: Record<string, string> = {
  A: "var(--green)", B: "var(--orange)", C: "var(--neg)", D: "rgba(27,42,74,.4)",
};

export default function Debrief() {
  const { go, sessionId } = useStore();
  const [data, setData] = useState<DebriefData | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api.get<DebriefData>(`/sessions/${sessionId}/debrief`).then(setData).catch(() => {});
  }, [sessionId]);

  if (!data) return <p className="note">Assembling the debrief…</p>;

  return (
    <>
      <div className="eyebrow">Debrief</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>What you believed, and what was true</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        None of this is scored. It is the part that matters.
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ padding: "18px 22px 16px", overflowX: "auto" }}>
          <div className="eyebrow">Your thesis</div>
          <table>
            <thead>
              <tr>
                <th>Your variable</th><th className="r">You said</th>
                <th className="r">In winners</th><th className="r">In failures</th>
                <th className="r">True lift</th><th>What it actually was</th>
              </tr>
            </thead>
            <tbody>
              {data.mirror.map((r) => (
                <tr key={r.feature}>
                  <td><strong>{r.label}</strong></td>
                  <td className="r mono">{r.stated_confidence}%</td>
                  <td className="r mono">{r.pct_winners}%</td>
                  <td className="r mono">{r.pct_failures_complete}%</td>
                  <td className="r mono" style={{ color: CLASS_COLOR[r.class] }}>{r.true_lift}x</td>
                  <td style={{ color: CLASS_COLOR[r.class], fontSize: 12 }}>{CLASS_NAMES[r.class]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 9 }}>You said this would change your mind</div>
        <p style={{ fontSize: 15, lineHeight: 1.6, fontStyle: "italic" }}>
          &ldquo;{data.falsification || "No statement recorded."}&rdquo;
        </p>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>
          What ranking by frequency would have told you
        </div>
        <table>
          <thead>
            <tr>
              <th>#</th><th>Most common among winners</th>
              <th className="r">% of winners</th><th className="r">True lift</th><th>Class</th>
            </tr>
          </thead>
          <tbody>
            {data.naive_top5.map((r) => (
              <tr key={r.feature}>
                <td className="mono">{r.rank_by_frequency}</td>
                <td>{r.label}</td>
                <td className="r mono">{r.pct_winners}%</td>
                <td className="r mono">{r.true_lift}x</td>
                <td style={{ color: CLASS_COLOR[r.class], fontSize: 12 }}>{CLASS_NAMES[r.class]}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: 10, lineHeight: 1.6 }}>
          Every one of the five most common attributes among the winners was just as common
          among the companies that failed. They looked like a pattern because you could only
          see the winners.
        </p>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 12 }}>What actually separated them</div>
        <table>
          <thead>
            <tr>
              <th>Variable</th><th className="r">Lift</th>
              <th className="r">% of winners</th><th className="r">Rank by frequency</th>
            </tr>
          </thead>
          <tbody>
            {data.causal_variables.map((r) => (
              <tr key={r.feature}>
                <td><strong>{r.label}</strong></td>
                <td className="r mono" style={{ color: "var(--green)" }}>{r.true_lift}x</td>
                <td className="r mono">{r.pct_winners}%</td>
                <td className="r mono">{r.rank_by_frequency}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: 10, lineHeight: 1.6 }}>
          The real signals were deliberately uncommon. Ranking by frequency buries them —
          they only surface when you can compare winners against failures.
        </p>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>The metrics you could not read without a comparison group</div>
        <table>
          <thead>
            <tr>
              <th>Metric</th><th className="r">Median, winners</th>
              <th className="r">Median, failures</th><th className="r">Gap</th>
            </tr>
          </thead>
          <tbody>
            {data.continuous_truth.map((m) => {
              const scale = m.unit === "pct" ? 100 : 1;
              const suffix = m.unit === "pct" ? "%" : " mo";
              return (
                <tr key={m.key}>
                  <td><strong>{m.label}</strong></td>
                  <td className="r mono">{(m.win_median * scale).toFixed(1)}{suffix}</td>
                  <td className="r mono">{(m.fail_median * scale).toFixed(1)}{suffix}</td>
                  <td className="r mono" style={{ color: "var(--green)" }}>
                    {Math.abs((m.win_median - m.fail_median) * scale).toFixed(1)}{suffix}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>
          20,000 simulated funds of five picks
        </div>
        <BarChart
          chartId="debrief.fund_distribution"
          bars={data.fund_distribution.map((d) => ({
            label: d.strategy.includes("causal") ? "Causal" : d.strategy.includes("trap") ? "Traps" : "Random",
            value: d.mean_wins,
            color: d.strategy.includes("causal") ? COLORS.GREEN : d.strategy.includes("trap") ? COLORS.RED : COLORS.NAVY,
          }))}
          max={5}
          ariaLabel="Mean wins per fund by strategy"
        />
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Strategy</th><th className="r">Mean wins / 5</th>
              <th className="r">P(zero wins)</th><th className="r">P(3+ wins)</th>
            </tr>
          </thead>
          <tbody>
            {data.fund_distribution.map((d) => (
              <tr key={d.strategy}>
                <td>{d.strategy}</td>
                <td className="r mono">{d.mean_wins}</td>
                <td className="r mono">{d.p_zero_wins}%</td>
                <td className="r mono">{d.p_three_plus}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: 10, lineHeight: 1.6 }}>
          A strategy built on the trap variables performs worse than picking at random. And
          because five picks is a small number, even a sound strategy blanks sometimes — which
          is why your fund&apos;s P&amp;L carries no weight in your score.
        </p>
      </div>

      <div className="card pad" style={{ marginBottom: 16, background: "rgba(163,45,45,.04)", borderLeft: "3px solid var(--neg)" }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>One more thing about the archive</div>
        <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(27,42,74,.75)" }}>{data.withhold_note}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginTop: 14 }}>
          <div className="stat"><div className="k">Portfolio</div><div className="v">{data.portfolio_count}</div></div>
          <div className="stat"><div className="k">Archive you got</div><div className="v">{data.archive_visible.toLocaleString("en-IN")}</div></div>
          <div className="stat"><div className="k">Failures that existed</div><div className="v">{data.archive_complete.toLocaleString("en-IN")}</div></div>
          <div className="stat">
            <div className="k">Still missing</div>
            <div className="v" style={{ color: "var(--neg)" }}>{data.withheld_count}</div>
          </div>
        </div>
        <p className="note" style={{ marginTop: 12 }}>
          Your thesis was formed on {data.share_of_evidence_seen}% of the total evidence.
        </p>
      </div>

      <button className="pri" onClick={() => go("scorecard")}>See your analyst scorecard</button>
    </>
  );
}
