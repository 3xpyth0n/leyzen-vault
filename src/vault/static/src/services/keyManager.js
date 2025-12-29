/**
 * Key management service for client-side encryption.
 *
 * Manages user master key derivation and secure storage.
 * The master key is encrypted with a session key derived from JWT and stored in IndexedDB.
 * This allows the key to persist across page refreshes while maintaining security.
 * The salt is stored in sessionStorage to allow key re-derivation with password if needed.
 */

import {
  deriveUserKey,
  generateSalt,
  generateVaultSpaceKey,
  encryptVaultSpaceKey,
  decryptVaultSpaceKey,
} from "./encryption";
import {
  storeEncryptedMasterKey,
  getEncryptedMasterKey,
  clearEncryptedMasterKey,
  clearAllEncryptedMasterKeys,
} from "./masterKeyStorage";
import { logger } from "../utils/logger.js";

const MASTER_KEY_STORAGE_KEY = "user_master_key_salt";
const VAULTSPACE_KEYS_CACHE_KEY = "vaultspace_keys_cache";

/**
 * Derive and cache user master key from password.
 * Stores the key encrypted in IndexedDB for persistence across page refreshes.
 *
 * @param {string} password - User password
 * @param {Uint8Array} salt - Salt for key derivation (if not provided, generates new)
 * @param {string} jwtToken - JWT token for session key derivation (optional, will try to get from localStorage)
 * @returns {Promise<CryptoKey>} User master key
 */
export async function initializeUserMasterKey(
  password,
  salt = null,
  jwtToken = null,
) {
  // Generate salt if not provided
  if (!salt) {
    salt = generateSalt(16);
  }

  // Always store salt in sessionStorage for this session
  const saltBase64 = btoa(String.fromCharCode(...salt));
  sessionStorage.setItem(MASTER_KEY_STORAGE_KEY, saltBase64);

  // Derive master key from password (extractable=true temporarily to store encrypted version)

  const masterKey = await deriveUserKey(password, salt, true);

  // Get JWT token if not provided
  if (!jwtToken) {
    jwtToken = localStorage.getItem("jwt_token");
  }

  // Store encrypted master key in IndexedDB if JWT is available
  if (jwtToken) {
    try {
      await storeEncryptedMasterKey(masterKey, jwtToken);
    } catch (error) {
      logger.warn("Failed to store encrypted master key in IndexedDB:", error);
      // Continue even if storage fails - key is still in memory
    }
  }

  // Store in memory Map for quick access
  if (!window.__leyzenMasterKey) {
    window.__leyzenMasterKey = new Map();
  }

  // Use a unique session ID as the key
  const sessionId = Date.now().toString();
  window.__leyzenMasterKey.set(sessionId, masterKey);
  window.__leyzenMasterKeyRef = sessionId;

  // Make key non-extractable after storing (security)

  // for now. The encrypted version in IndexedDB is protected by the session key.

  return masterKey;
}

/**
 * Get cached user master key.
 * Tries to retrieve from memory first, then from IndexedDB (encrypted).
 * Returns null if key cannot be retrieved (user must re-enter password).
 *
 * @returns {Promise<CryptoKey|null>} User master key or null if not available
 */
export async function getUserMasterKey() {
  if (window.__leyzenMasterKey && window.__leyzenMasterKeyRef) {
    const key = window.__leyzenMasterKey.get(window.__leyzenMasterKeyRef);
    if (key) {
      return key;
    }
  }

  // Key not in memory - try to retrieve from IndexedDB
  const jwtToken = localStorage.getItem("jwt_token");
  if (jwtToken) {
    try {
      const encryptedKey = await getEncryptedMasterKey(jwtToken);
      if (encryptedKey) {
        // Store in memory for future access
        if (!window.__leyzenMasterKey) {
          window.__leyzenMasterKey = new Map();
        }
        const sessionId = Date.now().toString();
        window.__leyzenMasterKey.set(sessionId, encryptedKey);
        window.__leyzenMasterKeyRef = sessionId;
        return encryptedKey;
      }
    } catch (error) {
      // Force clear all encrypted keys to force re-authentication with new secure system
      logger.warn(
        "Failed to retrieve encrypted master key from IndexedDB (may be old format):",
        error,
      );
      try {
        await clearAllEncryptedMasterKeys();
        logger.info(
          "Cleared all encrypted master keys due to decryption failure (migration to new secure format)",
        );
      } catch (clearError) {
        logger.error("Failed to clear encrypted master keys:", clearError);
      }
    }
  }

  // Key not available - user must re-enter password
  return null;
}

/**
 * Restore user master key from password and stored salt.
 * This should be called when the key is lost but salt exists in sessionStorage.
 *
 * @param {string} password - User password
 * @returns {Promise<CryptoKey|null>} User master key or null if salt not found
 */
export async function restoreUserMasterKey(password) {
  const salt = getStoredSalt();
  if (!salt) {
    return null;
  }

  return await initializeUserMasterKey(password, salt);
}

/**
 * Get salt from sessionStorage.
 *
 * @returns {Uint8Array|null} Salt or null if not found
 */
