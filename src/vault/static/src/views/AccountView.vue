<template>
  <AppLayout @logout="logout">
    <div class="account-view">
      <h1>Account Settings</h1>

      <!-- Account Information Section -->
      <section class="account-section">
        <h2>Account Information</h2>
        <div v-if="loading" class="loading">Loading...</div>
        <div v-else-if="accountError" class="error">{{ accountError }}</div>
        <div v-else class="account-info">
          <div class="info-item">
            <label>Email:</label>
            <span>{{ accountInfo.email }}</span>
          </div>
          <div class="info-item">
            <label>Account Created:</label>
            <span>{{ formatDate(accountInfo.created_at) }}</span>
          </div>
          <div class="info-item" v-if="accountInfo.last_login">
            <label>Last Login:</label>
            <span>{{ formatDate(accountInfo.last_login) }}</span>
          </div>
        </div>
      </section>

      <!-- Change Email Section -->
      <section class="account-section">
        <h2>Change Email</h2>
        <form @submit.prevent="handleUpdateEmail">
          <div class="form-group">
            <label for="new-email">New Email:</label>
            <input
              id="new-email"
              v-model="emailForm.newEmail"
              type="email"
              required
              :disabled="emailForm.loading"
              placeholder="newemail@example.com"
            />
          </div>
          <div class="form-group">
            <label for="email-password">Current Password:</label>
            <PasswordInput
              id="email-password"
              v-model="emailForm.password"
              autocomplete="current-password"
              required
              :disabled="emailForm.loading"
              placeholder="Enter your current password"
            />
          </div>
          <div v-if="emailForm.error" class="error-message">
            {{ emailForm.error }}
          </div>
          <div v-if="emailForm.success" class="success-message">
            {{ emailForm.success }}
          </div>
          <div class="form-actions">
            <button
              type="submit"
              :disabled="emailForm.loading"
              class="btn btn-primary"
            >
              {{ emailForm.loading ? "Updating..." : "Update Email" }}
            </button>
          </div>
        </form>
      </section>

      <!-- Change Password Section -->
      <section class="account-section">
        <h2>Change Password</h2>
        <form @submit.prevent="handleChangePassword">
          <div class="form-group">
            <label for="current-password">Current Password:</label>
            <PasswordInput
              id="current-password"
              v-model="passwordForm.currentPassword"
              autocomplete="current-password"
              required
              :disabled="passwordForm.loading"
              placeholder="Enter your current password"
            />
          </div>
          <div class="form-group">
            <label for="new-password">New Password:</label>
            <PasswordInput
              id="new-password"
              v-model="passwordForm.newPassword"
              autocomplete="new-password"
              :minlength="12"
              required
              :disabled="passwordForm.loading"
              placeholder="Enter new password (min 12 characters)"
            />
          </div>
          <div class="form-group">
            <label for="confirm-password">Confirm New Password:</label>
            <PasswordInput
              id="confirm-password"
              v-model="passwordForm.confirmPassword"
              autocomplete="new-password"
              required
              :disabled="passwordForm.loading"
              placeholder="Confirm new password"
            />
          </div>
          <div v-if="passwordForm.error" class="error-message">
            {{ passwordForm.error }}
          </div>
          <div v-if="passwordForm.success" class="success-message">
            {{ passwordForm.success }}
          </div>
          <div class="form-actions">
            <button
              type="submit"
              :disabled="passwordForm.loading"
              class="btn btn-primary"
            >
              {{ passwordForm.loading ? "Changing..." : "Change Password" }}
            </button>
          </div>
        </form>
      </section>

      <!-- Delete Account Section -->
      <section class="account-section danger-section">
        <h2>Delete Account</h2>
        <p class="warning-text">
          Warning: Deleting your account will permanently remove all your data.
          This action cannot be undone.
        </p>
        <button @click="showDeleteModal = true" class="btn btn-danger">
          Delete Account
        </button>
      </section>

      <!-- Delete Account Modal -->
      <div
        v-if="showDeleteModal"
        class="modal-overlay"
        @click="showDeleteModal = false"
      >
        <div class="modal glass glass-card" @click.stop>
          <h2>Confirm Account Deletion</h2>
          <p class="warning-text">
            This action cannot be undone. All your data will be permanently
            deleted.
          </p>
          <form @submit.prevent="handleDeleteAccount">
            <div class="form-group">
              <label for="delete-password"
                >Enter your password to confirm:</label
              >
              <PasswordInput
                id="delete-password"
                v-model="deleteForm.password"
                autocomplete="current-password"
                required
                :disabled="deleteForm.loading"
                placeholder="Enter your password"
              />
            </div>
            <div v-if="deleteForm.error" class="error-message">
              {{ deleteForm.error }}
            </div>
            <div class="form-actions">
              <button
                type="submit"
                :disabled="deleteForm.loading"
                class="btn btn-danger"
              >
                {{
                  deleteForm.loading
                    ? "Deleting..."
                    : "Delete Account Permanently"
                }}
              </button>
              <button
                type="button"
                @click="
                  showDeleteModal = false;
                  deleteForm.password = '';
                  deleteForm.error = '';
                "
                class="btn btn-secondary"
                :disabled="deleteForm.loading"
              >
                Cancel
              </button>
            </div>
          </form>
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
  </AppLayout>
