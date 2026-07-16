"use client";

import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppMobileNav, AppSidebar } from "../../_components/app-sidebar";
import { useSubjects } from "../../_hooks/use-subjects";
import {
  ApiError,
  ApiMaterial,
  MaterialKind,
  pathlyApi,
} from "../../_lib/api";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Check,
  FileQuestion,
  FileText,
  FileUp,
  Flag,
  FlaskConical,
  GraduationCap,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
} from "lucide-react";

const uploadGroups = [
  { kind: "course" as const, title: "Course PDFs", description: "Textbooks, course packets and reading material", icon: BookOpen },
  { kind: "notes" as const, title: "Notes & slides", description: "Lecture notes, presentations and summaries", icon: FileText },
  { kind: "exams" as const, title: "Past final exams", description: "Previous finals, answer keys and mock exams", icon: GraduationCap },
  { kind: "practice" as const, title: "Practice problems", description: "Worksheets, assignments and question banks", icon: FileQuestion },
];

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(bytes / 1024, 0.1).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has ended. Sign in again to continue.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

const statusCopy: Record<ApiMaterial["status"], string> = {
  uploaded: "Queued for processing",
  processing: "Pathly is reading this file",
  ready: "Ready for AI",
  failed: "Processing failed",
};

export default function SubjectWorkspacePage() {
  const params = useParams<{ slug: string }>();
  const subjectId = params.slug;
  const [subjects] = useSubjects();
  const fallbackName = subjectId.split("-").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
  const subject = subjects.find((item) => item.id === subjectId) ?? { name: fallbackName, icon: "✨", tone: "green", progress: 0 };
  const [files, setFiles] = useState<ApiMaterial[]>([]);
  const [question, setQuestion] = useState("");
  const [questions, setQuestions] = useState<string[]>([]);
  const [loadingMaterials, setLoadingMaterials] = useState(true);
  const [uploading, setUploading] = useState<MaterialKind | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [checkingPath, setCheckingPath] = useState(true);
  const [error, setError] = useState("");

  const readyFiles = useMemo(() => files.filter((file) => file.status === "ready"), [files]);
  const hasPendingFiles = useMemo(
    () => files.some((file) => file.status === "uploaded" || file.status === "processing"),
    [files],
  );
  const materialCount = files.length;

  const loadMaterials = useCallback(async (quiet = false) => {
    try {
      const materials = await pathlyApi.materials.list(subjectId);
      setFiles(materials);
    } catch (requestError) {
      if (!quiet) setError(errorMessage(requestError));
    } finally {
      if (!quiet) setLoadingMaterials(false);
    }
  }, [subjectId]);

  useEffect(() => {
    let active = true;
    window.queueMicrotask(() => {
      void loadMaterials();
      void pathlyApi.learning.getPath(subjectId)
        .then((path) => {
          if (active) setGenerated(path.status === "ready");
        })
        .catch((requestError: unknown) => {
          if (active && (!(requestError instanceof ApiError) || requestError.status !== 404)) {
            setError(errorMessage(requestError));
          }
        })
        .finally(() => {
          if (active) setCheckingPath(false);
        });
    });
    return () => {
      active = false;
    };
  }, [loadMaterials, subjectId]);

  useEffect(() => {
    if (!hasPendingFiles) return;
    const timer = window.setInterval(() => void loadMaterials(true), 1600);
    return () => window.clearInterval(timer);
  }, [hasPendingFiles, loadMaterials]);

  async function uploadFiles(kind: MaterialKind, event: ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!incoming.length) return;
    setUploading(kind);
    setError("");
    try {
      const uploaded = await pathlyApi.materials.upload(subjectId, kind, incoming);
      setFiles((current) => [
        ...uploaded,
        ...current.filter((item) => !uploaded.some((newItem) => newItem.id === item.id)),
      ]);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setUploading(null);
    }
  }

  async function processMaterial(materialId: string) {
    setProcessingId(materialId);
    setError("");
    setFiles((current) => current.map((item) => item.id === materialId ? { ...item, status: "processing", error_message: null } : item));
    try {
      const processed = await pathlyApi.materials.process(subjectId, materialId);
      setFiles((current) => current.map((item) => item.id === materialId ? processed : item));
    } catch (requestError) {
      setError(errorMessage(requestError));
      await loadMaterials(true);
    } finally {
      setProcessingId(null);
    }
  }

  async function removeMaterial(materialId: string) {
    setDeletingId(materialId);
    setError("");
    try {
      await pathlyApi.materials.remove(subjectId, materialId);
      setFiles((current) => current.filter((item) => item.id !== materialId));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDeletingId(null);
    }
  }

  function addQuestion(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;
    setQuestions((current) => [...current, value]);
    setQuestion("");
  }

  async function generateMap() {
    setGenerating(true);
    setError("");
    try {
      const path = await pathlyApi.learning.generatePath(subjectId, questions);
      setGenerated(path.status === "ready");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setGenerating(false);
    }
  }

  const readinessLabel = hasPendingFiles
    ? "Processing materials"
    : readyFiles.length >= 5
      ? "Great"
      : readyFiles.length
        ? "Ready to build"
        : "Add learning material";

  return (
    <main className={`course-shell theme-${subject.tone}`}><AppSidebar active="subjects" /><div className="subject-workspace">
      <header className={`workspace-hero ${subject.tone}`}>
        <div className="workspace-top"><Link href="/subjects"><ArrowLeft /> All subjects</Link><div className="workspace-xp"><Target /> {subject.progress}% complete</div></div>
        <div className="workspace-title"><span>{subject.icon}</span><div><p>SUBJECT WORKSPACE</p><h1>{subject.name}</h1><small>Give Pathly everything it needs to build your personalized study journey.</small></div></div>
        <div className="workspace-progress"><span><b>{materialCount}</b> {materialCount === 1 ? "source" : "sources"} added</span><i><em style={{ width: `${Math.min(readyFiles.length * 20, 100)}%` }} /></i><span>AI readiness: {readinessLabel}</span></div>
      </header>

      <div className="workspace-body">
        <section className="workspace-main" id="materials">
          <div className="workspace-heading"><div><span>STEP 1</span><h2>Add learning materials</h2><p>Pathly will read and connect everything you upload.</p></div><div className="privacy-pill"><Check /> Private to you</div></div>
          {error && <div className="workspace-alert" role="alert"><AlertCircle /><span>{error}</span><button type="button" onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
          {loadingMaterials && <div className="workspace-loading" aria-live="polite"><LoaderCircle className="spin" /> Loading your materials…</div>}
          <div className="upload-grid">
            {uploadGroups.map((group) => {
              const Icon = group.icon;
              const groupFiles = files.filter((file) => file.kind === group.kind);
              const isUploading = uploading === group.kind;
              return <article className={`upload-group ${group.kind}`} key={group.kind} aria-busy={isUploading}>
                <div className="upload-group-head"><span><Icon /></span><div><h3>{group.title}</h3><p>{group.description}</p></div></div>
                <label>{isUploading ? <LoaderCircle className="spin" /> : <FileUp />}<b>{isUploading ? "Uploading securely…" : "Drop files or browse"}</b><small>PDF, DOCX, PPTX or TXT · max 25 MB</small><input type="file" multiple disabled={uploading !== null} accept=".pdf,.docx,.pptx,.txt,.md" onChange={(event) => void uploadFiles(group.kind, event)} /></label>
                <div className="uploaded-list">{groupFiles.map((file) => {
                  const isBusy = file.status === "uploaded" || file.status === "processing" || processingId === file.id;
                  return <div key={file.id} className={`material-${file.status}`}>
                    {isBusy ? <LoaderCircle className="spin" /> : file.status === "failed" ? <AlertCircle /> : <FileText />}
                    <span><b>{file.original_name}</b><small>{formatSize(file.size_bytes)} · {statusCopy[file.status]}</small>{file.error_message && <em>{file.error_message}</em>}</span>
                    <div className="material-actions">
                      {file.status === "failed" && <button type="button" onClick={() => void processMaterial(file.id)} disabled={processingId !== null} aria-label={`Retry ${file.original_name}`} title="Retry processing"><RefreshCw /></button>}
                      <button type="button" onClick={() => void removeMaterial(file.id)} disabled={deletingId === file.id || isBusy} aria-label={`Remove ${file.original_name}`} title="Remove file">{deletingId === file.id ? <LoaderCircle className="spin" /> : <Trash2 />}</button>
                    </div>
                  </div>;
                })}</div>
              </article>;
            })}
          </div>

          <section className="ai-questions">
            <div className="question-heading"><span><MessageSquareText /></span><div><p>STEP 2</p><h2>Tell the AI what matters</h2><small>Add questions, exam instructions or topics your professor emphasized.</small></div></div>
            <form onSubmit={addQuestion}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: The professor said integration by parts will be 30% of the final. Focus on questions similar to problem set 6..." /><button type="submit"><Plus /> Add instruction</button></form>
            {questions.length > 0 && <div className="question-list">{questions.map((item, index) => <div key={`${item}-${index}`}><Sparkles /><p>{item}</p><button type="button" aria-label="Remove instruction" onClick={() => setQuestions((current) => current.filter((_, itemIndex) => itemIndex !== index))}><Trash2 /></button></div>)}</div>}
          </section>
        </section>

        <aside className="engine-panel">
          <div className="engine-title"><span><BrainCircuit /></span><div><p>STEP 3</p><h2>Build your learning path</h2></div></div>
          <p className="engine-copy">The AI tutor reads every file as one course, works out prerequisites and teaching order, then decides exactly how many levels this journey needs — from zero knowledge to exam-ready.</p>
          <div className="engine-checklist"><div className={readyFiles.length ? "ready" : ""}><Check /><span><b>Learning materials</b><small>{readyFiles.length} of {files.length} files ready</small></span></div><div className={readyFiles.some((file) => file.kind === "exams") ? "ready" : ""}><Check /><span><b>Exam context</b><small>Past finals improve accuracy</small></span></div><div className={questions.length ? "ready" : ""}><Check /><span><b>Your instructions</b><small>{questions.length} added</small></span></div></div>
          <div className="engine-preview"><span>AI WILL GENERATE</span><div><Sparkles /> A prerequisite-ordered level path</div><div><FlaskConical /> Concise notes, examples & analogies</div><div><FileQuestion /> Mini quizzes woven into lessons</div><div><Flag /> An exam-ready final level</div></div>
          <button className="generate-map" onClick={() => void generateMap()} disabled={generating || checkingPath || readyFiles.length === 0 || hasPendingFiles}>{generating ? <><LoaderCircle className="spin" /> Building your learning path…</> : checkingPath ? <><LoaderCircle className="spin" /> Checking your path…</> : generated ? <><RefreshCw /> Rebuild learning path</> : <><BrainCircuit /> Generate learning path <ArrowRight /></>}</button>
          {generated && <Link className="open-generated-map" href={`/subjects/${subjectId}/map`}>Open your learning path <ArrowRight /></Link>}
          <Link className="open-generated-map" href={`/subjects/${subjectId}/quiz`}>Practice with a quiz <FileQuestion /></Link>
          <small className="engine-note">Only successfully processed files are used. Add instructions before generating to personalize the result.</small>
        </aside>
      </div></div><AppMobileNav active="subjects" />
    </main>
  );
}
