"""Django settings for The Yearly Games.

Local development needs no environment variables (SQLite, DEBUG on).
Production (Railway, see Dockerfile and railway.toml) sets DJANGO_DEBUG=0, DJANGO_SECRET_KEY and DATABASE_URL.
"""

import importlib.util
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# The dev key is only accepted while DEBUG is on.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is not 1.")
    SECRET_KEY = "dev-only-key-not-for-production"

# ---------- hosts ----------
# Railway sets RAILWAY_PUBLIC_DOMAIN (e.g. yearly-games.up.railway.app) and checks health
# from healthcheck.railway.app. DJANGO_ALLOWED_HOSTS adds more, e.g. a custom domain.
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host]
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS += [RAILWAY_PUBLIC_DOMAIN]
if os.environ.get("RAILWAY_ENVIRONMENT_NAME"):
    ALLOWED_HOSTS += ["healthcheck.railway.app"]
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host != "healthcheck.railway.app"]

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "tailwind",
    "theme",
    "content",
    "games",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Reload the browser when a template or the CSS changes (dev only; installed with the dev dependencies).
BROWSER_RELOAD = DEBUG and importlib.util.find_spec("django_browser_reload") is not None
if BROWSER_RELOAD:
    INSTALLED_APPS += ["django_browser_reload"]
    MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------- database ----------
# Local: SQLite (db.sqlite3), nothing to set up.
# Production: Postgres, from DATABASE_URL (postgres://user:password@host:5432/name).
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

if not DEBUG and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise RuntimeError("Production needs Postgres: set DATABASE_URL to a postgres:// URL.")

# ---------- languages ----------
# The first language is the fallback for any content that has no translation yet.
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"
LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------- sessions: a game belongs to the browser that started it ----------
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_COOKIE_SAMESITE = "Lax"

# ---------- HTTPS (production) ----------
# DJANGO_HTTPS=0 only for running the production image locally over plain HTTP (make docker-run).
HTTPS = not DEBUG and os.environ.get("DJANGO_HTTPS", "1") == "1"
if not DEBUG:
    # Railway ends HTTPS at its proxy and forwards plain HTTP with this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # Railway's health check calls over plain HTTP
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------- Tailwind (django-tailwind, standalone binary: no Node needed) ----------
TAILWIND_APP_NAME = "theme"
TAILWIND_USE_STANDALONE_BINARY = True
TAILWIND_STANDALONE_BINARY_VERSION = "v4.3.5"

# ---------- files ----------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Production: WhiteNoise serves the collected files with hashed names and compression.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
# Uploaded photos. On Railway this is a volume (see railway.toml), or they vanish on each deploy.
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
# Photos are shrunk on upload; this only limits what a phone camera may send.
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024

# ---------- production logs go to the console (Railway collects them) ----------
if not DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
