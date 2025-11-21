/** @file service-worker.js - Service Worker DISABLED - No caching
 *
 * Service worker is disabled to prevent cache issues, especially with CSS files
 * that change frequently. All requests pass through to the server directly.
 */

// Service worker is effectively disabled - it doesn't intercept or cache anything
// This prevents cache-related 503 errors and ensures fresh files are always served

self.addEventListener("fetch", (event) => {
  // Don't intercept any requests - let them pass through to the server
  // This ensures no cache issues, especially with CSS files that change often
  return;
});

// Clean up any existing caches when service worker activates
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      // Delete ALL caches to ensure clean state
      return Promise.all(cacheNames.map((name) => caches.delete(name)));
    }),
  );
  return self.clients.claim();
});

// Message handler for cache clearing (if needed)
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "CACHE_CLEAR") {
    caches.keys().then((cacheNames) => {
      return Promise.all(cacheNames.map((name) => caches.delete(name)));
    });
  }
});
