"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";

import Brief from "@/components/screens/Brief";
import Dashboard from "@/components/screens/Dashboard";
import Research from "@/components/screens/Research";
import Thesis from "@/components/screens/Thesis";
import Committee from "@/components/screens/Committee";
import Deliberation from "@/components/screens/Deliberation";
import Inbox from "@/components/screens/Inbox";
import Evidence from "@/components/screens/Evidence";
import ModelBuilder from "@/components/screens/ModelBuilder";
import DealFlow from "@/components/screens/DealFlow";
import Results from "@/components/screens/Results";
import Debrief from "@/components/screens/Debrief";
import Scorecard from "@/components/screens/Scorecard";
import Report from "@/components/screens/Report";

const SCREENS = {
  brief: Brief,
  dashboard: Dashboard,
  research: Research,
  thesis: Thesis,
  committee: Committee,
  deliberation: Deliberation,
  inbox: Inbox,
  evidence: Evidence,
  model: ModelBuilder,
  dealflow: DealFlow,
  results: Results,
  debrief: Debrief,
  scorecard: Scorecard,
  report: Report,
} as const;

export default function Terminal() {
  const { state, sessionId, startSession, ready, user } = useStore();

  useEffect(() => {
    if (ready && user && !sessionId) void startSession();
  }, [ready, user, sessionId, startSession]);

  if (!state) {
    return <p className="note" style={{ paddingTop: 40 }}>Opening your session…</p>;
  }

  const Screen = SCREENS[state.current_screen] ?? Brief;
  return (
    <section className="fade" key={state.current_screen}>
      <Screen />
    </section>
  );
}