</template>

<script>
import { account, auth } from "../services/api";
import AppLayout from "../components/AppLayout.vue";
import PasswordInput from "../components/PasswordInput.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";

export default {
  name: "AccountView",
  components: {
    AppLayout,
    PasswordInput,
    ConfirmationModal,
    AlertModal,
  },
  data() {
    return {
      loading: true,
      accountError: null,
      accountInfo: {},
      emailForm: {
        newEmail: "",
        password: "",
        loading: false,
        error: null,
        success: null,
      },
      passwordForm: {
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
        loading: false,
        error: null,
        success: null,
      },
      showDeleteModal: false,
      deleteForm: {
        password: "",
        loading: false,
        error: null,
      },
      // Confirmation modal state
      showConfirmModal: false,
      confirmModalConfig: {
        title: "",
        message: "",
        confirmText: "Confirm",
        dangerous: false,
        onConfirm: null,
      },
      // Alert modal state
      showAlertModal: false,
      alertModalConfig: {
        type: "info",
        title: "",
        message: "",
      },
    };
  },
  async mounted() {
    await this.loadAccountInfo();
  },
  methods: {
    async loadAccountInfo() {
      this.loading = true;
      this.accountError = null;
      try {
        this.accountInfo = await account.getAccount();
      } catch (err) {
        this.accountError = err.message || "Failed to load account information";
      } finally {
        this.loading = false;
      }
    },
    showAlert(config) {
      this.alertModalConfig = {
        type: config.type || "info",
        title: config.title || "Alert",
        message: config.message || "",
      };
      this.showAlertModal = true;
    },
    showConfirm(config) {
      this.confirmModalConfig = {
        title: config.title || "Confirm Action",
        message: config.message || "Are you sure you want to proceed?",
        confirmText: config.confirmText || "Confirm",
        dangerous: config.dangerous || false,
        onConfirm: config.onConfirm || (() => {}),
      };
      this.showConfirmModal = true;
    },
    handleConfirmModalConfirm() {
      if (this.confirmModalConfig.onConfirm) {
        this.confirmModalConfig.onConfirm();
      }
      this.showConfirmModal = false;
    },
    handleConfirmModalCancel() {
      this.showConfirmModal = false;
    },
    handleAlertModalClose() {
      this.showAlertModal = false;
    },
    async handleUpdateEmail() {
      this.emailForm.loading = true;
      this.emailForm.error = null;
      this.emailForm.success = null;

      if (!this.emailForm.newEmail || !this.emailForm.password) {
        this.emailForm.error = "Please fill in all fields";
        this.emailForm.loading = false;
        return;
      }

      try {
        const updatedUser = await account.updateEmail(
          this.emailForm.newEmail,
          this.emailForm.password,
        );
        this.accountInfo = updatedUser;
        this.emailForm.success = "Email updated successfully";
        this.emailForm.newEmail = "";
        this.emailForm.password = "";
        // Reload account info to get latest data
        await this.loadAccountInfo();
      } catch (err) {
        this.emailForm.error = err.message || "Failed to update email";
      } finally {
        this.emailForm.loading = false;
      }
    },
    async handleChangePassword() {
      this.passwordForm.loading = true;
      this.passwordForm.error = null;
      this.passwordForm.success = null;

      if (
        !this.passwordForm.currentPassword ||
        !this.passwordForm.newPassword ||
        !this.passwordForm.confirmPassword
      ) {
        this.passwordForm.error = "Please fill in all fields";
        this.passwordForm.loading = false;
        return;
      }

      if (this.passwordForm.newPassword !== this.passwordForm.confirmPassword) {
        this.passwordForm.error = "New passwords do not match";
        this.passwordForm.loading = false;
        return;
      }

      if (this.passwordForm.newPassword.length < 12) {
        this.passwordForm.error =
          "Password must be at least 12 characters long";
        this.passwordForm.loading = false;
        return;
      }

      try {
        await account.changePassword(
          this.passwordForm.currentPassword,
          this.passwordForm.newPassword,
        );
        this.passwordForm.success = "Password changed successfully";
        this.passwordForm.currentPassword = "";
        this.passwordForm.newPassword = "";
        this.passwordForm.confirmPassword = "";
      } catch (err) {
        this.passwordForm.error = err.message || "Failed to change password";
      } finally {
        this.passwordForm.loading = false;
      }
    },
    async handleDeleteAccount() {
      this.deleteForm.loading = true;
      this.deleteForm.error = null;

      if (!this.deleteForm.password) {
        this.deleteForm.error = "Please enter your password";
        this.deleteForm.loading = false;
        return;
      }

      try {
        await account.deleteAccount(this.deleteForm.password);
        // Logout and redirect to login
        auth.logout();
        this.$router.push("/login");
      } catch (err) {
        this.deleteForm.error = err.message || "Failed to delete account";
        this.deleteForm.loading = false;
      }
    },
    formatDate(dateString) {
      if (!dateString) return "N/A";
      const date = new Date(dateString);
      return date.toLocaleString();
    },
    logout() {
      auth.logout();
      this.$router.push("/login");
    },
  },
};
</script>

