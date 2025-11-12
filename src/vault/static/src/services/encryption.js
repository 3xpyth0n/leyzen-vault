/**
 * Client-side encryption service using Web Crypto API.
 *
 * This service handles the complete encryption chain:
 * - User master key derivation (Argon2)
 * - VaultSpace key generation and encryption
 * - File key generation and encryption
 * - File encryption/decryption
 *
 * IMPORTANT: All encryption/decryption happens client-side.
 * The server never sees plaintext keys or file contents.
 */

import { logger } from "../utils/logger.js";

/**
 * Derive user master key from password using Argon2.
 * Falls back to PBKDF2 if Argon2 is not available.
 *
 * @param {string} password - User password
 * @param {Uint8Array} salt - Salt bytes
 * @param {boolean} extractable - Whether the key should be extractable (default: false for security)
 * @returns {Promise<CryptoKey>} User master key
 */
export async function deriveUserKey(password, salt, extractable = false) {
  // NOTE: Argon2 implementation is not feasible with Vite/Vue as WebAssembly
  // modules cannot be properly bundled by Rollup. While Argon2 would provide
  // better security against GPU-based attacks, PBKDF2 with 600,000 iterations
  // remains secure for our use case and is fully supported by the Web Crypto API.

  // Use PBKDF2 (current implementation)
  const encoder = new TextEncoder();
  const passwordData = encoder.encode(password);

  // Import password as key material
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    passwordData,
    "PBKDF2",
    false,
    ["deriveBits", "deriveKey"],
  );

  // Derive key using PBKDF2 (600,000 iterations)
  const masterKey = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt,
      iterations: 600000,
      hash: "SHA-256",
    },
    keyMaterial,
    {
      name: "AES-GCM",
      length: 256,
    },
    extractable, // Extractable flag (default: false for security)
    ["encrypt", "decrypt"],
  );

  return masterKey;
}

/**
 * Generate a random VaultSpace key.
 *
 * @returns {Promise<CryptoKey>} VaultSpace key
 */
export async function generateVaultSpaceKey() {
  return await crypto.subtle.generateKey(
    {
      name: "AES-GCM",
      length: 256,
    },
    true, // Extractable for encryption
    ["encrypt", "decrypt"],
  );
}

/**
 * Encrypt VaultSpace key with user master key.
 *
 * @param {CryptoKey} userKey - User master key
 * @param {CryptoKey} vaultspaceKey - VaultSpace key to encrypt
 * @returns {Promise<string>} Encrypted VaultSpace key (base64)
 */
export async function encryptVaultSpaceKey(userKey, vaultspaceKey) {
  // Export VaultSpace key to raw bytes
  const rawKey = await crypto.subtle.exportKey("raw", vaultspaceKey);

  // Generate IV
  const iv = crypto.getRandomValues(new Uint8Array(12));

  // Encrypt with user key
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    userKey,
    rawKey,
  );

  // Combine IV and encrypted data
  const combined = new Uint8Array(iv.length + encrypted.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(encrypted), iv.length);

  // Return as base64
  return btoa(String.fromCharCode(...combined));
}

/**
 * Decrypt VaultSpace key with user master key.
 *
 * @param {CryptoKey} userKey - User master key
 * @param {string} encryptedKey - Encrypted VaultSpace key (base64)
 * @param {boolean} extractable - Whether the key should be extractable (default: false for security)
 * @returns {Promise<CryptoKey>} Decrypted VaultSpace key
 */
export async function decryptVaultSpaceKey(
  userKey,
  encryptedKey,
  extractable = false,
) {
  // Decode base64
  const combined = Uint8Array.from(atob(encryptedKey), (c) => c.charCodeAt(0));

  // Extract IV and encrypted data
  const iv = combined.slice(0, 12);
  const encrypted = combined.slice(12);

  // Decrypt
  const decrypted = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    userKey,
    encrypted,
  );

  // Import as key
  return await crypto.subtle.importKey(
    "raw",
    decrypted,
    {
      name: "AES-GCM",
      length: 256,
    },
    extractable,
    ["encrypt", "decrypt"],
  );
}

