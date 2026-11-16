"""The pages. Every action is a plain form POST that redirects back to the one page (/)."""

from functools import wraps

from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from games import roster as roster_tools
from games import services
from games.engine.dice import Dice
from games.engine.rounds import is_night_round
from games.models import Game
from games.render import Translator, current_language, display_name
from games.styles import STATUS_PILLS, story_classes

NEW = "?new=1"  # tells the page to open at the start of the newest round


def with_game(view):
    """Gives the view this browser's game, locked for the duration of the request."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.session_key:
            request.session.create()
        with transaction.atomic():
            game = services.get_game(request.session.session_key)
            game = Game.objects.select_for_update().get(pk=game.pk)
            return view(request, game, *args, **kwargs)

    return wrapper


def _home_new():
    return redirect(reverse("index") + NEW)


def _no_answers(decision):  # the engine is only used to read the state here, so it never asks
    raise AssertionError("a round must not run on a page view without a saved seed")


# ---------- the page ----------


@require_GET
@with_game
def index(request, game):
    if game.status == Game.Status.SETUP:
        return _setup_page(request, game)
    return _game_page(request, game)


def _setup_page(request, game):
    rows = list(game.tributes.order_by("position"))
    return render(
        request,
        "games/setup.html",
        {
            "rows": [{"tribute": row, "number": row.position + 1, "letters": _letters(row)} for row in rows],
            "can_start": len(rows) >= services.MIN_TRIBUTES,
        },
    )


def _letters(row):
    return display_name(row).strip()[:2]


def _game_page(request, game):
    catalogue = services.load_catalogue()
    if game.round_seed is None:
        arena, decision = services.load_arena(game, catalogue, Dice(), _no_answers), None
    else:
        arena, decision = services.resume(game, catalogue)
        if decision is None:  # the round just completed (another tab answered the last question)
            return _home_new()

    translator = Translator(current_language())
    rows = list(game.tributes.order_by("position"))
    names = {row.position: display_name(row) for row in rows}
    name_of = names.__getitem__
    night = is_night_round(arena.round)

    show_new = decision is not None or "new" in request.GET
    first_new = game.first_new_entry if show_new else len(arena.log)
    entries = [
        {
            "index": index,
            "classes": story_classes(entry.style, index >= first_new),
            "heading": entry.style.startswith("heading"),
            "html": translator.story(entry, name_of),
        }
        for index, entry in enumerate(arena.log)
    ]

    cards = [_card(row, arena.tributes[row.position], arena, translator, names) for row in rows]
    cards.sort(key=lambda card: (not card["alive"], -card["died_on_day"]))

    if arena.winner:
        main_button = _("New game")
    elif arena.round:
        main_button = _("Continue")
    else:
        main_button = _("Sound the gong")

    return render(
        request,
        "games/game.html",
        {
            "title": translator.phase(arena.round, arena.day, night)
            if arena.round
            else _("The Yearly Games"),
            "is_night": night,
            "alive_count": len(arena.living()),
            "total": len(arena.tributes),
            "entries": entries,
            "first_new": first_new,
            "cards": cards,
            "main_button": main_button,
            "round_waiting": decision is not None,
            "decision": _decision_context(decision, rows, translator, names, game),
            "confirm_quit": "confirm_quit" in request.GET,
        },
    )


def _card(row, tribute, arena, translator, names):
    if not tribute.alive:
        when = translator.phase(1 if not tribute.died_on_day else 2, tribute.died_on_day, False)
        status = ("dead", mark_safe(f"{escape(_('dead'))} · {when}"))
    elif tribute.wounded:
        status = ("wounded", _("wounded"))
    else:
        status = ("", _("alive"))

    enemy_names = [names[i] for i in tribute.grudges if arena.tributes[i].alive]
    details = [f"{_('District')} {row.district}"]
    if tribute.alliance:
        alliance = f"{escape(_('Alliance'))} {tribute.alliance}"
        details.append(mark_safe(f'<span class="text-moon">{alliance}</span>'))
    if tribute.kills:
        details.append(f"{tribute.kills} {_('kills')}")
    if tribute.alive and enemy_names:
        details.append(f"{_('Grudge against')} {', '.join(enemy_names)}")

    return {
        "tribute": row,
        "name": names[row.position],
        "letters": _letters(row),
        "alive": tribute.alive,
        "died_on_day": tribute.died_on_day,
        "present": tribute.present,
        "status_classes": STATUS_PILLS[status[0]],
        "status_text": status[1],
        "items": [translator.items[item.key] for item in tribute.items] if tribute.alive else [],
        "details": details,
    }


def _decision_context(decision, rows, translator, names, game):
    if decision is None:
        return None
    row = rows[decision.tribute.id]
    if decision.for_whole_arena:
        label = _("Decides for the whole arena")
    elif decision.tribute.alive:
        label = _("Decision for")
    else:
        label = _("Fallen, still playing")
    return {
        "label": label,
        "tribute": row,
        "name": names[row.position],
        "letters": _letters(row),
        "question": translator.question_text(decision, names.__getitem__),
        "options": list(enumerate(translator.option_labels(decision, names.__getitem__))),
        "position": game.answers.count(),
    }


# ---------- health check (Railway calls it before switching traffic to a new deploy) ----------


@require_GET
def health(request):
    """200 when the app runs and reaches its database. Does not touch the session."""
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")


# ---------- actions ----------


@require_POST
@with_game
def roster(request, game):
    if game.status != Game.Status.SETUP:
        return redirect("index")
    roster_tools.save_roster(game, request.POST, request.FILES)
    action = request.POST.get("action", "save")
    if action == "add":
        roster_tools.add_tribute(game)
    elif action.startswith("remove-") and action[7:].isdigit():
        roster_tools.remove_tribute(game, int(action[7:]))
    elif action == "start":
        services.start_game(game)
    return redirect("index")


@require_POST
@with_game
def next_round(request, game):
    if game.status != Game.Status.PLAYING or game.round_seed is not None:
        return redirect("index")
    if game.winner_id:
        services.reset_game(game)  # "New game": back to the setup screen
        return redirect("index")
    services.start_round(game)
    return _home_new()


@require_POST
@with_game
def decision(request, game):
    position, choice = request.POST.get("position", ""), request.POST.get("choice", "")
    if game.status == Game.Status.PLAYING and position.isdigit() and choice.isdigit():
        services.answer_decision(game, int(position), int(choice))
    return _home_new()


@require_POST
@with_game
def quit_game(request, game):
    services.reset_game(game)
    return redirect("index")


@require_POST
@with_game
def set_present(request, game, position):
    """Ticks or unticks "here" for a tribute during the game (not while a question is open)."""
    if game.round_seed is not None:
        return JsonResponse({"error": "a question is open"}, status=409)
    updated = game.tributes.filter(position=position).update(present=request.POST.get("present") == "1")
    return HttpResponse(status=204 if updated else 404)
