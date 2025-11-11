<template>
  <div class="user-management">
    <div class="section-header glass glass-card">
      <h2>User Management</h2>
    </div>

    <div class="filters glass glass-card">
      <input
        v-model="searchQuery"
        @input="debouncedSearch"
        type="text"
        placeholder="Search by email..."
        class="search-input"
      />
      <select v-model="filterRole" @change="loadUsers" class="filter-select">
        <option value="">All Roles</option>
        <option value="user">User</option>
        <option value="admin">Admin</option>
        <option value="superadmin">Superadmin</option>
      </select>
    </div>

    <div v-if="loading" class="loading glass glass-card">
      <span v-html="getIcon('clock', 24)"></span>
      Loading users...
    </div>
    <div v-else-if="error" class="error glass glass-card">{{ error }}</div>
    <div v-else class="table-container glass glass-card">
      <table class="users-table">
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Created</th>
            <th>Last Login</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user?.id || Math.random()">
            <td>{{ user?.email || "N/A" }}</td>
            <td>
              <span
                class="role-badge"
                :class="`role-${user?.global_role || 'user'}`"
              >
                {{ user?.global_role || "user" }}
              </span>
            </td>
            <td>{{ formatDate(user?.created_at) }}</td>
            <td>{{ formatDate(user?.last_login) }}</td>
            <td class="actions">
              <button
                @click="viewUser(user?.id)"
                class="btn-icon"
                title="View"
                :disabled="!user?.id"
                v-html="getIcon('eye', 18)"
              ></button>
              <button
                @click.stop.prevent="handleEditClick(user, $event)"
                class="btn-icon"
                title="Edit"
                :disabled="!user"
                v-html="getIcon('edit', 18)"
              ></button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="pagination">
        <button
          @click="changePage((page || 1) - 1)"
          :disabled="!page || page === 1"
          class="btn btn-secondary"
        >
          Previous
        </button>
        <span class="page-info">
          Page {{ page || 1 }} of {{ totalPages || 1 }}
        </span>
        <button
          @click="changePage((page || 1) + 1)"
          :disabled="!page || !totalPages || page >= totalPages"
          class="btn btn-secondary"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Edit User Modal (Actions) -->
    <div
      v-if="showActionsModal"
      class="modal-overlay"
      @click.self="showActionsModal = false"
    >
      <div class="modal glass glass-card modal-wide" @click.stop>
        <div class="modal-header sticky-header">
          <h3>
            <span v-html="getIcon('edit', 20)"></span>
            Edit User
          </h3>
          <button
            @click="showActionsModal = false"
            class="modal-close-btn"
            aria-label="Close"
            type="button"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <div v-if="actionsModalUser" class="user-info glass">
            <p><strong>User:</strong> {{ actionsModalUser.email }}</p>
            <p>
              <strong>Current Role:</strong>
              <span
                class="role-badge"
                :class="`role-${actionsModalUser.global_role}`"
              >
                {{ actionsModalUser.global_role }}
              </span>
            </p>
          </div>

          <!-- Change Role Section -->
          <div
            v-if="actionsModalUser && canChangeRole(actionsModalUser)"
            class="actions-section glass"
          >
            <h4>Change Role</h4>

            <div class="form-group">
              <label>New Role:</label>
              <select
                v-model="actionsForm.newRole"
                required
                class="form-select"
              >
                <option
                  v-for="role in availableRoles"
                  :key="role"
                  :value="role"
                >
                  {{ role }}
                </option>
              </select>
            </div>

            <div
              v-if="actionsForm.newRole === 'superadmin'"
              class="warning-message glass"
            >
              <span v-html="getIcon('warning', 16)"></span>
              Assigning superadmin role will transfer the role from the current
              superadmin. The current superadmin will become admin.
            </div>

            <div class="form-actions">
              <button
                @click.prevent="saveRoleChange"
                class="btn btn-primary"
                :disabled="actionsForm.newRole === actionsModalUser.global_role"
              >
                Change Role
              </button>
            </div>
          </div>

          <div
            v-else-if="actionsModalUser && !canChangeRole(actionsModalUser)"
            class="info-message glass"
          >
            <span v-html="getIcon('info', 16)"></span>
            <span v-if="!currentUser">Unable to determine permissions.</span>
            <span
              v-else-if="
                currentUser.global_role === 'admin' &&
                actionsModalUser.global_role === 'superadmin'
              "
            >
              Admins cannot modify superadmin users.
            </span>
            <span
              v-else-if="
                currentUser.global_role === 'superadmin' &&
                currentUser.id === actionsModalUser.id
              "
            >
              You cannot change your own role.
            </span>
            <span v-else
              >You do not have permission to change this user's role.</span
            >
          </div>

          <!-- Delete User Section -->
          <div
            v-if="actionsModalUser && canDeleteUser(actionsModalUser)"
            class="actions-section glass"
          >
            <h4>Delete User</h4>

            <div class="danger-message glass">
              <span v-html="getIcon('warning', 16)"></span>
              This action will permanently delete the user and all associated
              data. This cannot be undone.
            </div>

            <div class="form-actions">
              <button
                @click.prevent="confirmDeleteUser(actionsModalUser.id)"
                class="btn btn-danger"
              >
                <span v-html="getIcon('delete', 16)"></span>
                Delete User
              </button>
            </div>
          </div>

          <div
            v-else-if="actionsModalUser && !canDeleteUser(actionsModalUser)"
            class="info-message glass"
          >
            <span v-html="getIcon('info', 16)"></span>
            <span v-if="!currentUser">Unable to determine permissions.</span>
            <span
              v-else-if="
                currentUser.global_role === 'admin' &&
                actionsModalUser.global_role === 'superadmin'
              "
            >
              Admins cannot delete superadmin users.
            </span>
            <span
              v-else-if="
                currentUser.global_role === 'superadmin' &&
                currentUser.id === actionsModalUser.id
              "
            >
              You cannot delete your own account. Transfer the superadmin role
              first.
            </span>
            <span v-else>You do not have permission to delete this user.</span>
          </div>
        </div>
      </div>
    </div>

    <!-- User Details Modal -->
    <div
      v-if="viewingUserDetails"
      class="modal-overlay"
      @click.self="viewingUserDetails = null"
    >
      <div class="modal glass glass-card modal-wide modal-view" @click.stop>
        <div class="modal-header">
          <h3>
            <span v-html="getIcon('eye', 20)"></span>
            User Details
          </h3>
          <button
            @click="viewingUserDetails = null"
            class="modal-close-btn"
            aria-label="Close"
            type="button"
          >
            ×
          </button>
        </div>
        <div v-if="userDetails && userDetails.user" class="user-details-grid">
          <div class="detail-section glass">
            <h4>Basic Information</h4>
            <div class="detail-item">
              <span class="detail-label">Email:</span>
              <span class="detail-value">{{
                userDetails.user?.email || "N/A"
              }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Role:</span>
              <span
                class="role-badge"
                :class="`role-${userDetails.user?.global_role || 'user'}`"
              >
                {{ userDetails.user?.global_role || "user" }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{
                formatDate(userDetails.user?.created_at)
              }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Last Login:</span>
              <span class="detail-value">{{
                formatDate(userDetails.user?.last_login)
              }}</span>
            </div>
          </div>
          <div class="detail-section glass">
            <h4>Storage</h4>
            <div class="detail-item">
              <span class="detail-label">Files:</span>
              <span class="detail-value">{{
                userDetails?.files_count || 0
              }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Used:</span>
              <span class="detail-value">{{
                formatSize(userDetails?.quota?.used)
              }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Limit:</span>
              <span class="detail-value">
                <span v-if="userDetails?.quota?.limit">{{
                  formatSize(userDetails.quota.limit)
                }}</span>
                <span v-else>Unlimited</span>
              </span>
            </div>
          </div>
          <div class="detail-section glass">
            <h4>VaultSpaces</h4>
            <div class="detail-item">
              <span class="detail-label">Total:</span>
              <span class="detail-value">{{
                userDetails?.vaultspaces?.length || 0
              }}</span>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button @click="viewingUserDetails = null" class="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Confirmation Modal -->
    <ConfirmationModal
      :show="showConfirmModal"
      :title="confirmModalConfig.title"
      :message="confirmModalConfig.message"
      :confirmText="confirmModalConfig.confirmText"
      :dangerous="confirmModalConfig.dangerous"
      @confirm="handleConfirmModalConfirm"
      @cancel="handleConfirmModalCancel"
      @close="handleConfirmModalCancel"
    />

    <!-- Alert Modal -->
    <AlertModal
      :show="showAlertModal"
      :type="alertModalConfig.type"
      :title="alertModalConfig.title"
      :message="alertModalConfig.message"
      @close="handleAlertModalClose"
      @ok="handleAlertModalClose"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed } from "vue";
import { admin, auth } from "../../services/api";
import ConfirmationModal from "../ConfirmationModal.vue";
import AlertModal from "../AlertModal.vue";

export default {
  name: "UserManagement",
  components: {
    ConfirmationModal,
    AlertModal,
  },
  setup() {
    const users = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const page = ref(1);
    const perPage = ref(50);
    const totalPages = ref(1);
    const searchQuery = ref("");
    const filterRole = ref("");
    const viewingUserDetails = ref(null);
    const userDetails = ref(null);
    const showConfirmModal = ref(false);
    const confirmModalConfig = ref({
      title: "",
      message: "",
      confirmText: "Confirm",
      dangerous: false,
      onConfirm: null,
    });
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "error",
      title: "Error",
      message: "",
    });
    const currentUser = ref(null);
    const showActionsModal = ref(false);
    const actionsModalUser = ref(null);
    const actionsForm = ref({
      newRole: "user",
    });

    let searchTimeout = null;

    const getIcon = (iconName, size = 24) => {
      try {
        if (!window || !window.Icons) {
          return "";
        }
        if (!window.Icons[iconName]) {
          return "";
        }
        const iconFn = window.Icons[iconName];
        if (typeof iconFn !== "function") {
          return "";
        }
        return iconFn.call(window.Icons, size, "currentColor");
      } catch (err) {
        console.warn("Error getting icon:", iconName, err);
        return "";
      }
    };

    const loadUsers = async () => {
      loading.value = true;
      error.value = null;
      try {
        const requestOptions = {
          query:
            searchQuery.value && searchQuery.value.trim()
              ? searchQuery.value.trim()
              : undefined,
          role:
            filterRole.value && filterRole.value.trim()
              ? filterRole.value.trim()
              : undefined,
          page:
            page.value && !isNaN(Number(page.value)) ? Number(page.value) : 1,
          per_page:
            perPage.value && !isNaN(Number(perPage.value))
              ? Number(perPage.value)
              : 50,
        };

        const result = await admin.listUsers(requestOptions);

        const normalizedUsers = (result.users || [])
          .map((user) => {
            if (!user) {
              return null;
            }
            return {
              id: user.id ? String(user.id) : null,
              email: user.email || "N/A",
              global_role: user.global_role || "user",
              created_at: user.created_at || null,
              last_login: user.last_login || null,
              ...user,
            };
          })
          .filter((user) => user !== null && user.id !== null);

        users.value = normalizedUsers;

        const pages = Number(result.pages);
        totalPages.value = pages && pages > 0 && !isNaN(pages) ? pages : 1;
      } catch (err) {
        console.error("Error in loadUsers:", err);
        error.value = err.message || "Failed to load users";
        users.value = [];
        totalPages.value = 1;
      } finally {
        loading.value = false;
      }
    };

    const debouncedSearch = () => {
      if (searchTimeout) clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        page.value = 1;
        loadUsers();
      }, 300);
    };

    const changePage = (newPage) => {
      const pageNum = Number(newPage);
      const maxPages = Number(totalPages.value) || 1;
      if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= maxPages) {
        page.value = pageNum;
        loadUsers();
      }
    };

    const loadCurrentUser = async () => {
      try {
        currentUser.value = await auth.getCurrentUser();
      } catch (err) {
        console.error("Failed to load current user:", err);
      }
    };

    const viewUser = async (userId) => {
      if (!userId) {
        return;
      }
      try {
        viewingUserDetails.value = userId;
        const details = await admin.getUserDetails(userId);
        if (!details.quota) {
          details.quota = { used: 0, limit: null };
        }
        userDetails.value = details;
      } catch (err) {
        console.error("Error loading user details:", err);
        showAlert({
          type: "error",
          title: "Error",
          message:
            "Failed to load user details: " + (err.message || "Unknown error"),
        });
      }
    };

    const handleEditClick = (user, event) => {
      if (!user || !user.id) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Invalid user data",
        });
        return;
      }

      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }

      openActionsModal(user);
    };

    const openActionsModal = async (user) => {
      if (!currentUser.value) {
        await loadCurrentUser();
      }

      actionsModalUser.value = user;
      actionsForm.value.newRole = user.global_role;
      showActionsModal.value = true;
    };

    const confirmDeleteUser = (userId) => {
      showActionsModal.value = false;

      setTimeout(() => {
        showConfirm({
          title: "Delete User",
          message: "Are you sure you want to delete this user?",
          confirmText: "Delete",
          dangerous: true,
          onConfirm: async () => {
            try {
              await admin.deleteUser(userId);
              loadUsers();
              showAlert({
                type: "success",
                title: "Success",
                message: "User deleted successfully",
              });
            } catch (err) {
              showAlert({
                type: "error",
                title: "Error",
                message: "Failed to delete user: " + err.message,
              });
            }
          },
        });
      }, 100);
    };

    const saveRoleChange = async () => {
      if (!actionsModalUser.value) {
        return;
      }

      try {
        await admin.updateUserRole(
          actionsModalUser.value.id,
          actionsForm.value.newRole,
        );
        showActionsModal.value = false;
        await loadUsers();
        await loadCurrentUser();
        showAlert({
          type: "success",
          title: "Success",
          message: "User role updated successfully",
        });
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to update role: " + err.message,
        });
      }
    };

    const canChangeRole = computed(() => (user) => {
      if (!currentUser.value || !user) {
        return false;
      }

      if (
        currentUser.value.global_role === "admin" &&
        user.global_role === "superadmin"
      ) {
        return false;
      }

      if (
        currentUser.value.global_role === "superadmin" &&
        currentUser.value.id === user.id
      ) {
        return false;
      }

      return true;
    });

    const canDeleteUser = computed(() => (user) => {
      if (!currentUser.value || !user) {
        return false;
      }

      if (
        currentUser.value.global_role === "admin" &&
        user.global_role === "superadmin"
      ) {
        return false;
      }

      if (
        currentUser.value.global_role === "superadmin" &&
        currentUser.value.id === user.id
      ) {
        return false;
      }

      return true;
    });

    const availableRoles = computed(() => {
      if (!currentUser.value) {
        return ["user"];
      }

      const role = currentUser.value.global_role;
      if (role === "admin") {
        return ["user", "admin"];
      }
      if (role === "superadmin") {
        return ["user", "admin", "superadmin"];
      }
      return ["user", "admin"];
    });

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const showConfirm = (config) => {
      confirmModalConfig.value = {
        title: config.title || "Confirm Action",
        message: config.message || "Are you sure you want to proceed?",
        confirmText: config.confirmText || "Confirm",
        dangerous: config.dangerous || false,
        onConfirm: config.onConfirm || (() => {}),
      };
      showConfirmModal.value = true;
    };

    const handleConfirmModalConfirm = () => {
      if (confirmModalConfig.value.onConfirm) {
        confirmModalConfig.value.onConfirm();
      }
      showConfirmModal.value = false;
    };

    const handleConfirmModalCancel = () => {
      showConfirmModal.value = false;
    };

    const handleAlertModalClose = () => {
      showAlertModal.value = false;
    };

    const formatDate = (dateString) => {
      if (!dateString || dateString === null || dateString === undefined) {
        return "Never";
      }
      try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
          return "Invalid Date";
        }
        return date.toLocaleString();
      } catch (err) {
        console.error("Error formatting date:", err, dateString);
        return "Invalid Date";
      }
    };

    const formatSize = (bytes) => {
      if (bytes === null || bytes === undefined || (bytes !== 0 && !bytes)) {
        return "0 B";
      }
      try {
        const numBytes = Number(bytes);
        if (isNaN(numBytes) || numBytes < 0) {
          return "0 B";
        }
        if (numBytes === 0) {
          return "0 B";
        }
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(numBytes) / Math.log(k));
        return (
          Math.round((numBytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i]
        );
      } catch (err) {
        console.error("Error formatting size:", err, bytes);
        return "0 B";
      }
    };

    onMounted(async () => {
      await loadCurrentUser();
      await loadUsers();
    });

    return {
      users,
      loading,
      error,
      page,
      totalPages,
      searchQuery,
      filterRole,
      viewingUserDetails,
      userDetails,
      showActionsModal,
      actionsModalUser,
      actionsForm,
      currentUser,
      showConfirmModal,
      confirmModalConfig,
      showAlertModal,
      alertModalConfig,
      getIcon,
      loadUsers,
      debouncedSearch,
      changePage,
      viewUser,
      handleEditClick,
      openActionsModal,
      confirmDeleteUser,
      saveRoleChange,
      canChangeRole,
      canDeleteUser,
      availableRoles,
      showAlert,
      showConfirm,
      handleConfirmModalConfirm,
      handleConfirmModalCancel,
      handleAlertModalClose,
      formatDate,
      formatSize,
    };
  },
};
</script>

