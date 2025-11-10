/** @file search.js - Advanced search with local index */

/**
 * Search index manager using IndexedDB for local full-text search
 */
class SearchIndex {
  constructor() {
    this.dbName = "leyzen_vault_search";
    this.dbVersion = 1;
    this.storeName = "files_index";
    this.db = null;
  }

  /**
   * Initialize IndexedDB database
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
          const store = db.createObjectStore(this.storeName, {
            keyPath: "file_id",
          });
          store.createIndex("name", "name", { unique: false });
          store.createIndex("tags", "tags", {
            unique: false,
            multiEntry: true,
          });
          store.createIndex("mime_type", "mime_type", { unique: false });
        }
      };
    });
  }

  /**
   * Index a file
   * @param {Object} file - File metadata
   */
  async indexFile(file) {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    // Decrypt tags if available (would need key manager)
    let tags = [];
    if (file.encrypted_tags && window.KeyManager) {
      // In production, decrypt tags here
      // For now, just store empty tags
    }

    const indexEntry = {
      file_id: file.file_id,
      name: file.original_name.toLowerCase(),
      tags: tags,
      mime_type: file.mime_type || "",
      folder_id: file.folder_id || null,
      created_at: file.created_at,
      size: file.size,
    };

    await new Promise((resolve, reject) => {
      const request = store.put(indexEntry);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Remove file from index
   * @param {string} fileId - File ID
   */
  async removeFile(fileId) {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    await new Promise((resolve, reject) => {
      const request = store.delete(fileId);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Search files
   * @param {string} query - Search query
   * @param {Object} filters - Search filters
   * @returns {Promise<string[]>} Array of file IDs matching search
   */
  async search(query, filters = {}) {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readonly");
    const store = transaction.objectStore(this.storeName);

    return new Promise((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => {
        const allFiles = request.result;
        const lowerQuery = query.toLowerCase();

        const results = allFiles.filter((file) => {
          // Name search
          if (query && !file.name.includes(lowerQuery)) {
            return false;
          }

          // MIME type filter
          if (filters.mime_type && file.mime_type !== filters.mime_type) {
            return false;
          }

          // Folder filter
          if (filters.folder_id !== undefined) {
            if (filters.folder_id === null && file.folder_id !== null) {
              return false;
            }
            if (
              filters.folder_id !== null &&
              file.folder_id !== filters.folder_id
            ) {
              return false;
            }
          }

          // Date range filter
          if (filters.date_from) {
            const fileDate = new Date(file.created_at);
            const fromDate = new Date(filters.date_from);
            if (fileDate < fromDate) {
              return false;
            }
          }

          if (filters.date_to) {
            const fileDate = new Date(file.created_at);
            const toDate = new Date(filters.date_to);
            if (fileDate > toDate) {
              return false;
            }
          }

          // Size filter
          if (filters.min_size && file.size < filters.min_size) {
            return false;
          }

          if (filters.max_size && file.size > filters.max_size) {
            return false;
          }

          // Tag filter
          if (filters.tags && filters.tags.length > 0) {
            const fileTags = file.tags || [];
            const hasTag = filters.tags.some((tag) =>
              fileTags.includes(tag.toLowerCase()),
            );
            if (!hasTag) {
              return false;
            }
          }

          return true;
        });

        resolve(results.map((f) => f.file_id));
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Clear entire index
   */
  async clear() {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    await new Promise((resolve, reject) => {
      const request = store.clear();
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Rebuild index from files list
   * @param {Array} files - Array of file metadata
   */
  async rebuildIndex(files) {
    await this.clear();
    for (const file of files) {
      await this.indexFile(file);
    }
  }
}

/**
 * Search manager for UI
 */
class SearchManager {
  constructor() {
    this.index = new SearchIndex();
    this.searchTimeout = null;
  }

  /**
   * Initialize search manager
   */
  async init() {
    await this.index.init();
  }

  /**
   * Perform search with debounce
   * @param {string} query - Search query
   * @param {Object} filters - Search filters
   * @param {Function} callback - Callback function
   */
  async search(query, filters = {}, callback) {
    // Clear previous timeout
    if (this.searchTimeout) {
      clearTimeout(this.searchTimeout);
    }

    // Debounce search
    this.searchTimeout = setTimeout(async () => {
      try {
        const fileIds = await this.index.search(query, filters);
        if (callback) {
          callback(fileIds);
        }
      } catch (error) {
        console.error("Search error:", error);
        if (callback) {
          callback([]);
        }
      }
    }, 300);
  }

  /**
   * Update index with new file
   * @param {Object} file - File metadata
   */
  async indexFile(file) {
    await this.index.indexFile(file);
  }

  /**
   * Remove file from index
   * @param {string} fileId - File ID
   */
  async removeFile(fileId) {
    await this.index.removeFile(fileId);
  }

  /**
   * Rebuild index
   * @param {Array} files - Array of file metadata
   */
  async rebuildIndex(files) {
    await this.index.rebuildIndex(files);
  }
}

// Global search manager instance
let searchManager = null;

/**
 * Initialize search manager
 */
async function initSearchManager() {
  if (!searchManager) {
    searchManager = new SearchManager();
    await searchManager.init();
  }
  return searchManager;
}

/**
 * Perform search
 */
async function performSearch(query, filters = {}) {
  const manager = await initSearchManager();
  return await manager.index.search(query, filters);
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", async () => {
  await initSearchManager();

  // Setup real-time search with highlighting
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    let searchTimeout;

    searchInput.addEventListener("input", async (e) => {
      const query = e.target.value.trim();

      // Clear previous timeout
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }

      // Debounce search
      searchTimeout = setTimeout(async () => {
        if (query.length > 0) {
          // Perform search
          if (searchManager && window.filesList) {
            const fileIds = await searchManager.index.search(query);
            // Filter files list by search results
            const filteredFiles = window.filesList.filter((file) =>
              fileIds.includes(file.file_id),
            );
            // Render with highlights
            if (window.renderFiles) {
              window.renderFiles(filteredFiles);
              highlightSearchResults(query);
            }
          } else {
            // Fallback to simple filter
            if (window.renderFilteredFiles) {
              window.renderFilteredFiles();
            }
          }
        } else {
          // Clear search, show all files
          if (window.renderFilteredFiles) {
            window.renderFilteredFiles();
          }
          clearHighlights();
        }
      }, 300);
    });
  }

  // Rebuild index when files are loaded
  if (window.loadFiles) {
    const originalLoadFiles = window.loadFiles;
    window.loadFiles = async function () {
      await originalLoadFiles();
      // Rebuild search index
      if (window.filesList && searchManager) {
        await searchManager.rebuildIndex(window.filesList);
      }
    };
  }
});

// Highlight search results
function highlightSearchResults(query) {
  if (!query) return;

  const container = document.getElementById("files-list");
  if (!container) return;

  const lowerQuery = query.toLowerCase();
  const elements = container.querySelectorAll(
    ".file-name, .folder-name, .file-row-name, .folder-row-name",
  );

  elements.forEach((element) => {
    const text = element.textContent || element.innerText;
    const lowerText = text.toLowerCase();

    if (lowerText.includes(lowerQuery)) {
      // Add highlight class
      element.classList.add("search-highlight");
    }
  });
}

// Clear highlights
function clearHighlights() {
  const container = document.getElementById("files-list");
  if (!container) return;

  const elements = container.querySelectorAll(".search-highlight");
  elements.forEach((element) => {
    element.classList.remove("search-highlight");
  });
}

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.SearchIndex = SearchIndex;
  window.SearchManager = SearchManager;
  window.initSearchManager = initSearchManager;
  window.performSearch = performSearch;
  window.highlightSearchResults = highlightSearchResults;
  window.clearHighlights = clearHighlights;
}
