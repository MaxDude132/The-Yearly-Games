"""Players on their own phones: the QR code, taking a seat, answering, betting, live updates."""

import re
import shutil

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from games import services
from games.models import Answer, Game
from games.tests.test_flow import MEDIA_ROOT, setup_form


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        page = self.client.get("/").content.decode()  # the host's screen: makes the game and its code
        self.game = Game.objects.get()
        self.code = self.game.join_code
        self.assertIn(f"/play/{self.code}/", page)  # the link under the QR code
        self.assertIn("<svg", page)  # the QR code itself

    def phone(self, kind="tribute", position=0, name="Gaël"):
        """A new phone that takes a seat."""
        phone = Client()
        phone.post(f"/play/{self.code}/join/", {"kind": kind, "position": position, "name": name})
        return phone

    def assert_answered(self, answers_before):
        """The answer was taken: saved, or it ended the round (which clears the round's answers)."""
        self.game.refresh_from_db()
        if self.game.round_seed is not None:
            self.assertEqual(Answer.objects.count(), answers_before + 1)

    def version(self):
        return self.client.get("/state/").json()["version"]

    # ---------- joining ----------

    def test_a_phone_sees_the_free_seats_and_takes_one(self):
        phone = Client()
        page = phone.get(f"/play/{self.code}/").content.decode()
        self.assertIn("?pick=tribute-0", page)
        self.assertIn("Choose who you are", page)
        page = phone.get(f"/play/{self.code}/?pick=tribute-3").content.decode()
        self.assertIn('name="position" value="3"', page)

        before = self.version()
        phone.post(f"/play/{self.code}/join/", {"kind": "tribute", "position": 3, "name": "Gaël"})
        tribute = self.game.tributes.get(position=3)
        self.assertEqual(tribute.name, "Gaël")
        self.assertTrue(tribute.present)
        self.assertTrue(tribute.phone_token)
        self.assertGreater(self.version(), before)  # the host's screen will reload
        page = phone.get(f"/play/{self.code}/").content.decode()
        self.assertIn("Gaël", page)
        self.assertIn("Wait for the host to start", page)

    def test_a_taken_seat_cannot_be_taken_again(self):
        self.phone(position=0, name="Gaël")
        other = self.phone(position=0, name="Intruder")
        self.assertEqual(self.game.tributes.get(position=0).name, "Gaël")
        self.assertNotIn("?pick=tribute-0", other.get(f"/play/{self.code}/").content.decode())

    def test_a_past_victor_can_join_too(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        phone = self.phone(kind="victor", position=0, name="Alex")
        self.assertEqual(self.game.victors.get().name, "Alex")
        self.assertIn("Past victor", phone.get(f"/play/{self.code}/").content.decode())

    def test_the_host_form_keeps_names_chosen_on_phones_and_can_disconnect_them(self):
        self.phone(position=0, name="Gaël")
        self.client.post("/roster/", setup_form(self.game, action="save"))  # an old page: "Name 1"
        self.assertEqual(self.game.tributes.get(position=0).name, "Gaël")
        self.client.post("/roster/", setup_form(self.game, action="release-0"))
        self.assertEqual(self.game.tributes.get(position=0).phone_token, "")

    def test_leaving_gives_the_seat_back(self):
        phone = self.phone(position=0)
        phone.post(f"/play/{self.code}/leave/")
        self.assertEqual(self.game.tributes.get(position=0).phone_token, "")
        self.assertIn("?pick=tribute-0", phone.get(f"/play/{self.code}/").content.decode())

    def test_an_unknown_code_is_not_found(self):
        self.assertEqual(Client().get("/play/nope/").status_code, 404)

    # ---------- playing ----------

    def start_with_one_phone(self):
        """Only tribute 0 is in the room, on a phone: every question is theirs."""
        phone = self.phone(position=0)
        self.client.post("/roster/", setup_form(self.game, lambda position: position == 0, action="start"))
        return phone

    def wait_for_question(self):
        for _ in range(100):
            self.game.refresh_from_db()
            if self.game.status == Game.Status.PLAYING and services.waiting_decision(self.game):
                return True
            if self.game.winner_id:
                return False
            self.client.post("/round/next/")
        self.fail("no question came")

    def test_the_phone_gets_its_own_questions_and_answers_them(self):
        phone = self.start_with_one_phone()
        self.assertTrue(self.wait_for_question())  # the Bloodbath asks everyone in the room
        page = phone.get(f"/play/{self.code}/").content.decode()
        self.assertIn('role="dialog"', page)
        self.assertNotIn("Let the dice decide", page)  # only the host has that button
        position = re.search(r'name="position" value="(\d+)"', page).group(1)
        host_page = self.client.get("/").content.decode()
        self.assertIn("can answer on their phone", host_page)

        before = Answer.objects.count()
        round_before = self.game.round
        phone.post(f"/play/{self.code}/decision/", {"position": position, "choice": 0})
        self.assert_answered(before)
        if self.game.round_seed is None:
            self.assertEqual(self.game.round, round_before + 1)  # the answer finished the Bloodbath

    def test_a_phone_cannot_answer_someone_elses_question(self):
        self.start_with_one_phone()
        self.assertTrue(self.wait_for_question())
        stranger = self.phone(position=5, name="Not asked")
        answers = Answer.objects.count()
        stranger.post(f"/play/{self.code}/decision/", {"position": answers, "choice": 0})
        self.assertEqual(Answer.objects.count(), answers)
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.round_seed)  # still waiting for tribute 0
        self.assertIn("Waiting for", stranger.get(f"/play/{self.code}/").content.decode())

    def test_the_host_can_let_the_dice_answer(self):
        self.start_with_one_phone()
        self.assertTrue(self.wait_for_question())
        answers = Answer.objects.count()
        self.client.post("/decision/", {"position": answers, "choice": "random"})
        self.assert_answered(answers)

    def test_a_whole_game_can_be_played_from_the_phone(self):
        phone = self.start_with_one_phone()
        for _ in range(300):
            if not self.wait_for_question():
                break
            page = phone.get(f"/play/{self.code}/").content.decode()
            position = re.search(r'name="position" value="(\d+)"', page).group(1)
            phone.post(f"/play/{self.code}/decision/", {"position": position, "choice": 0})
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.winner_id)
        self.assertRegex(
            phone.get(f"/play/{self.code}/").content.decode(), r"You won the Games!|wins the Games"
        )

    # ---------- bets ----------

    def test_a_phone_bets_and_the_host_form_keeps_that_bet(self):
        phone = self.phone(position=0)
        self.client.post(
            "/roster/", setup_form(self.game, lambda position: position in (0, 1), action="start")
        )
        for _ in range(200):  # play until bets open (just before a night)
            page = phone.get(f"/play/{self.code}/").content.decode()
            if "data-bets" in page:
                break
            if 'role="dialog"' in page:
                position = re.search(r'name="position" value="(\d+)"', page).group(1)
                phone.post(f"/play/{self.code}/decision/", {"position": position, "choice": 0})
                continue
            host = self.client.get("/").content.decode()
            if 'role="dialog"' in host:
                position = re.search(r'name="position" value="(\d+)"', host).group(1)
                self.client.post("/decision/", {"position": position, "choice": 0})
                continue
            self.client.post("/round/next/")
        else:
            self.fail("bets never opened")
        target = re.search(r'<option value="(\d+)"', page[page.index("data-bets") :]).group(1)
        phone.post(f"/play/{self.code}/bet/", {"target": target})
        self.assertIn("has bet", self.client.get("/").content.decode())
        coming = self.game.bets.get().round
        self.client.post("/round/next/", {"bet-1": target})  # the host bets for tribute 1, not for 0
        bets = {bet.bettor.position: bet.target.position for bet in self.game.bets.filter(round=coming)}
        self.assertEqual(bets, {0: int(target), 1: int(target)})

    def test_a_past_victor_bets_on_their_phone(self):
        self.client.post("/roster/", setup_form(self.game, action="add-victor"))
        phone = self.phone(kind="victor", position=0, name="Alex")
        self.client.post(
            "/roster/",
            setup_form(self.game, lambda position: False, action="start", **{"victor-here-0": "on"}),
        )
        for _ in range(200):  # the host answers Alex's sponsor questions until bets open
            page = phone.get(f"/play/{self.code}/").content.decode()
            if "data-bets" in page:
                break
            host = self.client.get("/").content.decode()
            if 'role="dialog"' in host:
                position = re.search(r'name="position" value="(\d+)"', host).group(1)
                self.client.post("/decision/", {"position": position, "choice": 0})
                continue
            self.client.post("/round/next/")
        else:
            self.fail("bets never opened")
        target = re.search(r'<option value="(\d+)"', page[page.index("data-bets") :]).group(1)
        phone.post(f"/play/{self.code}/bet/", {"target": target})
        bet = self.game.bets.get()
        self.assertEqual((bet.victor.name, bet.target.position), ("Alex", int(target)))
        self.assertIn("has bet", self.client.get("/").content.decode())
        self.client.post("/round/next/", {"victor-bet-0": ""})  # the host's form keeps the phone's bet
        self.assertTrue(self.game.bets.filter(victor__name="Alex").exists())
