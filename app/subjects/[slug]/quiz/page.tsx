"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileQuestion,
  Lightbulb,
  ListChecks,
  LoaderCircle,
  RotateCcw,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { AppMobileNav, AppSidebar } from "../../../_components/app-sidebar";
import { ApiError, ApiLearningLevel, ApiLearningPath, pathlyApi, session } from "../../../_lib/api";
import { useSubjects } from "../../../_hooks/use-subjects";
import styles from "./quiz.module.css";

type Difficulty = "easy" | "medium" | "hard" | "adaptive";

type QuizQuestion = {
  id: string;
  order_index: number;
  prompt: string;
  question_type: string;
  options: string[];
  explanation: string | null;
};

type Quiz = {
  id: string;
  subject_id: string;
  level_id: string | null;
  title: string;
  difficulty: string;
  questions: QuizQuestion[];
  created_at: string;
};

type AnswerResult = {
  question_id: string;
  correct: boolean;
  correct_answer: string;
  explanation: string;
};

type QuizAttempt = {
  id: string;
  quiz_id: string;
  score: number;
  correct_count: number;
  total_count: number;
  results: AnswerResult[];
  created_at: string;
};

function messageFor(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session ended. Sign in again to continue.";
    if (error.status === 503) return "The AI is not available right now. Check the Gemini setup and try again.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function levelLabel(level: ApiLearningLevel, index: number) {
  return `Level ${index + 1} · ${level.title}`;
}

