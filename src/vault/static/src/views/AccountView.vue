<template>
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
        <!-- Hidden username field for accessibility (required by browsers for password forms) -->
        <input
          type="text"
          name="username"
          autocomplete="username"
          style="position: absolute; left: -9999px; width: 1px; height: 1px"
          tabindex="-1"
          aria-hidden="true"
        />
        <div class="form-group">
          <label for="new-email">New Email:</label>
          <input
            id="new-email"
            v-model="emailForm.newEmail"
            type="email"
            required
            :disabled="emailForm.loading"
            placeholder="newemail@example.com"
            autocomplete="off"
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

    <!-- Two-Factor Authentication Section -->
    <section class="account-section">
      <div class="section-header-with-badge">
        <h2>Two-Factor Authentication</h2>
        <div
          v-if="!twoFactorLoading"
          class="status-badge"
          :class="twoFactorEnabled ? 'enabled' : 'disabled'"
        >
          <span class="status-icon">{{ twoFactorEnabled ? "✓" : "✗" }}</span>
          {{ twoFactorEnabled ? "2FA Enabled" : "2FA Disabled" }}
        </div>
      </div>

      <div v-if="twoFactorLoading" class="loading">Loading...</div>
      <div v-else>
        <p class="section-description">
          Add an extra layer of security to your account with two-factor
          authentication (2FA). You'll need to enter a code from your
          authenticator app when you log in.
        </p>

        <p v-if="twoFactorEnabled && twoFactorEnabledAt" class="enabled-date">
          Enabled on {{ formatDate(twoFactorEnabledAt) }}
        </p>

        <div v-if="twoFactorError" class="error-message">
          {{ twoFactorError }}
        </div>

        <div v-if="twoFactorEnabled" class="button-group">
          <button
            @click="showRegenerateBackupModal = true"
            class="btn btn-secondary"
          >
            Regenerate Backup Codes
          </button>
          <button @click="showDisable2FAModal = true" class="btn btn-danger">
            Disable 2FA
          </button>
        </div>

        <div v-else class="button-group">
          <button @click="start2FASetup" class="btn btn-primary">
            Enable 2FA
          </button>
        </div>
      </div>
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
            <label for="delete-password">Enter your password to confirm:</label>
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

    <!-- 2FA Setup Modal -->
    <div
      v-if="show2FASetupModal"
      class="modal-overlay"
      @click="show2FASetupModal = false"
    >
      <div class="modal glass glass-card modal-large" @click.stop>
        <TwoFactorSetup
          @success="handle2FASetupSuccess"
          @cancel="show2FASetupModal = false"
        />
      </div>
    </div>

    <!-- Disable 2FA Modal -->
    <div
      v-if="showDisable2FAModal"
      class="modal-overlay"
      @click="showDisable2FAModal = false"
    >
      <div class="modal glass glass-card" @click.stop>
        <h2>Disable 2FA</h2>
        <p class="warning-text">
          Are you sure you want to disable 2FA? Your account will be less
          secure.
        </p>
        <form @submit.prevent="handleDisable2FA">
          <div class="form-group">
            <label for="disable-2fa-password"
              >Enter your password to confirm:</label
            >
            <PasswordInput
              id="disable-2fa-password"
              v-model="disable2FAForm.password"
              autocomplete="current-password"
              required
              :disabled="disable2FAForm.loading"
              placeholder="Enter your password"
            />
          </div>
          <div v-if="disable2FAForm.error" class="error-message">
            {{ disable2FAForm.error }}
          </div>
          <div class="form-actions">
            <button
              type="submit"
              :disabled="disable2FAForm.loading"
              class="btn btn-danger"
            >
              {{ disable2FAForm.loading ? "Disabling..." : "Disable 2FA" }}
            </button>
            <button
              type="button"
              @click="showDisable2FAModal = false"
              class="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Regenerate Backup Codes Modal -->
    <div
      v-if="showRegenerateBackupModal"
      class="modal-overlay"
      @click="closeRegenerateBackupModal"
    >
      <div class="modal glass glass-card" @click.stop>
        <h2>Regenerate Backup Codes</h2>

        <div v-if="!regeneratedBackupCodes">
          <p>
            Regenerating backup codes will invalidate your existing codes. Make
            sure to save the new codes in a secure place.
          </p>
          <form @submit.prevent="handleRegenerateBackupCodes">
            <div class="form-group">
              <label for="regenerate-password"
                >Enter your password to confirm:</label
              >
              <PasswordInput
                id="regenerate-password"
                v-model="regenerateBackupForm.password"
                autocomplete="current-password"
                required
                :disabled="regenerateBackupForm.loading"
                placeholder="Enter your password"
              />
            </div>
            <div v-if="regenerateBackupForm.error" class="error-message">
              {{ regenerateBackupForm.error }}
            </div>
            <div class="form-actions">
              <button
                type="submit"
                :disabled="regenerateBackupForm.loading"
                class="btn btn-primary"
              >
                {{
                  regenerateBackupForm.loading
                    ? "Generating..."
                    : "Regenerate Codes"
                }}
              </button>
              <button
                type="button"
                @click="closeRegenerateBackupModal"
                class="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>

        <div v-else>
          <p class="warning-text">
            <strong>Save these codes now!</strong> They won't be shown again.
          </p>
          <div class="backup-codes-display">
            <div
              v-for="(code, index) in regeneratedBackupCodes"
              :key="index"
              class="backup-code"
            >
              <code>{{ code }}</code>
            </div>
          </div>
          <div class="form-actions">
            <button @click="downloadBackupCodes" class="btn btn-secondary">
              Download Codes
            </button>
            <button @click="closeRegenerateBackupModal" class="btn btn-primary">
              I've Saved My Codes
            </button>
          </div>
        </div>
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

  <!-- Re-encryption Modal -->
  <ReEncryptionModal
    :show="showReEncryptionModal"
    :progress="reEncryptionProgress"
    :currentStep="reEncryptionStep"
    :vaultspaceName="currentVaultspaceName"
    :currentIndex="reEncryptionCurrentIndex"
    :totalCount="reEncryptionTotalCount"
    :error="reEncryptionError"
    @cancel="handleReEncryptionCancel"
  />
