from django.core.management import call_command
from django.core.management.base import BaseCommand

FIXTURES = ["items", "arena_events", "story", "questions"]


class Command(BaseCommand):
    help = "Load items, story lines and questions from content/fixtures. Safe to run again."

    def handle(self, *args, **options):
        call_command("loaddata", *FIXTURES, verbosity=options["verbosity"])
