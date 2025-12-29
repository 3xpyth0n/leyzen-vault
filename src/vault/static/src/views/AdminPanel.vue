<template>
  <div class="admin-panel-view-container">
    <div class="admin-panel">
      <header>
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

      <main class="admin-content-wrapper">
        <div class="admin-content">
          <div v-if="activeTab === 'dashboard'" class="dashboard-tab">
            <div v-if="statsLoading" class="loading">Loading statistics...</div>
            <div v-else-if="statsError" class="error">
              {{ statsError }}
            </div>
            <div v-else-if="stats" class="dashboard-content">
              <div class="dashboard-header">
                <h2>Dashboard Overview</h2>
                <div class="header-actions">
                  <span class="last-update" v-if="lastUpdateTime">
                    Last updated: {{ formatTime(lastUpdateTime) }}
                  </span>
                  <button
                    @click="loadStats"
                    class="btn-refresh"
                    title="Refresh"
                  >
                    <span v-html="getIcon('clock', 18)"></span>
                  </button>
                </div>
              </div>

              <div class="stats-grid">
                <div class="stat-card">
                  <h3>Users</h3>
                  <div class="stat-value">{{ stats.users.total }}</div>
                  <div class="stat-details">
                    <div class="stat-detail-row" v-if="stats.users.by_role">
                      <span class="stat-detail-label">Regular:</span>
                      <span class="stat-detail-value">{{
                        stats.users.by_role.user || 0
                      }}</span>
                    </div>
                    <div class="stat-detail-row" v-if="stats.users.by_role">
                      <span class="stat-detail-label">Admins:</span>
                      <span class="stat-detail-value">{{
                        (stats.users.by_role.admin || 0) +
                        (stats.users.by_role.superadmin || 0)
                      }}</span>
                    </div>
                  </div>
                </div>
                <div class="stat-card">
                  <h3>Files</h3>
                  <div class="stat-value">{{ stats.files.total }}</div>
                  <div class="stat-details">
                    <div class="stat-detail-row">
                      <span class="stat-detail-label">Deleted:</span>
                      <span class="stat-detail-value">{{
                        stats.files.deleted
                      }}</span>
                    </div>
                  </div>
                </div>
                <div class="stat-card">
                  <h3>VaultSpaces</h3>
                  <div class="stat-value">{{ stats.vaultspaces.total }}</div>
                  <div class="stat-details">
                    <div
                      class="stat-detail-row"
                      v-if="stats.vaultspaces.avg_per_user"
                    >
                      <span class="stat-detail-label">Avg per user:</span>
                      <span class="stat-detail-value">{{
                        stats.vaultspaces.avg_per_user
                      }}</span>
                    </div>
                  </div>
                </div>
                <div class="stat-card">
                  <h3>Disk Storage</h3>
                  <div class="stat-value">
                    {{ stats.disk ? stats.disk.used_gb : 0 }} GB
                  </div>
                  <div class="stat-details">
                    <div class="storage-progress" v-if="stats.disk">
                      <div class="progress-bar">
                        <div
                          class="progress-fill"
                          :style="{
                            width:
                              Math.min(stats.disk.percentage || 0, 100) + '%',
                          }"
                          :class="{ 'high-usage': stats.disk.percentage >= 80 }"
                        ></div>
                      </div>
                      <div class="progress-text">
                        {{ Math.round(stats.disk.percentage || 0) }}% used
                      </div>
                    </div>
                    <div class="stat-detail-row" v-if="stats.disk">
                      <span class="stat-detail-label">Total:</span>
                      <span class="stat-detail-value"
                        >{{ stats.disk.total_gb }} GB</span
                      >
                    </div>
                    <div class="stat-detail-row" v-if="stats.disk">
                      <span class="stat-detail-label">Free:</span>
                      <span class="stat-detail-value"
                        >{{ stats.disk.free_gb }} GB</span
                      >
                    </div>
                  </div>
                </div>
              </div>

              <div class="overview-section">
                <div class="overview-left">
                  <RecentActivityList
                    :logs="stats.recent_audit_logs || []"
                    :loading="statsLoading"
                    @view-all="activeTab = 'audit'"
                  />
                </div>
                <div class="overview-right">
                  <TopUsersCard
                    :users="stats.top_users || []"
                    :loading="statsLoading"
                    @view-all="activeTab = 'users'"
                  />
                </div>
              </div>

              <div class="alerts-section">
                <QuotaAlertsCard
                  :alerts="stats.quota_alerts || []"
                  :loading="statsLoading"
                  @view-all="activeTab = 'quotas'"
                />
              </div>

              <div class="quick-stats-grid">
                <div class="quick-stat-card" @click="activeTab = 'api-keys'">
                  <h4>API Keys</h4>
                  <div class="quick-stat-value">
                    {{ stats.api_keys?.total || 0 }}
                  </div>
                  <div class="quick-stat-detail">
                    <span v-if="stats.api_keys?.with_usage">
                      {{ stats.api_keys.with_usage }} active
                    </span>
                    <span v-else>No usage data</span>
                  </div>
                </div>
                <div
                  class="quick-stat-card"
                  @click="activeTab = 'authentication'"
                >
                  <h4>Authentication</h4>
                  <div class="quick-stat-value">
                    {{ stats.sso_providers?.total || 0 }}
                  </div>
                  <div class="quick-stat-detail">
                    <span v-if="stats.sso_providers?.active">
                      {{ stats.sso_providers.active }} active
                    </span>
                    <span v-else>None configured</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="activeTab === 'users'" class="users-tab">
            <UserManagement />
            <InvitationManagement />
          </div>

          <div v-if="activeTab === 'quotas'">
            <QuotaManagement />
          </div>

          <div v-if="activeTab === 'audit'">
            <AuditLogViewer />
          </div>

          <div v-if="activeTab === 'api-keys'">
            <ApiKeyManagement />
          </div>

          <div v-if="activeTab === 'authentication'">
            <AdminSSOProviders />
          </div>

          <div v-if="activeTab === 'integrations'">
            <ExternalStorageConfig />
            <DatabaseBackupConfig style="margin-top: 1.5rem" />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, nextTick, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { admin } from "../services/api";
