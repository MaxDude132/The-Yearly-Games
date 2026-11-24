"""Bets for the night: before each night, everyone in the room (tributes and past victors) may
guess who falls first. 3 points if right, 1 point if that tribute falls later in the night.

A bettor is a seat, as in players.py: (kind, row), where kind is players.TRIBUTE or
players.VICTOR and row is a Tribute or a PastVictor. Bets never change the game, only the score.
"""

from games import models
from games.engine.rounds import is_night_round
from games.players import TRIBUTE, VICTOR

FIRST_TO_FALL_POINTS = 3
FELL_THAT_NIGHT_POINTS = 1


def _bettor_field(kind):
    """The Bet field that holds this kind of seat."""
    return "victor" if kind == VICTOR else "bettor"


# ---------- placing bets ----------


def place_bets(game, bets):
    """Saves the bets the host entered for the coming night.
    bets: {(kind, position): target position}. Only players in the room bet, only on living
    tributes, and only before a night. Players with a phone bet on their phone (place_bet):
    the host's form leaves their bets alone."""
    coming = game.round + 1
    if not is_night_round(coming):
        return
    seats = {
        TRIBUTE: {row.position: row for row in game.tributes.all()},
        VICTOR: {row.position: row for row in game.victors.all()},
    }
    living = {position: row for position, row in seats[TRIBUTE].items() if row.alive}
    game.bets.filter(round=coming, bettor__phone_token="").delete()
    game.bets.filter(round=coming, victor__phone_token="").delete()

    new_bets = []
    for (kind, position), target in bets.items():
        row = seats.get(kind, {}).get(position)
        if row and row.present and not row.phone_token and target in living:
            new_bets.append(
                models.Bet(game=game, round=coming, target=living[target], **{_bettor_field(kind): row})
            )
    models.Bet.objects.bulk_create(new_bets)


def place_bet(game, kind, row, target_position):
    """One player's bet for the coming night, from their phone. target_position None: no bet."""
    coming = game.round + 1
    if not is_night_round(coming) or not row.present:
        return False
    target = game.tributes.filter(position=target_position, alive=True).first()
    game.bets.filter(round=coming, **{_bettor_field(kind): row}).delete()
    if target_position is not None and target is None:
        return False
    if target:
        models.Bet.objects.create(game=game, round=coming, target=target, **{_bettor_field(kind): row})
    return True


def coming_bet(game, kind, row):
    """The tribute this player bet on for the coming night, or None."""
    bet = (
        game.bets.filter(round=game.round + 1, **{_bettor_field(kind): row}).select_related("target").first()
    )
    return bet.target if bet else None


# ---------- scores ----------


def score_bets(game, arena, rows):
    """After a night: 3 points for the first to fall, 1 for anyone else who fell that night."""
    bets = list(game.bets.filter(round=arena.round, points=None))
    if not bets:
        return
    cannon = next(entry for entry in reversed(arena.log) if entry.style == "cannon")
    fallen = [rows[tribute_id].pk for tribute_id in cannon.names]
    for bet in bets:
        if fallen and bet.target_id == fallen[0]:
            bet.points = FIRST_TO_FALL_POINTS
        elif bet.target_id in fallen:
            bet.points = FELL_THAT_NIGHT_POINTS
        else:
            bet.points = 0
    models.Bet.objects.bulk_update(bets, ["points"])


def bet_scores(game):
    """[(kind, row, points)] for everyone who bet, best first (tributes before victors on a tie)."""
    totals = {}
    for bet in game.bets.exclude(points=None).select_related("bettor", "victor"):
        kind = VICTOR if bet.victor_id else TRIBUTE
        key = (kind, bet.player.pk)
        _kind, row, points = totals.get(key, (kind, bet.player, 0))
        totals[key] = (kind, row, points + bet.points)
    return sorted(totals.values(), key=lambda score: (-score[2], score[0] == VICTOR, score[1].position))
