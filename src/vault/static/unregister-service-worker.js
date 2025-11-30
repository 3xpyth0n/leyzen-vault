/** @file unregister-service-worker.js - Unregister service workers and clear caches
 *
 * Service worker is disabled to prevent cache issues with CSS/JS files.
 * This script unregisters any existing service workers and clears all caches.
 */

(function () {
  if ("serviceWorker" in navigator) {
    // Unregister any existing service workers and clear all caches
    // This runs immediately to clear any stale service workers before page load
    (function () {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        for (let registration of registrations) {
          registration.unregister().then((success) => {
            if (success) {
              // Clear all caches after unregistering
              if ("caches" in window) {
                caches.keys().then((cacheNames) => {
                  cacheNames.forEach((cacheName) => {
                    caches.delete(cacheName);
                  });
                });
              }
            }
          });
        }
      });
    })();

    // Also run on load as a fallback
    window.addEventListener("load", () => {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        for (let registration of registrations) {
          registration.unregister().then((success) => {
            if (success) {
              // Clear all caches after unregistering
              if ("caches" in window) {
                caches.keys().then((cacheNames) => {
                  cacheNames.forEach((cacheName) => {
                    caches.delete(cacheName);
                  });
                });
              }
            }
          });
        }
      });
    });
  }
})();
