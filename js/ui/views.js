// Builds the HTML for each screen from the current state. No game logic here.
import { PHASES } from '../data/story.js';
import { UI_TEXT } from '../data/ui-text.js';
import { NAME_END, NAME_START, formatText } from '../engine/text.js';
import { installMode } from './install.js';

// ---------- helpers ----------

const escapeHtml = (text) =>
  String(text).replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));

/** A story sentence in the chosen language, with tribute names in bold. */
const storyHtml = (pair, language) =>
  escapeHtml(pair[language]).replaceAll(NAME_START, '<b>').replaceAll(NAME_END, '</b>');

/** The round photo, or the first letters of the name if there is no photo. */
function avatar(tribute, fallbackText) {
  if (tribute.photo) return `<img class="avatar" src="${tribute.photo}" alt="">`;
  const letters = (tribute.name || fallbackText || '').trim().slice(0, 2);
  return `<span class="avatar">${escapeHtml(letters)}</span>`;
}

const isNightRound = (game) => game.round > 1 && game.round % 2 === 1;

/** Shown only when a new version is out. Disabled mid-round, since the game saves between rounds. */
function updateButton(state, t) {
  if (!state.updateAvailable) return '';
  const busy = state.roundRunning || state.decision;
  return `<button class="update-button" data-action="update" ${busy ? 'disabled' : ''}>${t('update')}</button>`;
}

// ---------- setup screen ----------

function installButton(state, t) {
  const mode = installMode();
  if (mode === 'prompt') return `<button data-action="install">${t('install')}</button>`;
  if (mode === 'ios') return `<button data-action="toggleIosHint" aria-expanded="${state.showIosHint}">${t('install')}</button>`;
  return '';
}

function rosterRow(entry, index, t) {
  const number = index + 1;
  const district = Math.floor(index / 2) + 1;
  const photo = entry.photo ? avatar(entry) : '<span class="avatar" aria-hidden="true">📷</span>';

  return `<li>
    <span class="district-tag">D${district}</span>
    <label class="photo-picker" title="${t('photoOf')} ${t('tribute')} ${number}">
      ${photo}
      <input type="file" id="photo-${index}" data-field="photo" data-index="${index}" accept="image/*"
        class="visually-hidden" aria-label="${t('photoOf')} ${t('tribute')} ${number}">
    </label>
    <input type="text" id="name-${index}" data-field="name" data-index="${index}" value="${escapeHtml(entry.name)}"
      placeholder="${t('tribute')} ${number}" aria-label="${t('tribute')} ${number}" maxlength="30">
    <label class="presence">
      <input type="checkbox" id="here-${index}" data-field="here" data-index="${index}" ${entry.present ? 'checked' : ''}>
      ${t('here')}
    </label>
    <button data-action="removeTribute" data-index="${index}" aria-label="${t('remove')} ${number}">×</button>
  </li>`;
}

export function setupView(state) {
  const t = (key) => UI_TEXT[key][state.language];

  return `
    <header class="top-bar">
      <h1>${t('title')}</h1>
      <div class="row">
        ${updateButton(state, t)}
        ${installButton(state, t)}
        <button data-action="toggleLanguage">${t('language')}</button>
      </div>
    </header>
    <main class="setup">
      ${state.showIosHint ? `<p class="hint">${t('iosHint')}</p>` : ''}
      <p class="intro">${t('intro')}</p>
      <ol class="roster-list">${state.roster.map((entry, index) => rosterRow(entry, index, t)).join('')}</ol>
      <div class="row">
        <button data-action="addTribute">${t('addTribute')}</button>
        <button class="big-button" data-action="startGame" ${state.roster.length < 2 ? 'disabled' : ''}>${t('start')}</button>
      </div>
    </main>`;
}

// ---------- game screen ----------

function storyFeed(state, game) {
  if (!game.log.length) return `<p class="entry">${UI_TEXT.ready[state.language]}</p>`;

  return game.log.map((entry, index) => {
    const html = storyHtml(entry.text, state.language);
    if (entry.style.startsWith('heading')) return `<h2 id="entry-${index}" class="${entry.style}">${html}</h2>`;
    const isNew = index >= state.firstNewEntry ? 'new' : '';
    return `<p id="entry-${index}" class="entry ${entry.style} ${isNew}">${html}</p>`;
  }).join('');
}

