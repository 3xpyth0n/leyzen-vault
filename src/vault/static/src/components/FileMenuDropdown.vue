<template>
  <teleport to="body">
    <div
      v-if="show"
      class="file-menu-container"
      ref="menuContainer"
      :style="menuStyle"
      @click.stop
    >
      <div class="file-menu-dropdown">
        <button
          v-for="option in menuOptions"
          :key="option.action"
          @click="handleOptionClick(option.action)"
          class="file-menu-item"
          :disabled="option.disabled"
        >
          <span class="file-menu-icon" v-html="getIcon(option.icon)"></span>
          <span class="file-menu-label">{{ option.label }}</span>
        </button>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "FileMenuDropdown",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    item: {
      type: Object,
      default: null,
    },
    position: {
      type: Object,
      default: () => ({ x: 0, y: 0 }),
    },
  },
  emits: ["close", "action"],
  data() {
    return {
      clickOutsideHandler: null,
      escapeKeyHandler: null,
      scrollHandler: null,
      wheelHandler: null,
      touchMoveHandler: null,
      scrollableElements: [],
      menuTop: 0,
      menuLeft: 0,
    };
  },
  computed: {
    menuStyle() {
      return {
        top: `${this.menuTop}px`,
        left: `${this.menuLeft}px`,
      };
    },
    menuOptions() {
      if (!this.item) return [];

      const isFolder = this.item.mime_type === "application/x-directory";
      const isZipFile =
        this.item.mime_type === "application/zip" ||
        this.item.mime_type === "application/x-zip-compressed" ||
        (this.item.original_name &&
          this.item.original_name.toLowerCase().endsWith(".zip"));
      const options = [];

      if (!isFolder) {
        options.push({
          action: "preview",
          label: "Preview",
          icon: "eye",
          disabled: false,
        });
      }

      options.push({
        action: "rename",
        label: "Rename",
        icon: "edit",
        disabled: false,
      });

      options.push({
        action: "copy",
        label: "Copy",
        icon: "clipboard",
        disabled: false,
      });

      if (!isFolder) {
        options.push({
          action: "share",
          label: "Share",
          icon: "link",
          disabled: false,
        });
      }

      // Add ZIP-specific actions
      if (isFolder) {
        options.push({
          action: "zip-folder",
          label: "Zip Folder",
          icon: "zip",
          disabled: false,
        });
      }

      if (isZipFile) {
        options.push({
          action: "extract-zip",
          label: "Extract ZIP",
          icon: "folder",
          disabled: false,
        });
      }

      options.push({
        action: "star",
        label: this.item.is_starred ? "Unstar" : "Star",
        icon: "star",
        disabled: false,
      });

      if (!isFolder) {
        options.push({
          action: "download",
          label: "Download",
          icon: "download",
          disabled: false,
        });
      }

      options.push({
        action: "properties",
        label: "Properties",
        icon: "info",
        disabled: false,
      });

      options.push({
        action: "delete",
        label: "Delete",
        icon: "delete",
        disabled: false,
      });

      return options;
    },
  },
  watch: {
    show(newVal) {
      if (newVal) {
        // Position immediately with current coordinates
        this.positionMenu();
        this.$nextTick(() => {
          this.adjustPosition();
          this.setupClickOutside();
          this.setupEscapeKey();
          this.setupScroll();
        });
      } else {
        this.cleanup();
      }
    },
    position: {
      handler(newPosition) {
        if (this.show && newPosition) {
          // Update position immediately
          this.menuTop = newPosition.y || newPosition.top || 0;
          this.menuLeft = newPosition.x || newPosition.left || 0;
          this.$nextTick(() => {
            this.adjustPosition();
          });
        }
      },
      deep: true,
      immediate: true,
    },
  },
  beforeUnmount() {
    this.cleanup();
  },
  methods: {
    getIcon(iconName) {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      return window.Icons[iconName](16, "currentColor");
    },
    handleOptionClick(action) {
      this.$emit("action", action, this.item);
      this.closeMenu();
    },
    closeMenu() {
      this.$emit("close");
    },
    positionMenu() {
      // Position immediately at exact click point
      // Handle both x/y and top/left for compatibility
      this.menuTop = this.position.y || this.position.top || 0;
      this.menuLeft = this.position.x || this.position.left || 0;
    },
    adjustPosition() {
      if (!this.$refs.menuContainer) return;

      const container = this.$refs.menuContainer;
      const dropdown = container.querySelector(".file-menu-dropdown");
      if (!dropdown) return;

      const menuRect = dropdown.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let adjustedTop = this.menuTop;
      let adjustedLeft = this.menuLeft;

      // Adjust horizontally if necessary
      if (menuRect.right > viewportWidth - 10) {
        adjustedLeft = viewportWidth - menuRect.width - 10;
      }
      if (adjustedLeft < 10) {
        adjustedLeft = 10;
      }

      // Adjust vertically if necessary
      if (menuRect.bottom > viewportHeight - 10) {
        adjustedTop = viewportHeight - menuRect.height - 10;
      }
      if (adjustedTop < 10) {
        adjustedTop = 10;
      }

      // Apply adjustments
      this.menuTop = adjustedTop;
      this.menuLeft = adjustedLeft;
    },
    setupClickOutside() {
      // Clean up existing handler before creating a new one
      this.cleanupClickOutside();

      // Create a new handler
      this.clickOutsideHandler = (event) => {
        // Check that menu is still open
        if (!this.show) {
          this.cleanupClickOutside();
          return;
        }

        // Check if click is outside menu
        if (!this.$refs.menuContainer) {
          this.cleanupClickOutside();
          return;
        }

        const menuContainer = this.$refs.menuContainer;
        const clickedElement = event.target;

        // Check if click is inside menu
        if (menuContainer.contains(clickedElement)) {
          return;
        }

        // Check if it's a click on a menu button (3 dots) - don't close in this case
        const clickedButton = clickedElement.closest(
          ".btn-menu, .btn-menu-grid",
        );
        if (clickedButton) {
          return;
        }

        // Close menu for all other clicks (including sidebar, header, etc.)
        // This will catch clicks anywhere outside the menu, including:
        // - Sidebar
        // - Header
        // - Other parts of the page
        this.$emit("close");
      };

      // Attach listener with small delay to avoid immediate closure on open
      // Use capture phase to catch events before they bubble
      setTimeout(() => {
        if (this.show) {
          // Use both mousedown and click to catch all click events
          // Capture phase ensures we catch events even if they're stopped elsewhere
          document.addEventListener(
            "mousedown",
            this.clickOutsideHandler,
            true,
          );
          document.addEventListener("click", this.clickOutsideHandler, true);
          // Also listen on window to catch events that might not bubble to document
          window.addEventListener("mousedown", this.clickOutsideHandler, true);
          window.addEventListener("click", this.clickOutsideHandler, true);
        }
      }, 50);
    },
    setupEscapeKey() {
      // Clean up existing handler before creating a new one
      this.cleanupEscapeKey();

      // Create a new handler
      this.escapeKeyHandler = (event) => {
        if (event.key === "Escape" && this.show) {
          this.$emit("close");
        }
      };

      document.addEventListener("keydown", this.escapeKeyHandler);
    },
    cleanupClickOutside() {
      if (this.clickOutsideHandler) {
        document.removeEventListener(
          "mousedown",
          this.clickOutsideHandler,
          true,
        );
        document.removeEventListener("click", this.clickOutsideHandler, true);
        window.removeEventListener("mousedown", this.clickOutsideHandler, true);
        window.removeEventListener("click", this.clickOutsideHandler, true);
        this.clickOutsideHandler = null;
      }
    },
    cleanupEscapeKey() {
      if (this.escapeKeyHandler) {
        document.removeEventListener("keydown", this.escapeKeyHandler);
        this.escapeKeyHandler = null;
      }
    },
    setupScroll() {
      // Clean up existing handler before creating a new one
      this.cleanupScroll();

      // Create handlers that close the menu
      const closeMenuHandler = () => {
        if (this.show) {
          this.closeMenu();
        }
      };

      this.scrollHandler = closeMenuHandler;
      this.wheelHandler = closeMenuHandler;
      this.touchMoveHandler = closeMenuHandler;

      // Listen to scroll events on document and window (capture phase)
      document.addEventListener("scroll", this.scrollHandler, true);
      window.addEventListener("scroll", this.scrollHandler, true);

      // Also listen to wheel events (mouse wheel scrolling)
      document.addEventListener("wheel", this.wheelHandler, true);
      window.addEventListener("wheel", this.wheelHandler, true);

      // Listen to touchmove events (touch scrolling)
      document.addEventListener("touchmove", this.touchMoveHandler, true);
      window.addEventListener("touchmove", this.touchMoveHandler, true);

      // Listen on body as well
      if (document.body) {
        document.body.addEventListener("scroll", this.scrollHandler, true);
        document.body.addEventListener("wheel", this.wheelHandler, true);
        document.body.addEventListener(
          "touchmove",
          this.touchMoveHandler,
          true,
        );
      }

      // Also listen on all possible scrollable containers
      this.$nextTick(() => {
        // Find all scrollable elements
        const allElements = document.querySelectorAll("*");
        allElements.forEach((el) => {
          const style = window.getComputedStyle(el);
          if (
            style.overflow === "auto" ||
            style.overflow === "scroll" ||
            style.overflowY === "auto" ||
            style.overflowY === "scroll" ||
            style.overflowX === "auto" ||
            style.overflowX === "scroll"
          ) {
            el.addEventListener("scroll", this.scrollHandler, true);
            el.addEventListener("wheel", this.wheelHandler, true);
            el.addEventListener("touchmove", this.touchMoveHandler, true);
            this.scrollableElements.push(el);
          }
        });

        // Also listen on known container classes (including sidebar)
        const knownContainers = document.querySelectorAll(
          ".view-main, .files-list, .file-list-view, .grid-view, .list-view, .grid-container, .files-grid, main, aside, .sidebar, [class*='sidebar'], [class*='side-bar']",
        );
        knownContainers.forEach((container) => {
          if (!this.scrollableElements.includes(container)) {
            container.addEventListener("scroll", this.scrollHandler, true);
            container.addEventListener("wheel", this.wheelHandler, true);
            container.addEventListener(
              "touchmove",
              this.touchMoveHandler,
              true,
            );
            this.scrollableElements.push(container);
          }
        });

        // Also check for elements that might be scrollable but don't have explicit overflow styles
        // This includes elements with fixed heights and content that overflows
        const potentialScrollableElements = document.querySelectorAll(
          "div, section, article, aside, main",
        );
        potentialScrollableElements.forEach((el) => {
          // Skip if already added
          if (this.scrollableElements.includes(el)) {
            return;
          }

          // Check if element is actually scrollable
          const hasScrollableContent =
            el.scrollHeight > el.clientHeight ||
            el.scrollWidth > el.clientWidth;

          if (
            hasScrollableContent &&
            el !== document.body &&
            el !== document.documentElement
          ) {
            el.addEventListener("scroll", this.scrollHandler, true);
            el.addEventListener("wheel", this.wheelHandler, true);
            el.addEventListener("touchmove", this.touchMoveHandler, true);
            this.scrollableElements.push(el);
          }
        });
      });
    },
    cleanupScroll() {
      // Remove scroll handlers
      if (this.scrollHandler) {
        document.removeEventListener("scroll", this.scrollHandler, true);
        window.removeEventListener("scroll", this.scrollHandler, true);
        if (document.body) {
          document.body.removeEventListener("scroll", this.scrollHandler, true);
        }
        this.scrollHandler = null;
      }

      // Remove wheel handlers
      if (this.wheelHandler) {
        document.removeEventListener("wheel", this.wheelHandler, true);
        window.removeEventListener("wheel", this.wheelHandler, true);
        if (document.body) {
          document.body.removeEventListener("wheel", this.wheelHandler, true);
        }
        this.wheelHandler = null;
      }

      // Remove touchmove handlers
      if (this.touchMoveHandler) {
        document.removeEventListener("touchmove", this.touchMoveHandler, true);
        window.removeEventListener("touchmove", this.touchMoveHandler, true);
        if (document.body) {
          document.body.removeEventListener(
            "touchmove",
            this.touchMoveHandler,
            true,
          );
        }
        this.touchMoveHandler = null;
      }

      // Remove from all tracked scrollable elements
      this.scrollableElements.forEach((el) => {
        if (this.scrollHandler) {
          el.removeEventListener("scroll", this.scrollHandler, true);
        }
        if (this.wheelHandler) {
          el.removeEventListener("wheel", this.wheelHandler, true);
        }
        if (this.touchMoveHandler) {
          el.removeEventListener("touchmove", this.touchMoveHandler, true);
        }
      });
      this.scrollableElements = [];
    },
    cleanup() {
      this.cleanupClickOutside();
      this.cleanupEscapeKey();
      this.cleanupScroll();
    },
  },
};
</script>

<style scoped>
.file-menu-container {
  position: fixed;
  z-index: 10000;
  top: 0;
  left: 0;
  pointer-events: auto;
}

.file-menu-dropdown {
  position: relative;
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;

  padding: 0.5rem;
  min-width: 180px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  overflow: visible;
  margin: 0;
  isolation: isolate;
}

.file-menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: none;
  background: transparent;
  color: var(--text-primary, #a9b7aa);
  cursor: pointer;

  font-size: 0.9rem;
  transition: background-color 0.2s;
  text-align: left;
}

.file-menu-item:hover:not(:disabled) {
  background: #004225;
}

.file-menu-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-menu-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.file-menu-icon svg {
  width: 16px;
  height: 16px;
}

.file-menu-label {
  flex: 1;
}
</style>
