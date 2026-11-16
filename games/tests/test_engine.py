"""Plays thousands of games with random answers and checks that the engine is fair and never breaks."""

from django.core.management import call_command
from django.test import TestCase

from games.engine.dice import Dice
from games.engine.memory import callback_for
from games.engine.rounds import is_night_round, play_next_round
from games.engine.state import BETRAYER, FEARED, HIDDEN, MERCIFUL, Arena, Tribute, add_tag, has_tag
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

    def play_rounds(self, choose, rounds, seed=1):
        """Plays only the first rounds of a game, everyone in the room."""
        dice = Dice(seed)
        tributes = [Tribute(id=i) for i in range(TRIBUTES)]
        arena = Arena(self.catalogue, dice, tributes, lambda decision: choose(dice, decision))
        for _ in range(rounds):
            play_next_round(arena)
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
        """Half the tributes are "present" and always answer the same way. Choices may change a
        tribute's odds (reputation, items), but the dice that play the absent tributes must play
        about as well as a person would: whatever the habit, present players win about half the games."""
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

    # ---------- the story remembers ----------
    def arena_with_story(self, *told):
        """A small arena whose story already contains the given (group, a, b) lines."""
        tributes = [Tribute(id=i) for i in range(6)]
        arena = Arena(self.catalogue, Dice(1), tributes, lambda decision: 0)
        for group, a, b in told:
            arena.add_to_story("", self.catalogue.variants(group)[0], a=tributes[a], b=tributes[b])
        return arena, tributes

    def test_a_kill_calls_back_to_what_happened_between_the_two(self):
        cases = [
            ([("alliance.betrayal", 3, 2)], "callback.betrayal_avenged"),  # 3 betrayed 2, now 2 kills 3
            ([("alliance.betrayal", 2, 3)], "callback.betrayal_finished"),
            ([("encounter.steals", 3, 2)], "callback.theft_repaid"),
            ([("encounter.caught_stealing", 3, 2)], "callback.theft_repaid"),
            ([("encounter.leaves_sleeper", 3, 2)], "callback.mercy_repaid"),
            ([("encounter.alliance_formed", 3, 2)], "callback.former_allies"),
            ([("encounter.alliance_formed", 2, 3)], "callback.former_allies"),
            ([("combat.wound", 2, 3)], "callback.unfinished_business"),
        ]
        for told, expected in cases:
            arena, tributes = self.arena_with_story(*told)
            self.assertEqual(callback_for(arena, tributes[2], tributes[3]), expected, told)

    def test_district_partners_get_a_callback_and_strangers_do_not(self):
        arena, tributes = self.arena_with_story()
        self.assertIsNone(callback_for(arena, tributes[2], tributes[4]))
        self.assertEqual(callback_for(arena, tributes[0], tributes[1]), "callback.district_partners")
        self.assertIsNone(callback_for(arena, tributes[0], tributes[2]))

    def test_killing_tells_the_callback_after_the_death_line(self):
        arena, tributes = self.arena_with_story(("encounter.steals", 3, 2))
        before = len(arena.log)
        arena.kill_tribute(tributes[3], tributes[2])
        self.assertEqual([entry.line.group for entry in arena.log[before:]], ["callback.theft_repaid"])
        self.assertEqual((arena.log[-1].a, arena.log[-1].b), (2, 3))

    def test_a_death_without_a_killer_has_no_callback(self):
        arena, tributes = self.arena_with_story(("encounter.steals", 3, 2))
        before = len(arena.log)
        arena.kill_tribute(tributes[3])
        self.assertEqual(len(arena.log), before)

    # ---------- reputation ----------
    def test_no_bloodbath_option_is_clearly_better_than_the_others(self):
        """Rush, pack and flee have different strengths but win about equally often."""
        wins = [0, 0, 0]
        games = 4000
        for seed in range(games):
            picks = {}

            def answer(dice, decision, picks=picks):
                choice = dice.int(decision.option_count)
                if decision.question == "cornucopia":
                    picks[decision.tribute.id] = choice
                return choice

            arena = self.play(20_000 + seed, lambda i: True, answer)
            wins[picks[arena.winner.id]] += 1
        shares = [100 * count / games for count in wins]
        print(f"\nbloodbath option win shares (rush, pack, flee): {[round(s, 1) for s in shares]}")
        for share in shares:
            self.assertTrue(30 < share < 37, shares)

    def test_a_third_kill_makes_you_feared(self):
        arena, tributes = self.arena_with_story()
        killer = tributes[0]
        for victim in (2, 3, 4):
            arena.kill_tribute(tributes[victim], killer)
        self.assertTrue(has_tag(killer, FEARED))
        self.assertEqual([entry.line.group for entry in arena.log].count("reputation.feared"), 1)
        arena.kill_tribute(tributes[5], killer)
        self.assertEqual([entry.line.group for entry in arena.log].count("reputation.feared"), 1)

    def test_tags_are_given_once(self):
        _arena, tributes = self.arena_with_story()
        self.assertTrue(add_tag(tributes[0], HIDDEN))
        self.assertFalse(add_tag(tributes[0], HIDDEN))
        self.assertEqual(tributes[0].tags, [HIDDEN])

    def test_a_betrayer_sometimes_gets_a_cold_handshake(self):
        from games.engine.encounters import offer_alliance

        outcomes = set()
        for seed in range(200):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena.ask = lambda decision: 0  # always accept
            arena.choices_left = 5
            add_tag(tributes[2], BETRAYER)
            offer_alliance(arena, tributes[2], tributes[4])
            outcomes.add(arena.log[-1].line.group)
        self.assertEqual(outcomes, {"encounter.alliance_formed", "encounter.cold_handshake"})

    def test_a_tribute_without_a_past_always_gets_the_handshake(self):
        from games.engine.encounters import offer_alliance

        for seed in range(100):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena.ask = lambda decision: 0
            arena.choices_left = 5
            offer_alliance(arena, tributes[2], tributes[4])
            self.assertEqual(arena.log[-1].line.group, "encounter.alliance_formed")

    def test_fleeing_the_bloodbath_hides_you_for_two_nights_only(self):
        arena = self.play_rounds(
            lambda dice, decision: 2 if decision.question == "cornucopia" else 0, rounds=1
        )  # all flee
        self.assertTrue(all(has_tag(tribute, HIDDEN) for tribute in arena.tributes))
        for _ in range(4):  # Day 1, Night 1, Day 2, Night 2
            play_next_round(arena)
        survivors = [t for t in arena.living() if not has_tag(t, HIDDEN)]
        self.assertEqual(len(survivors), 0)
        play_next_round(arena)  # Day 3
        self.assertFalse(any(has_tag(t, HIDDEN) for t in arena.tributes))

    # ---------- mercy, debts and the Gamemaker's shield ----------
    def fight_until(self, wanted, mercy_answer, **fight_options):
        """Fights tributes 2 and 4 with new seeds until the story tells the wanted line."""
        from games.engine.combat import fight

        for seed in range(500):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena.choices_left = 5
            arena.ask = lambda decision: mercy_answer
            fight(arena, tributes[2], tributes[4], 0, 1.0, **fight_options)
            if wanted in [entry.line.group for entry in arena.log]:
                return arena, tributes
        self.fail(f"{wanted} never happened")

    def test_sparing_a_loser_wounds_them_and_creates_a_debt(self):
        arena, tributes = self.fight_until("combat.spared", mercy_answer=1)
        spared = next(t for t in (tributes[2], tributes[4]) if t.debts)
        winner = tributes[spared.debts[0]]
        self.assertTrue(spared.alive and spared.wounded)
        self.assertTrue(has_tag(winner, MERCIFUL))

    def test_finishing_never_spares(self):
        from games.engine.combat import fight

        for seed in range(100):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena.choices_left = 5
            arena.ask = lambda decision: 0
            fight(arena, tributes[2], tributes[4], 0, 1.0)
            self.assertNotIn("combat.spared", [entry.line.group for entry in arena.log])

    def test_the_final_duel_has_no_mercy(self):
        from games.engine.combat import fight

        for seed in range(100):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena.choices_left = 5
            arena.ask = lambda decision: 1
            fight(arena, tributes[2], tributes[4], 0, 1.0, mercy=False)
            self.assertNotIn("combat.spared", [entry.line.group for entry in arena.log])

    def test_a_debtor_who_wins_lets_the_benefactor_go_once(self):
        from games.engine.combat import fight
        from games.engine.state import add_debt

        repaid = 0
        for seed in range(200):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            add_debt(tributes[4], tributes[2])  # 2 once spared 4
            fight(arena, tributes[2], tributes[4], 0, 1.0, mercy=False)
            if "combat.debt_repaid" in [entry.line.group for entry in arena.log]:
                repaid += 1
                self.assertTrue(tributes[2].alive)
                self.assertEqual(tributes[4].debts, [])
            else:
                self.assertEqual(tributes[4].debts, [2])  # 2 won: the debt still stands
        self.assertGreater(repaid, 0)

    def test_the_shielded_tribute_is_never_caught(self):
        from games.engine.events import arena_event

        disaster = self.catalogue.arena_events[0]
        for seed in range(100):
            arena, tributes = self.arena_with_story()
            arena.dice = Dice(seed)
            arena_event(arena, disaster, death_chance=1.0, shielded=tributes[3])
            self.assertTrue(tributes[3].alive)
            self.assertFalse(tributes[3].wounded)
            self.assertIn("arena.shielded", [entry.line.group for entry in arena.log])

    def test_the_gamemaker_never_shields_themselves(self):
        from games.engine.rounds import ask_shield

        asked = []

        def ask(decision):
            asked.append(decision)
            return 0

        for seed in range(50):
            arena, tributes = self.arena_with_story()
            arena.dice, arena.ask = Dice(seed), ask
            tributes[1].alive = False
            ask_shield(arena, tributes[1], self.catalogue.arena_events[0])
        self.assertTrue(asked)
        for decision in asked:
            self.assertNotIn(decision.tribute, decision.option_tributes)
            self.assertEqual(decision.question, "shield")

    def test_more_pop_ups_when_few_are_left(self):
        from games.engine.rounds import choice_budget

        self.assertLess(choice_budget(20), choice_budget(8))
        self.assertLess(choice_budget(8), choice_budget(3))

    # ---------- votes for absent tributes ----------
    def voting_arena(self, voters, no_conflict_votes=True):
        """Tributes 0-5. 0 and 1 are in the room and alive, 2 is in the room and dead,
        3 is a past winner in the room, 4 and 5 are absent."""
        tributes = [Tribute(id=i, present=i < 4) for i in range(6)]
        tributes[2].alive = False
        tributes[3].past_winner_year = 2023
        arena = Arena(
            self.catalogue, Dice(1), tributes, lambda decision: 0,
            voters=voters, no_conflict_votes=no_conflict_votes,
        )  # fmt: skip
        return arena, tributes

    def voter_ids(self, voters, no_conflict_votes=True, b=5):
        arena, tributes = self.voting_arena(voters, no_conflict_votes)
        return [t.id for t in arena.voters_for(tributes[4], {"a": tributes[4], "b": tributes[b]})]

    def test_each_voter_setting_picks_the_right_players(self):
        self.assertEqual(self.voter_ids("nobody"), [])
        self.assertEqual(self.voter_ids("dead"), [2])
        self.assertEqual(self.voter_ids("past_winners"), [3])
        self.assertEqual(self.voter_ids("past_winners_and_dead"), [2, 3])
        self.assertEqual(self.voter_ids("everyone"), [0, 1, 2, 3])

    def test_fair_play_keeps_players_out_of_votes_about_them_or_their_alliance(self):
        self.assertEqual(self.voter_ids("everyone", b=0), [1, 2, 3])  # 0 is the other tribute
        arena, tributes = self.voting_arena("everyone")
        tributes[1].alliance = tributes[5].alliance = 1
        voters = arena.voters_for(tributes[4], {"a": tributes[4], "b": tributes[5]})
        self.assertEqual([t.id for t in voters], [0, 2, 3])  # 1 is allied with 5
        self.assertEqual(self.voter_ids("everyone", no_conflict_votes=False, b=0), [0, 1, 2, 3])

    def test_a_vote_asks_each_voter_and_the_majority_wins(self):
        arena, tributes = self.voting_arena("everyone")
        arena.choices_left, arena.votes_left = 5, 1
        asked = []
        answers = iter([2, 2, 0, 1])

        def ask(decision):
            asked.append(decision)
            return next(answers)

        arena.ask = ask
        choice = arena.decide(tributes[4], "meeting", [1, 1, 1], a=tributes[4], b=tributes[5])
        self.assertEqual(choice, 2)
        self.assertEqual([d.tribute.id for d in asked], [0, 1, 2, 3])
        self.assertTrue(all(d.vote_for is tributes[4] and d.vote_total == 4 for d in asked))
        self.assertEqual(arena.votes_left, 0)
        # Only one vote per round: the next big decision goes to the dice.
        arena.ask = lambda decision: self.fail("asked again")
        arena.decide(tributes[4], "meeting", [1, 1, 1], a=tributes[4], b=tributes[5])

    def test_a_tied_vote_goes_to_one_of_the_tied_options(self):
        for seed in range(30):
            arena, tributes = self.voting_arena("past_winners_and_dead")
            arena.dice, arena.choices_left, arena.votes_left = Dice(seed), 5, 1
            answers = iter([0, 2])
            arena.ask = lambda decision, answers=answers: next(answers)
            choice = arena.decide(tributes[4], "meeting", [1, 1, 1], a=tributes[4], b=tributes[5])
            self.assertIn(choice, (0, 2))

    def test_present_tributes_and_small_questions_are_never_voted_on(self):
        arena, tributes = self.voting_arena("everyone")
        arena.choices_left, arena.votes_left = 5, 1
        asked = []
        arena.ask = lambda decision: asked.append(decision) or 0
        arena.decide(tributes[4], "berries", [1, 1], a=tributes[4])
        self.assertEqual(asked, [])
        arena.decide(tributes[0], "meeting", [1, 1, 1], a=tributes[0], b=tributes[5])
        self.assertEqual([d.vote_for for d in asked], [None])  # tribute 0 answers for themselves

    def test_votes_do_not_help_the_room_win_with_fair_play(self):
        """With fair play on, random voters in the room must not make the room win more often."""
        games = 1200
        for voters in ("dead", "past_winners", "past_winners_and_dead", "everyone"):
            present_wins = 0
            for game in range(games):
                swapped = game % 2 == 1
                dice = Dice(30_000 + game)
                tributes = [Tribute(id=i, present=(i % 2 == 0) != swapped) for i in range(TRIBUTES)]
                for tribute in tributes[::5]:
                    tribute.past_winner_year = 2020
                answer = lambda decision, dice=dice: dice.int(decision.option_count)  # noqa: E731
                arena = Arena(self.catalogue, dice, tributes, answer, voters=voters)
                while not arena.winner:
                    play_next_round(arena)
                present_wins += arena.winner.present
            share = 100 * present_wins / games
            print(f"\nvotes by {voters}: present players win {share:.1f}%")
            self.assertTrue(44 < share < 56, f"{voters}: {share:.1f}%")

    # ---------- goals and bounties ----------
    def test_every_living_tribute_has_a_goal_after_the_first_day(self):
        from games.engine.rounds import GOALS

        arena = self.play_rounds(lambda dice, decision: dice.int(decision.option_count), rounds=2)
        self.assertTrue(all(t.goal in GOALS for t in arena.living()))

    def test_only_a_few_players_choose_their_goal_each_day(self):
        from games.engine.rounds import GOAL_POPUPS_PER_DAY, choose_goals

        arena, _tributes = self.arena_with_story()
        asked = []
        arena.ask = lambda decision: asked.append(decision) or 0
        choose_goals(arena)
        self.assertEqual(len(asked), GOAL_POPUPS_PER_DAY)
        self.assertTrue(all(d.question == "goal" for d in asked))

    def test_a_bounty_makes_others_hold_a_grudge_against_the_target(self):
        from games.engine.rounds import BOUNTY_HUNTERS, place_bounty

        arena, tributes = self.arena_with_story()
        tributes[0].alive = False
        arena.ask = lambda decision: 0
        place_bounty(arena, tributes[0])
        entry = arena.log[-1]
        self.assertEqual(entry.line.group, "bounty.placed")
        self.assertEqual(entry.sponsor, 0)
        self.assertEqual(len(entry.names), BOUNTY_HUNTERS)
        for hunter in entry.names:
            self.assertIn(entry.a, tributes[hunter].grudges)

    def test_a_living_gamemaker_shields_nobody(self):
        from games.engine.rounds import ask_shield

        arena, tributes = self.arena_with_story()
        arena.ask = lambda decision: self.fail("a living Gamemaker was asked to shield")
        self.assertIsNone(ask_shield(arena, tributes[1], self.catalogue.arena_events[0]))