export function getStoredSalt() {
  const saltBase64 = sessionStorage.getItem(MASTER_KEY_STORAGE_KEY);
  if (!saltBase64) {
    return null;
  }

  try {
    const saltStr = atob(saltBase64);
    return Uint8Array.from(saltStr, (c) => c.charCodeAt(0));
  } catch (e) {
    return null;
  }
}

/**
 * Clear user master key from memory, sessionStorage, and IndexedDB.
 */
export async function clearUserMasterKey() {
  if (window.__leyzenMasterKey && window.__leyzenMasterKeyRef) {
    window.__leyzenMasterKey.delete(window.__leyzenMasterKeyRef);
    window.__leyzenMasterKeyRef = null;
  }
  // Also clear the entire Map if it exists
  if (window.__leyzenMasterKey) {
    window.__leyzenMasterKey.clear();
    window.__leyzenMasterKey = null;
  }
  sessionStorage.removeItem(MASTER_KEY_STORAGE_KEY);
  sessionStorage.removeItem(VAULTSPACE_KEYS_CACHE_KEY);

  // Clear encrypted master key from IndexedDB
  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (jwtToken) {
      await clearEncryptedMasterKey(jwtToken);
    } else {
      await clearAllEncryptedMasterKeys();
    }
  } catch (error) {
    logger.warn("Failed to clear encrypted master key from IndexedDB:", error);
  }
}

/**
 * Create and encrypt VaultSpace key for a new VaultSpace.
 *
 * @param {CryptoKey} userMasterKey - User master key
 * @returns {Promise<{vaultspaceKey: CryptoKey, encryptedKey: string}>} VaultSpace key and encrypted key
 */
export async function createVaultSpaceKey(userMasterKey) {
  // Generate VaultSpace key
  const vaultspaceKey = await generateVaultSpaceKey();

  // Encrypt with user master key
  const encryptedKey = await encryptVaultSpaceKey(userMasterKey, vaultspaceKey);

  return {
    vaultspaceKey,
    encryptedKey,
  };
}

/**
 * Decrypt VaultSpace key from server.
 *
 * @param {CryptoKey} userMasterKey - User master key
 * @param {string} encryptedKey - Encrypted VaultSpace key from server
 * @param {boolean} extractable - Whether the key should be extractable (default: false for security)
 * @returns {Promise<CryptoKey>} Decrypted VaultSpace key
 */
export async function decryptVaultSpaceKeyForUser(
  userMasterKey,
  encryptedKey,
  extractable = false,
) {
  return await decryptVaultSpaceKey(userMasterKey, encryptedKey, extractable);
}

/**
 * Cache decrypted VaultSpace key in memory.
 *
 * @param {string} vaultspaceId - VaultSpace ID
 * @param {CryptoKey} vaultspaceKey - Decrypted VaultSpace key
 */
export function cacheVaultSpaceKey(vaultspaceId, vaultspaceKey) {
  if (!window.__leyzenVaultSpaceKeys) {
    window.__leyzenVaultSpaceKeys = new Map();
  }
  window.__leyzenVaultSpaceKeys.set(vaultspaceId, vaultspaceKey);
}

/**
 * Get cached VaultSpace key.
 *
 * @param {string} vaultspaceId - VaultSpace ID
 * @returns {CryptoKey|null} Cached VaultSpace key or null
 */
export function getCachedVaultSpaceKey(vaultspaceId) {
  if (!window.__leyzenVaultSpaceKeys) {
    return null;
  }
  return window.__leyzenVaultSpaceKeys.get(vaultspaceId) || null;
}

/**
 * Clear cached VaultSpace key.
 *
 * @param {string} vaultspaceId - VaultSpace ID
 */
export function clearCachedVaultSpaceKey(vaultspaceId) {
  if (window.__leyzenVaultSpaceKeys) {
    window.__leyzenVaultSpaceKeys.delete(vaultspaceId);
  }
}

/**
 * Clear all cached VaultSpace keys.
 */
export function clearAllCachedVaultSpaceKeys() {
  if (window.__leyzenVaultSpaceKeys) {
    window.__leyzenVaultSpaceKeys.clear();
  }
}

/**
 * Re-encrypt a VaultSpace key with a new master key.
 * Decrypts the key with the old master key and encrypts it with the new one.
 *
 * @param {CryptoKey} oldMasterKey - Old master key for decryption
 * @param {CryptoKey} newMasterKey - New master key for encryption
 * @param {string} encryptedKey - Encrypted VaultSpace key (base64)
 * @returns {Promise<string>} New encrypted VaultSpace key (base64)
 */
export async function reencryptVaultSpaceKey(
  oldMasterKey,
  newMasterKey,
  encryptedKey,
) {
  // Decrypt with old master key
  const decryptedKey = await decryptVaultSpaceKey(oldMasterKey, encryptedKey);

  // Re-encrypt with new master key
  const newEncryptedKey = await encryptVaultSpaceKey(
    newMasterKey,
    decryptedKey,
  );

  return newEncryptedKey;
}
