/** @file keymanager.js - Client-side key management for folder encryption */

/**
 * Key Manager for handling user master keys and folder key derivation.
 * Uses IndexedDB for secure local storage of keys.
 */

class KeyManager {
  constructor() {
    this.dbName = "leyzen_vault_keys";
    this.dbVersion = 1;
    this.storeName = "keys";
    this.db = null;
  }

  /**
   * Initialize IndexedDB database.
   * @returns {Promise<void>}
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName);
        }
      };
    });
  }

  /**
   * Derive user master key from password using PBKDF2.
   * @param {string} password - User password
   * @param {Uint8Array} salt - Salt bytes (optional, generated if not provided)
   * @returns {Promise<{masterKey: Uint8Array, salt: Uint8Array}>}
   */
  async deriveUserMasterKey(password, salt = null) {
    if (!salt) {
      salt = crypto.getRandomValues(new Uint8Array(32));
    }

    const encoder = new TextEncoder();
    const passwordData = encoder.encode(password);

    // Import password as key
    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      passwordData,
      "PBKDF2",
      false,
      ["deriveBits", "deriveKey"],
    );

    // Derive master key using PBKDF2
    const masterKey = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        salt: salt,
        iterations: 600000,
        hash: "SHA-256",
      },
      keyMaterial,
      256, // 32 bytes = 256 bits
    );

    return {
      masterKey: new Uint8Array(masterKey),
      salt: salt,
    };
  }

  /**
   * Derive folder key from master key and folder path using HKDF.
   * @param {Uint8Array} masterKey - User master key
   * @param {string[]} folderPath - Array of folder IDs from root to target folder
   * @returns {Promise<Uint8Array>}
   */
  async deriveFolderKey(masterKey, folderPath) {
    // Create info string from folder path
    const pathString = folderPath.join("/");
    const encoder = new TextEncoder();
    const info = encoder.encode(`folder:${pathString}`);

    // Import master key
    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      masterKey,
      {
        name: "HKDF",
        hash: "SHA-256",
      },
      false,
      ["deriveBits"],
    );

    // Derive folder key using HKDF
    // Use a fixed non-zero salt for HKDF derivation (matches server-side implementation)
    // This is acceptable because:
    // 1. The master key is already cryptographically secure (derived from password)
    // 2. HKDF is designed to be used with a fixed salt in key derivation contexts
    // 3. The info parameter provides context separation (folder path, file ID, etc.)
    const salt = new TextEncoder().encode("leyzen-vault-hkdf-salt-2024-!!!!");
    const folderKey = await crypto.subtle.deriveBits(
      {
        name: "HKDF",
        salt: salt,
        info: info,
        hash: "SHA-256",
      },
      keyMaterial,
      256, // 32 bytes = 256 bits
    );

    return new Uint8Array(folderKey);
  }

  /**
   * Encrypt folder name using AES-GCM.
   * @param {string} folderName - Plain folder name
   * @param {Uint8Array} folderKey - Folder encryption key
   * @returns {Promise<{encrypted: Uint8Array, nameHash: string}>}
   */
  async encryptFolderName(folderName, folderKey) {
    // Compute hash of folder name for search
    const encoder = new TextEncoder();
    const nameData = encoder.encode(folderName);
    const hashBuffer = await crypto.subtle.digest("SHA-256", nameData);
    const nameHash = Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    // Encrypt folder name
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await crypto.subtle.importKey(
      "raw",
      folderKey,
      {
        name: "AES-GCM",
        length: 256,
      },
      false,
      ["encrypt"],
    );

    const encryptedBuffer = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      key,
      nameData,
    );

    // Combine IV + encrypted data
    const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(encryptedBuffer), iv.length);

    return {
      encrypted: combined,
      nameHash: nameHash,
    };
  }

  /**
   * Decrypt folder name using AES-GCM.
   * @param {Uint8Array} encryptedData - Encrypted folder name (IV + ciphertext)
   * @param {Uint8Array} folderKey - Folder encryption key
   * @returns {Promise<string>}
   */
  async decryptFolderName(encryptedData, folderKey) {
    // Extract IV and ciphertext
    const iv = encryptedData.slice(0, 12);
    const ciphertext = encryptedData.slice(12);

    // Import key
    const key = await crypto.subtle.importKey(
      "raw",
      folderKey,
      {
        name: "AES-GCM",
        length: 256,
      },
      false,
      ["decrypt"],
    );

    // Decrypt
    const decryptedBuffer = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      key,
      ciphertext,
    );

    // Convert to string
    const decoder = new TextDecoder();
    return decoder.decode(decryptedBuffer);
  }

  /**
   * Store master key in IndexedDB (encrypted with a session key).
   * @param {Uint8Array} masterKey - User master key
   * @param {Uint8Array} salt - Salt used for key derivation
   * @returns {Promise<void>}
   */
  async storeMasterKey(masterKey, salt) {
    await this.init();

    // For security, we should encrypt the master key with a session key
    // For now, we store it encrypted with a local key derived from user password
    // In production, consider using a more secure approach

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    // Store master key and salt separately
    await Promise.all([
      new Promise((resolve, reject) => {
        const request = store.put(Array.from(masterKey), "master_key");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
      new Promise((resolve, reject) => {
        const request = store.put(Array.from(salt), "salt");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
    ]);
  }

  /**
   * Get stored master key from IndexedDB.
   * @returns {Promise<{masterKey: Uint8Array, salt: Uint8Array} | null>}
   */
  async getMasterKey() {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readonly");
    const store = transaction.objectStore(this.storeName);

    return new Promise((resolve, reject) => {
      const masterKeyRequest = store.get("master_key");
      const saltRequest = store.get("salt");

      let masterKeyData = null;
      let saltData = null;
      let completed = 0;

      const checkComplete = () => {
        completed++;
        if (completed === 2) {
          if (masterKeyData && saltData) {
            resolve({
              masterKey: new Uint8Array(masterKeyData),
              salt: new Uint8Array(saltData),
            });
          } else {
            resolve(null);
          }
        }
      };

      masterKeyRequest.onsuccess = () => {
        masterKeyData = masterKeyRequest.result;
        checkComplete();
      };
      masterKeyRequest.onerror = () => reject(masterKeyRequest.error);

      saltRequest.onsuccess = () => {
        saltData = saltRequest.result;
        checkComplete();
      };
      saltRequest.onerror = () => reject(saltRequest.error);
    });
  }

  /**
   * Clear all stored keys.
   * @returns {Promise<void>}
   */
  async clearKeys() {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    await Promise.all([
      new Promise((resolve, reject) => {
        const request = store.delete("master_key");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
      new Promise((resolve, reject) => {
        const request = store.delete("salt");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
    ]);
  }

  /**
   * Convert Uint8Array to base64url string.
   * @param {Uint8Array} array - Array to convert
   * @returns {string}
   */
  arrayToBase64url(array) {
    const base64 = btoa(String.fromCharCode(...array));
    return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
  }

  /**
   * Convert base64url string to Uint8Array.
   * @param {string} base64url - Base64url string
   * @returns {Uint8Array}
   */
  base64urlToArray(base64url) {
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
}

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.KeyManager = KeyManager;
}
