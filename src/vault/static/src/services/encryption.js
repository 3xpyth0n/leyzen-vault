/**
 * Client-side encryption service using Web Crypto API.
 *
 * This service handles the complete encryption chain:
 * - User master key derivation (Argon2-browser)
 * - VaultSpace key generation and encryption
 * - File key generation and encryption
 * - File encryption/decryption
 *
 * IMPORTANT: All encryption/decryption happens client-side.
 * The server never sees plaintext keys or file contents.
 *
 * CRYPTOGRAPHY NOTE:
 * - Server-side authentication: Argon2id (see auth_service.py)
 * - Client-side key derivation: Argon2-browser
 * These serve different purposes and both are secure for their use cases.
 */

import { logger } from "../utils/logger.js";
import argon2 from "argon2-browser/dist/argon2-bundled.min.js";

/**
 * Get the Web Crypto API, checking multiple possible contexts.
 * @returns {Crypto} The crypto API object
 * @throws {Error} If crypto API is not available
 */
function getCryptoAPI() {
  const cryptoAPI =
    (typeof window !== "undefined" && window.crypto) ||
    (typeof self !== "undefined" && self.crypto) ||
    (typeof globalThis !== "undefined" && globalThis.crypto) ||
    null;

  if (!cryptoAPI || !cryptoAPI.subtle) {
    const isSecureContext =
      (typeof window !== "undefined" && window.isSecureContext) ||
      (typeof location !== "undefined" && location.protocol === "https:");
    const errorMsg = isSecureContext
      ? "Web Crypto API (crypto.subtle) is not available. Please check your browser settings."
      : "Web Crypto API (crypto.subtle) requires a secure context (HTTPS). " +
        "Please access the application via HTTPS or use localhost for development. " +
        "Some browsers block crypto.subtle when accessing via IP address over HTTP.";
    throw new Error(errorMsg);
  }

  return cryptoAPI;
}

// Verify crypto.subtle is available at module load time (warning only)
if (typeof window !== "undefined") {
  try {
    getCryptoAPI();
  } catch (error) {
    logger.error("Web Crypto API check failed:", error.message);
  }
}

/**
 * Derive user master key from password using Argon2-browser.
 *
 * NOTE: This is for CLIENT-SIDE ENCRYPTION KEY DERIVATION ONLY.
 * Server-side password authentication uses Argon2id which provides better
 * protection against brute-force and GPU attacks.
 *
 * The salt must contain the "argon2:" prefix. The actual salt bytes follow
 * after the prefix. This prefix is automatically added by the server when
 * generating new salts.
 *
 * @param {string} password - User password
 * @param {Uint8Array} salt - Salt bytes (must start with "argon2:" prefix in UTF-8)
 * @param {boolean} extractable - Whether the key should be extractable (default: false for security)
 * @returns {Promise<CryptoKey>} User master key for encryption
 */
export async function deriveUserKey(password, salt, extractable = false) {
  // CRITICAL: Check if crypto.subtle is available
  // Some browsers block crypto.subtle in non-secure contexts (HTTP on IP addresses)
  const cryptoAPI = getCryptoAPI();

  // Extract actual salt (remove "argon2:" prefix)
  const argon2Prefix = new TextEncoder().encode("argon2:");

  if (salt.length < argon2Prefix.length) {
    throw new Error("Invalid salt: too short");
  }

  // Verify prefix
  const hasPrefix = salt
    .slice(0, argon2Prefix.length)
    .every((b, i) => b === argon2Prefix[i]);
  if (!hasPrefix) {
    throw new Error(
      "Invalid salt: missing 'argon2:' prefix. Migration required.",
    );
  }

  const actualSalt = salt.slice(argon2Prefix.length);

  // Validate salt length (Argon2 requires at least 8 bytes)
  if (actualSalt.length < 8) {
    throw new Error(
      `Invalid salt length: ${actualSalt.length} bytes (minimum 8 bytes required)`,
    );
  }

  // Derive key using Argon2-browser (version bundled to avoid WASM bundling issues)
  try {
    // Argon2-browser requires explicit parameters
    // Use secure defaults optimized for browser environment:
    // - time: 3 iterations (good balance between security and performance)
    // - mem: 4096 KiB (4MB) - reasonable for browsers, still secure
    // - parallelism: 4 threads
    // - hashLen: 32 bytes (256 bits)
    const result = await argon2.hash({
      pass: password,
      salt: actualSalt, // Uint8Array is accepted by argon2-browser
      type: argon2.ArgonType.Argon2id,
      time: 3, // Number of iterations
      mem: 4096, // Memory in KiB (4MB) - reduced for browser compatibility
      parallelism: 4, // Number of threads
      hashLen: 32, // Output length in bytes (256 bits)
    });

    // Verify result structure
    if (!result || !result.hash) {
      throw new Error("Argon2 returned invalid result structure");
    }

    // Convert derived hash (32 bytes) to CryptoKey
    const cryptoAPI = getCryptoAPI();
    const masterKeyBytes = new Uint8Array(result.hash);
    return await cryptoAPI.subtle.importKey(
      "raw",
      masterKeyBytes,
      {
        name: "AES-GCM",
        length: 256,
      },
      extractable,
      ["encrypt", "decrypt"],
    );
  } catch (error) {
    logger.error("Argon2 key derivation failed:", error);
    logger.error("Error details:", {
      message: error.message,
      code: error.code,
      stack: error.stack,
      saltLength: actualSalt.length,
      saltType: typeof actualSalt,
    });
    throw new Error(
      `Failed to derive master key with Argon2: ${
        error.message || error.code || "Unknown error"
      }`,
    );
  }
}

