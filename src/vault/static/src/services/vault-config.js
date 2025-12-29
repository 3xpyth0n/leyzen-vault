/**
 * Vault configuration service for frontend.
 * Provides access to vault configuration values like VAULT_URL.
 */

let cachedVaultUrl = null;
let configPromise = null;

/**
 * Get the vault base URL for display purposes.
 * Uses VAULT_URL from server config if available, otherwise falls back to window.location.origin.
 *
 * @returns {Promise<string>} The base URL (e.g., "https://vault.leyzen.com" or "http://localhost:5000")
 */
export async function getVaultBaseUrl() {
  if (cachedVaultUrl !== null) {
    return cachedVaultUrl;
  }

  if (configPromise) {
    return configPromise;
  }

  // Start fetching config
  configPromise = (async () => {
    try {
      const response = await fetch("/api/v2/config", {
        method: "GET",
        credentials: "same-origin",
      });

      if (response.ok) {
        const data = await response.json();
        const vaultUrl = data.vault_url;

        // Use VAULT_URL if configured, otherwise fallback to window.location.origin
        if (
          vaultUrl &&
          typeof vaultUrl === "string" &&
          vaultUrl.trim() !== ""
        ) {
          cachedVaultUrl = vaultUrl.trim().replace(/\/$/, ""); // Remove trailing slash
          return cachedVaultUrl;
        }
      }
    } catch (error) {}

    cachedVaultUrl = window.location.origin;
    return cachedVaultUrl;
  })();

  return configPromise;
}

/**
 * Get the vault base URL synchronously if already cached.
 * Returns null if not yet cached (use getVaultBaseUrl() instead).
 *
 * @returns {string|null} The cached base URL or null
 */
export function getVaultBaseUrlSync() {
  return cachedVaultUrl;
}

/**
 * Clear the cached vault URL (useful for testing or when config changes).
 */
export function clearVaultUrlCache() {
  cachedVaultUrl = null;
  configPromise = null;
}
