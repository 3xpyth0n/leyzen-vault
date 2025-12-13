/** @file drag-drop.js - Advanced drag & drop system for files and folders */

// Helper function to safely set innerHTML with Trusted Types
function setInnerHTML(element, html) {
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  element.innerHTML = html;
}

class DragDropManager {
  constructor() {
    this.draggedElement = null;
    this.dragType = null; // 'file' or 'folder'
    this.dragData = null;
    this.dropTarget = null;
    this.dropOverlay = null;

    this.init();
  }

  init() {
    // Create drop overlay for visual feedback
    this.createDropOverlay();

    // Setup drag events for files and folders
    document.addEventListener("dragstart", (e) => this.handleDragStart(e));
    document.addEventListener("dragend", (e) => this.handleDragEnd(e));
    document.addEventListener("dragover", (e) => this.handleDragOver(e));
    document.addEventListener("dragleave", (e) => this.handleDragLeave(e));
    document.addEventListener("drop", (e) => this.handleDrop(e));

    // Setup drag events on file/folder cards
    this.setupDragListeners();
  }

  /**
   * Create drop overlay for visual feedback
   */
  createDropOverlay() {
    this.dropOverlay = document.createElement("div");
    this.dropOverlay.className = "drag-drop-overlay";
    const messageDiv = document.createElement("div");
    messageDiv.className = "drag-drop-message";
    const iconDiv = document.createElement("div");
    iconDiv.className = "drag-drop-icon";
    iconDiv.textContent = "📂";
    const textDiv = document.createElement("div");
    textDiv.className = "drag-drop-text";
    textDiv.textContent = "Drop here to move";
    messageDiv.appendChild(iconDiv);
    messageDiv.appendChild(textDiv);
    this.dropOverlay.appendChild(messageDiv);
    document.body.appendChild(this.dropOverlay);
  }

  /**
   * Setup drag listeners on file and folder cards
   */
  setupDragListeners() {
    // Use event delegation since elements are dynamically created
    document.addEventListener("mousedown", (e) => {
      const card = e.target.closest(
        ".file-card, .folder-card, .file-row, .folder-row",
      );
      if (
        card &&
        !e.target.closest(
          ".file-actions, .folder-actions, .file-row-actions, .folder-row-actions",
        )
      ) {
        card.draggable = true;
      }
    });
  }

  /**
   * Handle drag start
   */
  handleDragStart(e) {
    const card = e.target.closest(
      ".file-card, .folder-card, .file-row, .folder-row",
    );
    if (!card) return;

    // Don't start drag if clicking on actions
    if (
      e.target.closest(
        ".file-actions, .folder-actions, .file-row-actions, .folder-row-actions",
      )
    ) {
      e.preventDefault();
      return;
    }

    this.draggedElement = card;

    // Determine type and get data
    const fileId = card.dataset.fileId;
    const folderId = card.dataset.folderId;

    if (fileId) {
      this.dragType = "file";
      this.dragData = {
        id: fileId,
        type: "file",
      };
    } else if (folderId) {
      this.dragType = "folder";
      this.dragData = {
        id: folderId,
        type: "folder",
      };
    } else {
      // Not a draggable element
      e.preventDefault();
      return;
    }

    // Add visual feedback
    card.classList.add("dragging");

    // Set drag data
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/json", JSON.stringify(this.dragData));

    // Create custom drag image
    const dragImage = card.cloneNode(true);
    dragImage.style.position = "absolute";
    dragImage.style.top = "-1000px";
    dragImage.style.opacity = "0.8";
    dragImage.style.transform = "rotate(5deg)";
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, e.offsetX, e.offsetY);