/**
 * Generate a random VaultSpace key.
 *
 * @returns {Promise<CryptoKey>} VaultSpace key
 */
export async function generateVaultSpaceKey() {
  const cryptoAPI = getCryptoAPI();
  return await cryptoAPI.subtle.generateKey(
    {
      name: "AES-GCM",
      length: 256,
    },
    true, // Extractable for encryption
    ["encrypt", "decrypt"],
  );
}

/**
 * Derive signing key from master key using HKDF.
 *
 * @param {CryptoKey} masterKey - Master key (must be extractable or already imported)
 * @returns {Promise<CryptoKey>} Signing key for HMAC
 */
async function deriveSigningKey(masterKey) {
  const cryptoAPI = getCryptoAPI();

  let keyMaterial;
  try {
    const rawKey = await cryptoAPI.subtle.exportKey("raw", masterKey);
    keyMaterial = await cryptoAPI.subtle.importKey(
      "raw",
      rawKey,
      {
        name: "HKDF",
        hash: "SHA-256",
      },
      false,
      ["deriveBits", "deriveKey"],
    );
  } catch (error) {
    // Otherwise, we need to derive from a different approach
    // For now, skip signature if key is not extractable
    throw new Error("Master key is not extractable, cannot derive signing key");
  }

  // Derive signing key using HKDF with specific info
  const encoder = new TextEncoder();
  const info = encoder.encode("leyzen-key-signature-v1");
  const salt = encoder.encode("leyzen-vault-hkdf-salt-2024-!!!!");

  return await cryptoAPI.subtle.deriveKey(
    {
      name: "HKDF",
      salt: salt,
      info: info,
      hash: "SHA-256",
    },
    keyMaterial,
    {
      name: "HMAC",
      hash: "SHA-256",
    },
    false,
    ["sign"],
  );
}

/**
 * Encrypt VaultSpace key with user master key.
 *
 * @param {CryptoKey} userKey - User master key
 * @param {CryptoKey} vaultspaceKey - VaultSpace key to encrypt
 * @returns {Promise<string>} Encrypted VaultSpace key (base64) with optional HMAC signature
 */