export default function QuizPage() {
  const params = useParams<{ slug: string }>();
  const subjectId = params.slug;
  const [subjects] = useSubjects();
  const subject = subjects.find((item) => item.id === subjectId) ?? {
    id: subjectId,
    name: "Study Journey",
    icon: "✨",
    tone: "purple",
    progress: 0,
    topics: 0,
  };
  const [learningPath, setLearningPath] = useState<ApiLearningPath | null>(null);
  const [loadingContext, setLoadingContext] = useState(true);
  const [selectedLevelId, setSelectedLevelId] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("adaptive");
  const [questionCount, setQuestionCount] = useState(8);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [hints, setHints] = useState<Record<string, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [hintLoading, setHintLoading] = useState<string | null>(null);
  const [error, setError] = useState("");

  const levels = useMemo(
    () => [...(learningPath?.levels ?? [])].sort((a, b) => a.order_index - b.order_index),
    [learningPath],
  );
  const question = quiz?.questions[currentIndex];
  const answeredCount = quiz
    ? quiz.questions.filter((item) => Boolean(answers[item.id])).length
    : 0;
  const questionProgress = quiz?.questions.length
    ? Math.round(((currentIndex + 1) / quiz.questions.length) * 100)
    : 0;
  const resultByQuestion = useMemo(
    () => new Map((attempt?.results ?? []).map((result) => [result.question_id, result])),
    [attempt],
  );
  const selectedLevel = levels.find((level) => level.id === selectedLevelId);

  const loadContext = useCallback(async () => {
    if (!session.getAccessToken()) {
      setError("Sign in to create a quiz from your saved materials.");
      setLoadingContext(false);
      return;
    }
    setLoadingContext(true);
    try {
      const savedPath = await pathlyApi.learning.getPath(subjectId);
      setLearningPath(savedPath);
      const requestedLevel = new URLSearchParams(window.location.search).get("level");
      const eligibleRequested = savedPath.levels.find(
        (level) => level.id === requestedLevel && level.status !== "locked",
      );
      const current = savedPath.levels.find((level) => level.status === "current");
      setSelectedLevelId(eligibleRequested?.id ?? current?.id ?? "");
    } catch (requestError) {
      if (!(requestError instanceof ApiError) || requestError.status !== 404) {
        setError(messageFor(requestError));
      }
      setLearningPath(null);
    } finally {
      setLoadingContext(false);
    }
  }, [subjectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadContext(), 0);
    return () => window.clearTimeout(timer);
  }, [loadContext]);

  async function generateQuiz() {
    setGenerating(true);
    setError("");
    setQuiz(null);
    setAttempt(null);
    setAnswers({});
    setHints({});
    setCurrentIndex(0);
    try {
      const generated = await pathlyApi.quizzes.generate(subjectId, {
        level_id: selectedLevelId || undefined,
        count: questionCount,
        difficulty,
      }) as unknown as Quiz;
      if (!generated.questions?.length) throw new Error("The AI returned an empty quiz. Try generating it again.");
      setQuiz(generated);
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setGenerating(false);
    }
  }

  function chooseAnswer(answer: string) {
    if (!question || attempt) return;
    setAnswers((current) => ({ ...current, [question.id]: answer }));
  }

  async function revealHint() {
    if (!quiz || !question || hints[question.id]) return;
    setHintLoading(question.id);
    setError("");
    try {
      const response = await pathlyApi.quizzes.hint(subjectId, quiz.id, question.id);
      setHints((current) => ({ ...current, [question.id]: response.hint }));
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setHintLoading(null);
    }
  }

  async function submitQuiz() {
    if (!quiz || answeredCount !== quiz.questions.length) return;
    setSubmitting(true);
    setError("");
    try {
      const submitted = await pathlyApi.quizzes.submit(subjectId, quiz.id, answers) as unknown as QuizAttempt;
      setAttempt(submitted);
      setCurrentIndex(0);
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  function resetQuiz() {
    setQuiz(null);
    setAttempt(null);
    setAnswers({});
    setHints({});
    setCurrentIndex(0);
    setError("");
  }

  if (loadingContext) {
    return (
      <main className={`course-shell theme-${subject.tone}`}>
        <AppSidebar active="subjects" />
        <div className={styles.page}><section className={styles.loading}><LoaderCircle /><span>PREPARING PRACTICE</span><h1>Setting up your study room…</h1></section></div>
        <AppMobileNav active="subjects" />
      </main>
    );
  }

  return (
    <main className={`course-shell theme-${subject.tone}`}>
      <AppSidebar active="subjects" />
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.topbar}>
            <Link href={`/subjects/${subjectId}/map`}><ArrowLeft /> Mastery map</Link>
            <div className={styles.subjectChip}><span>{subject.icon}</span><b>{subject.name}</b></div>
          </div>
          <div className={styles.headerContent}>
            <span className={styles.heroIcon}><FileQuestion /></span>
            <div><small>PERSONALIZED PRACTICE</small><h1>Mastery quiz</h1><p>Questions are generated from your own uploaded materials, so every answer moves your understanding forward.</p></div>
          </div>
          {quiz && !attempt && <div className={styles.headerProgress}><span><b>Question {currentIndex + 1}</b> of {quiz.questions.length}</span><i><em style={{ width: `${questionProgress}%` }} /></i><span>{answeredCount} answered</span></div>}
        </header>

        {error && <div className={styles.alert} role="alert"><AlertCircle /><span>{error}</span><button type="button" onClick={() => setError("")} aria-label="Dismiss error"><X /></button></div>}

        {!quiz && !generating && (
          <div className={styles.setupLayout}>
            <section className={styles.setupCard}>
              <div className={styles.sectionTitle}><span><BrainCircuit /></span><div><small>QUIZ BUILDER</small><h2>Choose what to practice</h2><p>Pathly will ground every question in your processed study materials.</p></div></div>

              <div className={styles.fieldGroup}>
                <label htmlFor="quiz-scope">Focus</label>
                <div className={styles.selectWrap}><BookOpenCheck /><select id="quiz-scope" value={selectedLevelId} onChange={(event) => setSelectedLevelId(event.target.value)}><option value="">Entire course</option>{levels.map((level, index) => <option key={level.id} value={level.id} disabled={level.status === "locked"}>{levelLabel(level, index)}{level.status === "locked" ? " — locked" : ""}</option>)}</select></div>
                <small>{selectedLevel ? selectedLevel.description : "A mixed review across all available material."}</small>
              </div>

              <fieldset className={styles.choiceGroup}><legend>Difficulty</legend><div>{(["easy", "medium", "hard", "adaptive"] as Difficulty[]).map((value) => <button type="button" key={value} className={difficulty === value ? styles.selectedChoice : ""} onClick={() => setDifficulty(value)}><span>{value === "adaptive" ? <Sparkles /> : value === "easy" ? "01" : value === "medium" ? "02" : "03"}</span><b>{value.charAt(0).toUpperCase() + value.slice(1)}</b><small>{value === "adaptive" ? "AI-balanced" : value === "easy" ? "Build confidence" : value === "medium" ? "Exam practice" : "Deep challenge"}</small></button>)}</div></fieldset>

              <fieldset className={styles.lengthGroup}><legend>Length</legend><div>{[5, 8, 12].map((count) => <button type="button" key={count} className={questionCount === count ? styles.selectedLength : ""} onClick={() => setQuestionCount(count)}><b>{count}</b><span>questions</span><small><Clock3 /> about {Math.ceil(count * 1.5)} min</small></button>)}</div></fieldset>

              <button className={styles.generateButton} type="button" onClick={() => void generateQuiz()}><Sparkles /> Generate my quiz <ArrowRight /></button>
            </section>

            <aside className={styles.setupAside}>
              <div className={styles.mascot}><span>{subject.icon}</span><Sparkles /></div>
              <small>HOW IT WORKS</small><h2>Practice with purpose.</h2><p>Your quiz is built only from files that Pathly has successfully processed.</p>
              <div className={styles.trustList}><div><Check /><span><b>Source-grounded</b><small>Based on your materials</small></span></div><div><Lightbulb /><span><b>Helpful hints</b><small>Clues without spoilers</small></span></div><div><ListChecks /><span><b>Clear review</b><small>Explanations after submitting</small></span></div><div><Target /><span><b>Real progress</b><small>Results saved to your profile</small></span></div></div>
              {!learningPath && <div className={styles.contextNote}><CircleHelp /><span><b>No map yet? No problem.</b><small>You can make a course-wide quiz now, or generate a mastery map first.</small></span></div>}
              <Link href={`/subjects/${subjectId}`}>Manage learning materials <ArrowRight /></Link>
            </aside>
          </div>
        )}

        {generating && <section className={styles.generating}><div className={styles.aiOrb}><BrainCircuit /><i /><i /><i /></div><span>GEMINI IS BUILDING YOUR QUIZ</span><h2>Turning your materials into useful questions…</h2><p>This can take a moment. Pathly is checking the questions, choices, hints and explanations.</p><div><i /><i /><i /></div></section>}

        {quiz && !attempt && question && (
          <div className={styles.quizLayout}>
            <section className={styles.questionCard}>
              <div className={styles.questionMeta}><span>QUESTION {currentIndex + 1}</span><small>{quiz.difficulty} · {selectedLevel?.title ?? "Course review"}</small></div>
              <h2>{question.prompt}</h2>
              <div className={styles.answers} role="radiogroup" aria-label={`Answers for question ${currentIndex + 1}`}>{question.options.map((option, index) => { const selected = answers[question.id] === option; return <button key={`${question.id}-${index}`} type="button" role="radio" aria-checked={selected} className={selected ? styles.answerSelected : ""} onClick={() => chooseAnswer(option)}><span>{String.fromCharCode(65 + index)}</span><b>{option}</b>{selected && <CheckCircle2 />}</button>; })}</div>
              {hints[question.id] && <div className={styles.hintBox}><Lightbulb /><div><b>A small nudge</b><p>{hints[question.id]}</p></div></div>}
              <div className={styles.questionActions}><button type="button" className={styles.hintButton} onClick={() => void revealHint()} disabled={Boolean(hints[question.id]) || hintLoading === question.id}>{hintLoading === question.id ? <LoaderCircle /> : <Lightbulb />} {hints[question.id] ? "Hint revealed" : "Show a hint"}</button><div><button type="button" onClick={() => setCurrentIndex((value) => Math.max(0, value - 1))} disabled={currentIndex === 0} aria-label="Previous question"><ChevronLeft /></button>{currentIndex < quiz.questions.length - 1 ? <button type="button" className={styles.nextButton} onClick={() => setCurrentIndex((value) => value + 1)}>Next question <ChevronRight /></button> : <button type="button" className={styles.submitButton} disabled={answeredCount !== quiz.questions.length || submitting} onClick={() => void submitQuiz()}>{submitting ? <><LoaderCircle /> Checking answers…</> : <><Check /> Submit quiz</>}</button>}</div></div>
              {currentIndex === quiz.questions.length - 1 && answeredCount !== quiz.questions.length && <p className={styles.unanswered}><CircleHelp /> Answer all {quiz.questions.length} questions before submitting. {quiz.questions.length - answeredCount} left.</p>}
            </section>

            <aside className={styles.navigator}>
              <div><small>QUIZ PROGRESS</small><b>{answeredCount}/{quiz.questions.length}</b><span>answered</span></div>
              <nav aria-label="Quiz questions">{quiz.questions.map((item, index) => <button type="button" key={item.id} className={`${index === currentIndex ? styles.currentDot : ""} ${answers[item.id] ? styles.answeredDot : ""}`} onClick={() => setCurrentIndex(index)} aria-label={`Question ${index + 1}${answers[item.id] ? ", answered" : ""}`}>{answers[item.id] ? <Check /> : index + 1}</button>)}</nav>
              <div className={styles.navigatorTip}><Lightbulb /><p>You can move between questions and change any answer before submitting.</p></div>
              <button type="button" onClick={resetQuiz}><RotateCcw /> Start over</button>
            </aside>
          </div>
        )}

        {quiz && attempt && (
          <div className={styles.resultsLayout}>
            <section className={styles.resultHero}>
              <div className={`${styles.scoreRing} ${attempt.score >= 70 ? styles.passed : styles.keepGoing}`} style={{ "--score": `${attempt.score * 3.6}deg` } as React.CSSProperties}><span><b>{attempt.score}%</b><small>score</small></span></div>
              <div><small>QUIZ COMPLETE</small><h2>{attempt.score >= 90 ? "Brilliant work!" : attempt.score >= 70 ? "You’re building real mastery." : "Good practice—keep going."}</h2><p>You answered <b>{attempt.correct_count} of {attempt.total_count}</b> questions correctly. Your result has been added to your progress.</p><div className={styles.resultActions}><button type="button" onClick={resetQuiz}><RotateCcw /> New quiz</button><Link href={`/subjects/${subjectId}/map`}>Back to mastery map <ArrowRight /></Link></div></div>
            </section>

            <section className={styles.review}>
              <div className={styles.reviewTitle}><div><small>ANSWER REVIEW</small><h2>Learn from every question</h2></div><span><CheckCircle2 /> {attempt.correct_count} correct</span></div>
              <div className={styles.reviewList}>{quiz.questions.map((item, index) => { const result = resultByQuestion.get(item.id); const correct = result?.correct ?? false; return <article key={item.id} className={correct ? styles.correctReview : styles.incorrectReview}><div className={styles.reviewNumber}>{correct ? <Check /> : <X />}</div><div><small>QUESTION {index + 1}</small><h3>{item.prompt}</h3><div className={styles.answerCompare}><span><small>Your answer</small><b>{answers[item.id]}</b></span>{!correct && <span><small>Correct answer</small><b>{result?.correct_answer}</b></span>}</div><div className={styles.explanation}><BrainCircuit /><p>{result?.explanation || "Review this concept in your learning materials before trying again."}</p></div></div></article>; })}</div>
            </section>
          </div>
        )}
      </div>
      <AppMobileNav active="subjects" />
    </main>
  );
}
