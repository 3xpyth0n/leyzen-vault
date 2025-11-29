<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <nav class="sidebar-nav">
        <button
          @click="$router.push('/dashboard')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/dashboard' }"
        >
          <Icon name="home" :size="20" class="sidebar-icon" />
          <span class="sidebar-label">Home</span>
        </button>
        <button
          @click="$router.push('/starred')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/starred' }"
        >
          <Icon name="star" :size="20" class="sidebar-icon" />
          <span class="sidebar-label">Starred</span>
        </button>
        <button
          @click="$router.push('/shared')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/shared' }"
        >
          <Icon name="link" :size="20" class="sidebar-icon" />
          <span class="sidebar-label">Shared</span>
        </button>
        <button
          @click="$router.push('/recent')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/recent' }"
        >
          <Icon name="clock" :size="20" class="sidebar-icon" />
          <span class="sidebar-label">Recent</span>
        </button>
        <button
          @click="$router.push('/trash')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/trash' }"
        >
          <Icon name="trash" :size="20" class="sidebar-icon" />
          <span class="sidebar-label">Trash</span>
        </button>

        <!-- Pinned VaultSpaces Section -->
        <div v-if="pinnedVaultSpaces.length > 0" class="pinned-section">
          <div class="pinned-section-header">
            <span v-if="!sidebarCollapsed" class="pinned-section-title"
              >Pinned</span
            >
            <span
              v-else
              class="pinned-section-icon"
              v-html="getIcon('pin', 20)"
            ></span>
          </div>
          <transition-group
            name="pinned-item"
            tag="div"
            class="pinned-items-container"
          >
            <button
              v-for="vaultspace in pinnedVaultSpaces"
              :key="vaultspace.id"
              @click="openVaultSpace(vaultspace.id)"
              class="sidebar-item pinned-item"
              :class="{
                'router-link-active':
                  $route.path === `/vaultspace/${vaultspace.id}`,
                'pinned-item-disintegrating': disintegratingPinnedItems.has(
                  vaultspace.id,
                ),
                'pinned-item-updating': updatingPinnedItems.has(vaultspace.id),
              }"
            >
              <span
                class="sidebar-icon pinned-icon"
                v-html="getIcon(vaultspace.icon_name || 'folder', 20)"
              ></span>
              <span class="sidebar-label">{{ vaultspace.name }}</span>
            </button>
          </transition-group>
        </div>
      </nav>
      <button
        @click="toggleSidebar"
        class="sidebar-toggle"
        :title="sidebarCollapsed ? 'Expand' : 'Collapse'"
      >
        <Icon name="chevron-left" :size="16" />
      </button>
    </aside>

    <!-- Main Content Area -->
    <div
      class="main-content"
      :class="{ 'sidebar-collapsed': sidebarCollapsed }"
    >
      <!-- Header -->
      <header class="app-header">
        <div class="header-left">
          <h1
            class="app-title"
            @click="$router.push('/dashboard')"
            style="cursor: pointer"
          >
            Leyzen Vault
          </h1>
          <p class="app-slogan">E2EE • Zero-Trust • Moving Target Defense</p>
        </div>
        <div class="header-right">
          <div class="header-actions">
            <router-link
              v-if="isAdmin"
              to="/admin"
              class="btn btn-admin"
              title="Admin Panel"
            >
              Admin
            </router-link>
            <router-link to="/account" class="btn btn-account"
              >Account</router-link
            >
            <button @click="handleLogout" class="btn btn-logout">Logout</button>
          </div>
        </div>
      </header>

      <!-- Page Content -->
      <main class="page-content">
        <slot />
      </main>
    </div>

    <!-- Logout Confirmation Modal -->
    <ConfirmationModal
      :show="showLogoutModal"
      title="Logout"
      message="Are you sure you want to logout?"
      confirm-text="Logout"
      :icon="logoutIcon"
      :dangerous="false"
      @confirm="performLogout"
      @close="showLogoutModal = false"
    />
  </div>
</template>

<script>
import Icon from "./Icon.vue";
import ConfirmationModal from "./ConfirmationModal.vue";
import { auth, account, vaultspaces } from "../services/api";

