"""The flow of the Games: the Bloodbath, then days and nights until one tribute is left."""

from .beats import acts, alliance_raid, announce_rumour, fallen_vote, rumour_effects, rumour_of_today
from .catalogue import ARMOR, FOOD, GEAR, HEALING, TRAP, WEAPON
from .combat import fight
from .encounters import ally_moment, meet_someone
from .events import arena_event, build_trap, feast, hazard, random_item, strange_berries, use_random_item
from .state import (
    FEARED,
    HIDDEN,
    VOTES_PER_ROUND,
    Decision,
    Victor,
    add_grudge,
    add_tag,
    find_item,
    remove_tag,
    same_alliance,
)


def choice_budget(alive):
    """How many pop-ups a normal day or night may have: more when the game gets tense."""
    if alive <= 4:
        return 6
    if alive <= 8:
        return 4
    return 3


HIDDEN_UNTIL_DAY = 3  # a tribute who fled the Bloodbath stays hidden for the first two nights

# Daily goals: what a tribute sets out to do each morning. They change which turns are likely.
HUNT, HIDE, SCAVENGE, GUARD = "hunt", "hide", "scavenge", "guard"
GOALS = [HUNT, HIDE, SCAVENGE, GUARD]  # in the order of the "goal" question's options
GOAL_POPUPS_PER_DAY = 3  # how many players in the room choose their goal each day (the others: the dice)
GOAL_EFFECTS = {
    HUNT: {"meet_someone": 10, "find_item": 3, "quiet": -6},
    HIDE: {"meet_someone": -10, "quiet": 8, "hazard": -2},
    SCAVENGE: {"find_item": 8, "berries": 2, "meet_someone": -6},
    GUARD: {"ally_moment": 12, "meet_someone": -4},
}
BOUNTY_HUNTERS = 2  # tributes who take up a bounty

# ---------- the Bloodbath ----------
# Balance (tuned with the simulation tests): rushing, grabbing a pack and fleeing
# should all lead to victory about equally often.
RUSHER_FINDS_WEAPON = 0.9
RUSHER_FIGHT_LETHALITY = 0.45
PACK_GRABBER_CAUGHT = 0.4

BOND_STYLES = ["team", "bad", ""]
BOND_GROUPS = ["district_bond.friends", "district_bond.rivals", "district_bond.strangers"]


def set_district_bonds(arena):
    """District partners (1 & 2, 3 & 4...) start as friends (allied), rivals (grudges) or strangers."""
    for i in range(0, len(arena.tributes) - 1, 2):
        a, b = arena.tributes[i], arena.tributes[i + 1]
        bond = arena.dice.int(3)  # 0 friends, 1 rivals, 2 strangers
        if bond == 0:
            arena.alliance_count += 1
            a.alliance = b.alliance = arena.alliance_count
        if bond == 1:
            add_grudge(a, b)
            add_grudge(b, a)
        arena.add_to_story(BOND_STYLES[bond], arena.line(BOND_GROUPS[bond]), n=a.district, a=a, b=b)