</template>

<script>
import { account, auth, vaultspaces } from "../services/api";
import {
  initializeUserMasterKey,
  getStoredSalt,
  decryptVaultSpaceKeyForUser,
  clearAllCachedVaultSpaceKeys,
  getUserMasterKey,
} from "../services/keyManager";
import { encryptVaultSpaceKey } from "../services/encryption";
import { clearEncryptedMasterKey } from "../services/masterKeyStorage";
import { twoFactor } from "../services/api";
import PasswordInput from "../components/PasswordInput.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import ReEncryptionModal from "../components/ReEncryptionModal.vue";
import TwoFactorSetup from "../components/TwoFactorSetup.vue";

export default {
  name: "AccountView",
  components: {
    PasswordInput,
    ConfirmationModal,
    AlertModal,
    ReEncryptionModal,
    TwoFactorSetup,
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
      // Re-encryption modal state
      showReEncryptionModal: false,
      reEncryptionProgress: 0,
      reEncryptionStep: "Retrieving VaultSpaces...",
      currentVaultspaceName: null,
      reEncryptionCurrentIndex: 0,
      reEncryptionTotalCount: 0,
      reEncryptionError: null,
      reEncryptionCancelled: false,
      // Two-Factor Authentication state
      twoFactorEnabled: false,
      twoFactorEnabledAt: null,
      twoFactorLoading: false,
      twoFactorError: null,
      show2FASetupModal: false,
      showDisable2FAModal: false,
      showRegenerateBackupModal: false,
      regeneratedBackupCodes: null,
      disable2FAForm: {
        password: "",
        loading: false,
        error: null,
      },
      regenerateBackupForm: {
        password: "",
        loading: false,
        error: null,
      },
    };
  },
  async mounted() {
    await this.loadAccountInfo();
    await this.load2FAStatus();
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
      this.reEncryptionError = null;
      this.reEncryptionCancelled = false;

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
        // Get salt (from sessionStorage or server)
        let salt = getStoredSalt();
        if (!salt) {
          try {
            const saltBase64 = await auth.getMasterKeySalt();
            if (saltBase64) {
              const saltStr = atob(saltBase64);
              salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));
            }
          } catch (err) {
            this.passwordForm.error =
              "Failed to retrieve salt. Please try again.";
            this.passwordForm.loading = false;
            return;
          }
        }

        if (!salt) {
          this.passwordForm.error =
            "Salt not available. Please log out and log back in.";
          this.passwordForm.loading = false;
          return;
        }

        // Derive old master key directly from currentPassword
        const oldMasterKey = await initializeUserMasterKey(
          this.passwordForm.currentPassword,
          salt,
        );

        // Get current user ID
        const currentUser = await auth.getCurrentUser();
        if (!currentUser || !currentUser.id) {
          throw new Error("Failed to get current user");
        }

        // List all VaultSpaces for verification
        const vaultspacesList = await vaultspaces.list();

        // Verification step: Verify that old master key can decrypt at least one VaultSpace key
        // Also clear old master key from IndexedDB to prevent using stale key
        if (vaultspacesList.length > 0) {
          let canDecryptAtLeastOne = false;
          for (const vs of vaultspacesList) {
            try {
              const vaultspaceKeyData = await vaultspaces.getKey(vs.id);
              if (vaultspaceKeyData && vaultspaceKeyData.encrypted_key) {
                // Try to decrypt with old master key
                await decryptVaultSpaceKeyForUser(
                  oldMasterKey,
                  vaultspaceKeyData.encrypted_key,
                );
                canDecryptAtLeastOne = true;
                break;
              }
            } catch (err) {
              // Continue to next VaultSpace
            }
          }

          if (!canDecryptAtLeastOne) {
            this.showReEncryptionModal = false;
            this.passwordForm.error =
              "The current password is incorrect or cannot decrypt your VaultSpace keys. Please verify your current password and try again.";
            this.passwordForm.loading = false;
            return;
          }
        }

        // Clear old master key from IndexedDB before proceeding
        // This ensures we don't use a stale master key during re-encryption
        const jwtToken = localStorage.getItem("jwt_token");
        if (jwtToken) {
          try {
            await clearEncryptedMasterKey(jwtToken);
          } catch (clearErr) {
            // Continue even if clearing fails - will be overwritten anyway
          }
        }

        // Show re-encryption modal
        this.showReEncryptionModal = true;
        this.reEncryptionProgress = 0;
        this.reEncryptionStep = "Retrieving VaultSpaces...";
        this.currentVaultspaceName = null;
        this.reEncryptionCurrentIndex = 0;
        this.reEncryptionTotalCount = 0;

        // List all VaultSpaces (Step 1: 0-10%)
        this.reEncryptionStep = "Retrieving VaultSpaces...";
        this.reEncryptionProgress = 5;
        this.reEncryptionTotalCount = vaultspacesList.length;
        this.reEncryptionProgress = 10;

        if (vaultspacesList.length === 0) {
          // No VaultSpaces to re-encrypt, skip to password change
          this.reEncryptionProgress = 95;
          this.reEncryptionStep = "Finalizing...";
          await account.changePassword(
            this.passwordForm.currentPassword,
            this.passwordForm.newPassword,
          );
          this.showReEncryptionModal = false;
          this.passwordForm.success = "Password changed successfully";
          this.passwordForm.currentPassword = "";
          this.passwordForm.newPassword = "";
          this.passwordForm.confirmPassword = "";
          this.passwordForm.loading = false;
          return;
        }

        // Step 2: Decrypt all keys (10-40%)
        const decryptedKeys = new Map();
        let decryptedCount = 0;
        const decryptErrors = [];

        for (let i = 0; i < vaultspacesList.length; i++) {
          if (this.reEncryptionCancelled) {
            throw new Error("Re-encryption cancelled by user");
          }

          const vs = vaultspacesList[i];
          this.reEncryptionCurrentIndex = i;
          this.currentVaultspaceName = vs.name;
          this.reEncryptionStep = `Decrypting keys... ${i + 1}/${vaultspacesList.length}`;
          this.reEncryptionProgress = 10 + (i / vaultspacesList.length) * 30;

          try {
            // Get encrypted key
            const vaultspaceKeyData = await vaultspaces.getKey(vs.id);

            if (!vaultspaceKeyData || !vaultspaceKeyData.encrypted_key) {
              // VaultSpace has no encrypted key - skip it
              continue;
            }

            // Decrypt with old master key
            // Make key extractable so we can re-encrypt it with new master key
            const decryptedKey = await decryptVaultSpaceKeyForUser(
              oldMasterKey,
              vaultspaceKeyData.encrypted_key,
              true, // extractable = true for re-encryption
            );

            if (!decryptedKey) {
              throw new Error("decryptVaultSpaceKeyForUser returned null");
            }

            decryptedKeys.set(vs.id, {
              key: decryptedKey,
              name: vs.name,
            });
            decryptedCount++;
          } catch (err) {
            // Decryption failed - abort the process
            const errorMsg = err.message || String(err);
            decryptErrors.push({
              vaultspaceId: vs.id,
              vaultspaceName: vs.name,
              error: errorMsg,
            });
          }
        }

        // If decryption failed for any VaultSpace, abort the process
        if (decryptErrors.length > 0) {
          const errorDetails = decryptErrors
            .map((e) => `- ${e.vaultspaceName || e.vaultspaceId}: ${e.error}`)
            .join("\n");

          this.showReEncryptionModal = false;
          this.passwordForm.error = `Failed to decrypt VaultSpace keys with the current password. Password change cannot proceed to prevent data loss. Please verify your current password and try again.\n\nAffected VaultSpaces:\n${errorDetails}`;
          this.passwordForm.loading = false;
          return;
        }

        // Step 3: Derive new master key (40-45%)
        this.reEncryptionProgress = 40;
        this.reEncryptionStep = "Deriving new master key...";
        this.currentVaultspaceName = null;

        // Derive new master key from new password
        // Note: Old master key was already cleared from IndexedDB after verification step
        const newMasterKey = await initializeUserMasterKey(
          this.passwordForm.newPassword,
          salt,
        );

        this.reEncryptionProgress = 45;

        // Step 4: Re-encrypt existing keys (45-75%)
        const reencryptedKeys = new Map();
        const reencryptErrors = [];
        const totalToProcess = decryptedKeys.size;

        this.reEncryptionProgress = 45;
        let processedCount = 0;

        // Re-encrypt existing keys
        for (const [vsId, decryptedData] of decryptedKeys.entries()) {
          if (this.reEncryptionCancelled) {
            throw new Error("Re-encryption cancelled by user");
          }

          const vs = vaultspacesList.find((v) => v.id === vsId);
          if (!vs) {
            continue;
          }

          this.reEncryptionCurrentIndex = processedCount;
          this.currentVaultspaceName = vs.name;
          this.reEncryptionStep = `Re-encrypting keys... ${processedCount + 1}/${totalToProcess}`;
          this.reEncryptionProgress =
            45 + (processedCount / totalToProcess) * 30;
          processedCount++;

          try {
            // Re-encrypt with new master key
            const newEncryptedKey = await encryptVaultSpaceKey(
              newMasterKey,
              decryptedData.key,
            );

            if (!newEncryptedKey) {
              throw new Error("encryptVaultSpaceKey returned null/undefined");
            }

            reencryptedKeys.set(vs.id, newEncryptedKey);
          } catch (err) {
            // Re-encryption failed - abort the process
            const errorMsg = err.message || String(err);
            const errorDetails = reencryptErrors
              .map((e) => `- ${e.vaultspaceName || e.vaultspaceId}: ${e.error}`)
              .concat(`- ${vs.name || vsId}: ${errorMsg}`)
              .join("\n");

            this.showReEncryptionModal = false;
            this.passwordForm.error = `Failed to re-encrypt VaultSpace keys. Password change cannot proceed to prevent data loss. Please verify your current password and try again.\n\nAffected VaultSpaces:\n${errorDetails}`;
            this.passwordForm.loading = false;
            return;
          }
        }

        // Verify that all keys were successfully re-encrypted
        if (reencryptedKeys.size !== totalToProcess) {
          const missingIds = Array.from(decryptedKeys.keys()).filter(
            (id) => !reencryptedKeys.has(id),
          );
          const missingNames = missingIds
            .map((id) => {
              const vs = vaultspacesList.find((v) => v.id === id);
              return vs?.name || id;
            })
            .join(", ");

          this.showReEncryptionModal = false;
          this.passwordForm.error = `Failed to re-encrypt all VaultSpace keys. Password change cannot proceed to prevent data loss. Missing keys for: ${missingNames}`;
          this.passwordForm.loading = false;
          return;
        }

        // Step 5: Update keys on server (75-95%)
        let updatedCount = 0;
        const updateErrors = [];

        // Only process VaultSpaces that were successfully re-encrypted
        for (const [vsId, newEncryptedKey] of reencryptedKeys.entries()) {
          if (this.reEncryptionCancelled) {
            throw new Error("Re-encryption cancelled by user");
          }

          const vs = vaultspacesList.find((v) => v.id === vsId);
          if (!vs) {
            continue;
          }

          this.reEncryptionCurrentIndex = updatedCount;
          this.currentVaultspaceName = vs.name;
          this.reEncryptionStep = `Updating on server... ${updatedCount + 1}/${reencryptedKeys.size}`;
          this.reEncryptionProgress =
            75 + (updatedCount / reencryptedKeys.size) * 20;

          try {
            // Update key on server (share with self to update own key)
            // Note: The backend uses the authenticated user, not user_id from body
            // The user_id parameter is sent but ignored by backend - it uses authenticated user
            await vaultspaces.share(vs.id, currentUser.id, newEncryptedKey);
            updatedCount++;
          } catch (err) {
            const errorMsg = err.message || String(err);
            updateErrors.push({
              vaultspaceId: vs.id,
              vaultspaceName: vs.name,
              error: errorMsg,
            });
            // Continue with other VaultSpaces
          }
        }

        // Step 6: Finalize (95-100%)
        this.reEncryptionProgress = 95;
        this.reEncryptionStep = "Finalizing...";
        this.currentVaultspaceName = null;

        // Check if any keys were successfully updated
        if (updatedCount === 0 && reencryptedKeys.size > 0) {
          // No keys were successfully updated - build detailed error message
          let errorMessage = `Failed to update any VaultSpace keys (${updateErrors.length} error(s)). Your password will not be changed to prevent data loss.\n\n`;
          if (updateErrors.length > 0) {
            errorMessage += "Errors:\n";
            updateErrors.forEach((e, idx) => {
              errorMessage += `${idx + 1}. ${e.vaultspaceName || e.vaultspaceId}: ${e.error}\n`;
            });
          }
          errorMessage +=
            "\nPlease check the browser console for more details and try again.";

          this.showReEncryptionModal = false;
          this.passwordForm.error = errorMessage;
          this.passwordForm.loading = false;
          return;
        }

        // Change password on server
        await account.changePassword(
          this.passwordForm.currentPassword,
          this.passwordForm.newPassword,
        );

        // Verify that re-encrypted keys can be decrypted with the new master key
        // This ensures the re-encryption worked correctly
        if (reencryptedKeys.size > 0) {
          const testVaultSpaceId = Array.from(reencryptedKeys.keys())[0];
          try {
            // Get the re-encrypted key from server
            const testKeyData = await vaultspaces.getKey(testVaultSpaceId);
            if (testKeyData && testKeyData.encrypted_key) {
              // Try to decrypt with the new master key stored in IndexedDB
              const storedMasterKey = await getUserMasterKey();
              if (storedMasterKey) {
                await decryptVaultSpaceKeyForUser(
                  storedMasterKey,
                  testKeyData.encrypted_key,
                );
              } else {
                // Master key not in IndexedDB - re-store it
                await initializeUserMasterKey(
                  this.passwordForm.newPassword,
                  salt,
                );
              }
            }
          } catch (verifyErr) {
            // Verification failed - clear master key from IndexedDB and re-store it
            // This ensures the master key is correctly stored
            const jwtToken = localStorage.getItem("jwt_token");
            if (jwtToken) {
              await clearEncryptedMasterKey(jwtToken);
            }
            // Re-store the master key
            await initializeUserMasterKey(this.passwordForm.newPassword, salt);
          }
        }

        // Clear all cached VaultSpace keys to force reload with new master key
        // This ensures the cached keys are cleared and will be reloaded with the new master key
        clearAllCachedVaultSpaceKeys();

        // Hide modal
        this.reEncryptionProgress = 100;
        await new Promise((resolve) => setTimeout(resolve, 500));
        this.showReEncryptionModal = false;

        // Show success message
        this.passwordForm.success = "Password changed successfully";
        this.passwordForm.currentPassword = "";
        this.passwordForm.newPassword = "";
        this.passwordForm.confirmPassword = "";
      } catch (err) {
        this.showReEncryptionModal = false;
        if (this.reEncryptionCancelled) {
          this.passwordForm.error =
            "Re-encryption was cancelled. Your password has not been changed. Please try again.";
        } else {
          this.passwordForm.error = err.message || "Failed to change password";
          // If re-encryption partially completed, inform user
          if (
            err.message &&
            !err.message.includes("cancelled") &&
            !err.message.includes("Master key not available")
          ) {
            this.passwordForm.error +=
              " Some keys may have been updated. Please try changing your password again.";
          }
        }
      } finally {
        this.passwordForm.loading = false;
        this.reEncryptionProgress = 0;
        this.reEncryptionStep = "Retrieving VaultSpaces...";
        this.currentVaultspaceName = null;
        this.reEncryptionCurrentIndex = 0;
        this.reEncryptionTotalCount = 0;
        this.reEncryptionError = null;
        this.reEncryptionCancelled = false;
      }
    },
    handleReEncryptionCancel() {
      this.reEncryptionCancelled = true;
      this.showReEncryptionModal = false;
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
    // Two-Factor Authentication Methods
    async load2FAStatus() {
      this.twoFactorLoading = true;
      this.twoFactorError = null;
      try {
        const status = await twoFactor.getStatus();
        this.twoFactorEnabled = status.enabled;
        this.twoFactorEnabledAt = status.enabled_at;
      } catch (err) {
        console.error("Failed to load 2FA status:", err);
        // Don't show error for 2FA status check failure
      } finally {
        this.twoFactorLoading = false;
      }
    },
    start2FASetup() {
      this.show2FASetupModal = true;
      this.twoFactorError = null;
    },
    async handle2FASetupSuccess() {
      this.show2FASetupModal = false;
      // Reload 2FA status
      await this.load2FAStatus();
      // Show success message
      this.showAlert({
        type: "success",
        title: "2FA Enabled",
        message:
          "Two-factor authentication has been enabled successfully. Make sure to save your backup codes!",
      });
    },
    async handleDisable2FA() {
      this.disable2FAForm.loading = true;
      this.disable2FAForm.error = null;

      try {
        await twoFactor.disable(this.disable2FAForm.password);
        this.showDisable2FAModal = false;
        this.disable2FAForm.password = "";
        // Reload 2FA status
        await this.load2FAStatus();
        // Show success message
        this.showAlert({
          type: "success",
          title: "2FA Disabled",
          message: "Two-factor authentication has been disabled.",
        });
      } catch (err) {
        this.disable2FAForm.error = err.message || "Failed to disable 2FA";
      } finally {
        this.disable2FAForm.loading = false;
      }
    },
    async handleRegenerateBackupCodes() {
      this.regenerateBackupForm.loading = true;
      this.regenerateBackupForm.error = null;

      try {
        const result = await twoFactor.regenerateBackupCodes(
          this.regenerateBackupForm.password,
        );
        this.regeneratedBackupCodes = result.backup_codes;
        this.regenerateBackupForm.password = "";
      } catch (err) {
        this.regenerateBackupForm.error =
          err.message || "Failed to regenerate backup codes";
      } finally {
        this.regenerateBackupForm.loading = false;
      }
    },
    downloadBackupCodes() {
      if (!this.regeneratedBackupCodes) return;

      const codesText = this.regeneratedBackupCodes.join("\n");
      const blob = new Blob([codesText], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leyzen-vault-backup-codes.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
    closeRegenerateBackupModal() {
      this.showRegenerateBackupModal = false;
      this.regeneratedBackupCodes = null;
      this.regenerateBackupForm.password = "";
      this.regenerateBackupForm.error = null;
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
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
  padding-left: calc(2rem + 250px); /* Default: sidebar expanded (250px) */
  overflow-y: auto;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px); /* Sidebar collapsed (70px) */
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 2rem;
  padding: 2rem;
  min-width: 400px;
  max-width: 500px;
  max-height: 90vh;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow-y: auto;
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
/* Two-Factor Authentication Styles */
.section-header-with-badge {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.section-header-with-badge h2 {
  margin: 0;
}

.section-description {
  color: #b8c5d6;
  margin-bottom: 1.5rem;
  line-height: 1.5;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-weight: 500;
  font-size: 0.9rem;
  white-space: nowrap;
}

.status-badge.enabled {
  background: rgba(40, 167, 69, 0.1);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.status-badge.disabled {
  background: rgba(220, 53, 69, 0.1);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.status-icon {
  font-size: 1.1rem;
}

.enabled-date {
  color: #b8c5d6;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}

.button-group {
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.button-group .btn {
  min-width: auto;
  white-space: nowrap;
}

.modal-large {
  max-width: 600px;
}

.backup-codes-display {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.5rem;
  margin: 1.5rem 0;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.backup-codes-display .backup-code {
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  text-align: center;
}

.backup-codes-display .backup-code code {
  font-family: "Courier New", monospace;
  color: #e6eef6;
  font-size: 1rem;
  letter-spacing: 0.1em;
}
</style>
