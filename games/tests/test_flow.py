"""The pages, end to end: setup, rounds, questions that pause a round, languages, photos."""

import re
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from PIL import Image

from games import services
from games.models import Answer, Bet, Game, LogEntry, Tribute

MEDIA_ROOT = tempfile.mkdtemp()


def without_tokens(page):
    """The page without its CSRF tokens, which change on every request."""
    return re.sub(r'(value|content)="[A-Za-z0-9]{32,}"', "", page)


def setup_form(game, here=lambda position: True, **extra):
    """The fields the setup form sends."""
    fields = {}
    for tribute in game.tributes.all():
        fields[f"name-{tribute.position}"] = f"Name {tribute.position + 1}"
        if here(tribute.position):
            fields[f"here-{tribute.position}"] = "on"
    return {**fields, **extra}


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class FlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client.get("/")  # starts the session and the game
        self.game = Game.objects.get()

    def start(self, here=lambda position: True):
        self.client.post("/roster/", setup_form(self.game, here, action="start"))
        self.game.refresh_from_db()

    def play_until_question_or_end(self):
        """Presses Continue until a question is open or the game is over. Returns the page."""
        for _ in range(100):
            # Look first: once there is a winner, the main button means "New game".
            page = self.client.get("/").content.decode()
            if 'role="dialog"' in page or "New game" in page:
                return page
            self.client.post("/round/next/")
        self.fail("the game did not end")

    # ---------- setup ----------

    def test_the_first_visit_shows_24_blank_tributes(self):
        page = self.client.get("/").content.decode()
        self.assertEqual(self.game.status, Game.Status.SETUP)
        self.assertEqual(self.game.tributes.count(), 24)
        self.assertIn("Start the Games", page)
        self.assertIn('placeholder="Tribute 24"', page)

    def test_names_presence_add_and_remove(self):
        self.client.post("/roster/", setup_form(self.game, lambda position: position < 2, action="add"))
        self.assertEqual(self.game.tributes.count(), 25)
        self.assertEqual(
            list(self.game.tributes.filter(present=True).values_list("position", flat=True)), [0, 1, 24]
        )  # a new tribute is in the room
        self.assertEqual(self.game.tributes.get(position=3).name, "Name 4")

        self.client.post("/roster/", setup_form(self.game, action="remove-0"))
        self.assertEqual(self.game.tributes.count(), 24)
        self.assertEqual(list(self.game.tributes.values_list("position", flat=True)), list(range(24)))
        self.assertEqual(self.game.tributes.get(position=0).name, "Name 2")  # the others moved up

    def test_a_game_needs_two_tributes(self):
        for _ in range(23):
            self.client.post("/roster/", setup_form(self.game, action="remove-0"))
        self.client.post("/roster/", setup_form(self.game, action="start"))
        self.game.refresh_from_db()
        self.assertEqual(self.game.tributes.count(), 1)
        self.assertEqual(self.game.status, Game.Status.SETUP)

    def test_a_photo_becomes_a_small_square_and_a_bad_file_is_ignored(self):
        buffer = BytesIO()
        Image.new("RGB", (400, 300), "red").save(buffer, "PNG")
        photo = SimpleUploadedFile("me.png", buffer.getvalue(), content_type="image/png")
        self.client.post("/roster/", setup_form(self.game, action="save", **{"photo-0": photo}))
        first = self.game.tributes.get(position=0)
        self.assertTrue(first.photo)
        with Image.open(first.photo.path) as saved:
            self.assertEqual(saved.size, (192, 192))
            self.assertEqual(saved.format, "JPEG")

        notes = SimpleUploadedFile("notes.png", b"not an image", content_type="image/png")
        self.client.post("/roster/", setup_form(self.game, action="save", **{"photo-0": notes}))
        self.assertEqual(self.game.tributes.get(position=0).photo.name, first.photo.name)

    # ---------- playing ----------

    def test_a_game_with_nobody_in_the_room_plays_to_a_winner_and_can_start_again(self):
        self.start(here=lambda position: False)
        self.assertEqual(self.game.status, Game.Status.PLAYING)
        page = self.client.get("/").content.decode()
        self.assertIn("Sound the gong", page)

        page = self.play_until_question_or_end()
        self.assertNotIn('role="dialog"', page)
        self.assertIn("New game", page)
        self.assertIn("wins the Games", page)
        self.game.refresh_from_db()
        self.assertEqual(self.game.tributes.filter(alive=True).count(), 1)
        self.assertEqual(self.game.winner.alive, True)
        self.assertEqual(self.game.log.filter(style="win").count(), 1)

        self.client.post("/round/next/")  # "New game"
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.SETUP)
        self.assertEqual(self.game.log.count(), 0)
        self.assertEqual(self.game.tributes.get(position=5).name, "Name 6")  # the roster stays
        self.assertEqual(self.game.tributes.filter(alive=True).count(), 24)

    def test_a_question_pauses_the_round_until_the_player_answers(self):
        self.start(here=lambda position: position == 0 or position == 1)
        self.client.post("/round/next/")
        page = self.client.get("/").content.decode()
        self.assertIn('role="dialog"', page)
        self.assertIn("The gong sounds.", page)
        self.assertIn("Sprint for the weapons", page)
        self.assertIn("Decision for", page)
        self.assertIn("data-decision-facts", page)
        self.assertIn("Healthy", page)
        self.assertIn("Carries nothing", page)
        self.assertIn("Tributes left: 24", page)
        self.assertRegex(page, r"<button[^>]*btn-main[^>]*disabled")

        # Nothing of the unfinished round is saved, and showing it again changes nothing.
        self.game.refresh_from_db()
        self.assertEqual(self.game.log.count(), 0)
        self.assertIsNotNone(self.game.round_seed)
        self.assertEqual(without_tokens(self.client.get("/").content.decode()), without_tokens(page))

        question = re.search(r'<div [^>]*id="decision-name"[^>]*>(.*?)</div>', page, re.S).group(1)
        self.client.post("/decision/", {"position": 0, "choice": 0})
        self.assertEqual(Answer.objects.filter(game=self.game).count(), 1)
        next_page = self.client.get("/").content.decode()
        self.assertIn('role="dialog"', next_page)  # the other player in the room is asked next
        self.assertNotEqual(next_page, page)
        self.assertIsNotNone(question)

    def test_an_old_or_wrong_answer_is_ignored(self):
        self.start(here=lambda position: position == 0)
        self.client.post("/round/next/")
        self.client.post("/decision/", {"position": 5, "choice": 0})  # not the question that is open
        self.client.post("/decision/", {"position": 0, "choice": 99})  # not an option
        self.client.post("/decision/", {"position": 0, "choice": "x"})
        self.assertEqual(Answer.objects.count(), 0)
        self.client.post("/decision/", {"position": 0, "choice": 2})
        self.client.post("/decision/", {"position": 0, "choice": 2})  # a double tap
        self.game.refresh_from_db()
        self.assertEqual(self.game.round, 1)  # the Bloodbath finished, with one question
        self.assertEqual(Answer.objects.count(), 1)  # one answer, the double tap is ignored (kept for Undo)
        self.assertGreater(self.game.log.count(), 10)

    def test_every_question_can_be_answered_to_the_end(self):
        self.start(here=lambda position: position % 3 == 0)
        for _ in range(400):
            page = self.play_until_question_or_end()
            if "New game" in page:
                break
            options = re.findall(r'name="choice" value="(\d+)"', page)
            position = re.search(r'name="position" value="(\d+)"', page).group(1)
            self.client.post("/decision/", {"position": position, "choice": options[-1]})
        else:
            self.fail("the game did not end")
        self.assertIn("wins the Games", self.client.get("/").content.decode())

    def test_the_story_is_stored_without_words_and_read_in_the_viewers_language(self):
        self.start(here=lambda position: False)
        self.client.post("/round/next/")
        self.assertTrue(LogEntry.objects.filter(game=self.game).exists())
        english = self.client.get("/").content.decode()
        self.assertIn("The Bloodbath", english)
        self.assertIn('<html lang="en"', english)

        self.client.post("/language/", {"language": "fr", "next": "/"})
        french = self.client.get("/").content.decode()
        self.assertIn("Le bain de sang", french)
        self.assertIn('<html lang="fr"', french)
        self.assertIn("Sonner le gong".replace("Sonner le gong", "Continuer"), french)

    def test_names_are_shown_in_bold_and_escaped(self):
        fields = setup_form(self.game, lambda position: False, action="start")
        fields["name-0"] = "<script>x</script>"
        self.client.post("/roster/", fields)
        self.client.post("/round/next/")
        page = self.client.get("/").content.decode()
        self.assertNotIn("<script>x</script>", page)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", page)

    def test_the_here_tick_changes_between_rounds_but_not_during_a_question(self):
        self.start(here=lambda position: position == 0)
        self.assertEqual(self.client.post("/tributes/3/present/", {"present": "1"}).status_code, 204)
        self.assertTrue(Tribute.objects.get(game=self.game, position=3).present)
        self.client.post("/round/next/")
        self.assertEqual(self.client.post("/tributes/3/present/", {"present": "0"}).status_code, 409)
        self.assertTrue(Tribute.objects.get(game=self.game, position=3).present)

    def test_quitting_returns_to_the_setup_and_keeps_the_roster(self):
        self.start()
        self.client.post("/round/next/")
        self.assertContains(self.client.get("/?confirm_quit=1"), "Really quit?")
        self.client.post("/quit/")
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.SETUP)
        self.assertEqual(self.game.round, 0)
        self.assertIsNone(self.game.round_seed)
        self.assertEqual(self.game.log.count(), 0)
        self.assertEqual(self.game.tributes.get(position=1).name, "Name 2")

    def test_each_browser_has_its_own_game(self):
        other = Client()
        other.get("/")
        self.assertEqual(Game.objects.count(), 2)
        self.start(here=lambda position: False)
        self.assertContains(other.get("/"), "Start the Games")

    def test_the_game_survives_a_reload_of_the_services(self):
        """The saved game is all in the database: a fresh load continues where it stopped."""
        self.start(here=lambda position: False)
        self.client.post("/round/next/")
        self.client.post("/round/next/")
        game = Game.objects.get()
        catalogue = services.load_catalogue()
        arena = services.load_arena(game, catalogue, None, None)
        self.assertEqual(arena.round, 2)
        self.assertEqual(len(arena.log), game.log.count())
        self.assertEqual(len(arena.living()), game.tributes.filter(alive=True).count())

    # ---------- votes, past victors, bets and the recap ----------
    def test_the_setup_saves_the_vote_settings(self):
        self.client.post("/roster/", setup_form(self.game, action="save", voters="everyone"))
        self.game.refresh_from_db()
        self.assertEqual(self.game.voters, Game.Voters.EVERYONE)
        self.assertFalse(self.game.no_conflict_votes)  # the box was not ticked
        self.assertRegex(self.client.get("/").content.decode(), r'<option value="everyone" selected>')
        self.client.post(
            "/roster/", setup_form(self.game, action="save", voters="hackers", no_conflict_votes="on")
        )
        self.game.refresh_from_db()
        self.assertEqual(self.game.voters, Game.Voters.EVERYONE)  # an unknown value is ignored
        self.assertTrue(self.game.no_conflict_votes)

    def test_past_victors_are_added_saved_and_removed_apart_from_the_tributes(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        self.assertEqual(self.game.victors.count(), 2)
        self.assertEqual(self.game.tributes.count(), 24)  # victors are not tributes
        fields = {
            "victor-name-0": "Alex", "victor-edition-0": "2", "victor-year-0": "2023", "victor-here-0": "on",
            "victor-name-1": "Sam", "victor-edition-1": "0", "victor-year-1": "nope",
        }  # fmt: skip
        self.client.post("/roster/", setup_form(self.game, action="save", **fields))
        alex, sam = self.game.victors.order_by("position")
        self.assertEqual((alex.name, alex.edition, alex.year, alex.present), ("Alex", 2, 2023, True))
        self.assertEqual((sam.name, sam.edition, sam.year, sam.present), ("Sam", None, None, False))
        page = self.client.get("/").content.decode()
        self.assertIn('value="Alex"', page)
        self.assertIn('value="2023"', page)
        self.client.post("/roster/", setup_form(self.game, action="remove-victor-0", **fields))
        self.assertEqual([v.name for v in self.game.victors.all()], ["Sam"])
        self.assertEqual(self.game.victors.get().position, 0)

    def test_a_past_victor_is_shown_on_the_board_and_can_leave_the_room(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        self.client.post(
            "/roster/",
            setup_form(
                self.game,
                action="start",
                **{
                    "victor-name-0": "Alex",
                    "victor-edition-0": "1",
                    "victor-year-0": "2021",
                    "victor-here-0": "on",
                },
            ),
        )
        page = self.client.get("/").content.decode()
        self.assertIn("Alex", page)
        self.assertIn("2021", page)
        self.assertIn("1st Games", page)
        self.assertEqual(self.client.post("/victors/0/present/", {"present": "0"}).status_code, 204)
        self.assertFalse(self.game.victors.get().present)
        self.assertEqual(self.client.post("/victors/5/present/", {"present": "1"}).status_code, 404)

    def test_every_reputation_tag_has_a_label_on_the_board(self):
        from games.engine.state import BETRAYER, FEARED, HIDDEN, MERCIFUL, TRUSTED, Tribute
        from games.views import _tag_labels

        tribute = Tribute(id=0, tags=[FEARED, HIDDEN, BETRAYER, MERCIFUL, TRUSTED])
        self.assertEqual(len(_tag_labels(tribute)), 5)

    def test_a_past_victor_in_the_room_sends_gifts_during_a_game(self):
        """No tribute is in the room, so the only pop-ups are the past victor's gifts."""
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        fields = {"victor-name-0": "Alex", "victor-edition-0": "2", "victor-here-0": "on"}
        self.client.post("/roster/", setup_form(self.game, lambda position: False, action="start", **fields))
        gifts = 0
        for _ in range(100):
            page = self.play_until_question_or_end()
            if "New game" in page:
                break
            self.assertIn("victor of the 2nd Yearly Games, you sponsor a tribute", page)
            gifts += 1
            position = re.search(r'name="position" value="(\d+)"', page).group(1)
            self.client.post("/decision/", {"position": position, "choice": 0})
        if not gifts:
            self.skipTest("this game happened to end without a gift")  # gifts are random
        gift_lines = LogEntry.objects.filter(line__group="item.from_victor_edition", victor__name="Alex")
        self.assertEqual(gift_lines.count(), gifts)
        self.assertIn("<b>Alex</b>, victor of the 2nd Yearly Games", self.client.get("/").content.decode())

    def test_absent_tributes_get_votes_from_the_dead_in_the_room(self):
        self.client.post(
            "/roster/",
            setup_form(self.game, lambda position: position < 12, action="start", voters="everyone"),
        )
        for _ in range(400):
            page = self.play_until_question_or_end()
            if "New game" in page:
                self.fail("no vote happened in a whole game")
            if re.search(r"Vote \d+ of \d+, for", page):
                break
            position = re.search(r'name="position" value="(\d+)"', page).group(1)
            self.client.post("/decision/", {"position": position, "choice": 0})

    def play_until_bets(self):
        """Answers questions and presses Continue until the bets for the night are offered."""
        for _ in range(400):
            page = self.client.get("/").content.decode()
            if "New game" in page:
                self.fail("never offered bets")
            if "data-bets" in page:
                self.game.refresh_from_db()
                return page
            if 'role="dialog"' in page:
                position = re.search(r'name="position" value="(\d+)"', page).group(1)
                self.client.post("/decision/", {"position": position, "choice": 0})
            else:
                self.client.post("/round/next/")
        self.fail("never offered bets")

    def finish_the_round(self):
        """Answers the open round's questions until it is saved."""
        self.game.refresh_from_db()
        while self.game.round_seed is not None:
            page = self.client.get("/").content.decode()
            position = re.search(r'name="position" value="(\d+)"', page).group(1)
            self.client.post("/decision/", {"position": position, "choice": 0})
            self.game.refresh_from_db()

    def test_bets_before_a_night_are_scored_after_it(self):
        self.start(here=lambda position: position < 2)
        self.play_until_bets()
        target = self.game.tributes.filter(alive=True).last()
        self.client.post("/round/next/", {"bet-0": target.position, "bet-1": "", "bet-5": target.position})
        bets = list(Bet.objects.filter(game=self.game))
        self.assertEqual(
            [(bet.bettor.position, bet.target_id) for bet in bets], [(0, target.pk)]
        )  # 5 is not here
        self.finish_the_round()
        bet = Bet.objects.get(game=self.game)
        self.assertIn(bet.points, (0, 1, 3))

    def test_past_victors_in_the_room_bet_on_the_night(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        victors = {"victor-name-0": "Alex", "victor-here-0": "on", "victor-name-1": "Sam"}  # Sam is away
        self.client.post("/roster/", setup_form(self.game, lambda position: False, action="start", **victors))
        self.game.refresh_from_db()
        page = self.play_until_bets()
        self.assertIn('name="victor-bet-0"', page)
        self.assertNotIn('name="victor-bet-1"', page)
        target = self.game.tributes.filter(alive=True).last()
        self.client.post("/round/next/", {"victor-bet-0": target.position, "victor-bet-1": target.position})
        bet = Bet.objects.get(game=self.game)
        self.assertEqual((bet.bettor, bet.victor.name, bet.target_id), (None, "Alex", target.pk))
        self.finish_the_round()
        bet.refresh_from_db()
        self.assertIn(bet.points, (0, 1, 3))
        self.assertRegex(self.client.get("/").content.decode(), rf"Alex {bet.points}")  # the score line

    def test_the_fallen_appear_in_the_sky_after_a_round(self):
        self.start(here=lambda position: False)  # nobody in the room, so nobody is asked
        dead = Tribute.objects.filter(game=self.game, alive=False)
        while not dead.exists():  # rarely, a round ends without a cannon
            self.client.post("/round/next/")
        page = self.client.get("/?new=1").content.decode()
        fallen = dead.count()
        sky = page[page.index("data-fallen") :]
        self.assertEqual(sky[: sky.index("</div>")].count("<figure"), fallen)
        self.assertNotIn("data-fallen", self.client.get("/").content.decode())  # only for the newest round

    def test_the_end_of_the_game_shows_a_recap(self):
        self.start(here=lambda position: False)
        page = self.play_until_question_or_end()
        self.assertIn("data-recap", page)
        self.assertRegex(page, r"wins with \d+ kills")
