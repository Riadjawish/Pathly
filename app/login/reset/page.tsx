"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { BrainCircuit, LoaderCircle, LockKeyhole, Sparkles } from "lucide-react";
import "../../auth.css";
import { ApiError, pathlyApi } from "../../_lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await pathlyApi.auth.confirmPasswordReset(token, password);
      setDone(true);
      window.setTimeout(() => router.replace("/login"), 1800);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not connect to Pathly.");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <form className="auth-card">
        <span>RESET YOUR PASSWORD</span>
        <h2>Link missing</h2>
        <p className="auth-error">This reset link is missing its token. Request a new one.</p>
        <Link className="auth-switch" href="/login/forgot">Request a new link</Link>
      </form>
    );
  }

  return (
    <form className="auth-card" onSubmit={submit}>
      <span>RESET YOUR PASSWORD</span>
      <h2>Choose a new password</h2>
      <label>
        New password
        <div className="input-icon">
          <LockKeyhole />
          <input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
      </label>
      {error && <p className="auth-error">{error}</p>}
      {done && <p className="auth-note" role="status">Password updated. Redirecting to sign in…</p>}
      <button disabled={busy || done}>{busy ? <LoaderCircle className="spin" /> : "Update password"}</button>
      <Link className="auth-switch" href="/login">Back to sign in</Link>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="auth-page">
      <section className="auth-brand">
        <span><BrainCircuit /></span>
        <b>pathly</b>
        <h1>Almost there.</h1>
        <p>Set a new password to get back into your study path.</p>
        <div><Sparkles /> Private and grounded in your files.</div>
      </section>
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </main>
  );
}
