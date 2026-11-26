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

from games import bets as bet_tools
from games import players, services, undo
from games import roster as roster_tools
from games.engine.combat import strength_bonus
from games.engine.dice import Dice
from games.engine.rounds import is_night_round
from games.engine.state import Victor, alliance_leader, holds_grudge, owes_life, same_alliance
from games.models import Game
from games.render import Translator, current_language, display_name, ordinal, victor_display_name
from games.styles import STATUS_PILLS, story_classes

NEW = "?new=1"  # tells the page to open at the start of the newest round


def with_game(view):
    """Gives the view this browser's game, locked for the duration of the request.
    After a POST, open pages (the host's other tabs, the players' phones) are told to reload."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.session_key:
            request.session.create()
        with transaction.atomic():
            game = services.get_game(request.session.session_key)
            game = Game.objects.select_for_update().get(pk=game.pk)
            response = view(request, game, *args, **kwargs)
            if request.method == "POST":
                players.bump(game)
            return response

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
    victors = list(game.victors.order_by("position"))
    return render(
        request,
        "games/setup.html",
        {
            "rows": [{"tribute": row, "number": row.position + 1, "letters": _letters(row)} for row in rows],
            "victors": [
                {"victor": row, "number": row.position + 1, "letters": _victor_letters(row)}
                for row in victors
            ],
            "can_start": len(rows) >= services.MIN_TRIBUTES,
            "join": _join(request, game),
            "live_url": reverse("state"),
            "version": game.version,
            "voter_choices": [
                (Game.Voters.NOBODY, _("Nobody: the arena decides")),
                (Game.Voters.DEAD, _("The dead")),
                (Game.Voters.PAST_WINNERS, _("Past victors")),
                (Game.Voters.PAST_WINNERS_AND_DEAD, _("Past victors and the dead")),
                (Game.Voters.EVERYONE, _("Everyone in the room")),
            ],
            "game": game,
        },
    )


def _letters(row):
    return display_name(row).strip()[:2]


def _join(request, game):
    """The link and QR code players scan to join from their phones."""
    url = request.build_absolute_uri(reverse("play", args=[players.join_code(game)]))
    return {"url": url, "qr": mark_safe(players.qr_svg(url))}


def _victor_letters(row):
    return victor_display_name(row).strip()[:2]


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
    victor_rows = list(game.victors.order_by("position"))
    victor_names = {row.position: victor_display_name(row) for row in victor_rows}
    victor_name_of = victor_names.get  # None for a victor removed since (the story then leaves a blank)
    night = is_night_round(arena.round)

    show_new = decision is not None or "new" in request.GET
    first_new = game.first_new_entry if show_new else len(arena.log)
    entries = [
        {
            "index": index,
            "classes": story_classes(entry.style, index >= first_new),
            "heading": entry.style.startswith("heading"),
            "html": translator.story(entry, name_of, victor_name_of=victor_name_of),
            "fallen": _fallen(entry, rows, names) if index >= first_new else [],
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
            "round": arena.round,
            "alive_count": len(arena.living()),
            "total": len(arena.tributes),
            "entries": entries,
            "first_new": first_new,
            "cards": cards,
            "victors": [
                {
                    "victor": row,
                    "name": victor_names[row.position],
                    "letters": _victor_letters(row),
                    "year": row.year,
                    "games": _("%(nth)s Games") % {"nth": ordinal(row.edition, current_language())}
                    if row.edition
                    else "",
                    "present": row.present,
                }
                for row in victor_rows
            ],  # fmt: skip
            "main_button": main_button,
            "round_waiting": decision is not None,
            "decision": _decision_context(decision, rows, victor_rows, translator, names, game, arena),
            "bets": _bet_form(game, arena, decision, rows, names, victor_rows),
            "scores": _scores(game, names, victor_names),
            "recap": _recap(arena, translator, name_of, victor_name_of) if arena.winner else None,
            "confirm_quit": "confirm_quit" in request.GET,
            "can_undo": undo.can_undo(game),
            "rehearsal": game.rehearsal,
            "join": _join(request, game),
            "live_url": reverse("state"),
            "version": game.version,
        },
    )


FALLEN_STAGGER = 0.8  # seconds between two faces in the sky (and two cannon shots, see app.js)


def _fallen(entry, rows, names):
    """The faces shown in the sky under a round's cannon line, one after the other."""
    if entry.style != "cannon":
        return []
    return [
        {
            "tribute": rows[position],
            "letters": _letters(rows[position]),
            "name": names[position],
            "district": rows[position].district,
            "delay": f"{order * FALLEN_STAGGER:.1f}",
        }
        for order, position in enumerate(entry.names)
    ]


