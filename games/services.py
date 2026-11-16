"""Moves a game between the database and the engine, and runs rounds.

A round that needs a player's answer cannot wait inside a web request. Instead the round is
replayed from the start every time: same dice seed, same saved answers, so it unfolds the same
way until it reaches the first question that has no answer yet. Nothing is written to the story
until the round is complete.
"""

import secrets

from django.db import transaction

from content import models as content
from games import models
from games.engine.catalogue import ArenaEvent, Catalogue, Item, Line
from games.engine.dice import Dice
from games.engine.rounds import play_next_round
from games.engine.state import Arena, Entry, NeedAnswer
from games.engine.state import Tribute as EngineTribute

DEFAULT_TRIBUTE_COUNT = 24
MIN_TRIBUTES = 2


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


def start_game(game):
    """Leaves the setup screen. Returns False if there are too few tributes."""
    if game.tributes.count() < MIN_TRIBUTES:
        return False
    game.status = models.Game.Status.PLAYING
    game.first_new_entry = 0
    game.save(update_fields=["status", "first_new_entry", "updated_at"])
    return True


@transaction.atomic
def reset_game(game):
    """Back to the setup screen. The roster (names, photos, who is here) is kept."""
    game.log.all().delete()
    game.answers.all().delete()
    models.TributeItem.objects.filter(tribute__game=game).delete()
    models.Grudge.objects.filter(tribute__game=game).delete()
    game.tributes.update(alive=True, wounded=False, alliance=0, kills=0, died_on_day=0)
    game.status = models.Game.Status.SETUP
    game.round = game.day = game.alliance_count = game.first_new_entry = 0
    game.feast_happened = False
    game.winner = None
    game.round_seed = None
    game.save()


# ---------- database to engine and back ----------


def load_arena(game, catalogue, dice, ask):
    rows = list(game.tributes.order_by("position"))
    id_of = {row.pk: row.position for row in rows}
    tributes = [
        EngineTribute(
            id=row.position,
            present=row.present,
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
    )  # fmt: skip


@transaction.atomic
def save_arena(game, arena):
    """Writes the state after a completed round."""
    item_rows = {item.key: item for item in content.Item.objects.all()}
    rows = list(game.tributes.order_by("position"))
    for row, tribute in zip(rows, arena.tributes, strict=True):
        row.alive, row.wounded, row.alliance = tribute.alive, tribute.wounded, tribute.alliance
        row.kills, row.died_on_day = tribute.kills, tribute.died_on_day
    models.Tribute.objects.bulk_update(rows, ["alive", "wounded", "alliance", "kills", "died_on_day"])

    models.TributeItem.objects.filter(tribute__game=game).delete()
    models.Grudge.objects.filter(tribute__game=game).delete()
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
    game.answers.all().delete()


# ---------- playing a round ----------


def start_round(game):
    """Begins the next round. Returns what resume() returns."""
    game.round_seed = secrets.randbits(62)
    game.first_new_entry = game.log.count()
    game.answers.all().delete()
    game.save(update_fields=["round_seed", "first_new_entry", "updated_at"])
    return resume(game)


def resume(game, catalogue=None):
    """Replays the round in progress as far as the saved answers allow.

    Returns (arena, decision). decision is None when the round is complete (and saved).
    Otherwise decision is the question waiting for an answer, and arena shows the story so far.
    """
    catalogue = catalogue or load_catalogue()
    answers = list(game.answers.order_by("position").values_list("choice", flat=True))
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
    answered = game.answers.count()
    arena, decision = resume(game)
    if decision is None or position != answered or not 0 <= choice < decision.option_count:
        return False
    models.Answer.objects.create(game=game, position=answered, choice=choice)
    resume(game)
    return True
