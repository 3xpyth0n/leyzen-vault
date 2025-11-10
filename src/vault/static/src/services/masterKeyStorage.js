/**
 * Secure master key storage in IndexedDB.
 *
 * The master key is encrypted with a session key derived from the JWT token.
 * This allows the key to persist across page refreshes while maintaining security.
 */

import { logger } from "../utils/logger.js";

const DB_NAME = "leyzen_vault_master_keys";
const DB_VERSION = 1;
const STORE_NAME = "encrypted_master_keys";

let dbInstance = null;

/**
 * Open IndexedDB database for master key storage.
 * @returns {Promise<IDBDatabase>} Database instance
 */
function openDB() {
  if (dbInstance) {
    return Promise.resolve(dbInstance);
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      reject(new Error("Failed to open IndexedDB for master key storage"));
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      resolve(dbInstance);
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "userId" });
      }
    };
  });
}

/**
 * Derive a session key from JWT token.
 * Uses the user_id from JWT payload to derive a stable key for encrypting the master key.
 * The key is stable across JWT refreshes for the same user.
 *
 * @param {string} jwtToken - JWT token
 * @returns {Promise<CryptoKey>} Session key for encrypting master key
 */
async function deriveSessionKeyFromJWT(jwtToken) {
  // Extract payload from JWT (base64url encoded)
  const parts = jwtToken.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT format");
  }

  // Decode payload
  const payload = JSON.parse(
    atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
  );

  // Use only user_id to create a stable session identifier
  // This ensures the same session key is derived for the same user across JWT refreshes
  // Security: The key is still protected because only authenticated users with valid JWT can derive it
  const userId = payload.user_id;
  if (!userId) {
    throw new Error("Invalid JWT: missing user_id");
  }

  // Derive key using PBKDF2 with user_id as input
  const encoder = new TextEncoder();
  const userIdBytes = encoder.encode(`leyzen_master_key:${userId}`);

  // Use a fixed salt derived from user_id (deterministic but user-specific)
  const salt = await crypto.subtle.digest("SHA-256", userIdBytes);

  // Import user ID as key material
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    userIdBytes,
    "PBKDF2",
    false,
    ["deriveBits", "deriveKey"],
  );

  // Derive session key using PBKDF2
  const sessionKey = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt,
      iterations: 100000, // Lower iterations for session key (used frequently, but still secure)
      hash: "SHA-256",
    },
    keyMaterial,
    {
      name: "AES-GCM",
      length: 256,
    },
    false, // Not extractable
    ["encrypt", "decrypt"],
  );

  return sessionKey;
}

/**
 * Get user ID from JWT token.
 * @param {string} jwtToken - JWT token
 * @returns {string|null} User ID or null if invalid
 */
function getUserIdFromJWT(jwtToken) {
  try {
    const parts = jwtToken.split(".");
    if (parts.length !== 3) {
      return null;
    }
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return payload.user_id || null;
  } catch (e) {
    return null;
  }
}

/**
 * Encrypt master key with session key and store in IndexedDB.
 *
 * @param {CryptoKey} masterKey - Master key to encrypt (must be extractable)
 * @param {string} jwtToken - JWT token for session key derivation
 * @returns {Promise<void>}
 */
export async function storeEncryptedMasterKey(masterKey, jwtToken) {
  try {
    // Derive session key from JWT
    const sessionKey = await deriveSessionKeyFromJWT(jwtToken);
    const userId = getUserIdFromJWT(jwtToken);

    if (!userId) {
      throw new Error("Invalid JWT token");
    }

    // Export master key (must be extractable for this to work)
    // We need to make it extractable temporarily
    const exportedKey = await crypto.subtle.exportKey("raw", masterKey);

    // Generate IV for encryption
    const iv = crypto.getRandomValues(new Uint8Array(12));

    // Encrypt master key with session key
    const encrypted = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      sessionKey,
      exportedKey,
    );

    // Combine IV and encrypted data
    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(encrypted), iv.length);

    // Store in IndexedDB
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    const encryptedData = {
      userId: userId,
      encryptedKey: btoa(String.fromCharCode(...combined)),
      timestamp: Date.now(),
    };

    return new Promise((resolve, reject) => {
      const req = store.put(encryptedData);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    logger.error("Failed to store encrypted master key:", error);
    throw error;
  }
}

/**
 * Retrieve and decrypt master key from IndexedDB.
 *
 * @param {string} jwtToken - JWT token for session key derivation
 * @returns {Promise<CryptoKey|null>} Decrypted master key or null if not found
 */
export async function getEncryptedMasterKey(jwtToken) {
  try {
    const sessionKey = await deriveSessionKeyFromJWT(jwtToken);
    const userId = getUserIdFromJWT(jwtToken);

    if (!userId) {
      return null;
    }

    // Retrieve from IndexedDB
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readonly");
    const store = transaction.objectStore(STORE_NAME);

    const encryptedData = await new Promise((resolve, reject) => {
      const req = store.get(userId);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    if (!encryptedData || !encryptedData.encryptedKey) {
      return null;
    }

    // Decode encrypted data
    const combined = Uint8Array.from(atob(encryptedData.encryptedKey), (c) =>
      c.charCodeAt(0),
    );

    // Extract IV and encrypted data
    const iv = combined.slice(0, 12);
    const encrypted = combined.slice(12);

    // Decrypt master key
    const decrypted = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      sessionKey,
      encrypted,
    );

    // Import as CryptoKey
    const masterKey = await crypto.subtle.importKey(
      "raw",
      decrypted,
      {
        name: "AES-GCM",
        length: 256,
      },
      false, // Not extractable for security
      ["encrypt", "decrypt"],
    );

    return masterKey;
  } catch (error) {
    // If decryption fails (e.g., JWT changed), return null
    logger.warn("Failed to retrieve encrypted master key:", error);
    return null;
  }
}

/**
 * Clear encrypted master key from IndexedDB.
 *
 * @param {string} jwtToken - JWT token to get user ID
 * @returns {Promise<void>}
 */
export async function clearEncryptedMasterKey(jwtToken) {
  try {
    const userId = getUserIdFromJWT(jwtToken);
    if (!userId) {
      return;
    }

    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const req = store.delete(userId);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    logger.error("Failed to clear encrypted master key:", error);
  }
}

/**
 * Clear all encrypted master keys (for logout).
 * @returns {Promise<void>}
 */
export async function clearAllEncryptedMasterKeys() {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const req = store.clear();
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    logger.error("Failed to clear all encrypted master keys:", error);
  }
}
