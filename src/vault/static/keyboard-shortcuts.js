/** @file keyboard-shortcuts.js - Comprehensive keyboard shortcuts system */

class KeyboardShortcuts {
  constructor() {
    this.shortcuts = new Map();
    this.enabled = true;

    this.init();
  }

  init() {
    // Register default shortcuts
    this.registerDefaults();

    // Listen for keyboard events
    document.addEventListener("keydown", (e) => this.handleKeyDown(e));
  }

  /**
   * Register default shortcuts
   */
  registerDefaults() {
    // Navigation shortcuts
    this.register("ArrowUp", () => this.navigate("up"), "Navigate up");
    this.register("ArrowDown", () => this.navigate("down"), "Navigate down");
    this.register("ArrowLeft", () => this.navigate("left"), "Navigate left");
    this.register("ArrowRight", () => this.navigate("right"), "Navigate right");
    this.register(
      "Enter",
      () => this.activateSelection(),
      "Open selected item",
    );
    this.register("Backspace", () => this.goBack(), "Go back to parent folder");

    // Selection shortcuts
    this.register("a", () => this.selectAll(), "Select all", {
      ctrl: true,
      meta: true,
    });
    this.register("Escape", () => this.deselectAll(), "Deselect all");

    // Actions shortcuts
    this.register("c", () => this.copy(), "Copy", { ctrl: true, meta: true });
    this.register("x", () => this.cut(), "Cut", { ctrl: true, meta: true });
    this.register("v", () => this.paste(), "Paste", { ctrl: true, meta: true });
    this.register("Delete", () => this.delete(), "Delete selected");
    this.register("d", () => this.delete(), "Delete selected", {
      ctrl: true,
      meta: true,
    });
    this.register("n", () => this.newFolder(), "New folder", {
      ctrl: true,
      meta: true,
    });
    this.register("u", () => this.upload(), "Upload files", {
      ctrl: true,
      meta: true,
    });
    this.register("k", () => this.focusSearch(), "Focus search", {
      ctrl: true,
      meta: true,
    });

    // View shortcuts
    this.register("1", () => this.switchView("grid"), "Switch to grid view");
    this.register("2", () => this.switchView("list"), "Switch to list view");

    // Help shortcut
    this.register("?", () => this.showHelp(), "Show keyboard shortcuts");
    this.register("h", () => this.showHelp(), "Show help", {
      ctrl: true,
      meta: true,
    });
  }

  /**
   * Register a keyboard shortcut
   */
  register(key, handler, description, options = {}) {
    const shortcut = {
      key,
      handler,
      description,
      ctrl: options.ctrl || false,
      meta: options.meta || false,
      shift: options.shift || false,
      alt: options.alt || false,
    };

    const keyString = this.getKeyString(shortcut);
    this.shortcuts.set(keyString, shortcut);
  }

  /**
   * Get key string for shortcut
   */
  getKeyString(shortcut) {
    const parts = [];
    if (shortcut.ctrl) parts.push("Ctrl");
    if (shortcut.meta) parts.push("Meta");
    if (shortcut.shift) parts.push("Shift");
    if (shortcut.alt) parts.push("Alt");
    parts.push(shortcut.key);
    return parts.join("+");
  }

  /**
   * Handle key down event
   */
  handleKeyDown(e) {
    if (!this.enabled) return;

    // Don't trigger shortcuts when typing in inputs
    if (
      e.target.tagName === "INPUT" ||
      e.target.tagName === "TEXTAREA" ||
      e.target.isContentEditable
    ) {
      // Allow some shortcuts even in inputs
      if (e.key === "Escape") {
        e.target.blur();
      }
      return;
    }

    const keyString = this.getKeyString({
      key: e.key,
      ctrl: e.ctrlKey,
      meta: e.metaKey,
      shift: e.shiftKey,
      alt: e.altKey,
    });

    const shortcut = this.shortcuts.get(keyString);
    if (shortcut) {
      e.preventDefault();
      e.stopPropagation();
      shortcut.handler(e);
    }
  }

