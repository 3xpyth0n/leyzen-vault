<template>
  <teleport to="body">
    <transition name="menu-fade">
      <div
        v-if="show"
        class="bg-menu-container"
        ref="menuContainer"
        :style="menuStyle"
        @click.stop
      >
        <div class="bg-menu-dropdown">
          <button
            v-for="option in menuOptions"
            :key="option.action"
            @click="handleOptionClick(option.action)"
            class="bg-menu-item"
            :disabled="option.disabled"
          >
            <span class="bg-menu-icon" v-html="getIcon(option.icon)"></span>
            <span class="bg-menu-label">{{ option.label }}</span>
          </button>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script>
import { clipboardManager } from "../utils/clipboard";
export default {
  name: "BackgroundContextMenu",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    position: {
      type: Object,
      default: () => ({ x: 0, y: 0 }),
    },
    canShowProperties: {
      type: Boolean,
      default: false,
    },
    menuId: {
      type: String,
      default: null,
    },
  },
  emits: ["close", "action"],
  data() {
    return {
      internalMenuId:
        this.menuId ||
        `bg-context-menu-${Math.random().toString(36).substr(2, 9)}`,
      clickOutsideHandler: null,
      escapeKeyHandler: null,
      scrollHandler: null,
      wheelHandler: null,
      touchMoveHandler: null,
      scrollableElements: [],
      menuTop: 0,
      menuLeft: 0,
      hasClipboardItems: false,
      unsubscribeClipboard: null,
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
      const options = [];
      options.push({
        action: "paste",
        label: "Paste",
        icon: "clipboardPaste",
        disabled: !this.hasClipboardItems,
      });
      options.push({
        action: "new-folder",
        label: "New Folder",
        icon: "folderPlus",
        disabled: false,
      });
      options.push({
        action: "upload-file",
        label: "Upload File",
        icon: "upload",
        disabled: false,
      });
      options.push({
        action: "properties",
        label: "Properties",
        icon: "info",
        disabled: !this.canShowProperties,
      });
      return options;
    },
  },
  watch: {
    show(newVal) {
      if (newVal) {
        // Dispatch global event to close other menus
        window.dispatchEvent(
          new CustomEvent("close-all-menus", {
            detail: { origin: this.internalMenuId },
          }),
        );

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
  mounted() {
    window.addEventListener("close-all-menus", this.handleCloseAllMenus);
  },
  beforeUnmount() {
    window.removeEventListener("close-all-menus", this.handleCloseAllMenus);
    this.cleanup();
    if (this.unsubscribeClipboard) {
      this.unsubscribeClipboard();
      this.unsubscribeClipboard = null;
    }
  },
  methods: {
    handleCloseAllMenus(event) {
      // Ignore if event came from this component
      if (event?.detail?.origin === this.internalMenuId) return;

      if (this.show) {
        this.$emit("close");
      }
    },
    getIcon(iconName) {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      return window.Icons[iconName](16, "currentColor");
    },
    handleOptionClick(action) {
      this.$emit("action", action);
      this.closeMenu();
    },
    closeMenu() {
      this.$emit("close");
    },
    positionMenu() {
      this.menuTop = this.position.y || this.position.top || 0;
      this.menuLeft = this.position.x || this.position.left || 0;
    },
    adjustPosition() {
      if (!this.$refs.menuContainer) return;
      const container = this.$refs.menuContainer;
      const dropdown = container.querySelector(".bg-menu-dropdown");
      if (!dropdown) return;
      const menuRect = dropdown.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      let adjustedTop = this.menuTop;
      let adjustedLeft = this.menuLeft;
      if (menuRect.right > viewportWidth - 10) {
        adjustedLeft = viewportWidth - menuRect.width - 10;
      }
      if (adjustedLeft < 10) {
        adjustedLeft = 10;
      }
      if (menuRect.bottom > viewportHeight - 10) {
        adjustedTop = viewportHeight - menuRect.height - 10;
      }
      if (adjustedTop < 10) {
        adjustedTop = 10;
      }
      this.menuTop = adjustedTop;
      this.menuLeft = adjustedLeft;
    },
    setupClickOutside() {
      this.cleanupClickOutside();
      this.clickOutsideHandler = (event) => {
        if (!this.show) {
          this.cleanupClickOutside();
          return;
        }
        if (!this.$refs.menuContainer) {
          this.cleanupClickOutside();
          return;
        }
        const menuContainer = this.$refs.menuContainer;
        const clickedElement = event.target;
        if (menuContainer.contains(clickedElement)) {
          return;
        }
        const clickedButton = clickedElement.closest(
          ".btn-menu, .btn-menu-grid",
        );
        if (clickedButton) {
          return;
        }
        this.$emit("close");
      };
      setTimeout(() => {
        if (this.show) {
          document.addEventListener(
            "mousedown",
            this.clickOutsideHandler,
            true,
          );
          document.addEventListener("click", this.clickOutsideHandler, true);
          window.addEventListener("mousedown", this.clickOutsideHandler, true);
          window.addEventListener("click", this.clickOutsideHandler, true);
        }
      }, 50);
    },
    setupEscapeKey() {
      this.cleanupEscapeKey();
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
      this.cleanupScroll();
      const closeMenuHandler = () => {
        if (this.show) {
          this.closeMenu();
        }
      };
      this.scrollHandler = closeMenuHandler;
      this.wheelHandler = closeMenuHandler;
      this.touchMoveHandler = closeMenuHandler;
      document.addEventListener("scroll", this.scrollHandler, true);
      window.addEventListener("scroll", this.scrollHandler, true);
      document.addEventListener("wheel", this.wheelHandler, true);
      window.addEventListener("wheel", this.wheelHandler, true);
      document.addEventListener("touchmove", this.touchMoveHandler, true);
      window.addEventListener("touchmove", this.touchMoveHandler, true);
      if (document.body) {
        document.body.addEventListener("scroll", this.scrollHandler, true);
        document.body.addEventListener("wheel", this.wheelHandler, true);
        document.body.addEventListener(
          "touchmove",
          this.touchMoveHandler,
          true,
        );
      }
      this.$nextTick(() => {
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
      });
    },
    cleanupScroll() {
      if (this.scrollHandler) {
        document.removeEventListener("scroll", this.scrollHandler, true);
        window.removeEventListener("scroll", this.scrollHandler, true);
        if (document.body) {
          document.body.removeEventListener("scroll", this.scrollHandler, true);
        }
        this.scrollHandler = null;
      }
      if (this.wheelHandler) {
        document.removeEventListener("wheel", this.wheelHandler, true);
        window.removeEventListener("wheel", this.wheelHandler, true);
        if (document.body) {
          document.body.removeEventListener("wheel", this.wheelHandler, true);
        }
        this.wheelHandler = null;
      }
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
  created() {
    this.hasClipboardItems =
      clipboardManager && clipboardManager.hasItems
        ? clipboardManager.hasItems()
        : false;
    if (clipboardManager && clipboardManager.subscribe) {
      this.unsubscribeClipboard = clipboardManager.subscribe((items) => {
        this.hasClipboardItems = Array.isArray(items) && items.length > 0;
      });
    }
  },
};
</script>

<style scoped>
.bg-menu-container {
  position: fixed;
  z-index: 100002;
  top: 0;
  left: 0;
  pointer-events: auto;
}
.bg-menu-dropdown {
  position: relative;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey) !important;
  padding: 0.5rem;
  min-width: 180px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  overflow: visible;
  margin: 0;
  isolation: isolate;
}
.bg-menu-item {
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
.bg-menu-item:hover:not(:disabled) {
  background: #004225;
}
.bg-menu-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.bg-menu-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.bg-menu-icon svg {
  width: 16px;
  height: 16px;
}
.bg-menu-label {
  flex: 1;
}

/* Transition animations */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.95);
}
</style>
