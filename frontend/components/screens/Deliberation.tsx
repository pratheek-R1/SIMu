"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

/** The wait.
 *
 *  Deliberately empty: no task, nothing to click. It substitutes for the
 *  overnight gap between presenting a thesis and receiving evidence against it,
 *  which is what makes the reveal land as a correction rather than as the next
 *  step of the same exercise. The countdown is authoritative on the server, so
 *  refreshing the page does not skip it. */
export default function Deliberation() {
  const { go, sessionId, config, state } = useStore();
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let alive = true;
    const tick = async () => {
      const r = await api.get<{ remaining_seconds: number; ready: boolean }>(
        `/sessions/${sessionId}/deliberation`,
      );
      if (alive) setRemaining(r.remaining_seconds);
    };
    void tick();
    const id = setInterval(tick, 1000);
    return () => { alive = false; clearInterval(id); };
  }, [sessionId]);

  const total = config?.deliberation_seconds ?? 15;
  const done = remaining !== null && remaining <= 0;
  const display = remaining === null ? "—" : done ? "Ready" : `0:${String(remaining).padStart(2, "0")}`;

  return (
    <div style={{ textAlign: "center", padding: "70px 0" }}>
      <div className="eyebrow">Closed session</div>
      <h2 className="stitle" style={{ fontSize: 22, marginBottom: 8 }}>
        The partners are deliberating
      </h2>
      <p style={{ color: "rgba(27,42,74,.4)", maxWidth: 400, margin: "0 auto 34px" }}>
        You&apos;ve been asked to wait outside.
      </p>

      <div className="count">{display}</div>

      <div style={{ maxWidth: 440, margin: "34px auto 0", textAlign: "left" }}>
        <p className="note">
          The committee is reviewing your responses on{" "}
          {(state?.thesis_variables ?? [])
            .map((v) => config?.variables.find((x) => x.key === v)?.label ?? v)
            .join(", ")}
          .
        </p>
      </div>

      <button className="pri" style={{ marginTop: 28 }} disabled={!done} onClick={() => go("inbox")}>
        Return to your desk
      </button>
      {!done && remaining !== null && (
        <p className="note" style={{ marginTop: 10 }}>{total}-second recess.</p>
      )}
    </div>
  );
}
