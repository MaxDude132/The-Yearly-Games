"""Moves a game between the database and the engine, and runs rounds.

A round that needs a player's answer cannot wait inside a web request. Instead the round is
replayed from the start every time: same dice seed, same saved answers, so it unfolds the same
way until it reaches the first question that has no answer yet. Nothing is written to the story
until the round is complete.
"""

import secrets

from django.db import transaction

from content import models as content
from games import history, models
from games.bets import score_bets
from games.engine.catalogue import ArenaEvent, Catalogue, Item, Line
from games.engine.dice import Dice
from games.engine.rounds import play_next_round
from games.engine.state import Arena, Entry, NeedAnswer
from games.engine.state import Tribute as EngineTribute
from games.engine.state import Victor as EngineVictor

DEFAULT_TRIBUTE_COUNT = 24
MIN_TRIBUTES = 2
MAX_ROUNDS = 200  # skip_to_the_end stops here, in case a game never ends


# ---------- content ----------


def load_catalogue():
    """The items, events, lines and questions that exist (the text is looked up later, per language)."""
    items = [Item(item.key, item.kind) for item in content.Item.objects.order_by("key")]
    events = [
        ArenaEvent(event.key, event.counter, event.is_feast)
        for event in content.ArenaEvent.objects.order_by("key")
    ]
    line_groups = {}
    for group in content.StoryLine.objects.order_by("group", "variant").values_list("group", flat=True):
        line_groups[group] = line_groups.get(group, 0) + 1
    question_options = {
        question.key: question.options.count() for question in content.Question.objects.order_by("key")
    }
    return Catalogue(items, events, line_groups, question_options)


# ---------- the game of a browser session ----------


def get_game(session_key):
    """The game of this browser session, created with an empty roster the first time."""
    game, created = models.Game.objects.get_or_create(session_key=session_key)
    if created:
        models.Tribute.objects.bulk_create(
            models.Tribute(game=game, position=position) for position in range(DEFAULT_TRIBUTE_COUNT)
        )
    return game


def start_game(game, rehearsal=False):
    """Leaves the setup screen. Returns False if there are too few tributes."""
    if game.tributes.count() < MIN_TRIBUTES:
        return False
    game.status = models.Game.Status.PLAYING
    game.rehearsal = rehearsal
    game.first_new_entry = 0
    game.save(update_fields=["status", "rehearsal", "first_new_entry", "updated_at"])
    return True


def skip_to_the_end(game):
    """Rehearsal: plays every remaining round, the dice answering every question."""
    for _ in range(MAX_ROUNDS):
        if game.winner_id:
            return
        if game.round_seed is None:
            start_round(game)
        while (decision := waiting_decision(game)) is not None:
            answer_decision(game, current_answers(game).count(), secrets.randbelow(decision.option_count))


@transaction.atomic
def reset_game(game):
    """Back to the setup screen. The roster and the past victors (names, photos, who is here) are kept."""
    clear_arena(game)
    game.answers.all().delete()
    game.played_rounds.all().delete()
    game.bets.all().delete()
    if game.rehearsal:  # game night starts with every seat free
        game.tributes.update(phone_token="")
        game.victors.update(phone_token="")
    game.status = models.Game.Status.SETUP
    game.rehearsal = False
    game.save(update_fields=["status", "rehearsal", "updated_at"])


def clear_arena(game):
    """Undoes everything the Games did to the tributes and the story, as before the gong.
    The answers, played rounds and bets stay (Undo replays them)."""
    game.log.all().delete()
    models.TributeItem.objects.filter(tribute__game=game).delete()
    models.TributeTag.objects.filter(tribute__game=game).delete()
    models.Grudge.objects.filter(tribute__game=game).delete()
    models.Debt.objects.filter(tribute__game=game).delete()
    game.tributes.update(alive=True, wounded=False, alliance=0, kills=0, died_on_day=0, goal="")
    game.round = game.day = game.alliance_count = game.first_new_entry = 0
    game.feast_happened = False
    game.winner = None
    game.round_seed = None
    game.save()


def current_answers(game):
    """The answers of the round in progress."""
    return game.answers.filter(round=game.round + 1)


