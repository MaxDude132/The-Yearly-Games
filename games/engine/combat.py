"""How a fight between two tributes plays out."""

from .catalogue import ARMOR, WEAPON
from .state import add_grudge, find_item, remove_item

WEAPON_BONUS = 0.35
ARMOR_BONUS = 0.1
WOUND_PENALTY = 0.25
WEAPON_BREAK_CHANCE = 0.15  # a weapon is never a guarantee
ARMOR_SAVE_CHANCE = 0.4
LOOT_CHANCE = 0.6


def fighting_strength(arena, tribute):
    """A tribute's fighting roll: luck, plus weapon and armour, minus wounds."""
    weapon = find_item(tribute, WEAPON)
    if weapon and arena.dice.chance(WEAPON_BREAK_CHANCE):
        arena.add_to_story("bad", arena.line("combat.weapon_breaks"), a=tribute, item=weapon)
        remove_item(tribute, weapon)
        weapon = None
    return (
        arena.dice.random()
        + (WEAPON_BONUS if weapon else 0)
        + (ARMOR_BONUS if find_item(tribute, ARMOR) else 0)
        - (WOUND_PENALTY if tribute.wounded else 0)
    )


def fight(arena, first, second, edge=0, lethal_chance=0.6):
    """first and second fight.

    edge: a bonus for first (positive) or second (negative).
    lethal_chance: how likely the loser dies instead of being wounded or escaping.
    """
    dice = arena.dice
    first_strength = fighting_strength(arena, first)
    second_strength = fighting_strength(arena, second)
    first_wins = first_strength + edge >= second_strength
    winner, loser = (first, second) if first_wins else (second, first)
    roll = dice.random()
    loser_armor = find_item(loser, ARMOR)
    winner_weapon = find_item(winner, WEAPON)

    # A wounded loser always takes the fatal blow (unless armour saves them).
    if loser.wounded or roll < lethal_chance:
        if loser_armor and dice.chance(ARMOR_SAVE_CHANCE):
            remove_item(loser, loser_armor)
            add_grudge(loser, winner)
            arena.add_to_story("item", arena.line("combat.saved_by_armor"), b=loser, item=loser_armor)
            return
        if winner_weapon:
            line = arena.pick_line("combat.kill_with_weapon")
            arena.add_to_story("death", line, a=winner, b=loser, item=winner_weapon)
        else:
            arena.add_to_story("death", arena.pick_line("combat.kill_bare_handed"), a=winner, b=loser)
        arena.kill_tribute(loser, winner)
        if loser.items and dice.chance(LOOT_CHANCE):
            loot = dice.pick(loser.items)
            winner.items.append(loot)
            arena.add_to_story("item", arena.line("combat.loot"), a=winner, item=loot)
        return

    if roll < lethal_chance + 0.25:
        loser.wounded = True
        add_grudge(loser, winner)
        arena.add_to_story("hurt", arena.line("combat.wound"), a=winner, b=loser)
        return

    # Nobody wins: now they both hold a grudge.
    add_grudge(first, second)
    add_grudge(second, first)
    arena.add_to_story("", arena.line("combat.draw"), a=first, b=second)
