"use client";

import { useStore } from "@/lib/store";

/** The progress rail.
 *
 *  One entry per screen, generated from the server's own screen list, so the
 *  rail and the router cannot disagree about how many steps there are. (The
 *  prototype's STEPS array had 12 entries against 14 screens, which is why the
 *  Scorecard step had no clean label.) */
export default function RunPanel({ open }: { open: boolean }) {
  const { state, go } = useStore();
  if (!state) return null;

  return (
    <aside className={`run-panel${open ? " open" : ""}`} aria-label="Session progress">
      <div className="eyebrow">Your run</div>
      {state.rail.map((step) => {
        const reachable = step.state !== "pending";
        return (
          <div
            key={step.key}
            className={`run-step${reachable ? " clickable" : ""}`}
            onClick={() => reachable && go(step.key)}
            role={reachable ? "button" : undefined}
            tabIndex={reachable ? 0 : undefined}
            onKeyDown={(e) => {
              if (reachable && (e.key === "Enter" || e.key === " ")) go(step.key);
            }}
          >
            <div className={`run-dot ${step.state}`} />
            <div
              className={`run-label${step.state === "current" ? " active" : step.state === "done" ? " done" : ""}`}
            >
              {step.label}
            </div>
          </div>
        );
      })}
    </aside>
  );
}
