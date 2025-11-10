/** @file selection.js - Multi-selection system for files and folders */

class SelectionManager {
  constructor() {
    this.selectedIds = new Set();
    this.lastSelectedIndex = -1;
    this.isShiftSelecting = false;
    this.isCtrlSelecting = false;

    this.init();
  }

  init() {
    // Listen for keyboard shortcuts
    document.addEventListener("keydown", (e) => {
      // Ctrl/Cmd + A to select all
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        e.preventDefault();
        this.selectAll();
      }

      // Escape to deselect all
      if (e.key === "Escape") {
        this.deselectAll();
      }

      // Delete key to delete selected
      if (e.key === "Delete" && this.selectedIds.size > 0) {
        this.handleDelete();
      }
    });

    // Update selection state on click
    document.addEventListener("click", (e) => {
      // Check if clicking outside selection area
      if (
        !e.target.closest(".file-card, .folder-card, .file-row, .folder-row")
      ) {
        if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
          this.deselectAll();
        }
      }
    });
  }

  /**
   * Select an item
   */
  select(id, multi = false) {
    if (!multi) {
      this.selectedIds.clear();
      this.lastSelectedIndex = -1;
    }

    this.selectedIds.add(id);
    this.updateUI();
  }

  /**
   * Deselect an item
   */
  deselect(id) {
    this.selectedIds.delete(id);
    this.updateUI();
  }

  /**
   * Toggle selection of an item
   */
  toggle(id, event) {
    this.isCtrlSelecting = event.ctrlKey || event.metaKey;
    this.isShiftSelecting = event.shiftKey;

    if (this.isShiftSelecting && this.lastSelectedIndex !== -1) {
      // Range selection
      this.selectRange(this.lastSelectedIndex, this.getIndexById(id));
    } else if (this.isCtrlSelecting) {
      // Multi-select
      if (this.selectedIds.has(id)) {
        this.deselect(id);
      } else {
        this.select(id, true);
      }
    } else {
      // Single select
      this.select(id, false);
    }

    this.lastSelectedIndex = this.getIndexById(id);
    this.updateUI();
  }

  /**
   * Select range of items
   */
  selectRange(startIndex, endIndex) {
    const items = this.getAllSelectableItems();
    const start = Math.min(startIndex, endIndex);
    const end = Math.max(startIndex, endIndex);

    for (let i = start; i <= end; i++) {
      if (items[i]) {
        const id =
          items[i].dataset.id ||
          items[i].dataset.fileId ||
          items[i].dataset.folderId;
        if (id) {
          this.selectedIds.add(id);
        }
      }
    }
  }

  /**
   * Get all selectable items
   */
  getAllSelectableItems() {
    const items = [];
    const cards = document.querySelectorAll(
      ".file-card, .folder-card, .file-row, .folder-row",
    );
    cards.forEach((card) => items.push(card));
    return items;
  }

  /**
   * Get index of item by ID
   */
  getIndexById(id) {
    const items = this.getAllSelectableItems();
    for (let i = 0; i < items.length; i++) {
      const itemId =
        items[i].dataset.id ||
        items[i].dataset.fileId ||
        items[i].dataset.folderId;
      if (itemId === id) {
        return i;
      }
    }
    return -1;
  }

  /**
   * Select all items
   */
  selectAll() {
    const items = this.getAllSelectableItems();
    items.forEach((item) => {
      const id =
        item.dataset.id || item.dataset.fileId || item.dataset.folderId;
      if (id) {
        this.selectedIds.add(id);
      }
    });
    this.updateUI();
  }

  /**
   * Deselect all items
   */
  deselectAll() {
    this.selectedIds.clear();
    this.lastSelectedIndex = -1;
    this.updateUI();
  }

  /**
   * Get selected IDs
   */
  getSelectedIds() {
    return Array.from(this.selectedIds);
  }

  /**
   * Get selected count
   */
  getSelectedCount() {
    return this.selectedIds.size;
  }

  /**
   * Check if item is selected
   */
  isSelected(id) {
    return this.selectedIds.has(id);
  }

  /**
   * Update UI to reflect selection state
   */
  updateUI() {
    // Update checkboxes/selection indicators
    const allItems = this.getAllSelectableItems();
    allItems.forEach((item) => {
      const id =
        item.dataset.id || item.dataset.fileId || item.dataset.folderId;
      if (id) {
        if (this.selectedIds.has(id)) {
          item.classList.add("selected");
          // Add checkbox if it doesn't exist
          if (!item.querySelector(".selection-checkbox")) {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "selection-checkbox";
            checkbox.checked = true;
            item.insertBefore(checkbox, item.firstChild);
          }
        } else {
          item.classList.remove("selected");
          const checkbox = item.querySelector(".selection-checkbox");
          if (checkbox) {
            checkbox.remove();
          }
        }
      }
    });

    // Update batch toolbar
    const batchToolbar = document.getElementById("batch-toolbar");
    const batchCount = document.getElementById("batch-count");

    if (this.selectedIds.size > 0) {
      if (batchToolbar) {
        batchToolbar.classList.remove("hidden");
        if (window.Animations) {
          window.Animations.fadeIn(batchToolbar);
        }
      }
      if (batchCount) {
        batchCount.textContent = `${this.selectedIds.size} selected`;
      }
    } else {
      if (batchToolbar) {
        if (window.Animations) {
          window.Animations.fadeOut(batchToolbar).then(() => {
            batchToolbar.classList.add("hidden");
          });
        } else {
          batchToolbar.classList.add("hidden");
        }
      }
    }
  }

  /**
   * Handle delete action
   */
  handleDelete() {
    if (this.selectedIds.size === 0) return;

    const count = this.selectedIds.size;
    const message = `Are you sure you want to delete ${count} item${count > 1 ? "s" : ""}?`;

    if (confirm(message)) {
      // Trigger delete for each selected item
      this.selectedIds.forEach((id) => {
        // Check if it's a file or folder
        const fileElement = document.querySelector(`[data-file-id="${id}"]`);
        const folderElement = document.querySelector(
          `[data-folder-id="${id}"]`,
        );

        if (fileElement) {
          // Delete file
          if (window.deleteFile) {
            window.deleteFile(id);
          }
        } else if (folderElement) {
          // Delete folder
          if (window.deleteFolder) {
            window.deleteFolder(id);
          }
        }
      });

      this.deselectAll();
    }
  }

  /**
   * Handle batch action
   */
  handleBatchAction(action) {
    const selectedIds = this.getSelectedIds();
    if (selectedIds.length === 0) return;

    switch (action) {
      case "download":
        this.handleDownload(selectedIds);
        break;
      case "share":
        this.handleShare(selectedIds);
        break;
      case "move":
        this.handleMove(selectedIds);
        break;
      case "star":
        this.handleStar(selectedIds);
        break;
      case "delete":
        this.handleDelete();
        break;
    }
  }

  /**
   * Handle download action
   */
  handleDownload(ids) {
    ids.forEach((id) => {
      const fileElement = document.querySelector(`[data-file-id="${id}"]`);
      if (fileElement && window.downloadFile) {
        window.downloadFile(id);
      }
    });
  }

  /**
   * Handle share action
   */
  handleShare(ids) {
    if (ids.length === 1) {
      // Single file share
      if (window.showShareModal) {
        window.showShareModal(ids[0]);
      }
    } else {
      // Multiple files - show message
      alert("Please select a single file to share");
    }
  }

  /**
   * Handle move action
   */
  handleMove(ids) {
    // TODO: Implement folder picker modal
    alert("Move functionality coming soon");
  }

  /**
   * Handle star action
   */
  handleStar(ids) {
    // TODO: Implement star/unstar
    alert("Star functionality coming soon");
  }
}

// Initialize selection manager
let selectionManager = null;

document.addEventListener("DOMContentLoaded", () => {
  selectionManager = new SelectionManager();

  // Setup batch action buttons
  const batchButtons = document.querySelectorAll(".batch-action-btn");
  batchButtons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const action = btn.dataset.action;
      if (action && selectionManager) {
        selectionManager.handleBatchAction(action);
      }
    });
  });

  // Export for use in other scripts
  if (typeof window !== "undefined") {
    window.SelectionManager = SelectionManager;
    window.selectionManager = selectionManager;
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.SelectionManager = SelectionManager;
}
