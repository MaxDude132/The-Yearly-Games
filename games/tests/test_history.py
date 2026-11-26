"""History: finished Games are kept for the shared recap and the hall of fame (never rehearsals)."""

from django.core.management import call_command
from django.test import Client, TestCase

from games import services, undo
from games.models import Game, PastGame
from games.render import display_name
from games.tests.test_flow import setup_form


class HistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.client.get("/")
        self.game = Game.objects.get()

    def play_to_the_end(self, action="start", **extra):
        self.client.post(
            "/roster/", setup_form(self.game, lambda position: position < 3, action=action, **extra)
        )
        self.game.refresh_from_db()
        services.skip_to_the_end(self.game)
        self.game.refresh_from_db()

    def test_a_finished_games_is_kept_with_everyone_s_place(self):
        self.play_to_the_end()
        past = PastGame.objects.get()
        self.assertEqual(past.edition, 1)
        self.assertEqual(past.tributes.count(), 24)
        self.assertEqual(past.winner.name, display_name(self.game.winner))
        self.assertEqual(sorted(past.tributes.values_list("place", flat=True)), list(range(1, 25)))
        kills = sum(past.tributes.values_list("kills", flat=True))
        self.assertEqual(kills, sum(self.game.tributes.values_list("kills", flat=True)))

    def test_the_shared_recap_and_the_hall_of_fame(self):
        self.play_to_the_end()
        past = PastGame.objects.get()
        page = self.client.get("/").content.decode()
        self.assertIn(f"/recap/{past.share_code}/", page)
        shared = Client().get(f"/recap/{past.share_code}/").content.decode()  # anyone with the link
        self.assertIn(past.winner.name, shared)
        standings = shared[shared.index("data-standings") :]
        self.assertEqual(standings[: standings.index("</ol>")].count("<li"), 24)
        hall = self.client.get("/hall/").content.decode()
        self.assertIn(past.winner.name, hall)
        self.assertIn("#1", hall)
        self.assertEqual(Client().get("/recap/nope/").status_code, 404)

    def test_the_edition_follows_the_past_victors(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        self.play_to_the_end(**{"victor-name-0": "Alex", "victor-edition-0": "5"})
        self.assertEqual(PastGame.objects.get().edition, 6)
        hall = self.client.get("/hall/").content.decode()
        self.assertLess(hall.index("Alex"), hall.index("#6"))  # the 5th Games' victor comes first

    def test_a_rehearsal_is_not_kept(self):
        self.play_to_the_end(action="rehearse")
        self.assertIsNotNone(self.game.winner_id)
        self.assertFalse(PastGame.objects.exists())

    def test_undoing_the_final_round_forgets_the_games(self):
        self.play_to_the_end()
        undo.undo(self.game)
        self.game.refresh_from_db()
        self.assertIsNone(self.game.winner_id)
        self.assertFalse(PastGame.objects.exists())
