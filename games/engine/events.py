"""Things that happen to tributes: arena disasters, the feast, accidents, berries, traps, using items."""

from .catalogue import FOOD, HEALING, WEAPON
from .combat import fight
from .state import add_grudge, find_item, remove_item, same_alliance


def random_item(arena, kind=None):
    """A random item, optionally of one kind."""
    choices = arena.catalogue.items_of_kind(kind) if kind else arena.catalogue.items
    return arena.dice.pick(choices)


# ---------- arena-wide ----------


def arena_event(arena, event, death_chance=0.12, shielded=None):
    """A disaster hits everyone. Each tribute has a small chance to be caught;
    the right kind of item (event.counter) often saves them. A shielded tribute is never caught."""
    if event.is_feast:
        return feast(arena)
    arena.add_to_story("arena", arena.catalogue.intro(event))
    anyone_caught = False
    for tribute in arena.living():
        roll = arena.dice.random()
        if roll >= death_chance + 0.2:
            continue  # not caught
        if tribute is shielded:
            arena.add_to_story("team", arena.line("arena.shielded"), a=tribute)
            continue
        anyone_caught = True
        lifesaver = find_item(tribute, event.counter)
        if lifesaver and arena.dice.chance(0.6):
            if lifesaver.kind == HEALING:
                remove_item(tribute, lifesaver)  # medicine gets used up
            arena.add_to_story("item", arena.line("arena.saved_by"), a=tribute, item=lifesaver)
        elif roll < death_chance and arena.more_than_one_alive():
            arena.add_to_story("death", arena.line("arena.dies"), a=tribute)
            arena.kill_tribute(tribute)
        else:
            tribute.wounded = True
            arena.add_to_story("hurt", arena.line("arena.wounded"), a=tribute)
    if not anyone_caught:
        arena.add_to_story("", arena.line("arena.everyone_safe"))


def feast(arena):
    """Half the tributes risk the Cornucopia: they pair off and fight, and survivors take a prize."""
    arena.feast_happened = True
    arena.add_to_story("arena", arena.line("arena.feast_announced"))
    attendees = [t for t in arena.dice.shuffle(arena.living()) if arena.dice.chance(0.5)]
    if not attendees:
        return arena.add_to_story("", arena.line("arena.feast_empty"))
    for i in range(0, len(attendees) - 1, 2):
        a, b = attendees[i], attendees[i + 1]
        if not same_alliance(a, b):
            fight(arena, a, b, 0, 0.7)
    for tribute in attendees:
        if not tribute.alive:
            continue
        prize = random_item(arena)
        tribute.items.append(prize)
        arena.add_to_story("item", arena.line("arena.feast_prize"), a=tribute, item=prize)


# ---------- one tribute ----------


def hazard(arena, tribute, under_pressure):
    """An accident. Late in the game (under_pressure) it is deadlier."""
    roll = arena.dice.random()
    death_chance = 0.4 if under_pressure else 0.3
    if roll < death_chance and arena.more_than_one_alive():
        arena.add_to_story("death", arena.pick_line("hazard.deadly"), a=tribute)
        arena.kill_tribute(tribute)
    elif roll < 0.65:
        tribute.wounded = True
        arena.add_to_story("hurt", arena.pick_line("hazard.wounding"), a=tribute)
    else:
        arena.add_to_story("", arena.pick_line("hazard.close_call"), a=tribute)


def strange_berries(arena, tribute):
    choice = arena.decide(tribute, "berries", [50, 50], a=tribute)
    if choice == 1:
        return arena.add_to_story("", arena.line("berries.left_alone"), a=tribute)
    roll = arena.dice.random()
    if roll < 0.65:
        tribute.wounded = False
        arena.add_to_story("item", arena.line("berries.delicious"), a=tribute)
    elif roll < 0.88 or not arena.more_than_one_alive():
        tribute.wounded = True
        arena.add_to_story("hurt", arena.line("berries.sick"), a=tribute)
    else:
        arena.add_to_story("death", arena.line("berries.deadly"), a=tribute)
        arena.kill_tribute(tribute)


def build_trap(arena, tribute, material):
    """A tribute with rope, a net or wire builds either a snare (food) or a trap for other tributes."""
    dice = arena.dice
    choice = arena.decide(tribute, "trap", [50, 50], a=tribute, item=material)
    if dice.chance(0.5):
        remove_item(tribute, material)
    if choice == 0:
        if dice.chance(0.7):
            tribute.items.append(random_item(arena, FOOD))
            arena.add_to_story("item", arena.line("trap.snare_works"), a=tribute)
        else:
            arena.add_to_story("", arena.line("trap.snare_empty"), a=tribute)
        return
    possible_victims = [t for t in arena.living() if t is not tribute and not same_alliance(tribute, t)]
    victim = dice.pick(possible_victims)
    roll = dice.random()
    if victim and roll < 0.45:
        if victim.wounded or dice.chance(0.5):
            arena.add_to_story("death", arena.line("trap.kills"), a=tribute, b=victim)
            arena.kill_tribute(victim, tribute)
        else:
            victim.wounded = True
            add_grudge(victim, tribute)
            arena.add_to_story("hurt", arena.line("trap.wounds"), a=tribute, b=victim)
    elif roll < 0.6:
        tribute.wounded = True
        arena.add_to_story("hurt", arena.line("trap.backfires"), a=tribute)
    else:
        arena.add_to_story("", arena.line("trap.nobody_comes"), a=tribute)


def use_random_item(arena, tribute):
    """A tribute uses something they carry. Items help most of the time, not always."""
    item = arena.dice.pick(tribute.items)
    roll = arena.dice.random()
    if item.kind == HEALING and tribute.wounded:
        remove_item(tribute, item)
        if roll < 0.8:
            tribute.wounded = False
            arena.add_to_story("item", arena.line("item.healed"), a=tribute, item=item)
        else:
            arena.add_to_story("bad", arena.line("item.heal_fails"), a=tribute, item=item)
    elif item.kind == FOOD:
        remove_item(tribute, item)
        if roll < 0.12:
            tribute.wounded = True
            arena.add_to_story("hurt", arena.line("item.spoiled"), a=tribute, item=item)
        else:
            arena.add_to_story("item", arena.line("item.eats"), a=tribute, item=item)
    elif item.kind == WEAPON and roll < 0.08:
        tribute.wounded = True
        arena.add_to_story("hurt", arena.line("item.training_accident"), a=tribute, item=item)
    elif item.kind == WEAPON and roll < 0.14:
        remove_item(tribute, item)
        arena.add_to_story("bad", arena.line("item.dropped"), a=tribute, item=item)
    else:
        group = "item.trains" if item.kind == WEAPON else "item.checks_gear"
        arena.add_to_story("", arena.line(group), a=tribute, item=item)
