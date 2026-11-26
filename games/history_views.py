"""The hall of fame (the host's) and the shared recap of a finished Games (anyone with the link)."""

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from games import history
from games.models import PastGame
from games.views import with_game


@require_GET
@with_game
def hall_of_fame(request, game):
    return render(request, "games/hall.html", history.hall_of_fame(game))


@require_GET
def shared_recap(request, code):
    past = get_object_or_404(PastGame.objects.prefetch_related("tributes", "bet_scores"), share_code=code)
    return render(request, "games/shared_recap.html", {"past": past, "winner": past.winner})
