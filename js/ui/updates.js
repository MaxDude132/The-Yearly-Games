// Shows an "Update" button when a newer version of the app is on GitHub.
// How it works: version.json holds a number. The app remembers the number it started with,
// checks again every few minutes and whenever you come back to the app,
// and if the number changed, a new version is out.
// To publish an update: change the code, add 1 to the number in version.json, push.

const CHECK_EVERY = 5 * 60 * 1000; // 5 minutes

let runningVersion = null;
let onUpdateFound = () => {};

async function fetchLatestVersion() {
  try {
    const response = await fetch(`version.json?t=${Date.now()}`, { cache: 'no-store' });
    return (await response.json()).version;
  } catch {
    return null; // offline: try again later
  }
}

async function check() {
  const latest = await fetchLatestVersion();
  if (latest == null) return;
  if (runningVersion == null) runningVersion = latest;
  else if (latest !== runningVersion) onUpdateFound();
}

/** Starts checking. whenFound runs once a newer version exists. */
export function watchForUpdates(whenFound) {
  onUpdateFound = whenFound;
  check();
  setInterval(check, CHECK_EVERY);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check();
  });
}

/** Reloads the app on the new version (the service worker fetches every file fresh). */
export function applyUpdate() {
  window.location.reload();
}
