FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system pathly && adduser --system --ingroup pathly pathly

COPY pyproject.toml ./
COPY README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN python -m pip install --upgrade pip && python -m pip install .

RUN mkdir -p /data/uploads /data/chroma && chown -R pathly:pathly /app /data
USER pathly

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
