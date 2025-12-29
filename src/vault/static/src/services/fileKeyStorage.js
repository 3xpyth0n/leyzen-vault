/**
 * File key storage service using IndexedDB.
 * Migrates from localStorage to IndexedDB for better security.
 */

const DB_NAME = "leyzen_vault_keys";
const DB_VERSION = 1;
const STORE_NAME = "file_keys";

let dbInstance = null;

/**
 * Open IndexedDB database.
 * @returns {Promise<IDBDatabase>} Database instance
 */
function openDB() {
  if (dbInstance) {
    return Promise.resolve(dbInstance);
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      reject(new Error("Failed to open IndexedDB"));
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      resolve(dbInstance);
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const objectStore = db.createObjectStore(STORE_NAME, {
          keyPath: "fileId",
        });
        objectStore.createIndex("fileId", "fileId", { unique: true });
      }
    };
  });
}

/**
 * Migrate file keys from localStorage to IndexedDB.
 * @returns {Promise<void>}
 */
async function migrateFromLocalStorage() {
  try {
    const stored = localStorage.getItem("vault_keys");
    if (!stored) {
      return; // Nothing to migrate
    }

    const keys = JSON.parse(stored);
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    const existing = await new Promise((resolve) => {
      const req = store.get("__migration_done");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });

    if (existing) {
      return; // Already migrated
    }

    // Migrate all keys
    const promises = Object.entries(keys).map(([fileId, key]) => {
      return new Promise((resolve, reject) => {
        const req = store.put({ fileId, key });
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
    });

    await Promise.all(promises);

    // Mark migration as done
    await new Promise((resolve, reject) => {
      const req = store.put({ fileId: "__migration_done", key: "true" });
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });

    // Optionally clear localStorage after migration
    // localStorage.removeItem("vault_keys");
  } catch (error) {}
}

/**
 * Store a file key in IndexedDB.
 * @param {string} fileId - File ID
 * @param {string} key - Base64-encoded key
 * @returns {Promise<void>}
 */
export async function storeFileKey(fileId, key) {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const req = store.put({ fileId, key });
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    keys[fileId] = key;
    localStorage.setItem("vault_keys", JSON.stringify(keys));
  }
}

/**
 * Get a file key from IndexedDB.
 * @param {string} fileId - File ID
 * @returns {Promise<string|null>} Base64-encoded key or null if not found
 */
export async function getFileKey(fileId) {
  try {
    // Migrate on first access
    await migrateFromLocalStorage();

    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readonly");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve) => {
      const req = store.get(fileId);
      req.onsuccess = () => {
        const result = req.result;
        resolve(result ? result.key : null);
      };
      req.onerror = () => {
        const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
        resolve(keys[fileId] || null);
      };
    });
  } catch (error) {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    return keys[fileId] || null;
  }
}

/**
 * Remove a file key from IndexedDB.
 * @param {string} fileId - File ID
 * @returns {Promise<void>}
 */
export async function removeFileKey(fileId) {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const req = store.delete(fileId);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    delete keys[fileId];
    localStorage.setItem("vault_keys", JSON.stringify(keys));
  }
}

/**
 * Clear all file keys from IndexedDB.
 * @returns {Promise<void>}
 */
export async function clearAllFileKeys() {
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
    localStorage.removeItem("vault_keys");
  }
}
