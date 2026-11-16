"""Everything random in the Games. One Dice per round, seeded, so a round can be replayed exactly."""

import random


class Dice:
    def __init__(self, seed=None):
        self._random = random.Random(seed)

    def random(self):
        """A float from 0 up to (but not including) 1."""
        return self._random.random()

    def int(self, upper):
        """A whole number from 0 up to (but not including) upper."""
        return self._random.randrange(upper)

    def pick(self, items):
        """One random element of a list, or None if the list is empty."""
        return items[self.int(len(items))] if items else None

    def chance(self, probability):
        """True with the given probability (0 to 1)."""
        return self._random.random() < probability

    def shuffle(self, items):
        """Shuffles a list in place and returns it."""
        self._random.shuffle(items)
        return items

    def weighted_index(self, weights):
        """Picks an index where bigger weights are more likely: [70, 20, 10] gives 0 about 70% of the time."""
        roll = self._random.random() * sum(weights)
        for index, weight in enumerate(weights):
            roll -= weight
            if roll < 0:
                return index
        return max(index for index, weight in enumerate(weights) if weight > 0)  # float rounding only
