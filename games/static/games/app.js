// Small touches on top of the server-rendered pages: press feedback, scrolling the story,
// the phone story/board switch, the "here" ticks, photo upload and live updates. All game logic is on the server.
const PRESS_TIME = 160; // milliseconds a tapped button stays pressed before its form is sent
let pressing = false;

// Show the press first, then send the form: otherwise the page reloads before the tap can be seen.
document.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button || button.disabled || !button.form || (button.type && button.type !== 'submit')) return;
  event.preventDefault();
  if (pressing) return;
  pressing = true;
  button.classList.add('pressed');
  navigator.vibrate?.(12); // a short buzz on Android; iPhones ignore this
  setTimeout(() => button.form.requestSubmit(button), PRESS_TIME);
});

// Coming back with the browser's back button restores the page as it was: undo the press.
window.addEventListener('pageshow', () => {
  pressing = false;
  document.querySelectorAll('button.pressed').forEach((button) => button.classList.remove('pressed'));
});

// iPhone Safari only shows the :active press style if the page listens for touches.
document.addEventListener('touchstart', () => {}, { passive: true });

// A chosen photo is sent right away (together with the names typed so far).
document.addEventListener('change', async (event) => {
  const input = event.target;
  if (input.matches('input[data-photo]') && input.files.length) {
    input.form.requestSubmit(input.form.querySelector('button[value=save]'));
  } else if (input.matches('input[data-present-url]')) {
    const body = new URLSearchParams({ present: input.checked ? '1' : '0' });
    const token = document.querySelector('meta[name=csrf-token]').content;
    const response = await fetch(input.dataset.presentUrl, { method: 'POST', body, headers: { 'X-CSRFToken': token } });
    if (!response.ok) input.checked = !input.checked; // e.g. a question is open: undo the tick
  }
});

// Phones show either the story or the tribute board.
document.addEventListener('click', (event) => {
  const toggle = event.target.closest('[data-toggle-board]');
  if (!toggle) return;
  const stage = document.getElementById('stage');
  const showBoard = stage.classList.toggle('show-board');
  toggle.textContent = showBoard ? toggle.dataset.storyLabel : toggle.dataset.boardLabel;
});

// Open the story at the newest round, or at the end if there is nothing new.
const story = document.getElementById('story');
if (story) {
  const firstNew = document.getElementById(`entry-${story.dataset.firstNew}`);
  if (firstNew) firstNew.scrollIntoView({ block: 'start' });
  else story.scrollTop = story.scrollHeight;
}

// Live updates: players answer on their phones, so every page asks the server every few seconds
// whether the game changed, and reloads. If the person is typing or choosing something, a button
// offers the update instead, so nothing they entered is lost.
const liveUrl = document.body.dataset.liveUrl;
if (liveUrl) {
  const CHECK_EVERY = 2000; // milliseconds
  const banner = document.querySelector('[data-live-banner]');
  let edited = false;
  document.addEventListener('input', () => { edited = true; });

  const reload = () => {
    // The host's game page opens at the start of the newest round, as after pressing Continue.
    if (document.getElementById('story')) location.href = `${location.pathname}?new=1`;
    else location.reload();
  };

  const check = async () => {
    if (document.hidden || pressing) return;
    try {
      const response = await fetch(liveUrl, { cache: 'no-store' });
      const { version } = await response.json();
      if (String(version) === document.body.dataset.version) return;
      const busy = edited || document.activeElement?.matches('input, select, textarea')
        || document.querySelector('details[open][data-popover]');
      if (busy) {
        banner.classList.replace('hidden', 'flex');
      } else {
        reload();
      }
    } catch {
      // offline for a moment: try again on the next check
    }
  };

  setInterval(check, CHECK_EVERY);
  document.addEventListener('visibilitychange', check);
  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-live-reload]')) reload();
  });
}

// The cannon: one boom per fallen face in the sky, once per round, if this browser turned the sound on.
// The boom is made by the browser (no sound file): a low thump and a burst of rumble.
const CANNON_STAGGER = 800; // milliseconds between two shots, as FALLEN_STAGGER in views.py
const cannonsOn = () => { try { return localStorage.getItem('cannons') === 'on'; } catch { return false; } };

const boom = (audio, delay) => {
  const start = audio.currentTime + delay / 1000;
  const thump = audio.createOscillator();
  const thumpVolume = audio.createGain();
  thump.frequency.setValueAtTime(90, start);
  thump.frequency.exponentialRampToValueAtTime(30, start + 0.8);
  thumpVolume.gain.setValueAtTime(0.9, start);
  thumpVolume.gain.exponentialRampToValueAtTime(0.001, start + 1.2);
  thump.connect(thumpVolume).connect(audio.destination);
  thump.start(start);
  thump.stop(start + 1.2);

  const noise = audio.createBuffer(1, audio.sampleRate, audio.sampleRate);
  noise.getChannelData(0).forEach((_, i, samples) => { samples[i] = Math.random() * 2 - 1; });
  const rumble = audio.createBufferSource();
  const muffle = audio.createBiquadFilter();
  const rumbleVolume = audio.createGain();
  rumble.buffer = noise;
  muffle.type = 'lowpass';
  muffle.frequency.value = 400;
  rumbleVolume.gain.setValueAtTime(0.6, start);
  rumbleVolume.gain.exponentialRampToValueAtTime(0.001, start + 1);
  rumble.connect(muffle).connect(rumbleVolume).connect(audio.destination);
  rumble.start(start);
};

const cannonToggle = document.querySelector('[data-cannon-toggle]');
if (cannonToggle) {
  cannonToggle.setAttribute('aria-pressed', cannonsOn());
  cannonToggle.addEventListener('click', () => {
    try { localStorage.setItem('cannons', cannonsOn() ? 'off' : 'on'); } catch { return; }
    cannonToggle.setAttribute('aria-pressed', cannonsOn());
    if (cannonsOn()) boom(new AudioContext(), 0); // one test shot
  });
}

const sky = document.querySelector('[data-fallen]');
const skyKey = sky && `cannons-${sky.dataset.round}`;
if (sky && cannonsOn() && !sessionStorage.getItem(skyKey)) {
  sessionStorage.setItem(skyKey, 'fired'); // the page reloads often: fire once per round
  const audio = new AudioContext();
  const fire = () => sky.querySelectorAll('figure').forEach((_, order) => boom(audio, order * CANNON_STAGGER));
  if (audio.state === 'running') fire();
  // shortcut: a browser may block sound until the page is touched; then the shots wait for the first tap.
  else document.addEventListener('pointerdown', () => audio.resume().then(fire), { once: true });
}
