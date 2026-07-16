"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle, ArrowLeft, ArrowRight, BookOpenCheck, Calculator,
  Check, ClipboardCheck, Clock3, Eye, FlaskConical, Lightbulb,
  ListChecks, LoaderCircle, LockKeyhole, PenLine, Sparkles, Target, Trophy, Wand2, X,
} from "lucide-react";
import { ApiError, ApiLearningLevel, ApiLearningPath, SlideBlock, pathlyApi, session } from "../../../_lib/api";
import { useSubjects } from "../../../_hooks/use-subjects";
import { AppMobileNav, AppSidebar } from "../../../_components/app-sidebar";
import styles from "./slides.module.css";

const textBlockMeta: Record<string, { label: string; icon: typeof Lightbulb }> = {
  explanation: { label: "Notes", icon: Lightbulb },
  example: { label: "Example", icon: FlaskConical },
  analogy: { label: "Analogy", icon: Sparkles },
  formula: { label: "Formula", icon: Calculator },
  tip: { label: "Tip", icon: Wand2 },
  common_mistake: { label: "Common mistake", icon: AlertTriangle },
  summary: { label: "Recap", icon: BookOpenCheck },
};

const ROW_HEIGHT = 128;
const DIVIDER_HEIGHT = 66;
const WAVE_X = [50, 76, 50, 24];
const CONFETTI_COLORS = ["#ffd151", "#55de7a", "#7754ce", "#4d76df", "#e0555d", "#ffa64d"];

function RevealBlock({ label, icon: Icon, prompt, answer }: { label: string; icon: typeof Lightbulb; prompt: string; answer: string }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className={styles.block}>
      <div className={styles.blockLabel}><Icon /> {label}</div>
      <p>{prompt}</p>
      {revealed
        ? <div className={styles.answer}>{answer || "No answer was provided for this question."}</div>
        : <button type="button" className={styles.revealButton} onClick={() => setRevealed(true)}><Eye /> Reveal answer</button>}
    </div>
  );
}

