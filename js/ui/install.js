// The "Install app" button: works on Android/Chrome/Edge; on iPhone it shows how to add it by hand.

let installPrompt = null; // the browser's install offer, kept until the button is tapped
let onChange = () => {};

const isInstalled = () =>
  window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

const isIphoneOrIpad = () => /iphone|ipad|ipod/i.test(navigator.userAgent);

/** Registers the service worker (needed to install) and listens for the install offer. */
export function setupInstall(whenAvailabilityChanges) {
  onChange = whenAvailabilityChanges;

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {}); // the app still works without it
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    onChange();
  });

  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    onChange();
  });
}

/** 'prompt' (one-tap install), 'ios' (show instructions), or null (hide the button). */
export function installMode() {
  if (isInstalled()) return null;
  if (installPrompt) return 'prompt';
  if (isIphoneOrIpad()) return 'ios';
  return null;
}

/** Opens the browser's install dialog. */
export async function promptInstall() {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  onChange();
}
