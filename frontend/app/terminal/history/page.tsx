"use client";

/** Session history.
 *
 * A run is a sequence of decisions, and the only record of it used to be five
 * truncated rows in a dropdown. This is the same data given room: what was
 * decided, in what order, on what evidence, and what it scored.
 *
 * Deliberately outside the linear screen flow -- it is not a stage of the
 * simulation and must not pass through the state machine, so it is its own
 * route rather than an entry in SCREENS.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SessionHistory, type SessionSummaryRow } from "@/lib/api";
import { money } from "@/lib/format";
import { useStore } from "@/lib/store";
import { IconArrowRight, IconCheck, IconDash } from "@/components/Icon";

const STATUS_LABEL: Record<string, string> = {
  active: "In progress",
  complete: "Complete",
  abandoned: "Abandoned",
};

function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function duration(from: string, to: string | null): string {
  if (!to) return "—";
  const ms = new Date(to).getTime() - new Date(from).getTime();
  if (ms < 0) return "—";
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  if (mins < 60) return `${mins}m ${secs}s`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

export default function HistoryPage() {
  const router = useRouter();
  const { loadSession, startSession, sessionId, toast } = useStore();
  const [rows, setRows] = useState<SessionSummaryRow[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, SessionHistory>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  // Clearing is irreversible and takes the reports with it, so it is a
  // deliberate two-step rather than one click next to the run you were reading.
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setOpenId(null);
    setDetail({});
    try {
      setRows(await api.get<SessionSummaryRow[]>("/sessions"));
    } catch {
      setRows([]);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const clearAll = useCallback(async () => {
    if (!rows) return;
    setBusy(true);
    // The run currently open is work in progress, not history -- it is spared,
    // so clearing cannot leave the terminal pointing at a deleted session.
    const keep = sessionId && rows.some((r) => r.id === sessionId) ? sessionId : null;
    try {
      const res = await api.delete<{ deleted: number; kept: string | null }>(
        `/sessions${keep ? `?keep=${encodeURIComponent(keep)}` : ""}`,
      );
      toast(
        "History cleared",
        `${res.deleted} run${res.deleted === 1 ? "" : "s"} deleted.` +
          (res.kept ? " The run you have open was kept." : ""),
      );
      setConfirming(false);
      await reload();
    } catch {
      toast("Could not clear", "Nothing was deleted.");
    } finally {
      setBusy(false);
    }
  }, [rows, sessionId, toast, reload]);

  const removeOne = useCallback(
    async (id: string) => {
      setBusy(true);
      try {
        await api.delete(`/sessions/${id}`);
        // Deleting the open run would leave the terminal holding a dead id, so
        // a fresh one is started in its place.
        if (id === sessionId) await startSession();
        toast("Run deleted", "That run and its report are gone.");
        await reload();
      } catch {
        toast("Could not delete", "That run is still there.");
      } finally {
        setBusy(false);
      }
    },
    [sessionId, startSession, toast, reload],
  );

  const open = useCallback(
    async (id: string) => {
      if (openId === id) {
        setOpenId(null);
        return;
      }
      setOpenId(id);
      if (detail[id]) return;
      setLoadingId(id);
      try {
        const h = await api.get<SessionHistory>(`/sessions/${id}/history`);
        setDetail((d) => ({ ...d, [id]: h }));
      } catch {
        toast("Could not load", "That session's history is unavailable.");
        setOpenId(null);
      } finally {
        setLoadingId(null);
      }
    },
    [openId, detail, toast],
  );

  const resume = useCallback(
    async (id: string) => {
      await loadSession(id);
      router.push("/terminal");
    },
    [loadSession, router],
  );

  if (!rows) return <p className="note" style={{ paddingTop: 32 }}>Loading your history…</p>;

  const scored = rows.filter((r) => r.total_score != null);
  const best = scored.length ? Math.max(...scored.map((r) => r.total_score as number)) : null;

  return (
    <>
      <div className="hist-head">
        <div>
          <div className="eyebrow">Analyst record</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Session history</h2>
          <p className="note" style={{ marginTop: 6, maxWidth: 560 }}>
            Every run you have opened, what you decided in it, and what it scored. Click a
            run to expand the full record.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {rows.length > 0 && !confirming && (
            <button className="danger" onClick={() => setConfirming(true)}>
              Clear history
            </button>
          )}
          <button onClick={() => router.push("/terminal")}>
            Back to terminal <IconArrowRight size={13} />
          </button>
        </div>
      </div>

      {confirming && (
        <div
          className="card pad"
          style={{ marginBottom: 16, borderLeft: "3px solid var(--neg)" }}
        >
          <div className="eyebrow" style={{ marginBottom: 6 }}>Delete every run?</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.65, marginBottom: 12 }}>
            This removes {rows.filter((r) => r.id !== sessionId).length} run
            {rows.filter((r) => r.id !== sessionId).length === 1 ? "" : "s"} along with
            every scorecard, report and recorded action attached to them. Your facilitator
            will no longer be able to retrieve those reports. It cannot be undone.
            {sessionId && rows.some((r) => r.id === sessionId) && (
              <> The run you currently have open will be kept.</>
            )}
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="danger" onClick={() => void clearAll()} disabled={busy}>
              {busy ? "Deleting…" : "Yes, delete them"}
            </button>
            <button onClick={() => setConfirming(false)} disabled={busy}>Cancel</button>
          </div>
        </div>
      )}

      <div className="hist-stats">
        <div className="stat"><div className="k">Runs</div><div className="v">{rows.length}</div></div>
        <div className="stat"><div className="k">Completed</div><div className="v">{scored.length}</div></div>
        <div className="stat">
          <div className="k">Best score</div>
          <div className="v">{best != null ? best : "—"}</div>
        </div>
      </div>

      {rows.length === 0 && (
        <div className="card pad">
          <p className="note">
            No runs yet. Open the terminal and your first session will appear here.
          </p>
        </div>
      )}

      {rows.map((r) => {
        const isOpen = openId === r.id;
        const h = detail[r.id];
        return (
          <div key={r.id} className={`hist-run${isOpen ? " open" : ""}`}>
            <button
              className="hist-row"
              onClick={() => void open(r.id)}
              aria-expanded={isOpen}
            >
              <span className="hist-when mono">{when(r.created_at)}</span>
              <span className={`hist-badge ${r.status}`}>
                {STATUS_LABEL[r.status] ?? r.status}
              </span>
              <span className="hist-stage note">
                reached {r.furthest_label ?? r.current_screen}
              </span>
              <span className="hist-score mono">
                {r.total_score != null ? (
                  <>
                    {r.total_score}
                    <span style={{ color: "var(--ink-4)" }}> · {r.band}</span>
                  </>
                ) : (
                  <span style={{ color: "var(--ink-5)" }}>unscored</span>
                )}
              </span>
              <span className="hist-caret" aria-hidden>{isOpen ? "−" : "+"}</span>
            </button>

            {isOpen && (
              <div className="hist-body">
                {loadingId === r.id && <p className="note">Loading…</p>}
                {h && (
                  <>
                    <div className="hist-meta">
                      <div><span className="hk">Dataset</span><span className="hv mono">{h.dataset_fingerprint}</span></div>
                      <div><span className="hk">Seed</span><span className="hv mono">{h.seed}</span></div>
                      <div><span className="hk">Recorded actions</span><span className="hv mono">{h.event_count}</span></div>
                      <div>
                        <span className="hk">Elapsed</span>
                        <span className="hv mono">{duration(h.created_at, h.completed_at)}</span>
                      </div>
                    </div>

                    {h.score && (
                      <section className="hist-sec">
                        <div className="eyebrow">Result</div>
                        <div className="hist-scores">
                          <div>
                            <div className="big">{h.score.myelin_total}<span style={{ fontSize: 15, color: "var(--ink-4)" }}> / {h.score.myelin_max}</span></div>
                            <div className="note">Standard rubric · {h.score.myelin_band}</div>
                          </div>
                          <div>
                            <div className="big">{h.score.total}<span style={{ fontSize: 15, color: "var(--ink-4)" }}> / {h.score.max}</span></div>
                            <div className="note">Process detail · {h.score.band}</div>
                          </div>
                          {h.fund && (
                            <div>
                              <div className="big">{h.fund.hits}<span style={{ fontSize: 15, color: "var(--ink-4)" }}> / {h.fund.cheques}</span></div>
                              <div className="note">Investments that succeeded · not scored</div>
                            </div>
                          )}
                        </div>
                        <div className="hist-dims">
                          {h.score.myelin_dimensions.map((d) => (
                            <div key={d.key} className="hist-dim">
                              <span className="note">{d.label}</span>
                              <span className="mono">{d.score} / {d.max}</span>
                            </div>
                          ))}
                        </div>
                      </section>
                    )}

                    <section className="hist-sec">
                      <div className="eyebrow">What happened, in order</div>
                      <ol className="hist-timeline">
                        {h.milestones.map((m, i) => (
                          <li key={`${m.kind}-${i}`}>
                            <span className="tl-time mono">{clockTime(m.at)}</span>
                            <span className="tl-dot" aria-hidden />
                            <span className="tl-text">
                              <strong>{m.label}</strong>
                              {m.detail && <span className="note"> {m.detail}</span>}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </section>

                    {h.thesis && (
                      <section className="hist-sec">
                        <div className="eyebrow">Thesis you locked</div>
                        <div className="chips" style={{ marginBottom: 10 }}>
                          {h.thesis.variables.map((v) => (
                            <span key={v.key} className="tag" style={{ background: "rgb(var(--accent-rgb) / 0.1)", color: "var(--orange-deep)", fontSize: 11 }}>
                              {v.label} · {v.confidence}%
                            </span>
                          ))}
                        </div>
                        {h.thesis.falsification && (
                          <p className="note" style={{ lineHeight: 1.65 }}>
                            <span className="hk" style={{ display: "block", marginBottom: 4 }}>
                              What would have disproved it
                            </span>
                            {h.thesis.falsification}
                          </p>
                        )}
                      </section>
                    )}

                    {h.model && h.model.changes.length > 0 && (
                      <section className="hist-sec">
                        <div className="eyebrow">
                          Model {h.model.untouched ? "(left at its starting weights)" : "revisions"}
                        </div>
                        <table>
                          <thead>
                            <tr><th>Variable</th><th className="r">Start</th><th className="r">Final</th><th className="r">Moved</th></tr>
                          </thead>
                          <tbody>
                            {h.model.changes.map((c) => (
                              <tr key={c.key}>
                                <td>{c.label}</td>
                                <td className="r mono">{c.from}</td>
                                <td className="r mono">{c.to}</td>
                                <td className="r mono" style={{ color: c.moved === 0 ? "var(--ink-5)" : c.moved > 0 ? "var(--green)" : "var(--neg)" }}>
                                  {c.moved > 0 ? `+${c.moved}` : c.moved}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </section>
                    )}

                    {h.allocation && (
                      <section className="hist-sec">
                        <div className="eyebrow">Capital deployed</div>
                        <table>
                          <thead>
                            <tr><th>Company</th><th className="r">Cheque</th><th className="r">Outcome</th></tr>
                          </thead>
                          <tbody>
                            {h.allocation.positions.map((p) => (
                              <tr key={p.id}>
                                <td className="mono">#{p.id}</td>
                                <td className="r mono">{p.cheque_usd != null ? money(p.cheque_usd) : "—"}</td>
                                <td className="r" style={{ color: p.outcome === "Success" ? "var(--ok-text)" : p.outcome ? "var(--neg)" : "var(--ink-5)" }}>
                                  {p.outcome ?? "not yet deployed"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </section>
                    )}

                    <div className="hist-cols">
                      <section className="hist-sec">
                        <div className="eyebrow">Research activity</div>
                        {h.activity.map((a) => (
                          <div key={a.key} className="hist-dim">
                            <span className="note">{a.label}</span>
                            <span className="mono">{a.count}</span>
                          </div>
                        ))}
                      </section>
                      <section className="hist-sec">
                        <div className="eyebrow">Questions you asked of the data</div>
                        {h.provenance.map((p) => (
                          <div key={p.label} className="hist-check">
                            <span className={p.done ? "on" : "off"} aria-hidden>
                              {p.done ? <IconCheck size={13} /> : <IconDash size={13} />}
                            </span>
                            <span className="note">{p.label}</span>
                          </div>
                        ))}
                        {h.screens_visited.length > 0 && (
                          <p className="note" style={{ marginTop: 12, lineHeight: 1.6 }}>
                            <span className="hk" style={{ display: "block", marginBottom: 4 }}>
                              Where the work happened
                            </span>
                            {h.screens_visited.map((s) => `${s.label} (${s.events})`).join(" · ")}
                          </p>
                        )}
                      </section>
                    </div>

                    <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
                      {r.id === sessionId ? (
                        <button className="pri" onClick={() => router.push("/terminal")}>
                          Continue this run <IconArrowRight size={13} />
                        </button>
                      ) : (
                        <button className="pri" onClick={() => void resume(r.id)}>
                          {h.status === "complete" ? "Reopen this run" : "Resume this run"}
                          <IconArrowRight size={13} />
                        </button>
                      )}
                      <button
                        className="danger"
                        onClick={() => void removeOne(r.id)}
                        disabled={busy}
                        title="Delete this run, its scorecard and its report"
                      >
                        Delete this run
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
