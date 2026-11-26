"""More about yourself on your phone: your living allies, the last story lines about your tribute,
and what you can still do in the Games (for the fallen and past victors)."""

from django.utils.translation import gettext as _

from games import players
from games.engine.state import alliance_members
from games.models import Game

MY_STORY_LINES = 5  # the newest lines about my tribute

VOTES_OF_THE_DEAD = (Game.Voters.DEAD, Game.Voters.PAST_WINNERS_AND_DEAD, Game.Voters.EVERYONE)
VOTES_OF_VICTORS = (Game.Voters.PAST_WINNERS, Game.Voters.PAST_WINNERS_AND_DEAD, Game.Voters.EVERYONE)


def allies(arena, tribute, names):
    """The names of my living allies."""
    if not tribute.alive or not tribute.alliance:
        return []
    return [names[t.id] for t in alliance_members(arena, tribute.alliance) if t is not tribute and t.alive]


def my_story(arena, tribute, translator, names, victor_names):
    """The newest story lines that name my tribute, oldest first."""
    mine = [
        entry for entry in arena.log
        if tribute.id in (entry.a, entry.b, entry.sponsor) or tribute.id in entry.names
    ][-MY_STORY_LINES:]  # fmt: skip
    return [translator.story(entry, names.__getitem__, victor_name_of=victor_names.get) for entry in mine]


def powers(game, kind, row, arena):
    """What this player can still do, in plain words. Empty for a living tribute: their questions say it."""
    if not row.present:
        return []
    if kind == players.VICTOR:
        can = [_("Send sponsor gifts to the tributes you choose.")]
        if game.voters in VOTES_OF_VICTORS:
            can.append(_("Vote for tributes who are not in the room when they face a big decision."))
    elif arena.tributes[row.position].alive:
        return []
    else:
        can = [
            _("Choose the disasters that hit the arena, and shield a tribute from them."),
            _("Put a bounty on a living tribute."),
        ]
        if not any(victor.present for victor in arena.victors):
            can.append(_("Send sponsor gifts to the tributes you choose."))
        if game.voters in VOTES_OF_THE_DEAD:
            can.append(_("Vote for tributes who are not in the room when they face a big decision."))
    return [*can, _("Bet on who falls first each night.")]
