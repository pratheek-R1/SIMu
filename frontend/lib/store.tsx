"use client";

/** Auth, config, session state and toasts.
 *
 * Deliberately thin. The client holds no simulation truth -- it holds a token,
 * a cached copy of server state, and whatever the student is currently typing.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api, getToken, setToken, type AppConfig, type ScreenKey, type SessionState, type User } from "./api";
import { setInrRate } from "./format";

interface Toast { id: number; title: string; message: string }

interface Store {
  ready: boolean;
  user: User | null;
  config: AppConfig | null;
  state: SessionState | null;
  toasts: Toast[];
  toast: (title: string, message: string) => void;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  signOut: () => void;
  refreshUser: () => Promise<void>;
  startSession: () => Promise<string>;
  loadSession: (id: string) => Promise<void>;
  refreshState: () => Promise<void>;
  go: (screen: ScreenKey) => Promise<void>;
  chartSeen: (chartId: string) => void;
  sessionId: string | null;
  /** True when the current session was opened deliberately from the history
   *  page, rather than restored from localStorage at boot. The terminal rolls a
   *  finished run onto a fresh one, and must not do that to a run the student
   *  just asked to reopen. */
  openedFromHistory: boolean;
}

const Ctx = createContext<Store | null>(null);
const SESSION_KEY = "meridian.session";

export function StoreProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [openedFromHistory, setOpenedFromHistory] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastSeq = useRef(0);
  // Charts already reported this session -- the server dedupes too, this just
  // avoids pointless requests on every re-render.
  const seenCharts = useRef<Set<string>>(new Set());

  const toast = useCallback((title: string, message: string) => {
    const id = ++toastSeq.current;
    setToasts((t) => [...t, { id, title, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api.get<User>("/auth/me", { silent: true }));
    } catch {
      setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.get<AppConfig>("/meta/config");
        setConfig(cfg);
        setInrRate(cfg.inr_rate);
      } catch {
        // Surfaced by the screens that need it rather than blocking boot.
      }
      if (getToken()) await refreshUser();
      const saved = typeof window !== "undefined" ? localStorage.getItem(SESSION_KEY) : null;
      if (saved) setSessionId(saved);
      setReady(true);
    })();
  }, [refreshUser]);

  const refreshState = useCallback(async () => {
    if (!sessionId) return;
    try {
      setState(await api.get<SessionState>(`/sessions/${sessionId}/state`));
    } catch {
      localStorage.removeItem(SESSION_KEY);
      setSessionId(null);
      setState(null);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId && user) void refreshState();
  }, [sessionId, user, refreshState]);

  // Whether the stale-session decision below has already been made this page
  // load. The provider lives in the root layout and does not remount on route
  // changes, so this survives navigating between the terminal and history.
  const staleChecked = useRef(false);

  const signIn = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ access_token: string }>("/auth/login", { email, password });
    setToken(r.access_token);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const r = await api.post<{ access_token: string }>("/auth/register", { email, password, name });
    setToken(r.access_token);
    await refreshUser();
  }, [refreshUser]);

  const signOut = useCallback(() => {
    setToken(null);
    localStorage.removeItem(SESSION_KEY);
    setUser(null);
    setState(null);
    setSessionId(null);
    seenCharts.current.clear();
    router.push("/");
  }, [router]);

  const startSession = useCallback(async () => {
    const s = await api.post<{ id: string }>("/sessions", {});
    localStorage.setItem(SESSION_KEY, s.id);
    setSessionId(s.id);
    setOpenedFromHistory(false);
    seenCharts.current.clear();
    setState(await api.get<SessionState>(`/sessions/${s.id}/state`));
    return s.id;
  }, []);

  const loadSession = useCallback(async (id: string) => {
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setOpenedFromHistory(true);
    seenCharts.current.clear();
    setState(await api.get<SessionState>(`/sessions/${id}/state`));
  }, []);

  /* A session id restored from localStorage can point at a run that is already
     finished, and resuming into it drops you onto an old scorecard with no
     obvious way to begin again. So a finished run gets replaced by a fresh one.
     The old run is not lost -- it is in Session history.
  
     This must happen on the FIRST state we see in a page load and never again.
     An earlier version of this lived in the terminal screen and re-evaluated on
     every state change, which meant it also fired at the natural end of a run:
     completing the scorecard flipped status to "complete", a new session was
     created while the student was reading their results, and the Report screen
     then POSTed /report against the empty session and got a 409, leaving the
     download button dead. Deciding once, here, is what keeps that from
     recurring. */
  useEffect(() => {
    if (!ready || !user || !state || staleChecked.current) return;
    staleChecked.current = true;
    if (state.status === "complete" && !openedFromHistory) void startSession();
  }, [ready, user, state, openedFromHistory, startSession]);

  const go = useCallback(
    async (screen: ScreenKey) => {
      if (!sessionId) return;
      await api.post(`/sessions/${sessionId}/screen`, { screen });
      await refreshState();
      if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [sessionId, refreshState],
  );

  const chartSeen = useCallback(
    (chartId: string) => {
      if (!sessionId || seenCharts.current.has(chartId)) return;
      seenCharts.current.add(chartId);
      void api.post(`/sessions/${sessionId}/telemetry/chart`, { chart_id: chartId }, { silent: true }).catch(() => {});
    },
    [sessionId],
  );

  const value = useMemo<Store>(
    () => ({
      ready, user, config, state, toasts, toast, signIn, register, signOut,
      refreshUser, startSession, loadSession, refreshState, go, chartSeen, sessionId,
      openedFromHistory,
    }),
    [ready, user, config, state, toasts, toast, signIn, register, signOut,
     refreshUser, startSession, loadSession, refreshState, go, chartSeen, sessionId,
     openedFromHistory],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used inside StoreProvider");
  return ctx;
}
