// Saves settings, the roster and the game in this browser (localStorage).
// shortcut: data lives on this device only; use a cloud backup if you ever host from several devices.

export const KEYS = {
  language: 'yg-lang',
  roster: 'yg-roster',
  game: 'yg-game-v2', // v2: the multi-file version; older saves are ignored
};

/** Returns the saved value, or null if there is none or storage is blocked. */
export function load(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

/** Saves a value; null removes it. Returns false if the browser refused (full or blocked). */
export function save(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
