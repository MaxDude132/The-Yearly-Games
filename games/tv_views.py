"""The TV screen at /tv/<join code>/: the story in big letters for the whole room, the faces of
the fallen, whose turn it is, the recap and the QR code. Nothing to press: the host plays from
their own screen and the TV follows (it checks for changes like the phones do)."""

from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from games import views
from games.models import Game
from games.phone_views import with_join_game


@require_GET
@with_join_game
def tv(request, game):
    extra = {"tv": True, "live_url": reverse("play_state", args=[game.join_code])}
    if game.status == Game.Status.SETUP:
        context = {
            "title": _("The Yearly Games"),
            "join": views._join(request, game),
            "version": game.version,
        }
        return render(request, "games/tv.html", context | extra | {"waiting": True})
    return views._game_page(request, game, template="games/tv.html", **extra)
