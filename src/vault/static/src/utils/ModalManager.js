/**
 * Global Modal Manager
 * Ensures only one modal can be open at a time across the entire application
 */

class ModalManager {
  constructor() {
    this.currentModal = null;
    this.listeners = new Set();
  }

  /**
   * Open a modal
   * @param {string} modalId - Unique identifier for the modal
   * @param {Function} openCallback - Callback to open the modal
   * @param {Function} closeCallback - Callback to close the modal
   */
  open(modalId, openCallback, closeCallback) {
    // Close any existing modal first
    if (this.currentModal && this.currentModal.id !== modalId) {
      this.close();
    }

    // Set current modal
    this.currentModal = {
      id: modalId,
      close: closeCallback,
    };

    // Execute open callback
    if (openCallback) {
      openCallback();
    }

    // Notify listeners
    this.notifyListeners("open", modalId);
  }

  /**
   * Close the current modal
   */
  close() {
    if (this.currentModal && this.currentModal.close) {
      this.currentModal.close();
      const closedId = this.currentModal.id;
      this.currentModal = null;
      this.notifyListeners("close", closedId);
    }
  }

  /**
   * Check if a modal is currently open
   * @param {string} modalId - Optional modal ID to check
   * @returns {boolean}
   */
  isOpen(modalId = null) {
    if (modalId) {
      return this.currentModal && this.currentModal.id === modalId;
    }
    return this.currentModal !== null;
  }

  /**
   * Get the current modal ID
   * @returns {string|null}
   */
  getCurrentModalId() {
    return this.currentModal ? this.currentModal.id : null;
  }

  /**
   * Subscribe to modal events
   * @param {Function} callback - Callback function (event, modalId)
   * @returns {Function} Unsubscribe function
   */
  subscribe(callback) {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Notify all listeners of modal events
   * @param {string} event - Event type ('open' or 'close')
   * @param {string} modalId - Modal ID
   */
  notifyListeners(event, modalId) {
    this.listeners.forEach((callback) => {
      try {
        callback(event, modalId);
      } catch (error) {}
    });
  }

  /**
   * Close modal on Escape key
   */
  setupEscapeKeyHandler() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) {
        e.preventDefault();
        this.close();
      }
    });
  }
}

// Export singleton instance
export const modalManager = new ModalManager();

// Setup escape key handler
if (typeof window !== "undefined") {
  modalManager.setupEscapeKeyHandler();
}
