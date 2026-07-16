# Pathly

**AI study platform that turns your course material into a Duolingo-style mastery path.**

🔗 **Live demo:** https://pathly-drab.vercel.app
📘 **API docs:** https://pathly-api-production.up.railway.app/docs

Upload lecture slides, notes, past exams, and practice problems for a course.
Pathly reads all of it as one syllabus, works out the prerequisite chain
between topics — teaching foundational concepts the material assumes but
never explains — and builds a level-by-level path from zero knowledge to
being ready for the hardest questions in your own exam material. Each level
mixes concise notes, worked examples, and a mini-quiz gating progress to the
next one.

## Features

- **Full auth**: email/password, Google Sign-In, password reset, email verification
- **AI-generated mastery paths**: Gemini reads your uploaded material via RAG (chunking + embeddings + Chroma vector search), decides how many levels a course actually needs, and sequences them by prerequisite
- **Source-grounded content** with the freedom to teach real prerequisites your material doesn't cover, so nothing has a gap
- **Mastery gating**: a level only unlocks the next one once its mini-quiz is answered correctly
- **AI tutor chat and standalone practice quizzes**, both grounded in your uploaded material with cited sources
- **Progress tracking** per subject, with study streaks

## Tech stack

**Frontend** — Next.js 16 (App Router), TypeScript, React
**Backend** — FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL
**AI/RAG** — Google Gemini (generation + embeddings), ChromaDB vector search
**Infra** — Docker, deployed on Vercel (web) + Railway (API + Postgres)

## Architecture

```text
Next.js 16 web app
        │ typed REST client
        ▼
FastAPI /api/v1
   ├── PostgreSQL + SQLAlchemy + Alembic  (users, subjects, mastery paths, progress)
   ├── Local object storage               (S3-ready boundary)
   ├── document extraction + chunking     (PDF, DOCX, PPTX, TXT, Markdown)
   ├── Gemini generation + embeddings
   └── Chroma vector search               (source-grounded retrieval)
```

Gemini credentials stay on the API server. Browser clients receive short-lived
JWT access tokens; rotating refresh tokens are hashed in the database.

## Run it locally

The easiest development setup uses Docker Desktop:

```bash
cp .env.example .env
# Fill SECRET_KEY, GEMINI_API_KEY, and GOOGLE_CLIENT_ID.
docker compose up --build
```

- Web app: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/v1/health>

For running PostgreSQL, FastAPI, and Next.js separately, see
[BACKEND_SETUP.md](BACKEND_SETUP.md).

## Development checks

```bash
npm run lint
npm run build

cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
```

## API coverage

- Email/password registration, Google ID-token sign-in, password reset, email verification, access/refresh/logout
- Profile, university, course, goals, and friends
- Subject CRUD with synchronized theme, icon, progress, and topic counts
- Secure multi-file uploads and background extraction/indexing
- AI-generated mastery paths with prerequisite sequencing, mastery-gated levels, and boss levels
- Source-grounded summaries, tutor chat, quizzes, grading, hints, and recommendations
- Progress summary/history with source and quiz records

The interactive OpenAPI page documents all request and response shapes.

## Repository layout

```text
app/                 Next.js App Router frontend
backend/app/         FastAPI routes, models, and services
backend/alembic/     database migrations
backend/tests/       API, auth, storage, and chunking tests
docker-compose.yml   web + API + PostgreSQL development stack
```