def _goal_labels():  # a function, so the labels follow the viewer's language
    return {"hunt": _("Hunting"), "hide": _("Hiding"), "scavenge": _("Scavenging"), "guard": _("With allies")}


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
    if tribute.alive and tribute.goal:
        details.append(_goal_labels()[tribute.goal])
    if tribute.alliance:
        alliance = f"{escape(_('Alliance'))} {tribute.alliance}"
        if tribute.alive and alliance_leader(arena, tribute.alliance) is tribute:
            alliance += f" ({escape(_('leader'))})"
        details.append(mark_safe(f'<span class="text-moon">{alliance}</span>'))
    if tribute.kills:
        details.append(f"{tribute.kills} {_('kills')}")
    if tribute.alive and tribute.tags:
        details.append(mark_safe(f'<span class="text-gold">{escape(", ".join(_tag_labels(tribute)))}</span>'))
    if tribute.alive and enemy_names:
        details.append(f"{_('Grudge against')} {', '.join(enemy_names)}")
    if tribute.alive and tribute.debts:
        details.append(f"{_('Owes a life to')} {', '.join(names[i] for i in tribute.debts)}")

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


def _decision_context(decision, rows, victor_rows, translator, names, game, arena):
    if decision is None:
        return None
    by_victor = isinstance(decision.tribute, Victor)
    if by_victor:
        row = victor_rows[decision.tribute.id]
        name, letters = victor_display_name(row), _victor_letters(row)
    else:
        row = rows[decision.tribute.id]
        name, letters = names[row.position], _letters(row)
    victor_names = {victor.position: victor_display_name(victor) for victor in victor_rows}
    if decision.vote_total and not decision.vote_for:
        label = _("The fallen vote: %(number)s of %(total)s") % {
            "number": decision.vote_number, "total": decision.vote_total,
        }  # fmt: skip
    elif decision.vote_for:
        label = _("Vote %(number)s of %(total)s, for %(name)s") % {
            "number": decision.vote_number, "total": decision.vote_total, "name": names[decision.vote_for.id],
        }  # fmt: skip
    elif decision.for_whole_arena:
        label = _("Decides for the whole arena")
    elif by_victor:
        label = _("Past victor")
    elif decision.tribute.alive:
        label = _("Decision for")
    else:
        label = _("Fallen, still playing")
    return {
        "label": label,
        "tribute": row,
        "name": name,
        "letters": letters,
        "question": translator.question_text(decision, names.__getitem__, victor_name_of=victor_names.get),
        "options": list(enumerate(_option_labels(decision, arena, translator, names))),
        "facts": _decision_facts(decision, arena, translator, names),
        "position": services.current_answers(game).count(),
        "on_phone": bool(row.phone_token),  # the player can also answer on their phone
    }


def _tag_labels(tribute):
    labels = {
        "feared": _("Feared"),
        "hidden": _("Hidden"),
        "betrayer": _("Betrayer"),
        "merciful": _("Merciful"),
        "trusted": _("Trusted"),
    }
    return [labels[tag] for tag in tribute.tags if tag in labels]  # an unknown tag is not shown


def _status(tribute):
    return _("Wounded") if tribute.wounded else _("Healthy")


def _option_labels(decision, arena, translator, names):
    """The buttons of a question. A sponsor gift offers tributes, each shown with its condition."""
    labels = translator.option_labels(decision, names.__getitem__)
    if not decision.option_tributes:
        return labels
    pairs = zip(labels, decision.option_tributes, strict=True)
    return [f"{label} · {_status(tribute)}" for label, tribute in pairs]


def _person(tribute, translator, names):
    items = ", ".join(translator.items[item.key] for item in tribute.items)
    return {
        "name": names[tribute.id],
        "status": _status(tribute),
        "tags": ", ".join(_tag_labels(tribute)),
        "items": _("Carries: %(items)s") % {"items": items} if items else _("Carries nothing"),
    }


