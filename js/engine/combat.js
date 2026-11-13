// How a fight between two tributes plays out.
import { KIND } from '../data/items.js';
import { COMBAT } from '../data/story.js';
import { chance, pickRandom } from '../utils/random.js';
import { addGrudge, addToStory, findItem, killTribute, removeItem } from './state.js';

const WEAPON_BONUS = 0.35;
const ARMOR_BONUS = 0.1;
const WOUND_PENALTY = 0.25;
const WEAPON_BREAK_CHANCE = 0.15; // a weapon is never a guarantee
const ARMOR_SAVE_CHANCE = 0.4;
const LOOT_CHANCE = 0.6;

/** A tribute's fighting roll: luck, plus weapon and armour, minus wounds. */
function fightingStrength(tribute) {
  let weapon = findItem(tribute, KIND.WEAPON);

  if (weapon && chance(WEAPON_BREAK_CHANCE)) {
    addToStory('bad', COMBAT.weaponBreaks, { a: tribute, item: weapon.name });
    removeItem(tribute, weapon);
    weapon = null;
  }

  return Math.random()
    + (weapon ? WEAPON_BONUS : 0)
    + (findItem(tribute, KIND.ARMOR) ? ARMOR_BONUS : 0)
    - (tribute.wounded ? WOUND_PENALTY : 0);
}

/**
 * first and second fight.
 * edge: a bonus for first (positive) or second (negative).
 * lethalChance: how likely the loser dies instead of being wounded or escaping.
 */
export function fight(first, second, edge = 0, lethalChance = 0.6) {
  const firstWins = fightingStrength(first) + edge >= fightingStrength(second);
  const [winner, loser] = firstWins ? [first, second] : [second, first];

  const roll = Math.random();
  const loserArmor = findItem(loser, KIND.ARMOR);
  const winnerWeapon = findItem(winner, KIND.WEAPON);

  // A wounded loser always takes the fatal blow (unless armour saves them).
  if (loser.wounded || roll < lethalChance) {
    if (loserArmor && chance(ARMOR_SAVE_CHANCE)) {
      removeItem(loser, loserArmor);
      addGrudge(loser, winner);
      addToStory('item', COMBAT.savedByArmor, { b: loser, item: loserArmor.name });
      return;
    }

    if (winnerWeapon) {
      addToStory('death', pickRandom(COMBAT.killWithWeapon), { a: winner, b: loser, item: winnerWeapon.name });
    } else {
      addToStory('death', pickRandom(COMBAT.killBareHanded), { a: winner, b: loser });
    }
    killTribute(loser, winner);

    if (loser.items.length && chance(LOOT_CHANCE)) {
      const loot = pickRandom(loser.items);
      winner.items.push(loot);
      addToStory('item', COMBAT.loot, { a: winner, item: loot.name });
    }
    return;
  }

  if (roll < lethalChance + 0.25) {
    loser.wounded = true;
    addGrudge(loser, winner);
    addToStory('hurt', COMBAT.wound, { a: winner, b: loser });
    return;
  }

  // Nobody wins: now they both hold a grudge.
  addGrudge(first, second);
  addGrudge(second, first);
  addToStory('', COMBAT.draw, { a: first, b: second });
}
