"use client";

import { useEffect, useState } from "react";
import { api, type Deal } from "@/lib/api";
import { money, mult, pct } from "@/lib/format";
import { useStore } from "@/lib/store";

export default function DealFlow() {
  const { go, sessionId, refreshState, toast } = useStore();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [picks, setPicks] = useState<number[]>([]);
  const [cheque, setCheque] = useState(10_000_000);
  const [maxPicks, setMaxPicks] = useState(5);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<{ deals: Deal[]; cheque_usd: number; cheques: number; picks: number[] }>(
        `/sessions/${sessionId}/dealflow`,
      )
      .then((r) => {
        setDeals(r.deals);
        setPicks(r.picks);
        setCheque(r.cheque_usd);
        setMaxPicks(r.cheques);
      })
      .catch(() => {});
  }, [sessionId]);

  async function toggle(id: number) {
    let next: number[];
    if (picks.includes(id)) next = picks.filter((p) => p !== id);
    else if (picks.length < maxPicks) next = [...picks, id];
    else { toast("Slots full", `You have selected ${maxPicks} companies.`); return; }
    setPicks(next);
    if (sessionId && next.length) await api.put(`/sessions/${sessionId}/picks`, { picks: next });
  }

  async function deploy() {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.post(`/sessions/${sessionId}/deploy`);
      await refreshState();
      await go("results");
    } finally {
      setBusy(false);
    }
  }

  // All 40 render. The prototype sliced indices 6..22 and left 18 companies
  // unreachable while the copy claimed "40 live deals".
  const top = deals.slice(0, 6);
  const rest = deals.slice(6);

  const card = (d: Deal) => (
    <div
      key={d.id}
      className={`dc${picks.includes(d.id) ? " pick" : ""}`}
      onClick={() => toggle(d.id)}
      role="button" tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && toggle(d.id)}
    >
      <div style={{ fontWeight: 600, fontFamily: "var(--font-heading), sans-serif", marginBottom: 4 }}>
        {d.name}
      </div>
      <div className="note mono" style={{ marginBottom: 8 }}>{d.sector} · {d.city}</div>
      <div className="mono" style={{ fontSize: 11 }}>
        ARR {money(d.arr_usd)} · Ret {pct(d.month6_retention)} · LTV/CAC {mult(d.ltv_cac_ratio)}
      </div>
      <div className="tag" style={{ background: "rgba(27,42,74,.05)", color: "rgba(27,42,74,.5)", marginTop: 8 }}>
        #{d.model_rank} · score {d.model_score.toFixed(1)}
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Step four</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Deal flow</h2>
          <p style={{ color: "var(--ink-3)", marginTop: 4 }}>
            {deals.length} live deals. {money(cheque)} per cheque, {maxPicks} cheques.
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>Slots filled</div>
          <div className="big">{picks.length}/{maxPicks}</div>
        </div>
      </div>

      <div className="eyebrow" style={{ marginBottom: 8 }}>Ranked highest by your model</div>
      <div className="shelf" style={{ marginBottom: 24 }}>{top.map(card)}</div>

      <div className="eyebrow" style={{ marginBottom: 8 }}>
        Everything else this week ({rest.length})
      </div>
      <div className="shelf">{rest.map(card)}</div>

      <div style={{ marginTop: 24 }}>
        <button className="pri" disabled={picks.length !== maxPicks || busy} onClick={deploy}>
          {busy ? "Deploying…" : `Deploy ${money(cheque * maxPicks)}`}
        </button>
        {picks.length !== maxPicks && (
          <span className="note" style={{ marginLeft: 12 }}>
            Select {maxPicks - picks.length} more.
          </span>
        )}
      </div>
    </>
  );
}
