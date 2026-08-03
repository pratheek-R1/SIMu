"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import WaveCanvas from "@/components/WaveCanvas";
import { ApiError } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function LoginPage() {
  const router = useRouter();
  const { user, ready, signIn, register } = useStore();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(false);

  useEffect(() => {
    if (ready && user) router.replace("/terminal");
  }, [ready, user, router]);

  const fail = (next: typeof errors) => {
    setErrors(next);
    setShake(true);
    setTimeout(() => setShake(false), 420);
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!email.includes("@")) next.email = "Please enter a valid email address";
    if (password.length < 8) next.password = "Password must be at least 8 characters";
    if (Object.keys(next).length) return fail(next);

    setErrors({});
    setBusy(true);
    try {
      if (mode === "signin") await signIn(email, password);
      else await register(email, password, name || email.split("@")[0]);
      router.push("/terminal");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      fail({ form: message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <WaveCanvas />
      <div className={`login-card${shake ? " login-shake" : ""}`}>
        <div className="login-brand">
          <div className="mark" />
          <span>Meridian Partners</span>
        </div>
        <h2>{mode === "signin" ? "Sign in" : "Create an account"}</h2>
        <p className="login-sub">
          {mode === "signin"
            ? "Enter your credentials to access the terminal"
            : "Your run is saved against this account, including your scorecard"}
        </p>

        {errors.form && <div className="login-error-msg">{errors.form}</div>}

        <form onSubmit={submit} noValidate>
          {mode === "signup" && (
            <div className="login-field">
              <label htmlFor="name">Name</label>
              <input
                id="name" type="text" value={name} autoComplete="name"
                onChange={(e) => setName(e.target.value)} placeholder="Your name"
              />
            </div>
          )}

          <div className={`login-field${errors.email ? " error" : ""}`}>
            <label htmlFor="email">Email</label>
            <input
              id="email" type="email" value={email} autoComplete="email"
              onChange={(e) => setEmail(e.target.value)}
              placeholder="analyst@meridianpartners.com"
            />
            {errors.email && <div className="field-error">{errors.email}</div>}
          </div>

          <div className={`login-field${errors.password ? " error" : ""}`}>
            <label htmlFor="password">Password</label>
            <input
              id="password" type="password" value={password}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
            {errors.password && <div className="field-error">{errors.password}</div>}
          </div>

          <button type="submit" className="login-btn" disabled={busy}>
            {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="login-footer">
          {mode === "signin" ? (
            <>
              Need an account?{" "}
              <a onClick={() => { setMode("signup"); setErrors({}); }}>Sign up</a>
            </>
          ) : (
            <>
              Already registered?{" "}
              <a onClick={() => { setMode("signin"); setErrors({}); }}>Sign in</a>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
