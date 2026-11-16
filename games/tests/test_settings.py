"""Production runs on Postgres with photos in S3; local development uses SQLite and media/."""

import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from games.models import Game

PRODUCTION = {
    "DJANGO_DEBUG": "0",
    "DJANGO_SECRET_KEY": "test",
    "DATABASE_URL": "postgres://user:secret@db.example/games",
    "AWS_STORAGE_BUCKET_NAME": "photos",
}


def read_settings(*names, **environment):
    """Loads the settings in a fresh Python with the given environment.
    Returns (process result, {name: repr of the value})."""
    script = "import django; django.setup(); from django.conf import settings as s; " + "; ".join(
        f"print(repr(s.{name}))" for name in names
    )
    ours = ("DJANGO_", "DATABASE_", "AWS_")
    env = {key: value for key, value in os.environ.items() if not key.startswith(ours)}
    env.update(DJANGO_SETTINGS_MODULE="config.settings", **environment)
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        cwd=settings.BASE_DIR,
        check=False,
    )
    return result, dict(zip(names, result.stdout.splitlines(), strict=False))


class DatabaseSettingsTests(SimpleTestCase):
    ENGINE = "DATABASES['default']['ENGINE']"

    def test_local_uses_sqlite(self):
        result, values = read_settings(self.ENGINE)
        self.assertEqual(values.get(self.ENGINE), "'django.db.backends.sqlite3'", result.stderr)

    def test_database_url_selects_postgres(self):
        result, values = read_settings(
            self.ENGINE, DATABASE_URL="postgres://user:secret@db.example:5432/games"
        )
        self.assertEqual(values.get(self.ENGINE), "'django.db.backends.postgresql'", result.stderr)

    def test_production_refuses_to_start_without_postgres(self):
        result, _ = read_settings(self.ENGINE, **{**PRODUCTION, "DATABASE_URL": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production needs Postgres", result.stderr)

    def test_production_starts_with_postgres(self):
        result, values = read_settings(self.ENGINE, **PRODUCTION)
        self.assertEqual(values.get(self.ENGINE), "'django.db.backends.postgresql'", result.stderr)


class PhotoStorageSettingsTests(SimpleTestCase):
    BACKEND = "STORAGES['default']['BACKEND']"
    OPTIONS = "STORAGES['default']['OPTIONS']"

    def test_local_photos_go_to_the_media_folder(self):
        result, values = read_settings(self.BACKEND)
        local = "'django.core.files.storage.FileSystemStorage'"
        self.assertEqual(values.get(self.BACKEND), local, result.stderr)

    def test_a_bucket_selects_a_private_s3_storage(self):
        result, values = read_settings(
            self.BACKEND,
            self.OPTIONS,
            AWS_STORAGE_BUCKET_NAME="photos",
            AWS_S3_REGION_NAME="auto",
            AWS_S3_ENDPOINT_URL="https://t3.storageapi.dev",
            AWS_S3_ADDRESSING_STYLE="virtual",
        )
        self.assertEqual(values.get(self.BACKEND), "'storages.backends.s3.S3Storage'", result.stderr)
        options = values[self.OPTIONS]
        self.assertIn("'bucket_name': 'photos'", options)
        self.assertIn("'region_name': 'auto'", options)
        self.assertIn("'endpoint_url': 'https://t3.storageapi.dev'", options)
        self.assertIn("'addressing_style': 'virtual'", options)
        self.assertIn("'signature_version': 's3v4'", options)
        self.assertNotIn("default_acl", options)  # private: the page uses signed URLs

    def test_production_refuses_to_start_without_a_bucket(self):
        result, _ = read_settings(self.BACKEND, **{**PRODUCTION, "AWS_STORAGE_BUCKET_NAME": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production stores photos in S3", result.stderr)


class RailwaySettingsTests(SimpleTestCase):
    def test_the_railway_domain_and_health_check_host_are_allowed(self):
        result, values = read_settings(
            "ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
            "SECURE_SSL_REDIRECT",
            **PRODUCTION,
            RAILWAY_PUBLIC_DOMAIN="yearly.up.railway.app",
            RAILWAY_ENVIRONMENT_NAME="production",
        )
        hosts = "['yearly.up.railway.app', 'healthcheck.railway.app']"
        self.assertEqual(values.get("ALLOWED_HOSTS"), hosts, result.stderr)
        self.assertEqual(values["CSRF_TRUSTED_ORIGINS"], "['https://yearly.up.railway.app']")
        self.assertEqual(values["SECURE_SSL_REDIRECT"], "True")


class HealthTests(TestCase):
    def test_health_answers_without_starting_a_game(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertFalse(Game.objects.exists())
        self.assertNotIn("sessionid", response.cookies)


class CustomDomainSettingsTests(SimpleTestCase):
    def test_the_custom_domain_is_allowed_and_trusted_for_https_forms(self):
        domain = "yearlygames.maximetoussaint.com"
        result, values = read_settings(
            "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS", **PRODUCTION, DJANGO_ALLOWED_HOSTS=domain
        )
        self.assertEqual(values.get("ALLOWED_HOSTS"), f"['{domain}']", result.stderr)
        self.assertEqual(values["CSRF_TRUSTED_ORIGINS"], f"['https://{domain}']")
