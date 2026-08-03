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
    seenCharts.current.clear();
    setState(await api.get<SessionState>(`/sessions/${s.id}/state`));
    return s.id;
  }, []);

  const loadSession = useCallback(async (id: string) => {
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setState(await api.get<SessionState>(`/sessions/${id}/state`));
  }, []);

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
    }),
    [ready, user, config, state, toasts, toast, signIn, register, signOut,
     refreshUser, startSession, loadSession, refreshState, go, chartSeen, sessionId],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used inside StoreProvider");
  return ctx;
}
