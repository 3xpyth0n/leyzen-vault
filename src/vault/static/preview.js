/** @file preview.js - File preview functionality */

// Helper function to safely set innerHTML with Trusted Types
function setInnerHTML(element, html) {
  // Use the global policy created in base.html if available
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {
      // Fallback if policy fails
      console.warn("Failed to use vaultHTMLPolicy:", e);
    }
  }

  // Fallback: if Trusted Types is required but policy doesn't exist, this will fail
  // This should not happen if base.html script executed correctly
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use defaultPolicy:", e);
    }
  }

  // Last resort: direct assignment (will fail if Trusted Types is enforced)
  element.innerHTML = html;
}

// Helper function to safely clear an element without using innerHTML
function clearElement(element) {
  if (!element) return;
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

/**
 * Preview manager for displaying file previews
 */
class PreviewManager {
  constructor() {
    this.previewModal = null;
    this.currentPreview = null;
    this.previewFiles = []; // List of files for navigation
    this.currentIndex = -1;
  }

  /**
   * Set the list of files for navigation
   * @param {Array} files - Array of file objects
   */
  setPreviewFiles(files) {
    this.previewFiles = files || [];
  }

  /**
   * Navigate to previous file
   */
  navigatePrevious() {
    if (this.previewFiles.length === 0 || this.currentIndex <= 0) return;

    this.currentIndex--;
    const file = this.previewFiles[this.currentIndex];
    if (file) {
      this.showPreview(file.file_id, file.original_name, file.mime_type);
    }
  }

  /**
   * Navigate to next file
   */
  navigateNext() {
    if (
      this.previewFiles.length === 0 ||
      this.currentIndex >= this.previewFiles.length - 1
    )
      return;

    this.currentIndex++;
    const file = this.previewFiles[this.currentIndex];
    if (file) {
      this.showPreview(file.file_id, file.original_name, file.mime_type);
    }
  }

  /**
   * Initialize preview modal
   */
  init() {
    // Create preview modal if it doesn't exist
    if (!document.getElementById("preview-modal")) {
      const modal = document.createElement("div");
      modal.id = "preview-modal";
      modal.className = "modal hidden";
      setInnerHTML(
        modal,
        `
                <div class="modal-content preview-modal-content">
                    <div class="modal-header">
                        <h3 id="preview-title">Preview</h3>
                        <div class="preview-nav-buttons">
                            <button class="preview-nav-btn" id="preview-prev" title="Previous file">‹</button>
                            <button class="preview-nav-btn" id="preview-next" title="Next file">›</button>
                        </div>
                        <button class="modal-close" id="preview-close">&times;</button>
                    </div>
                    <div class="modal-body preview-body">
                        <div id="preview-container"></div>
                    </div>
                </div>
                <div class="modal-backdrop"></div>
            `,
      );
      document.body.appendChild(modal);
    }

    this.previewModal = document.getElementById("preview-modal");
    const closeBtn = document.getElementById("preview-close");
    const prevBtn = document.getElementById("preview-prev");
    const nextBtn = document.getElementById("preview-next");
    const backdrop = this.previewModal.querySelector(".modal-backdrop");

    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.hide());
    }
    if (prevBtn) {
      prevBtn.addEventListener("click", () => this.navigatePrevious());
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", () => this.navigateNext());
    }
    if (backdrop) {
      backdrop.addEventListener("click", () => this.hide());
    }

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (
        e.key === "Escape" &&
        !this.previewModal.classList.contains("hidden")
      ) {
        this.hide();
      } else if (
        e.key === "ArrowLeft" &&
        !this.previewModal.classList.contains("hidden")
      ) {
        this.navigatePrevious();
      } else if (
        e.key === "ArrowRight" &&
        !this.previewModal.classList.contains("hidden")
      ) {
        this.navigateNext();
      }
    });
  }

  /**
   * Show preview for a file
   * @param {string} fileId - File ID
   * @param {string} fileName - File name
   * @param {string} mimeType - MIME type
   */
  async showPreview(fileId, fileName, mimeType) {
    if (!this.previewModal) {
      this.init();
    }

    const title = document.getElementById("preview-title");
    const container = document.getElementById("preview-container");
    const prevBtn = document.getElementById("preview-prev");
    const nextBtn = document.getElementById("preview-next");

    if (title) {
      title.textContent = fileName || "Preview";
    }

    // Update navigation buttons
    if (this.previewFiles.length > 0) {
      this.currentIndex = this.previewFiles.findIndex(
        (f) => f.file_id === fileId,
      );
      if (this.currentIndex === -1) {
        this.currentIndex = 0;
      }

      if (prevBtn) {
        prevBtn.disabled = this.currentIndex <= 0;
        prevBtn.classList.toggle("disabled", this.currentIndex <= 0);
      }
      if (nextBtn) {
        nextBtn.disabled = this.currentIndex >= this.previewFiles.length - 1;
        nextBtn.classList.toggle(
          "disabled",
          this.currentIndex >= this.previewFiles.length - 1,
        );
      }
    } else {
      if (prevBtn) {
        prevBtn.disabled = true;
        prevBtn.classList.add("disabled");
      }
      if (nextBtn) {
        nextBtn.disabled = true;
        nextBtn.classList.add("disabled");
      }
    }

    if (container) {
      setInnerHTML(
        container,
        '<div class="preview-loading">Loading preview...</div>',
      );
    }

    this.previewModal.classList.remove("hidden");
    this.currentPreview = { fileId, fileName, mimeType };

    try {
      await this.loadPreview(fileId, mimeType, container);
    } catch (error) {
      console.error("Error loading preview:", error);
      if (container) {
        const errorHtml = `<div class="preview-error">Failed to load preview: ${escapeHtml(error.message)}</div>`;
        setInnerHTML(container, errorHtml);
      }
    }
  }

  /**
   * Load preview content
   * @param {string} fileId - File ID
   * @param {string} mimeType - MIME type
   * @param {HTMLElement} container - Container element
   */
  async loadPreview(fileId, mimeType, container) {
    if (!mimeType) {
      setInnerHTML(
        container,
        '<div class="preview-error">Preview not available for this file type</div>',
      );
      return;
    }

    if (mimeType.startsWith("image/")) {
      await this.loadImagePreview(fileId, container);
    } else if (mimeType === "application/pdf") {
      await this.loadPdfPreview(fileId, container);
    } else if (mimeType.startsWith("text/")) {
      await this.loadTextPreview(fileId, container);
    } else {
      setInnerHTML(
        container,
        '<div class="preview-error">Preview not available for this file type</div>',
      );
    }
  }

  /**
   * Load image preview
   * @param {string} fileId - File ID
   * @param {HTMLElement} container - Container element
   */
  async loadImagePreview(fileId, container) {
    // Download and decrypt file
    const key = window.getFileKey ? window.getFileKey(fileId) : null;
    if (!key) {
      setInnerHTML(
        container,
        '<div class="preview-error">Decryption key not found</div>',
      );
      return;
    }

    try {
      const response = await fetch(`/api/files/${fileId}`);
      if (!response.ok) throw new Error("Download failed");

      const encryptedBlob = await response.blob();
      const encryptedArrayBuffer = await encryptedBlob.arrayBuffer();
      const encryptedData = new Uint8Array(encryptedArrayBuffer);

      // Decrypt
      const decryptedBuffer = await window.VaultCrypto.decryptFile(
        encryptedData,
        key,
      );
      const decryptedBlob = new Blob([decryptedBuffer]);

      // Create image preview
      const url = URL.createObjectURL(decryptedBlob);
      const img = document.createElement("img");
      img.src = url;
      img.style.maxWidth = "100%";
      img.style.maxHeight = "80vh";
      img.style.objectFit = "contain";

      img.onload = () => {
        URL.revokeObjectURL(url);
      };

      clearElement(container);
      container.appendChild(img);
    } catch (error) {
      const errorHtml = `<div class="preview-error">Failed to load image: ${escapeHtml(error.message)}</div>`;
      setInnerHTML(container, errorHtml);
    }
  }

  /**
   * Load PDF preview
   * @param {string} fileId - File ID
   * @param {HTMLElement} container - Container element
   */
  async loadPdfPreview(fileId, container) {
    setInnerHTML(
      container,
      '<div class="preview-error">PDF preview requires PDF.js library (not implemented)</div>',
    );
  }

  /**
   * Load text preview
   * @param {string} fileId - File ID
   * @param {HTMLElement} container - Container element
   */
  async loadTextPreview(fileId, container) {
    const key = window.getFileKey ? window.getFileKey(fileId) : null;
    if (!key) {
      setInnerHTML(
        container,
        '<div class="preview-error">Decryption key not found</div>',
      );
      return;
    }

    try {
      const response = await fetch(`/api/files/${fileId}`);
      if (!response.ok) throw new Error("Download failed");

      const encryptedBlob = await response.blob();
      const encryptedArrayBuffer = await encryptedBlob.arrayBuffer();
      const encryptedData = new Uint8Array(encryptedArrayBuffer);

      // Decrypt
      const decryptedBuffer = await window.VaultCrypto.decryptFile(
        encryptedData,
        key,
      );
      const decoder = new TextDecoder();
      const text = decoder.decode(decryptedBuffer);

      // Create text preview
      const pre = document.createElement("pre");
      pre.style.whiteSpace = "pre-wrap";
      pre.style.wordWrap = "break-word";
      pre.style.maxHeight = "70vh";
      pre.style.overflow = "auto";
      pre.textContent = text.substring(0, 10000); // Limit to 10KB

      clearElement(container);
      container.appendChild(pre);
    } catch (error) {
      const errorHtml = `<div class="preview-error">Failed to load text: ${escapeHtml(error.message)}</div>`;
      setInnerHTML(container, errorHtml);
    }
  }

  /**
   * Hide preview modal
   */
  hide() {
    if (this.previewModal) {
      this.previewModal.classList.add("hidden");
      this.currentPreview = null;
    }
  }
}

// Global preview manager instance
let previewManager = null;

/**
 * Initialize preview manager
 */
function initPreviewManager() {
  if (!previewManager) {
    previewManager = new PreviewManager();
    previewManager.init();
  }
  return previewManager;
}

/**
 * Show preview for a file
 */
function showFilePreview(fileId, fileName, mimeType) {
  const manager = initPreviewManager();

  // Set preview files from current files list for navigation
  if (window.filesList && Array.isArray(window.filesList)) {
    manager.setPreviewFiles(window.filesList);
  }

  manager.showPreview(fileId, fileName, mimeType);
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  initPreviewManager();
});

// Helper function to escape HTML (if not already defined)
function escapeHtml(text) {
  if (
    typeof window !== "undefined" &&
    window.Notifications &&
    window.Notifications.escapeHtml
  ) {
    return window.Notifications.escapeHtml(text);
  }
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.PreviewManager = PreviewManager;
  window.showFilePreview = showFilePreview;
  window.initPreviewManager = initPreviewManager;
  window.clearElement = clearElement; // Export clearElement utility
}
