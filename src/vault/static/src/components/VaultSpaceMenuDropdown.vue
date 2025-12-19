<template>
  <teleport to="body">
    <div
      v-if="show"
      class="vaultspace-menu-container"
      ref="menuContainer"
      :style="menuStyle"
      @click.stop
    >
      <div class="vaultspace-menu-dropdown">
        <button
          v-for="option in menuOptions"
          :key="option.action"
          @click="handleOptionClick(option.action)"
          class="vaultspace-menu-item"
          :disabled="option.disabled"
        >
          <span
            class="vaultspace-menu-icon"
            v-html="getIcon(option.icon)"
          ></span>
          <span class="vaultspace-menu-label">{{ option.label }}</span>
        </button>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "VaultSpaceMenuDropdown",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    vaultspace: {
      type: Object,
      default: null,
    },
    isPinned: {
      type: Boolean,
      default: false,
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
      if (!this.vaultspace) return [];

      const options = [];

      options.push({
        action: this.isPinned ? "unpin" : "pin",
        label: this.isPinned ? "Unpin" : "Pin",
        icon: this.isPinned ? "unpin" : "pin",
        disabled: false,
      });

      options.push({
        action: "change-icon",
        label: "Change Icon",
        icon: "sparkles",
        disabled: false,
      });

      options.push({
        action: "rename",
        label: "Rename",
        icon: "edit",
        disabled: false,
      });

      options.push({
        action: "delete",
        label: "Delete",
        icon: "trash",
        disabled: false,
      });

      return options;
    },
  },
  watch: {
    show(newVal) {
      if (newVal) {
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
      this.$emit("action", action, this.vaultspace);
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
      const dropdown = container.querySelector(".vaultspace-menu-dropdown");
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
          ".vaultspace-menu-btn, .vaultspace-action-btn",
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
};
</script>

<style scoped>
.vaultspace-menu-container {
  position: fixed;
  z-index: 10000;
  top: 0;
  left: 0;
  pointer-events: auto;
}

.vaultspace-menu-dropdown {
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

.vaultspace-menu-item {
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

.vaultspace-menu-item:hover:not(:disabled) {
  background: #004225;
}

.vaultspace-menu-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.vaultspace-menu-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.vaultspace-menu-icon svg {
  width: 16px;
  height: 16px;
}

.vaultspace-menu-label {
  flex: 1;
}
</style>
