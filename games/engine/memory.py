"""The story remembers. When one tribute kills another, the arena looks back through the story
for something that happened between the two and, if it finds something, tells a callback line.
No dice are used here, so this never changes who wins: it only adds a sentence.
"""

# The callbacks in order of importance: the first one that matches is told.
CALLBACK_GROUPS = [
    "callback.betrayal_avenged",
    "callback.betrayal_finished",
    "callback.theft_repaid",
    "callback.mercy_repaid",
    "callback.former_allies",
    "callback.unfinished_business",
    "callback.district_partners",
]


def told(arena, group, a, b):
    """True if the story already told a line of this group with a as {a} and b as {b}."""
    return any(entry.line.group == group and entry.a == a.id and entry.b == b.id for entry in arena.log)


def callback_for(arena, killer, victim):
    """The callback group that fits this kill, or None."""
    if told(arena, "alliance.betrayal", victim, killer):
        return "callback.betrayal_avenged"  # the victim once betrayed the killer
    if told(arena, "alliance.betrayal", killer, victim):
        return "callback.betrayal_finished"  # the killer once betrayed the victim
    if any(told(arena, group, victim, killer) for group in ("encounter.steals", "encounter.caught_stealing")):
        return "callback.theft_repaid"  # the victim once robbed the killer
    if told(arena, "encounter.leaves_sleeper", victim, killer):
        return "callback.mercy_repaid"  # the victim once walked away from the killer asleep
    if told(arena, "encounter.alliance_formed", killer, victim) or told(
        arena, "encounter.alliance_formed", victim, killer
    ):
        return "callback.former_allies"
    if told(arena, "combat.wound", killer, victim):
        return "callback.unfinished_business"  # the killer wounded the victim earlier
    if killer.district == victim.district:
        return "callback.district_partners"
    return None


def remember_kill(arena, killer, victim):
    """Tells the callback that fits this kill, if there is one."""
    group = callback_for(arena, killer, victim)
    if group:
        arena.add_to_story("bad", arena.line(group), a=killer, b=victim)
