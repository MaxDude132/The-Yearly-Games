"""Plays thousands of games with random answers and checks that the engine is fair and never breaks."""

from django.core.management import call_command
from django.test import TestCase

from games.engine.dice import Dice
from games.engine.rounds import is_night_round, play_next_round
from games.engine.state import Arena, Tribute
from games.render import MissingValue, Translator
from games.services import load_catalogue

GAMES = 5000
TRIBUTES = 24
FAIRNESS_GAMES = 4000
RENDERED_GAMES = 300  # rendering every line of every game would take long and add little


class EngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.catalogue = load_catalogue()
        cls.translators = {code: Translator(code) for code in ("en", "fr")}

    def play(self, seed, present, choose):
        """Plays one whole game. present(i) says who is in the room; choose(dice, decision) answers."""
        dice = Dice(seed)
        tributes = [Tribute(id=i, present=present(i)) for i in range(TRIBUTES)]
        arena = Arena(self.catalogue, dice, tributes, lambda decision: choose(dice, decision))
        while not arena.winner:
            play_next_round(arena)
            self.assertLess(arena.round, 200, "a game did not end")
        return arena

    def test_every_game_ends_with_one_winner_and_no_missing_text(self):
        wins = [0] * TRIBUTES
        total_rounds = total_choices = 0
        choices = []

        def answer_randomly(dice, decision):
            choices.append(decision)
            return dice.int(decision.option_count)

        for seed in range(GAMES):
            choices.clear()
            # Every second tribute is "in the room", so pop-ups happen.
            arena = self.play(seed, lambda i: i % 2 == 0, answer_randomly)
            self.assertEqual(len(arena.living()), 1, "there must be exactly one winner")
            wins[arena.winner.id] += 1
            total_rounds += arena.round
            total_choices += len(choices)
            if seed < RENDERED_GAMES:
                self.assert_story_renders(arena)

        print(f"\naverage rounds {total_rounds / GAMES:.1f}, average choices {total_choices / GAMES:.1f}, "
              f"fewest wins {min(wins)}, most wins {max(wins)}")  # fmt: skip
        # With 5000 games and 24 tributes, each should win about 208 times.
        self.assertGreater(min(wins), 120)
        self.assertLess(max(wins), 300)

    def assert_story_renders(self, arena):
        name_of = lambda tribute_id: f"T{tribute_id}"  # noqa: E731
        for translator in self.translators.values():
            for entry in arena.log:
                try:
                    html = translator.story(entry, name_of, strict=True)
                except MissingValue as error:
                    self.fail(str(error))
                self.assertNotRegex(html, r"None|undefined|NaN|\{|\}")

    def test_the_story_starts_with_the_bloodbath_and_alternates_days_and_nights(self):
        arena = self.play(1, lambda i: False, lambda dice, decision: 0)
        headings = [entry for entry in arena.log if entry.style.startswith("heading")]
        self.assertEqual(len(headings), arena.round)
        self.assertEqual(headings[0].line.group, "phase.bloodbath")
        for number, heading in enumerate(headings, start=1):
            if number > 1:
                self.assertEqual(heading.line.group, "phase.night" if is_night_round(number) else "phase.day")
                self.assertEqual(heading.n, number // 2)

    def test_being_in_the_room_does_not_help_you_win(self):
        """Half the tributes are "present" and always answer the same way. Whatever the habit,
        present players should win about half the games: choices change the story, not the odds."""
        habits = {
            "random": lambda dice, decision: dice.int(decision.option_count),
            "alwaysFirstOption": lambda dice, decision: 0,
            "alwaysMiddleOption": lambda dice, decision: min(1, decision.option_count - 1),
            "alwaysLastOption": lambda dice, decision: decision.option_count - 1,
        }
        for habit, choose in habits.items():
            present_wins = 0
            for game in range(FAIRNESS_GAMES):
                # Swap which half is present every game, so list position cancels out.
                swapped = game % 2 == 1
                arena = self.play(10_000 + game, lambda i, s=swapped: (i % 2 == 0) != s, choose)
                present_wins += arena.winner.present
            share = 100 * present_wins / FAIRNESS_GAMES
            print(f"\n{habit}: present players win {share:.1f}% of games (fair is 50%)")
            self.assertTrue(46 < share < 54, f'players in the room who play "{habit}" win {share:.1f}%')

    def test_the_same_seed_and_answers_replay_the_same_game(self):
        def answer_first(dice, decision):
            return 0

        first = self.play(7, lambda i: i % 2 == 0, answer_first)
        again = self.play(7, lambda i: i % 2 == 0, answer_first)
        self.assertEqual(first.log, again.log)