  /**
   * Navigate in file list
   */
  navigate(direction) {
    const items = this.getSelectableItems();
    if (items.length === 0) return;

    const selectedIndex = this.getSelectedIndex(items);
    let newIndex = selectedIndex;

    switch (direction) {
      case "up":
        newIndex = Math.max(0, selectedIndex - 1);
        break;
      case "down":
        newIndex = Math.min(items.length - 1, selectedIndex + 1);
        break;
      case "left":
        // Navigate to parent folder
        this.goBack();
        return;
      case "right":
        // Open selected folder
        if (items[selectedIndex]) {
          const folderId = items[selectedIndex].dataset.folderId;
          if (folderId && window.Folders && window.Folders.navigateToFolder) {
            window.Folders.navigateToFolder(folderId);
          }
        }
        return;
    }

    if (newIndex !== selectedIndex && items[newIndex]) {
      const id =
        items[newIndex].dataset.fileId || items[newIndex].dataset.folderId;
      if (id && window.selectionManager) {
        window.selectionManager.deselectAll();
        window.selectionManager.select(id);
        items[newIndex].scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  /**
   * Get selectable items
   */
  getSelectableItems() {
    return Array.from(
      document.querySelectorAll(
        ".file-card, .folder-card, .file-row, .folder-row",
      ),
    );
  }

  /**
   * Get selected index
   */
  getSelectedIndex(items) {
    for (let i = 0; i < items.length; i++) {
      if (items[i].classList.contains("selected")) {
        return i;
      }
    }
    return -1;
  }

  /**
   * Activate selected item
   */
  activateSelection() {
    const selected = document.querySelector(
      ".file-card.selected, .folder-card.selected, .file-row.selected, .folder-row.selected",
    );
    if (!selected) return;

    const fileId = selected.dataset.fileId;
    const folderId = selected.dataset.folderId;

    if (folderId && window.Folders && window.Folders.navigateToFolder) {
      window.Folders.navigateToFolder(folderId);
    } else if (fileId && window.showFilePreview) {
      const fileName =
        selected.querySelector(".file-name, .file-row-name")?.textContent || "";
      const mimeType = selected.dataset.mimeType || "";
      window.showFilePreview(fileId, fileName, mimeType);
    }
  }

  /**
   * Go back to parent folder
   */
  goBack() {
    if (window.Folders && window.Folders.navigateToParent) {
      window.Folders.navigateToParent();
    }
  }

  /**
   * Select all items
   */
  selectAll() {
    if (window.selectionManager) {
      window.selectionManager.selectAll();
    }
  }

  /**
   * Deselect all items
   */
  deselectAll() {
    if (window.selectionManager) {
      window.selectionManager.deselectAll();
    }
  }

  /**
   * Get item objects from selected IDs
   */
  async getSelectedItems() {
    if (!window.selectionManager) {
      return [];
    }

    const selectedIds = window.selectionManager.getSelectedIds();
    if (selectedIds.length === 0) {
      return [];
    }

    const items = [];
    const filesList = window.filesList || [];
    const foldersList = window.foldersList || [];

    for (const id of selectedIds) {
      // Try to find in filesList
      let item =
        filesList.find((f) => f.id === id || f.file_id === id) ||
        foldersList.find((f) => f.id === id || f.folder_id === id);

      // If not found in lists, try to get from DOM
      if (!item) {
        const fileElement = document.querySelector(
          `[data-file-id="${id}"], [data-id="${id}"]`,
        );
        const folderElement = document.querySelector(
          `[data-folder-id="${id}"], [data-id="${id}"]`,
        );

        if (fileElement) {
          item = {
            id: id,
            file_id: id,
            original_name:
              fileElement.dataset.name ||
              fileElement.querySelector(".file-name, .file-row-name")
                ?.textContent ||
              "Unknown",
            mime_type:
              fileElement.dataset.mimeType || "application/octet-stream",
            vaultspace_id:
              fileElement.dataset.vaultspaceId || window.currentVaultspaceId,
            parent_id: fileElement.dataset.parentId || null,
          };
        } else if (folderElement) {
          item = {
            id: id,
            folder_id: id,
            original_name:
              folderElement.dataset.name ||
              folderElement.querySelector(".folder-name, .folder-row-name")
                ?.textContent ||
              "Unknown",
            mime_type: "application/x-directory",
            vaultspace_id:
              folderElement.dataset.vaultspaceId || window.currentVaultspaceId,
            parent_id: folderElement.dataset.parentId || null,
          };
        }
      }

      if (item) {
        items.push(item);
      }
    }

    return items;
  }

  /**
   * Copy selected items
   */
  async copy() {
    if (!window.selectionManager) {
      return;
    }

    const selectedIds = window.selectionManager.getSelectedIds();
    if (selectedIds.length === 0) {
      if (window.Notifications) {
        window.Notifications.info("No items selected");
      }
      return;
    }

    try {
      // Get item objects
      const items = await this.getSelectedItems();
      if (items.length === 0) {
        if (window.Notifications) {
          window.Notifications.error("Could not find selected items");
        }
        return;
      }

      // Load clipboard manager
      let clipboardManager;
      try {
        const clipboardModule = await import(
          window.location.origin + "/static/src/utils/clipboard.js"
        );
        clipboardManager = clipboardModule.clipboardManager;
      } catch (e1) {
        try {
          const clipboardModule2 = await import("../src/utils/clipboard.js");
          clipboardManager = clipboardModule2.clipboardManager;
        } catch (e2) {
          console.error("Failed to load clipboard manager:", e1, e2);
          if (window.Notifications) {
            window.Notifications.error(
              "Clipboard manager not available. Please refresh the page.",
            );
          }
          return;
        }
      }

      // Copy to clipboard
      clipboardManager.copy(items);

      if (window.Notifications) {
        window.Notifications.success(
          `${items.length} item${items.length > 1 ? "s" : ""} copied`,
        );
      }
    } catch (error) {
      console.error("Copy error:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to copy: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  /**
   * Cut selected items
   */
  async cut() {
    if (!window.selectionManager) {
      return;
    }

    const selectedIds = window.selectionManager.getSelectedIds();
    if (selectedIds.length === 0) {
      if (window.Notifications) {
        window.Notifications.info("No items selected");
      }
      return;
    }

    try {
      // Get item objects
      const items = await this.getSelectedItems();
      if (items.length === 0) {
        if (window.Notifications) {
          window.Notifications.error("Could not find selected items");
        }
        return;
      }

      // Load clipboard manager
      let clipboardManager;
      try {
        const clipboardModule = await import(
          window.location.origin + "/static/src/utils/clipboard.js"
        );
        clipboardManager = clipboardModule.clipboardManager;
      } catch (e1) {
        try {
          const clipboardModule2 = await import("../src/utils/clipboard.js");
          clipboardManager = clipboardModule2.clipboardManager;
        } catch (e2) {
          console.error("Failed to load clipboard manager:", e1, e2);
          if (window.Notifications) {
            window.Notifications.error(
              "Clipboard manager not available. Please refresh the page.",
            );
          }
          return;
        }
      }

      // Cut to clipboard
      clipboardManager.cut(items);

      if (window.Notifications) {
        window.Notifications.success(
          `${items.length} item${items.length > 1 ? "s" : ""} cut`,
        );
      }
    } catch (error) {
      console.error("Cut error:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to cut: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  /**
   * Paste items
   */
  async paste() {
    try {
      // Load clipboard manager
      let clipboardManager;
      try {
        const clipboardModule = await import(
          window.location.origin + "/static/src/utils/clipboard.js"
        );
        clipboardManager = clipboardModule.clipboardManager;
      } catch (e1) {
        try {
          const clipboardModule2 = await import("../src/utils/clipboard.js");
          clipboardManager = clipboardModule2.clipboardManager;
        } catch (e2) {
          console.error("Failed to load clipboard manager:", e1, e2);
          if (window.Notifications) {
            window.Notifications.error(
              "Clipboard manager not available. Please refresh the page.",
            );
          }
          return;
        }
      }

      // Check if clipboard has items
      if (!clipboardManager.hasItems()) {
        if (window.Notifications) {
          window.Notifications.info("Clipboard is empty");
        }
        return;
      }

      const clipboardItems = clipboardManager.getItems();
      if (clipboardItems.length === 0) {
        if (window.Notifications) {
          window.Notifications.info("Clipboard is empty");
        }
        return;
      }

      // Get vaultspace ID
      const vaultspaceId =
        clipboardItems[0].vaultspaceId ||
        window.currentVaultspaceId ||
        (() => {
          const match = window.location.pathname.match(/\/vaultspace\/([^/]+)/);
          return match
            ? match[1]
            : localStorage.getItem("current_vaultspace_id");
        })();

      if (!vaultspaceId) {
        if (window.Notifications) {
          window.Notifications.error("Cannot paste: VaultSpace ID not found");
        }
        return;
      }

      // Load files API
      let files;
      try {
        const apiModule = await import(
          window.location.origin + "/static/src/services/api.js"
        );
        files = apiModule.files;
      } catch (e1) {
        try {
          const apiModule2 = await import("../src/services/api.js");
          files = apiModule2.files;
        } catch (e2) {
          console.error("Failed to load files API:", e1, e2);
          if (window.Notifications) {
            window.Notifications.error(
              "Files API not available. Please refresh the page.",
            );
          }
          return;
        }
      }

      // Load folder picker
      const folders = window.foldersList || [];
      const currentFolderId = window.currentFolderId || null;
      let folderPicker = window.folderPicker;
      if (!folderPicker) {
        try {
          const folderPickerModule = await import(
            window.location.origin + "/static/src/utils/FolderPicker.js"
          );
          folderPicker = folderPickerModule.folderPicker;
          window.folderPicker = folderPicker;
        } catch (e1) {
          try {
            const folderPickerModule2 = await import(
              "../src/utils/FolderPicker.js"
            );
            folderPicker = folderPickerModule2.folderPicker;
            window.folderPicker = folderPicker;
          } catch (e2) {
            console.error("Failed to load folder picker:", e1, e2);
            if (window.Notifications) {
              window.Notifications.error(
                "Folder picker not available. Please refresh the page.",
              );
            }
            return;
          }
        }
      }

      // Show folder picker to select destination
      const selectedFolderId = await folderPicker.show(
        folders,
        currentFolderId,
        vaultspaceId,
        null,
      );

      if (selectedFolderId === undefined) {
        // User cancelled
        return;
      }

      const isCut = clipboardManager.isCut();
      const itemIds = clipboardItems.map((item) => item.id);

      if (isCut) {
        // Move items
        await files.batchMove(itemIds, selectedFolderId || null);

        if (window.Notifications) {
          window.Notifications.success(
            `${clipboardItems.length} item${clipboardItems.length > 1 ? "s" : ""} moved`,
          );
        }

        // Clear clipboard after move
        clipboardManager.clear();
      } else {
        // Copy items
        const copyPromises = clipboardItems.map((item) =>
          files.copy(item.id, {
            newParentId: selectedFolderId || null,
          }),
        );
        await Promise.all(copyPromises);

        if (window.Notifications) {
          window.Notifications.success(
            `${clipboardItems.length} item${clipboardItems.length > 1 ? "s" : ""} copied`,
          );
        }
      }

      // Reload files
      if (window.loadFiles) {
        await window.loadFiles();
      } else if (window.Folders && window.Folders.loadFolderContents) {
        await window.Folders.loadFolderContents(
          selectedFolderId || currentFolderId,
        );
      } else {
        // Fallback: reload page
        window.location.reload();
      }
    } catch (error) {
      console.error("Paste error:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to paste: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  /**
   * Delete selected items
   */
  delete() {
    if (window.selectionManager) {
      window.selectionManager.handleDelete();
    }
  }

  /**
   * Create new folder
   */
  newFolder() {
    const btn = document.getElementById("new-folder-btn");
    if (btn) {
      btn.click();
    }
  }

  /**
   * Upload files
   */
  upload() {
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
      fileInput.click();
    }
  }

  /**
   * Focus search input
   */
  focusSearch() {
    const searchInput =
      document.getElementById("search-input") ||
      document.querySelector(".toolbar-search-input");
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }

  /**
   * Switch view mode
   */
  switchView(view) {
    if (view === "grid") {
      const btn = document.getElementById("view-grid-btn");
      if (btn) btn.click();
    } else if (view === "list") {
      const btn = document.getElementById("view-list-btn");
      if (btn) btn.click();
    }
  }

  /**
   * Show help modal
   */
  showHelp() {
    const shortcuts = Array.from(this.shortcuts.values());
    const shortcutsHTML = shortcuts
      .map((s) => {
        const keyString = this.getKeyString(s);
        return `
          <div class="shortcut-item">
            <div class="shortcut-keys">
              ${keyString
                .split("+")
                .map((k) => `<kbd>${k}</kbd>`)
                .join(" + ")}
            </div>
            <div class="shortcut-description">${s.description}</div>
          </div>
        `;
      })
      .join("");

    const modalHTML = `
      <div class="modal-overlay" id="shortcuts-modal" aria-hidden="false">
        <div class="modal-container">
          <div class="modal-content-confirm">
            <div class="modal-header">
              <h2 class="modal-title">Keyboard Shortcuts</h2>
              <button class="modal-close" onclick="document.getElementById('shortcuts-modal').remove()">&times;</button>
            </div>
            <div class="shortcuts-list">
              ${shortcutsHTML}
            </div>
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if any
    const existing = document.getElementById("shortcuts-modal");
    if (existing) existing.remove();

    // Create and show modal
    if (window.vaultHTMLPolicy) {
      try {
        document.body.insertAdjacentHTML(
          "beforeend",
          window.vaultHTMLPolicy.createHTML(modalHTML),
        );
      } catch (e) {
        document.body.insertAdjacentHTML("beforeend", modalHTML);
      }
    } else {
      document.body.insertAdjacentHTML("beforeend", modalHTML);
    }

    // Close on Escape
    const modal = document.getElementById("shortcuts-modal");
    if (modal) {
      modal.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          modal.remove();
        }
      });

      // Close on backdrop click
      const backdrop = modal.querySelector(".modal-overlay");
      if (backdrop) {
        backdrop.addEventListener("click", (e) => {
          if (e.target === backdrop) {
            modal.remove();
          }
        });
      }
    }
  }

  /**
   * Enable shortcuts
   */
  enable() {
    this.enabled = true;
  }

  /**
   * Disable shortcuts
   */
  disable() {
    this.enabled = false;
  }
}

// Initialize keyboard shortcuts
let keyboardShortcuts = null;

document.addEventListener("DOMContentLoaded", () => {
  keyboardShortcuts = new KeyboardShortcuts();

  // Export for use in other scripts
  if (typeof window !== "undefined") {
    window.KeyboardShortcuts = KeyboardShortcuts;
    window.keyboardShortcuts = keyboardShortcuts;
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.KeyboardShortcuts = KeyboardShortcuts;
}