    // Remove drag image after a short delay
    setTimeout(() => {
      document.body.removeChild(dragImage);
    }, 0);
  }

  /**
   * Handle drag end
   */
  handleDragEnd(e) {
    if (this.draggedElement) {
      this.draggedElement.classList.remove("dragging");
      this.draggedElement = null;
    }

    this.hideDropOverlay();
    this.clearDropTargets();
  }

  /**
   * Handle drag over
   */
  handleDragOver(e) {
    if (!this.dragData) return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    // Find drop target (folder card or folder row)
    const target = e.target.closest(".folder-card, .folder-row");
    const uploadArea = e.target.closest(".upload-area");
    const contentArea = e.target.closest(".content-area");

    if (target && this.dragType === "file") {
      // Can drop files into folders
      const folderId = target.dataset.folderId || target.dataset.id;
      if (folderId && folderId !== this.dragData.id) {
        this.setDropTarget(target, folderId);
      } else {
        this.clearDropTargets();
      }
    } else if (uploadArea && this.dragType === "file") {
      // Can drop files into upload area (for upload)
      this.clearDropTargets();
      // Upload area handles its own drag styling
    } else if (contentArea && this.dragType === "file") {
      // Can drop files into root (content area)
      this.setDropTarget(contentArea, null);
    } else {
      this.clearDropTargets();
    }
  }

  /**
   * Handle drag leave
   */
  handleDragLeave(e) {
    // Only clear if we're leaving the drop target completely
    const relatedTarget = e.relatedTarget;
    if (!relatedTarget || !relatedTarget.closest) {
      this.clearDropTargets();
      return;
    }

    const currentTarget = e.currentTarget;
    if (currentTarget && !currentTarget.contains(relatedTarget)) {
      this.clearDropTargets();
    }
  }

  /**
   * Handle drop
   */
  async handleDrop(e) {
    e.preventDefault();

    if (!this.dragData || !this.dropTarget) {
      this.clearDropTargets();
      return;
    }

    const targetFolderId =
      this.dropTarget.dataset.dropFolderId ||
      this.dropTarget.dataset.folderId ||
      null;

    // Don't drop on itself
    if (targetFolderId === this.dragData.id) {
      this.clearDropTargets();
      return;
    }

    try {
      if (this.dragType === "file") {
        await this.moveFile(this.dragData.id, targetFolderId);
      } else if (this.dragType === "folder") {
        await this.moveFolder(this.dragData.id, targetFolderId);
      }
    } catch (error) {
      if (window.Notifications) {
        window.Notifications.error(`Failed to move: ${error.message}`);
      }
    }

    this.clearDropTargets();
  }

  /**
   * Set drop target and show visual feedback
   */
  setDropTarget(element, folderId) {
    // Clear previous target
    this.clearDropTargets();

    this.dropTarget = element;
    element.dataset.dropFolderId = folderId || "";
    element.classList.add("drop-target");

    // Show overlay
    this.showDropOverlay(element);
  }

  /**
   * Clear drop targets
   */
  clearDropTargets() {
    if (this.dropTarget) {
      this.dropTarget.classList.remove("drop-target");
      delete this.dropTarget.dataset.dropFolderId;
      this.dropTarget = null;
    }

    this.hideDropOverlay();

    // Remove drop-target class from all elements
    document.querySelectorAll(".drop-target").forEach((el) => {
      el.classList.remove("drop-target");
    });
  }

  /**
   * Show drop overlay
   */
  showDropOverlay(element) {
    if (!this.dropOverlay) return;

    const rect = element.getBoundingClientRect();
    this.dropOverlay.style.display = "flex";
    this.dropOverlay.style.left = `${rect.left}px`;
    this.dropOverlay.style.top = `${rect.top}px`;
    this.dropOverlay.style.width = `${rect.width}px`;
    this.dropOverlay.style.height = `${rect.height}px`;
  }

  /**
   * Hide drop overlay
   */
  hideDropOverlay() {
    if (this.dropOverlay) {
      this.dropOverlay.style.display = "none";
    }
  }

  /**
   * Move file to folder
   */
  async moveFile(fileId, folderId) {
    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // Use the move endpoint with new_parent_id (API v2)
    const response = await fetch(`/api/v2/files/${fileId}/move`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        parent_id: folderId || null,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to move file");
    }

    // Reload files
    if (window.loadFiles) {
      await window.loadFiles();
    }

    // Reload folders if available
    if (window.Folders && window.Folders.loadFolderContents) {
      const currentFolderId = window.Folders.getCurrentFolderId();
      await window.Folders.loadFolderContents(currentFolderId);
    }

    if (window.Notifications) {
      window.Notifications.success("File moved successfully");
    }
  }

  /**
   * Move folder to parent folder
   */
  async moveFolder(folderId, parentId) {
    // CSRF token not needed - using JWT authentication

    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // Use the move endpoint with new_parent_id
    const response = await fetch(`/api/v2/files/${folderId}/move`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        new_parent_id: parentId || null,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to move folder");
    }

    // Reload folders
    if (window.Folders && window.Folders.loadFolderContents) {
      const currentFolderId = window.Folders.getCurrentFolderId();
      await window.Folders.loadFolderContents(currentFolderId);
    }

    if (window.Notifications) {
      window.Notifications.success("Folder moved successfully");
    }
  }
}

// Initialize drag & drop manager
let dragDropManager = null;

document.addEventListener("DOMContentLoaded", () => {
  dragDropManager = new DragDropManager();

  // Export for use in other scripts
  if (typeof window !== "undefined") {
    window.DragDropManager = DragDropManager;
    window.dragDropManager = dragDropManager;
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.DragDropManager = DragDropManager;
}
