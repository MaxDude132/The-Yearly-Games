"""Undo: the host takes back the last thing that happened.

- A question is open and someone already answered in this round: the last answer is taken back.
- A round was started and nobody answered yet: the round is called off (Continue plays a new one).
- Otherwise the last finished round is taken back. The game is played again from the gong,
  every round with its own seed, answers and who was in the room (PlayedRound), so it unfolds
  exactly as before, minus that round.
"""

from django.db import transaction

from games import models, services


class CannotReplay(Exception):
    """The saved rounds do not give back the same game."""


def can_undo(game):
    return game.status == models.Game.Status.PLAYING and (game.round_seed is not None or game.round > 0)


def undo(game):
    """Takes back the last answer or round. Returns False if there is nothing it can take back."""
    if not can_undo(game):
        return False
    if game.round_seed is not None:
        _take_back_answer_or_round_in_progress(game)
        return True
    try:
        with transaction.atomic():  # all or nothing: a failed replay leaves the game as it was
            _replay_without_last_round(game)
    except CannotReplay:
        game.refresh_from_db()
        return False
    return True


def _take_back_answer_or_round_in_progress(game):
    last_answer = services.current_answers(game).last()
    if last_answer:
        last_answer.delete()
        return
    game.played_rounds.filter(number=game.round + 1).delete()
    game.round_seed = None
    game.save(update_fields=["round_seed", "updated_at"])


def _replay_without_last_round(game):
    rounds = list(game.played_rounds.prefetch_related("present_tributes", "present_victors"))
    # shortcut: games started before Undo existed have no saved rounds and cannot be undone.
    if [played.number for played in rounds] != list(range(1, game.round + 1)):
        raise CannotReplay
    undone = rounds.pop()
    here_now = list(game.tributes.filter(present=True)), list(game.victors.filter(present=True))

    services.clear_arena(game)
    game.bets.update(points=None)  # scored again as the nights are replayed
    catalogue = services.load_catalogue()
    for played in rounds:
        _set_present(game, played.present_tributes.all(), played.present_victors.all())
        game.first_new_entry = game.log.count()
        game.round_seed = played.seed
        game.save(update_fields=["first_new_entry", "round_seed", "updated_at"])
        _arena, decision = services.resume(game, catalogue)
        if decision is not None:  # e.g. the story content changed since the round was played
            raise CannotReplay

    _set_present(game, *here_now)
    game.answers.filter(round=undone.number).delete()
    undone.delete()


def _set_present(game, tributes, victors):
    game.tributes.update(present=False)
    game.tributes.filter(pk__in=[row.pk for row in tributes]).update(present=True)
    game.victors.update(present=False)
    game.victors.filter(pk__in=[row.pk for row in victors]).update(present=True)
