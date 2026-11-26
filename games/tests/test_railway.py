"""The Railway Infrastructure as Code file compiles to the settings production needs.

Evaluated offline, the same way the Railway CLI loads it: nothing here talks to Railway.
"""

import importlib.util

from django.conf import settings
from django.test import SimpleTestCase
from railway_sdk import create_railway_context

CONFIG = settings.BASE_DIR / ".railway" / "railway.py"
# The bucket variable each setting reads (see config/settings.py).
BUCKET_VARIABLES = {
    "AWS_STORAGE_BUCKET_NAME": "BUCKET",
    "AWS_ACCESS_KEY_ID": "ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY": "SECRET_ACCESS_KEY",
    "AWS_S3_REGION_NAME": "REGION",
    "AWS_S3_ENDPOINT_URL": "ENDPOINT",
}


def compile_config(environment="production"):
    spec = importlib.util.spec_from_file_location("railway_config", CONFIG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    graph = module.main(create_railway_context(environment=environment)).to_graph()
    return graph, {resource["address"]: resource for resource in graph["resources"]}


class RailwayConfigTests(SimpleTestCase):
    def setUp(self):
        self.graph, self.resources = compile_config()
        self.web = self.resources["service.web"]

    def test_the_project_has_the_web_service_postgres_and_the_photo_bucket(self):
        self.assertEqual(self.graph["name"], "the-yearly-games")
        names = {"service.web", "database.postgres", "volume.postgres-volume", "bucket.photos"}
        self.assertEqual(set(self.resources), names)
        self.assertEqual(self.resources["database.postgres"]["engine"], "postgres")
        self.assertIn(self.resources["bucket.photos"]["config"]["region"], {"sjc", "iad", "ams", "sin"})

    def test_web_builds_the_dockerfile_from_the_main_branch(self):
        source = {"type": "github", "repo": "MaxDude132/The-Yearly-Games", "branch": "main"}
        self.assertEqual(self.web["source"], source)
        build = {"buildEnvironment": "V3", "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"}
        self.assertEqual(self.web["build"], build)
        self.assertTrue((settings.BASE_DIR / "Dockerfile").exists())

    def test_web_deploys_like_production_needs(self):
        deploy = self.web["deploy"]
        self.assertEqual(deploy["preDeployCommand"], ["sh scripts/predeploy.sh"])
        self.assertTrue((settings.BASE_DIR / "scripts" / "predeploy.sh").exists())
        self.assertEqual(deploy["healthcheckPath"], "/health/")

    def test_the_database_and_bucket_credentials_are_references(self):
        variables = self.web["variables"]
        reference = {"type": "reference", "resource": "database.postgres", "output": "DATABASE_URL"}
        self.assertEqual(variables["DATABASE_URL"], reference)
        for name, output in BUCKET_VARIABLES.items():
            expected = {"type": "reference", "resource": "bucket.photos", "output": output}
            self.assertEqual(variables[name], expected, name)
        self.assertEqual(variables["AWS_S3_ADDRESSING_STYLE"], {"type": "literal", "value": "virtual"})

    def test_the_only_secret_stays_in_railway(self):
        variables = self.web["variables"]
        self.assertEqual(variables["DJANGO_SECRET_KEY"], {"type": "preserve"})
        literals = {name for name, variable in variables.items() if variable["type"] == "literal"}
        # Only plain settings are written in the file, never a secret value.
        self.assertEqual(literals, {"AWS_S3_ADDRESSING_STYLE", "PORT", "DJANGO_ALLOWED_HOSTS"})

    def test_the_site_allows_its_domain_and_binds_the_port(self):
        domain = "yearlygames.maximetoussaint.com"
        # The domain was added in the dashboard and pulled into the file.
        self.assertEqual(self.web["networking"]["customDomains"], {domain: {"port": 8000}})
        variables = self.web["variables"]
        self.assertEqual(variables["DJANGO_ALLOWED_HOSTS"], {"type": "literal", "value": domain})
        # The domain routes to the port gunicorn binds (gunicorn.conf.py reads PORT).
        self.assertEqual(variables["PORT"], {"type": "literal", "value": "8000"})
