"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import ProfileMenu from "@/components/ProfileMenu";
import RunPanel from "@/components/RunPanel";

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { ready, user, state } = useStore();
  const [runOpen, setRunOpen] = useState(false);

  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);

  if (!ready || !user) {
    return (
      <div className="wrap" style={{ paddingTop: 80 }}>
        <p className="note">Loading terminal…</p>
      </div>
    );
  }

  return (
    <>
      <button className="run-toggle" onClick={() => setRunOpen((o) => !o)} aria-expanded={runOpen}>
        MY RUN
      </button>
      <RunPanel open={runOpen} />

      <header className="terminal-header">
        <div className="header-inner">
          <div className="brand">
            <div className="mark" />
            Meridian Partners
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {/* Segments rather than ●◆○: the dingbats came from whatever font
                the browser had for them, at three different optical weights. */}
            {state && (
              <div className="rail-mini" aria-hidden="true">
                {state.rail.map((r) => (
                  <i key={r.key} className={r.state} />
                ))}
              </div>
            )}
            <ProfileMenu />
          </div>
        </div>
      </header>

      <main className="wrap">{children}</main>
    </>
  );
}
