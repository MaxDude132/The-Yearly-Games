// Service worker: lets the app be installed and open without internet.
// Strategy: try the network first (so updates show up right away), fall back to the saved copy.

const CACHE = 'yearly-games';

const APP_FILES = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/style.css',
  'icons/icon.svg',
  'icons/icon-192.png',
  'js/ui/app.js',
  'js/ui/views.js',
  'js/ui/install.js',
  'js/ui/photos.js',
  'js/ui/storage.js',
  'js/engine/state.js',
  'js/engine/text.js',
  'js/engine/combat.js',
  'js/engine/events.js',
  'js/engine/encounters.js',
  'js/engine/rounds.js',
  'js/data/items.js',
  'js/data/arena-events.js',
  'js/data/story.js',
  'js/data/ui-text.js',
  'js/utils/random.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_FILES)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok || response.type === 'opaque') {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request)),
  );
});