import UserManagement from "../components/admin/UserManagement.vue";
import InvitationManagement from "../components/admin/InvitationManagement.vue";
import QuotaManagement from "../components/admin/QuotaManagement.vue";
import AuditLogViewer from "../components/admin/AuditLogViewer.vue";
import ApiKeyManagement from "../components/admin/ApiKeyManagement.vue";
import AdminSSOProviders from "./AdminSSOProviders.vue";
import ExternalStorageConfig from "../components/admin/ExternalStorageConfig.vue";
import DatabaseBackupConfig from "../components/admin/DatabaseBackupConfig.vue";
import RecentActivityList from "../components/admin/RecentActivityList.vue";
import TopUsersCard from "../components/admin/TopUsersCard.vue";
import QuotaAlertsCard from "../components/admin/QuotaAlertsCard.vue";

export default {
  name: "AdminPanel",
  components: {
    UserManagement,
    InvitationManagement,
    QuotaManagement,
    AuditLogViewer,
    ApiKeyManagement,
    AdminSSOProviders,
    ExternalStorageConfig,
    DatabaseBackupConfig,
    RecentActivityList,
    TopUsersCard,
    QuotaAlertsCard,
  },
  setup() {
    const router = useRouter();
    const stats = ref(null);
    const statsLoading = ref(false);
    const statsError = ref(null);
    const lastUpdateTime = ref(null);
    const tabsContainer = ref(null);
    const indicator = ref(null);
    const tabRefs = ref({});
    const indicatorStyle = ref({
      left: "0px",
      width: "0px",
    });
    let resizeObserver = null;

    const tabs = [
      { id: "dashboard", label: "Dashboard" },
      { id: "users", label: "Users" },
      { id: "quotas", label: "Quotas" },
      { id: "authentication", label: "Authentication" },
      { id: "api-keys", label: "API Keys" },
      { id: "integrations", label: "Integrations" },
      { id: "audit", label: "Audit Logs" },
    ];

    // Mapping between tab IDs and URL hashes
    const tabToHashMap = {
      dashboard: "dashboard",
      users: "users",
      quotas: "quotas",
      authentication: "authentication",
      "api-keys": "api-keys",
      integrations: "integrations",
      audit: "audit",
    };

    // Reverse mapping: hash to tab ID
    const hashToTabMap = Object.fromEntries(
      Object.entries(tabToHashMap).map(([tab, hash]) => [hash, tab]),
    );

    // Get tab ID from URL hash
    const getTabFromHash = () => {
      if (typeof window === "undefined") {
        return "dashboard";
      }
      const hash = window.location.hash.replace("#", "");
      return hashToTabMap[hash] || "dashboard";
    };

    // Get hash from tab ID
    const getHashFromTab = (tabId) => {
      return tabToHashMap[tabId] || "dashboard";
    };

    const updateUrlHash = (tabId) => {
      if (typeof window === "undefined") {
        return;
      }
      const hash = getHashFromTab(tabId);
      if (window.location.hash !== `#${hash}`) {
        window.history.replaceState(null, "", `#${hash}`);
      }
    };

    const initialTab =
      typeof window !== "undefined" ? getTabFromHash() : "dashboard";
    const activeTab = ref(initialTab);

    const setTabRef = (el, tabId) => {
      if (el) {
        tabRefs.value[tabId] = el;
        // Observe the new tab element if ResizeObserver is set up
        if (resizeObserver && typeof ResizeObserver !== "undefined") {
          resizeObserver.observe(el);
        }
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
        const left =
          tabRect.left - containerRect.left + tabsContainer.value.scrollLeft;
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
        lastUpdateTime.value = new Date();
      } catch (err) {
        statsError.value = err.message || "Failed to load statistics";
      } finally {
        statsLoading.value = false;
      }
    };

    const formatTime = (date) => {
      if (!date) return "";
      return new Date(date).toLocaleTimeString();
    };

    // Watch for activeTab changes to update indicator position and URL hash
    watch(activeTab, (newTab) => {
      updateIndicatorPosition();
      updateUrlHash(newTab);
    });

    // Watch for window resize to update indicator position
    const handleResize = () => {
      updateIndicatorPosition();
    };

    // Handle hash changes from browser navigation (back/forward buttons)
    const handleHashChange = () => {
      const tabFromHash = getTabFromHash();
      if (tabFromHash !== activeTab.value) {
        activeTab.value = tabFromHash;
      }
    };

    // Handle scroll on tabs container to update indicator position
    const handleScroll = () => {
      updateIndicatorPosition();
    };

    onMounted(async () => {
      if (typeof window !== "undefined") {
        const currentHash = window.location.hash.replace("#", "");
        if (!currentHash || !hashToTabMap[currentHash]) {
          updateUrlHash(activeTab.value);
        }
      }

      await loadStats();

      // to ensure DOM is fully rendered
      setTimeout(() => {
        updateIndicatorPosition();
      }, 100);

      // Add resize and hashchange listeners
      if (typeof window !== "undefined") {
        window.addEventListener("resize", handleResize);
        window.addEventListener("hashchange", handleHashChange);
      }

      // Add scroll listener to tabs container
      if (tabsContainer.value) {
        tabsContainer.value.addEventListener("scroll", handleScroll);
      }

      // Setup ResizeObserver to watch for size changes
      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            updateIndicatorPosition();
          });
        });

        // Observe the tabs container
        if (tabsContainer.value) {
          resizeObserver.observe(tabsContainer.value);
        }

        // Observe each tab button
        nextTick(() => {
          Object.values(tabRefs.value).forEach((tabEl) => {
            if (tabEl) {
              resizeObserver.observe(tabEl);
            }
          });
        });
      }
    });

    onBeforeUnmount(() => {
      // Remove listeners on unmount
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", handleResize);
        window.removeEventListener("hashchange", handleHashChange);
      }

      // Remove scroll listener from tabs container
      if (tabsContainer.value) {
        tabsContainer.value.removeEventListener("scroll", handleScroll);
      }

      // Disconnect ResizeObserver
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
    });

    const getIcon = (iconName, size = 24) => {
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
    };

    return {
      getIcon,
      activeTab,
      tabs,
      stats,
      statsLoading,
      statsError,
      lastUpdateTime,
      tabsContainer,
      indicator,
      indicatorStyle,
      setTabRef,
      loadStats,
      formatTime,
    };
  },
};
</script>

