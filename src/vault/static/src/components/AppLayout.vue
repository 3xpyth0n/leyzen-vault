<template>
  <div class="app-layout" :class="{ 'mobile-mode': isMobileMode }">
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
          <UserMenuDropdown @logout="handleLogout" />
        </div>
      </div>
    </header>

    <aside
      v-if="!isMobileMode"
      class="sidebar"
      :class="{ collapsed: isCollapsed }"
      @click="toggleSidebar"
    >
      <div class="sidebar-header">
        <div class="sidebar-title-section">
          <div class="app-title-wrapper">
            <Transition name="title-fade">
              <img
                v-if="isCollapsed"
                :src="faviconUrl"
                alt="Leyzen Vault"
                class="app-logo"
                key="logo"
              />
              <h1 v-else class="app-title" key="title">Leyzen Vault</h1>
            </Transition>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <button
          @click="handleNavigation('/dashboard')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/dashboard' }"
        >
          <span v-html="getIcon('home', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Home</span>
        </button>
        <button
          @click="handleNavigation('/starred')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/starred' }"
        >
          <span v-html="getIcon('star', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Starred</span>
        </button>
        <button
          @click="handleNavigation('/recent')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/recent' }"
        >
          <span v-html="getIcon('clock', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Recent</span>
        </button>
        <button
          @click="handleNavigation('/shared')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/shared' }"
        >
          <span v-html="getIcon('link', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Shared</span>
        </button>
        <button
          @click="handleNavigation('/trash')"
          class="sidebar-item"
          :class="{ 'router-link-active': $route.path === '/trash' }"
        >
          <span v-html="getIcon('trash', 20)" class="sidebar-icon"></span>
          <span class="sidebar-label">Trash</span>
        </button>

        <div v-if="pinnedVaultSpaces.length > 0" class="pinned-section">
          <div class="pinned-section-header">
            <Transition name="pinned-header-fade">
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
            </Transition>
          </div>
          <TransitionGroup
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
          </TransitionGroup>
        </div>
      </nav>

      <div class="sidebar-footer">
        <ServerStatusIndicator />
        <UserMenuDropdown
          @logout="handleLogout"
          @menu-open="handleMenuOpen"
          @menu-close="handleMenuClose"
        />
      </div>
    </aside>

    <div
      class="main-content"
      id="main-content-container"
      :class="{
        'mobile-mode': isMobileMode,
      }"
    >
      <div id="encryption-overlay-portal"></div>

      <main
        class="page-content"
        ref="pageContentRef"
        @scroll="updateScrollProgress"
        @contextmenu="handlePageContentContextMenu"
      >
        <Transition name="page">
          <div :key="$route.path" class="page-transition-wrapper">
            <slot />
          </div>
        </Transition>
      </main>

      <div v-if="!isMobileMode" class="scroll-progress-indicator">
        <svg class="progress-circle" viewBox="0 0 36 36">
          <circle
            class="progress-circle-bg"
            cx="18"
            cy="18"
            r="14"
            fill="none"
            stroke="var(--border-color)"
            stroke-width="2"
          />
          <circle
            class="progress-circle-fill"
            cx="18"
            cy="18"
            r="14"
            fill="none"
            stroke="var(--accent)"
            stroke-width="2"
            :stroke-dasharray="circumference"
            :stroke-dashoffset="
              circumference - (scrollProgress * circumference) / 100
            "
            transform="rotate(-90 18 18)"
          />
        </svg>

        <button
          v-if="scrollProgress > 0"
          class="scroll-to-top-button"
          @click="scrollToTop"
          aria-label="Scroll to top"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M12 19V5M5 12L12 5L19 12"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>

    <BottomNavigation v-if="isMobileMode" />

    <ConfirmationModal
      :show="showLogoutModal"
      title="Logout"
      message="Are you sure you want to logout?"
      confirm-text="Logout"
      :icon="logoutIcon"
      :dangerous="true"
      @confirm="performLogout"
      @close="showLogoutModal = false"
    />

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
import { vaultspaces } from "../services/api";
import { useAuthStore } from "../store/auth";
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
      showLogoutModal: false,
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
      sidebarExpanded: true,
      menuOpen: false,
      scrollProgress: 0,
      scrollResizeObserver: null,
    };
  },
  computed: {
    circumference() {
      return 2 * Math.PI * 14;
    },
    faviconUrl() {
      // Construct URL at runtime to avoid Vite bundling
      // Using template literal to prevent static analysis
      const path = "/favicon";
      return `${path}.ico`;
    },
    logoutIcon() {
      if (window.Icons && window.Icons.logout) {
        return window.Icons.logout(48, "#ef4444");
      }
      // Fallback SVG if Icons not available
      return `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
    },
    isCollapsed() {
      return !this.sidebarExpanded;
    },
    authStore() {
      return useAuthStore();
    },
    currentUser() {
      return this.authStore.user;
    },
    isAdmin() {
      const user = this.currentUser;
      if (!user) return false;
      const role = user.global_role || user.role;
      return role === "admin" || role === "superadmin";
    },
    isSuperAdmin() {
      const user = this.currentUser;
      if (!user) return false;
      const role = user.global_role || user.role;
      return role === "superadmin";
    },
  },
  watch: {
    $route() {
      window.dispatchEvent(new CustomEvent("close-all-menus"));
    },
    isMobileMode(newVal, oldVal) {
      if (oldVal === true && newVal === false) {
        this.sidebarExpanded = false;
      }
    },
    isCollapsed: {
      handler(newVal) {
        if (newVal) {
          document.body.classList.add("sidebar-collapsed");
        } else {
          document.body.classList.remove("sidebar-collapsed");
        }
      },
      immediate: true,
    },
    sidebarExpanded: {
      handler(newVal) {
        // Only save to localStorage if not in mobile mode
        if (!this.isMobileMode) {
          this.saveSidebarStateToStorage(newVal);
        }
      },
    },
  },
  methods: {
    updateScrollProgress() {
      if (!this.$refs.pageContentRef || this.isMobileMode) {
        return;
      }
      const pageContent = this.$refs.pageContentRef;
      const scrollHeight = pageContent.scrollHeight;
      const clientHeight = pageContent.clientHeight;
      const scrollTop = pageContent.scrollTop;

      if (scrollHeight <= clientHeight) {
        this.scrollProgress = 0;
        return;
      }

      const maxScroll = scrollHeight - clientHeight;
      this.scrollProgress = Math.min(
        100,
        Math.max(0, (scrollTop / maxScroll) * 100),
      );
    },
    handlePageContentContextMenu(event) {
      // Only handle if we are in VaultSpaceView
      if (this.$route.name !== "VaultSpaceView") {
        return;
      }

      const target = event.target;
      const isInteractive =
        target.closest("button") ||
        target.closest("a") ||
        target.closest("input") ||
        target.closest("textarea") ||
        target.closest(".interactive");

      if (isInteractive) {
        return;
      }

      event.preventDefault();

      // Dispatch custom event for VaultSpaceView to catch
      window.dispatchEvent(
        new CustomEvent("show-vault-background-menu", {
          detail: {
            x: event.clientX,
            y: event.clientY,
          },
        }),
      );
    },
    scrollToTop() {
      if (!this.$refs.pageContentRef) {
        return;
      }
      this.$refs.pageContentRef.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    },
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
    getSidebarStateFromStorage() {
      try {
        const stored = localStorage.getItem("vaultSidebarExpanded");
        if (stored !== null) {
          return JSON.parse(stored);
        }
      } catch (err) {
        // Invalid JSON, ignore
      }
      return null;
    },
    saveSidebarStateToStorage(expanded) {
      try {
        localStorage.setItem("vaultSidebarExpanded", JSON.stringify(expanded));
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
        await this.authStore.fetchAuthConfig();
      } catch (err) {}
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

      this.pinnedVaultSpaces = newOrder;

      // Save to localStorage immediately
      const order = newOrder.map((vs) => vs.id);
      this.savePinnedOrderToStorage(order);

      // Save to database in background
      try {
        await vaultspaces.updatePinnedOrder(order);
      } catch (err) {
        // It will be synced on next load
      }

      this.draggedItemIndex = null;
    },
    openVaultSpace(vaultspaceId) {
      this.$router.push(`/vaultspace/${vaultspaceId}`);
    },
    handleNavigation(path) {
      this.$router.push(path);
    },
    handleMenuOpen() {
      this.menuOpen = true;
    },
    handleMenuClose() {
      this.menuOpen = false;
    },
    toggleSidebar(event) {
      const target = event.target;
      const isInteractiveElement =
        target.closest("button") ||
        target.closest("a") ||
        target.closest(".sidebar-item") ||
        target.closest(".user-menu-wrapper") ||
        target.closest(".server-status-indicator") ||
        target.closest(".pinned-section");
      if (!isInteractiveElement) {
        this.sidebarExpanded = !this.sidebarExpanded;
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

      this.menuOpen = false;
      this.showLogoutModal = true;
    },
    async performLogout() {
      this.showLogoutModal = false;
      const authStore = useAuthStore();

      try {
        if (
          "serviceWorker" in navigator &&
          navigator.serviceWorker.controller
        ) {
          navigator.serviceWorker.controller.postMessage({
            type: "CLEAR_CACHE",
          });
        }

        await authStore.logout();
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
    this.isMobileMode = checkMobileMode();

    // Load sidebar state from localStorage (only if not in mobile mode)
    if (!this.isMobileMode) {
      const storedState = this.getSidebarStateFromStorage();
      if (storedState !== null) {
        this.sidebarExpanded = storedState;
      }
    }

    // Listen for mobile mode changes
    const handleMobileModeChange = (event) => {
      this.isMobileMode = event.detail?.mobileMode ?? checkMobileMode();
    };
    window.addEventListener("mobile-mode-changed", handleMobileModeChange);

    this.mobileModeChangeHandler = handleMobileModeChange;

    this.$nextTick(() => {
      this.updateHeaderHeight();
      window.addEventListener("resize", this.updateHeaderHeight);
      window.addEventListener("load", this.updateHeaderHeight);

      // Setup scroll progress indicator
      if (this.$refs.pageContentRef && !this.isMobileMode) {
        this.updateScrollProgress();

        const resizeObserver = new ResizeObserver(() => {
          this.updateScrollProgress();
        });
        resizeObserver.observe(this.$refs.pageContentRef);
        this.scrollResizeObserver = resizeObserver;
      }
    });

    try {
      const authStore = useAuthStore();
      await authStore.fetchCurrentUser();

      // Load orchestrator_enabled if user is admin/superadmin
      if (this.isAdmin || this.isSuperAdmin) {
        await this.loadOrchestratorEnabled();
      }
    } catch (err) {
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

      const exists = this.pinnedVaultSpaces.some(
        (vs) => vs.id === vaultspaceId,
      );
      if (exists) {
        // Start disintegration animation
        this.disintegratingPinnedItems.add(vaultspaceId);

        await new Promise((resolve) => setTimeout(resolve, 600));

        // Remove from pinned list after animation
        this.pinnedVaultSpaces = this.pinnedVaultSpaces.filter(
          (vs) => vs.id !== vaultspaceId,
        );

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

    if (this.scrollResizeObserver) {
      this.scrollResizeObserver.disconnect();
      this.scrollResizeObserver = null;
    }
    if (this.scrollResizeObserver) {
      this.scrollResizeObserver.disconnect();
      this.scrollResizeObserver = null;
    }

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
  },
};
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  position: relative;
  background: var(--bg-secondary);
}

/* Sidebar */
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  height: 100vh;
  width: 70px;
  min-width: 70px;
  max-width: 250px;
  background: var(--bg-secondary, #0a0a0a);
  border: none;
  transition: width 400ms cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex !important;
  flex-direction: column;
  visibility: visible !important;
  opacity: 1 !important;
}

/* Sidebar width controlled by collapsed class, not hover */
.sidebar:not(.collapsed) {
  width: 250px;
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
  background: #004225;
}

.sidebar::-webkit-scrollbar-thumb:hover {
  background: #004225;
}

.sidebar.collapsed {
  display: flex !important;
  flex-direction: column !important;
  visibility: visible !important;
  opacity: 1 !important;
  transform: none !important;
  width: 70px !important;
}

/* Sidebar Header */
.sidebar-header {
  position: relative;
  padding: 1rem 0.75rem 1rem;
  border-bottom: 1px solid var(--slate-grey);
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

.sidebar:not(.collapsed) .sidebar-header .app-title-wrapper {
  justify-content: center;
  gap: 0.75rem;
}

.sidebar-header .app-logo {
  height: 1.75rem;
  width: 1.75rem;
  object-fit: contain;
  flex-shrink: 0;
  cursor: pointer;
}

.sidebar-header .app-title {
  margin: 0;
  padding: 0;
  font-family: var(--font-family-branding);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.75rem;
  color: #a9b7aa;
  transition: color var(--transition-base);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.sidebar-header .app-title:hover {
  color: #a9b7aa;
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
  padding: 1rem 0.5rem 1rem 0.5rem;
}

.sidebar:not(.collapsed) .sidebar-header {
  padding: 0rem 0.5rem 1rem 0.5rem;
}

.sidebar.collapsed .sidebar-title-section {
  align-items: center;
  justify-content: center;
  width: 100%;
  overflow: visible;
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

.sidebar:not(.collapsed) .sidebar-nav {
  padding: 1rem 0.75rem;
  align-items: flex-start;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 0.75rem;
  background: transparent;
  border: none;
  color: #a9b7aa;
  text-decoration: none;
  cursor: pointer;
  transition:
    background var(--transition-base),
    color var(--transition-base);
  font-size: 0.95rem;
  text-align: left;
  width: 100%;
  justify-content: flex-start;
  position: relative;
  z-index: 1;
  pointer-events: auto;
}

.sidebar.collapsed .sidebar-item {
  padding: 0.875rem;
  justify-content: center;
  align-items: center;
  width: 100%;
  gap: 0;
  min-height: 2.75rem;
}

.sidebar:not(.collapsed) .sidebar-item {
  padding: 0.875rem 0.75rem;
  justify-content: flex-start;
  gap: 0.75rem;
}

.sidebar-item:hover {
  color: #a9b7aa;
  background: rgba(0, 66, 37, 0.1);
}

.sidebar.collapsed .sidebar-item:hover {
  color: #a9b7aa;
  background: rgba(0, 66, 37, 0.1);
}

.sidebar-item.router-link-active {
  background: rgba(0, 66, 37, 0.2);
  border-radius: 0.5rem;
}

.sidebar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--slate-grey);
  pointer-events: none;
  width: 20px;
  height: 20px;
  margin: 0;
}

.sidebar-item:hover .sidebar-icon {
  color: var(--slate-grey);
}

.sidebar.collapsed .sidebar-item:hover .sidebar-icon {
  color: var(--slate-grey);
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

.sidebar:not(.collapsed) .sidebar-label {
  opacity: 1;
  transform: translateX(0);
  max-width: 200px;
  margin: 0;
  padding: 0;
  pointer-events: auto;
}

.pinned-item .sidebar-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* Pinned Section */
.pinned-section {
  position: relative;
  margin-top: 0.5rem;
  padding: 0.75rem 0.5rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  width: 100%;
  min-width: 0;
  border: 1px solid var(--accent);
}

.pinned-section-header {
  position: absolute;
  top: -0.5rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0;
  margin-bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  pointer-events: none;
}

.sidebar.collapsed .pinned-section-header {
  padding: 0;
}

.sidebar:not(.collapsed) .pinned-section-header {
  padding: 0;
}

.pinned-section-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #a9b7aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--bg-secondary);
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.pinned-section-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: 20px;
  height: 20px;
  color: #a9b7aa;
  background: var(--bg-secondary);
  padding-left: 0.25rem;
  padding-right: 0.25rem;
  pointer-events: auto;
}

.pinned-section-icon svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: inherit;
  stroke: currentColor;
}

.sidebar.collapsed .pinned-section-icon {
  width: auto;
  min-width: 20px;
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
  gap: 0;
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

.sidebar:not(.collapsed) .pinned-item,
.sidebar:not(.collapsed) .sidebar-item.pinned-item,
.sidebar:not(.collapsed) button.sidebar-item.pinned-item {
  padding: 0.875rem 0.75rem;
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
  border-top: 2px solid #004225;
  margin-top: -2px;
}

.pinned-item.drag-over-bottom {
  border-bottom: 2px solid #004225;
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
  border-top: 1px solid var(--slate-grey);
  flex-shrink: 0;
  margin-top: auto;
  justify-content: space-between;
  position: relative;
}

.sidebar.collapsed .sidebar-footer {
  padding: 1rem 0.5rem 1.5rem 0.5rem;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.sidebar:not(.collapsed) .sidebar-footer,
.sidebar.menu-open .sidebar-footer {
  padding: 1rem 0.75rem 1.5rem 0.75rem;
  flex-direction: row-reverse;
  align-items: center;
  gap: 0.75rem;
  justify-content: space-between;
  transition:
    padding 400ms cubic-bezier(0.4, 0, 0.2, 1),
    gap 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-footer :deep(.server-status-indicator) {
  flex: 0 0 auto;
  width: auto !important;
  min-width: 0;
  max-width: 60%;
  display: flex !important;
  justify-content: center;
  box-sizing: border-box;
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(0) translateY(0);
  position: relative;
}

.sidebar:not(.collapsed) .sidebar-footer :deep(.server-status-indicator),
.sidebar.menu-open .sidebar-footer :deep(.server-status-indicator) {
  flex: 0 0 auto;
  width: auto !important;
  max-width: 60%;
  min-width: 0;
  transform: translateY(0) translateX(0);
  position: relative;
  top: 0;
  left: 0;
}

.sidebar.collapsed .sidebar-footer :deep(.server-status-indicator) {
  flex: none;
  width: 100% !important;
  padding: 0.5rem;
  justify-content: center;
  transform: translateY(0) translateX(0);
  position: relative;
  top: 0;
  left: 0;
}

.sidebar.collapsed
  .sidebar-footer
  :deep(.server-status-indicator .status-text) {
  display: none;
}

.sidebar:not(.collapsed)
  .sidebar-footer
  :deep(.server-status-indicator .status-text),
.sidebar.menu-open
  .sidebar-footer
  :deep(.server-status-indicator .status-text) {
  display: block;
}

.sidebar-footer :deep(.user-menu-wrapper) {
  flex: 1 1 auto;
  width: auto !important;
  min-width: 0;
  max-width: none;
  display: block !important;
  box-sizing: border-box;
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(0) translateY(0);
  position: relative;
}

.sidebar:not(.collapsed) .sidebar-footer :deep(.user-menu-wrapper),
.sidebar.menu-open .sidebar-footer :deep(.user-menu-wrapper) {
  flex: 1 1 auto;
  width: auto !important;
  min-width: 0;
  max-width: none;
}

.sidebar-footer :deep(.user-menu-button) {
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  justify-content: flex-start;
  box-sizing: border-box;
}

.sidebar:not(.collapsed) .sidebar-footer :deep(.user-menu-button),
.sidebar.menu-open .sidebar-footer :deep(.user-menu-button) {
  width: auto !important;
  min-width: 0;
  max-width: none;
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

.sidebar.collapsed .sidebar-footer :deep(.user-menu-wrapper) {
  transform: translateX(0) translateY(0);
  position: relative;
  top: 0;
  left: 0;
}

.sidebar:not(.collapsed) .sidebar-footer :deep(.user-menu-chevron),
.sidebar.menu-open .sidebar-footer :deep(.user-menu-chevron) {
  display: block;
}

/* Main Content */
.main-content {
  flex: 1;
  padding-top: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  /* CSS Variables for layout offsets */
  --header-offset: 0px;
  --bottom-nav-offset: 0px;
  --content-padding: 2rem;
}

.main-content:not(.mobile-mode) {
  position: fixed;
  top: 1rem;
  right: 1rem;
  bottom: 1rem;
  left: calc(250px + 0px);
  margin: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  transition: left 400ms cubic-bezier(0.4, 0, 0.2, 1);
  width: auto;
  height: auto;
  z-index: 1;
}

body.sidebar-collapsed .main-content:not(.mobile-mode) {
  left: calc(70px + 0px);
}

.mobile-mode .main-content {
  --header-offset: var(--header-height, 80px);
  --bottom-nav-offset: 80px; /* Approximate height of bottom navigation */
  --content-padding: 1rem;

  margin-left: 0 !important;
  margin-top: 0 !important;
  padding-top: var(--header-offset);
  padding-bottom: var(--bottom-nav-offset);
  border: none;
  border-radius: 0;
}

/* Encryption Overlay - CSS only implementation */
#encryption-overlay-portal :deep(.encryption-overlay) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 10, 0.95);
  backdrop-filter: blur(8px);
  border-radius: 1rem;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--accent);
  transition: all 0.3s ease;
}

.mobile-mode #encryption-overlay-portal :deep(.encryption-overlay) {
  border-radius: 0;
}

/* Header */
.app-header {
  background: #0a0a0a;
  border-bottom: 1px solid #004225;
  padding: 1.5rem 2rem;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100; /* Above encryption overlay (50) but below dropdown (1000) */
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  font-family: var(--font-family-branding);
  font-size: 1.75rem;
  font-weight: 600;
  color: #a9b7aa;
  transition: color 0.2s ease;
}

.app-title:hover {
  color: #a9b7aa;
}

.app-slogan {
  margin: 0;
  font-size: 0.85rem;
  color: #a9b7aa;
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
  padding: var(--content-padding);
  padding-top: 0rem;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  z-index: 1;
  background: #0a0a0a;
  min-height: 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
  display: flex;
  flex-direction: column;
}

.page-content::-webkit-scrollbar {
  display: none;
}

.scroll-to-top-button {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 36px;
  height: 36px;
  z-index: 11;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--ash-grey);
  cursor: pointer;
  pointer-events: auto;
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
  opacity: 1;
  padding: 0;
}

.scroll-to-top-button:hover {
  transform: translate(-50%, calc(-50% - 2px));
}

.scroll-to-top-button:active {
  transform: translate(-50%, calc(-50% - 1px));
}

.scroll-to-top-button svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  filter: drop-shadow(0 1px 2px var(--slate-grey));
}

.scroll-progress-indicator {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  width: 36px;
  height: 36px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
}

.progress-circle {
  width: 100%;
  height: 100%;
}

.progress-circle-bg {
  opacity: 0.3;
}

.progress-circle-fill {
  transition: stroke-dashoffset 0.1s ease-out;
  stroke-linecap: round;
}

.page-transition-wrapper {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* Mobile Mode Styles */
.mobile-mode .app-header {
  padding: 1rem;
}

.mobile-mode .app-title {
  font-size: 1.25rem;
  color: #a9b7aa;
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
  color: #a9b7aa;
}

@media (max-width: 768px) {
  .sidebar {
    width: 70px;
    min-width: 70px;
    max-width: 250px;
  }

  .sidebar:not(.collapsed) {
    width: 250px;
  }

  .app-header {
    padding: 1rem;
  }

  .app-title {
    font-size: 1.5rem;
    color: #a9b7aa;
  }

  .app-slogan {
    font-size: 0.75rem;
  }
}
</style>
