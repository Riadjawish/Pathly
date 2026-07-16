"use client";

import {
  FormEvent,
  KeyboardEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  Bot,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Copy,
  FileText,
  GraduationCap,
  LibraryBig,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";
import { AppMobileNav, AppSidebar } from "../../../_components/app-sidebar";
import { useSubjects } from "../../../_hooks/use-subjects";
import { ApiError, pathlyApi, session } from "../../../_lib/api";
import styles from "./chat.module.css";

type ChatSource = {
  id: string;
  materialName: string;
  pageNumber: string | number | null;
  excerpt: string;
  score: number | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  createdAt: string;
  pending?: boolean;
  failed?: boolean;
};

const quickPrompts = [
  {
    icon: BookOpen,
    label: "Explain a concept",
    prompt: "Explain the most important concept in my materials in simple terms, then give me an example.",
  },
  {
    icon: ClipboardCheck,
    label: "Prepare for my exam",
    prompt: "Based on my uploaded materials, what should I focus on first for the exam and why?",
  },
  {
    icon: CircleHelp,
    label: "Test my understanding",
    prompt: "Ask me one challenging question from my materials, but do not reveal the answer yet.",
  },
  {
    icon: GraduationCap,
    label: "Build a review plan",
    prompt: "Create a short, ordered review plan using the topics in my uploaded materials.",
  },
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSource(value: unknown): ChatSource | null {
  if (!isRecord(value)) return null;
  const id = typeof value.id === "string" ? value.id : "Source";
  const materialName = typeof value.material_name === "string" && value.material_name.trim()
    ? value.material_name
    : "Course material";
  const pageNumber = typeof value.page_number === "string" || typeof value.page_number === "number"
    ? value.page_number
    : null;
  const excerpt = typeof value.excerpt === "string" ? value.excerpt : "";
  const score = typeof value.score === "number" ? value.score : null;
  return { id, materialName, pageNumber, excerpt, score };
}

function parseMessage(value: unknown): ChatMessage | null {
  if (!isRecord(value)) return null;
  if (value.role !== "user" && value.role !== "assistant") return null;
  if (typeof value.content !== "string" || !value.content.trim()) return null;
  const sources = Array.isArray(value.sources)
    ? value.sources.map(parseSource).filter((source): source is ChatSource => source !== null)
    : [];
  return {
    id: typeof value.id === "string" ? value.id : crypto.randomUUID(),
    role: value.role,
    content: value.content,
    sources,
    createdAt: typeof value.created_at === "string" ? value.created_at : new Date().toISOString(),
  };
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Now";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
}

function requestError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session ended. Sign in again to continue your conversation.";
    if (error.status === 503) return "The AI assistant is temporarily unavailable. Your conversation is still saved.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Pathly could not reach the study assistant.";
}

function inlineCitations(text: string): ReactNode[] {
  return text.split(/(\[S\d+\])/g).map((part, index) =>
    /^\[S\d+\]$/.test(part)
      ? <mark className={styles.inlineCitation} key={`${part}-${index}`}>{part.slice(1, -1)}</mark>
      : part,
  );
}

function AnswerContent({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let bullets: string[] = [];

  function flushBullets() {
    if (!bullets.length) return;
    elements.push(
      <ul key={`list-${elements.length}`}>
        {bullets.map((item, index) => <li key={`${item}-${index}`}>{inlineCitations(item)}</li>)}
      </ul>,
    );
    bullets = [];
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (/^[-*•]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*•]\s+/, ""));
      return;
    }
    flushBullets();
    if (!line) return;
    if (/^#{1,3}\s+/.test(line)) {
      elements.push(<h4 key={`heading-${elements.length}`}>{inlineCitations(line.replace(/^#{1,3}\s+/, ""))}</h4>);
    } else {
      elements.push(<p key={`paragraph-${elements.length}`}>{inlineCitations(line)}</p>);
    }
  });
  flushBullets();
  return <div className={styles.answerContent}>{elements}</div>;
}

export default function SubjectChatPage() {
  const params = useParams<{ slug: string }>();
  const subjectId = params.slug;
  const [subjects] = useSubjects();
  const subject = subjects.find((item) => item.id === subjectId) ?? {
    id: subjectId,
    name: "Study workspace",
    icon: "✨",
    tone: "purple",
    progress: 0,
    topics: 0,
  };
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [sendError, setSendError] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [materialCount, setMaterialCount] = useState(0);
  const [readyMaterialCount, setReadyMaterialCount] = useState(0);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const sourceCount = useMemo(
    () => new Set(messages.flatMap((message) => message.sources.map((source) => `${source.materialName}-${source.pageNumber}-${source.id}`))).size,
    [messages],
  );

  const loadConversation = useCallback(async () => {
    if (!session.getAccessToken()) {
      setLoadError("Sign in to start a private, saved study conversation.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError("");
    try {
      const [history, materials] = await Promise.all([
        pathlyApi.chat.history(subjectId),
        pathlyApi.materials.list(subjectId),
      ]);
      setMessages(history.map(parseMessage).filter((message): message is ChatMessage => message !== null));
      setMaterialCount(materials.length);
      setReadyMaterialCount(materials.filter((material) => material.status === "ready").length);
    } catch (error) {
      setLoadError(requestError(error));
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadConversation(), 0);
    return () => window.clearTimeout(timer);
  }, [loadConversation]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: messages.length > 1 ? "smooth" : "auto", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    const input = textareaRef.current;
    if (!input) return;
    input.style.height = "0px";
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
  }, [draft]);

  async function sendMessage(value?: string) {
    const message = (value ?? draft).trim();
    if (!message || sending) return;
    const optimisticId = `local-${messages.length}`;
    setDraft("");
    setSending(true);
    setSendError("");
    setMessages((current) => [...current, {
      id: optimisticId,
      role: "user",
      content: message,
      sources: [],
      createdAt: new Date().toISOString(),
      pending: true,
    }]);
    try {
      const rawReply = await pathlyApi.chat.send(subjectId, message);
      const userMessage = isRecord(rawReply) ? parseMessage(rawReply.user_message) : null;
      const assistantMessage = isRecord(rawReply) ? parseMessage(rawReply.assistant_message) : null;
      if (!assistantMessage) throw new Error("The assistant returned an unreadable response.");
      setMessages((current) => [
        ...current.filter((item) => item.id !== optimisticId),
        ...(userMessage ? [userMessage] : [{
          id: optimisticId,
          role: "user" as const,
          content: message,
          sources: [],
          createdAt: new Date().toISOString(),
        }]),
        assistantMessage,
      ]);
    } catch (error) {
      setMessages((current) => current.map((item) => item.id === optimisticId
        ? { ...item, pending: false, failed: true }
        : item));
      setSendError(requestError(error));
    } finally {
      setSending(false);
      window.setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }

  function submitMessage(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  async function copyAnswer(message: ChatMessage) {
    await navigator.clipboard.writeText(message.content);
    setCopiedId(message.id);
    window.setTimeout(() => setCopiedId((current) => current === message.id ? null : current), 1500);
  }

  const hasToken = Boolean(session.getAccessToken());

  return (
    <main className={`course-shell theme-${subject.tone}`}>
      <AppSidebar active="subjects" />
      <div className={styles.chatPage}>
        <header className={styles.chatHeader}>
          <div className={styles.headerTop}>
            <Link href={`/subjects/${subjectId}`}><ArrowLeft /> Subject workspace</Link>
            <div className={styles.headerActions}>
              <Link href={`/subjects/${subjectId}/map`}><Target /> Learning path</Link>
              <span><Sparkles /> Grounded AI</span>
            </div>
          </div>
          <div className={styles.headerIdentity}>
            <span className={styles.subjectIcon}>{subject.icon}</span>
            <div><small>PATHLY STUDY ASSISTANT</small><h1>Learn {subject.name} together.</h1><p>Ask questions, untangle difficult ideas, and get answers grounded in your own course materials.</p></div>
          </div>
        </header>

        <div className={styles.chatLayout}>
          <aside className={styles.contextRail}>
            <div className={styles.contextCard}>
              <span className={styles.contextIcon}><LibraryBig /></span>
              <small>YOUR KNOWLEDGE BASE</small>
              <h2>{readyMaterialCount} ready {readyMaterialCount === 1 ? "source" : "sources"}</h2>
              <p>{materialCount
                ? `${readyMaterialCount} of ${materialCount} uploaded files can currently ground the assistant.`
                : "Upload notes, slides, PDFs or exams to give the assistant course context."}</p>
              <div className={styles.readinessBar}><span style={{ width: `${materialCount ? (readyMaterialCount / materialCount) * 100 : 0}%` }} /></div>
              <Link href={`/subjects/${subjectId}#materials`}>{materialCount ? "Manage sources" : "Add materials"} <ChevronRight /></Link>
            </div>

            <div className={styles.promptCard}>
              <div><Sparkles /><span><small>QUICK START</small><b>Try asking Pathly</b></span></div>
              <div className={styles.promptList}>
                {quickPrompts.map(({ icon: Icon, label, prompt }) => (
                  <button type="button" onClick={() => void sendMessage(prompt)} disabled={sending || loading || !hasToken} key={label}>
                    <Icon /><span>{label}</span><ChevronRight />
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.privacyNote}><Check /><span><b>Private to your account</b><small>Your chat is saved so you can continue later.</small></span></div>
          </aside>

          <section className={styles.conversation} aria-label={`${subject.name} study conversation`}>
            <div className={styles.conversationBar}>
              <div className={styles.assistantIdentity}><span><Bot /></span><div><b>Pathly tutor</b><small><i /> Ready to study {subject.name}</small></div></div>
              <div className={styles.contextStatus}><FileText /> {sourceCount || readyMaterialCount} sources used</div>
            </div>

            <div className={styles.messageList} aria-live="polite" aria-busy={loading}>
              {loading ? (
                <div className={styles.stateCard}><LoaderCircle className={styles.spin} /><span>OPENING YOUR CONVERSATION</span><h2>Getting your study space ready…</h2></div>
              ) : loadError ? (
                <div className={styles.stateCard}><MessageSquareText /><span>YOUR PRIVATE STUDY SPACE</span><h2>{loadError}</h2><p>Your messages and subject materials are linked to your Pathly account.</p><div>{hasToken ? <button type="button" onClick={() => void loadConversation()}><RefreshCw /> Try again</button> : <Link href="/login">Sign in to continue <ChevronRight /></Link>}</div></div>
              ) : messages.length === 0 ? (
                <div className={styles.welcomeCard}>
                  <div className={styles.welcomeMascot}><span>{subject.icon}</span><i><Sparkles /></i></div>
                  <span>YOUR COURSE-AWARE TUTOR</span>
                  <h2>What can we make clearer today?</h2>
                  <p>I&apos;ll answer from your processed {subject.name} materials and show exactly which sources helped me.</p>
                  <div className={styles.welcomePrompts}>{quickPrompts.slice(0, 3).map(({ label, prompt }) => <button type="button" onClick={() => void sendMessage(prompt)} key={label}>{label}<ChevronRight /></button>)}</div>
                </div>
              ) : (
                <>
                  <div className={styles.dayDivider}><span>Study session</span></div>
                  {messages.map((message) => (
                    <article className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage} ${message.failed ? styles.failedMessage : ""}`} key={message.id}>
                      <div className={styles.messageAvatar}>{message.role === "user" ? <UserRound /> : <Bot />}</div>
                      <div className={styles.messageColumn}>
                        <div className={styles.messageMeta}><b>{message.role === "user" ? "You" : "Pathly tutor"}</b><time>{formatTime(message.createdAt)}</time>{message.pending && <span><LoaderCircle className={styles.spin} /> Sending</span>}{message.failed && <span className={styles.failedLabel}>Not answered</span>}</div>
                        <div className={styles.messageBubble}>
                          {message.role === "assistant" ? <AnswerContent content={message.content} /> : <p>{message.content}</p>}
                        </div>
                        {message.role === "assistant" && (
                          <div className={styles.messageTools}>
                            <button type="button" onClick={() => void copyAnswer(message)}><Copy /> {copiedId === message.id ? "Copied" : "Copy answer"}</button>
                            {message.sources.length > 0 && <span><Check /> Grounded in {message.sources.length} {message.sources.length === 1 ? "source" : "sources"}</span>}
                          </div>
                        )}
                        {message.sources.length > 0 && (
                          <div className={styles.sources}>
                            <div className={styles.sourcesHeading}><LibraryBig /><span><b>Sources from your materials</b><small>Open a source to see the supporting passage.</small></span></div>
                            <div className={styles.sourceGrid}>
                              {message.sources.map((source, index) => (
                                <details key={`${message.id}-${source.id}-${index}`}>
                                  <summary><span>{source.id}</span><div><b>{source.materialName}</b><small>{source.pageNumber !== null ? `Page ${source.pageNumber}` : "Course material"}</small></div><ChevronRight /></summary>
                                  {source.excerpt && <p>{source.excerpt}</p>}
                                </details>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                  {sending && <article className={`${styles.message} ${styles.assistantMessage}`}><div className={styles.messageAvatar}><Bot /></div><div className={styles.messageColumn}><div className={styles.messageMeta}><b>Pathly tutor</b><span><Sparkles /> Reading your materials</span></div><div className={`${styles.messageBubble} ${styles.thinkingBubble}`}><i /><i /><i /></div></div></article>}
                </>
              )}
              <div ref={messageEndRef} />
            </div>

            <div className={styles.composerArea}>
              {sendError && <div className={styles.sendError} role="alert"><CircleHelp /><span>{sendError}</span><button type="button" onClick={() => setSendError("")}>Dismiss</button></div>}
              <form className={styles.composer} onSubmit={submitMessage}>
                <textarea ref={textareaRef} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder={`Ask anything about ${subject.name}…`} rows={1} maxLength={5000} disabled={!hasToken || loading} aria-label="Message Pathly tutor" />
                <button type="submit" disabled={!draft.trim() || sending || !hasToken} aria-label="Send message">{sending ? <LoaderCircle className={styles.spin} /> : <Send />}</button>
              </form>
              <div className={styles.composerNote}><span><Sparkles /> Answers use your uploaded course materials</span><small>Enter to send · Shift + Enter for a new line</small></div>
            </div>
          </section>
        </div>
      </div>
      <AppMobileNav active="subjects" />
    </main>
  );
}
