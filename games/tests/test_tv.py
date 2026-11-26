"""The TV screen: big story for the room, nothing to press."""

from django.core.management import call_command
from django.test import Client, TestCase

from games import services
from games.models import Game
from games.tests.test_flow import setup_form


class TvTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.client.get("/")  # the host's setup page makes the join code
        self.game = Game.objects.get()
        self.tv = Client()  # another device: no session
        self.url = f"/tv/{self.game.join_code}/"

    def test_before_the_gong_the_tv_shows_the_qr_code(self):
        self.assertIn("/tv/", self.client.get("/").content.decode())  # the host's link to it
        page = self.tv.get(self.url).content.decode()
        self.assertIn("<svg", page)
        self.assertIn(f"/play/{self.game.join_code}/", page)

    def test_the_tv_follows_the_story_and_shows_whose_turn_it_is(self):
        self.client.post("/roster/", setup_form(self.game, lambda position: position == 0, action="start"))
        self.client.post("/round/next/")  # the Bloodbath asks tribute 1
        self.game.refresh_from_db()
        page = self.tv.get(self.url).content.decode()
        self.assertIn("Name 1 decides", page)
        self.assertNotIn("<form", page)  # nothing to press
        while services.waiting_decision(self.game) is not None:  # answer until the Bloodbath ends
            services.answer_decision(self.game, services.current_answers(self.game).count(), 0)
        page = self.tv.get(self.url + "?new=1").content.decode()
        if self.game.tributes.filter(alive=False).exists():  # a Bloodbath without deaths is rare, but happens
            self.assertIn("data-fallen", page)
        self.assertNotIn("decides", page)

    def test_a_wrong_code_is_not_found(self):
        self.assertEqual(self.tv.get("/tv/nope/").status_code, 404)
