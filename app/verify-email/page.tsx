"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BadgeCheck, BrainCircuit, LoaderCircle, Sparkles } from "lucide-react";
import "../auth.css";
import { ApiError, pathlyApi } from "../_lib/api";

function VerifyEmailStatus() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"checking" | "done" | "error">(token ? "checking" : "error");
  const [message, setMessage] = useState(token ? "" : "This verification link is missing its token.");

  useEffect(() => {
    if (!token) return;
    let active = true;
    pathlyApi.auth.confirmEmailVerification(token)
      .then((result) => {
        if (!active) return;
        setState("done");
        setMessage(result.message);
      })
      .catch((reason) => {
        if (!active) return;
        setState("error");
        setMessage(reason instanceof ApiError ? reason.message : "Could not connect to Pathly.");
      });
    return () => { active = false; };
  }, [token]);

  return (
    <form className="auth-card">
      <span>EMAIL VERIFICATION</span>
      <h2>{state === "checking" ? "Confirming your email…" : state === "done" ? "Email verified" : "Verification failed"}</h2>
      {state === "checking" && <LoaderCircle className="spin" />}
      {state === "done" && <p className="auth-note" role="status"><BadgeCheck /> {message}</p>}
      {state === "error" && <p className="auth-error" role="alert">{message}</p>}
      <Link className="auth-switch" href="/">Go to Pathly</Link>
    </form>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="auth-page">
      <section className="auth-brand">
        <span><BrainCircuit /></span>
        <b>pathly</b>
        <h1>Confirming your email.</h1>
        <p>One more step before your mastery journey begins.</p>
        <div><Sparkles /> Private and grounded in your files.</div>
      </section>
      <Suspense fallback={null}>
        <VerifyEmailStatus />
      </Suspense>
    </main>
  );
}
