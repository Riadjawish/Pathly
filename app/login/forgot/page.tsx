"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { BrainCircuit, LoaderCircle, Mail, Sparkles } from "lucide-react";
import "../../auth.css";
import { ApiDevEmail, ApiError, pathlyApi } from "../../_lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [devEmails, setDevEmails] = useState<ApiDevEmail[]>([]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await pathlyApi.auth.requestPasswordReset(email);
      setSent(true);
      setDevEmails(await pathlyApi.auth.devOutbox(email));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not connect to Pathly.");
    } finally {
      setBusy(false);
    }
  }

  const latestLink = devEmails.at(-1)?.body.match(/https?:\S+/)?.[0];

  return (
    <main className="auth-page">
      <section className="auth-brand">
        <span><BrainCircuit /></span>
        <b>pathly</b>
        <h1>Forgot your password?</h1>
        <p>Enter your account email and we&apos;ll send you a link to reset it.</p>
        <div><Sparkles /> Private and grounded in your files.</div>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <span>RESET YOUR PASSWORD</span>
        <h2>Reset password</h2>
        <label>
          Email
          <div className="input-icon">
            <Mail />
            <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </label>
        {error && <p className="auth-error">{error}</p>}
        {sent && (
          <p className="auth-note" role="status">
            If an account exists for that email, we&apos;ve sent reset instructions.
            {latestLink && (
              <>
                {" "}This is a development build without real email delivery — open your{" "}
                <a href={latestLink}>reset link</a> directly.
              </>
            )}
          </p>
        )}
        <button disabled={busy}>{busy ? <LoaderCircle className="spin" /> : "Send reset link"}</button>
        <Link className="auth-switch" href="/login">Back to sign in</Link>
      </form>
    </main>
  );
}