def bloodbath(arena):
    dice = arena.dice
    set_district_bonds(arena)
    rushers = []
    pack_grabbers = []
    for tribute in dice.shuffle(arena.living()):
        choice = arena.decide(tribute, "cornucopia", [35, 35, 30], a=tribute)
        if choice == 0:
            rushers.append(tribute)
            if dice.chance(RUSHER_FINDS_WEAPON):
                weapon = random_item(arena, WEAPON)
                tribute.items.append(weapon)
                arena.add_to_story("item", arena.line("bloodbath.grabs_weapon"), a=tribute, item=weapon)
            else:
                arena.add_to_story("", arena.line("bloodbath.too_late"), a=tribute)
        elif choice == 1:
            pack_grabbers.append(tribute)
            if dice.chance(0.85):
                supply = random_item(arena, dice.pick([ARMOR, HEALING, FOOD, TRAP, GEAR]))
                tribute.items.append(supply)
                arena.add_to_story("item", arena.line("bloodbath.grabs_pack"), a=tribute, item=supply)
            else:
                arena.add_to_story("bad", arena.line("bloodbath.empty_pack"), a=tribute)
        else:
            add_tag(tribute, HIDDEN)
            arena.add_to_story("", arena.pick_line("bloodbath.flees"), a=tribute)

    # Rushers fight each other in pairs (district friends spare each other).
    for i in range(0, len(rushers) - 1, 2):
        a, b = rushers[i], rushers[i + 1]
        if not same_alliance(a, b):
            fight(arena, a, b, 0, RUSHER_FIGHT_LETHALITY)
    for rusher in rushers:
        if rusher.alive and rusher.kills and add_tag(rusher, FEARED):
            arena.add_to_story("bad", arena.line("reputation.feared"), a=rusher)

    # Some pack grabbers get caught by a surviving rusher.
    for tribute in pack_grabbers:
        hunters = [r for r in rushers if r.alive and not same_alliance(r, tribute)]
        if tribute.alive and hunters and dice.chance(PACK_GRABBER_CAUGHT):
            fight(arena, dice.pick(hunters), tribute, 0.2, 0.7)


# ---------- between rounds ----------
def ask_shield(arena, gamemaker, event):
    """After choosing a disaster, a fallen Gamemaker shields one of a few tributes from it.
    Only the fallen: a living Gamemaker could never shield themselves, which would make being in
    the room a disadvantage. Returns the shielded tribute or None."""
    if event.is_feast or gamemaker.alive:
        return None
    candidates = arena.dice.shuffle([t for t in arena.living() if t is not gamemaker])[:4]
    if not candidates:
        return None
    decision = Decision(
        gamemaker, "shield", len(candidates), sponsor=gamemaker, option_tributes=tuple(candidates),
        for_whole_arena=True,
    )  # fmt: skip
    return candidates[arena.ask_player(decision)]


def start_of_day(arena):
    """At the start of each day, something may happen to the whole arena:
    a fallen player in the room places a bounty, someone in the room sends a sponsor gift,
    or a fallen player in the room decides which disaster hits everyone.

    Gifts come from the past victors in the room; when none is here, from the fallen in the room.
    Disasters are only ever chosen by the fallen."""
    dice = arena.dice
    fallen_in_room = [t for t in arena.tributes if t.present and not t.alive]
    victors_in_room = [victor for victor in arena.victors if victor.present]
    sponsors = victors_in_room or fallen_in_room
    if fallen_in_room and dice.chance(0.2):
        arena.choices_left -= 1
        return place_bounty(arena, dice.pick(fallen_in_room))
    if sponsors and dice.chance(0.35):
        arena.choices_left -= 1
        send_gift(arena, dice.pick(sponsors))
    elif fallen_in_room and dice.chance(0.45):
        arena.choices_left -= 1
        gamemaker = dice.pick(fallen_in_room)
        pool = list(arena.catalogue.arena_events)
        if not arena.feast_happened and arena.catalogue.feast:
            pool.append(arena.catalogue.feast)
        events = dice.shuffle(pool)[:3]
        if len(fallen_in_room) >= 2 and dice.chance(0.5):  # the fallen vote together
            return fallen_vote(arena, fallen_in_room, events)
        decision = Decision(
            gamemaker, "gamemaker", len(events), sponsor=gamemaker, option_events=tuple(events),
            for_whole_arena=True,
        )  # fmt: skip
        event = events[arena.ask_player(decision)]
        arena_event(arena, event, shielded=ask_shield(arena, gamemaker, event))
    elif not arena.feast_happened and len(arena.living()) <= 8:
        feast(arena)
    elif arena.day > 1 and dice.chance(0.2):
        arena_event(arena, dice.pick(arena.catalogue.arena_events))


