/**
 * Mobile mode utility
 * Manages forced mobile/desktop mode preference and viewport detection
 */

const STORAGE_KEY = "forceMobileMode";

/**
 * Check if mobile mode should be active
 * Priority: forced mode > viewport width
 * @returns {boolean}
 */
export function isMobileMode() {
  const forced = localStorage.getItem(STORAGE_KEY);
  if (forced !== null) {
    return forced === "true";
  }

  return window.innerWidth <= 768;
}

/**
 * Set forced mobile mode
 * @param {boolean} enabled - true for mobile, false for desktop
 */
export function setMobileMode(enabled) {
  if (enabled) {
    localStorage.setItem(STORAGE_KEY, "true");
  } else {
    localStorage.setItem(STORAGE_KEY, "false");
  }

  updateBodyClass();

  // Dispatch event for components to react
  window.dispatchEvent(
    new CustomEvent("mobile-mode-changed", {
      detail: { mobileMode: enabled },
    }),
  );
}

/**
 * Clear forced mode (use viewport detection)
 */
export function clearForcedMode() {
  localStorage.removeItem(STORAGE_KEY);
  updateBodyClass();

  // Dispatch event
  const mobileMode = window.innerWidth <= 768;
  window.dispatchEvent(
    new CustomEvent("mobile-mode-changed", {
      detail: { mobileMode },
    }),
  );
}

/**
 * Check if mode is forced (not using viewport detection)
 * @returns {boolean}
 */
export function isModeForced() {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

/**
 * Update body class based on current mobile mode state
 */
export function updateBodyClass() {
  const mobile = isMobileMode();
  if (mobile) {
    document.body.classList.add("mobile-mode");
    document.body.classList.remove("desktop-mode");
  } else {
    document.body.classList.add("desktop-mode");
    document.body.classList.remove("mobile-mode");
  }
}

/**
 * Initialize mobile mode on page load
 */
export function initMobileMode() {
  updateBodyClass();

  // Listen for window resize if mode is not forced
  let resizeTimeout;
  window.addEventListener("resize", () => {
    if (!isModeForced()) {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        updateBodyClass();
        const mobileMode = isMobileMode();
        window.dispatchEvent(
          new CustomEvent("mobile-mode-changed", {
            detail: { mobileMode },
          }),
        );
      }, 150);
    }
  });
}
