const CACHE_NAME = 'pc-remote-v1';
const ASSETS = [
  '/',
  '/static/icon.png',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (event) => {
  // We want real-time socket communication, so we mostly bypass cache for logic
  // but cache the UI assets for faster loading.
  if (event.request.url.includes('/socket.io/')) {
    return; // Don't cache socket.io
  }
  
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
