"""The shape of the story: acts that come at fixed points of the game and look back at what
the tributes did, the daily rumour, alliance raids led by an alliance's leader, and the vote of
the fallen on the next disaster.
"""

from .combat import fight
from .events import arena_event
from .memory import told
from .state import FEARED, Decision, add_tag, alliance_leader, alliance_members, owes_life

# ---------- acts ----------
MANHUNT_AT = 12  # tributes left when the Gamemakers name the most dangerous one
FINAL_FOUR_AT = 4


def told_group(arena, group):
    return any(entry.line.group == group for entry in arena.log)


def acts(arena):
    """The turning points of the Games, each told once."""
    living = arena.living()
    if len(living) <= MANHUNT_AT and not told_group(arena, "act.manhunt"):
        deadliest = max(living, key=lambda t: (t.kills, -t.id))
        if deadliest.kills:  # nobody has killed yet: wait for someone to earn it
            arena.add_to_story("arena", arena.line("act.manhunt"), a=deadliest, n=deadliest.kills)
            add_tag(deadliest, FEARED)
    if len(living) <= FINAL_FOUR_AT and not told_group(arena, "act.final_four"):
        arena.add_to_story("arena", arena.line("act.final_four"), names=living)
        for i, a in enumerate(living):
            for b in living[i + 1 :]:
                look_back(arena, a, b)


def look_back(arena, a, b):
    """At the final four, the story reminds everyone what binds or divides two finalists."""
    if owes_life(a, b) or owes_life(b, a):
        debtor, benefactor = (a, b) if owes_life(a, b) else (b, a)
        arena.add_to_story("team", arena.line("endgame.debt"), a=debtor, b=benefactor)
    elif a.alliance and a.alliance == b.alliance:
        arena.add_to_story("team", arena.line("endgame.allies"), a=a, b=b)
    elif b.id in a.grudges and a.id in b.grudges:
        arena.add_to_story("bad", arena.line("endgame.grudge"), a=a, b=b)
    elif told(arena, "alliance.betrayal", a, b) or told(arena, "alliance.betrayal", b, a):
        arena.add_to_story("bad", arena.line("endgame.grudge"), a=a, b=b)


# ---------- rumours ----------
# Each morning the arena whispers something. Players see it before they choose their goal:
# the goal that fits the rumour works better that day and night.
SUPPLIES, HUNTERS, STORM = "supplies", "hunters", "storm"
RUMOURS = [SUPPLIES, HUNTERS, STORM]
RUMOUR_EFFECTS = {  # rumour: {goal (or "" for everyone): changes to the turn weights}
    SUPPLIES: {"scavenge": {"find_item": 8}},
    HUNTERS: {"hide": {"quiet": 6, "meet_someone": -6}, "hunt": {"meet_someone": 6}},
    STORM: {"guard": {"hazard": -3}, "": {"hazard": 2}},
}


def announce_rumour(arena):
    arena.rumour = arena.dice.pick(RUMOURS)
    arena.add_to_story("arena", arena.line(f"rumour.{arena.rumour}"))


def rumour_of_today(arena):
    """The rumour told this morning (a night replays it from the story)."""
    for entry in reversed(arena.log):
        if entry.line.group.startswith("rumour."):
            return entry.line.group.removeprefix("rumour.")
        if entry.line.group == "phase.day":
            return ""
    return ""


def rumour_effects(arena, tribute):
    effects = RUMOUR_EFFECTS.get(arena.rumour, {})
    return [effects.get("", {}), effects.get(tribute.goal, {})]


# ---------- alliance raids ----------
RAID_CHANCE = 0.3
RAID_WEIGHTS = [40, 60]  # attack the other alliance, or lie low


def alliance_raid(arena):
    """Sometimes the leader of an alliance decides whether to attack another alliance."""
    dice = arena.dice
    alliances = sorted({t.alliance for t in arena.living() if t.alliance})
    alliances = [a for a in alliances if len(alliance_members(arena, a)) >= 2]
    if len(alliances) < 2 or not dice.chance(RAID_CHANCE):
        return
    ours, theirs = dice.shuffle(alliances)[:2]
    leader, rival = alliance_leader(arena, ours), alliance_leader(arena, theirs)
    if arena.decide(leader, "raid", RAID_WEIGHTS, a=leader, b=rival) == 1:
        return arena.add_to_story("", arena.line("alliance.lies_low"), a=leader, b=rival)
    arena.add_to_story("bad", arena.line("alliance.raid"), a=leader, b=rival)
    attackers = dice.shuffle(alliance_members(arena, ours))
    defenders = dice.shuffle(alliance_members(arena, theirs))
    for attacker, defender in zip(attackers, defenders, strict=False):
        if attacker.alive and defender.alive and arena.more_than_one_alive():
            fight(arena, attacker, defender, 0.1, 0.5)


# ---------- the fallen vote on the disaster ----------
def fallen_vote(arena, fallen, events):
    """Every fallen player in the room votes for the next disaster. A tie goes to the dice."""
    counts = [0] * len(events)
    for number, voter in enumerate(fallen, start=1):
        decision = Decision(
            voter, "gamemaker", len(events), sponsor=voter, option_events=tuple(events),
            for_whole_arena=True, vote_number=number, vote_total=len(fallen),
        )  # fmt: skip
        counts[arena.ask_player(decision)] += 1
    best = max(counts)
    tied = [i for i, count in enumerate(counts) if count == best]
    event = events[tied[0] if len(tied) == 1 else arena.dice.pick(tied)]
    arena.add_to_story("arena", arena.line("arena.fallen_vote"), names=fallen)
    arena_event(arena, event)
