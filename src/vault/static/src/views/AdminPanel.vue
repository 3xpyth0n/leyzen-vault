<template>
  <div class="admin-panel-layout">
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
      </nav>
      <button
        @click="toggleSidebar"
        class="sidebar-toggle"
        :title="sidebarCollapsed ? 'Expand' : 'Collapse'"
      >
        <Icon
          :name="sidebarCollapsed ? 'chevron-right' : 'chevron-left'"
          :size="16"
        />
      </button>
    </aside>

    <!-- Main Content Area -->
    <div
      class="main-content"
      :class="{ 'sidebar-collapsed': sidebarCollapsed }"
    >
      <!-- Admin Header with Tabs -->
      <header class="admin-header-section">
        <div class="admin-header-top">
          <div class="header-left">
            <h1
              class="admin-title"
              @click="$router.push('/dashboard')"
              style="cursor: pointer"
            >
              Admin Panel
            </h1>
          </div>
          <div class="header-right">
            <div class="header-actions">
              <router-link to="/account" class="btn btn-account"
                >Account</router-link
              >
              <button @click="handleLogout" class="btn btn-logout">
                Logout
              </button>
            </div>
          </div>
        </div>
        <div class="admin-tabs-wrapper">
          <div class="admin-tabs" ref="tabsContainer">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              :ref="(el) => setTabRef(el, tab.id)"
              @click="activeTab = tab.id"
              :class="['admin-tab-button', { active: activeTab === tab.id }]"
            >
              {{ tab.label }}
            </button>
            <div
              class="tab-indicator"
              ref="indicator"
              :style="indicatorStyle"
            ></div>
          </div>
        </div>
      </header>

      <!-- Page Content -->
      <main class="admin-content-wrapper">
        <div class="admin-content">
          <!-- Dashboard Tab -->
          <div v-if="activeTab === 'dashboard'" class="dashboard-tab">
            <div v-if="statsLoading" class="loading glass glass-card">
              Loading statistics...
            </div>
            <div v-else-if="statsError" class="error glass glass-card">
              {{ statsError }}
            </div>
            <div v-else-if="stats" class="stats-grid">
              <div class="stat-card glass glass-card">
                <h3>Users</h3>
                <div class="stat-value">{{ stats.users.total }}</div>
              </div>
              <div class="stat-card glass glass-card">
                <h3>Files</h3>
                <div class="stat-value">{{ stats.files.total }}</div>
                <div class="stat-details">
                  <span class="stat-detail"
                    >Deleted: {{ stats.files.deleted }}</span
                  >
                </div>
              </div>
              <div class="stat-card glass glass-card">
                <h3>VaultSpaces</h3>
                <div class="stat-value">{{ stats.vaultspaces.total }}</div>
                <div class="stat-details">
                  <span class="stat-detail"
                    >Personal: {{ stats.vaultspaces.personal }}</span
                  >
                </div>
              </div>
              <div class="stat-card glass glass-card">
                <h3>Disk Storage</h3>
                <div class="stat-value">
                  {{ stats.disk ? stats.disk.total_gb : 0 }} GB
                </div>
                <div class="stat-details">
                  <span class="stat-detail" v-if="stats.disk"
                    >Total: {{ stats.disk.total_mb }} MB</span
                  >
                  <span class="stat-detail" v-if="stats.disk"
                    >Used: {{ stats.disk.used_mb }} MB</span
                  >
                  <span class="stat-detail" v-if="stats.disk"
                    >Free: {{ stats.disk.free_mb }} MB</span
                  >
                </div>
              </div>
              <div class="stat-card glass glass-card">
                <h3>Recent Activity</h3>
                <div class="stat-value">{{ stats.users.recent_activity }}</div>
                <div class="stat-details">
                  <span class="stat-detail">Users (last 7 days)</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Users Tab -->
          <div v-if="activeTab === 'users'">
            <UserManagement />
          </div>

          <!-- Quotas Tab -->
          <div v-if="activeTab === 'quotas'">
            <QuotaManagement />
          </div>

          <!-- Audit Logs Tab -->
          <div v-if="activeTab === 'audit'">
            <AuditLogViewer />
          </div>

          <!-- API Keys Tab -->
          <div v-if="activeTab === 'api-keys'">
            <ApiKeyManagement />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, nextTick, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { admin, auth } from "../services/api";