# ---------- database to engine and back ----------


def load_arena(game, catalogue, dice, ask):
    rows = list(game.tributes.order_by("position"))
    id_of = {row.pk: row.position for row in rows}
    tributes = [
        EngineTribute(
            id=row.position,
            present=row.present,
            goal=row.goal,
            alive=row.alive,
            wounded=row.wounded,
            alliance=row.alliance,
            kills=row.kills,
            died_on_day=row.died_on_day,
        )
        for row in rows
    ]
    for carried in models.TributeItem.objects.filter(tribute__game=game).select_related("item"):
        tributes[id_of[carried.tribute_id]].items.append(catalogue.item(carried.item.key))
    for grudge in models.Grudge.objects.filter(tribute__game=game):
        tributes[id_of[grudge.tribute_id]].grudges.append(id_of[grudge.target_id])
    for debt in models.Debt.objects.filter(tribute__game=game):
        tributes[id_of[debt.tribute_id]].debts.append(id_of[debt.target_id])
    for tag in models.TributeTag.objects.filter(tribute__game=game):
        tributes[id_of[tag.tribute_id]].tags.append(tag.tag)

    victor_rows = list(game.victors.order_by("position"))
    victor_id_of = {row.pk: row.position for row in victor_rows}
    victors = [EngineVictor(id=row.position, present=row.present, edition=row.edition) for row in victor_rows]

    def tribute_id(pk):
        return None if pk is None else id_of[pk]

    entries = (
        models.LogEntry.objects.filter(game=game).select_related("line", "item").prefetch_related("names")
    )
    log = [
        Entry(
            entry.style,
            Line(entry.line.group, entry.line.variant),
            a=tribute_id(entry.a_id),
            b=tribute_id(entry.b_id),
            sponsor=tribute_id(entry.sponsor_id),
            victor=victor_id_of.get(entry.victor_id),
            item=entry.item.key if entry.item_id else None,
            n=entry.n,
            names=tuple(id_of[name.tribute_id] for name in entry.names.all()),
        )
        for entry in entries
    ]
    return Arena(
        catalogue, dice, tributes, ask,
        log=log,
        round=game.round,
        day=game.day,
        alliance_count=game.alliance_count,
        feast_happened=game.feast_happened,
        winner=tributes[id_of[game.winner_id]] if game.winner_id else None,
        voters=game.voters,
        no_conflict_votes=game.no_conflict_votes,
        victors=victors,
    )  # fmt: skip


