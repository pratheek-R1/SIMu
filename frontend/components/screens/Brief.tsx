"use client";

import { useStore } from "@/lib/store";

export default function Brief() {
  const { go, state } = useStore();
  const total = state?.summary.total_companies ?? 500;

  return (
    <div style={{ maxWidth: 620, padding: "32px 0" }}>
      <div className="eyebrow">Fund IV · analyst onboarding</div>
      <h1 className="stitle" style={{ fontSize: 28, marginBottom: 0 }}>
        You joined on Monday. The fund closes Friday.
      </h1>
      <p style={{ color: "rgba(27,42,74,.5)", marginTop: 14, lineHeight: 1.7 }}>
        Meridian is raising a ₹415 Cr seed fund and the partners want a thesis before it
        closes. Your job is to work out what actually distinguishes a company worth backing.
      </p>
      <p style={{ color: "rgba(27,42,74,.5)", marginTop: 8, lineHeight: 1.7 }}>
        Research has given you the firm&apos;s portfolio history — {total} companies. Read it
        however you like. When you&apos;re ready, you&apos;ll present to the investment committee
        and then deploy the fund.
      </p>

      <div
        className="card pad"
        style={{ margin: "24px 0", background: "rgba(232,115,42,.04)", borderLeft: "3px solid var(--orange)" }}
      >
        <div className="eyebrow" style={{ marginBottom: 8 }}>From Ana Behl, Managing Partner</div>
        <p style={{ fontSize: 14, lineHeight: 1.65, color: "rgba(27,42,74,.7)" }}>
          Don&apos;t bring me a list of things that sound clever. Bring me variables you can
          defend with evidence, and tell me how confident you are in each one.
        </p>
      </div>

      <button className="pri" onClick={() => go("dashboard")}>
        Open the terminal
      </button>
    </div>
  );
}
