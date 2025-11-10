/** @file context-menu.js - Context menu for files and folders */

class ContextMenu {
  constructor() {
    this.menu = null;
    this.currentTarget = null;
  }

  init() {
    // Create context menu element
    if (!document.getElementById("context-menu")) {
      const menu = document.createElement("div");
      menu.id = "context-menu";
      menu.className = "context-menu hidden";
      document.body.appendChild(menu);
      this.menu = menu;
    } else {
      this.menu = document.getElementById("context-menu");
    }

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {
      if (
        !this.menu.contains(e.target) &&
        !e.target.closest("[data-context-target]")
      ) {
        this.hide();
      }
    });

    // Close menu on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !this.menu.classList.contains("hidden")) {
        this.hide();
      }
    });
  }

  show(event, target, type) {
    event.preventDefault();
    event.stopPropagation();

    this.currentTarget = target;
    const menuItems = this.getMenuItems(type);

    if (!this.menu) {
      this.init();
    }

    // Build menu HTML
    const menuHTML = menuItems
      .map((item) => {
        if (item === "divider") {
          return '<div class="context-menu-divider"></div>';
        }
        const icon = item.icon || "";
        const disabled = item.disabled ? "disabled" : "";
        return `
                <button class="context-menu-item ${disabled}" data-action="${item.action}" ${disabled}>
                    <span class="context-menu-icon">${icon}</span>
                    <span class="context-menu-label">${item.label}</span>
                </button>
            `;
      })
      .join("");

    // Use setInnerHTML if available
    if (window.vaultHTMLPolicy) {
      try {
        this.menu.innerHTML = window.vaultHTMLPolicy.createHTML(menuHTML);
      } catch (e) {
        this.menu.innerHTML = menuHTML;
      }
    } else {
      this.menu.innerHTML = menuHTML;
    }

    // Position menu
    const x = event.clientX;
    const y = event.clientY;
    this.menu.style.left = `${x}px`;
    this.menu.style.top = `${y}px`;

    // Ensure menu stays within viewport
    this.menu.classList.remove("hidden");
    const rect = this.menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      this.menu.style.left = `${window.innerWidth - rect.width - 10}px`;
    }
    if (rect.bottom > window.innerHeight) {
      this.menu.style.top = `${window.innerHeight - rect.height - 10}px`;
    }

    // Attach event listeners
    this.menu.querySelectorAll(".context-menu-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const action = item.getAttribute("data-action");
        this.handleAction(action, target, type);
        this.hide();
      });
    });
  }

  hide() {
    if (this.menu) {
      this.menu.classList.add("hidden");
      this.currentTarget = null;
    }
  }

  getMenuItems(type) {
    if (type === "file") {
      return [
        { icon: "⬇️", label: "Download", action: "download" },
        { icon: "👁️", label: "Preview", action: "preview" },
        { icon: "🔗", label: "Share", action: "share" },
        "divider",
        { icon: "✏️", label: "Rename", action: "rename" },
        { icon: "📋", label: "Properties", action: "properties" },
        "divider",
        { icon: "🗑️", label: "Delete", action: "delete", dangerous: true },
      ];
    } else if (type === "folder") {
      return [
        { icon: "📂", label: "Open", action: "open" },
        "divider",
        { icon: "✏️", label: "Rename", action: "rename" },
        { icon: "📋", label: "Properties", action: "properties" },
        "divider",
        { icon: "🗑️", label: "Delete", action: "delete", dangerous: true },
      ];
    }
    return [];
  }

  handleAction(action, target, type) {
    const id =
      target.getAttribute("data-file-id") ||
      target.getAttribute("data-folder-id");
    if (!id) return;

    switch (action) {
      case "download":
        if (type === "file" && window.downloadFile) {
          window.downloadFile(id);
        }
        break;
      case "preview":
        if (type === "file" && window.showFilePreview) {
          const file = window.filesList?.find((f) => f.file_id === id);
          if (file) {
            window.showFilePreview(id, file.original_name, file.mime_type);
          }
        }
        break;
      case "share":
        if (type === "file" && window.shareFile) {
          window.shareFile(id);
        }
        break;
      case "open":
        if (
          type === "folder" &&
          window.Folders &&
          window.Folders.navigateToFolder
        ) {
          window.Folders.navigateToFolder(id);
        }
        break;
      case "rename":
        // TODO: Implement rename functionality
        if (window.Notifications) {
          window.Notifications.info("Rename functionality coming soon");
        }
        break;
      case "properties":
        // TODO: Implement properties modal
        if (window.Notifications) {
          window.Notifications.info("Properties functionality coming soon");
        }
        break;
      case "delete":
        if (type === "file" && window.deleteFile) {
          window.deleteFile(id);
        } else if (
          type === "folder" &&
          window.Folders &&
          window.Folders.deleteFolder
        ) {
          window.Folders.deleteFolder(id);
        }
        break;
    }
  }
}

// Global context menu instance
let contextMenu = null;

function initContextMenu() {
  if (!contextMenu) {
    contextMenu = new ContextMenu();
    contextMenu.init();
  }
  return contextMenu;
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  initContextMenu();

  // Attach context menu to files and folders
  document.addEventListener("contextmenu", (e) => {
    const fileCard = e.target.closest(".file-card, .file-row");
    const folderCard = e.target.closest(".folder-card, .folder-row");

    if (fileCard) {
      e.preventDefault();
      contextMenu.show(e, fileCard, "file");
    } else if (folderCard) {
      e.preventDefault();
      contextMenu.show(e, folderCard, "folder");
    }
  });
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.ContextMenu = ContextMenu;
  window.initContextMenu = initContextMenu;
}
