// Plays thousands of games with random answers and checks that the engine is fair and never breaks.
// Run with: npm test   (or: node test/simulate.test.js)
import assert from 'node:assert/strict';
import { playNextRound } from '../js/engine/rounds.js';
import { game, livingTributes, restoreGame, snapshotGame, startNewGame } from '../js/engine/state.js';
import { randomInt } from '../js/utils/random.js';

const GAMES = 5000;
const TRIBUTES = 24;
const BROKEN_TEXT = /undefined|\{|NaN|null|false/;

const winsPerTribute = Array(TRIBUTES).fill(0);
let totalRounds = 0;
let totalChoices = 0;

const answerRandomly = async (tribute, question, options) => {
  totalChoices++;
  return randomInt(options.length);
};

for (let g = 0; g < GAMES; g++) {
  // Every second tribute is "in the room", so pop-ups happen.
  const roster = Array.from({ length: TRIBUTES }, (_, i) => ({ name: `T${i}`, present: i % 2 === 0 }));
  startNewGame(roster, answerRandomly);

  while (!game.winner) {
    await playNextRound();
    assert.ok(game.round < 200, 'a game did not end');

    // Every other game: save and reload between rounds, like closing and reopening the app.
    if (!game.winner && g % 2) restoreGame(snapshotGame(), answerRandomly);
  }

  assert.equal(livingTributes().length, 1, 'there must be exactly one winner');
  const brokenLine = game.log.find((entry) => entry.text.some((line) => BROKEN_TEXT.test(line)));
  assert.equal(brokenLine, undefined, `a story line has missing text: ${JSON.stringify(brokenLine)}`);

  winsPerTribute[game.winner.id]++;
  totalRounds += game.round;
}

const fewest = Math.min(...winsPerTribute);
const most = Math.max(...winsPerTribute);
console.log({
  averageRounds: totalRounds / GAMES,
  averageChoices: totalChoices / GAMES,
  fewestWinsForOneTribute: fewest,
  mostWinsForOneTribute: most,
});

// With 5000 games and 24 tributes, each should win about 208 times.
assert.ok(fewest > 120 && most < 300, 'some tributes win much more than others');
console.log('All checks passed.');