function tributeCard(tribute, game, state) {
  const t = (key) => UI_TEXT[key][state.language];

  // Names of living tributes this one holds a grudge against.
  const enemyNames = tribute.grudges.reduce((names, id) => {
    const enemy = game.tributes[id];
    return enemy.alive ? [...names, escapeHtml(enemy.name)] : names;
  }, []);

  let status = ['', t('statusAlive')];
  if (!tribute.alive) {
    const when = tribute.diedOnDay ? formatText(PHASES.day, { n: tribute.diedOnDay }) : PHASES.bloodbath;
    status = ['dead', `${t('statusDead')} · ${storyHtml(when, state.language)}`];
  } else if (tribute.wounded) {
    status = ['wounded', t('statusWounded')];
  }

  const details = [
    `${t('district')} ${tribute.district}`,
    tribute.alliance ? `<span class="ally">${t('alliance')} ${tribute.alliance}</span>` : '',
    tribute.kills ? `${tribute.kills} ${t('kills')}` : '',
    tribute.alive && enemyNames.length ? `${t('grudgeAgainst')} ${enemyNames.join(', ')}` : '',
  ].filter(Boolean).join(' · ');

  const items = tribute.alive && tribute.items.length
    ? `<div class="items">${tribute.items.map((item) => `<span>${escapeHtml(item.name[state.language])}</span>`).join('')}</div>`
    : '';

  return `<div class="card ${tribute.alive ? '' : 'dead'}">
    <div class="card-top">
      ${avatar(tribute)}
      <span class="name">${escapeHtml(tribute.name)}</span>
      <span class="pill ${status[0]}">${status[1]}</span>
      <label class="presence">
        <input type="checkbox" id="present-${tribute.id}" data-field="present" data-index="${tribute.id}" ${tribute.present ? 'checked' : ''}>
        ${t('here')}
      </label>
    </div>
    ${items}
    <div class="details">${details}</div>
  </div>`;
}

function decisionDialog(state) {
  const { tribute, question, options, forWholeArena } = state.decision;
  const t = (key) => UI_TEXT[key][state.language];
  const label = forWholeArena ? t('wholeArena') : tribute.alive ? t('decisionFor') : t('fallenButPlaying');

  return `<div class="overlay">
    <div class="decision" role="dialog" aria-modal="true" aria-labelledby="decision-name">
      <small>${label}</small>
      <div class="decision-name" id="decision-name">${avatar(tribute)}${escapeHtml(tribute.name)}</div>
      <p>${storyHtml(question, state.language)}</p>
      ${options.map((option, index) => `<button data-action="choose" data-index="${index}">${escapeHtml(option[state.language])}</button>`).join('')}
    </div>
  </div>`;
}

export function gameView(state, game) {
  const t = (key) => UI_TEXT[key][state.language];
  const aliveCount = game.tributes.filter((tribute) => tribute.alive).length;
  const sortedTributes = [...game.tributes].sort((a, b) => b.alive - a.alive || b.diedOnDay - a.diedOnDay);

  let mainButton = t('soundGong');
  if (game.winner) mainButton = t('newGame');
  else if (game.round) mainButton = t('continue');

  return `
    <header class="top-bar ${isNightRound(game) ? 'night' : ''}">
      <div>
        <h1>${game.round ? storyHtml(game.title, state.language) : t('title')}</h1>
        <span class="alive-count">${aliveCount} / ${game.tributes.length} ${t('aliveCount')}</span>
      </div>
      <div class="row">
        ${updateButton(state, t)}
        <button data-action="toggleLanguage">${t('language')}</button>
      </div>
    </header>
    <div class="stage ${state.showBoard ? 'show-board' : ''}">
      <section class="story" id="story">${storyFeed(state, game)}</section>
      <aside class="board">${sortedTributes.map((tribute) => tributeCard(tribute, game, state)).join('')}</aside>
    </div>
    <footer class="bottom-bar">
      <button data-action="quit">${state.confirmQuit ? t('reallyQuit') : t('quit')}</button>
      <button class="phone-only" data-action="toggleBoard">${state.showBoard ? t('showStory') : t('showBoard')}</button>
      <button class="big-button" data-action="nextRound" ${state.roundRunning ? 'disabled' : ''}>${mainButton}</button>
    </footer>
    ${state.decision ? decisionDialog(state) : ''}`;
}
