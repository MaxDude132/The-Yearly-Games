"""Production must run on Postgres; local development stays on SQLite."""

import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from games.models import Game

READ_ENGINE = "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"


def load_settings(**environment):
    """Imports the settings in a fresh Python with the given environment. Prints the database engine."""
    return run_python(f"import django; django.setup(); {READ_ENGINE}", **environment)


def run_python(script, **environment):
    """Runs a Python script in a fresh process with the given environment. Returns the process result."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("DJANGO_", "DATABASE_"))}
    env.update(DJANGO_SETTINGS_MODULE="config.settings", **environment)
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        cwd=settings.BASE_DIR,
        check=False,
    )


class DatabaseSettingsTests(SimpleTestCase):
    def test_local_uses_sqlite(self):
        result = load_settings()
        self.assertEqual(result.stdout.strip(), "django.db.backends.sqlite3", result.stderr)

    def test_database_url_selects_postgres(self):
        result = load_settings(DATABASE_URL="postgres://user:secret@db.example:5432/games")
        self.assertEqual(result.stdout.strip(), "django.db.backends.postgresql", result.stderr)

    def test_production_refuses_to_start_without_postgres(self):
        result = load_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="test")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production needs Postgres", result.stderr)

    def test_production_starts_with_postgres(self):
        result = load_settings(
            DJANGO_DEBUG="0", DJANGO_SECRET_KEY="test", DATABASE_URL="postgres://user:secret@db.example/games"
        )
        self.assertEqual(result.stdout.strip(), "django.db.backends.postgresql", result.stderr)


class RailwaySettingsTests(SimpleTestCase):
    def test_the_railway_domain_and_health_check_host_are_allowed(self):
        env = {
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "test",
            "DATABASE_URL": "postgres://user:secret@db.example/games",
            "RAILWAY_PUBLIC_DOMAIN": "yearly.up.railway.app",
            "RAILWAY_ENVIRONMENT_NAME": "production",
        }
        script = (
            "import django; django.setup(); from django.conf import settings as s; "
            "print(s.ALLOWED_HOSTS); print(s.CSRF_TRUSTED_ORIGINS); print(s.SECURE_SSL_REDIRECT)"
        )
        result = run_python(script, **env)
        hosts, origins, redirect = result.stdout.splitlines()
        self.assertEqual(hosts, "['yearly.up.railway.app', 'healthcheck.railway.app']", result.stderr)
        self.assertEqual(origins, "['https://yearly.up.railway.app']")
        self.assertEqual(redirect, "True")


class HealthTests(TestCase):
    def test_health_answers_without_starting_a_game(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertFalse(Game.objects.exists())
        self.assertNotIn("sessionid", response.cookies)
