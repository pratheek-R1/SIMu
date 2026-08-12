"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CompanyModal from "@/components/CompanyModal";
import { COLORS, ScatterChart } from "@/components/Chart";
import { IconArrowRight, IconSearch } from "@/components/Icon";
import { api, qs, type CompanyRow } from "@/lib/api";
import { money, mult, pct } from "@/lib/format";
import { useStore } from "@/lib/store";

const SECTORS = ["SaaS", "Fintech", "D2C", "Healthtech", "Edtech"];
const CITIES = ["Mumbai", "Bangalore", "Delhi", "Hyderabad", "Chennai", "Pune"];

interface ScatterData {
  axes: { key: string; label: string; unit: string }[];
  winners: number[][];
  failures: number[][];
  failures_locked: boolean;
}

export default function Research() {
  const { go, sessionId, config, state, toast } = useStore();
  const [rows, setRows] = useState<CompanyRow[]>([]);
  const [stats, setStats] = useState<{ matching: number; share: number; median_retention: number | null; median_arr_usd: number | null } | null>(null);
  const [total, setTotal] = useState(0);
  const [features, setFeatures] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [searchNote, setSearchNote] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [scatter, setScatter] = useState<ScatterData | null>(null);
  const [xAxis, setXAxis] = useState(0);
  const [yAxis, setYAxis] = useState(1);
  // Pairs already reported this session. The server deduplicates at scoring
  // time too, so this only avoids pointless repeat POSTs while someone flicks
  // back and forth through the selects.
  const reportedPairs = useRef<Set<string>>(new Set());

  const load = useCallback(async () => {
    if (!sessionId) return;
    const r = await api.get<{ rows: CompanyRow[]; total: number; stats: typeof stats }>(
      `/sessions/${sessionId}/companies${qs({ feature: features, sector: sectors, city: cities, limit: 60 })}`,
    );
    setRows(r.rows);
    setTotal(r.total);
    setStats(r.stats);
  }, [sessionId, features, sectors, cities]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!sessionId) return;
    api.get<ScatterData>(`/sessions/${sessionId}/scatter`).then(setScatter).catch(() => {});
  }, [sessionId, state?.archive_unlocked]);

  /* Cross-plotting two continuous metrics is the only way to see the four
     variables that genuinely predict success, and it was invisible to the
     server -- so Evidence Depth could not credit it. Reported on change rather
     than on mount: the default pairing is not something the student chose. */
  const reportAxes = useCallback(
    (xi: number, yi: number) => {
      if (!sessionId || !scatter || xi === yi) return;
      const kx = scatter.axes[xi]?.key;
      const ky = scatter.axes[yi]?.key;
      if (!kx || !ky) return;
      const pair = [kx, ky].sort().join("|");
      if (reportedPairs.current.has(pair)) return;
      reportedPairs.current.add(pair);
      void api
        .post(`/sessions/${sessionId}/telemetry/metric`, { x: kx, y: ky })
        .catch(() => {
          // Let a failed report be retried rather than silently lost.
          reportedPairs.current.delete(pair);
        });
    },
    [sessionId, scatter],
  );

  const toggle = (list: string[], set: (v: string[]) => void, value: string) =>
    set(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);

  async function runSearch() {
    if (!sessionId || !query.trim()) return;
    const r = await api.post<{ matches: CompanyRow[]; total: number; notice: { title: string; message: string } | null }>(
      `/sessions/${sessionId}/search`, { query },
    );
    setRows(r.matches);
    setTotal(r.total);
    setSearchNote(
      r.total ? `${r.total} match${r.total === 1 ? "" : "es"} for “${query}”` : `No matches for “${query}”`,
    );
    if (r.notice) toast(r.notice.title, r.notice.message);
  }

  /* The "request a comparison group" control has been removed. It read as a
     button that would reveal withheld failure data, which is the opposite of
     what it did -- it asked Ops for a comparison group and was refused. The
     failure overlay still appears on its own once the archive arrives: the
     scatter refetches on `state.archive_unlocked` below. */

  const scatterSeries = useMemo(() => {
    if (!scatter) return [];
    const series = [
      {
        points: scatter.winners.map((p) => [p[xAxis], p[yAxis]] as [number, number]),
        color: COLORS.GREEN, alpha: 0.5, label: "Portfolio",
      },
    ];
    if (scatter.failures.length) {
      series.unshift({
        points: scatter.failures.map((p) => [p[xAxis], p[yAxis]] as [number, number]),
        color: COLORS.RED, alpha: 0.26, label: "Archive",
      });
    }
    return series;
  }, [scatter, xAxis, yAxis]);

  const axisRange = (idx: number): [number, number] => {
    if (!scatter) return [0, 1];
    const all = [...scatter.winners, ...scatter.failures].map((p) => p[idx]);
    if (!all.length) return [0, 1];
    const lo = Math.min(...all), hi = Math.max(...all);
    const pad = (hi - lo) * 0.06 || 1;
    return [lo - pad, hi + pad];
  };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Step one</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Portfolio history</h2>
        </div>
        <button className="pri" onClick={() => go("thesis")}>
          Draft thesis <IconArrowRight size={14} />
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1, position: "relative", display: "flex", alignItems: "center" }}>
          <IconSearch
            size={15}
            style={{ position: "absolute", left: 13, color: "var(--ink-4)", pointerEvents: "none" }}
          />
          <input
            type="search" value={query} placeholder="Search company, sector, city — or ask about the data…"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <button onClick={runSearch}>Search</button>
        {searchNote && (
          <button onClick={() => { setQuery(""); setSearchNote(null); void load(); }}>Clear</button>
        )}
      </div>
      {searchNote && <p className="note" style={{ marginBottom: 12 }}>{searchNote}</p>}

      <div style={{ marginBottom: 16 }}>
        <div className="filter-row">
          <div className="eyebrow">Variables</div>
          <div className="chips">
            {(config?.variables ?? []).map((v) => (
              <button
                key={v.key}
                className={`chip${features.includes(v.key) ? " on" : ""}`}
                onClick={() => toggle(features, setFeatures, v.key)}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-row">
          <div className="eyebrow">Sector</div>
          <div className="chips">
            {SECTORS.map((s) => (
              <button key={s} className={`chip${sectors.includes(s) ? " on" : ""}`} onClick={() => toggle(sectors, setSectors, s)}>{s}</button>
            ))}
          </div>
        </div>
        <div className="filter-row">
          <div className="eyebrow">HQ</div>
          <div className="chips">
            {CITIES.map((c) => (
              <button key={c} className={`chip${cities.includes(c) ? " on" : ""}`} onClick={() => toggle(cities, setCities, c)}>{c}</button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", marginBottom: 18 }}>
        <div className="stat"><div className="k">Matching</div><div className="v">{stats?.matching ?? "—"}</div></div>
        <div className="stat"><div className="k">Share</div><div className="v">{stats ? `${stats.share}%` : "—"}</div></div>
        <div className="stat"><div className="k">Median M6 ret.</div><div className="v">{stats?.median_retention != null ? `${stats.median_retention}%` : "—"}</div></div>
        <div className="stat"><div className="k">Median ARR</div><div className="v">{stats?.median_arr_usd != null ? money(stats.median_arr_usd) : "—"}</div></div>
      </div>

      <div className="card pad" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 10 }}>
          <div className="eyebrow" style={{ marginBottom: 0 }}>Cross-plot</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              value={xAxis}
              aria-label="Cross-plot X axis metric"
              onChange={(e) => {
                const v = Number(e.target.value);
                setXAxis(v);
                reportAxes(v, yAxis);
              }}
            >
              {scatter?.axes.map((a, i) => <option key={a.key} value={i}>{a.label}</option>)}
            </select>
            <span className="note">vs</span>
            <select
              value={yAxis}
              aria-label="Cross-plot Y axis metric"
              onChange={(e) => {
                const v = Number(e.target.value);
                setYAxis(v);
                reportAxes(xAxis, v);
              }}
            >
              {scatter?.axes.map((a, i) => <option key={a.key} value={i}>{a.label}</option>)}
            </select>
            {!scatter?.failures_locked && scatter?.failures.length ? (
              <span className="tag" style={{ background: "rgb(var(--neg-rgb) / 0.12)", color: "var(--neg)" }}>
                Archive overlay on
              </span>
            ) : null}
          </div>
        </div>
        {scatter && (
          <ScatterChart
            chartId="research.crossplot"
            series={scatterSeries}
            xLabel={scatter.axes[xAxis]?.label ?? ""}
            yLabel={scatter.axes[yAxis]?.label ?? ""}
            xRange={axisRange(xAxis)}
            yRange={axisRange(yAxis)}
            xUnit={scatter.axes[xAxis]?.unit ?? ""}
            yUnit={scatter.axes[yAxis]?.unit ?? ""}
            height={280}
            ariaLabel="Cross-plot of continuous metrics"
          />
        )}
        <p className="note" style={{ marginTop: 8 }}>
          {scatter?.failures_locked
            ? "Portfolio companies only — every company plotted here is one the firm backed. This dataset holds no failures to plot against them."
            : "Hover a point to read it. Click a series in the key to isolate it."}
        </p>
      </div>

      <div className="card">
        <div style={{ padding: "6px 22px 14px", overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Company</th><th>Sector</th><th>HQ</th>
                <th className="r">ARR</th><th className="r">M6 ret.</th>
                <th className="r">Head</th><th className="r">LTV/CAC</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => setOpenId(r.id)}>
                  <td><strong>{r.name}</strong></td>
                  <td>{r.sector}</td>
                  <td>{r.city}</td>
                  <td className="r mono">{money(r.arr_usd)}</td>
                  <td className="r mono">{pct(r.month6_retention)}</td>
                  <td className="r mono">{r.headcount}</td>
                  <td className="r mono">{mult(r.ltv_cac_ratio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note" style={{ paddingTop: 10 }}>
            {total > rows.length
              ? `Showing ${rows.length} of ${total} companies. Click a row for the full profile.`
              : rows.length === 0
                ? "No companies match these filters."
                : "Click a row for the full profile."}
          </p>
        </div>
      </div>

      {openId !== null && (
        <CompanyModal companyId={openId} onClose={() => setOpenId(null)} />
      )}
    </>
  );
}