def _decision_facts(decision, arena, translator, names):
    """What the player needs to know to choose: how the tributes involved are doing, how they
    relate to each other, and how many are left."""
    me = decision.vote_for or decision.tribute
    other = next((t for t in (decision.a, decision.b) if t is not None and t is not me), None)
    people, relations = [], []
    if not isinstance(me, Victor) and me.alive and not decision.for_whole_arena:
        people.append(_person(me, translator, names))
        if other:
            people.append(_person(other, translator, names))
            if same_alliance(me, other):
                relations.append(_("Allies."))
            for holder, target in ((me, other), (other, me)):
                if holds_grudge(holder, target):
                    relations.append(
                        _("%(holder)s holds a grudge against %(target)s.")
                        % {"holder": names[holder.id], "target": names[target.id]}
                    )
            if me.district == other.district:
                relations.append(_("Same district."))
            for debtor, benefactor in ((me, other), (other, me)):
                if owes_life(debtor, benefactor):
                    relations.append(
                        _("%(debtor)s owes %(benefactor)s a life.")
                        % {"debtor": names[debtor.id], "benefactor": names[benefactor.id]}
                    )
            relations.append(_fight_hint(me, other, names))
        if me.alliance:
            size = len([t for t in arena.living() if t.alliance == me.alliance])
            relations.append(
                _("%(name)s is in an alliance of %(count)s.") % {"name": names[me.id], "count": size}
            )
    relations.append(_("Tributes left: %(count)s") % {"count": len(arena.living())})
    if decision.question == "goal" and arena.rumour:
        relations.append(_rumour_hints()[arena.rumour])
    return {"people": people, "relations": relations}


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
    elif action == "add-victor":
        roster_tools.add_victor(game)
    elif action.startswith("remove-victor-") and action[14:].isdigit():
        roster_tools.remove_victor(game, int(action[14:]))
    elif action.startswith("release-victor-") and action[15:].isdigit():
        players.release(game, players.VICTOR, int(action[15:]))
    elif action.startswith("release-") and action[8:].isdigit():
        players.release(game, players.TRIBUTE, int(action[8:]))
    elif action == "start":
        services.start_game(game)
    elif action == "rehearse":
        services.start_game(game, rehearsal=True)
    return redirect("index")


@require_POST
@with_game
def next_round(request, game):
    if game.status != Game.Status.PLAYING or game.round_seed is not None:
        return redirect("index")
    if game.winner_id:
        services.reset_game(game)  # "New game": back to the setup screen
        return redirect("index")
    bet_tools.place_bets(game, _posted_bets(request.POST))
    services.start_round(game)
    return _home_new()


@require_POST
@with_game
def decision(request, game):
    position, choice = request.POST.get("position", ""), request.POST.get("choice", "")
    if game.status == Game.Status.PLAYING and position.isdigit():
        if choice == "random":  # "Let the dice decide": the player is not answering on their phone
            services.answer_randomly(game, int(position))
        elif choice.isdigit():
            services.answer_decision(game, int(position), int(choice))
    return _home_new()


@require_POST
@with_game
def skip_to_the_end(request, game):
    """Rehearsal only: plays the rest of the game at once, to see the recap."""
    if game.status == Game.Status.PLAYING and game.rehearsal:
        services.skip_to_the_end(game)
    return redirect("index")


@require_POST
@with_game
def undo_last(request, game):
    """Takes back the last answer or the last round (see undo.py)."""
    undo.undo(game)
    return _home_new()


@require_GET
def state(request):
    """The game's version number, for app.js to know when to reload. Light: no lock, no game made."""
    game = Game.objects.filter(session_key=request.session.session_key or "").first()
    return JsonResponse({"version": game.version if game else 0})


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


@require_POST
@with_game
def set_victor_present(request, game, position):
    """Ticks or unticks "here" for a past victor during the game (not while a question is open)."""
    if game.round_seed is not None:
        return JsonResponse({"error": "a question is open"}, status=409)
    updated = game.victors.filter(position=position).update(present=request.POST.get("present") == "1")
    return HttpResponse(status=204 if updated else 404)


