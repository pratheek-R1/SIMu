"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function Report() {
  const { sessionId, toast } = useStore();
  const [html, setHtml] = useState<string | null>(null);
  const [publicUrl, setPublicUrl] = useState<string | null>(null);
  const [stored, setStored] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api
      .post<{ html: string; public_url: string | null; stored: boolean }>(`/sessions/${sessionId}/report`)
      .then((r) => { setHtml(r.html); setPublicUrl(r.public_url); setStored(r.stored); })
      .catch(() => toast("Report failed", "Could not generate the report. Try again."));
  }, [sessionId, toast]);

  function download() {
    if (!html) return;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "meridian-investment-report.html";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Fund IV · analyst file</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Investment report</h2>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={download} disabled={!html}>Download</button>
          {publicUrl && (
            <a href={publicUrl} target="_blank" rel="noreferrer">
              <button>Open stored copy</button>
            </a>
          )}
        </div>
      </div>

      {stored ? (
        <p className="note" style={{ marginBottom: 12 }}>
          Saved to object storage and to your session record. Your facilitator can retrieve it.
        </p>
      ) : (
        <p className="note" style={{ marginBottom: 12 }}>
          Saved to your session record.
        </p>
      )}

      {html ? (
        <iframe
          title="Investment report"
          srcDoc={html}
          style={{
            width: "100%", height: "80vh", border: "1px solid rgba(27,42,74,.1)",
            borderRadius: 8, background: "#fff",
          }}
        />
      ) : (
        <p className="note">Generating…</p>
      )}
    </>
  );
}
