/** @file vault.js - Leyzen Vault client-side encryption using Web Crypto API */

/**
 * Encrypts a file using AES-GCM encryption.
 * @param {File} file - The file to encrypt
 * @returns {Promise<{encryptedData: Uint8Array, key: CryptoKey}>}
 */
async function encryptFile(file) {
  // Generate a random 256-bit key
  const key = await crypto.subtle.generateKey(
    {
      name: "AES-GCM",
      length: 256,
    },
    true,
    ["encrypt"],
  );

  // Generate a random 96-bit IV
  const iv = crypto.getRandomValues(new Uint8Array(12));

  // Read file as ArrayBuffer
  const fileBuffer = await file.arrayBuffer();

  // Encrypt the file
  const encryptedBuffer = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    fileBuffer,
  );

  // Export the key to raw format
  const exportedKey = await crypto.subtle.exportKey("raw", key);
  const keyArray = new Uint8Array(exportedKey);

  // Combine IV + encrypted data
  const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(encryptedBuffer), iv.length);

  return {
    encryptedData: combined,
    key: keyArray,
  };
}

/**
 * Decrypts encrypted data using AES-GCM.
 * @param {Uint8Array} encryptedData - The encrypted data (IV + ciphertext)
 * @param {Uint8Array} keyArray - The encryption key as raw bytes
 * @returns {Promise<ArrayBuffer>}
 */
async function decryptFile(encryptedData, keyArray) {
  // Import the key
  const key = await crypto.subtle.importKey(
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
  const decryptedBuffer = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    ciphertext,
  );

  return decryptedBuffer;
}

/**
 * Converts a Uint8Array to base64url string.
 * @param {Uint8Array} array - The array to convert
 * @returns {string}
 */
function arrayToBase64url(array) {
  const base64 = btoa(String.fromCharCode(...array));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

/**
 * Converts a base64url string to Uint8Array.
 * @param {string} base64url - The base64url string
 * @returns {Uint8Array}
 */
function base64urlToArray(base64url) {
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
 * Creates a shareable URL with the encryption key in the fragment.
 * @param {string} fileId - The file ID
 * @param {Uint8Array} key - The encryption key
 * @returns {string}
 */
function createShareUrl(fileId, key) {
  const keyBase64url = arrayToBase64url(key);
  const baseUrl = window.location.origin;
  return `${baseUrl}/share#file=${fileId}&key=${keyBase64url}`;
}

/**
 * Extracts file ID and key from URL fragment.
 * @returns {{fileId: string|null, key: Uint8Array|null}}
 */
function parseShareUrl() {
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
    console.error("Failed to parse key from URL:", e);
    return { fileId: null, key: null };
  }
}

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.VaultCrypto = {
    encryptFile,
    decryptFile,
    createShareUrl,
    parseShareUrl,
    arrayToBase64url,
    base64urlToArray,
  };
}