<style scoped>
.user-management {
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  border-radius: 1rem;
}

.section-header h2 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
}

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  border-radius: 1rem;
}

.search-input,
.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.4);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  flex: 1;
  min-width: 0;
}

.search-input:focus,
.filter-select:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(30, 41, 59, 0.6);
}

.search-input::placeholder {
  color: #94a3b8;
}

.table-container {
  padding: 1.5rem;
  border-radius: 1rem;
  overflow: hidden;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
}

.users-table th {
  background: rgba(30, 41, 59, 0.4);
  padding: 1rem;
  text-align: left;
  color: #cbd5e1;
  font-weight: 600;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid rgba(148, 163, 184, 0.2);
}

.users-table td {
  padding: 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  color: #e6eef6;
}

.users-table tr:hover {
  background: rgba(30, 41, 59, 0.3);
}

.role-badge {
  padding: 0.375rem 0.875rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
  display: inline-block;
}

.role-user {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.role-admin {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.3);
}

.role-superadmin {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  width: 36px;
  height: 36px;
}

.btn-icon:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
  color: #38bdf8;
  transform: translateY(-2px);
}

.btn-icon:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon :deep(svg) {
  display: block;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.page-info {
  color: #cbd5e1;
  font-size: 0.9rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
  overflow-y: auto;
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.95),
    rgba(15, 23, 42, 0.9)
  );
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  padding: 0;
  border-radius: 1.25rem;
  min-width: 400px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
  margin: auto;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
}