/**
 * Generate a random file key.
 *
 * @returns {Promise<CryptoKey>} File key
 */
export async function generateFileKey() {
  return await crypto.subtle.generateKey(
    {
      name: "AES-GCM",
      length: 256,
    },
    true, // Extractable for encryption
    ["encrypt", "decrypt"],
  );
}

/**
 * Encrypt file key with VaultSpace key.
 *
 * @param {CryptoKey} vaultspaceKey - VaultSpace key
 * @param {CryptoKey} fileKey - File key to encrypt
 * @returns {Promise<string>} Encrypted file key (base64)
 */
export async function encryptFileKey(vaultspaceKey, fileKey) {
  // Export file key to raw bytes
  const rawKey = await crypto.subtle.exportKey("raw", fileKey);

  // Generate IV
  const iv = crypto.getRandomValues(new Uint8Array(12));

  // Encrypt with VaultSpace key
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    vaultspaceKey,
    rawKey,
  );

  // Combine IV and encrypted data
  const combined = new Uint8Array(iv.length + encrypted.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(encrypted), iv.length);

  // Return as base64
  return btoa(String.fromCharCode(...combined));
}

/**
 * Decrypt file key with VaultSpace key.
 *
 * @param {CryptoKey} vaultspaceKey - VaultSpace key
 * @param {string} encryptedKey - Encrypted file key (base64)
 * @param {boolean} extractable - Whether the key should be extractable (default: false)
 * @returns {Promise<CryptoKey>} Decrypted file key
 */
export async function decryptFileKey(
  vaultspaceKey,
  encryptedKey,
  extractable = false,
) {
  // Decode base64
  const combined = Uint8Array.from(atob(encryptedKey), (c) => c.charCodeAt(0));

  // Extract IV and encrypted data
  const iv = combined.slice(0, 12);
  const encrypted = combined.slice(12);

  // Decrypt
  const decrypted = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    vaultspaceKey,
    encrypted,
  );

  // Import as key
  return await crypto.subtle.importKey(
    "raw",
    decrypted,
    {
      name: "AES-GCM",
      length: 256,
    },
    extractable,
    ["encrypt", "decrypt"],
  );
}

/**
 * Encrypt file data with file key.
 *
 * @param {CryptoKey} fileKey - File key
 * @param {ArrayBuffer|Uint8Array} fileData - File data to encrypt
 * @returns {Promise<{encrypted: ArrayBuffer, iv: Uint8Array}>} Encrypted data and IV
 */
export async function encryptFile(fileKey, fileData) {
  // Convert to ArrayBuffer if needed
  const data = fileData instanceof ArrayBuffer ? fileData : fileData.buffer;

  // Generate IV
  const iv = crypto.getRandomValues(new Uint8Array(12));

  // Encrypt
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    fileKey,
    data,
  );

  return {
    encrypted: encrypted,
    iv: iv,
  };
}

/**
 * Decrypt file data with file key.
 *
 * @param {CryptoKey} fileKey - File key
 * @param {ArrayBuffer} encryptedData - Encrypted file data
 * @param {Uint8Array} iv - Initialization vector
 * @returns {Promise<ArrayBuffer>} Decrypted file data
 */
export async function decryptFile(fileKey, encryptedData, iv) {
  return await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    fileKey,
    encryptedData,
  );
}

/**
 * Convert ArrayBuffer to base64 string.
 *
 * @param {ArrayBuffer} buffer - Buffer to convert
 * @returns {string} Base64 string
 */
export function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert base64 string to ArrayBuffer.
 *
 * @param {string} base64 - Base64 string
 * @returns {ArrayBuffer} ArrayBuffer
 */
export function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Generate random salt.
 *
 * @param {number} length - Salt length in bytes (default: 16)
 * @returns {Uint8Array} Random salt
 */
