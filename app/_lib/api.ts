export type ApiTokens = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};

export type ApiUser = {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  university: string | null;
  course: string | null;
  study_goal: string | null;
  streak_days: number;
  email_verified: boolean;
  created_at: string;
};

export type ApiDevEmail = {
  subject: string;
  body: string;
  sent_at: string;
};

export type ApiSubject = {
  id: string;
  name: string;
  short_name: string;
  description: string;
  icon: string;
  tone: string;
  progress: number;
  topics_count: number;
  created_at: string;
  updated_at: string;
};

export type MaterialKind = "course" | "notes" | "exams" | "practice";

export type ApiMaterial = {
  id: string;
  subject_id: string;
  kind: MaterialKind;
  original_name: string;
  content_type: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  error_message: string | null;
  extracted_chars: number;
  created_at: string;
};

export type SlideMiniQuizQuestion = {
  prompt: string;
  choices: string[];
  correct_index: number;
  explanation: string;
};

export type SlideBlock =
  | { type: "explanation" | "example" | "analogy" | "formula" | "tip" | "common_mistake" | "summary"; text: string }
  | { type: "checkpoint_question" | "practice_question"; prompt: string; answer: string }
  | { type: "mini_quiz"; questions: SlideMiniQuizQuestion[] };

export type ApiLearningLevel = {
  id: string;
  order_index: number;
  chapter: string;
  title: string;
  description: string;
  status: "locked" | "current" | "complete";
  kind: "lesson" | "summary" | "practice" | "checkpoint" | "boss" | "final_review";
  estimated_minutes: number;
  content: { objectives?: string[]; blocks?: SlideBlock[] };
};

export type ApiLearningPath = {
  id: string;
  subject_id: string;
  title: string;
  summary: string;
  status: "generating" | "ready" | "failed";
  levels: ApiLearningLevel[];
  created_at: string;
  updated_at: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
const ACCESS_KEY = "pathly-access-token";
const REFRESH_KEY = "pathly-refresh-token";

function canUseStorage() {
  return typeof window !== "undefined";
}

export const session = {
  getAccessToken: () => canUseStorage() ? window.localStorage.getItem(ACCESS_KEY) : null,
  getRefreshToken: () => canUseStorage() ? window.localStorage.getItem(REFRESH_KEY) : null,
  save(tokens: ApiTokens) {
    if (!canUseStorage()) return;
    window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
    window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() {
    if (!canUseStorage()) return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

async function readResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, body);
  }
  return body as T;
}

async function refreshSession(): Promise<boolean> {
  const refreshToken = session.getRefreshToken();
  if (!refreshToken) return false;
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    session.clear();
    return false;
  }
  session.save(await readResponse<ApiTokens>(response));
  return true;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  const accessToken = session.getAccessToken();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (response.status === 401 && retry && await refreshSession()) {
    return request<T>(path, init, false);
  }
  return readResponse<T>(response);
}

function json(method: string, value?: unknown): RequestInit {
  return { method, body: value === undefined ? undefined : JSON.stringify(value) };
}

