"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function Report() {
  const { sessionId, toast } = useStore();
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setError(null);
    api
      .post<{ html: string; stored: boolean }>(`/sessions/${sessionId}/report`)
      .then((r) => {
        if (!cancelled) setHtml(r.html);
      })
      .catch((e) => {
        if (cancelled) return;
        // Surfaced in the page, not only as a toast that disappears after four
        // seconds and leaves a disabled button with no explanation.
        setError(e instanceof ApiError ? e.message : "Could not generate the report.");
        toast("Report failed", "Could not generate the report.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, toast, attempt]);

  function download() {
    if (!html) return;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "meridian-investment-report.html";
    // Firefox ignores a click on an anchor that is not in the document, and
    // revoking the blob URL in the same tick can outrun the browser starting to
    // read it. Attach, click, then clean up on the next macrotask.
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Fund IV · analyst file</div>
          <h2 className="stitle" style={{ fontSize: 22 }}>Investment report</h2>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {error && (
            <button onClick={() => setAttempt((a) => a + 1)}>Try again</button>
          )}
          <button onClick={download} disabled={!html}>Download</button>
        </div>
      </div>

      <p className="note" style={{ marginBottom: 12 }}>
        Saved to your session record. Your facilitator can retrieve it.
      </p>

      {error && (
        <div
          className="card pad"
          style={{ marginBottom: 12, borderLeft: "3px solid var(--neg)" }}
        >
          <div className="eyebrow" style={{ marginBottom: 6 }}>Report not generated</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.6 }}>{error}</p>
        </div>
      )}

      {html ? (
        <iframe
          title="Investment report"
          srcDoc={html}
          style={{
            // The report is a printable document and stays on its own light
            // ground regardless of the terminal's theme -- it is meant to
            // survive being downloaded, emailed and printed.
            width: "100%", height: "80vh", border: "1px solid rgb(var(--ink-rgb) / 0.1)",
            borderRadius: 8, background: "var(--report-paper)",
          }}
        />
      ) : (
        !error && <p className="note">Generating…</p>
      )}
    </>
  );
}