export function generateSalt(length = 16) {
  return crypto.getRandomValues(new Uint8Array(length));
}

/**
 * Convert Uint8Array to base64url string.
 *
 * @param {Uint8Array} array - The array to convert
 * @returns {string} Base64url string
 */
export function arrayToBase64url(array) {
  const base64 = btoa(String.fromCharCode(...array));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

/**
 * Convert base64url string to Uint8Array.
 *
 * @param {string} base64url - The base64url string
 * @returns {Uint8Array} Uint8Array
 */
export function base64urlToArray(base64url) {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const padding = base64.length % 4;
  const paddedBase64 = base64 + "=".repeat(padding ? 4 - padding : 0);
  const binaryString = atob(paddedBase64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

/**
 * Parse share URL to extract file ID and key from URL fragment.
 *
 * @returns {{fileId: string|null, key: Uint8Array|null}} Parsed file ID and key
 */
export function parseShareUrl() {
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  const fileId = params.get("file");
  const keyBase64url = params.get("key");

  if (!fileId || !keyBase64url) {
    return { fileId: null, key: null };
  }

  try {
    const key = base64urlToArray(keyBase64url);
    return { fileId, key };
  } catch (e) {
    logger.error("Failed to parse key from URL:", e);
    return { fileId: null, key: null };
  }
}

/**
 * Create a shareable URL with the encryption key in the fragment.
 *
 * @param {string} fileId - The file ID
 * @param {Uint8Array} key - The encryption key
 * @returns {string} Share URL
 */
export function createShareUrl(fileId, key) {
  const keyBase64url = arrayToBase64url(key);
  const baseUrl = window.location.origin;
  return `${baseUrl}/share/${fileId}#key=${keyBase64url}&file=${fileId}`;
}

/**
 * Encrypt file (vault.js compatibility wrapper).
 * Takes a File object and returns {encryptedData: Uint8Array, key: Uint8Array}.
 *
 * @param {File} file - The file to encrypt
 * @returns {Promise<{encryptedData: Uint8Array, key: Uint8Array}>} Encrypted data and key
 */
export async function encryptFileLegacy(file) {
  // Generate a random 256-bit key
  const fileKey = await generateFileKey();

  // Read file as ArrayBuffer
  const fileBuffer = await file.arrayBuffer();

  // Encrypt the file
  const { encrypted, iv } = await encryptFile(fileKey, fileBuffer);

  // Export the key to raw format
  const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
  const keyArray = new Uint8Array(exportedKey);

  // Combine IV + encrypted data
  const combined = new Uint8Array(iv.length + encrypted.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(encrypted), iv.length);

  return {
    encryptedData: combined,
    key: keyArray,
  };
}

/**
 * Decrypt file (vault.js compatibility wrapper).
 * Takes Uint8Array for both encryptedData and keyArray.
 *
 * @param {Uint8Array} encryptedData - The encrypted data (IV + ciphertext)
 * @param {Uint8Array} keyArray - The encryption key as raw bytes
 * @returns {Promise<ArrayBuffer>} Decrypted file data
 */
export async function decryptFileLegacy(encryptedData, keyArray) {
  // Import the key
  const fileKey = await crypto.subtle.importKey(
    "raw",
    keyArray,
    {
      name: "AES-GCM",
      length: 256,
    },
    false,
    ["decrypt"],
  );

  // Extract IV (first 12 bytes) and ciphertext
  const iv = encryptedData.slice(0, 12);
  const ciphertext = encryptedData.slice(12);

  // Decrypt
  return await decryptFile(fileKey, ciphertext, iv);
}

// Wrapper for compatibility with vault.js API
if (typeof window !== "undefined") {
  window.VaultCrypto = {
    encryptFile: encryptFileLegacy,
    decryptFile: decryptFileLegacy,
    arrayToBase64url,
    base64urlToArray,
    parseShareUrl,
    createShareUrl,
  };
}
