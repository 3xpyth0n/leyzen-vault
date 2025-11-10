<template>
  <teleport to="body">
    <div
      v-if="show"
      class="file-menu-container"
      ref="menuContainer"
      :style="menuStyle"
      @click.stop
    >
      <div class="file-menu-dropdown glass glass-card">
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
      const options = [];

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

      options.push({
        action: "move",
        label: "Move",
        icon: "folder",
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
        icon: "eye",
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
      // Clean up old handler first if it exists
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

        // Close menu for all other clicks
        this.$emit("close");
      };

      // Attach listener with small delay to avoid immediate closure on open
      setTimeout(() => {
        if (this.show) {
          document.addEventListener(
            "mousedown",
            this.clickOutsideHandler,
            true,
          );
          document.addEventListener("click", this.clickOutsideHandler, true);
        }
      }, 50);
    },
    setupEscapeKey() {
      // Clean up old handler first if it exists
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
        this.clickOutsideHandler = null;
      }
    },
    cleanupEscapeKey() {
      if (this.escapeKeyHandler) {
        document.removeEventListener("keydown", this.escapeKeyHandler);
        this.escapeKeyHandler = null;
      }
    },
    cleanup() {
      this.cleanupClickOutside();
      this.cleanupEscapeKey();
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
    rgba(30, 41, 59, 0.85),
    rgba(15, 23, 42, 0.8)
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  padding: 0.5rem;
  min-width: 180px;
  box-shadow:
    0 8px 32px rgba(2, 6, 23, 0.5),
    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
  overflow: visible;
  margin: 0;
}

.file-menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: none;
  background: transparent;
  color: var(--text-primary, #e6eef6);
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.9rem;
  transition: background-color 0.2s;
  text-align: left;
}

.file-menu-item:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.1);
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
