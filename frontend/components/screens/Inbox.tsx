"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { IconPaperclip } from "@/components/Icon";
import { useStore } from "@/lib/store";

interface Mail {
  from: string; department: string; time: string; subject: string; body: string;
  attachment: { filename: string; records: number };
  unlocked: boolean;
}

export default function Inbox() {
  const { go, sessionId, refreshState } = useStore();
  const [mail, setMail] = useState<Mail | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api.get<Mail>(`/sessions/${sessionId}/inbox`).then(setMail).catch(() => {});
  }, [sessionId]);

  async function open() {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.post(`/sessions/${sessionId}/archive/unlock`);
      await refreshState();
      await go("evidence");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="eyebrow">Inbox · 1 new</div>
      <div className="mail" style={{ margin: "14px 0 22px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: "var(--ink-4)", marginBottom: 12 }}>
          <span>
            <strong style={{ color: "var(--ink-1)" }}>{mail?.from ?? "Devika Rao"}</strong> ·{" "}
            {mail?.department ?? "Operations"}
          </span>
          <span className="mono">{mail?.time ?? "09:12"}</span>
        </div>
        <div style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.02em", marginBottom: 10 }}>
          {mail?.subject ?? "Pre-2019 pipeline records"}
        </div>
        <p style={{ lineHeight: 1.7, color: "var(--ink-2)" }}>{mail?.body ?? ""}</p>
        {mail && (
          <p
            className="mono"
            style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 14, fontSize: 12, color: "var(--ink-4)" }}
          >
            <IconPaperclip size={13} />
            {mail.attachment.filename} · {mail.attachment.records.toLocaleString("en-IN")} records
          </p>
        )}
      </div>
      <button className="pri" onClick={open} disabled={busy}>
        {busy ? "Opening…" : "Open the archive"}
      </button>
    </>
  );
}
