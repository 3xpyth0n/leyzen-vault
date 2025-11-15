/**
 * Clipboard Manager for file operations
 * Manages copied items for paste operations (Ctrl+C/Ctrl+V)
 */

class ClipboardManager {
  constructor() {
    this.items = [];
    this.listeners = new Set();
    this.isCutMode = false; // Flag to distinguish copy vs cut
  }

  /**
   * Copy items to clipboard
   * @param {Array} items - Array of items to copy (files/folders)
   */
  copy(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return;
    }

    this.items = items.map((item) => ({
      id: item.id,
      type: item.mime_type === "application/x-directory" ? "folder" : "file",
      name: item.original_name,
      vaultspaceId: item.vaultspace_id,
      parentId: item.parent_id,
    }));
    this.isCutMode = false;

    this.notifyListeners();
  }

  /**
   * Cut items to clipboard (for move operation)
   * @param {Array} items - Array of items to cut (files/folders)
   */
  cut(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return;
    }

    this.items = items.map((item) => ({
      id: item.id,
      type: item.mime_type === "application/x-directory" ? "folder" : "file",
      name: item.original_name,
      vaultspaceId: item.vaultspace_id,
      parentId: item.parent_id,
    }));
    this.isCutMode = true;

    this.notifyListeners();
  }

  /**
   * Get copied items
   * @returns {Array} Array of copied items
   */
  getItems() {
    return [...this.items];
  }

  /**
   * Check if clipboard has items
   * @returns {boolean}
   */
  hasItems() {
    return this.items.length > 0;
  }

  /**
   * Clear clipboard
   */
  clear() {
    this.items = [];
    this.isCutMode = false;
    this.notifyListeners();
  }

  /**
   * Check if clipboard is in cut mode
   * @returns {boolean}
   */
  isCut() {
    return this.isCutMode;
  }

  /**
   * Subscribe to clipboard changes
   * @param {Function} callback - Callback function
   * @returns {Function} Unsubscribe function
   */
  subscribe(callback) {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Notify all listeners of clipboard changes
   */
  notifyListeners() {
    this.listeners.forEach((callback) => {
      try {
        callback(this.items);
      } catch (error) {
        console.error("Clipboard listener error:", error);
      }
    });
  }
}

// Export singleton instance
export const clipboardManager = new ClipboardManager();
