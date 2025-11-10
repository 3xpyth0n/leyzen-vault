/**
 * Folder Picker Modal
 * Allows user to select a destination folder for move/copy operations
 */

// Helper function to safely set innerHTML with Trusted Types
function setInnerHTML(element, html) {
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use vaultHTMLPolicy:", e);
    }
  }
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use defaultPolicy:", e);
    }
  }
  element.innerHTML = html;
}

class FolderPicker {
  constructor() {
    this.modal = null;
    this.selectedFolderId = null;
    this.resolvePromise = null;
    this.rejectPromise = null;
    this.folders = [];
    this.currentFolderId = null;
    this.vaultspaceId = null;
  }

  /**
   * Show folder picker modal
   * @param {Array} folders - List of folders
   * @param {string} currentFolderId - Current folder ID
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string} excludeFolderId - Folder ID to exclude (e.g., source folder)
   * @returns {Promise<string|null>} Selected folder ID or null
   */
  async show(folders, currentFolderId, vaultspaceId, excludeFolderId = null) {
    this.folders = folders || [];
    this.currentFolderId = currentFolderId;
    this.vaultspaceId = vaultspaceId;
    this.selectedFolderId = null;
    this.excludeFolderId = excludeFolderId;

    return new Promise((resolve, reject) => {
      this.resolvePromise = resolve;
      this.rejectPromise = reject;
      this.createModal();
      this.renderFolders();
      this.modal.classList.remove("hidden");
    });
  }

  /**
   * Create modal HTML
   */
  createModal() {
    // Remove existing modal if any
    const existing = document.getElementById("folder-picker-modal");
    if (existing) {
      existing.remove();
    }

    const modalHTML = `
      <div id="folder-picker-modal" class="modal-overlay">
        <div class="modal folder-picker-modal">
          <div class="modal-header">
            <h2>Select Destination Folder</h2>
            <button class="modal-close" id="folder-picker-close">&times;</button>
          </div>
          <div class="modal-content">
            <div class="folder-picker-options">
              <button class="folder-picker-option" data-folder-id="root">
                <span class="folder-icon"></span>
                <span>Root (Current Location)</span>
              </button>
              <div id="folder-picker-list" class="folder-picker-list"></div>
            </div>
            <div class="modal-actions">
              <button class="btn btn-secondary" id="folder-picker-cancel">Cancel</button>
              <button class="btn btn-primary" id="folder-picker-confirm" disabled>Select</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Use safe HTML insertion with Trusted Types
    // Create a temporary container, set its innerHTML with Trusted Types, then append the modal
    const tempContainer = document.createElement("div");
    setInnerHTML(tempContainer, modalHTML);
    const modalElement = tempContainer.firstElementChild;
    if (modalElement) {
      document.body.appendChild(modalElement);
    }
    this.modal = document.getElementById("folder-picker-modal");

    // Setup root folder icon
    const rootFolderIcon = document.querySelector(
      ".folder-picker-option[data-folder-id='root'] .folder-icon",
    );
    if (rootFolderIcon && window.Icons && window.Icons.folder) {
      setInnerHTML(rootFolderIcon, window.Icons.folder(20, "currentColor"));
    }

    // Setup event listeners
    const closeBtn = document.getElementById("folder-picker-close");
    const cancelBtn = document.getElementById("folder-picker-cancel");
    const confirmBtn = document.getElementById("folder-picker-confirm");

    const closeHandler = () => {
      this.hide();
      // Resolve with undefined instead of rejecting - cancellation is not an error
      if (this.resolvePromise) {
        this.resolvePromise(undefined);
      }
      // Clear reject promise since we're resolving instead
      this.rejectPromise = null;
    };

    closeBtn.addEventListener("click", closeHandler);
    cancelBtn.addEventListener("click", closeHandler);
    this.modal.addEventListener("click", (e) => {
      if (e.target === this.modal) {
        closeHandler();
      }
    });

    confirmBtn.addEventListener("click", () => {
      this.hide();
      if (this.resolvePromise) {
        this.resolvePromise(this.selectedFolderId);
      }
      // Clear reject promise since we resolved
      this.rejectPromise = null;
    });

    // Handle escape key
    const escapeHandler = (e) => {
      if (e.key === "Escape" && !this.modal.classList.contains("hidden")) {
        closeHandler();
        document.removeEventListener("keydown", escapeHandler);
      }
    };
    document.addEventListener("keydown", escapeHandler);
  }

  /**
   * Render folders list
   */
  renderFolders() {
    const list = document.getElementById("folder-picker-list");
    if (!list) return;

    if (this.folders.length === 0) {
      setInnerHTML(
        list,
        '<p class="folder-picker-empty">No folders available</p>',
      );
      return;
    }

    const filteredFolders = this.folders.filter(
      (f) => f.id !== this.excludeFolderId,
    );

    if (filteredFolders.length === 0) {
      setInnerHTML(
        list,
        '<p class="folder-picker-empty">No other folders available</p>',
      );
      return;
    }

    const foldersHTML = filteredFolders
      .map((folder) => {
        const isSelected = this.selectedFolderId === folder.id;
        const folderIcon =
          window.Icons && window.Icons.folder
            ? window.Icons.folder(20, "currentColor")
            : "";
        return `
          <button class="folder-picker-option ${isSelected ? "selected" : ""}" 
                  data-folder-id="${folder.id}">
            <span class="folder-icon">${folderIcon}</span>
            <span>${this.escapeHtml(folder.original_name || folder.name)}</span>
          </button>
        `;
      })
      .join("");

    setInnerHTML(list, foldersHTML);

    // Add click handlers
    list.querySelectorAll(".folder-picker-option").forEach((btn) => {
      btn.addEventListener("click", () => {
        const folderId =
          btn.dataset.folderId === "root" ? null : btn.dataset.folderId;

        // Update selection
        list.querySelectorAll(".folder-picker-option").forEach((b) => {
          b.classList.remove("selected");
        });
        btn.classList.add("selected");
        this.selectedFolderId = folderId;

        // Enable confirm button
        const confirmBtn = document.getElementById("folder-picker-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = false;
        }
      });
    });

    // Handle root option
    const rootOption = this.modal.querySelector('[data-folder-id="root"]');
    if (rootOption) {
      rootOption.addEventListener("click", () => {
        this.modal.querySelectorAll(".folder-picker-option").forEach((b) => {
          b.classList.remove("selected");
        });
        rootOption.classList.add("selected");
        this.selectedFolderId = null;

        const confirmBtn = document.getElementById("folder-picker-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = false;
        }
      });
    }
  }

  /**
   * Hide modal
   */
  hide() {
    if (this.modal) {
      this.modal.classList.add("hidden");
      setTimeout(() => {
        if (this.modal && this.modal.parentNode) {
          this.modal.remove();
        }
      }, 300);
    }
  }

  /**
   * Escape HTML
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Export singleton instance
export const folderPicker = new FolderPicker();

// Make available globally for non-module scripts
if (typeof window !== "undefined") {
  window.folderPicker = folderPicker;
}
