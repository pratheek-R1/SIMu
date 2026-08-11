"use client";

import { useEffect, useState } from "react";
import { BarChart, COLORS } from "@/components/Chart";
import { api, type FundResult } from "@/lib/api";
import { money } from "@/lib/format";
import { useStore } from "@/lib/store";

export default function Results() {
  const { go, sessionId } = useStore();
  const [fund, setFund] = useState<FundResult | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api.get<FundResult>(`/sessions/${sessionId}/results`).then(setFund).catch(() => {});
  }, [sessionId]);

  if (!fund) return <p className="note">Resolving the fund…</p>;

  return (
    <>
      <div className="eyebrow">Four quarters later</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Fund IV performance</h2>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 12, margin: "18px 0" }}>
        <div className="stat"><div className="k">Deployed</div><div className="v">{money(fund.deployed_usd)}</div></div>
        <div className="stat"><div className="k">Returned</div><div className="v">{money(fund.returned_usd)}</div></div>
        <div className="stat">
          <div className="k">Net</div>
          <div className="v" style={{ color: fund.net_usd >= 0 ? "var(--green)" : "var(--neg)" }}>
            {money(fund.net_usd)}
          </div>
        </div>
        <div className="stat"><div className="k">Hit rate</div><div className="v">{fund.hits}/{fund.cheques}</div></div>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Investment outcomes</div>
        <BarChart
          chartId="results.outcomes"
          bars={fund.rows.map((r) => ({
            label: r.name.slice(0, 10),
            value: Math.round(r.returned_usd / 1e6),
            color: r.outcome === "Success" ? COLORS.GREEN : COLORS.RED,
          }))}
          ariaLabel="Returned capital by investment"
        />
        <p className="note" style={{ marginTop: 8 }}>Returned capital, $M per cheque.</p>
      </div>

      <div className="card">
        <div style={{ padding: "6px 22px 16px", overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Company</th><th>Sector</th>
                <th className="r">Cheque</th><th className="r">Outcome</th><th className="r">Returned</th>
              </tr>
            </thead>
            <tbody>
              {fund.rows.map((r) => (
                <tr key={r.id}>
                  <td><strong>{r.name}</strong></td>
                  <td>{r.sector}</td>
                  <td className="r mono">{money(r.cheque_usd)}</td>
                  <td className="r mono" style={{ color: r.outcome === "Success" ? "var(--green)" : "var(--neg)" }}>
                    {r.outcome}
                  </td>
                  <td className="r mono">{money(r.returned_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {fund.missed_winners.length > 0 && (
        <div className="card pad" style={{ marginTop: 18 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>You passed on these. They worked.</div>
          <p style={{ fontSize: 13.5 }}>
            {fund.missed_winners.map((m) => `${m.name} (${m.sector})`).join(" · ")}
          </p>
        </div>
      )}

      <div className="card pad" style={{ marginTop: 18, background: "rgb(var(--accent-rgb) / 0.04)", borderLeft: "3px solid var(--orange)" }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>This number is not scored</div>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, color: "rgb(var(--ink-rgb) / 0.7)" }}>{fund.note}</p>
      </div>

      <button className="pri" style={{ marginTop: 20 }} onClick={() => go("debrief")}>
        See what happened
      </button>
    </>
  );
}
