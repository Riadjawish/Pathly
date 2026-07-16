"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, BarChart3, BookOpen, Camera, Check, Folder,
  GraduationCap, LockKeyhole, Mail, MailWarning, Save, School, Target,
  UserPlus, UserRound, Users,
} from "lucide-react";
import { useSubjects } from "../_hooks/use-subjects";
import { ApiUser, pathlyApi, session } from "../_lib/api";
import { AppMobileNav, AppSidebar } from "../_components/app-sidebar";
import "../auth.css";

type ProgressSummary = {
  subjects_count: number;
  materials_count: number;
  quizzes_completed: number;
  average_quiz_score: number;
  completed_levels: number;
  subjects: Array<{ progress: number }>;
};

export default function AccountPage() {
  const [subjects] = useSubjects();
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [goal, setGoal] = useState("");
  const [university, setUniversity] = useState("");
  const [course, setCourse] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [inviteReady, setInviteReady] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const [resetBusy, setResetBusy] = useState(false);
  const [resetMessage, setResetMessage] = useState("");

  useEffect(() => {
    if (!session.getAccessToken()) return;
    let activeRequest = true;
    Promise.all([
      pathlyApi.users.me(),
      pathlyApi.progress.summary() as Promise<ProgressSummary>,
    ]).then(([user, summary]) => {
      if (!activeRequest) return;
      setProfile(user);
      setProgress(summary);
      setName(user.full_name);
      setEmail(user.email);
      setUniversity(user.university ?? "");
      setCourse(user.course ?? "");
      setGoal(user.study_goal ?? "");
    }).catch((requestError) => {
      if (activeRequest) setMessage(requestError instanceof Error ? requestError.message : "Could not load your account.");
    });
    return () => { activeRequest = false; };
  }, []);

  const averageProgress = progress?.subjects.length
    ? Math.round(progress.subjects.reduce((total, subject) => total + subject.progress, 0) / progress.subjects.length)
    : subjects.length
      ? Math.round(subjects.reduce((total, subject) => total + subject.progress, 0) / subjects.length)
      : 0;

  async function resendVerification() {
    setResendBusy(true);
    setResendMessage("");
    try {
      const result = await pathlyApi.auth.requestEmailVerification();
      setResendMessage(result.message);
    } catch (requestError) {
      setResendMessage(requestError instanceof Error ? requestError.message : "Could not send verification email.");
    } finally {
      setResendBusy(false);
    }
  }

  async function sendPasswordReset() {
    if (!profile) return;
    setResetBusy(true);
    setResetMessage("");
    try {
      await pathlyApi.auth.requestPasswordReset(profile.email);
      setResetMessage("Check your email for a link to set a new password.");
    } catch (requestError) {
      setResetMessage(requestError instanceof Error ? requestError.message : "Could not send reset email.");
    } finally {
      setResetBusy(false);
    }
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (!session.getAccessToken()) {
      setMessage("Sign in before saving your profile.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const updated = await pathlyApi.users.updateMe({
        full_name: name.trim(),
        university: university.trim() || null,
        course: course.trim() || null,
        study_goal: goal.trim() || null,
      });
      setProfile(updated);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1800);
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  return <main className="settings-page">
    <AppSidebar active="account" />
    <section className="settings-content">
      <header className="page-title"><Link href="/"><ArrowLeft /></Link><div><span>PERSONAL ACCOUNT</span><h1>Your Pathly profile</h1><p>Manage your identity, study goals and learning preferences.</p></div></header>
      {profile && !profile.email_verified && (
        <div className="auth-verify-banner">
          <span><MailWarning /> {resendMessage || "Verify your email to secure your account."}</span>
          <button type="button" disabled={resendBusy} onClick={resendVerification}>
            {resendBusy ? "Sending…" : "Resend verification"}
          </button>
        </div>
      )}
      <section className="profile-banner"><div className="profile-avatar"><span>👨🏻‍🎓</span><button disabled aria-label="Profile picture editing is not available yet" title="Profile picture editing is coming soon"><Camera /></button></div><div><span>STUDY PROFILE</span><h2>{profile?.full_name || "Your account"}</h2><p>{[course, university].filter(Boolean).join(" · ") || "Add your university and course"}</p><small>{progress?.subjects_count ?? subjects.length} subjects · {progress?.completed_levels ?? 0} levels completed · {averageProgress}% overall progress</small></div><div className="profile-level"><span><Target />{averageProgress}%<small>progress</small></span><span><Check />{progress?.completed_levels ?? 0}<small>complete</small></span></div>{!profile && <Link className="account-signin" href="/login">Sign in</Link>}</section>
      <div className="account-grid">
        <form className="account-card profile-form" onSubmit={saveProfile}><div className="account-card-title"><UserRound /><div><h2>Personal information</h2><p>How you appear throughout Pathly.</p></div></div><label>Full name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" required minLength={2} /></label><label>Email address<div className="input-icon"><Mail /><input type="email" value={email} readOnly placeholder="Saved with your account" /></div></label><div className="education-fields"><label>University<div className="input-icon"><School /><input value={university} onChange={(event) => setUniversity(event.target.value)} placeholder="Your university" /></div></label><label>Course / degree<div className="input-icon"><GraduationCap /><input value={course} onChange={(event) => setCourse(event.target.value)} placeholder="Your course" /></div></label></div><label>Primary study goal<textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="What do you want Pathly to help you achieve?" /></label><button type="submit" disabled={saving}>{saving ? "Saving…" : saved ? <><Check /> Saved</> : <><Save /> Save changes</>}</button>{message && <p className="backend-note" role="alert">{message}</p>}</form>
        <div className="account-side">
          <section className="account-card friends-card"><div className="account-card-title"><Users /><div><h2>Study friends</h2><p>Learn together and compare progress.</p></div></div><div className="friend-list"><div><span>👩🏽‍🎓</span><p><b>Maya</b><small>Calculus · studying today</small></p><i>Online</i></div><div><span>👨🏼‍💻</span><p><b>Leo</b><small>Physics · reviewing notes</small></p><i>Studying</i></div><div><span>👩🏻‍🔬</span><p><b>Sofia</b><small>Chemistry · quiz complete</small></p><i>Online</i></div></div><button className="invite-friend" onClick={() => setInviteReady(true)}>{inviteReady ? <><Check /> Invite ready</> : <><UserPlus /> Invite a friend</>}</button>{inviteReady && <p className="backend-note" role="status">Enter a friend&apos;s email from the friends screen when invitations are connected.</p>}</section>
          <section className="account-card account-security"><div className="account-card-title"><LockKeyhole /><div><h2>Security</h2><p>Password and account protection.</p></div></div><button type="button" onClick={sendPasswordReset} disabled={resetBusy || !profile}>{resetBusy ? "Sending…" : "Change password"} <small>{resetMessage || "Emails you a reset link"}</small></button><button disabled>Active sessions <small>Secure session management enabled</small></button></section>
        </div>
      </div>
      <section className="account-stats"><article><BookOpen /><b>{progress?.subjects_count ?? subjects.length}</b><span>Subjects</span></article><article><BarChart3 /><b>{averageProgress}%</b><span>Average progress</span></article><article><Check /><b>{progress?.completed_levels ?? 0}</b><span>Levels completed</span></article><article><Folder /><b>{progress?.materials_count ?? 0}</b><span>Materials</span></article></section>
    </section><AppMobileNav active="account" />
  </main>;
}
