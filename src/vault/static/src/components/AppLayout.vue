<template>
  <div class="app-layout" :class="{ 'mobile-active': isMobileMode }">
    <!-- Header (Mobile Only) -->
    <header v-if="isMobileMode" class="app-header">
      <div class="header-left">
        <div class="app-title-wrapper">
          <img :src="faviconUrl" alt="Leyzen Vault" class="app-logo" />
          <h1
            class="app-title"
            @click="$router.push('/dashboard')"
            style="cursor: pointer"
          >
            Leyzen Vault
          </h1>
        </div>
        <p class="app-slogan">E2EE • Zero-Trust • Moving Target Defense</p>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <ServerStatusIndicator />
          <UserMenuDropdown
            :is-admin="isAdmin"
            :is-super-admin="isSuperAdmin"
            :orchestrator-enabled="orchestratorEnabled"
            @logout="handleLogout"
          />
        </div>
      </div>
    </header>

    <!-- Sidebar (hidden on mobile) -->
    <aside
      v-if="!isMobileMode"
      class="sidebar"
      :class="{ collapsed: isCollapsed }"
      :style="{ width: sidebarWidth + 'px' }"
    >
      <!-- Sidebar Header: Title -->
      <div class="sidebar-header">
        <div class="sidebar-title-section">
          <div class="app-title-wrapper">
            <transition name="title-fade" mode="out-in">
              <img
                v-if="isCollapsed"
                :src="faviconUrl"
                alt="Leyzen Vault"
                class="app-logo"
                key="logo"
              />
              <h1
                v-else
                class="app-title"
                @click="$router.push('/dashboard')"
                style="cursor: pointer"
                key="title"
              >
                Leyzen Vault
              </h1>
            </transition>
          </div>
        </div>
      </div>

      <!-- Resize Handle -->
      <div
        class="sidebar-resize-handle"
        @mousedown="startResize"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      ></div>

      <!-- Sidebar Navigation -->
      <nav class="sidebar-nav">
        <button
          @click="handleNavigation('/dashboard')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/dashboard' }"
          :disabled="isServerOffline"
        >
          <span v-html="getIcon('home', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Home</span>
        </button>
        <button
          @click="handleNavigation('/starred')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/starred' }"
          :disabled="isServerOffline"
        >
          <span v-html="getIcon('star', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Starred</span>
        </button>
        <button
          @click="handleNavigation('/shared')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/shared' }"
          :disabled="isServerOffline"
        >
          <span v-html="getIcon('link', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Shared</span>
        </button>
        <button
          @click="handleNavigation('/recent')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/recent' }"
          :disabled="isServerOffline"
        >
          <span v-html="getIcon('clock', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Recent</span>
        </button>
        <button
          @click="handleNavigation('/trash')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/trash' }"
          :disabled="isServerOffline"
        >
          <span v-html="getIcon('trash', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Trash</span>
        </button>

        <!-- Pinned VaultSpaces Section -->
        <div v-if="pinnedVaultSpaces.length > 0" class="pinned-section">
          <div class="pinned-section-header">
            <transition name="pinned-header-fade" mode="out-in">
              <span
                v-if="!isCollapsed"
                class="pinned-section-title"
                key="title"
              >
                Pinned
              </span>
              <span
                v-else
                class="pinned-section-icon"
                v-html="getIcon('pin', 20)"
                key="icon"
              ></span>
            </transition>
          </div>
          <transition-group
            name="pinned-item"
            tag="div"
            class="pinned-items-container"
          >
            <button
              v-for="(vaultspace, index) in pinnedVaultSpaces"
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
                dragging: draggedItemIndex === index,
                'drag-over': dragOverIndex === index,
                'drag-over-top':
                  dragOverIndex === index && dragOverPosition === 'top',
                'drag-over-bottom':
                  dragOverIndex === index && dragOverPosition === 'bottom',
              }"
              :disabled="isServerOffline"
              draggable="true"
              @dragstart="handleDragStart($event, index)"
              @dragend="handleDragEnd($event)"
              @dragover="handleDragOver($event, index)"
              @dragenter="handleDragEnter($event, index)"
              @dragleave="handleDragLeave($event, index)"
              @drop="handleDrop($event, index)"
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

      <!-- Sidebar Footer: Status + User Menu -->
      <div class="sidebar-footer">
        <ServerStatusIndicator />
        <UserMenuDropdown
          :is-admin="isAdmin"
          :is-super-admin="isSuperAdmin"
          :orchestrator-enabled="orchestratorEnabled"
          @logout="handleLogout"
        />
      </div>
    </aside>

    <!-- Main Content Area -->
    <div
      class="main-content"
      :class="{
        'mobile-active': isMobileMode,
      }"
      :style="{ marginLeft: sidebarWidth + 'px' }"
    >
      <!-- Page Content -->
      <main class="page-content">
        <transition name="page" mode="out-in">
          <div :key="$route.path" class="page-transition-wrapper">
            <slot />
          </div>
        </transition>
      </main>
    </div>

    <!-- Bottom Navigation (Mobile Only) -->
    <BottomNavigation v-if="isMobileMode" />

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

    <!-- Offline Modal -->
    <OfflineModal />
    <MaintenanceModal />
  </div>
