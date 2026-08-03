"use client";

import { useEffect, useState } from "react";
import { BarChart, COLORS, ScatterChart } from "@/components/Chart";
import { IconArrowRight } from "@/components/Icon";
import { api, qs, type CompanyRow } from "@/lib/api";
import { money, mult, pct } from "@/lib/format";
import { useStore } from "@/lib/store";

const SECTORS = ["SaaS", "Fintech", "D2C", "Healthtech", "Edtech"];

export default function Dashboard() {
  const { go, state, sessionId } = useStore();
  const [rows, setRows] = useState<CompanyRow[]>([]);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<{ rows: CompanyRow[] }>(`/sessions/${sessionId}/companies${qs({ limit: 200 })}`)
      .then((r) => setRows(r.rows))
      .catch(() => setRows([]));
  }, [sessionId]);

  const summary = state?.summary;

  const sectorBars = SECTORS.map((s) => ({
    label: s,
    value: rows.filter((r) => r.sector === s).length,
    color: COLORS.NAVY,
  }));

  const retentionBands = [
    { label: "<50", lo: 0, hi: 0.5 },
    { label: "50-65", lo: 0.5, hi: 0.65 },
    { label: "65-80", lo: 0.65, hi: 0.8 },
    { label: "80+", lo: 0.8, hi: 1.01 },
  ].map((b) => ({
    label: b.label,
    value: rows.filter((r) => r.month6_retention >= b.lo && r.month6_retention < b.hi).length,
    color: COLORS.ORANGE,
  }));

  const ltvBands = [
    { label: "<1.5", lo: 0, hi: 1.5 },
    { label: "1.5-3", lo: 1.5, hi: 3 },
    { label: "3-5", lo: 3, hi: 5 },
    { label: "5+", lo: 5, hi: Infinity },
  ].map((b) => ({
    label: b.label,
    value: rows.filter((r) => r.ltv_cac_ratio >= b.lo && r.ltv_cac_ratio < b.hi).length,
    color: COLORS.GREEN,
  }));

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Dashboard</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Portfolio overview</h2>
        </div>
        <button className="pri" onClick={() => go("research")}>
          Explore portfolio <IconArrowRight size={14} />
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12, marginBottom: 20 }}>
        <div className="stat"><div className="k">Total companies</div><div className="v">{summary?.total_companies ?? "—"}</div></div>
        <div className="stat"><div className="k">Median ARR</div><div className="v">{summary ? money(summary.median_arr_usd) : "—"}</div></div>
        <div className="stat"><div className="k">Median M6 ret.</div><div className="v">{summary ? pct(summary.median_retention) : "—"}</div></div>
        <div className="stat"><div className="k">Median LTV/CAC</div><div className="v">{summary ? mult(summary.median_ltv_cac) : "—"}</div></div>
      </div>

      <div className="pcols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div className="card pad">
          <div className="eyebrow" style={{ marginBottom: 8 }}>Sector distribution</div>
          <BarChart chartId="dashboard.sector" bars={sectorBars} ariaLabel="Companies by sector" />
        </div>
        <div className="card pad">
          <div className="eyebrow" style={{ marginBottom: 8 }}>Retention vs ARR</div>
          <ScatterChart
            chartId="dashboard.retention_arr"
            series={[{ points: rows.map((r) => [r.arr_usd / 1e6, r.month6_retention * 100] as [number, number]), color: COLORS.NAVY }]}
            xLabel="ARR ($M)"
            yLabel="M6 retention (%)"
            xRange={[0, 8]}
            yRange={[0, 100]}
            ariaLabel="Retention against ARR for the portfolio"
          />
        </div>
      </div>

      <div className="pcols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
        <div className="card pad">
          <div className="eyebrow" style={{ marginBottom: 8 }}>Companies by retention band</div>
          <BarChart chartId="dashboard.win_by_retention" bars={retentionBands} ariaLabel="Companies by retention band" />
        </div>
        <div className="card pad">
          <div className="eyebrow" style={{ marginBottom: 8 }}>LTV/CAC distribution</div>
          <BarChart chartId="dashboard.ltv_distribution" bars={ltvBands} ariaLabel="LTV to CAC distribution" />
        </div>
      </div>

      <p className="note" style={{ marginTop: 14 }}>
        Figures are computed across the {summary?.total_companies ?? 500} companies in the
        firm&apos;s portfolio history.
      </p>
    </>
  );
}
