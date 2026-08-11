"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Deal } from "@/lib/api";
import { money, mult, pct } from "@/lib/format";
import { useStore } from "@/lib/store";

interface DealFlowResponse {
  deals: Deal[];
  cheque_usd: number;
  cheques: number;
  picks: number[];
  cheque_sizes: Record<string, number>;
  pool_usd: number;
  cheque_min_usd: number;
  cheque_max_usd: number;
  cheque_step_usd: number;
}

/** Spread the pool evenly, handing the remainder out one step at a time so the
 *  total is the pool exactly rather than the pool minus a rounding crumb. */
function splitEvenly(ids: number[], pool: number, step: number): Record<string, number> {
  if (!ids.length) return {};
  const units = Math.floor(pool / step);
  const base = Math.floor(units / ids.length);
  let leftover = units - base * ids.length;
  const next: Record<string, number> = {};
  for (const id of ids) {
    next[String(id)] = (base + (leftover > 0 ? 1 : 0)) * step;
    if (leftover > 0) leftover -= 1;
  }
  return next;
}

export default function DealFlow() {
  const { go, sessionId, refreshState, toast } = useStore();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [picks, setPicks] = useState<number[]>([]);
  const [sizes, setSizes] = useState<Record<string, number>>({});
  const [maxPicks, setMaxPicks] = useState(5);
  const [pool, setPool] = useState(50_000_000);
  const [minCheque, setMinCheque] = useState(2_000_000);
  const [maxCheque, setMaxCheque] = useState(30_000_000);
  const [step, setStep] = useState(1_000_000);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<DealFlowResponse>(`/sessions/${sessionId}/dealflow`)
      .then((r) => {
        setDeals(r.deals);
        setPicks(r.picks);
        setMaxPicks(r.cheques);
        setPool(r.pool_usd);
        setMinCheque(r.cheque_min_usd);
        setMaxCheque(r.cheque_max_usd);
        setStep(r.cheque_step_usd);

        // A session resumed with all five picks but no stored allocation --
        // picked in an earlier build, or via the API -- starts from an even
        // split rather than five zero cheques the student has to fix by hand.
        const stored = r.cheque_sizes ?? {};
        const complete =
          r.picks.length === r.cheques &&
          r.picks.every((id) => stored[String(id)] > 0);
        setSizes(
          complete
            ? stored
            : r.picks.length === r.cheques
              ? splitEvenly(r.picks, r.pool_usd, r.cheque_step_usd)
              : {},
        );
      })
      .catch(() => {});
  }, [sessionId]);

  const allocated = useMemo(
    () => picks.reduce((sum, id) => sum + (sizes[String(id)] ?? 0), 0),
    [picks, sizes],
  );
  const remaining = pool - allocated;
  const fullySized = picks.length === maxPicks && remaining === 0;

  const evenSplit = (ids: number[]) => splitEvenly(ids, pool, step);

  async function persist(nextPicks: number[], nextSizes: Record<string, number>) {
    setPicks(nextPicks);
    setSizes(nextSizes);
    if (!sessionId || !nextPicks.length) return;
    await api
      .put(`/sessions/${sessionId}/picks`, {
        picks: nextPicks,
        cheque_sizes: nextSizes,
      })
      .catch(() => {});
  }

  async function toggle(id: number) {
    let next: number[];
    if (picks.includes(id)) next = picks.filter((p) => p !== id);
    else if (picks.length < maxPicks) next = [...picks, id];
    else {
      toast("Slots full", `You have selected ${maxPicks} companies.`);
      return;
    }
    // Re-split evenly on every change to selection. The student then adjusts
    // from a valid allocation rather than from zero, so the deploy button is
    // never blocked by an arithmetic puzzle they did not ask for.
    await persist(next, next.length === maxPicks ? evenSplit(next) : {});
  }

  /** Move one cheque, taking the difference from the others so the pool holds. */
  async function resize(id: number, value: number) {
    const key = String(id);
    const clamped = Math.max(minCheque, Math.min(maxCheque, value));
    const next = { ...sizes, [key]: clamped };

    // Rebalance across the other picks one step at a time, cycling through
    // them, so the difference is shared rather than emptying the first cheque
    // in the list before touching the last. Bounded by each cheque's own limits.
    let drift = pool - Object.values(next).reduce((a, b) => a + b, 0);
    const others = picks.filter((p) => p !== id);
    const direction = drift > 0 ? step : -step;

    let guard = 0;
    while (drift !== 0 && others.length && guard < 1000) {
      let moved = false;
      for (const other of others) {
        if (drift === 0) break;
        const k = String(other);
        const current = next[k] ?? 0;
        const target = current + direction;
        if (target < minCheque || target > maxCheque) continue;
        next[k] = target;
        drift -= direction;
        moved = true;
      }
      // Every remaining cheque is pinned at a bound -- nothing further to give.
      if (!moved) break;
      guard += 1;
    }
    await persist(picks, next);
  }

  async function deploy() {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.post(`/sessions/${sessionId}/deploy`);
      await refreshState();
      await go("results");
    } catch (e) {
      toast("Could not deploy", e instanceof Error ? e.message : "Check your allocation.");
    } finally {
      setBusy(false);
    }
  }

  // All 40 render. The prototype sliced indices 6..22 and left 18 companies
  // unreachable while the copy claimed "40 live deals".
  const top = deals.slice(0, 6);
  const rest = deals.slice(6);
  const byId = useMemo(() => new Map(deals.map((d) => [d.id, d])), [deals]);

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
      <div className="tag" style={{ background: "rgb(var(--ink-rgb) / 0.06)", color: "var(--ink-3)", marginTop: 8 }}>
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
            {deals.length} live deals. {money(pool)} to deploy across {maxPicks} cheques —
            you decide how much goes behind each.
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>Slots filled</div>
          <div className="big">{picks.length}/{maxPicks}</div>
        </div>
      </div>

      {picks.length === maxPicks && (
        <div className="card pad" style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 0 }}>Size your cheques</div>
            <div className="mono" style={{ fontSize: 12, color: remaining === 0 ? "var(--ink-3)" : "var(--orange)" }}>
              {money(allocated)} of {money(pool)} allocated
              {remaining !== 0 && ` · ${money(Math.abs(remaining))} ${remaining > 0 ? "unallocated" : "over"}`}
            </div>
          </div>

          {picks.map((id) => {
            const d = byId.get(id);
            const amount = sizes[String(id)] ?? 0;
            const share = pool ? amount / pool : 0;
            return (
              <div key={id} style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5, gap: 10 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "var(--font-heading), sans-serif" }}>
                    {d?.name ?? `Deal ${id}`}
                    <span className="note" style={{ marginLeft: 8, fontWeight: 400 }}>
                      #{d?.model_rank} · score {d?.model_score.toFixed(1)}
                    </span>
                  </span>
                  <span className="mono" style={{ fontSize: 12.5 }}>
                    {money(amount)}
                    <span style={{ color: "var(--ink-4)" }}> · {pct(share)}</span>
                  </span>
                </div>
                <input
                  type="range"
                  min={minCheque}
                  max={maxCheque}
                  step={step}
                  value={amount}
                  onChange={(e) => resize(id, Number(e.target.value))}
                  style={{ width: "100%", accentColor: share > 0.3 ? "var(--orange)" : "var(--navy)" }}
                  aria-label={`Cheque size for ${d?.name ?? id}`}
                />
              </div>
            );
          })}

          <p className="note" style={{ lineHeight: 1.6, marginTop: 4 }}>
            Moving one cheque takes the difference from the others, so the fund always totals
            {" "}{money(pool)}. Any single position above 30% of the fund counts as concentration.
          </p>
        </div>
      )}

      <div className="eyebrow" style={{ marginBottom: 8 }}>Ranked highest by your model</div>
      <div className="shelf" style={{ marginBottom: 24 }}>{top.map(card)}</div>

      <div className="eyebrow" style={{ marginBottom: 8 }}>
        Everything else this week ({rest.length})
      </div>
      <div className="shelf">{rest.map(card)}</div>

      <div style={{ marginTop: 24 }}>
        <button className="pri" disabled={!fullySized || busy} onClick={deploy}>
          {busy ? "Deploying…" : `Deploy ${money(pool)}`}
        </button>
        {picks.length !== maxPicks && (
          <span className="note" style={{ marginLeft: 12 }}>
            Select {maxPicks - picks.length} more.
          </span>
        )}
        {picks.length === maxPicks && remaining !== 0 && (
          <span className="note" style={{ marginLeft: 12 }}>
            {money(Math.abs(remaining))} {remaining > 0 ? "still unallocated" : "over the pool"}.
          </span>
        )}
      </div>
    </>
  );
}