<style scoped>
.admin-panel {
  width: 100%;
  min-height: 100%;
  background: transparent;
}

/* Admin Header */
.admin-header-section {
  background: var(--bg-modal);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
  width: 100%;
}

.admin-tabs-wrapper {
  background: var(--bg-modal);
  border: 1px solid var(--border-color);
  width: 100%;
  box-sizing: border-box;
  margin-top: 1rem;
  margin-bottom: 2rem;
}

.admin-tabs {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  position: relative;
  justify-content: center;
  align-items: center;
  background: var(--bg-modal, #141414);
}

.admin-tab-button {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #a9b7aa;
  padding: 0.75rem 1.25rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition:
    background var(--transition-base),
    border-color var(--transition-base);
  position: relative;
  z-index: 1;
}

.admin-tab-button:hover {
  color: #a9b7aa;
  background: rgba(10, 10, 10, 0.3);
}

.admin-tab-button.active {
  color: #a9b7aa;
  background: var(--accent);
}

/* Tab indicator */
.tab-indicator {
  position: absolute;
  bottom: 0;
  height: 2px;
  background: var(--accent);
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

.users-tab {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.dashboard-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
}

.dashboard-header h2 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.last-update {
  color: #a9b7aa;
  font-size: 0.85rem;
}

.btn-refresh {
  background: transparent !important;
  border: none !important;
  padding: 0.25rem !important;
  margin: 0 !important;
  cursor: pointer;
  color: #a9b7aa;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    color 0.2s ease,
    transform 0.2s ease;

  box-shadow: none !important;
  min-width: auto !important;
  width: auto !important;
  height: auto !important;
  font-size: inherit !important;
  font-weight: inherit !important;
  line-height: 1 !important;
}

.btn-refresh:hover {
  background: transparent !important;
  color: #a9b7aa;
  transform: rotate(90deg);
  box-shadow: none !important;
  border: none !important;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

.mobile-mode .stats-grid {
  grid-template-columns: 1fr;
  gap: 1rem;
}

.stat-card {
  background: var(--bg-modal, #141414);
  border: 1px solid var(--border-color);
  padding: 1.5rem;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.mobile-mode .stat-card {
  padding: 1rem;
  max-width: 100%;
}

.mobile-mode .stat-card-large {
  grid-column: span 1;
}

.stat-card-large {
  grid-column: span 2;
}

.stat-card h3 {
  margin: 0 0 1rem 0;
  color: #a9b7aa;
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.stat-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.stat-detail {
  color: #a9b7aa;
  font-size: 0.85rem;
}

.stat-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.stat-detail-label {
  color: #a9b7aa;
  font-size: 0.85rem;
}

.stat-detail-value {
  color: #a9b7aa;
  font-size: 0.85rem;
  font-weight: 500;
}

.stat-growth {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #004225;
}

.growth-indicator {
  font-size: 0.9rem;
  font-weight: 600;
  padding: 0.25rem 0.5rem;
}

.growth-indicator.positive {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
}

.growth-indicator.negative {
  color: #f87171;
  background: rgba(239, 68, 68, 0.15);
}

.growth-label {
  color: #a9b7aa;
  font-size: 0.8rem;
}

.storage-progress {
  margin-top: 0.75rem;
  margin-bottom: 0.5rem;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
}

.progress-fill.high-usage {
  background: var(--error);
}

.progress-text {
  color: #a9b7aa;
  font-size: 0.8rem;
  text-align: center;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.overview-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .overview-section {
    grid-template-columns: 1fr;
  }
}

.mobile-mode .overview-section {
  grid-template-columns: 1fr;
  gap: 1rem;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

.mobile-mode .overview-left,
.mobile-mode .overview-right {
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

/* Mobile Mode Styles */
.mobile-mode .admin-tabs-wrapper {
  overflow: hidden; /* Hide scrollbar on wrapper */
}

.mobile-mode .admin-tabs {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 0.75rem 1rem;
  gap: 0.25rem;
  justify-content: flex-start; /* Align tabs to the left instead of center */
  min-width: 100%; /* Ensure tabs can extend beyond viewport */
}

.mobile-mode .admin-tabs::-webkit-scrollbar {
  display: none;
}

.mobile-mode .admin-tab-button {
  padding: 0.625rem 1rem;
  font-size: 0.85rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.mobile-mode .admin-content-wrapper {
  padding: 1rem;
}

.mobile-mode .quick-stats-grid {
  grid-template-columns: 1fr;
  gap: 1rem;
}

.mobile-mode .quick-stat-card {
  padding: 1rem;
}

.mobile-mode .dashboard-header {
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
}

.mobile-mode .overview-section {
  grid-template-columns: 1fr;
  gap: 1rem;
}

.alerts-section {
  width: 100%;
}

.quick-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.quick-stat-card {
  padding: 1.5rem;
  background: var(--bg-modal, #141414);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s ease;
}

.quick-stat-card:hover {
  background: rgba(10, 10, 10, 0.8);
  border-color: var(--border-color);
}

.quick-stat-card h4 {
  margin: 0 0 0.75rem 0;
  color: #a9b7aa;
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.quick-stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.quick-stat-detail {
  color: #a9b7aa;
  font-size: 0.85rem;
}
</style>
