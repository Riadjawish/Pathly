"use client";

import { FormEvent, useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { BrainCircuit, LoaderCircle, LogIn, Sparkles } from "lucide-react";
import "../auth.css";
import { ApiError, pathlyApi } from "../_lib/api";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }): void;
          renderButton(parent: HTMLElement, options: Record<string, unknown>): void;
        };
      };
    };
  }
}

function GoogleSignInButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const buttonRef = useRef<HTMLDivElement>(null);

  const renderButton = useCallback(() => {
    if (!GOOGLE_CLIENT_ID || !window.google || !buttonRef.current) return;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (response) => onCredential(response.credential),
    });
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
      width: 354,
      text: "continue_with",
    });
  }, [onCredential]);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={renderButton} />
      <div className="auth-divider">or</div>
      <div ref={buttonRef} />
    </>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [registering, setRegistering] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (registering) await pathlyApi.auth.register({ email, password, full_name: name });
      else await pathlyApi.auth.login(email, password);
      router.replace("/");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not connect to Pathly.");
    } finally {
      setBusy(false);
    }
  }

  const handleGoogleCredential = useCallback(async (idToken: string) => {
    setBusy(true);
    setError("");
    try {
      await pathlyApi.auth.google(idToken);
      router.replace("/");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not sign in with Google.");
    } finally {
      setBusy(false);
    }
  }, [router]);

  return (
    <main className="auth-page">
      <section className="auth-brand">
        <span><BrainCircuit /></span>
        <b>pathly</b>
        <h1>Your course becomes a clear path.</h1>
        <p>Upload your material, let Gemini organize it, and track real mastery progress.</p>
        <div><Sparkles /> Private and grounded in your files.</div>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <span>{registering ? "CREATE YOUR ACCOUNT" : "WELCOME BACK"}</span>
        <h2>{registering ? "Start your study path" : "Continue learning"}</h2>
        {registering && (
          <label>
            Full name
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
        )}
        <label>
          Email
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {!registering && (
          <a className="auth-switch" style={{ marginTop: 8 }} href="/login/forgot">Forgot password?</a>
        )}
        {error && <p className="auth-error">{error}</p>}
        <button disabled={busy}>
          {busy ? <LoaderCircle className="spin" /> : <LogIn />}
          {registering ? "Create account" : "Sign in"}
        </button>
        <GoogleSignInButton onCredential={handleGoogleCredential} />
        <button className="auth-switch" type="button" onClick={() => setRegistering(!registering)}>
          {registering ? "Already have an account? Sign in" : "New to Pathly? Create an account"}
        </button>
      </form>
    </main>
  );
}
