"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { initials } from "@/lib/format";
import { useStore } from "@/lib/store";

interface Row {
  id: string; status: string; current_screen: string;
  total_score: number | null; band: string | null; hits: number | null; created_at: string;
}

export default function ProfileMenu() {
  const { user, state, signOut, refreshUser, startSession, loadSession, toast } = useStore();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(user?.name ?? "");
  const [rows, setRows] = useState<Row[]>([]);
  const [saved, setSaved] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => setName(user?.name ?? ""), [user?.name]);

  useEffect(() => {
    if (!open) return;
    api.get<Row[]>("/sessions").then(setRows).catch(() => setRows([]));
  }, [open]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (!user) return null;

  const save = async () => {
    await api.patch("/auth/me", { name });
    await refreshUser();
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const best = rows.reduce<number | null>(
    (acc, r) => (r.total_score != null && (acc == null || r.total_score > acc) ? r.total_score : acc),
    null,
  );

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="profile-trigger" onClick={() => setOpen((o) => !o)} role="button" tabIndex={0}>
        <div className="profile-avatar">{initials(user.name)}</div>
        <span className="profile-name">{user.name}</span>
      </div>

      {open && (
        <div className="profile-dropdown">
          <div className="pd-header">
            <div className="pd-avatar">{initials(user.name)}</div>
            <div className="pd-name">{user.name}</div>
            <div className="pd-email">{user.email}</div>
          </div>
          <div className="pd-body">
            <div className="pd-field">
              <label htmlFor="pd-name">Name</label>
              <input id="pd-name" type="text" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <button className="pri" style={{ width: "100%" }} onClick={save}>
              {saved ? "Saved" : "Save changes"}
            </button>

            <div className="pd-divider" />
            <div className="eyebrow" style={{ marginBottom: 8 }}>Analyst stats</div>
            <div className="pd-stats">
              <div className="pd-stat">
                <div className="sk">Sessions</div>
                <div className="sv">{rows.length}</div>
              </div>
              <div className="pd-stat">
                <div className="sk">Best score</div>
                <div className="sv">{best != null ? best : "—"}</div>
              </div>
              <div className="pd-stat">
                <div className="sk">Variables</div>
                <div className="sv">{state?.thesis_variables?.length ?? 0}</div>
              </div>
              <div className="pd-stat">
                <div className="sk">Cheques</div>
                <div className="sv">{state?.picks?.length ?? 0}</div>
              </div>
            </div>

            {rows.length > 0 && (
              <>
                <div className="eyebrow" style={{ marginBottom: 6 }}>Past sessions</div>
                <div style={{ marginBottom: 10 }}>
                  {rows.slice(0, 5).map((r) => (
                    <div
                      key={r.id}
                      className="pd-srow"
                      style={{ cursor: "pointer" }}
                      onClick={() => { void loadSession(r.id); setOpen(false); }}
                    >
                      <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
                        {new Date(r.created_at).toLocaleDateString()}
                      </span>
                      <span className="mono" style={{ fontSize: 11 }}>
                        {r.total_score != null ? `${r.total_score} · ${r.band}` : r.current_screen}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}

            <button
              style={{ width: "100%", background: "var(--orange)", color: "var(--on-accent)", borderColor: "var(--orange)" }}
              onClick={async () => {
                await startSession();
                setOpen(false);
                toast("New session", "Terminal cleared. A fresh run has started.");
              }}
            >
              New session
            </button>

            <div className="pd-divider" />
            <button className="danger" style={{ width: "100%" }} onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
