"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { IconAlert } from "@/components/Icon";
import { useStore } from "@/lib/store";

interface Partner { index: number; name: string; title: string; question: string }

export default function Committee() {
  const { go, sessionId, refreshState } = useStore();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [current, setCurrent] = useState(0);
  const [answer, setAnswer] = useState("");
  const [warn, setWarn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<{ partners: Partner[]; answers: unknown[]; complete: boolean }>(`/sessions/${sessionId}/committee`)
      .then((r) => {
        setPartners(r.partners);
        setCurrent(r.answers.length);
      })
      .catch(() => {});
  }, [sessionId]);

  async function submit() {
    if (!answer.trim()) { setWarn(true); return; }
    if (!sessionId) return;
    setWarn(false);
    setBusy(true);
    try {
      const r = await api.post<{ answered: number; total: number; complete: boolean }>(
        `/sessions/${sessionId}/committee/answer`,
        { partner_index: current, answer },
      );
      setAnswer("");
      if (r.complete) {
        await api.post(`/sessions/${sessionId}/deliberation/start`);
        await refreshState();
        await go("deliberation");
      } else {
        setCurrent(r.answered);
      }
    } finally {
      setBusy(false);
    }
  }

  const partner = partners[current];
  const radius = 110, centre = 140;

  return (
    <>
      <div className="eyebrow">Step three</div>
      <h2 className="stitle" style={{ fontSize: 22 }}>Investment committee</h2>
      <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 20 }}>
        {partners.length} partners. Answer on the record.
      </p>

      <div className="committee-container">
        <div className="committee-circle">
          {partners.map((p, i) => {
            const angle = (i / partners.length) * 2 * Math.PI - Math.PI / 2;
            const x = centre + radius * Math.cos(angle) - 25;
            const y = centre + radius * Math.sin(angle) - 25;
            const cls = i === current ? "active" : i < current ? "done" : "";
            return (
              <div key={p.index} className={`cm-member ${cls}`} style={{ left: x, top: y }}>
                <div className="cm-init">{p.name.split(" ").map((w) => w[0]).join("")}</div>
                <div className="cm-name">{p.name.split(" ")[0]}</div>
              </div>
            );
          })}
        </div>

        {partner && (
          <div className="committee-qa">
            <div className="committee-question">
              <strong>{partner.name} ({partner.title}):</strong>
              <br />
              {partner.question}
            </div>
            <textarea
              rows={4} value={answer} placeholder="Type your answer…"
              onChange={(e) => setAnswer(e.target.value)}
            />
            <div className="committee-warning">
              {warn && (
                <>
                  <IconAlert size={13} />
                  Please provide an answer before proceeding.
                </>
              )}
            </div>
            <button className="pri" style={{ marginTop: 8 }} onClick={submit} disabled={busy}>
              {busy ? "Submitting…" : current === partners.length - 1 ? "Submit and withdraw" : "Submit response"}
            </button>
            <p className="note" style={{ marginTop: 12 }}>
              Partner {current + 1} of {partners.length}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
