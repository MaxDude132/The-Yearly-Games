"""When two tributes cross paths: fights, alliances, sleeping targets, and loyalty between allies."""

from .catalogue import HEALING
from .combat import fight
from .state import (
    BETRAYER,
    FEARED,
    HIDDEN,
    MERCIFUL,
    add_grudge,
    add_tag,
    find_item,
    forgive_grudge,
    has_tag,
    holds_grudge,
    remove_item,
    same_alliance,
)

MAX_ALLIANCE_SIZE = 4

# Balance: no option should be the "safe" one. These are tuned with the simulation tests
# so that a player who always picks the same option wins as often as anyone else.
SURPRISE_ATTACK_EDGE = 0.35  # attacking someone who has not noticed you
SPOTTED_WHILE_SLIPPING = 0.2  # chance the other tribute notices you sneaking off
CHASE_EDGE = 0.15  # the chaser's advantage
STEAL_SUCCESS = 0.55  # stealing from a sleeper
REFUSAL_STARTS_FIGHT = 0.25  # a refused alliance can turn ugly
FEARED_SOUGHT = 0.2  # chance a tribute goes looking for a feared rival instead of a random one
HIDDEN_SKIPPED = 0.5  # chance a sleeper who hid well is walked past at night
COLD_HANDSHAKE = 0.4  # chance an alliance with a known betrayer falls through
MERCY_WINS_OVER = 0.5  # chance a refusal turns into a yes when the offer comes from someone known for mercy


def meet_someone(arena, tribute, busy, is_night):
    """tribute runs into someone who is not busy and not an ally.

    Tributes with a grudge are more likely to find the person they hate.
    busy: tributes who already had their turn this round.
    """
    dice = arena.dice
    candidates = [
        other
        for other in arena.living()
        if other is not tribute and other not in busy and not same_alliance(tribute, other)
    ]
    if not candidates:
        group = "filler.night" if is_night else "filler.day"
        return arena.add_to_story("", arena.pick_line(group), a=tribute)
    enemies = [other for other in candidates if holds_grudge(tribute, other)]
    feared = [other for other in candidates if has_tag(other, FEARED) and not has_tag(tribute, FEARED)]
    if enemies and dice.chance(0.6):
        other = dice.pick(enemies)
    elif feared and dice.chance(FEARED_SOUGHT):
        other = dice.pick(feared)
    else:
        other = dice.pick(candidates)
    busy.add(other)
    if is_night and dice.chance(0.35):
        if has_tag(other, HIDDEN) and dice.chance(HIDDEN_SKIPPED):
            return arena.add_to_story("", arena.line("encounter.hidden_well"), a=tribute, b=other)
        return find_sleeper(arena, tribute, other)
    return face_to_face(arena, tribute, other)


def find_sleeper(arena, tribute, sleeper):
    dice = arena.dice
    weights = [70, 20, 10] if holds_grudge(tribute, sleeper) else [35, 30, 35]  # strike, steal, walk away
    choice = arena.decide(tribute, "sleeper", weights, a=tribute, b=sleeper)
    if choice == 0:
        if dice.chance(0.65):
            arena.add_to_story("death", arena.line("encounter.kills_sleeper"), a=tribute, b=sleeper)
            arena.kill_tribute(sleeper, tribute)
        else:
            arena.add_to_story("bad", arena.line("encounter.sleeper_wakes"), a=tribute, b=sleeper)
            add_grudge(sleeper, tribute)
            fight(arena, sleeper, tribute, 0.15)
    elif choice == 1 and sleeper.items:
        if dice.chance(STEAL_SUCCESS):
            stolen = dice.pick(sleeper.items)
            remove_item(sleeper, stolen)
            tribute.items.append(stolen)
            arena.add_to_story("item", arena.line("encounter.steals"), a=tribute, b=sleeper, item=stolen)
        else:
            add_grudge(sleeper, tribute)
            arena.add_to_story("bad", arena.line("encounter.caught_stealing"), a=tribute, b=sleeper)
    else:
        arena.add_to_story("", arena.line("encounter.leaves_sleeper"), a=tribute, b=sleeper)