export async function encryptVaultSpaceKey(userKey, vaultspaceKey) {
  const cryptoAPI = getCryptoAPI();

  const rawKey = await cryptoAPI.subtle.exportKey("raw", vaultspaceKey);

  // Generate IV
  const iv = cryptoAPI.getRandomValues(new Uint8Array(12));

  // Encrypt with user key
  const encrypted = await cryptoAPI.subtle.encrypt(
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

  // Generate HMAC signature for integrity verification
  try {
    const signingKey = await deriveSigningKey(userKey);
    const signature = await cryptoAPI.subtle.sign("HMAC", signingKey, combined);

    // Append signature (32 bytes for HMAC-SHA256)
    const withSignature = new Uint8Array(combined.length + 32);
    withSignature.set(combined, 0);
    withSignature.set(new Uint8Array(signature), combined.length);

    return btoa(String.fromCharCode(...withSignature));
  } catch (error) {
    logger.warn("Failed to generate signature for encrypted key:", error);
    return btoa(String.fromCharCode(...combined));
  }
}

/**
 * Decrypt VaultSpace key with user master key.
 *
 * @param {CryptoKey} userKey - User master key
 * @param {string} encryptedKey - Encrypted VaultSpace key (base64) with optional HMAC signature
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

  const cryptoAPI = getCryptoAPI();
  let encryptedData = combined;
  let hasSignature = false;
  if (combined.length >= 92) {
    // Minimum size with signature: IV (12) + key (32) + tag (16) + signature (32) = 92 bytes

    const signature = combined.slice(-32);
    const dataWithoutSignature = combined.slice(0, -32);
    try {
      const signingKey = await deriveSigningKey(userKey);
      const isValid = await cryptoAPI.subtle.verify(
        "HMAC",
        signingKey,
        signature,
        dataWithoutSignature,
      );
      if (isValid) {
        encryptedData = dataWithoutSignature;
        hasSignature = true;
      }
    } catch (error) {
      logger.debug(
        "Signature verification failed, using key without signature:",
        error,
      );
    }
  }

  // Extract IV and encrypted data
  const iv = encryptedData.slice(0, 12);
  const encrypted = encryptedData.slice(12);

  // Decrypt
  const decrypted = await cryptoAPI.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    userKey,
    encrypted,
  );

  return await cryptoAPI.subtle.importKey(
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
  const cryptoAPI = getCryptoAPI();
  return await cryptoAPI.subtle.generateKey(
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
 * @returns {Promise<string>} Encrypted file key (base64) with optional HMAC signature
 */
export async function encryptFileKey(vaultspaceKey, fileKey) {
  const cryptoAPI = getCryptoAPI();

  const rawKey = await cryptoAPI.subtle.exportKey("raw", fileKey);

  // Generate IV
  const iv = cryptoAPI.getRandomValues(new Uint8Array(12));

  // Encrypt with VaultSpace key
  const encrypted = await cryptoAPI.subtle.encrypt(
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

  // Generate HMAC signature for integrity verification
  try {
    const signingKey = await deriveSigningKey(vaultspaceKey);
    const signature = await cryptoAPI.subtle.sign("HMAC", signingKey, combined);

    // Append signature (32 bytes for HMAC-SHA256)
    const withSignature = new Uint8Array(combined.length + 32);
    withSignature.set(combined, 0);
    withSignature.set(new Uint8Array(signature), combined.length);

    return btoa(String.fromCharCode(...withSignature));
  } catch (error) {
    logger.warn("Failed to generate signature for encrypted key:", error);
    return btoa(String.fromCharCode(...combined));
  }
}

/**
 * Decrypt file key with VaultSpace key.
 *
 * @param {CryptoKey} vaultspaceKey - VaultSpace key
 * @param {string} encryptedKey - Encrypted file key (base64) with optional HMAC signature
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

  const cryptoAPI = getCryptoAPI();
  let encryptedData = combined;
  let hasSignature = false;
  if (combined.length >= 92) {
    // Minimum size with signature: IV (12) + key (32) + tag (16) + signature (32) = 92 bytes

    const signature = combined.slice(-32);
    const dataWithoutSignature = combined.slice(0, -32);
    try {
      const signingKey = await deriveSigningKey(vaultspaceKey);
      const isValid = await cryptoAPI.subtle.verify(
        "HMAC",
        signingKey,
        signature,
        dataWithoutSignature,
      );
      if (isValid) {
        encryptedData = dataWithoutSignature;
        hasSignature = true;
      }
    } catch (error) {
      logger.debug(
        "Signature verification failed, using key without signature:",
        error,
      );
    }
  }

  // Extract IV and encrypted data
  const iv = encryptedData.slice(0, 12);
  const encrypted = encryptedData.slice(12);

  // Decrypt
  const decrypted = await cryptoAPI.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    vaultspaceKey,
    encrypted,
  );

  return await cryptoAPI.subtle.importKey(
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
  const cryptoAPI = getCryptoAPI();
  // Convert to ArrayBuffer if needed
  const data = fileData instanceof ArrayBuffer ? fileData : fileData.buffer;

  // Generate IV
  const iv = cryptoAPI.getRandomValues(new Uint8Array(12));

  // Encrypt
  const encrypted = await cryptoAPI.subtle.encrypt(
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
  const cryptoAPI = getCryptoAPI();
  return await cryptoAPI.subtle.decrypt(
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
  const cryptoAPI = getCryptoAPI();
  return cryptoAPI.getRandomValues(new Uint8Array(length));
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
 * @returns {Promise<string>} Share URL
 */
export async function createShareUrl(fileId, key) {
  const keyBase64url = arrayToBase64url(key);

  // Get base URL using VAULT_URL (with fallback to window.location.origin)
  let baseUrl;
  try {
    const { getVaultBaseUrl } = await import("./vault-config.js");
    baseUrl = await getVaultBaseUrl();
  } catch (e) {
    baseUrl = window.location.origin;
  }

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

  const cryptoAPI = getCryptoAPI();
  const exportedKey = await cryptoAPI.subtle.exportKey("raw", fileKey);
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
  const cryptoAPI = getCryptoAPI();
  const fileKey = await cryptoAPI.subtle.importKey(
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
