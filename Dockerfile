# The production image (Railway builds it from this file; see .railway/railway.py).
# Two stages: "build" installs the dependencies and builds the CSS, translations and static files;
# the final image only gets the results, without build tools or the Tailwind binary.

# ---------- build ----------
FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

# gettext: compiles the French interface text (.po to .mo).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    TAILWINDCSS_BIN_DIR=/tmp/tailwind

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Production settings refuse to load without a secret, a Postgres URL and a photo bucket. These values
# are only used to build files; nothing connects to the database or the bucket here.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-only DATABASE_URL=postgres://build@localhost/build \
    AWS_STORAGE_BUCKET_NAME=build-only \
    sh -c "python manage.py tailwind install \
        && python manage.py tailwind build \
        && python manage.py compilemessages --ignore=.venv \
        && python manage.py collectstatic --noinput"

# ---------- run ----------
FROM python:3.13-slim

# The app runs as this user. The code stays owned by root, so the app cannot change it.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_DEBUG=0 \
    PORT=8000

WORKDIR /app
COPY --from=build /app /app

# Nothing is written to disk at run time: data is in Postgres, photos in S3.
USER app

EXPOSE 8000
CMD ["gunicorn"]
