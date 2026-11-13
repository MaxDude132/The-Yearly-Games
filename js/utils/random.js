// Small helpers for everything random in the Games.

/** A whole number from 0 up to (but not including) max. */
export const randomInt = (max) => Math.floor(Math.random() * max);

/** One random element of a list. */
export const pickRandom = (list) => list[randomInt(list.length)];

/** True with the given probability (0 to 1). */
export const chance = (probability) => Math.random() < probability;

/** Shuffles a list in place and returns it. */
export function shuffle(list) {
  for (let i = list.length - 1; i > 0; i--) {
    const j = randomInt(i + 1);
    [list[i], list[j]] = [list[j], list[i]];
  }
  return list;
}

/**
 * Picks an index where bigger weights are more likely.
 * weightedIndex([70, 20, 10]) returns 0 about 70% of the time.
 */
export function weightedIndex(weights) {
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let roll = Math.random() * total;
  return weights.findIndex((weight) => (roll -= weight) < 0);
}
