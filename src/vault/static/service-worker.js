/** @file service-worker.js - Service Worker for offline caching and performance */

// Updated cache version to force cache refresh
const CACHE_NAME = "leyzen-vault-v2";
const STATIC_CACHE_NAME = "leyzen-vault-static-v2";
const DYNAMIC_CACHE_NAME = "leyzen-vault-dynamic-v2";

// Assets to cache immediately
const STATIC_ASSETS = [
  "/static/vault.css",
  "/static/vault.js",
  "/static/theme-toggle.js",
  "/static/animations.js",
  "/static/notifications.js",
  "/static/user-menu.js",
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }),
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return (
              name !== STATIC_CACHE_NAME &&
              name !== DYNAMIC_CACHE_NAME &&
              name !== CACHE_NAME
            );
          })
          .map((name) => caches.delete(name)),
      );
    }),
  );
  return self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") {
    return;
  }

  // Skip API requests (they should always be fresh)
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // Skip authentication endpoints
  if (url.pathname.startsWith("/login") || url.pathname.startsWith("/logout")) {
    return;
  }

  // IMPORTANT: Bypass cache for Vue.js build files (assets/*.js) to ensure fresh code
  // This prevents serving stale JavaScript after rebuilds
  if (
    url.pathname.startsWith("/static/assets/") &&
    url.pathname.endsWith(".js")
  ) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Still cache it for offline use, but always fetch fresh first
          if (response.ok) {
            const responseToCache = response.clone();
            caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // Fallback to cache only if network fails completely
          return caches.match(request);
        }),
    );
    return;
  }

  // Strategy: Cache first, then network (for other files)
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Return cached version, but also fetch fresh in background
        event.waitUntil(
          fetch(request).then((response) => {
            if (response.ok) {
              caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
                cache.put(request, response.clone());
              });
            }
          }),
        );
        return cachedResponse;
      }

      // Not in cache, fetch from network
      return fetch(request)
        .then((response) => {
          // Don't cache non-successful responses
          if (
            !response ||
            response.status !== 200 ||
            response.type !== "basic"
          ) {
            return response;
          }

          // Clone response for cache
          const responseToCache = response.clone();

          caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });

          return response;
        })
        .catch(() => {
          // Network failed, return offline page if available
          if (request.headers.get("accept").includes("text/html")) {
            return caches.match("/offline.html");
          }
        });
    }),
  );
});

// Message handler for cache updates
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }

  if (event.data && event.data.type === "CACHE_CLEAR") {
    caches.keys().then((cacheNames) => {
      return Promise.all(cacheNames.map((name) => caches.delete(name)));
    });
  }
});