<style scoped>
.account-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

.account-view h1 {
  margin-bottom: 2rem;
  color: #e6eef6;
  font-size: 2rem;
}

.account-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.account-section h2 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #e6eef6;
  font-size: 1.5rem;
}

.danger-section {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.warning-text {
  color: #fca5a5;
  margin-bottom: 1rem;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-item label {
  font-weight: 600;
  color: #94a3b8;
  font-size: 0.9rem;
}

.info-item span {
  color: #e6eef6;
  font-size: 1rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #e6eef6;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #e6eef6;
  font-size: 1rem;
  transition: all 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.form-group input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-group input::placeholder {
  color: #64748b;
}

.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: rgba(88, 166, 255, 0.2);
  color: #e6eef6;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.3);
  border-color: rgba(88, 166, 255, 0.5);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #e6eef6;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
  border-color: rgba(239, 68, 68, 0.5);
}

.error-message {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.success-message {
  color: #86efac;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.loading {
  color: #94a3b8;
  text-align: center;
  padding: 2rem;
}

.error {
  color: #fca5a5;
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: rgba(30, 41, 59, 0.95);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  padding: 2rem;
  min-width: 400px;
  max-width: 500px;
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.4);
}

.modal h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #e6eef6;
}

.modal p {
  color: #94a3b8;
  margin-bottom: 1.5rem;
}
</style>
