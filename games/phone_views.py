"""The pages a player sees on their own phone after scanning the QR code: choose a seat, then
answer their own questions, see their character and bet on the night. The host's screen keeps
working as before (views.py): the host can still answer for anyone."""

from functools import wraps

from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from games import bets as bet_tools
from games import phone_extras, players, services, views
from games.engine.dice import Dice
from games.engine.rounds import is_night_round
from games.engine.state import Victor
from games.models import Game
from games.render import Translator, current_language, display_name, ordinal, victor_display_name


def with_join_game(view):
    """Gives the view the game of this join code, locked for the duration of the request.
    After a POST, the host's screen and the other phones are told to reload."""

    @wraps(view)
    def wrapper(request, code, *args, **kwargs):
        with transaction.atomic():
            game = Game.objects.select_for_update().filter(join_code=code).first()
            if game is None:
                raise Http404("No game with this code")
            response = view(request, game, *args, **kwargs)
            if request.method == "POST":
                players.bump(game)
            return response

    return wrapper


def _home(game):
    return redirect("play", code=game.join_code)


# ---------- the page ----------


@require_GET
@with_join_game
def play(request, game):
    kind, row = players.my_seat(game, request.session)
    if row is None:
        return _choose_seat_page(request, game)
    if game.status == Game.Status.SETUP:
        return render(request, "games/play.html", _base(game, kind, row) | {"waiting_to_start": True})
    return _playing_page(request, game, kind, row)


def _base(game, kind, row):
    name = victor_display_name(row) if kind == players.VICTOR else display_name(row)
    return {
        "game": game,
        "seat": row,
        "is_victor": kind == players.VICTOR,
        "name": name,
        "letters": name.strip()[:2],
        "live_url": f"/play/{game.join_code}/state/",
        "version": game.version,
    }


def _choose_seat_page(request, game):
    """Step 1: the free tributes and past victors. Step 2 (?pick=tribute-3): name and photo."""
    picked = None
    kind, _sep, position = request.GET.get("pick", "").partition("-")
    if kind in (players.TRIBUTE, players.VICTOR) and position.isdigit():
        row = players.seat_rows(game, kind).filter(position=int(position), phone_token="").first()
        if row:
            label = victor_display_name(row) if kind == players.VICTOR else display_name(row)
            picked = {"kind": kind, "row": row, "label": label}
    tributes = [
        {
            "key": f"{players.TRIBUTE}-{row.position}",
            "name": display_name(row),
            "district": row.district,
            "row": row,
        }
        for row in players.free_seats(game, players.TRIBUTE)
    ]
    victors = [
        {"key": f"{players.VICTOR}-{row.position}", "name": victor_display_name(row), "row": row}
        for row in players.free_seats(game, players.VICTOR)
    ]
    return render(
        request,
        "games/play_join.html",
        {
            "game": game, "picked": picked, "tributes": tributes, "victors": victors,
            "live_url": f"/play/{game.join_code}/state/", "version": game.version,
        },
    )  # fmt: skip


def _playing_page(request, game, kind, row):
    catalogue = services.load_catalogue()
    if game.round_seed is None:
        arena, decision = services.load_arena(game, catalogue, Dice(), views._no_answers), None
    else:
        arena, decision = services.resume(game, catalogue)

    translator = Translator(current_language())
    rows = list(game.tributes.order_by("position"))
    names = {r.position: display_name(r) for r in rows}
    victor_rows = list(game.victors.order_by("position"))
    context = _base(game, kind, row)

    if kind == players.TRIBUTE:
        tribute = arena.tributes[row.position]
        victor_names = {r.position: victor_display_name(r) for r in victor_rows}
        context["card"] = views._card(row, tribute, arena, translator, names)
        context["allies"] = phone_extras.allies(arena, tribute, names)
        context["my_story"] = phone_extras.my_story(arena, tribute, translator, names, victor_names)
    elif row.edition:
        context["victor_games"] = _("%(nth)s Games") % {"nth": ordinal(row.edition, current_language())}

    context["powers"] = phone_extras.powers(game, kind, row, arena)

    if players.decides(decision, kind, row):
        context["decision"] = views._decision_context(
            decision, rows, victor_rows, translator, names, game, arena
        )
    elif decision is not None:
        waiting_for = decision.tribute
        if isinstance(waiting_for, Victor):
            context["waiting_for"] = victor_display_name(victor_rows[waiting_for.id])
        else:
            context["waiting_for"] = names[waiting_for.id]

    if row.present:  # tributes and past victors in the room both bet
        bets = views._bet_form(game, arena, decision, rows, names, victor_rows)
        if bets:
            target = bet_tools.coming_bet(game, kind, row)
            context["bets"] = {"targets": bets["targets"], "current": target.position if target else None}

    context.update(
        {
            "title": translator.phase(arena.round, arena.day, is_night_round(arena.round))
            if arena.round
            else "",
            "is_night": is_night_round(arena.round),
            "alive_count": len(arena.living()),
            "total": len(arena.tributes),
            "winner": names[arena.winner.id] if arena.winner else None,
            "i_won": arena.winner is not None and kind == players.TRIBUTE and arena.winner.id == row.position,
        }
    )
    return render(request, "games/play.html", context)


# ---------- actions ----------


@require_POST
@with_join_game
def join(request, game):
    kind, position = request.POST.get("kind", ""), request.POST.get("position", "")
    if kind in (players.TRIBUTE, players.VICTOR) and position.isdigit():
        players.take_seat(
            game,
            request.session,
            kind,
            int(position),
            request.POST.get("name", ""),
            request.FILES.get("photo"),
        )
    return _home(game)


@require_POST
@with_join_game
def leave(request, game):
    players.leave_seat(game, request.session)
    return _home(game)


@require_POST
@with_join_game
def decision(request, game):
    """Answers the waiting question, only if this phone's seat is the one asked."""
    kind, row = players.my_seat(game, request.session)
    position, choice = request.POST.get("position", ""), request.POST.get("choice", "")
    if row and position.isdigit() and choice.isdigit():
        if players.decides(services.waiting_decision(game), kind, row):
            services.answer_decision(game, int(position), int(choice))
    return _home(game)


@require_POST
@with_join_game
def bet(request, game):
    kind, row = players.my_seat(game, request.session)
    target = request.POST.get("target", "")
    if row and services.waiting_decision(game) is None:
        bet_tools.place_bet(game, kind, row, int(target) if target.isdigit() else None)
    return _home(game)


@require_GET
def state(request, code):
    """The game's version number, for app.js to know when to reload."""
    game = Game.objects.filter(join_code=code).first()
    if game is None:
        raise Http404("No game with this code")
    return JsonResponse({"version": game.version})
