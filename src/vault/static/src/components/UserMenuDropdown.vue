<template>
  <div class="user-menu-wrapper" ref="menuWrapper">
    <button
      class="user-menu-button"
      @click="toggleMenu"
      :aria-expanded="showMenu"
      aria-haspopup="true"
      aria-label="User menu"
    >
      <span class="user-menu-icon" v-html="getIcon('user', 20)"></span>
      <span
        class="user-menu-chevron"
        v-html="getIcon('chevron-down', 16)"
      ></span>
    </button>

    <teleport to="body">
      <transition name="menu-fade">
        <div
          v-if="showMenu"
          class="user-menu-dropdown"
          ref="menuDropdown"
          :style="menuStyle"
          @click.stop
        >
          <router-link to="/account" class="user-menu-item" @click="closeMenu">
            <span
              class="user-menu-item-icon"
              v-html="getIcon('user', 16)"
            ></span>
            <span class="user-menu-item-label">Account</span>
          </router-link>

          <router-link
            v-if="isAdmin"
            to="/admin"
            class="user-menu-item"
            @click="closeMenu"
          >
            <span
              class="user-menu-item-icon"
              v-html="getIcon('settings', 16)"
            ></span>
            <span class="user-menu-item-label">Admin</span>
          </router-link>

          <div class="user-menu-divider" v-if="isAdmin"></div>

          <button
            class="user-menu-item user-menu-item-logout"
            @click="handleLogoutClick"
          >
            <span
              class="user-menu-item-icon"
              v-html="getIcon('logout', 16)"
            ></span>
            <span class="user-menu-item-label">Logout</span>
          </button>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script>
export default {
  name: "UserMenuDropdown",
  props: {
    isAdmin: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["logout"],
  data() {
    return {
      showMenu: false,
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
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
    toggleMenu() {
      this.showMenu = !this.showMenu;
      if (this.showMenu) {
        this.$nextTick(() => {
          this.positionMenu();
          this.setupEventListeners();
        });
      } else {
        this.removeEventListeners();
      }
    },
    closeMenu() {
      this.showMenu = false;
      this.removeEventListeners();
    },
    positionMenu() {
      if (!this.$refs.menuWrapper || !this.$refs.menuDropdown) {
        return;
      }

      const buttonRect = this.$refs.menuWrapper.getBoundingClientRect();
      const menuRect = this.$refs.menuDropdown.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Position below the button, aligned to the right
      let left = buttonRect.right - menuRect.width;
      let top = buttonRect.bottom + 8;

      // Adjust if menu would go off-screen to the left
      if (left < 8) {
        left = 8;
      }

      // Adjust if menu would go off-screen to the right
      if (left + menuRect.width > viewportWidth - 8) {
        left = viewportWidth - menuRect.width - 8;
      }

      // Adjust if menu would go off-screen at the bottom
      if (top + menuRect.height > viewportHeight - 8) {
        // Position above the button instead
        top = buttonRect.top - menuRect.height - 8;
      }

      this.menuTop = top;
      this.menuLeft = left;
    },
    setupEventListeners() {
      // Click outside handler
      this.clickOutsideHandler = (e) => {
        if (
          this.$refs.menuWrapper &&
          !this.$refs.menuWrapper.contains(e.target) &&
          this.$refs.menuDropdown &&
          !this.$refs.menuDropdown.contains(e.target)
        ) {
          this.closeMenu();
        }
      };

      // Escape key handler
      this.escapeKeyHandler = (e) => {
        if (e.key === "Escape") {
          this.closeMenu();
        }
      };

      // Window resize handler
      this.resizeHandler = () => {
        if (this.showMenu) {
          this.positionMenu();
        }
      };

      // Scroll handler
      this.scrollHandler = () => {
        if (this.showMenu) {
          this.positionMenu();
        }
      };

      document.addEventListener("click", this.clickOutsideHandler, true);
      document.addEventListener("keydown", this.escapeKeyHandler);
      window.addEventListener("resize", this.resizeHandler);
      window.addEventListener("scroll", this.scrollHandler, true);
    },
    removeEventListeners() {
      if (this.clickOutsideHandler) {
        document.removeEventListener("click", this.clickOutsideHandler, true);
        this.clickOutsideHandler = null;
      }
      if (this.escapeKeyHandler) {
        document.removeEventListener("keydown", this.escapeKeyHandler);
        this.escapeKeyHandler = null;
      }
      if (this.resizeHandler) {
        window.removeEventListener("resize", this.resizeHandler);
        this.resizeHandler = null;
      }
      if (this.scrollHandler) {
        window.removeEventListener("scroll", this.scrollHandler, true);
        this.scrollHandler = null;
      }
    },
    handleLogoutClick() {
      this.closeMenu();
      this.$emit("logout");
    },
  },
  beforeUnmount() {
    this.removeEventListeners();
  },
};
</script>

<style scoped>
.user-menu-wrapper {
  position: relative;
  display: inline-block;
}

.user-menu-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: transparent;
  color: #e6eef6;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  font-size: 0.95rem;
}

.user-menu-button:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(88, 166, 255, 0.3);
}

.user-menu-button[aria-expanded="true"] {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(88, 166, 255, 0.5);
}

.user-menu-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.user-menu-chevron {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  transition: transform 0.2s ease;
}

.user-menu-button[aria-expanded="true"] .user-menu-chevron {
  transform: rotate(180deg);
}

.user-menu-dropdown {
  position: fixed;
  z-index: 1000;
  min-width: 180px;
  background: linear-gradient(140deg, #1e293b8c, #0f172a66);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.user-menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #e6eef6;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  font-size: 0.9rem;
  text-align: left;
  width: 100%;
}

.user-menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #60a5fa;
}

.user-menu-item.router-link-active {
  background: rgba(88, 166, 255, 0.15);
  color: #60a5fa;
}

.user-menu-item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.user-menu-item-label {
  flex: 1;
}

.user-menu-item-logout {
  color: #ef4444;
}

.user-menu-item-logout:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.user-menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0.25rem 0;
}

/* Transition animations */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.menu-fade-enter-from {
  opacity: 0;
  transform: translateY(-8px) scale(0.95);
}

.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.95);
}
</style>