def face_to_face(arena, tribute, other):
    hates = holds_grudge(tribute, other)
    same_district = tribute.district == other.district
    # Weights for: attack, offer an alliance, slip away.
    weights = [45, 20, 35]
    if hates:
        weights = [80, 0, 20]
    elif len(arena.living()) <= 5:
        weights = [60, 5, 35]
    elif same_district:
        weights = [20, 50, 30]
    choice = arena.decide(tribute, "meeting", weights, a=tribute, b=other)
    if choice == 0:
        if hates:
            arena.add_to_story("bad", arena.line("encounter.hunted"), a=tribute, b=other)
        fight(arena, tribute, other, SURPRISE_ATTACK_EDGE)
    elif choice == 1:
        offer_alliance(arena, tribute, other)
    elif arena.dice.chance(SPOTTED_WHILE_SLIPPING):
        arena.add_to_story("bad", arena.line("encounter.spotted_slipping"), a=tribute, b=other)
        fight(arena, other, tribute, CHASE_EDGE)
    else:
        arena.add_to_story("", arena.line("encounter.slips_away"), a=tribute, b=other)


def offer_alliance(arena, tribute, other):
    # Weights for: accept, refuse, attack instead.
    weights = [60, 30, 10]
    if holds_grudge(other, tribute):
        weights = [10, 40, 50]
    elif tribute.district == other.district:
        weights = [80, 15, 5]
    answer = arena.decide(other, "alliance_offer", weights, a=tribute, b=other)
    if answer == 1 and has_tag(tribute, MERCIFUL) and arena.dice.chance(MERCY_WINS_OVER):
        arena.add_to_story("team", arena.line("encounter.mercy_wins_over"), a=tribute, b=other)
        answer = 0

    # Whoever already has an alliance brings the other one in.
    host = tribute if tribute.alliance else other
    guest = other if host is tribute else tribute
    alliance_is_full = (
        host.alliance and len([t for t in arena.living() if t.alliance == host.alliance]) >= MAX_ALLIANCE_SIZE
    )
    doubted = BETRAYER in (*tribute.tags, *other.tags)  # someone here betrayed an ally before
    if answer == 0 and not alliance_is_full and doubted and arena.dice.chance(COLD_HANDSHAKE):
        arena.add_to_story("", arena.line("encounter.cold_handshake"), a=tribute, b=other)
    elif answer == 0 and not alliance_is_full:
        if not host.alliance:
            arena.alliance_count += 1
            host.alliance = arena.alliance_count
        guest.alliance = host.alliance
        arena.dissolve_lonely_alliances()
        forgive_grudge(tribute, other)
        forgive_grudge(other, tribute)
        arena.add_to_story("team", arena.line("encounter.alliance_formed"), a=tribute, b=other)
    elif answer == 2:
        arena.add_to_story("bad", arena.line("encounter.offer_answered_with_attack"), a=tribute, b=other)
        fight(arena, other, tribute, 0.15)
    else:
        add_grudge(tribute, other)
        arena.add_to_story("", arena.line("encounter.alliance_refused"), a=tribute, b=other)
        if arena.dice.chance(REFUSAL_STARTS_FIGHT):
            arena.add_to_story("bad", arena.line("encounter.refusal_turns_ugly"), a=tribute, b=other)
            fight(arena, tribute, other, 0.1)


def ally_moment(arena, tribute, ally):
    """Two allies spend time together. Late in the game, one may betray the other
    (district partners almost never do). Otherwise they help each other."""
    tributes_left = len(arena.living())
    choice = 0  # stay loyal
    if tributes_left <= 8:
        weights = [88, 12]
        if tribute.district == ally.district:
            weights = [92, 8]
        elif tributes_left <= 5:
            weights = [65, 35]
        choice = arena.decide(tribute, "loyalty", weights, a=tribute, b=ally)
    if choice == 1:
        add_tag(tribute, BETRAYER)
        tribute.alliance = 0
        arena.dissolve_lonely_alliances()
        add_grudge(ally, tribute)
        arena.add_to_story("bad", arena.line("alliance.betrayal"), a=tribute, b=ally)
        fight(arena, tribute, ally, 0.3, 0.75)
        return
    medicine = find_item(tribute, HEALING) if ally.wounded else None
    if medicine:
        remove_item(tribute, medicine)
        ally.wounded = False
        arena.add_to_story("item", arena.line("item.heals_ally"), a=tribute, b=ally, item=medicine)
    else:
        arena.add_to_story("team", arena.pick_line("alliance.loyal"), a=tribute, b=ally)
