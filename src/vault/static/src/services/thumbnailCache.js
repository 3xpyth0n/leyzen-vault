/**
 * Thumbnail cache service using IndexedDB.
 * Stores decoded thumbnail blob data for persistent caching.
 */

const DB_NAME = "leyzen_vault_thumbnails";
const DB_VERSION = 1;
const STORE_NAME = "thumbnails";

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
      reject(new Error("Failed to open IndexedDB for thumbnail cache"));
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
        objectStore.createIndex("timestamp", "timestamp", { unique: false });
      }
    };
  });
}

/**
 * Get a thumbnail from cache.
 * @param {string} fileId - File ID
 * @returns {Promise<Blob|null>} Thumbnail blob or null if not found
 */
export async function getThumbnail(fileId) {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readonly");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve) => {
      const req = store.get(fileId);
      req.onsuccess = () => {
        const result = req.result;
        if (result && result.blob) {
          resolve(result.blob);
        } else {
          resolve(null);
        }
      };
      req.onerror = () => {
        resolve(null);
      };
    });
  } catch (error) {
    return null;
  }
}

/**
 * Store a thumbnail in cache.
 * @param {string} fileId - File ID
 * @param {Blob} blob - Thumbnail blob data
 * @param {string} mimeType - MIME type of the thumbnail
 * @returns {Promise<void>}
 */
export async function setThumbnail(fileId, blob, mimeType = "image/jpeg") {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readwrite");
    const store = transaction.objectStore(STORE_NAME);

    const data = {
      fileId,
      blob,
      mimeType,
      timestamp: Date.now(),
    };

    return new Promise((resolve, reject) => {
      const req = store.put(data);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    // Silently fail - cache is optional
  }
}

/**
 * Delete a thumbnail from cache.
 * @param {string} fileId - File ID
 * @returns {Promise<void>}
 */
export async function deleteThumbnail(fileId) {
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
    // Silently fail
  }
}

/**
 * Clear all thumbnails from cache.
 * @returns {Promise<void>}
 */
export async function clearCache() {
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
    // Silently fail
  }
}

/**
 * Check if a thumbnail exists in cache.
 * @param {string} fileId - File ID
 * @returns {Promise<boolean>} True if thumbnail exists in cache
 */
export async function hasThumbnail(fileId) {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], "readonly");
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve) => {
      const req = store.get(fileId);
      req.onsuccess = () => {
        resolve(req.result !== undefined);
      };
      req.onerror = () => {
        resolve(false);
      };
    });
  } catch (error) {
    return false;
  }
}