@transaction.atomic
def save_arena(game, arena):
    """Writes the state after a completed round."""
    item_rows = {item.key: item for item in content.Item.objects.all()}
    rows = list(game.tributes.order_by("position"))
    for row, tribute in zip(rows, arena.tributes, strict=True):
        row.alive, row.wounded, row.alliance = tribute.alive, tribute.wounded, tribute.alliance
        row.kills, row.died_on_day, row.goal = tribute.kills, tribute.died_on_day, tribute.goal
    models.Tribute.objects.bulk_update(rows, ["alive", "wounded", "alliance", "kills", "died_on_day", "goal"])

    models.TributeItem.objects.filter(tribute__game=game).delete()
    models.Grudge.objects.filter(tribute__game=game).delete()
    models.Debt.objects.filter(tribute__game=game).delete()
    models.TributeTag.objects.filter(tribute__game=game).delete()
    models.TributeItem.objects.bulk_create(
        models.TributeItem(tribute=row, position=position, item=item_rows[item.key])
        for row, tribute in zip(rows, arena.tributes, strict=True)
        for position, item in enumerate(tribute.items)
    )
    models.Grudge.objects.bulk_create(
        models.Grudge(tribute=row, position=position, target=rows[target])
        for row, tribute in zip(rows, arena.tributes, strict=True)
        for position, target in enumerate(tribute.grudges)
    )
    models.Debt.objects.bulk_create(
        models.Debt(tribute=row, position=position, target=rows[target])
        for row, tribute in zip(rows, arena.tributes, strict=True)
        for position, target in enumerate(tribute.debts)
    )
    models.TributeTag.objects.bulk_create(
        models.TributeTag(tribute=row, position=position, tag=tag)
        for row, tribute in zip(rows, arena.tributes, strict=True)
        for position, tag in enumerate(tribute.tags)
    )

    victor_rows = list(game.victors.order_by("position"))
    new_entries = arena.log[arena.saved_log_length :]
    lines = {(line.group, line.variant): line for line in content.StoryLine.objects.all()}
    entry_rows = models.LogEntry.objects.bulk_create(
        models.LogEntry(
            game=game,
            position=arena.saved_log_length + offset,
            style=entry.style,
            line=lines[entry.line],
            a=None if entry.a is None else rows[entry.a],
            b=None if entry.b is None else rows[entry.b],
            sponsor=None if entry.sponsor is None else rows[entry.sponsor],
            victor=None if entry.victor is None else victor_rows[entry.victor],
            item=item_rows[entry.item] if entry.item else None,
            n=entry.n,
        )
        for offset, entry in enumerate(new_entries)
    )
    models.LogEntryName.objects.bulk_create(
        models.LogEntryName(entry=entry_row, position=position, tribute=rows[tribute_id])
        for entry_row, entry in zip(entry_rows, new_entries, strict=True)
        for position, tribute_id in enumerate(entry.names)
    )
    arena.saved_log_length = len(arena.log)

    game.round, game.day = arena.round, arena.day
    game.alliance_count, game.feast_happened = arena.alliance_count, arena.feast_happened
    game.winner = rows[arena.winner.id] if arena.winner else None
    game.round_seed = None
    game.save()
    score_bets(game, arena, rows)
    if arena.winner and not game.rehearsal:
        history.record(game, arena, rows)


# ---------- playing a round ----------


def start_round(game):
    """Begins the next round. Returns what resume() returns."""
    game.round_seed = secrets.randbits(62)
    game.first_new_entry = game.log.count()
    current_answers(game).delete()
    game.save(update_fields=["round_seed", "first_new_entry", "updated_at"])
    record_round(game)
    return resume(game)


def record_round(game):
    """Remembers the round now starting, so Undo can play it again."""
    game.played_rounds.filter(number=game.round + 1).delete()
    played = models.PlayedRound.objects.create(game=game, number=game.round + 1, seed=game.round_seed)
    played.present_tributes.set(game.tributes.filter(present=True))
    played.present_victors.set(game.victors.filter(present=True))


def resume(game, catalogue=None):
    """Replays the round in progress as far as the saved answers allow.

    Returns (arena, decision). decision is None when the round is complete (and saved).
    Otherwise decision is the question waiting for an answer, and arena shows the story so far.
    """
    catalogue = catalogue or load_catalogue()
    answers = list(current_answers(game).values_list("choice", flat=True))
    cursor = iter(answers)

    def ask(decision):
        try:
            return next(cursor)
        except StopIteration:
            raise NeedAnswer(decision) from None

    arena = load_arena(game, catalogue, Dice(game.round_seed), ask)
    try:
        play_next_round(arena)
    except NeedAnswer as waiting:
        return arena, waiting.decision
    save_arena(game, arena)
    return arena, None


@transaction.atomic
def answer_decision(game, position, choice):
    """Saves a player's answer and carries on. Returns False if the answer does not fit the
    question now waiting (an old page, a double tap, an option that does not exist)."""
    if game.round_seed is None:
        return False
    answered = current_answers(game).count()
    arena, decision = resume(game)
    if decision is None or position != answered or not 0 <= choice < decision.option_count:
        return False
    models.Answer.objects.create(game=game, round=game.round + 1, position=answered, choice=choice)
    resume(game)
    return True


def answer_randomly(game, position):
    """The host lets the dice answer the question now waiting (someone left their phone)."""
    if game.round_seed is None:
        return False
    arena, decision = resume(game)
    if decision is None:
        return False
    return answer_decision(game, position, secrets.randbelow(decision.option_count))


def waiting_decision(game):
    """The question now waiting for an answer, or None."""
    if game.round_seed is None:
        return None
    return resume(game)[1]
