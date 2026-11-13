// Things that happen to tributes: arena disasters, the feast, accidents, berries, traps, using items.
import { KIND, randomItem } from '../data/items.js';
import { ARENA_STORY, BERRIES, HAZARDS, ITEM_STORY, QUESTIONS, TRAPS } from '../data/story.js';
import { chance, pickRandom, shuffle } from '../utils/random.js';
import { fight } from './combat.js';
import {
  addGrudge, addToStory, decide, findItem, game, killTribute,
  livingTributes, moreThanOneAlive, removeItem, sameAlliance,
} from './state.js';

// ---------- arena-wide ----------

/**
 * A disaster hits everyone. Each tribute has a small chance to be caught;
 * the right kind of item (event.counter) often saves them.
 */
export function arenaEvent(event, deathChance = 0.12) {
  if (event.isFeast) return feast();

  addToStory('arena', event.intro);
  let anyoneCaught = false;

  livingTributes().forEach((tribute) => {
    const roll = Math.random();
    if (roll >= deathChance + 0.2) return; // not caught

    anyoneCaught = true;
    const lifesaver = findItem(tribute, event.counter);

    if (lifesaver && chance(0.6)) {
      if (lifesaver.kind === KIND.HEALING) removeItem(tribute, lifesaver); // medicine gets used up
      addToStory('item', ARENA_STORY.savedBy, { a: tribute, item: lifesaver.name });
    } else if (roll < deathChance && moreThanOneAlive()) {
      addToStory('death', ARENA_STORY.dies, { a: tribute });
      killTribute(tribute);
    } else {
      tribute.wounded = true;
      addToStory('hurt', ARENA_STORY.wounded, { a: tribute });
    }
  });

  if (!anyoneCaught) addToStory('', ARENA_STORY.everyoneSafe);
}

/** Half the tributes risk the Cornucopia: they pair off and fight, and survivors take a prize. */
export function feast() {
  game.feastHappened = true;
  addToStory('arena', ARENA_STORY.feastAnnounced);

  const attendees = shuffle(livingTributes()).filter(() => chance(0.5));
  if (!attendees.length) return addToStory('', ARENA_STORY.feastEmpty);

  for (let i = 0; i + 1 < attendees.length; i += 2) {
    const [a, b] = [attendees[i], attendees[i + 1]];
    if (!sameAlliance(a, b)) fight(a, b, 0, 0.7);
  }

  attendees.forEach((tribute) => {
    if (!tribute.alive) return;
    const prize = randomItem();
    tribute.items.push(prize);
    addToStory('item', ARENA_STORY.feastPrize, { a: tribute, item: prize.name });
  });
}

// ---------- one tribute ----------

/** An accident. Late in the game (underPressure) it is deadlier. */
export function hazard(tribute, underPressure) {
  const roll = Math.random();
  const deathChance = underPressure ? 0.4 : 0.3;

  if (roll < deathChance && moreThanOneAlive()) {
    addToStory('death', pickRandom(HAZARDS.deadly), { a: tribute });
    killTribute(tribute);
  } else if (roll < 0.65) {
    tribute.wounded = true;
    addToStory('hurt', pickRandom(HAZARDS.wounding), { a: tribute });
  } else {
    addToStory('', pickRandom(HAZARDS.closeCall), { a: tribute });
  }
}

export async function strangeBerries(tribute) {
  const choice = await decide(tribute, QUESTIONS.berries, { a: tribute }, [50, 50]);
  if (choice === 1) return addToStory('', BERRIES.leftAlone, { a: tribute });

  const roll = Math.random();
  if (roll < 0.55) {
    tribute.wounded = false;
    addToStory('item', BERRIES.delicious, { a: tribute });
  } else if (roll < 0.8 || !moreThanOneAlive()) {
    tribute.wounded = true;
    addToStory('hurt', BERRIES.sick, { a: tribute });
  } else {
    addToStory('death', BERRIES.deadly, { a: tribute });
    killTribute(tribute);
  }
}

/** A tribute with rope, a net or wire builds either a snare (food) or a trap for other tributes. */
export async function buildTrap(tribute, material) {
  const choice = await decide(tribute, QUESTIONS.trap, { a: tribute, item: material.name }, [50, 50]);
  if (chance(0.5)) removeItem(tribute, material);

  if (choice === 0) {
    if (chance(0.7)) {
      tribute.items.push(randomItem(KIND.FOOD));
      addToStory('item', TRAPS.snareWorks, { a: tribute });
    } else {
      addToStory('', TRAPS.snareEmpty, { a: tribute });
    }
    return;
  }

  const possibleVictims = livingTributes().filter((other) => other !== tribute && !sameAlliance(tribute, other));
  const victim = pickRandom(possibleVictims);
  const roll = Math.random();

  if (victim && roll < 0.45) {
    if (victim.wounded || chance(0.5)) {
      addToStory('death', TRAPS.kills, { a: tribute, b: victim });
      killTribute(victim, tribute);
    } else {
      victim.wounded = true;
      addGrudge(victim, tribute);
      addToStory('hurt', TRAPS.wounds, { a: tribute, b: victim });
    }
  } else if (roll < 0.6) {
    tribute.wounded = true;
    addToStory('hurt', TRAPS.backfires, { a: tribute });
  } else {
    addToStory('', TRAPS.nobodyComes, { a: tribute });
  }
}

/** A tribute uses something they carry. Items help most of the time, not always. */
export function useRandomItem(tribute) {
  const item = pickRandom(tribute.items);
  const values = { a: tribute, item: item.name };
  const roll = Math.random();

  if (item.kind === KIND.HEALING && tribute.wounded) {
    removeItem(tribute, item);
    if (roll < 0.8) {
      tribute.wounded = false;
      addToStory('item', ITEM_STORY.healed, values);
    } else {
      addToStory('bad', ITEM_STORY.healFails, values);
    }
  } else if (item.kind === KIND.FOOD) {
    removeItem(tribute, item);
    if (roll < 0.12) {
      tribute.wounded = true;
      addToStory('hurt', ITEM_STORY.spoiled, values);
    } else {
      addToStory('item', ITEM_STORY.eats, values);
    }
  } else if (item.kind === KIND.WEAPON && roll < 0.08) {
    tribute.wounded = true;
    addToStory('hurt', ITEM_STORY.trainingAccident, values);
  } else if (item.kind === KIND.WEAPON && roll < 0.14) {
    removeItem(tribute, item);
    addToStory('bad', ITEM_STORY.dropped, values);
  } else {
    addToStory('', item.kind === KIND.WEAPON ? ITEM_STORY.trains : ITEM_STORY.checksGear, values);
  }
}
