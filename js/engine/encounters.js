// When two tributes cross paths: fights, alliances, sleeping targets, and loyalty between allies.
import { KIND } from '../data/items.js';
import { ALLIANCE, ENCOUNTERS, FILLER, ITEM_STORY, QUESTIONS } from '../data/story.js';
import { chance, pickRandom } from '../utils/random.js';
import { fight } from './combat.js';
import {
  addGrudge, addToStory, decide, dissolveLonelyAlliances, findItem, forgiveGrudge, game,
  holdsGrudge, killTribute, livingTributes, removeItem, sameAlliance,
} from './state.js';

const MAX_ALLIANCE_SIZE = 4;

/**
 * tribute runs into someone who is not busy and not an ally.
 * Tributes with a grudge are more likely to find the person they hate.
 * busy: tributes who already had their turn this round.
 */
export async function meetSomeone(tribute, busy, isNight) {
  const candidates = livingTributes().filter(
    (other) => other !== tribute && !busy.has(other) && !sameAlliance(tribute, other),
  );
  if (!candidates.length) {
    return addToStory('', pickRandom(isNight ? FILLER.night : FILLER.day), { a: tribute });
  }

  const enemies = candidates.filter((other) => holdsGrudge(tribute, other));
  const other = enemies.length && chance(0.6) ? pickRandom(enemies) : pickRandom(candidates);
  busy.add(other);

  if (isNight && chance(0.35)) return findSleeper(tribute, other);
  return faceToFace(tribute, other);
}

async function findSleeper(tribute, sleeper) {
  const values = { a: tribute, b: sleeper };
  const weights = holdsGrudge(tribute, sleeper) ? [70, 20, 10] : [35, 30, 35]; // strike, steal, walk away
  const choice = await decide(tribute, QUESTIONS.sleeper, values, weights);

  if (choice === 0) {
    if (chance(0.65)) {
      addToStory('death', ENCOUNTERS.killsSleeper, values);
      killTribute(sleeper, tribute);
    } else {
      addToStory('bad', ENCOUNTERS.sleeperWakes, values);
      addGrudge(sleeper, tribute);
      fight(sleeper, tribute, 0.15);
    }
  } else if (choice === 1 && sleeper.items.length) {
    if (chance(0.7)) {
      const stolen = pickRandom(sleeper.items);
      removeItem(sleeper, stolen);
      tribute.items.push(stolen);
      addToStory('item', ENCOUNTERS.steals, { ...values, item: stolen.name });
    } else {
      addGrudge(sleeper, tribute);
      addToStory('bad', ENCOUNTERS.caughtStealing, values);
    }
  } else {
    addToStory('', ENCOUNTERS.leavesSleeper, values);
  }
}

async function faceToFace(tribute, other) {
  const values = { a: tribute, b: other };
  const hates = holdsGrudge(tribute, other);
  const sameDistrict = tribute.district === other.district;

  // Weights for: attack, offer an alliance, slip away.
  let weights = [45, 20, 35];
  if (hates) weights = [80, 0, 20];
  else if (livingTributes().length <= 5) weights = [60, 5, 35];
  else if (sameDistrict) weights = [20, 50, 30];

  const choice = await decide(tribute, QUESTIONS.meeting, values, weights);

  if (choice === 0) {
    if (hates) addToStory('bad', ENCOUNTERS.hunted, values);
    fight(tribute, other, 0.1);
  } else if (choice === 1) {
    await offerAlliance(tribute, other);
  } else {
    addToStory('', ENCOUNTERS.slipsAway, values);
  }
}

async function offerAlliance(tribute, other) {
  const values = { a: tribute, b: other };

  // Weights for: accept, refuse, attack instead.
  let weights = [60, 30, 10];
  if (holdsGrudge(other, tribute)) weights = [10, 40, 50];
  else if (tribute.district === other.district) weights = [80, 15, 5];

  const answer = await decide(other, QUESTIONS.allianceOffer, values, weights);

  // Whoever already has an alliance brings the other one in.
  const host = tribute.alliance ? tribute : other;
  const guest = host === tribute ? other : tribute;
  const allianceIsFull = host.alliance
    && livingTributes().filter((t) => t.alliance === host.alliance).length >= MAX_ALLIANCE_SIZE;

  if (answer === 0 && !allianceIsFull) {
    host.alliance = host.alliance || ++game.allianceCount;
    guest.alliance = host.alliance;
    dissolveLonelyAlliances();
    forgiveGrudge(tribute, other);
    forgiveGrudge(other, tribute);
    addToStory('team', ENCOUNTERS.allianceFormed, values);
  } else if (answer === 2) {
    addToStory('bad', ENCOUNTERS.offerAnsweredWithAttack, values);
    fight(other, tribute, 0.15);
  } else {
    addGrudge(tribute, other);
    addToStory('', ENCOUNTERS.allianceRefused, values);
  }
}

/**
 * Two allies spend time together. Late in the game, one may betray the other
 * (district partners almost never do). Otherwise they help each other.
 */
export async function allyMoment(tribute, ally) {
  const values = { a: tribute, b: ally };
  const tributesLeft = livingTributes().length;

  let choice = 0; // stay loyal
  if (tributesLeft <= 8) {
    let weights = [88, 12];
    if (tribute.district === ally.district) weights = [92, 8];
    else if (tributesLeft <= 5) weights = [65, 35];
    choice = await decide(tribute, QUESTIONS.loyalty, values, weights);
  }

  if (choice === 1) {
    tribute.alliance = 0;
    dissolveLonelyAlliances();
    addGrudge(ally, tribute);
    addToStory('bad', ALLIANCE.betrayal, values);
    fight(tribute, ally, 0.3, 0.75);
    return;
  }

  const medicine = ally.wounded && findItem(tribute, KIND.HEALING);
  if (medicine) {
    removeItem(tribute, medicine);
    ally.wounded = false;
    addToStory('item', ITEM_STORY.healsAlly, { ...values, item: medicine.name });
  } else {
    addToStory('team', pickRandom(ALLIANCE.loyal), values);
  }
}
