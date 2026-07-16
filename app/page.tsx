"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSubjects } from "./_hooks/use-subjects";
import { AppMobileNav, AppSidebar } from "./_components/app-sidebar";
import { ApiError, ApiLearningPath, ApiUser, pathlyApi, session } from "./_lib/api";
import {
  ArrowRight, BookOpen, BrainCircuit, Check, ChevronLeft, ChevronRight,
  CircleHelp, Folder,
  Link2, LoaderCircle, LockKeyhole, Sparkles,
  Target, Upload,
} from "lucide-react";

type ProgressSummary = {
  subjects_count: number;
  materials_count: number;
  quizzes_completed: number;
  average_quiz_score: number;
  completed_levels: number;
  subjects: Array<{
    subject_id: string;
    progress: number;
    completed_levels: number;
    total_levels: number;
  }>;
};

export default function HomePage() {
  const [subjects, , subjectsLoading] = useSubjects();
  const [active, setActive] = useState(0);
  const [heroSlide, setHeroSlide] = useState(0);
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [path, setPath] = useState<ApiLearningPath | null>(null);
  const [pathLoading, setPathLoading] = useState(false);
  const [pathError, setPathError] = useState("");
  const selected = subjects[active] ?? subjects[0] ?? { id: "subject", name: "Your next subject", icon: "✨", tone: "purple", progress: 0, topics: 0, description: "" };
  const dashboardSubjects = subjects.slice(0, 5);
  const extraSubjects = Math.max(subjects.length - dashboardSubjects.length, 0);

  useEffect(() => {
    if (!session.getAccessToken()) return;
    let activeRequest = true;
    Promise.all([
      pathlyApi.users.me(),
      pathlyApi.progress.summary() as Promise<ProgressSummary>,
    ]).then(([user, progress]) => {
      if (!activeRequest) return;
      setProfile(user);
      setSummary(progress);
    }).catch(() => undefined);
    return () => { activeRequest = false; };
  }, []);

  useEffect(() => {
    if (selected.id === "subject" || !session.getAccessToken()) {
      return;
    }
    let activeRequest = true;
    const timer = window.setTimeout(() => {
      setPathLoading(true);
      setPathError("");
      pathlyApi.learning.getPath(selected.id).then((savedPath) => {
        if (activeRequest) setPath(savedPath);
      }).catch((requestError) => {
        if (!activeRequest) return;
        setPath(null);
        if (!(requestError instanceof ApiError && requestError.status === 404)) {
          setPathError(requestError instanceof Error ? requestError.message : "Could not load this path.");
        }
      }).finally(() => {
        if (activeRequest) setPathLoading(false);
      });
    }, 0);
    return () => { activeRequest = false; window.clearTimeout(timer); };
  }, [selected.id]);

  const visibleLevels = useMemo(
    () => [...(path?.levels ?? [])].sort((a, b) => a.order_index - b.order_index).slice(0, 6),
    [path],
  );
  const completedLevels = path?.levels.filter((level) => level.status === "complete").length ?? 0;
  const pathProgress = path?.levels.length ? Math.round((completedLevels / path.levels.length) * 100) : selected.progress;
  const activeProgress = summary?.subjects.find((item) => item.subject_id === selected.id);
  const overallProgress = summary?.subjects.length
    ? Math.round(summary.subjects.reduce((total, item) => total + item.progress, 0) / summary.subjects.length)
    : subjects.length
      ? Math.round(subjects.reduce((total, item) => total + item.progress, 0) / subjects.length)
      : 0;
  const currentChapter = visibleLevels.find((level) => level.status === "current")?.chapter ?? visibleLevels[0]?.chapter ?? "Your next chapter";
  const unlockedLevels = path?.levels.filter((level) => level.status !== "locked").length ?? 0;
  const firstName = profile?.full_name.trim().split(/\s+/)[0] || "learner";

  return (
    <main className="pathly-app">
      <AppSidebar active="home" />

      <section className="main-dashboard" id="dashboard">
        <header className="student-header">
          <div className="student"><span className="avatar">👨🏻‍🎓</span><div><h2>Hello, {firstName}</h2><p>{subjects.length ? "Ready to continue your journey?" : "Ready to build your first study path?"}</p></div></div>
          <div className="student-actions"><div className="streak-chip progress-chip"><Target /><b>{overallProgress}%</b><span>overall progress</span></div></div>
        </header>

        <section className="mastery-hero hero-carousel" aria-label="Pathly introduction">
          <div className="hero-track" style={{ transform: `translateX(-${heroSlide * 50}%)` }}>
            <article className="hero-slide intro-slide">
              <div className="hero-copy">
                <span className="micro-label">YOUR PERSONAL STUDY PATH</span>
                <h1>Master your next exam.</h1>
                <p>Upload your materials and let Pathly turn them into a focused, rewarding mastery journey.</p>
                <a href="#mastery-map">Continue learning <ArrowRight /></a>
              </div>
              <div className="hero-book" aria-hidden="true"><span>✦</span><div className="book-body"><i /><i /><b>⌣</b></div></div>
            </article>

            <article className="hero-slide workflow-slide">
              <div className="workflow-title"><span className="micro-label">HOW PATHLY WORKS</span><h2>Three steps to exam-ready</h2></div>
              <div className="hero-steps">
                <div><span>1</span><Upload /><h3>Upload materials</h3><p>Add PDFs, notes, slides, problems and past exams.</p><Link href="/subjects">Upload files <ArrowRight /></Link></div>
                <div><span>2</span><BrainCircuit /><h3>AI builds your plan</h3><p>Get summaries, explanations, practice questions and weak-topic insights.</p><b><Check /> Study plan ready</b></div>
                <div><span>3</span><Link2 /><h3>Follow your path</h3><p>Complete lessons and quizzes while Pathly tracks your progress.</p><a href="#mastery-map">Open your path <ArrowRight /></a></div>
              </div>
            </article>
          </div>
          <div className="carousel-controls">
            <button onClick={() => setHeroSlide((slide) => Math.max(0, slide - 1))} disabled={heroSlide === 0} aria-label="Previous slide"><ChevronLeft /></button>
            <div><button className={heroSlide === 0 ? "active" : ""} onClick={() => setHeroSlide(0)} aria-label="Show first slide" /><button className={heroSlide === 1 ? "active" : ""} onClick={() => setHeroSlide(1)} aria-label="Show second slide" /></div>
            <button onClick={() => setHeroSlide((slide) => Math.min(1, slide + 1))} disabled={heroSlide === 1} aria-label="Next slide"><ChevronRight /></button>
          </div>
        </section>

        <section className="subjects-block">
          <div className="block-heading"><div><span className="micro-label dark">YOUR COURSES</span><h2>My subjects</h2></div><Link className="see-all-subjects" href="/subjects"><span>See all{extraSubjects > 0 && <small>+{extraSubjects} more</small>}</span><ArrowRight /></Link></div>
          <div className="subjects-scroll">
            {!subjectsLoading && dashboardSubjects.length === 0 && <Link className="dashboard-empty-subjects" href={session.getAccessToken() ? "/subjects" : "/login"}><BookOpen /><span><b>{session.getAccessToken() ? "Create your first subject" : "Sign in to start"}</b><small>{session.getAccessToken() ? "Add a course to build its mastery journey." : "Your courses and progress stay synced to your account."}</small></span><ArrowRight /></Link>}
            {dashboardSubjects.map((subject, index) => (
              <button key={subject.id} className={`course-mini ${subject.id === selected.id ? "selected" : ""}`} onClick={() => setActive(index)}>
                <span className={`course-art ${subject.tone}`}>{subject.icon}</span>
                <strong>{subject.name}</strong>
                <span className="course-description">{subject.description}</span>
                <span className="ring" style={{ background: `conic-gradient(#35a64b ${subject.progress * 3.6}deg,#e7eae5 0)` }}><i>{subject.progress}%</i></span>
                <small>{subject.topics} levels</small>
              </button>
            ))}
          </div>
          {extraSubjects > 0 && <Link className="extra-subjects-strip" href="/subjects"><span className="extra-avatars">{subjects.slice(5, 9).map((subject) => <i className={subject.tone} key={subject.id}>{subject.icon}</i>)}</span><span><b>{extraSubjects} more {extraSubjects === 1 ? "subject" : "subjects"}</b><small>Open your full learning library</small></span><ArrowRight /></Link>}
        </section>

        <section className={`mastery-panel theme-${selected.tone}`} id="mastery-map">
          <header>
            <button className="subject-switch" onClick={() => setActive((current) => subjects.length ? (current - 1 + subjects.length) % subjects.length : 0)} disabled={subjects.length < 2} aria-label="Previous subject"><ChevronLeft /></button><div className="embedded-subject" key={selected.id}><b>{selected.icon}</b><span><small>Current mastery path</small><h2>{selected.name}</h2></span></div><button className="subject-switch" onClick={() => setActive((current) => subjects.length ? (current + 1) % subjects.length : 0)} disabled={subjects.length < 2} aria-label="Next subject"><ChevronRight /></button>
            <div className="path-stats"><div><Check /><b>{activeProgress?.completed_levels ?? completedLevels}</b><small>levels complete</small></div><div className="level-progress"><span><b>Course progress</b><small>{pathProgress}%</small></span><i><em style={{ width: `${pathProgress}%` }} /></i></div><div><CircleHelp /><b>{summary?.quizzes_completed ?? 0}</b><small>quizzes finished</small></div></div>
          </header>
          <div className="path-preview">
            {pathLoading ? <div className="dashboard-map-state"><LoaderCircle className="spin" /><b>Loading your path…</b><small>Getting your latest progress.</small></div> : visibleLevels.length === 0 ? <div className="dashboard-map-state"><Sparkles /><b>{pathError || "No learning path yet"}</b><small>Upload and process course materials, then generate your path.</small><Link href={selected.id === "subject" ? "/subjects" : `/subjects/${selected.id}`}>{selected.id === "subject" ? "Choose a subject" : "Set up this subject"}<ArrowRight /></Link></div> : <>
              <div className="path-preview-current">
                <span>{currentChapter}</span>
                <h3>{visibleLevels.find((level) => level.status === "current")?.title ?? visibleLevels[0].title}</h3>
                <p>{visibleLevels.find((level) => level.status === "current")?.description ?? visibleLevels[0].description}</p>
                <small>{unlockedLevels} of {path?.levels.length ?? 0} levels unlocked</small>
                <Link href={`/subjects/${selected.id}/map`}>Continue learning <ArrowRight /></Link>
              </div>
              <div className="path-preview-trail">
                <span className="path-preview-trail-line" aria-hidden="true" />
                {visibleLevels.map((level, index) => (
                  <Link key={level.id} href={`/subjects/${selected.id}/map`} className={`path-node ${level.status}`} title={level.title}>
                    {level.status === "complete" ? <Check /> : level.status === "locked" ? <LockKeyhole /> : index + 1}
                  </Link>
                ))}
              </div>
            </>}
          </div>
        </section>

        <section className="stats-row">
          <article className="stat-box peach"><Folder /><span>Materials</span><b>{summary?.materials_count ?? 0}</b><small>uploaded</small></article>
          <article className="stat-box lilac"><BookOpen /><span>Levels</span><b>{summary?.completed_levels ?? 0}</b><small>completed</small></article>
          <article className="stat-box blue"><Target /><span>Quiz score</span><b>{Math.round(summary?.average_quiz_score ?? 0)}%</b><small>average</small></article>
          <article className="weekly-goal"><div><span className="micro-label dark">OVERALL PROGRESS</span><h3>{overallProgress}% across {summary?.subjects_count ?? subjects.length} subjects</h3><div className="goal-bar"><i style={{ width: `${overallProgress}%` }} /></div></div><span>🎯</span></article>
        </section>
      </section>

      <AppMobileNav active="home" />
    </main>
  );
}