</template>

<script>
import ConfirmationModal from "./ConfirmationModal.vue";
import ServerStatusIndicator from "./ServerStatusIndicator.vue";
import UserMenuDropdown from "./UserMenuDropdown.vue";
import BottomNavigation from "./BottomNavigation.vue";
import OfflineModal from "./OfflineModal.vue";
import MaintenanceModal from "./MaintenanceModal.vue";
import { auth, account, vaultspaces } from "../services/api";
import { isMobileMode as checkMobileMode } from "../utils/mobileMode";

export default {
  name: "AppLayout",
  components: {
    ConfirmationModal,
    ServerStatusIndicator,
    UserMenuDropdown,
    BottomNavigation,
    OfflineModal,
    MaintenanceModal,
  },
  emits: ["logout"],
  data() {
    return {
      sidebarWidth: 250,
      isResizing: false,
      showLogoutModal: false,
      isAdmin: false,
      isSuperAdmin: false,
      orchestratorEnabled: true, // Default to true for compatibility
      loading: true,
      pinnedVaultSpaces: [],
      loadingPinned: false,
      pinnedVaultSpacesChangedHandler: null,
      vaultspaceUpdatedHandler: null,
      vaultspaceDeletedHandler: null,
      disintegratingPinnedItems: new Set(),
      updatingPinnedItems: new Set(),
      draggedItemIndex: null,
      dragOverIndex: null,
      dragOverPosition: null, // 'top' or 'bottom'
      isMobileMode: false,
      mobileModeChangeHandler: null,
      resizeStartX: 0,
      resizeStartWidth: 0,
    };
  },
  computed: {
    faviconUrl() {
      // Construct URL at runtime to avoid Vite bundling
      // Using template literal to prevent static analysis
      const path = "/favicon";
      return `${path}.ico`;
    },
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
    isServerOffline() {
      // Check server status via global function
      if (typeof window !== "undefined" && window.getServerStatus) {
        return !window.getServerStatus();
      }
      return false; // Default to online if status not available
    },
    isCollapsed() {
      return this.sidebarWidth < 175;
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
    getPinnedOrderFromStorage() {
      try {
        const stored = localStorage.getItem("pinnedVaultSpacesOrder");
        if (stored) {
          return JSON.parse(stored);
        }
      } catch (err) {
        // Invalid JSON, ignore
      }
      return null;
    },
    savePinnedOrderToStorage(order) {
      try {
        localStorage.setItem("pinnedVaultSpacesOrder", JSON.stringify(order));
      } catch (err) {
        // Storage quota exceeded or other error, ignore
      }
    },
    sortVaultSpacesByOrder(vaultspaces, order) {
      if (!order || order.length === 0) {
        return vaultspaces;
      }
      // Create a map for quick lookup
      const vaultspaceMap = new Map(vaultspaces.map((vs) => [vs.id, vs]));
      // Sort by order array
      const sorted = [];
      const orderSet = new Set(order);
      // First, add items in the order specified
      for (const id of order) {
        if (vaultspaceMap.has(id)) {
          sorted.push(vaultspaceMap.get(id));
          vaultspaceMap.delete(id);
        }
      }
      // Then add any remaining items (newly pinned, not in localStorage)
      for (const vs of vaultspaceMap.values()) {
        sorted.push(vs);
      }
      return sorted;
    },
    async loadPinnedVaultSpaces() {
      this.loadingPinned = true;
      try {
        const pinnedList = await vaultspaces.listPinned();
        const storedOrder = this.getPinnedOrderFromStorage();

        if (storedOrder && storedOrder.length > 0) {
          // Use stored order to sort
          this.pinnedVaultSpaces = this.sortVaultSpacesByOrder(
            pinnedList,
            storedOrder,
          );
          // Update localStorage with current vaultspaces (in case some were removed)
          const currentIds = this.pinnedVaultSpaces.map((vs) => vs.id);
          this.savePinnedOrderToStorage(currentIds);
        } else {
          // No stored order, use API order and save it
          this.pinnedVaultSpaces = pinnedList;
          const order = pinnedList.map((vs) => vs.id);
          this.savePinnedOrderToStorage(order);
        }
      } catch (err) {
        this.pinnedVaultSpaces = [];
      } finally {
        this.loadingPinned = false;
      }
    },
    async loadOrchestratorEnabled() {
      try {
        // Use fetch with JWT token from localStorage
        const token = localStorage.getItem("jwt_token");
        const headers = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch("/api/v2/config", {
          method: "GET",
          credentials: "same-origin",
          headers,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.orchestrator_enabled !== undefined) {
            this.orchestratorEnabled = data.orchestrator_enabled === true;
          }
        }
      } catch (err) {
        // If API call fails, keep default value (true for compatibility)
      }
    },
    refreshPinnedVaultSpaces() {
      // Force refresh pinned VaultSpaces
      this.loadPinnedVaultSpaces();
    },
    handleDragStart(event, index) {
      this.draggedItemIndex = index;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/html", event.target.outerHTML);
      event.target.style.opacity = "0.5";
    },
    handleDragEnd(event) {
      event.target.style.opacity = "";
      this.draggedItemIndex = null;
      this.dragOverIndex = null;
      this.dragOverPosition = null;
    },
    handleDragOver(event, index) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      if (this.draggedItemIndex !== null && this.draggedItemIndex !== index) {
        this.dragOverIndex = index;
        // Determine if we're over the top or bottom half of the element
        const rect = event.currentTarget.getBoundingClientRect();
        const y = event.clientY - rect.top;
        this.dragOverPosition = y < rect.height / 2 ? "top" : "bottom";
      }
    },
    handleDragEnter(event, index) {
      event.preventDefault();
      if (this.draggedItemIndex !== null && this.draggedItemIndex !== index) {
        this.dragOverIndex = index;
        // Determine if we're over the top or bottom half of the element
        const rect = event.currentTarget.getBoundingClientRect();
        const y = event.clientY - rect.top;
        this.dragOverPosition = y < rect.height / 2 ? "top" : "bottom";
      }
    },
    handleDragLeave(event, index) {
      // Only clear dragOverIndex if we're actually leaving the container
      // Don't clear if we're moving to a sibling pinned item
      // Check if relatedTarget is another pinned item (sibling)
      let isMovingToSibling = false;
      if (event.relatedTarget && event.relatedTarget.closest) {
        const siblingPinnedItem = event.relatedTarget.closest(".pinned-item");
        isMovingToSibling =
          siblingPinnedItem !== null &&
          siblingPinnedItem !== event.currentTarget;
      }

      if (!isMovingToSibling) {
        // Only clear if this was the element we were hovering over
        if (this.dragOverIndex === index) {
          this.dragOverIndex = null;
          this.dragOverPosition = null;
        }
      }
    },
    async handleDrop(event, dropIndex) {
      event.preventDefault();
      event.stopPropagation();

      if (
        this.draggedItemIndex === null ||
        this.draggedItemIndex === dropIndex
      ) {
        this.dragOverIndex = null;
        this.dragOverPosition = null;
        return;
      }

      // Reorder the array
      const newOrder = [...this.pinnedVaultSpaces];
      const [draggedItem] = newOrder.splice(this.draggedItemIndex, 1);

      // Calculate the insertion index based on drop position
      // When we remove an element, all indices after it shift down by 1
      let insertIndex;
      const position = this.dragOverPosition || "top"; // Default to 'top' if not set

      if (this.draggedItemIndex < dropIndex) {
        // Dragging down: after removal, the drop target is now at (dropIndex - 1)
        if (position === "top") {
          // Insert before the drop target
          insertIndex = dropIndex - 1;
        } else {
          // Insert after the drop target
          insertIndex = dropIndex;
        }
      } else {
        // Dragging up: the drop target index doesn't change
        if (position === "top") {
          // Insert before the drop target
          insertIndex = dropIndex;
        } else {
          // Insert after the drop target
          insertIndex = dropIndex + 1;
        }
      }
      newOrder.splice(insertIndex, 0, draggedItem);

      // Clear drag state
      this.dragOverIndex = null;
      this.dragOverPosition = null;

      // Update local state immediately
      this.pinnedVaultSpaces = newOrder;

      // Save to localStorage immediately
      const order = newOrder.map((vs) => vs.id);
      this.savePinnedOrderToStorage(order);

      // Save to database in background
      try {
        await vaultspaces.updatePinnedOrder(order);
      } catch (err) {
        // If API call fails, keep localStorage order
        // It will be synced on next load
      }

      this.draggedItemIndex = null;
    },
    openVaultSpace(vaultspaceId) {
      // Block navigation if server is offline
      if (this.isServerOffline) {
        return;
      }
      this.$router.push(`/vaultspace/${vaultspaceId}`);
    },
    handleNavigation(path) {
      // Block navigation if server is offline
      if (this.isServerOffline) {
        return;
      }
      this.$router.push(path);
    },
    startResize(e) {
      this.isResizing = true;
      this.resizeStartX = e.clientX;
      this.resizeStartWidth = this.sidebarWidth;
      const sidebar = document.querySelector(".sidebar");
      if (sidebar) {
        sidebar.style.transition = "none";
      }
      document.addEventListener("mousemove", this.handleResize);
      document.addEventListener("mouseup", this.stopResize);
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      e.preventDefault();
    },
    handleResize(e) {
      if (!this.isResizing) return;
      const deltaX = e.clientX - this.resizeStartX;
      const newWidth = this.resizeStartWidth + deltaX;
      this.setSidebarWidth(newWidth);
    },
    stopResize() {
      this.isResizing = false;
      document.removeEventListener("mousemove", this.handleResize);
      document.removeEventListener("mouseup", this.stopResize);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      const sidebar = document.querySelector(".sidebar");
      if (sidebar) {
        sidebar.style.transition = "";
      }
    },
    setSidebarWidth(width) {
      const minWidth = 70;
      const maxWidth = 250;
      this.sidebarWidth = Math.max(minWidth, Math.min(maxWidth, width));
      localStorage.setItem("sidebarWidth", this.sidebarWidth);
      this.updateBodyClass();
    },
    updateBodyClass() {
      if (this.isCollapsed) {
        document.body.classList.add("sidebar-collapsed");
      } else {
        document.body.classList.remove("sidebar-collapsed");
      }
    },
    handleMouseEnter() {
      if (!this.isResizing) {
        document.body.style.cursor = "col-resize";
      }
    },
    handleMouseLeave() {
      if (!this.isResizing) {
        document.body.style.cursor = "";
      }
    },
    updateHeaderHeight() {
      this.$nextTick(() => {
        const header = document.querySelector(".app-header");
        if (header) {
          const height = header.offsetHeight;
          document.documentElement.style.setProperty(
            "--header-height",
            `${height}px`,
          );
        }
      });
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
      // Close modal first for smooth transition
      this.showLogoutModal = false;

      // Wait for modal to close before navigating
      await this.$nextTick();

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
        // Navigate to login page - use push to trigger Vue Router transition
        await this.$router.push("/login");
        this.$emit("logout");
      } catch (error) {
        // Still redirect even if logout API call fails
        await this.$router.push("/login");
        this.$emit("logout");
      }
    },
  },
  async mounted() {
    // Initialize mobile mode state
    this.isMobileMode = checkMobileMode();

    // Listen for mobile mode changes
    const handleMobileModeChange = (event) => {
      this.isMobileMode = event.detail?.mobileMode ?? checkMobileMode();
    };
    window.addEventListener("mobile-mode-changed", handleMobileModeChange);

    // Store handler for cleanup
    this.mobileModeChangeHandler = handleMobileModeChange;

    // Calculate and set header height for sidebar positioning
    this.$nextTick(() => {
      this.updateHeaderHeight();
      // Recalculate on resize
      window.addEventListener("resize", this.updateHeaderHeight);
      // Also recalculate when window loads to ensure accuracy
      window.addEventListener("load", this.updateHeaderHeight);
    });

    // Load sidebar width from localStorage
    const savedWidth = localStorage.getItem("sidebarWidth");
    if (savedWidth !== null) {
      const width = parseInt(savedWidth, 10);
      if (!isNaN(width) && width >= 70 && width <= 250) {
        this.sidebarWidth = width;
      }
    }
    // Update body class based on initial sidebar state
    this.updateBodyClass();

    // Check if user is admin or superadmin
    try {
      const accountInfo = await account.getAccount();
      this.isAdmin =
        accountInfo.global_role === "admin" ||
        accountInfo.global_role === "superadmin";
      this.isSuperAdmin = accountInfo.global_role === "superadmin";

      // Load orchestrator_enabled if user is admin/superadmin
      if (this.isAdmin || this.isSuperAdmin) {
        await this.loadOrchestratorEnabled();
      }
    } catch (err) {
      // Check if it's a network error (server offline, etc.)
      // Don't log as error if it's just a network issue
      const isNetworkErr =
        err?.message?.toLowerCase().includes("network") ||
        err?.message?.toLowerCase().includes("offline") ||
        err?.isOffline;
      if (isNetworkErr) {
      } else {
      }
      // Don't disconnect user - just leave isAdmin and isSuperAdmin as false
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
        // Update localStorage order
        const order = this.pinnedVaultSpaces.map((vs) => vs.id);
        this.savePinnedOrderToStorage(order);
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

        // Update localStorage order
        const order = this.pinnedVaultSpaces.map((vs) => vs.id);
        this.savePinnedOrderToStorage(order);

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
    // Clean up mobile mode change listener
    if (this.mobileModeChangeHandler) {
      window.removeEventListener(
        "mobile-mode-changed",
        this.mobileModeChangeHandler,
      );
    }
    // Clean up resize and load listeners
    window.removeEventListener("resize", this.updateHeaderHeight);
    window.removeEventListener("load", this.updateHeaderHeight);
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
    // Clean up body class
    document.body.classList.remove("sidebar-collapsed");
    // Clean up resize event listeners
    this.stopResize();
  },
};
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  position: relative;
}

