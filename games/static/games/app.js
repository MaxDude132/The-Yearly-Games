// Small touches on top of the server-rendered pages: press feedback, scrolling the story,
// the phone story/board switch, the "here" ticks and photo upload. All game logic is on the server.
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