def send_gift(arena, sponsor):
    """A sponsor (a past victor, or a fallen player) chooses which of a few living tributes
    receives a random item."""
    candidates = arena.dice.shuffle(arena.living())[:4]
    gift = random_item(arena)
    if isinstance(sponsor, Victor):
        question, line, who = "victor_sponsor", "item.from_victor", {"victor": sponsor}
    else:
        question, line, who = "sponsor", "item.from_sponsor", {"sponsor": sponsor}
    decision = Decision(
        sponsor, question, len(candidates), item=gift, option_tributes=tuple(candidates), **who
    )
    receiver = candidates[arena.ask_player(decision)]
    receiver.items.append(gift)
    arena.add_to_story("item", arena.line(line), a=receiver, item=gift, **who)


def place_bounty(arena, sponsor):
    """A fallen player puts a price on one of a few living tributes: some others now hunt them."""
    dice = arena.dice
    candidates = dice.shuffle(arena.living())[:4]
    decision = Decision(
        sponsor, "bounty", len(candidates), sponsor=sponsor, option_tributes=tuple(candidates)
    )
    target = candidates[arena.ask_player(decision)]
    hunters = [t for t in arena.living() if t is not target and not same_alliance(t, target)]
    hunters = dice.shuffle(hunters)[:BOUNTY_HUNTERS]
    for hunter in hunters:
        add_grudge(hunter, target)
    if hunters:
        arena.add_to_story("bad", arena.line("bounty.placed"), sponsor=sponsor, a=target, names=hunters)
    else:
        arena.add_to_story("bad", arena.line("bounty.ignored"), sponsor=sponsor, a=target)


def choose_goals(arena):
    """Each morning every living tribute sets a goal. A few players in the room choose theirs."""
    asked = 0
    for tribute in arena.dice.shuffle(arena.living()):
        if tribute.present and asked < GOAL_POPUPS_PER_DAY:
            asked += 1
            choice = arena.ask_player(Decision(tribute, "goal", len(GOALS), a=tribute))
        else:
            choice = arena.dice.int(len(GOALS))
        tribute.goal = GOALS[choice]


# ---------- a normal day or night ----------


def everyones_turn(arena, is_night):
    """Every living tribute gets one turn, in random order. Some turns involve a second tribute."""
    dice = arena.dice
    busy = set()
    for tribute in dice.shuffle(arena.living()):
        if not tribute.alive or tribute in busy:
            continue
        busy.add(tribute)
        under_pressure = arena.day >= 5 or len(arena.living()) <= 5
        trap_material = find_item(tribute, TRAP)
        ally = dice.pick(
            [o for o in arena.living() if o is not tribute and same_alliance(tribute, o) and o not in busy]
        )

        # How likely each kind of turn is. Late in the game, more fights and fewer quiet moments.
        turn_weights = {
            "meet_someone": 60 if under_pressure else 36,
            "find_item": 12,
            "use_item": 14 if tribute.items else 0,
            "parachute": 6,
            "hazard": 10 if under_pressure else 6,
            "ally_moment": 12 if ally else 0,
            "build_trap": 7 if trap_material else 0,
            "berries": 4,
            "quiet": 10 if under_pressure else 25,
        }
        for effects in [GOAL_EFFECTS.get(tribute.goal, {}), *rumour_effects(arena, tribute)]:
            for turn_name, change in effects.items():
                if turn_weights[turn_name]:  # 0 means this turn is not possible (no ally, no items)
                    turn_weights[turn_name] = max(0, turn_weights[turn_name] + change)
        turn = list(turn_weights)[dice.weighted_index(list(turn_weights.values()))]

        if turn == "meet_someone":
            meet_someone(arena, tribute, busy, is_night)
        elif turn == "find_item":
            found = random_item(arena)
            tribute.items.append(found)
            arena.add_to_story("item", arena.pick_line("item.found"), a=tribute, item=found)
        elif turn == "use_item":
            use_random_item(arena, tribute)
        elif turn == "parachute":
            gift = random_item(arena)
            tribute.items.append(gift)
            arena.add_to_story("item", arena.line("item.parachute"), a=tribute, item=gift)
        elif turn == "hazard":
            hazard(arena, tribute, under_pressure)
        elif turn == "ally_moment":
            busy.add(ally)
            ally_moment(arena, tribute, ally)
        elif turn == "build_trap":
            build_trap(arena, tribute, trap_material)
        elif turn == "berries":
            strange_berries(arena, tribute)
        else:
            group = "filler.night" if is_night else "filler.day"
            arena.add_to_story("", arena.pick_line(group), a=tribute)