export const pathlyApi = {
  health: () => request<{ status: string; database: string }>("/health"),

  auth: {
    async register(input: { email: string; password: string; full_name: string }) {
      const tokens = await request<ApiTokens>("/auth/register", json("POST", input));
      session.save(tokens);
      return tokens;
    },
    async login(email: string, password: string) {
      const tokens = await request<ApiTokens>("/auth/login", json("POST", { email, password }));
      session.save(tokens);
      return tokens;
    },
    async google(idToken: string) {
      const tokens = await request<ApiTokens>("/auth/google", json("POST", { id_token: idToken }));
      session.save(tokens);
      return tokens;
    },
    async logout() {
      const refreshToken = session.getRefreshToken();
      try {
        if (refreshToken) await request<void>("/auth/logout", json("POST", { refresh_token: refreshToken }));
      } finally {
        session.clear();
      }
    },
    requestPasswordReset: (email: string) =>
      request<{ message: string }>("/auth/password-reset/request", json("POST", { email })),
    confirmPasswordReset: (token: string, newPassword: string) =>
      request<{ message: string }>(
        "/auth/password-reset/confirm",
        json("POST", { token, new_password: newPassword }),
      ),
    requestEmailVerification: () =>
      request<{ message: string }>("/auth/verify-email/request", json("POST")),
    confirmEmailVerification: (token: string) =>
      request<{ message: string }>("/auth/verify-email/confirm", json("POST", { token })),
    // Dev-only: reads the in-memory mail outbox instead of a real inbox. The backend
    // returns 404 outside development/test so this is a no-op against production.
    async devOutbox(email: string): Promise<ApiDevEmail[]> {
      try {
        return await request<ApiDevEmail[]>(`/auth/dev-outbox?email=${encodeURIComponent(email)}`);
      } catch {
        return [];
      }
    },
  },

  users: {
    me: () => request<ApiUser>("/users/me"),
    updateMe: (input: Partial<Pick<ApiUser, "full_name" | "avatar_url" | "university" | "course" | "study_goal">>) =>
      request<ApiUser>("/users/me", json("PATCH", input)),
  },

  subjects: {
    list: () => request<ApiSubject[]>("/subjects"),
    get: (id: string) => request<ApiSubject>(`/subjects/${id}`),
    create: (input: Pick<ApiSubject, "name" | "short_name" | "description" | "icon" | "tone">) =>
      request<ApiSubject>("/subjects", json("POST", input)),
    update: (id: string, input: Partial<Pick<ApiSubject, "name" | "short_name" | "description" | "icon" | "tone">>) =>
      request<ApiSubject>(`/subjects/${id}`, json("PATCH", input)),
    remove: (id: string) => request<void>(`/subjects/${id}`, { method: "DELETE" }),
  },

  materials: {
    list: (subjectId: string) => request<ApiMaterial[]>(`/subjects/${subjectId}/materials`),
    upload(subjectId: string, kind: MaterialKind, files: File[]) {
      const form = new FormData();
      form.set("kind", kind);
      files.forEach((file) => form.append("files", file));
      return request<ApiMaterial[]>(`/subjects/${subjectId}/materials`, { method: "POST", body: form });
    },
    process: (subjectId: string, materialId: string) =>
      request<ApiMaterial>(`/subjects/${subjectId}/materials/${materialId}/process`, { method: "POST" }),
    remove: (subjectId: string, materialId: string) =>
      request<void>(`/subjects/${subjectId}/materials/${materialId}`, { method: "DELETE" }),
  },

  learning: {
    getPath: (subjectId: string) => request<ApiLearningPath>(`/subjects/${subjectId}/learning-path`),
    generatePath: (subjectId: string, instructions: string[]) =>
      request<ApiLearningPath>(`/subjects/${subjectId}/learning-path/generate`, json("POST", { instructions })),
    completeLevel: (subjectId: string, levelId: string) =>
      request<ApiLearningPath>(`/subjects/${subjectId}/learning-path/levels/${levelId}/complete`, { method: "POST" }),
  },

  quizzes: {
    generate: (subjectId: string, input: { level_id?: string; count?: number; difficulty?: string }) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/quizzes/generate`, json("POST", input)),
    get: (subjectId: string, quizId: string) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/quizzes/${quizId}`),
    submit: (subjectId: string, quizId: string, answers: Record<string, string>) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/quizzes/${quizId}/submit`, json("POST", { answers })),
    hint: (subjectId: string, quizId: string, questionId: string) =>
      request<{ question_id: string; hint: string }>(`/subjects/${subjectId}/quizzes/${quizId}/questions/${questionId}/hint`),
  },

  study: {
    summary: (subjectId: string, topic?: string) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/study/summary`, json("POST", { topic: topic || null })),
    recommendations: (subjectId: string) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/study/recommendations`),
  },

  chat: {
    history: (subjectId: string) => request<Record<string, unknown>[]>(`/subjects/${subjectId}/chat`),
    send: (subjectId: string, message: string) =>
      request<Record<string, unknown>>(`/subjects/${subjectId}/chat`, json("POST", { message })),
  },

  progress: {
    summary: () => request<Record<string, unknown>>("/progress/summary"),
    history: () => request<Record<string, unknown>[]>("/progress/history"),
  },

  friends: {
    list: () => request<Record<string, unknown>[]>("/friends"),
    requests: () => request<Record<string, unknown>[]>("/friends/requests"),
    invite: (email: string) => request<Record<string, unknown>>("/friends/requests", json("POST", { email })),
    accept: (requestId: string) => request<Record<string, unknown>>(`/friends/requests/${requestId}/accept`, { method: "POST" }),
    decline: (requestId: string) => request<void>(`/friends/requests/${requestId}`, { method: "DELETE" }),
    remove: (userId: string) => request<void>(`/friends/${userId}`, { method: "DELETE" }),
  },
};