import UserManagement from "../components/admin/UserManagement.vue";
import QuotaManagement from "../components/admin/QuotaManagement.vue";
import AuditLogViewer from "../components/admin/AuditLogViewer.vue";
import ApiKeyManagement from "../components/admin/ApiKeyManagement.vue";
import Icon from "../components/Icon.vue";

export default {
  name: "AdminPanel",
  components: {
    UserManagement,
    QuotaManagement,
    AuditLogViewer,
    ApiKeyManagement,
    Icon,
  },
  setup() {
    const router = useRouter();
    const activeTab = ref("dashboard");
    const stats = ref(null);
    const statsLoading = ref(false);
    const statsError = ref(null);
    const sidebarCollapsed = ref(false);
    const tabsContainer = ref(null);
    const indicator = ref(null);
    const tabRefs = ref({});
    const indicatorStyle = ref({
      left: "0px",
      width: "0px",
    });

    const tabs = [
      { id: "dashboard", label: "Dashboard" },
      { id: "users", label: "Users" },
      { id: "quotas", label: "Quotas" },
      { id: "audit", label: "Audit Logs" },
      { id: "api-keys", label: "API Keys" },
    ];

    const setTabRef = (el, tabId) => {
      if (el) {
        tabRefs.value[tabId] = el;
      }
    };

    const updateIndicatorPosition = () => {
      nextTick(() => {
        const activeTabElement = tabRefs.value[activeTab.value];
        if (!activeTabElement || !tabsContainer.value) {
          return;
        }

        const containerRect = tabsContainer.value.getBoundingClientRect();
        const tabRect = activeTabElement.getBoundingClientRect();

        const left = tabRect.left - containerRect.left;
        const width = tabRect.width;

        indicatorStyle.value = {
          left: `${left}px`,
          width: `${width}px`,
        };
      });
    };

    const loadStats = async () => {
      statsLoading.value = true;
      statsError.value = null;
      try {
        stats.value = await admin.getStats();
      } catch (err) {
        statsError.value = err.message || "Failed to load statistics";
      } finally {
        statsLoading.value = false;
      }
    };

    const handleLogout = () => {
      auth.logout();
      router.push("/login");
    };

    const toggleSidebar = () => {
      sidebarCollapsed.value = !sidebarCollapsed.value;
      // Save preference to localStorage
      localStorage.setItem("sidebarCollapsed", sidebarCollapsed.value);
      // Update indicator position after sidebar toggle
      updateIndicatorPosition();
    };

    // Watch for activeTab changes to update indicator position
    watch(activeTab, () => {
      updateIndicatorPosition();
    });

    // Watch for window resize to update indicator position
    const handleResize = () => {
      updateIndicatorPosition();
    };

    onMounted(async () => {
      // Load sidebar state from localStorage
      const saved = localStorage.getItem("sidebarCollapsed");
      if (saved !== null) {
        sidebarCollapsed.value = saved === "true";
      }
      await loadStats();
      // Update indicator position after mounting with a small delay
      // to ensure DOM is fully rendered
      setTimeout(() => {
        updateIndicatorPosition();
      }, 100);

      // Add resize listener
      if (typeof window !== "undefined") {
        window.addEventListener("resize", handleResize);
      }
    });

    onBeforeUnmount(() => {
      // Remove resize listener on unmount
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", handleResize);
      }
    });

    return {
      activeTab,
      tabs,
      stats,
      statsLoading,
      statsError,
      sidebarCollapsed,
      tabsContainer,
      indicator,
      indicatorStyle,
      setTabRef,
      loadStats,
      handleLogout,
      toggleSidebar,
    };
  },
};
</script>

