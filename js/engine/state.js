// The game state and the small rules every part of the engine shares.
// No screen code here, so the engine can also run in the test (test/simulate.test.js).
import { randomInt, weightedIndex } from '../utils/random.js';
import { formatText } from './text.js';

/** The current game. Other modules read it; only this file replaces it. */
export let game = null;

// Picks a random answer: used when no screen is attached (tests).
const answerRandomly = async (tribute, question, options) => randomInt(options.length);

/**
 * Starts a fresh game.
 * roster: [{ name, photo, present }] in district order (1 & 2 are District 1, 3 & 4 District 2...).
 * askPlayer(tribute, question, options, forWholeArena) must resolve to the chosen option index.
 */
export function startNewGame(roster, askPlayer = answerRandomly) {
  game = {
    tributes: roster.map((entry, index) => ({
      id: index,
      district: Math.floor(index / 2) + 1,
      name: entry.name,
      photo: entry.photo || null,
      present: entry.present,
      alive: true,
      wounded: false,
      items: [],
      alliance: 0,   // 0 means no alliance; same number means same alliance
      grudges: [],   // ids of tributes this one wants revenge on
      kills: 0,
      diedOnDay: 0,
    })),
    log: [],              // the story so far: { style, text: [english, french] }
    round: 0,             // 1 = Bloodbath, 2 = Day 1, 3 = Night 1, 4 = Day 2...
    day: 0,
    title: null,
    allianceCount: 0,
    fallenThisRound: [],
    feastHappened: false,
    choicesLeft: 0,       // pop-ups still allowed this round
    winner: null,
    askPlayer,
  };
  return game;
}

/** A plain copy of the game that can be saved as JSON. */
export function snapshotGame() {
  const { askPlayer, winner, ...rest } = game;
  return JSON.parse(JSON.stringify({ ...rest, winnerId: winner ? winner.id : null }));
}

/** Brings back a game saved with snapshotGame(). */
export function restoreGame(saved, askPlayer = answerRandomly) {
  const { winnerId, ...rest } = saved;
  game = { ...rest, winner: winnerId == null ? null : rest.tributes[winnerId], askPlayer };
  return game;
}

// ---------- story ----------

/** Adds a sentence to the story. style colours it on screen: death, hurt, item, team, arena, bad... */
export function addToStory(style, templatePair, values) {
  game.log.push({ style, text: formatText(templatePair, values) });
}

// ---------- tributes ----------

export const livingTributes = () => game.tributes.filter((tribute) => tribute.alive);

/** Never kill the last tribute standing by accident. */
export const moreThanOneAlive = () => livingTributes().length > 1;

export const findItem = (tribute, kind) => tribute.items.find((item) => item.kind === kind);

export const removeItem = (tribute, item) => tribute.items.splice(tribute.items.indexOf(item), 1);

export const holdsGrudge = (tribute, other) => tribute.grudges.includes(other.id);

export function addGrudge(tribute, other) {
  if (!holdsGrudge(tribute, other)) tribute.grudges.push(other.id);
}

export function forgiveGrudge(tribute, other) {
  tribute.grudges = tribute.grudges.filter((id) => id !== other.id);
}

export const sameAlliance = (a, b) => a.alliance !== 0 && a.alliance === b.alliance;

/** An alliance of one is no alliance. */
export function dissolveLonelyAlliances() {
  const living = livingTributes();
  living.forEach((tribute) => {
    const hasAlly = living.some((other) => other !== tribute && sameAlliance(tribute, other));
    if (!hasAlly) tribute.alliance = 0;
  });
}

/** Kills a tribute. If someone did it, the victim's allies now hold a grudge against the killer. */
export function killTribute(victim, killer) {
  victim.alive = false;
  victim.diedOnDay = game.day;
  game.fallenThisRound.push(victim);

  if (killer) {
    killer.kills++;
    livingTributes().forEach((tribute) => {
      if (tribute !== killer && sameAlliance(tribute, victim)) addGrudge(tribute, killer);
    });
  }

  victim.alliance = 0;
  dissolveLonelyAlliances();
}

// ---------- decisions ----------

/**
 * Who decides what a tribute does: the player, if they are in the room and the round still
 * allows a pop-up, otherwise the app rolls using the weights (one per option).
 */
export async function decide(tribute, question, values, weights) {
  if (tribute.present && game.choicesLeft > 0) {
    game.choicesLeft--;
    return game.askPlayer(tribute, formatText(question.text, values), question.options);
  }
  return weightedIndex(weights);
}
