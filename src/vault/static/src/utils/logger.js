/**
 * Conditional logger utility for client-side code.
 *
 * Only logs in development mode to prevent sensitive information
 * from being exposed in production browser consoles.
 *
 * This logger respects the backend's LEYZEN_ENVIRONMENT setting by fetching
 * is_production from the /api/v2/config endpoint. If the config is not yet
 * loaded, it falls back to Vite's import.meta.env.MODE for immediate logging.
 *
 * Usage:
 *   import { logger } from '@/utils/logger';
 *   logger.log('Debug message');
 *   logger.error('Error message');
 *   logger.warn('Warning message');
 */

// Cached production mode state from backend
let isProductionBackend = null;
let configLoadPromise = null;

/**
 * Load production mode from backend config API.
 * This ensures frontend logging respects backend LEYZEN_ENVIRONMENT setting.
 */
async function loadProductionMode() {
  // Return cached value if available
  if (isProductionBackend !== null) {
    return isProductionBackend;
  }

  // If a request is already in progress, return the same promise
  if (configLoadPromise) {
    await configLoadPromise;
    return isProductionBackend;
  }

  // Start fetching config
  configLoadPromise = (async () => {
    try {
      const response = await fetch("/api/v2/config", {
        method: "GET",
        credentials: "same-origin",
      });

      if (response.ok) {
        const data = await response.json();
        // Backend returns is_production (true = production, false = development)
        isProductionBackend = data.is_production === true;
      } else {
        // On error, default to production mode (secure)
        isProductionBackend = true;
      }
    } catch (error) {
      // On error, default to production mode (secure)
      isProductionBackend = true;
    }
    return isProductionBackend;
  })();

  return await configLoadPromise;
}

// Initialize on module load (non-blocking)
loadProductionMode().catch(() => {
  // Silently handle errors, will use fallback
});

/**
 * Check if we're in development mode.
 * Uses backend is_production state if available, otherwise falls back to Vite's MODE.
 */
function isDevelopmentMode() {
  // If backend config is loaded, use it
  if (isProductionBackend !== null) {
    return !isProductionBackend; // is_production=true means NOT development
  }

  // Fallback to Vite's build-time mode (for immediate logging before config loads)
  return import.meta.env.MODE === "development";
}

/**
 * Logger object that conditionally logs based on environment.
 * In production, all logging is suppressed to prevent information leakage.
 * This respects the backend's LEYZEN_ENVIRONMENT setting.
 */
export const logger = {
  /**
   * Log a message (only in development mode according to backend config).
   * @param {...any} args - Arguments to log
   */
  log: (...args) => {
    if (isDevelopmentMode()) {
      console.log(...args);
    }
  },

  /**
   * Log an error (only in development mode according to backend config).
   * @param {...any} args - Arguments to log
   */
  error: (...args) => {
    if (isDevelopmentMode()) {
      console.error(...args);
    }
  },

  /**
   * Log a warning (only in development mode according to backend config).
   * @param {...any} args - Arguments to log
   */
  warn: (...args) => {
    if (isDevelopmentMode()) {
      console.warn(...args);
    }
  },

  /**
   * Log information (only in development mode according to backend config).
   * @param {...any} args - Arguments to log
   */
  info: (...args) => {
    if (isDevelopmentMode()) {
      console.info(...args);
    }
  },

  /**
   * Log debug information (only in development mode according to backend config).
   * @param {...any} args - Arguments to log
   */
  debug: (...args) => {
    if (isDevelopmentMode()) {
      console.debug(...args);
    }
  },
};

// Export for testing or advanced usage
export { loadProductionMode, isDevelopmentMode };