.modal-large {
  min-width: 600px;
}

.modal-wide {
  width: 90%;
  max-width: 900px;
  min-width: 500px;
}

.modal-view .user-details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin: 1.5rem 0;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  width: 100%;
  box-sizing: border-box;
}

.modal-header.sticky-header {
  position: sticky;
  top: 0;
  -webkit-backdrop-filter: blur(20px);
  margin: 0;
  padding: 1.5rem 2rem;
  width: 100%;
  box-sizing: border-box;
  border-radius: 1.25rem 1.25rem 0 0;
  z-index: 20;
  border-top: none;
  border-left: none;
  border-right: none;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 2rem;
  padding-top: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.modal-header h3 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-header h3 :deep(svg) {
  color: #38bdf8;
}

.modal-close-btn {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #94a3b8;
  cursor: pointer;
  padding: 0.5rem;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.user-info {
  padding: 1.25rem;
  border-radius: 0.75rem;
  margin-top: 1rem;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-top: 1px solid rgba(148, 163, 184, 0.2);
  width: 100%;
  box-sizing: border-box;
}

.user-info p {
  margin: 0.5rem 0;
  color: #e6eef6;
  font-size: 0.95rem;
  width: 100%;
}

.user-info strong {
  color: #cbd5e1;
  margin-right: 0.5rem;
}

.actions-section {
  padding: 1.5rem;
  border-radius: 0.75rem;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(148, 163, 184, 0.1);
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.actions-section h4 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #cbd5e1;
  font-size: 1.1rem;
  font-weight: 600;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  padding-bottom: 0.5rem;
  width: 100%;
}

.actions-section:last-of-type {
  margin-bottom: 0;
}

.modal-form {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.form-group {
  margin-bottom: 1.25rem;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-size: 0.9rem;
  font-weight: 500;
  width: 100%;
}

.form-input,
.form-select {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.4);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(30, 41, 59, 0.6);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
  margin: 0;
  cursor: pointer;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  width: 100%;
  box-sizing: border-box;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.75rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-primary {
  background: linear-gradient(
    135deg,
    rgba(56, 189, 248, 0.2) 0%,
    rgba(129, 140, 248, 0.2) 100%
  );
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(56, 189, 248, 0.3) 0%,
    rgba(129, 140, 248, 0.3) 100%
  );
  border-color: rgba(56, 189, 248, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.2);
  border-color: rgba(148, 163, 184, 0.3);
}

.btn-danger {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.2) 0%,
    rgba(220, 38, 38, 0.2) 100%
  );
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.3) 0%,
    rgba(220, 38, 38, 0.3) 100%
  );
  border-color: rgba(239, 68, 68, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.warning-message,
.danger-message,
.info-message {
  padding: 1rem;
  border-radius: 0.75rem;
  margin: 1rem 0;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  font-size: 0.9rem;
  border: 1px solid;
  width: 100%;
  box-sizing: border-box;
}

.warning-message {
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

.danger-message {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.info-message {
  background: rgba(148, 163, 184, 0.1);
  border-color: rgba(148, 163, 184, 0.3);
  color: #94a3b8;
}

.warning-message :deep(svg),
.danger-message :deep(svg),
.info-message :deep(svg) {
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.user-details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.detail-section {
  padding: 1.5rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.1);
  background: rgba(30, 41, 59, 0.3);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.detail-section h4 {
  margin-top: 0;
  margin-bottom: 1.25rem;
  color: #cbd5e1;
  font-size: 1.1rem;
  font-weight: 600;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  padding-bottom: 0.75rem;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.05);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  color: #94a3b8;
  font-size: 0.9rem;
  font-weight: 500;
}

.detail-value {
  color: #e6eef6;
  font-size: 0.95rem;
  text-align: right;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  border-radius: 1rem;
}

.loading {
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.loading :deep(svg) {
  color: #38bdf8;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Glass morphism effect - uses global styles from assets/styles.css */
</style>
