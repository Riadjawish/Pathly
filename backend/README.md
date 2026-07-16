# Pathly API

FastAPI backend for Pathly. It provides JWT sessions, Google sign-in, subjects,
learning-material uploads, Gemini + Chroma RAG, generated mastery paths, quizzes,
study chat, friends, progress, and study streaks.

The complete local and Docker instructions live in the project root at
`BACKEND_SETUP.md`.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs> for the interactive API reference.