# ---------- the final duel ----------


def final_duel(arena):
    """Each finalist picks a tactic, like rock-paper-scissors:
    ambush beats charge, waiting beats ambush, charge beats waiting.
    The better tactic gives an edge, but luck still decides."""
    a, b = arena.living()
    a.alliance = b.alliance = 0
    arena.add_to_story("arena", arena.line("finale.announced"), a=a, b=b)
    tactic_a = arena.decide(a, "final_duel", [1, 1, 1], a=a, b=b)
    tactic_b = arena.decide(b, "final_duel", [1, 1, 1], a=b, b=a)
    tactics = arena.catalogue.variants("finale.tactic")
    arena.add_to_story("", tactics[tactic_a], a=a)
    arena.add_to_story("", tactics[tactic_b], a=b)
    outcome = (tactic_a - tactic_b + 3) % 3  # 0 same tactic, 1 a wins the matchup, 2 b wins it
    edge = [0, 0.3, -0.3][outcome]
    while len(arena.living()) == 2:
        fight(arena, a, b, edge, 0.9, mercy=False)


# ---------- one round ----------


def is_night_round(round_number):
    return round_number > 1 and round_number % 2 == 1


def play_next_round(arena):
    """Plays the next round (Bloodbath, Day or Night) and adds it to the story.

    Raises NeedAnswer when a player in the room has to choose and has not answered yet.
    """
    dice = arena.dice
    arena.round += 1
    arena.day = arena.round // 2
    is_night = is_night_round(arena.round)
    alive_at_start = len(arena.living())
    is_finale = alive_at_start == 2

    # Everyone present chooses at the Bloodbath and in the final duel; otherwise a few pop-ups per round.
    arena.choices_left = float("inf") if arena.round == 1 or is_finale else choice_budget(alive_at_start)
    arena.votes_left = VOTES_PER_ROUND

    if arena.round == 1:
        title, style = "phase.bloodbath", "heading"
    elif is_night:
        title, style = "phase.night", "heading night"
    else:
        title, style = "phase.day", "heading"
    arena.add_to_story(style, arena.line(title), n=arena.day)

    if arena.day >= HIDDEN_UNTIL_DAY:
        for tribute in arena.tributes:
            remove_tag(tribute, HIDDEN)
    if arena.round == 1:
        bloodbath(arena)
    elif is_finale:
        final_duel(arena)
    else:
        living = arena.living()
        if all(same_alliance(t, living[0]) for t in living):
            for tribute in living:
                tribute.alliance = 0
            arena.add_to_story("bad", arena.line("phase.alliances_shatter"))

        acts(arena)
        if is_night:
            arena.rumour = rumour_of_today(arena)
        else:
            announce_rumour(arena)
            choose_goals(arena)
            start_of_day(arena)
            alliance_raid(arena)
        everyones_turn(arena, is_night)

        # Nobody died late in the game: the Gamemakers step in so the Games always end.
        nobody_died = len(arena.living()) == alive_at_start
        if nobody_died and (arena.day >= 4 or alive_at_start <= 4):
            arena_event(arena, dice.pick(arena.catalogue.arena_events), 0.3)
            if len(arena.living()) == alive_at_start:
                a, b = dice.shuffle(arena.living())[:2]
                a.alliance = b.alliance = 0
                arena.dissolve_lonely_alliances()
                fight(arena, a, b, 0, 0.9, mercy=False)

    fallen = arena.fallen_this_round
    line = arena.line("phase.cannons" if fallen else "phase.no_cannons")
    arena.add_to_story("cannon", line, n=len(fallen), names=fallen)
    arena.fallen_this_round = []

    if len(arena.living()) == 1:
        arena.winner = arena.living()[0]
        arena.add_to_story("win", arena.line("phase.winner"), a=arena.winner)
