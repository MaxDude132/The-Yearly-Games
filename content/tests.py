import re

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from content import models
from games.engine.memory import CALLBACK_GROUPS
from games.engine.rounds import BOND_GROUPS
from games.services import load_catalogue

LANGUAGES = [code for code, _name in settings.LANGUAGES]
NEW_GROUPS = [
    "reputation.trusted", "encounter.trust_wins_over", "encounter.lets_go", "act.manhunt", "act.final_four",
    "endgame.debt", "endgame.allies", "endgame.grudge", "rumour.supplies", "rumour.hunters", "rumour.storm",
    "alliance.raid", "alliance.lies_low", "arena.fallen_vote",
]  # fmt: skip
QUESTIONS_THE_ENGINE_ASKS = {
    "cornucopia", "meeting", "alliance_offer", "sleeper", "loyalty", "trap", "berries", "final_duel",
    "sponsor", "victor_sponsor", "gamemaker", "mercy", "shield", "goal", "bounty", "chase", "raid",
}  # fmt: skip
PLACEHOLDER = re.compile(r"\{(\w+)\}")
KNOWN_PLACEHOLDERS = {"a", "b", "item", "n", "names", "sponsor", "victor"}


class ContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def assertTranslated(self, parents, translations, parent_field):
        for parent in parents:
            languages = set(translations.filter(**{parent_field: parent}).values_list("language", flat=True))
            self.assertEqual(languages, set(LANGUAGES), f"{parent} is missing a translation")

    def test_everything_is_translated_in_every_language(self):
        self.assertTranslated(models.Item.objects.all(), models.ItemTranslation.objects, "item")
        self.assertTranslated(models.ArenaEvent.objects.all(), models.ArenaEventTranslation.objects, "event")
        self.assertTranslated(models.StoryLine.objects.all(), models.StoryLineTranslation.objects, "line")
        self.assertTranslated(models.Question.objects.all(), models.QuestionTranslation.objects, "question")
        self.assertTranslated(
            models.QuestionOption.objects.all(), models.QuestionOptionTranslation.objects, "option"
        )

    def test_loading_twice_updates_rows_instead_of_duplicating_them(self):
        before = [model.objects.count() for model in (models.Item, models.StoryLine, models.ItemTranslation)]
        call_command("load_content", verbosity=0)
        after = [model.objects.count() for model in (models.Item, models.StoryLine, models.ItemTranslation)]
        self.assertEqual(before, after)

    def test_a_reload_updates_changed_text(self):
        translation = models.ItemTranslation.objects.get(item__key="sword", language="en")
        translation.name = "changed by hand"
        translation.save()
        call_command("load_content", verbosity=0)
        translation.refresh_from_db()
        self.assertEqual(translation.name, "a sword")

    def test_placeholders_are_known_and_the_same_in_every_language(self):
        for line in models.StoryLine.objects.all():
            found = {
                language: set(PLACEHOLDER.findall(text))
                for language, text in line.translations.values_list("language", "text")
            }
            self.assertEqual(len({frozenset(names) for names in found.values()}), 1, f"{line}: {found}")
            for names in found.values():
                self.assertLessEqual(names, KNOWN_PLACEHOLDERS, str(line))

    def test_every_question_the_engine_asks_exists(self):
        keys = set(models.Question.objects.values_list("key", flat=True))
        self.assertEqual(keys, QUESTIONS_THE_ENGINE_ASKS)
        catalogue = load_catalogue()
        for key in ("cornucopia", "meeting", "alliance_offer", "sleeper", "loyalty", "trap", "berries"):
            self.assertGreaterEqual(catalogue.option_count(key), 2, key)
        self.assertEqual(catalogue.option_count("final_duel"), 3)

    def test_every_arena_event_has_an_announcement_and_a_counter(self):
        catalogue = load_catalogue()
        self.assertIsNotNone(catalogue.feast)
        self.assertTrue(catalogue.arena_events)
        for event in catalogue.arena_events:
            self.assertTrue(catalogue.intro(event))
            self.assertIn(event.counter, {item.kind for item in catalogue.items}, event.key)

    def test_the_engine_finds_every_group_it_tells(self):
        catalogue = load_catalogue()
        groups = [
            *BOND_GROUPS,
            *CALLBACK_GROUPS,
            "reputation.feared",
            "encounter.cold_handshake",
            "encounter.hidden_well",
            "phase.bloodbath",
            "phase.day",
            "phase.night",
        ]
        for group in [*groups, "finale.announced"]:
            self.assertTrue(catalogue.variants(group), group)
        self.assertEqual(len(catalogue.variants("finale.tactic")), 3)
