// The flow of the Games: the Bloodbath, then days and nights until one tribute is left.
import { ARENA_EVENTS, FEAST } from '../data/arena-events.js';
import { KIND, randomItem } from '../data/items.js';
import { BLOODBATH, DISTRICT_BONDS, FILLER, FINALE, ITEM_STORY, PHASES, QUESTIONS } from '../data/story.js';
import { chance, pickRandom, randomInt, shuffle, weightedIndex } from '../utils/random.js';
import { fight } from './combat.js';
import { allyMoment, meetSomeone } from './encounters.js';
import { arenaEvent, buildTrap, feast, hazard, strangeBerries, useRandomItem } from './events.js';
import {
  addGrudge, addToStory, decide, dissolveLonelyAlliances, findItem, game, livingTributes, sameAlliance,
} from './state.js';
import { formatText, nameTag } from './text.js';

const MAX_CHOICES_PER_ROUND = 2; // keeps the game moving: about 15 to 20 pop-ups per game

// ---------- the Bloodbath ----------

/** District partners (1 & 2, 3 & 4...) start as friends (allied), rivals (grudges) or strangers. */
function setDistrictBonds() {
  for (let i = 0; i + 1 < game.tributes.length; i += 2) {
    const [a, b] = [game.tributes[i], game.tributes[i + 1]];
    const bond = randomInt(3); // 0 friends, 1 rivals, 2 strangers

    if (bond === 0) a.alliance = b.alliance = ++game.allianceCount;
    if (bond === 1) {
      addGrudge(a, b);
      addGrudge(b, a);
    }
    addToStory(['team', 'bad', ''][bond], DISTRICT_BONDS[bond], { n: a.district, a, b });
  }
}

async function bloodbath() {
  setDistrictBonds();
  const rushers = [];
  const packGrabbers = [];

  for (const tribute of shuffle(livingTributes())) {
    const choice = await decide(tribute, QUESTIONS.cornucopia, { a: tribute }, [35, 35, 30]);

    if (choice === 0) {
      rushers.push(tribute);
      if (chance(0.75)) {
        const weapon = randomItem(KIND.WEAPON);
        tribute.items.push(weapon);
        addToStory('item', BLOODBATH.grabsWeapon, { a: tribute, item: weapon.name });
      } else {
        addToStory('', BLOODBATH.tooLate, { a: tribute });
      }
    } else if (choice === 1) {
      packGrabbers.push(tribute);
      if (chance(0.85)) {
        const supply = randomItem(pickRandom([KIND.ARMOR, KIND.HEALING, KIND.FOOD, KIND.TRAP, KIND.GEAR]));
        tribute.items.push(supply);
        addToStory('item', BLOODBATH.grabsPack, { a: tribute, item: supply.name });
      } else {
        addToStory('bad', BLOODBATH.emptyPack, { a: tribute });
      }
    } else {
      addToStory('', pickRandom(BLOODBATH.flees), { a: tribute });
    }
  }

  // Rushers fight each other in pairs (district friends spare each other).
  for (let i = 0; i + 1 < rushers.length; i += 2) {
    const [a, b] = [rushers[i], rushers[i + 1]];
    if (!sameAlliance(a, b)) fight(a, b, 0, 0.85);
  }

  // Some pack grabbers get caught by a surviving rusher.
  packGrabbers.forEach((tribute) => {
    const hunters = rushers.filter((rusher) => rusher.alive && !sameAlliance(rusher, tribute));
    if (tribute.alive && hunters.length && chance(0.15)) fight(pickRandom(hunters), tribute, 0.2, 0.7);
  });
}

// ---------- between rounds ----------

/**
 * At the start of each day, something may happen to the whole arena:
 * a fallen player in the room sends a sponsor gift, or one player in the room
 * (alive or not) decides which disaster hits everyone.
 */
async function startOfDay() {
  const playersInRoom = game.tributes.filter((tribute) => tribute.present);
  const fallenInRoom = playersInRoom.filter((tribute) => !tribute.alive);

  if (fallenInRoom.length && chance(0.35)) {
    game.choicesLeft--;
    const sponsor = pickRandom(fallenInRoom);
    const candidates = shuffle(livingTributes()).slice(0, 4);
    const gift = randomItem();
    const question = formatText(QUESTIONS.sponsor.text, { sponsor, item: gift.name });
    const options = candidates.map((tribute) => [tribute.name, tribute.name]);
    const receiver = candidates[await game.askPlayer(sponsor, question, options)];

    receiver.items.push(gift);
    addToStory('item', ITEM_STORY.fromSponsor, { sponsor, a: receiver, item: gift.name });
  } else if (playersInRoom.length && chance(0.45)) {
    game.choicesLeft--;
    const gamemaker = pickRandom(playersInRoom);
    const events = shuffle([...ARENA_EVENTS, ...(game.feastHappened ? [] : [FEAST])]).slice(0, 3);
    const question = formatText(QUESTIONS.gamemaker.text, { sponsor: gamemaker });
    const options = events.map((event) => event.name);
    const forWholeArena = true;

    arenaEvent(events[await game.askPlayer(gamemaker, question, options, forWholeArena)]);
  } else if (!game.feastHappened && livingTributes().length <= 8) {
    feast();
  } else if (game.day > 1 && chance(0.2)) {
    arenaEvent(pickRandom(ARENA_EVENTS));
  }
}

// ---------- a normal day or night ----------

