"""Undo (taking back the last answer, the round in progress, or the last round) and rehearsals."""

from django.core.management import call_command
from django.test import TestCase

from games import services, undo
from games.models import Game
from games.tests.test_flow import setup_form


def snapshot(game):
    """Everything a round changes, to compare a game before and after Undo."""
    game.refresh_from_db()
    return {
        "round": game.round,
        "winner": game.winner_id,
        "log": list(game.log.values_list("style", "line_id", "a_id", "b_id", "item_id", "n")),
        "tributes": list(game.tributes.values_list("alive", "wounded", "alliance", "kills", "goal")),
        "items": sorted(game.tributes.values_list("pk", "carried__item_id")),
        "bets": list(game.bets.values_list("round", "points")),
    }


class UndoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.client.get("/")
        self.game = Game.objects.get()
        # Half the tributes in the room, so rounds ask questions.
        self.client.post(
            "/roster/", setup_form(self.game, lambda position: position % 2 == 0, action="start")
        )
        self.game.refresh_from_db()

    def play_round(self):
        """Plays one round, answering every question with the first option."""
        services.start_round(self.game)
        while services.waiting_decision(self.game) is not None:
            services.answer_decision(self.game, services.current_answers(self.game).count(), 0)
        self.game.refresh_from_db()

    def test_undoing_a_round_gives_back_the_game_as_it_was(self):
        for _ in range(4):
            self.play_round()
        before = snapshot(self.game)
        self.play_round()
        self.assertNotEqual(snapshot(self.game), before)
        self.assertTrue(undo.undo(self.game))
        self.assertEqual(snapshot(self.game), before)

    def test_presence_is_replayed_as_it_was_and_kept_as_it_is(self):
        self.play_round()
        self.play_round()
        before = snapshot(self.game)
        self.game.tributes.update(present=True)  # everyone arrived after round 2
        self.play_round()
        undo.undo(self.game)
        self.assertEqual(snapshot(self.game), before)
        self.assertFalse(self.game.tributes.filter(present=False).exists())

    def test_undo_takes_back_the_last_answer(self):
        self.play_round()
        services.start_round(self.game)
        self.assertIsNotNone(services.waiting_decision(self.game), "the round should ask a question")
        services.answer_decision(self.game, 0, 0)
        answered = services.current_answers(self.game).count()
        undo.undo(self.game)
        self.assertEqual(services.current_answers(self.game).count(), answered - 1)
        self.assertIsNotNone(self.game.round_seed)

    def test_undo_calls_off_a_round_nobody_answered(self):
        services.start_round(self.game)  # the Bloodbath asks the players in the room
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.round_seed)
        undo.undo(self.game)
        self.game.refresh_from_db()
        self.assertIsNone(self.game.round_seed)
        self.assertFalse(undo.can_undo(self.game))

    def test_the_undo_button_on_the_page(self):
        self.play_round()
        self.assertIn("Undo", self.client.get("/").content.decode())
        self.client.post("/undo/")
        self.game.refresh_from_db()
        self.assertEqual(self.game.round, 0)


class RehearsalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.client.get("/")
        self.game = Game.objects.get()

    def test_a_rehearsal_skips_to_the_end_and_frees_the_phones_on_quit(self):
        self.client.post("/roster/", setup_form(self.game, action="rehearse"))
        self.game.refresh_from_db()
        self.assertTrue(self.game.rehearsal)
        self.game.tributes.filter(position=0).update(phone_token="abc")
        self.assertIn("Rehearsal: nothing here counts", self.client.get("/").content.decode())
        self.client.post("/skip/")
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.winner_id)
        self.assertIn("data-recap", self.client.get("/").content.decode())
        self.client.post("/quit/")
        self.game.refresh_from_db()
        self.assertFalse(self.game.rehearsal)
        self.assertFalse(self.game.tributes.exclude(phone_token="").exists())

    def test_skip_does_nothing_in_a_real_game(self):
        self.client.post("/roster/", setup_form(self.game, action="start"))
        self.client.post("/skip/")
        self.game.refresh_from_db()
        self.assertEqual(self.game.round, 0)
