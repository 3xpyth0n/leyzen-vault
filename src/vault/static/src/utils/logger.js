/**
 * Conditional logger utility for client-side code.
 *
 * Only logs in development mode to prevent sensitive information
 * from being exposed in production browser consoles.
 *
 * Usage:
 *   import { logger } from '@/utils/logger';
 *   logger.log('Debug message');
 *   logger.error('Error message');
 *   logger.warn('Warning message');
 */

// Check if we're in development mode
// Vite sets import.meta.env.MODE to 'development' in dev mode
const isDev = import.meta.env.MODE === "development";

/**
 * Logger object that conditionally logs based on environment.
 * In production, all logging is suppressed to prevent information leakage.
 */
export const logger = {
  /**
   * Log a message (only in development).
   * @param {...any} args - Arguments to log
   */
  log: (...args) => {
    if (isDev) {
      console.log(...args);
    }
  },

  /**
   * Log an error (only in development).
   * @param {...any} args - Arguments to log
   */
  error: (...args) => {
    if (isDev) {
      console.error(...args);
    }
  },

  /**
   * Log a warning (only in development).
   * @param {...any} args - Arguments to log
   */
  warn: (...args) => {
    if (isDev) {
      console.warn(...args);
    }
  },

  /**
   * Log information (only in development).
   * @param {...any} args - Arguments to log
   */
  info: (...args) => {
    if (isDev) {
      console.info(...args);
    }
  },

  /**
   * Log debug information (only in development).
   * @param {...any} args - Arguments to log
   */
  debug: (...args) => {
    if (isDev) {
      console.debug(...args);
    }
  },
};