/** Every living tribute gets one turn, in random order. Some turns involve a second tribute. */
async function everyonesTurn(isNight) {
  const busy = new Set();

  for (const tribute of shuffle(livingTributes())) {
    if (!tribute.alive || busy.has(tribute)) continue;
    busy.add(tribute);

    const underPressure = game.day >= 5 || livingTributes().length <= 5;
    const trapMaterial = findItem(tribute, KIND.TRAP);
    const ally = pickRandom(livingTributes().filter(
      (other) => other !== tribute && sameAlliance(tribute, other) && !busy.has(other),
    ));

    // How likely each kind of turn is. Late in the game, more fights and fewer quiet moments.
    const turnWeights = {
      meetSomeone: underPressure ? 60 : 36,
      findItem: 12,
      useItem: tribute.items.length ? 14 : 0,
      parachute: 6,
      hazard: underPressure ? 10 : 6,
      allyMoment: ally ? 12 : 0,
      buildTrap: trapMaterial ? 7 : 0,
      berries: 4,
      quiet: underPressure ? 10 : 25,
    };
    const turn = Object.keys(turnWeights)[weightedIndex(Object.values(turnWeights))];

    if (turn === 'meetSomeone') await meetSomeone(tribute, busy, isNight);
    else if (turn === 'findItem') {
      const found = randomItem();
      tribute.items.push(found);
      addToStory('item', pickRandom(ITEM_STORY.found), { a: tribute, item: found.name });
    } else if (turn === 'useItem') useRandomItem(tribute);
    else if (turn === 'parachute') {
      const gift = randomItem();
      tribute.items.push(gift);
      addToStory('item', ITEM_STORY.parachute, { a: tribute, item: gift.name });
    } else if (turn === 'hazard') hazard(tribute, underPressure);
    else if (turn === 'allyMoment') {
      busy.add(ally);
      await allyMoment(tribute, ally);
    } else if (turn === 'buildTrap') await buildTrap(tribute, trapMaterial);
    else if (turn === 'berries') await strangeBerries(tribute);
    else addToStory('', pickRandom(isNight ? FILLER.night : FILLER.day), { a: tribute });
  }
}

// ---------- the final duel ----------

/**
 * Each finalist picks a tactic, like rock-paper-scissors:
 * ambush beats charge, waiting beats ambush, charge beats waiting.
 * The better tactic gives an edge, but luck still decides.
 */
async function finalDuel() {
  const [a, b] = livingTributes();
  a.alliance = b.alliance = 0;
  addToStory('arena', FINALE.announced, { a, b });

  const tacticA = await decide(a, QUESTIONS.finalDuel, { a, b }, [1, 1, 1]);
  const tacticB = await decide(b, QUESTIONS.finalDuel, { a: b, b: a }, [1, 1, 1]);
  addToStory('', FINALE.tactics[tacticA], { a });
  addToStory('', FINALE.tactics[tacticB], { a: b });

  const outcome = (tacticA - tacticB + 3) % 3; // 0 same tactic, 1 a wins the matchup, 2 b wins it
  const edge = [0, 0.3, -0.3][outcome];
  while (livingTributes().length === 2) fight(a, b, edge, 0.9);
}

// ---------- one round ----------

/** Plays the next round (Bloodbath, Day or Night) and adds it to the story. */
export async function playNextRound() {
  game.round++;
  game.day = Math.floor(game.round / 2);
  const isNight = game.round > 1 && game.round % 2 === 1;
  const aliveAtStart = livingTributes().length;
  const isFinale = aliveAtStart === 2;

  // Everyone present chooses at the Bloodbath and in the final duel; otherwise a few pop-ups per round.
  game.choicesLeft = game.round === 1 || isFinale ? Infinity : MAX_CHOICES_PER_ROUND;

  const titleTemplate = game.round === 1 ? PHASES.bloodbath : isNight ? PHASES.night : PHASES.day;
  game.title = formatText(titleTemplate, { n: game.day });
  game.log.push({ style: isNight ? 'heading night' : 'heading', text: game.title });

  if (game.round === 1) {
    await bloodbath();
  } else if (isFinale) {
    await finalDuel();
  } else {
    const living = livingTributes();
    if (living.every((tribute) => sameAlliance(tribute, living[0]))) {
      living.forEach((tribute) => { tribute.alliance = 0; });
      addToStory('bad', PHASES.alliancesShatter);
    }

    if (!isNight) await startOfDay();
    await everyonesTurn(isNight);

    // Nobody died late in the game: the Gamemakers step in so the Games always end.
    const nobodyDied = livingTributes().length === aliveAtStart;
    if (nobodyDied && (game.day >= 4 || aliveAtStart <= 4)) {
      arenaEvent(pickRandom(ARENA_EVENTS), 0.3);
      if (livingTributes().length === aliveAtStart) {
        const [a, b] = shuffle(livingTributes());
        a.alliance = b.alliance = 0;
        dissolveLonelyAlliances();
        fight(a, b, 0, 0.9);
      }
    }
  }

  const fallen = game.fallenThisRound;
  addToStory('cannon', fallen.length ? PHASES.cannons : PHASES.noCannons, {
    n: fallen.length,
    names: fallen.map(nameTag).join(', '),
  });
  game.fallenThisRound = [];

  if (livingTributes().length === 1) {
    game.winner = livingTributes()[0];
    addToStory('win', PHASES.winner, { a: game.winner });
  }
}
