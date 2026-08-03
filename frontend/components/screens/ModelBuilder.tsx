"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart, COLORS } from "@/components/Chart";
import { IconArrowRight } from "@/components/Icon";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

interface WeightVar { key: string; label: string; weight: number; baseline: number; in_thesis: boolean }
interface Backtest { top_n: number; success_rate: number; baseline_rate: number; sample_size: number; lift_vs_random: number }

export default function ModelBuilder() {
  const { go, sessionId, refreshState } = useStore();
  const [vars, setVars] = useState<WeightVar[]>([]);
  const [range, setRange] = useState({ min: -3, max: 3, step: 0.5 });
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<{ variables: WeightVar[]; range: typeof range }>(`/sessions/${sessionId}/model`)
      .then((r) => { setVars(r.variables); setRange(r.range); })
      .catch(() => {});
  }, [sessionId]);

  const runBacktest = useCallback(async () => {
    if (!sessionId) return;
    setBacktest(await api.get<Backtest>(`/sessions/${sessionId}/model/backtest`));
  }, [sessionId]);

  useEffect(() => { if (vars.length) void runBacktest(); }, [vars.length, runBacktest]);

  function setWeight(key: string, value: number) {
    setVars((vs) => vs.map((v) => (v.key === key ? { ...v, weight: value } : v)));
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!sessionId) return;
      await api.put(`/sessions/${sessionId}/model/weights`, { weights: { [key]: value } });
      await runBacktest();
      await refreshState();
    }, 260);
  }

  const changed = vars.filter((v) => v.weight !== v.baseline).length;

  return (
    <>
      <div className="eyebrow">Model builder</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Scoring model</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        Turn your thesis into weights. Your thesis variables start at +2; everything else at 0.
        Negative weights count against a company.
      </p>

      <div className="pcols" style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 14 }}>
        <div className="card pad">
          <div className="eyebrow" style={{ marginBottom: 10 }}>Variable weights</div>
          {vars.map((v) => (
            <div className="weight-row" key={v.key}>
              <span className={`wl${v.in_thesis ? " thesis" : ""}`}>{v.label}</span>
              <input
                type="range" min={range.min} max={range.max} step={range.step}
                value={v.weight} className="green-slider"
                style={{
                  "--fill": `${((v.weight - range.min) / (range.max - range.min)) * 100}%`,
                } as React.CSSProperties}
                onChange={(e) => setWeight(v.key, Number(e.target.value))}
                aria-label={`Weight for ${v.label}`}
              />
              <span className="wv">{v.weight > 0 ? `+${v.weight.toFixed(1)}` : v.weight.toFixed(1)}</span>
            </div>
          ))}
        </div>

        <div>
          <div className="card pad" style={{ marginBottom: 12 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Model accuracy</div>
            <BarChart
              chartId="model.accuracy"
              bars={[
                { label: "Your model", value: backtest?.success_rate ?? 0, color: COLORS.GREEN },
                { label: "Random", value: backtest?.baseline_rate ?? 20, color: COLORS.NAVY },
              ]}
              max={100}
              suffix="%"
              ariaLabel="Model accuracy against random picking"
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 12 }}>
              <div className="stat">
                <div className="k">Top {backtest?.top_n ?? 50} it picks</div>
                <div className="v">{backtest ? `${backtest.success_rate}%` : "—"}</div>
                <div className="note" style={{ marginTop: 3 }}>succeed</div>
              </div>
              <div className="stat">
                <div className="k">Picking at random</div>
                <div className="v">{backtest?.baseline_rate ?? 20}%</div>
                <div className="note" style={{ marginTop: 3 }}>succeed</div>
              </div>
            </div>
            {backtest && (
              <p className="note" style={{ marginTop: 10, lineHeight: 1.6 }}>
                Ranked against {backtest.sample_size.toLocaleString("en-IN")} held-out companies.
                That is {backtest.lift_vs_random.toFixed(2)}x the base rate.
              </p>
            )}
          </div>

          <div className="card pad">
            <div className="eyebrow" style={{ marginBottom: 6 }}>Revisions</div>
            <p style={{ fontSize: 13.5 }}>
              {changed === 0
                ? "You have not moved any weight away from your original thesis yet."
                : `You have moved ${changed} variable${changed === 1 ? "" : "s"} away from your original thesis.`}
            </p>
            <p className="note" style={{ marginTop: 8, lineHeight: 1.6 }}>
              Changing your mind is not penalised. Changing it in the right direction is
              rewarded.
            </p>
          </div>
        </div>
      </div>

      <button className="pri" style={{ marginTop: 16 }} onClick={() => go("dealflow")}>
        Apply model to deal flow <IconArrowRight size={14} />
      </button>
    </>
  );
}
