// Starts the app: holds the screen state, reacts to taps, saves progress.
import { UI_TEXT } from '../data/ui-text.js';
import { playNextRound } from '../engine/rounds.js';
import { game, restoreGame, snapshotGame, startNewGame } from '../engine/state.js';
import { promptInstall, setupInstall } from './install.js';
import { photoToSmallSquare } from './photos.js';
import { KEYS, load, save } from './storage.js';
import { applyUpdate, watchForUpdates } from './updates.js';
import { gameView, setupView } from './views.js';

const DEFAULT_TRIBUTE_COUNT = 24;
const appElement = document.getElementById('app');

const emptyRoster = () => Array.from({ length: DEFAULT_TRIBUTE_COUNT }, () => ({ name: '', photo: null, present: true }));

// Everything about the screen that is not the game itself.
const state = {
  language: load(KEYS.language) ?? 0, // 0 English, 1 French
  screen: 'setup',                    // 'setup' or 'game'
  roster: load(KEYS.roster) ?? emptyRoster(),
  decision: null,                     // the open pop-up: { tribute, question, options, forWholeArena, answer }
  roundRunning: false,
  showBoard: false,                   // phones show either the story or the tribute board
  firstNewEntry: 0,                   // story entries from here on are new (scrolled to, animated)
  confirmQuit: false,
  showIosHint: false,
  updateAvailable: false,            // a newer version is on GitHub
};

/** The engine calls this when a player in the room must choose. Resolves when they tap an option. */
function askPlayer(tribute, question, options, forWholeArena = false) {
  return new Promise((answer) => {
    state.decision = { tribute, question, options, forWholeArena, answer };
    render();
  });
}

// ---------- drawing ----------

function render() {
  document.documentElement.lang = state.language ? 'fr' : 'en';
  document.title = UI_TEXT.title[state.language];
  appElement.innerHTML = state.screen === 'setup' ? setupView(state) : gameView(state, game);
  scrollToNewestEntries();
}

function scrollToNewestEntries() {
  const story = document.getElementById('story');
  if (!story) return;
  const firstNew = document.getElementById(`entry-${state.firstNewEntry}`);
  if (firstNew) firstNew.scrollIntoView({ block: 'start' });
  else story.scrollTop = story.scrollHeight;
}

// ---------- actions (one per button) ----------

const actions = {
  toggleLanguage() {
    state.language = 1 - state.language;
    save(KEYS.language, state.language);
  },

  update() {
    applyUpdate();
  },

  install() {
    promptInstall();
  },

  toggleIosHint() {
    state.showIosHint = !state.showIosHint;
  },

  addTribute() {
    state.roster.push({ name: '', photo: null, present: true });
    save(KEYS.roster, state.roster);
  },

  removeTribute(index) {
    state.roster.splice(index, 1);
    save(KEYS.roster, state.roster);
  },

  startGame() {
    save(KEYS.roster, state.roster);
    const tributeWord = UI_TEXT.tribute[state.language];
    const roster = state.roster.map((entry, index) => ({ ...entry, name: entry.name.trim() || `${tributeWord} ${index + 1}` }));
    startNewGame(roster, askPlayer);
    state.screen = 'game';
    state.firstNewEntry = 0;
    state.showBoard = false;
  },

  toggleBoard() {
    state.showBoard = !state.showBoard;
  },

  quit() {
    if (!state.confirmQuit) {
      state.confirmQuit = true; // first tap asks "Really quit?"
      return;
    }
    state.confirmQuit = false;
    state.decision = null;
    state.roundRunning = false;
    save(KEYS.game, null);
    state.screen = 'setup';
  },

  choose(index) {
    if (!state.decision) return;
    const { answer } = state.decision;
    state.decision = null;
    // firstNewEntry stays at the round's heading, so the story opens at the top of the day or night.
    answer(index);
  },

  async nextRound() {
    if (state.roundRunning) return;
    if (game.winner) {
      save(KEYS.game, null);
      state.screen = 'setup';
      return;
    }

    state.roundRunning = true;
    state.showBoard = false;
    state.firstNewEntry = game.log.length;
    const thisGame = game;

    await playNextRound();
    if (thisGame !== game || state.screen !== 'game') return; // quit during the round

    state.roundRunning = false;
    save(KEYS.game, snapshotGame()); // shortcut: saved between rounds only; a reload mid-round replays that round
    render();
  },
};

// ---------- events ----------

const PRESS_TIME = 160; // milliseconds a tapped button stays pressed before its action runs
let pressing = false;

appElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled || pressing) return;

  // Show the press first, then act: otherwise the screen redraws before the tap can be seen.
  pressing = true;
  button.classList.add('pressed');
  navigator.vibrate?.(12); // a short buzz on Android; iPhones ignore this

  setTimeout(() => {
    pressing = false;
    const action = button.dataset.action;
    if (action !== 'quit') state.confirmQuit = false;

    const result = actions[action](Number(button.dataset.index));
    if (!(result instanceof Promise)) render(); // async actions draw the screen when they finish
  }, PRESS_TIME);
});

// iPhone Safari only shows the :active press style if the page listens for touches.
document.addEventListener('touchstart', () => {}, { passive: true });

appElement.addEventListener('input', async (event) => {
  const { field, index } = event.target.dataset;
  const i = Number(index);

  if (field === 'name') state.roster[i].name = event.target.value;
  else if (field === 'here') state.roster[i].present = event.target.checked;
  else if (field === 'present') game.tributes[i].present = event.target.checked;
  else if (field === 'photo' && event.target.files[0]) {
    try {
      state.roster[i].photo = await photoToSmallSquare(event.target.files[0]);
    } catch {
      return; // not an image: keep the old photo
    }
    render();
  }

  if (state.screen === 'setup') save(KEYS.roster, state.roster);
});

// ---------- start ----------

const savedGame = load(KEYS.game);
if (savedGame && savedGame.tributes) {
  restoreGame(savedGame, askPlayer);
  state.screen = 'game';
  state.firstNewEntry = game.log.length;
}

watchForUpdates(() => {
  state.updateAvailable = true;
  render();
});
setupInstall(() => {
  if (state.screen === 'setup') render();
});
render();
