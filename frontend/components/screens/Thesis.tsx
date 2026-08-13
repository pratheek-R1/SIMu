"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type VariableEvidence } from "@/lib/api";
import { IconArrowRight, IconLock } from "@/components/Icon";
import { useStore } from "@/lib/store";

export default function Thesis() {
  const { go, sessionId, config, state, refreshState, toast } = useStore();
  const [selected, setSelected] = useState<string[]>(state?.thesis_variables ?? []);
  const [confidence, setConfidence] = useState<Record<string, number>>(state?.thesis_confidence ?? {});
  const [falsification, setFalsification] = useState(state?.falsification ?? "");
  const [evidence, setEvidence] = useState<VariableEvidence | null>(null);
  const [busy, setBusy] = useState(false);

  const locked = state?.thesis_locked ?? false;
  const max = config?.max_thesis_variables ?? 4;
  const labelOf = (k: string) => config?.variables.find((v) => v.key === k)?.label ?? k;

  const loadEvidence = useCallback(async () => {
    if (!sessionId) return;
    setEvidence(await api.get<VariableEvidence>(`/sessions/${sessionId}/variables`));
  }, [sessionId]);

  useEffect(() => { void loadEvidence(); }, [loadEvidence, state?.archive_unlocked]);

  function toggle(key: string) {
    if (locked) return;
    if (selected.includes(key)) {
      setSelected(selected.filter((k) => k !== key));
    } else if (selected.length < max) {
      setSelected([...selected, key]);
      setConfidence((c) => ({ ...c, [key]: c[key] ?? 60 }));
    } else {
      toast("Limit reached", `Choose at most ${max} variables.`);
    }
  }

  /* The win-rate row used to carry a "Needs a comparison group" button that
     asked Ops for the failures and was refused. Clicking it could only ever
     produce the same rejection toast, so it read as a dead control. The row is
     still shown locked -- that absence is the point of the screen -- but it is
     now a static indicator rather than something to press. */

  async function lock() {
    if (!sessionId) return;
    if (!falsification.trim()) {
      toast("Field required", "State what evidence would change your mind.");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/sessions/${sessionId}/thesis`, {
        variables: selected,
        confidence: Object.fromEntries(selected.map((k) => [k, confidence[k] ?? 60])),
        falsification,
      });
      await refreshState();
      toast("Thesis locked", "Presenting to the investment committee.");
      await go("committee");
    } catch (err) {
      toast("Could not lock", err instanceof ApiError ? err.message : "Try again.");
    } finally {
      setBusy(false);
    }
  }

  const rowFor = (key: string) => evidence?.rows.find((r) => r.key === key);

  return (
    <>
      <div className="eyebrow">Step two</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Investment thesis</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        Choose up to {max} variables and state how confident you are in each.{" "}
        <strong>This locks permanently.</strong>
      </p>

      {locked && (
        <div className="card pad" style={{ marginBottom: 14, borderLeft: "3px solid var(--green)" }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Locked</div>
          <p style={{ fontSize: 13.5 }}>
            Your thesis is on the record and cannot be changed.
          </p>
          <button className="pri" style={{ marginTop: 12 }} onClick={() => go("committee")}>
            Present to the committee <IconArrowRight size={14} />
          </button>
        </div>
      )}

      <div className="card pad" style={{ marginBottom: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>Available variables</div>
        <div className="chips">
          {(config?.variables ?? []).map((v) => (
            <button
              key={v.key}
              className={`chip${selected.includes(v.key) ? " on" : ""}`}
              onClick={() => toggle(v.key)}
              disabled={locked}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card pad" style={{ marginBottom: 14 }}>
        {selected.length === 0 ? (
          <p className="note">
            Select variables above to see the evidence behind each one and set your confidence.
          </p>
        ) : (
          <>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              Evidence from the portfolio · set your confidence
            </div>
            {selected.map((key) => {
              const row = rowFor(key);
              const conf = confidence[key] ?? 60;
              return (
                <div className="thesis-var" key={key}>
                  <div className="thesis-var-header">
                    <span><strong>{labelOf(key)}</strong></span>
                    <span className="mono">{conf}% confident</span>
                  </div>
                  {/* --fill paints the track up to the handle, so the slider
                      reads as a quantity rather than a bare rail. */}
                  <input
                    type="range" min={10} max={99} step={1} value={conf} disabled={locked}
                    style={{ "--fill": `${((conf - 10) / 89) * 100}%` } as React.CSSProperties}
                    onChange={(e) => setConfidence({ ...confidence, [key]: Number(e.target.value) })}
                    aria-label={`Confidence in ${labelOf(key)}`}
                  />

                  {row && (
                    <div style={{ marginTop: 14 }}>
                      <div className="metric-row">
                        <span className="ml accent">Share of the portfolio with this trait</span>
                        <span className="mv">{row.pct_portfolio}%</span>
                      </div>
                      <div className="sharebar" style={{ height: 7, marginBottom: 12 }}>
                        <div style={{ width: `${row.pct_portfolio}%`, background: "var(--orange)" }} />
                      </div>

                      {row.win_rate_with == null ? (
                        <div className="lockbar">
                          <div className="metric-row">
                            <span className="ml">Success rate with this trait</span>
                            <span className="ml-locked mono">
                              <IconLock size={11} />
                              Not available
                            </span>
                          </div>
                          <div className="locked" />
                        </div>
                      ) : (
                        <>
                          <div className="metric-row">
                            <span className="ml" style={{ color: "var(--ink-1)" }}>Success rate with this trait</span>
                            <span className="mv">{row.win_rate_with}%</span>
                          </div>
                          <div className="sharebar" style={{ height: 7, marginBottom: 10 }}>
                            <div style={{ width: `${row.win_rate_with}%`, background: "var(--green)" }} />
                          </div>
                          <div className="metric-row">
                            <span className="ml">Success rate without it</span>
                            <span className="mv">{row.win_rate_without}%</span>
                          </div>
                          <div className="sharebar" style={{ height: 7 }}>
                            <div style={{ width: `${row.win_rate_without}%`, background: "rgb(var(--ink-rgb) / 0.32)" }} />
                          </div>
                        </>
                      )}

                      <p className="note" style={{ marginTop: 7 }}>
                        {row.count_portfolio} of {evidence?.portfolio_count} portfolio companies
                        ({row.pct_portfolio}%) have this trait.
                        {row.lift != null && ` Lift ${row.lift}x.`}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}

            {evidence && !evidence.archive_unlocked && (
              <p className="note" style={{ marginTop: 14, lineHeight: 1.6 }}>
                The portfolio history records companies the firm backed. Prevalence is
                therefore the only figure it can support on its own.
              </p>
            )}
          </>
        )}
      </div>

      <div className="card pad" style={{ margin: "14px 0" }}>
        <label className="eyebrow" style={{ display: "block", marginBottom: 9 }} htmlFor="falsify">
          What evidence would change your mind?
        </label>
        <textarea
          id="falsify" rows={3} value={falsification} disabled={locked}
          placeholder="Be specific. Name the observation that would make you drop a variable."
          onChange={(e) => setFalsification(e.target.value)}
        />
      </div>

      {!locked && (
        <>
          <button className="pri" disabled={selected.length === 0 || busy} onClick={lock}>
            {busy ? "Locking…" : "Lock thesis and present"}
          </button>
          <span className="note" style={{ marginLeft: 12 }}>
            {selected.length === 0 ? "Select at least one variable." : "This cannot be undone."}
          </span>
        </>
      )}
    </>
  );
}