export default {
  name: "AppLayout",
  components: {
    Icon,
    ConfirmationModal,
  },
  emits: ["logout"],
  data() {
    return {
      sidebarCollapsed: false,
      showLogoutModal: false,
      isAdmin: false,
      loading: true,
      pinnedVaultSpaces: [],
      loadingPinned: false,
      pinnedVaultSpacesChangedHandler: null,
      vaultspaceUpdatedHandler: null,
      vaultspaceDeletedHandler: null,
      disintegratingPinnedItems: new Set(),
      updatingPinnedItems: new Set(),
    };
  },
  computed: {
    logoutIcon() {
      // Return logout icon as SVG string
      if (window.Icons && window.Icons.logout) {
        return window.Icons.logout(48, "#ef4444");
      }
      // Fallback SVG if Icons not available
      return `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
    },
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
    async loadPinnedVaultSpaces() {
      this.loadingPinned = true;
      try {
        this.pinnedVaultSpaces = await vaultspaces.listPinned();
      } catch (err) {
        console.error("Failed to load pinned VaultSpaces:", err);
        this.pinnedVaultSpaces = [];
      } finally {
        this.loadingPinned = false;
      }
    },
    refreshPinnedVaultSpaces() {
      // Force refresh pinned VaultSpaces
      this.loadPinnedVaultSpaces();
    },
    openVaultSpace(vaultspaceId) {
      this.$router.push(`/vaultspace/${vaultspaceId}`);
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      // Save preference to localStorage
      localStorage.setItem("sidebarCollapsed", this.sidebarCollapsed);
    },
    handleLogout(e) {
      // Prevent any default behavior
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }

      // Show logout confirmation modal
      this.showLogoutModal = true;
    },
    async performLogout() {
      try {
        // Clear service worker cache if available
        if (
          "serviceWorker" in navigator &&
          navigator.serviceWorker.controller
        ) {
          navigator.serviceWorker.controller.postMessage({
            type: "CLEAR_CACHE",
          });
        }

        await auth.logout();
        this.$router.push("/login");
        this.$emit("logout");
      } catch (error) {
        // Still redirect even if logout API call fails
        this.$router.push("/login");
        this.$emit("logout");
      }
    },
  },
  async mounted() {
    // Load sidebar state from localStorage
    const saved = localStorage.getItem("sidebarCollapsed");
    if (saved !== null) {
      this.sidebarCollapsed = saved === "true";
    }

    // Check if user is admin
    try {
      const accountInfo = await account.getAccount();
      this.isAdmin =
        accountInfo.global_role === "admin" ||
        accountInfo.global_role === "superadmin";
    } catch (err) {
      console.error("Failed to load account info:", err);
    } finally {
      this.loading = false;
    }

    // Load pinned VaultSpaces
    await this.loadPinnedVaultSpaces();

    // Listen for changes to pinned VaultSpaces via document event
    this.pinnedVaultSpacesChangedHandler = () => {
      this.refreshPinnedVaultSpaces();
    };
    document.addEventListener(
      "pinned-vaultspaces-changed",
      this.pinnedVaultSpacesChangedHandler,
    );

    // Listen for VaultSpace updates (rename, icon change)
    this.vaultspaceUpdatedHandler = (event) => {
      const { vaultspaceId, vaultspace } = event.detail;
      // Update the vaultspace in pinned list if it exists
      const index = this.pinnedVaultSpaces.findIndex(
        (vs) => vs.id === vaultspaceId,
      );
      if (index >= 0) {
        // Trigger update animation
        this.updatingPinnedItems.add(vaultspaceId);
        setTimeout(() => {
          this.updatingPinnedItems.delete(vaultspaceId);
        }, 300);

        // Replace the vaultspace object completely to trigger reactivity
        this.pinnedVaultSpaces.splice(index, 1, vaultspace);
      } else {
        // Refresh full list if vaultspace not found (may have been pinned in the meantime)
        this.refreshPinnedVaultSpaces();
      }
    };
    document.addEventListener(
      "vaultspace-updated",
      this.vaultspaceUpdatedHandler,
    );

    // Listen for VaultSpace deletion
    this.vaultspaceDeletedHandler = async (event) => {
      const { vaultspaceId } = event.detail;
      // Check if item is in pinned list
      const exists = this.pinnedVaultSpaces.some(
        (vs) => vs.id === vaultspaceId,
      );
      if (exists) {
        // Start disintegration animation
        this.disintegratingPinnedItems.add(vaultspaceId);

        // Wait for animation to complete (600ms)
        await new Promise((resolve) => setTimeout(resolve, 600));

        // Remove from pinned list after animation
        this.pinnedVaultSpaces = this.pinnedVaultSpaces.filter(
          (vs) => vs.id !== vaultspaceId,
        );

        // Clean up animation state
        this.disintegratingPinnedItems.delete(vaultspaceId);
      }
    };
    document.addEventListener(
      "vaultspace-deleted",
      this.vaultspaceDeletedHandler,
    );
  },
  beforeUnmount() {
    // Remove document event listeners
    if (this.pinnedVaultSpacesChangedHandler) {
      document.removeEventListener(
        "pinned-vaultspaces-changed",
        this.pinnedVaultSpacesChangedHandler,
      );
    }
    if (this.vaultspaceUpdatedHandler) {
      document.removeEventListener(
        "vaultspace-updated",
        this.vaultspaceUpdatedHandler,
      );
    }
    if (this.vaultspaceDeletedHandler) {
      document.removeEventListener(
        "vaultspace-deleted",
        this.vaultspaceDeletedHandler,
      );
    }
  },
};
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  position: relative;
}

/* Sidebar */
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  width: 250px;
  background: linear-gradient(
    180deg,
    rgba(30, 41, 59, 0.7),
    rgba(15, 23, 42, 0.6)
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0 1rem 1rem 0;
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15);
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
  overflow-y: auto;
  overflow-x: hidden;
  padding-top: 1.5rem;
  padding-bottom: 4rem;
  display: flex;
  flex-direction: column;
  visibility: visible;
  opacity: 1;
  will-change: width;
  contain: layout style paint;
}

/* Custom scrollbar for sidebar */
.sidebar::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.sidebar.collapsed {
  width: 70px !important;
  display: flex !important;
  flex-direction: column !important;
  visibility: visible !important;
  opacity: 1 !important;
  transform: none !important;
}

.sidebar-toggle {
  position: absolute;
  bottom: 1rem;
  right: 0.5rem;
  width: 2rem;
  height: 2rem;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: none;
  border-radius: 8px;
  color: #e6eef6;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition:
    background 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 101;
  visibility: visible;
  opacity: 1;
  will-change: transform, background;
  transform: rotate(0deg);
}

.sidebar.collapsed .sidebar-toggle {
  right: 0.5rem;
  left: auto;
  visibility: visible;
  opacity: 1;
  transform: rotate(180deg);
}

.sidebar-toggle:hover {
  background: rgba(255, 255, 255, 0.12);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 0 0.75rem;
  flex: 1;
}

.sidebar.collapsed .sidebar-nav {
  padding: 1.25rem 0.75rem;
  align-items: center;
  gap: 0.625rem;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 0.75rem;
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(10px);
  border: none;
  border-radius: 10px;
  color: #e6eef6;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 0.95rem;
  text-align: left;
  width: 100%;
  justify-content: flex-start;
  position: relative;
  z-index: 1;
  pointer-events: auto;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.sidebar.collapsed .sidebar-item {
  padding: 0.875rem;
  justify-content: center;
  align-items: center;
  width: 100%;
  gap: 0;
  min-height: 2.75rem;
}

.sidebar-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(88, 166, 255, 0.15);
}

.sidebar.collapsed .sidebar-item:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 16px rgba(88, 166, 255, 0.25);
}

.sidebar-item.router-link-active {
  background: linear-gradient(
    135deg,
    rgba(88, 166, 255, 0.2),
    rgba(56, 189, 248, 0.15)
  );
  box-shadow: 0 4px 16px rgba(88, 166, 255, 0.2);
  color: #60a5fa;
}

.sidebar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: currentColor;
  pointer-events: none;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  will-change: transform;
  width: 20px;
  height: 20px;
  margin: 0;
}

.sidebar-item:hover .sidebar-icon {
  transform: scale(1.15) rotate(5deg);
}

.sidebar.collapsed .sidebar-item:hover .sidebar-icon {
  transform: scale(1.2) rotate(0deg);
}

.sidebar-label {
  flex: 1;
  opacity: 1;
  transition:
    opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(0);
  will-change: opacity, transform;
}

.sidebar.collapsed .sidebar-label {
  display: none;
  width: 0;
  min-width: 0;
  overflow: hidden;
  pointer-events: none;
}

/* Pinned Section */
.pinned-section {
  margin-top: 0.25rem;
  padding-top: 0;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.pinned-section-header {
  padding: 0.25rem 0.75rem 0.75rem 0.25rem;
  margin-bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar.collapsed .pinned-section-header {
  padding: 0rem;
}

.pinned-section-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.pinned-section-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: #94a3b8;
}

.pinned-section-icon svg {
  width: 20px;
  height: 20px;
}

.pinned-items-container {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.pinned-item {
  padding-left: 0.75rem;
}

.pinned-icon {
  width: 20px;
  height: 20px;
}

.pinned-icon :deep(svg) {
  width: 20px;
  height: 20px;
  color: currentColor;
}

/* Pinned item animations */
@keyframes pinnedItemDisintegrate {
  0% {
    opacity: 1;
    filter: blur(0px);
    transform: translateX(0) scale(1);
  }
  50% {
    opacity: 0.5;
    filter: blur(2px);
    transform: translateX(-5px) scale(0.95);
  }
  100% {
    opacity: 0;
    filter: blur(8px);
    transform: translateX(-15px) scale(0.8);
  }
}

@keyframes pinnedItemFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.9) translateX(-10px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateX(0);
  }
}

@keyframes pinnedItemUpdate {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}

.pinned-item-disintegrating {
  animation: pinnedItemDisintegrate 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  pointer-events: none;
  will-change: opacity, transform, filter;
}

.pinned-item-updating {
  animation: pinnedItemUpdate 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  will-change: transform;
}

/* Transition group animations for pinned items */
.pinned-item-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.pinned-item-leave-active {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  position: absolute;
  width: 100%;
  z-index: 1;
}

.pinned-item-enter-from {
  opacity: 0;
  transform: scale(0.9) translateX(-10px);
}

.pinned-item-leave-to {
  opacity: 0;
  filter: blur(8px);
  transform: translateX(-15px) scale(0.8);
}

.pinned-item-move {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Main Content */
.main-content {
  flex: 1;
  margin-left: 250px;
  transition: margin-left 0.3s ease;
  display: flex;
  flex-direction: column;
}

.main-content.sidebar-collapsed {
  margin-left: 70px;
}

/* Header */
.app-header {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  border-top-left-radius: 0.75rem;
  padding: 1.5rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 20px rgba(2, 6, 23, 0.2);
  position: relative;
  z-index: 1;
}

/* Add a gradient overlay on the left edge of header to blend with sidebar */
.app-header::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 20px;
  background: linear-gradient(
    to right,
    rgba(30, 41, 59, 0.95),
    rgba(30, 41, 59, 0.5),
    transparent
  );
  pointer-events: none;
  border-top-left-radius: 0.75rem;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.app-title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: #e6eef6;
  transition: color 0.2s ease;
}

.app-title:hover {
  color: rgba(88, 166, 255, 0.8);
}

.app-slogan {
  margin: 0;
  font-size: 0.85rem;
  color: #94a3b8;
  font-weight: 400;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.btn-admin,
.btn-account,
.btn-logout {
  padding: 0.625rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  font-family: inherit;
}

.btn-admin {
  color: #38bdf8;
  border-color: rgba(56, 189, 248, 0.3);
}

.btn-admin:hover {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.5);
}

.btn-account {
  color: #e6eef6;
}

.btn-account:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(88, 166, 255, 0.3);
}

.btn-logout {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}

.btn-logout:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.5);
}

.page-content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

/* Responsive */
@media (max-width: 768px) {
  .sidebar {
    width: 70px;
  }

  .sidebar:not(.collapsed) {
    width: 250px;
  }

  .main-content {
    margin-left: 70px;
  }

  .main-content.sidebar-collapsed {
    margin-left: 70px;
  }

  .app-header {
    padding: 1rem;
  }

  .app-title {
    font-size: 1.5rem;
  }

  .app-slogan {
    font-size: 0.75rem;
  }
}
</style>
