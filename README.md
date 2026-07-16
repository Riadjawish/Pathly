# Pathly

Pathly turns a student's PDFs, notes, slides, practice problems, and past exams
into a source-grounded mastery journey. The interface is a playful course map;
the backend handles identity, materials, Gemini RAG, quizzes, progress, study
streaks, and friends.

## Architecture

```text
Next.js 16 web app
        │ typed REST client
        ▼
FastAPI /api/v1
   ├── PostgreSQL + SQLAlchemy + Alembic  (users, courses, maps, progress)
   ├── Local object storage               (S3-ready boundary)
   ├── document extraction + chunking     (PDF, DOCX, PPTX, TXT, Markdown)
   ├── Gemini generation + embeddings
   └── Chroma vector search               (source-grounded retrieval)
```

Gemini credentials stay on the API server. Browser clients receive short-lived
JWT access tokens; rotating refresh tokens are hashed in the database.

## Run the complete stack

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

- Email/password registration, Google ID-token sign-in, access/refresh/logout
- Profile, university, course, goals, and friends
- Subject CRUD with synchronized theme, icon, progress, and topic counts
- Secure multi-file uploads and background extraction/indexing
- Generated mastery paths, progress-based unlocks, boss levels, and study streaks
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