# ---------- bets and the recap ----------
# A bet field in the host's form is named after the seat: "bet-3" for tribute 3,
# "victor-bet-0" for past victor 0.
BET_FIELD_PREFIXES = {"bet-": players.TRIBUTE, "victor-bet-": players.VICTOR}


def _bet_field(kind, position):
    return f"{'victor-bet' if kind == players.VICTOR else 'bet'}-{position}"


def _posted_bets(post):
    """{(kind, position): target position} from the host's bet fields. Empty fields are no bet."""
    bets = {}
    for key, value in post.items():
        for prefix, kind in BET_FIELD_PREFIXES.items():
            position = key.removeprefix(prefix)
            if key.startswith(prefix) and position.isdigit() and value.isdigit():
                bets[(kind, int(position))] = int(value)
    return bets


def _bet_form(game, arena, decision, rows, names, victor_rows):
    """Before a night (not the final duel), each player in the room may bet on who falls first:
    the tributes in the room, then the past victors in the room."""
    living = arena.living()
    if decision is not None or arena.winner or not arena.round or len(living) <= 2:
        return None
    if not is_night_round(arena.round + 1):
        return None
    seats = [(players.TRIBUTE, row, names[row.position]) for row in rows if row.present]
    seats += [(players.VICTOR, row, victor_display_name(row)) for row in victor_rows if row.present]
    if not seats:
        return None

    def bettor(kind, row, name):
        entry = {"field": _bet_field(kind, row.position), "name": name, "on_phone": bool(row.phone_token)}
        if row.phone_token:
            target = bet_tools.coming_bet(game, kind, row)
            entry["bet"] = names[target.position] if target else None
        return entry

    return {
        "bettors": [bettor(kind, row, name) for kind, row, name in seats],
        "targets": [{"position": t.id, "name": names[t.id]} for t in living],
    }


def _scores(game, names, victor_names):
    """The bet scores so far, best first, with each player's name."""
    return [
        {
            "name": victor_names[row.position] if kind == players.VICTOR else names[row.position],
            "points": points,
        }
        for kind, row, points in bet_tools.bet_scores(game)
    ]


# Story lines worth repeating in the recap: the moments where the story turned.
RECAP_GROUPS = (
    "alliance.betrayal", "combat.spared", "combat.debt_repaid", "reputation.feared", "arena.shielded",
    "bounty.placed", "encounter.mercy_wins_over", "encounter.cold_handshake", "encounter.trust_wins_over",
    "reputation.trusted", "act.manhunt", "alliance.raid", "arena.fallen_vote",
)  # fmt: skip


def _recap(arena, translator, name_of, victor_name_of):
    """The end of the game: the victor's kills and the turning points of the story."""
    winner = arena.winner.id
    moments = [
        translator.story(entry, name_of, victor_name_of=victor_name_of)
        for entry in arena.log
        if entry.line.group in RECAP_GROUPS
        or entry.line.group.startswith("callback.")
        or (entry.style == "death" and entry.a == winner)
    ]
    deadliest = max(arena.tributes, key=lambda tribute: tribute.kills)
    return {
        "winner": name_of(winner),
        "winner_kills": arena.winner.kills,
        "deadliest": name_of(deadliest.id) if deadliest.kills else None,
        "deadliest_kills": deadliest.kills,
        "moments": moments,
    }


# ---------- hints in the pop-up ----------
FIGHT_HINT_MARGIN = 0.2  # about the bonus of a weapon: enough to call a fight one-sided


def _fight_hint(me, other, names):
    """In plain words, who would likely win a fight (luck still decides)."""
    gap = strength_bonus(me) - strength_bonus(other)
    if gap >= FIGHT_HINT_MARGIN:
        return _("In a fight, %(name)s would likely have the upper hand.") % {"name": names[me.id]}
    if gap <= -FIGHT_HINT_MARGIN:
        return _("In a fight, %(name)s would likely be at a disadvantage.") % {"name": names[me.id]}
    return _("A fight between them would be close.")


def _rumour_hints():  # a function, so the hints follow the viewer's language
    return {
        "supplies": _("Today's rumour favours scavenging."),
        "hunters": _("Today's rumour favours hiding, and hunters will find more prey."),
        "storm": _("Today's rumour favours staying with allies."),
    }
