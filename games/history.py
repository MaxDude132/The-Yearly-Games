"""History: every finished Games (never a rehearsal) is kept, for the shared recap and the hall
of fame. Names are copied when the Games ends, so renaming or removing someone later keeps history."""

import secrets

from django.db.models import Count, Max, Sum
from django.urls import reverse

from games import bets as bet_tools
from games import players
from games.models import PastBetScore, PastGame, PastTribute
from games.render import display_name, victor_display_name

TOP = 3  # how many names each hall of fame record lists


def record(game, arena, rows):
    """Keeps the Games that just ended: everyone's place, kills and bet points."""
    death_order = {tribute: order for order, tribute in enumerate(_fallen_in_order(arena))}
    others = [t for t in arena.tributes if t is not arena.winner]
    # The last to fall gets 2nd place. Not in a cannon line (the final duel's loser): fell last.
    others.sort(key=lambda t: death_order.get(t.id, len(death_order)), reverse=True)

    past = PastGame.objects.create(
        game=game, edition=next_edition(game), days=arena.day, share_code=secrets.token_urlsafe(6)
    )
    PastTribute.objects.bulk_create(
        PastTribute(
            past_game=past, place=place, name=display_name(rows[t.id]), district=rows[t.id].district,
            kills=t.kills, died_on_day=t.died_on_day,
        )
        for place, t in enumerate([arena.winner, *others], start=1)
    )  # fmt: skip
    PastBetScore.objects.bulk_create(
        PastBetScore(
            past_game=past,
            name=victor_display_name(row) if kind == players.VICTOR else display_name(row),
            points=points,
        )
        for kind, row, points in bet_tools.bet_scores(game)
    )
    return past


def _fallen_in_order(arena):
    return [tribute for entry in arena.log if entry.style == "cannon" for tribute in entry.names]


def next_edition(game):
    """The number of the Games being played: one more than the past victors' and past Games'."""
    victors = game.victors.aggregate(last=Max("edition"))["last"] or 0
    played = game.past_games.aggregate(last=Max("edition"))["last"] or 0
    return max(victors, played) + 1


def hall_of_fame(game):
    """Every victor by edition, and the records across all the Games played in the app."""
    winners = {past.edition: past for past in game.past_games.prefetch_related("tributes")}
    victors = [
        {"edition": past.edition, "year": past.finished_on.year, "name": past.winner.name,
         "kills": past.winner.kills, "share_code": past.share_code}
        for past in winners.values()
    ]  # fmt: skip
    victors += [
        {"edition": victor.edition, "year": victor.year, "name": victor_display_name(victor)}
        for victor in game.victors.exclude(edition=None)
        if victor.edition not in winners
    ]
    victors.sort(key=lambda victor: victor["edition"])

    results = PastTribute.objects.filter(past_game__game=game)
    bets = PastBetScore.objects.filter(past_game__game=game)
    return {
        "victors": victors,
        "most_wins": _most_wins(victors),
        "most_kills_in_one_games": results.filter(kills__gt=0)
        .order_by("-kills", "past_game__edition")
        .values("name", "kills", "past_game__edition")[:TOP],
        "most_kills_ever": results.values("name").annotate(total=Sum("kills")).filter(total__gt=0)
        .order_by("-total", "name")[:TOP],
        "best_bettors_ever": bets.values("name").annotate(total=Sum("points")).filter(total__gt=0)
        .order_by("-total", "name")[:TOP],
        "games_played": len(winners),
        "tributes_seen": results.values("name").annotate(n=Count("pk")).count(),
    }  # fmt: skip


def _most_wins(victors):
    """Names that won more than once, most wins first."""
    wins = {}
    for victor in victors:
        wins[victor["name"]] = wins.get(victor["name"], 0) + 1
    return sorted(((name, n) for name, n in wins.items() if n > 1), key=lambda pair: -pair[1])[:TOP]


def share_url(request, game):
    """The link to the recap of the Games that just ended, or None (a rehearsal, or not over)."""
    past = game.past_games.order_by("pk").last()
    if not game.winner_id or game.rehearsal or past is None:
        return None
    return request.build_absolute_uri(reverse("shared_recap", args=[past.share_code]))
