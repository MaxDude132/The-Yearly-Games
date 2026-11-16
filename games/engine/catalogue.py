"""What the engine needs to know about the content: which items, events, lines and questions exist.

No text here. The text lives in the database (the content app) and is only looked up when a
story line or question is shown to a player, in that player's language.
"""

from dataclasses import dataclass
from typing import NamedTuple

WEAPON, ARMOR, HEALING, FOOD, TRAP, GEAR = "weapon", "armor", "healing", "food", "trap", "gear"


@dataclass(frozen=True)
class Item:
    key: str
    kind: str


@dataclass(frozen=True)
class ArenaEvent:
    key: str
    counter: str  # the kind of item that can save a tribute (empty for the feast)
    is_feast: bool = False


class Line(NamedTuple):
    """One story sentence: the group it belongs to and which variation of that group."""

    group: str
    variant: int = 0


class Catalogue:
    def __init__(self, items, events, line_groups, question_options):
        """
        items: list of Item.
        events: list of ArenaEvent, feast included.
        line_groups: {group: number of variations}.
        question_options: {question key: number of options}.
        """
        self.items = list(items)
        self._items = {item.key: item for item in self.items}
        self.arena_events = [event for event in events if not event.is_feast]
        feasts = [event for event in events if event.is_feast]
        self.feast = feasts[0] if feasts else None
        self._variants = {
            group: [Line(group, i) for i in range(count)] for group, count in line_groups.items()
        }
        self._question_options = dict(question_options)

    def item(self, key):
        return self._items[key]

    def items_of_kind(self, kind):
        return [item for item in self.items if item.kind == kind]

    def variants(self, group):
        """All variations of a group of lines."""
        return self._variants[group]

    def line(self, group):
        """The one line of a group that has no variations."""
        return self._variants[group][0]

    def intro(self, event):
        return self.line(f"arena_event.{event.key}")

    def option_count(self, question_key):
        return self._question_options[question_key]