<style scoped>
.admin-panel-layout {
  display: flex;
  min-height: 100vh;
  background: transparent;
}

/* Sidebar Styles */
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
  transition: width 0.3s ease;
  z-index: 100;
  overflow-y: auto;
  overflow-x: hidden;
  padding-top: 1.5rem;
  padding-bottom: 4rem;
  display: flex;
  flex-direction: column;
  visibility: visible;
  opacity: 1;
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

.sidebar.collapsed .sidebar-label {
  display: none;
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
  transition: all 0.2s ease;
  z-index: 101;
  visibility: visible;
  opacity: 1;
}

.sidebar.collapsed .sidebar-toggle {
  right: 0.5rem;
  left: auto;
  visibility: visible;
  opacity: 1;
}

.sidebar-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: scale(1.05);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 0 1rem;
  flex: 1;
}

.sidebar.collapsed .sidebar-nav {
  padding: 0 0.5rem;
  align-items: center;
  margin-top: 1rem;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(10px);
  border: none;
  border-radius: 10px;
  color: #e6eef6;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
}

.sidebar-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(88, 166, 255, 0.15);
}

.sidebar.collapsed .sidebar-item:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(88, 166, 255, 0.2);
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
  transition: transform 0.2s ease;
}

.sidebar-item:hover .sidebar-icon {
  transform: scale(1.1);
}

.sidebar-label {
  flex: 1;
}

/* Main Content */
.main-content {
  flex: 1;
  margin-left: 250px;
  transition: margin-left 0.3s ease;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content.sidebar-collapsed {
  margin-left: 70px;
}

/* Admin Header */
.admin-header-section {
  background: rgba(30, 41, 59, 0.4);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
  width: 100%;
}

.admin-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
}

.admin-title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: #e6eef6;
  transition: color 0.2s ease;
}

.admin-title:hover {
  color: rgba(88, 166, 255, 0.8);
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

.admin-tabs-wrapper {
  background: rgba(30, 41, 59, 0.2);
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  width: 100%;
  box-sizing: border-box;
}

.admin-tabs {
  display: flex;
  gap: 0;
  padding: 0 2rem;
  position: relative;
}

.admin-tab-button {
  background: transparent;
  border: none;
  color: #64748b;
  padding: 1rem 1.5rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
}

.admin-tab-button:hover {
  color: #cbd5e1;
  background: transparent;
}

.admin-tab-button.active {
  color: #60a5fa;
  background: transparent;
}

/* Liquid glass indicator */
.tab-indicator {
  position: absolute;
  bottom: 0;
  height: 2.5px;
  background: linear-gradient(
    90deg,
    rgba(96, 165, 250, 1),
    rgba(56, 189, 248, 1),
    rgba(96, 165, 250, 1)
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-radius: 999px;
  box-shadow:
    0 0 8px rgba(96, 165, 250, 0.6),
    0 0 16px rgba(56, 189, 248, 0.4),
    inset 0 1px 1px rgba(255, 255, 255, 0.3);
  transition:
    left 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
    width 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 2;
  pointer-events: none;
  will-change: left, width;
}

.admin-content-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  width: 100%;
  padding: 2rem;
  box-sizing: border-box;
}

.admin-content {
  width: 100%;
}

.dashboard-tab {
  width: 100%;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

.stat-card {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.55),
    rgba(15, 23, 42, 0.4)
  );
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.stat-card-large {
  grid-column: span 2;
}

.stat-card h3 {
  margin: 0 0 1rem 0;
  color: #cbd5e1;
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 2.5rem;
  font-weight: 700;
  color: #38bdf8;
  margin-bottom: 0.5rem;
}

.stat-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 0.75rem;
}

.stat-detail {
  color: #94a3b8;
  font-size: 0.85rem;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  border-radius: 1rem;
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
</style>