/* Sidebar */
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  height: 100vh;
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
  transition: width 400ms cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 99;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  visibility: visible;
  opacity: 1;
  contain: layout style paint;
}

.mobile-mode .sidebar {
  display: none !important;
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
  display: flex !important;
  flex-direction: column !important;
  visibility: visible !important;
  opacity: 1 !important;
  transform: none !important;
}

/* Sidebar Header */
.sidebar-header {
  position: relative;
  padding: 0rem 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.sidebar-title-section {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
  width: 100%;
  overflow: hidden;
}

.sidebar-header .app-title-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  min-width: 0;
  width: 100%;
  overflow: hidden;
}

.sidebar.collapsed .sidebar-header .app-title-wrapper {
  justify-content: center;
  width: 100%;
  overflow: visible;
}

.sidebar-header .app-logo {
  height: 1.75rem;
  width: 1.75rem;
  object-fit: contain;
  flex-shrink: 0;
}

.sidebar-header .app-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  background: linear-gradient(120deg, #ba9cfff2, #9465ffe6, #6366f1f2);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  transition:
    background 0.3s ease,
    transform 0.2s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
}

.sidebar-header .app-title:hover {
  background: linear-gradient(120deg, #c5b0ffff, #a575ffff, #818cf8ff);
  -webkit-background-clip: text;
  background-clip: text;
  transform: scale(1.03);
}

.title-fade-enter-active,
.title-fade-leave-active {
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

.title-fade-enter-from {
  opacity: 0;
  transform: scale(0.9);
}

.title-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.sidebar.collapsed .sidebar-header {
  padding: 1.5rem 0.5rem 1rem 0.5rem;
}

.sidebar.collapsed .sidebar-title-section {
  align-items: center;
  justify-content: center;
  width: 100%;
  overflow: visible;
}

/* Resize Handle */
.sidebar-resize-handle {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: 101;
  background: transparent;
  transition: background 0.2s ease;
  user-select: none;
  -webkit-user-select: none;
}

.sidebar-resize-handle:hover {
  background: rgba(88, 166, 255, 0.3);
}

.sidebar-resize-handle:active {
  background: rgba(88, 166, 255, 0.5);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 1rem 0.75rem;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  transition: padding 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed .sidebar-nav {
  padding: 1rem 0.5rem;
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
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
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
  color: #8b5cf6;
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
    opacity 400ms cubic-bezier(0.4, 0, 0.2, 1),
    transform 400ms cubic-bezier(0.4, 0, 0.2, 1),
    max-width 400ms cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(0);
  will-change: opacity, transform, max-width;
  max-width: 200px;
}

.sidebar.collapsed .sidebar-label {
  opacity: 0;
  transform: translateX(-10px);
  max-width: 0;
  margin: 0;
  padding: 0;
  pointer-events: none;
}

.pinned-item .sidebar-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* Pinned Section */
.pinned-section {
  margin-top: 0.25rem;
  padding-top: 0;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  width: 100%;
  min-width: 0;
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

.pinned-header-fade-enter-active,
.pinned-header-fade-leave-active {
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

.pinned-header-fade-enter-from {
  opacity: 0;
  transform: scale(0.9);
}

.pinned-header-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.pinned-items-container {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  width: 100%;
}

.pinned-item {
  padding-left: 0.75rem;
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  flex-shrink: 0 !important;
}

.sidebar-item.pinned-item,
button.sidebar-item.pinned-item,
.sidebar .sidebar-item.pinned-item,
.sidebar-nav .sidebar-item.pinned-item,
.pinned-items-container .sidebar-item.pinned-item {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  flex-shrink: 0 !important;
  box-sizing: border-box !important;
}

.sidebar.collapsed .pinned-item,
.sidebar.collapsed .sidebar-item.pinned-item,
.sidebar.collapsed button.sidebar-item.pinned-item {
  padding: 0.875rem;
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
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
  width: 100% !important;
  box-sizing: border-box;
}

.pinned-item-leave-active {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  position: absolute;
  width: 100% !important;
  z-index: 1;
  box-sizing: border-box;
  min-width: 0 !important;
  max-width: 100% !important;
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

/* Drag and drop styles for pinned items */
.pinned-item.dragging {
  opacity: 0.5;
  cursor: grabbing;
}

.pinned-item.drag-over-top {
  border-top: 2px solid #3b82f6;
  margin-top: -2px;
}

.pinned-item.drag-over-bottom {
  border-bottom: 2px solid #3b82f6;
  margin-bottom: -2px;
}

.pinned-item[draggable="true"] {
  cursor: grab;
}

.pinned-item[draggable="true"]:active {
  cursor: grabbing;
}

/* Sidebar Footer */
.sidebar-footer {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0.75rem 1.5rem 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
  margin-top: auto;
}

.sidebar.collapsed .sidebar-footer {
  padding: 1rem 0.5rem 1.5rem 0.5rem;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.sidebar-footer :deep(.server-status-indicator) {
  flex: 1;
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  display: flex !important;
  justify-content: center;
  box-sizing: border-box;
}

.sidebar.collapsed .sidebar-footer :deep(.server-status-indicator) {
  flex: none;
  width: 100% !important;
  padding: 0.5rem;
  justify-content: center;
}

.sidebar.collapsed
  .sidebar-footer
  :deep(.server-status-indicator .status-text) {
  display: none;
}

.sidebar-footer :deep(.user-menu-wrapper) {
  flex: 1;
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  display: block !important;
  box-sizing: border-box;
}

.sidebar-footer :deep(.user-menu-button) {
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  justify-content: flex-start;
  box-sizing: border-box;
}

.sidebar.collapsed .sidebar-footer :deep(.user-menu-button) {
  width: 100% !important;
  padding: 0.625rem;
  min-width: 0;
  max-width: 100%;
  justify-content: center;
}

.sidebar.collapsed .sidebar-footer :deep(.user-menu-chevron) {
  display: none;
}

/* Main Content */
.main-content {
  flex: 1;
  padding-top: 0;
  transition: none;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.mobile-mode .main-content {
  margin-left: 0 !important;
  margin-top: 0 !important;
  padding-top: var(--header-height, 100px);
}

/* Header */
.app-header {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding: 1.5rem 2rem;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100; /* Above encryption overlay (50) but below dropdown (1000) */
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 20px rgba(2, 6, 23, 0.2);
  width: 100%;
  margin-left: 0;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.app-title-wrapper {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.app-logo {
  height: 1.75rem;
  width: 1.75rem;
  object-fit: contain;
  flex-shrink: 0;
}

.app-title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  background: linear-gradient(120deg, #ba9cfff2, #9465ffe6, #6366f1f2);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  transition:
    background 0.3s ease,
    transform 0.2s ease;
}

.app-title:hover {
  background: linear-gradient(120deg, #c5b0ffff, #a575ffff, #818cf8ff);
  -webkit-background-clip: text;
  background-clip: text;
  transform: scale(1.03);
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

.page-content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

.page-transition-wrapper {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.mobile-mode .page-content {
  padding-bottom: calc(2rem + 64px);
  padding: 1rem;
}

/* Mobile Mode Styles */
.mobile-mode .app-header {
  padding: 1rem;
}

.mobile-mode .app-title {
  font-size: 1.25rem;
  background: linear-gradient(120deg, #ba9cfff2, #9465ffe6, #6366f1f2);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.mobile-mode .app-slogan {
  font-size: 0.7rem;
  display: none;
}

.mobile-mode .header-left {
  flex: 1;
  min-width: 0;
}

.mobile-mode .header-right {
  flex-shrink: 0;
}

/* Responsive (viewport-based) */
/* Disabled state for buttons */
.sidebar-item:disabled,
.sidebar-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.sidebar-item:disabled:hover,
.sidebar-item.disabled:hover {
  background: rgba(255, 255, 255, 0.04);
  transform: none;
  box-shadow: none;
}

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

  .app-header {
    padding: 1rem;
  }

  .app-title {
    font-size: 1.5rem;
    background: linear-gradient(120deg, #ba9cfff2, #9465ffe6, #6366f1f2);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .app-slogan {
    font-size: 0.75rem;
  }
}
</style>