function MiniQuizBlock({
  block, onMastery,
}: {
  block: Extract<SlideBlock, { type: "mini_quiz" }>;
  onMastery: (allCorrect: boolean) => void;
}) {
  const [selected, setSelected] = useState<Record<number, number>>({});

  useEffect(() => {
    const allCorrect = block.questions.every((question, index) => selected[index] === question.correct_index);
    onMastery(allCorrect);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, block.questions]);

  return (
    <div className={`${styles.block} ${styles.quiz}`}>
      <div className={styles.blockLabel}><ListChecks /> Quick check — required to continue</div>
      {block.questions.map((question, questionIndex) => {
        const pickedIndex = selected[questionIndex];
        const isCorrect = pickedIndex === question.correct_index;
        return (
          <div key={questionIndex} className={styles.quizQuestion}>
            <p>{question.prompt}</p>
            <div className={styles.quizChoices}>
              {question.choices.map((choice, choiceIndex) => {
                const isPicked = pickedIndex === choiceIndex;
                const showState = pickedIndex !== undefined;
                const isCorrectChoice = choiceIndex === question.correct_index;
                const className = [
                  styles.quizChoice,
                  showState && isCorrectChoice ? styles.correct : "",
                  showState && isPicked && !isCorrectChoice ? styles.incorrect : "",
                ].join(" ");
                return (
                  <button
                    key={choiceIndex}
                    type="button"
                    className={className}
                    onClick={() => setSelected((current) => ({ ...current, [questionIndex]: choiceIndex }))}
                  >
                    {choice}
                  </button>
                );
              })}
            </div>
            {pickedIndex !== undefined && (
              <p className={isCorrect ? styles.quizCorrectNote : styles.quizExplanation}>
                {isCorrect ? "Correct!" : "Not quite — try another answer."} {question.explanation}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function LevelDialog({
  level, index, total, updating, error, onClose, onComplete,
}: {
  level: ApiLearningLevel;
  index: number;
  total: number;
  updating: boolean;
  error: string;
  onClose: () => void;
  onComplete: () => void;
}) {
  const blocks = useMemo(() => level.content.blocks ?? [], [level.content.blocks]);
  const quizBlockIndexes = useMemo(
    () => blocks.reduce<number[]>((acc, block, i) => (block.type === "mini_quiz" ? [...acc, i] : acc), []),
    [blocks],
  );
  const [mastery, setMastery] = useState<Record<number, boolean>>({});
  const requiresMastery = quizBlockIndexes.length > 0;
  const hasMastered = quizBlockIndexes.every((i) => mastery[i]);
  const canComplete = !requiresMastery || hasMastered;

  return (
    <div className={styles.dialogBackdrop} onClick={onClose}>
      <section className={styles.dialog} onClick={(event) => event.stopPropagation()}>
        <button type="button" className={styles.dialogClose} onClick={onClose} aria-label="Close level"><X /></button>
        <div className={styles.chapterRow}>
          <span className={styles.chapterLabel}>{level.chapter}</span>
          {level.kind === "boss" && <span className={styles.bossBadge}><Trophy /> Final challenge</span>}
          {level.kind === "checkpoint" && <span className={styles.checkpointBadge}><ListChecks /> Checkpoint</span>}
        </div>
        <h2 className={styles.slideTitle}>Level {index + 1} of {total}: {level.title}</h2>
        <p className={styles.slideDescription}>{level.description}</p>
        <div className={styles.slideMeta}>
          <span><Clock3 /> {level.estimated_minutes} min</span>
          <span><Target /> {level.status === "complete" ? "Completed" : level.status === "current" ? "In progress" : "Locked"}</span>
        </div>

        <div className={styles.blocks}>
          {blocks.length === 0
            ? <div className={styles.block}><p>{level.description}</p></div>
            : blocks.map((block, blockIndex) => block.type === "mini_quiz"
              ? (
                <MiniQuizBlock
                  key={blockIndex}
                  block={block}
                  onMastery={(allCorrect) => setMastery((current) => ({ ...current, [blockIndex]: allCorrect }))}
                />
              )
              : <SlideBlockView key={blockIndex} block={block} />)}
        </div>

        {error && <p className="map-action-error" role="alert">{error}</p>}

        <div className={styles.footer}>
          <button type="button" className={styles.secondaryNav} onClick={onClose}>Back to path</button>
          {level.status === "current" && (
            <div className={styles.completeGroup}>
              {requiresMastery && !hasMastered && (
                <small className={styles.gateHint}>Answer the quick check correctly to unlock the next level</small>
              )}
              <button type="button" className={styles.completeButton} disabled={updating || !canComplete} onClick={onComplete}>
                {updating ? <LoaderCircle className="spin" /> : <Check />} Mark complete & continue
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function SlideBlockView({ block }: { block: Exclude<SlideBlock, { type: "mini_quiz" }> }) {
  if ("prompt" in block) {
    return (
      <RevealBlock
        label={block.type === "checkpoint_question" ? "Checkpoint" : "Practice question"}
        icon={block.type === "checkpoint_question" ? ClipboardCheck : PenLine}
        prompt={block.prompt}
        answer={block.answer}
      />
    );
  }
  const meta = textBlockMeta[block.type] ?? textBlockMeta.explanation;
  const Icon = meta.icon;
  return (
    <div className={`${styles.block} ${styles[block.type] ?? ""}`}>
      <div className={styles.blockLabel}><Icon /> {meta.label}</div>
      <p>{block.text}</p>
    </div>
  );
}

function nodeIcon(level: ApiLearningLevel) {
  if (level.status === "complete") return Check;
  if (level.status === "locked") return LockKeyhole;
  if (level.kind === "boss") return Trophy;
  if (level.kind === "checkpoint") return ListChecks;
  return Sparkles;
}

type PathItem =
  | { kind: "divider"; y: number; label: string }
  | { kind: "node"; y: number; x: number; prevX: number | null; level: ApiLearningLevel; index: number };

function buildPath(levels: ApiLearningLevel[], chapterNumbers: Map<string, number>) {
  const items: PathItem[] = [];
  let cursor = 0;
  let waveIndex = 0;
  let prevX: number | null = null;
  levels.forEach((level, index) => {
    const startsChapter = index === 0 || levels[index - 1].chapter !== level.chapter;
    if (startsChapter) {
      items.push({ kind: "divider", y: cursor, label: `Chapter ${chapterNumbers.get(level.chapter)} · ${level.chapter}` });
      cursor += DIVIDER_HEIGHT;
      waveIndex = 0;
      prevX = null;
    }
    cursor += ROW_HEIGHT;
    const x = WAVE_X[waveIndex % WAVE_X.length];
    items.push({ kind: "node", y: cursor, x, prevX, level, index });
    prevX = x;
    waveIndex += 1;
  });
  return { items, height: cursor + 60 };
}

const CONFETTI_PIECES = Array.from({ length: 32 }, (_, i) => ({
  id: i,
  left: (i * 29) % 100,
  delay: ((i * 13) % 25) / 100,
  duration: 1 + ((i * 17) % 70) / 100,
  rotate: (i * 47) % 360,
  color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
}));

function Confetti() {
  const pieces = CONFETTI_PIECES;
  return (
    <div className={styles.confetti} aria-hidden="true">
      {pieces.map((piece) => (
        <span
          key={piece.id}
          style={{
            left: `${piece.left}%`,
            animationDelay: `${piece.delay}s`,
            animationDuration: `${piece.duration}s`,
            background: piece.color,
            transform: `rotate(${piece.rotate}deg)`,
          }}
        />
      ))}
    </div>
  );
}

export default function LearningPathPage() {
  const params = useParams<{ slug: string }>();
  const [subjects] = useSubjects();
  const subject = subjects.find((item) => item.id === params.slug) ?? {
    id: params.slug,
    name: "Study Journey",
    icon: "✨",
    tone: "purple",
    progress: 0,
    topics: 0,
  };
  const [path, setPath] = useState<ApiLearningPath | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [celebrating, setCelebrating] = useState(false);
  const [error, setError] = useState("");

  const loadPath = useCallback(async () => {
    if (!session.getAccessToken()) {
      setError("Sign in to load your saved learning path.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const savedPath = await pathlyApi.learning.getPath(params.slug);
      setPath(savedPath);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 404) {
        setError("Your learning path has not been generated yet.");
      } else {
        setError(requestError instanceof Error ? requestError.message : "Could not load this learning path.");
      }
      setPath(null);
    } finally {
      setLoading(false);
    }
  }, [params.slug]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPath(), 0);
    return () => window.clearTimeout(timer);
  }, [loadPath]);

  const levels = useMemo(
    () => [...(path?.levels ?? [])].sort((a, b) => a.order_index - b.order_index),
    [path],
  );
  const completedCount = levels.filter((level) => level.status === "complete").length;
  const progress = levels.length ? Math.round((completedCount / levels.length) * 100) : subject.progress;
  const chapterNumbers = useMemo(() => {
    const chapters = new Map<string, number>();
    levels.forEach((level) => {
      if (!chapters.has(level.chapter)) chapters.set(level.chapter, chapters.size + 1);
    });
    return chapters;
  }, [levels]);
  const { items: pathItems, height: pathHeight } = useMemo(
    () => buildPath(levels, chapterNumbers),
    [levels, chapterNumbers],
  );
  const opened = openIndex !== null ? levels[openIndex] : undefined;
  const journeyComplete = levels.length > 0 && completedCount === levels.length;

  async function markComplete() {
    if (!opened || opened.status !== "current") return;
    setUpdating(true);
    setError("");
    try {
      const updatedPath = await pathlyApi.learning.completeLevel(subject.id, opened.id);
      setPath(updatedPath);
      setCelebrating(true);
      window.setTimeout(() => {
        setCelebrating(false);
        const nextLevel = updatedPath.levels.findIndex((level) => level.status === "current");
        setOpenIndex(nextLevel >= 0 ? nextLevel : null);
      }, 1100);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update your progress.");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <main className={`course-shell theme-${subject.tone}`}>
      <AppSidebar active="subjects" />
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.topbar}>
            <Link href="/"><ArrowLeft /> Dashboard</Link>
          </div>
          <div className={styles.subjectTitle}>
            <span>{subject.icon}</span>
            <div><small>YOUR LEARNING PATH</small><h1>{subject.name}</h1></div>
          </div>
          {levels.length > 0 && (
            <div className={styles.progressRow}>
              <i><em style={{ width: `${progress}%` }} /></i>
              <b>{completedCount} / {levels.length} levels · {progress}%</b>
            </div>
          )}
        </header>

        {loading ? (
          <section className={styles.stateCard}><LoaderCircle className="spin" /><span>LOADING YOUR PATH</span><h2>Bringing your journey into focus…</h2></section>
        ) : !path || levels.length === 0 ? (
          <section className={styles.stateCard}>
            <Sparkles /><span>YOUR PATH STARTS HERE</span>
            <h2>{error || "No levels yet."}</h2>
            <p>Upload and process at least one course file and let the AI tutor build your journey, from your first concept to the hardest exam questions.</p>
            <div className={styles.stateLinks}>
              <Link href={`/subjects/${subject.id}`}>Manage materials <ArrowRight /></Link>
              {!session.getAccessToken() && <Link href="/login">Sign in</Link>}
            </div>
          </section>
        ) : (
          <section className={styles.trailWrap}>
            <div className={styles.trailIntro}>
              <Sparkles />
              <div><span>YOUR AI-BUILT JOURNEY</span><h2>{path.title}</h2><p>{path.summary || "Every level builds on the last, from your first concept to the hardest exam questions."}</p></div>
            </div>

            <div className={styles.trail} style={{ height: pathHeight }}>
              {pathItems.map((item, itemIndex) => {
                if (item.kind === "divider") {
                  return (
                    <div key={`divider-${itemIndex}`} className={styles.chapterDivider} style={{ top: item.y }}>
                      <span>{item.label}</span>
                    </div>
                  );
                }
                const { level, index, x, prevX } = item;
                const Icon = nodeIcon(level);
                return (
                  <div key={level.id}>
                    {prevX !== null && (
                      <svg
                        className={styles.connector}
                        style={{ top: item.y - ROW_HEIGHT, height: ROW_HEIGHT }}
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        aria-hidden="true"
                      >
                        <path
                          className={level.status === "locked" ? styles.connectorLocked : styles.connectorActive}
                          d={`M ${prevX} 0 C ${prevX} 55, ${x} 45, ${x} 100`}
                        />
                      </svg>
                    )}
                    <button
                      type="button"
                      className={`${styles.trailNode} ${styles[level.status]} ${styles[level.kind] ?? ""}`}
                      style={{ top: item.y - 33, left: `${x}%`, animationDelay: `${Math.min(index, 20) * 45}ms` }}
                      onClick={() => setOpenIndex(index)}
                      aria-label={`${level.title}, ${level.status}`}
                    >
                      <Icon />
                      {level.status === "current" && <em>{index === 0 ? "START" : "NEXT"}</em>}
                    </button>
                    <span
                      className={styles.nodeCaption}
                      style={{ top: item.y + 8, left: `${x}%`, animationDelay: `${Math.min(index, 20) * 45}ms` }}
                    >
                      {level.title}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className={`${styles.trailFinish} ${journeyComplete ? styles.complete : ""}`}>
              <Trophy />
              <div>
                <b>{journeyComplete ? "Journey complete!" : "Exam-ready awaits"}</b>
                <small>{journeyComplete ? "You mastered every level in this path." : "Finish every level to be ready for the hardest questions."}</small>
              </div>
            </div>
          </section>
        )}
      </div>

      {opened && (
        <LevelDialog
          level={opened}
          index={openIndex ?? 0}
          total={levels.length}
          updating={updating}
          error={error}
          onClose={() => setOpenIndex(null)}
          onComplete={() => void markComplete()}
        />
      )}
      {celebrating && <Confetti />}
      <AppMobileNav active="subjects" />
    </main>
  );
}
