<template>
  <div class="setup-wrapper">
    <div class="setup-container">
      <div class="slides-container">
        <!-- Slide 1: Setup Form -->
        <transition name="slide" mode="out-in">
          <div v-if="currentSlide === 0" key="form" class="slide slide-form">
            <div class="setup-header">
              <h1>Leyzen Vault Setup</h1>
              <p class="setup-subtitle">
                Welcome! Let's create your administrator account to get started.
              </p>
            </div>

            <form @submit.prevent="handleSetup" class="setup-form">
              <div v-if="error" class="error-message">
                {{ error }}
              </div>

              <div class="form-group">
                <label for="email">Email Address</label>
                <input
                  id="email"
                  v-model="email"
                  type="email"
                  placeholder="admin@example.com"
                  required
                  autocomplete="email"
                  :disabled="loading"
                />
              </div>

              <div class="form-group">
                <label for="password">Password</label>
                <PasswordInput
                  id="password"
                  v-model="password"
                  placeholder="Enter your password"
                  required
                  autocomplete="new-password"
                  :disabled="loading"
                  :minlength="12"
                />
                <p class="password-hint">
                  Must be at least 12 characters with uppercase, lowercase, and
                  digits
                </p>
              </div>

              <div class="form-group">
                <label for="confirmPassword">Confirm Password</label>
                <PasswordInput
                  id="confirmPassword"
                  v-model="confirmPassword"
                  placeholder="Confirm your password"
                  required
                  autocomplete="new-password"
                  :disabled="loading"
                  :minlength="12"
                />
              </div>

              <button
                type="submit"
                class="btn btn-primary btn-setup"
                :disabled="loading || !email || !password || !confirmPassword"
              >
                {{
                  loading
                    ? "Creating Account..."
                    : "Create Administrator Account"
                }}
              </button>

              <p>
                or
                <a href="#" @click.prevent="goToRestore">Restore from backup</a>
              </p>
            </form>
          </div>

          <!-- Slide 2: Backup Selection -->
          <div
            v-else-if="currentSlide === 2"
            key="restore"
            class="slide slide-restore"
          >
            <div class="setup-header">
              <h1>Restore from Backup</h1>
              <p class="setup-subtitle">
                Select a backup to restore your database
              </p>
            </div>

            <div class="restore-content">
              <div v-if="loadingBackups" class="loading-state">
                <div class="spinner"></div>
                <p>Loading backups...</p>
              </div>

              <div v-else-if="backupsError" class="error-message">
                {{ backupsError }}
              </div>

              <div v-else-if="backups.length === 0" class="empty-state">
                <p>No backups available</p>
                <p class="empty-hint">
                  No local backups found. Please create a backup first or use
                  the setup form to create a new account.
                </p>
              </div>

              <div v-else class="backups-list">
                <div
                  v-for="backup in backups"
                  :key="backup.id"
                  class="backup-item"
                  :class="{
                    selected: String(selectedBackupId) === String(backup.id),
                  }"
                  @click.stop="selectBackup(backup.id)"
                >
                  <div class="backup-info">
                    <div class="backup-header">
                      <span class="backup-type">{{ backup.backup_type }}</span>
                      <span class="backup-status status-completed">
                        {{ backup.status }}
                      </span>
                    </div>
                    <div class="backup-details">
                      <div>Date: {{ formatDate(backup.created_at) }}</div>
                      <div>Size: {{ formatSize(backup.size_bytes) }}</div>
                    </div>
                  </div>
                  <div class="backup-check">
                    <span v-if="String(selectedBackupId) === String(backup.id)"
                      >✓</span
                    >
                  </div>
                </div>
              </div>

              <div class="restore-actions">
                <button
                  class="btn btn-secondary btn-back"
                  @click="goBackToSetup"
                  :disabled="restoring"
                >
                  Back
                </button>
                <button
                  class="btn btn-primary btn-restore-confirm"
                  @click="handleRestore"
                  :disabled="!selectedBackupId || restoring"
                >
                  {{ restoring ? "Restoring..." : "Restore" }}
                </button>
              </div>
            </div>
          </div>

          <!-- Slide 3: Restore Loading -->
          <div
            v-else-if="currentSlide === 3"
            key="restore-loading"
            class="slide slide-restore-loading"
          >
            <div class="setup-header">
              <h1>Restoring Database</h1>
              <p class="setup-subtitle">
                Please wait while we restore your database...
              </p>
            </div>

            <div class="restore-loading-content">
              <div class="spinner-large"></div>
              <p class="loading-message">{{ restoreMessage }}</p>
            </div>
          </div>

          <!-- Slide 1: Verification Message -->
          <div
            v-else-if="currentSlide === 1"
            key="verification"
            class="slide slide-verification"
          >
            <div class="setup-header">
              <h1>Account Created Successfully</h1>
              <p class="setup-subtitle">
                Your superadmin account has been created.
              </p>
            </div>

            <div class="verification-content">
              <div class="verification-icon">✓</div>
              <div class="verification-info">
                <p>
                  A verification email has been sent to
                  <strong>{{ email }}</strong
                  >. Please check your inbox and click on the verification link
                  in the email.
                </p>
                <p class="verification-warning">
                  <strong>Important:</strong> While you can continue without
                  verifying your email, all other users must verify their email
                  address before they can access Leyzen Vault.
                </p>
              </div>
              <div class="verification-actions">
                <button
                  class="btn btn-primary btn-continue"
                  @click="continueToLogin"
                >
                  Continue Anyway
                </button>
                <button
                  class="btn btn-secondary btn-verify"
                  @click="goToVerificationPage"
                >
                  Go to Verification Page
                </button>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { auth, removeToken, admin, config as configApi } from "../services/api";
import PasswordInput from "../components/PasswordInput.vue";
import { logger } from "../utils/logger";

export default {
  name: "Setup",
  components: {
    PasswordInput,
  },
  setup() {
    const router = useRouter();
    const email = ref("");
    const password = ref("");
    const confirmPassword = ref("");
    const error = ref("");
    const loading = ref(false);
    const currentSlide = ref(0); // 0 = form, 1 = verification, 2 = restore, 3 = restore-loading
    const createdUserId = ref(null);
    const backups = ref([]);
    const loadingBackups = ref(false);
    const backupsError = ref(null);
    const selectedBackupId = ref(null);
    const restoring = ref(false);
    const restoreMessage = ref("Preparing restore...");

    const clearAllStorage = () => {
      // Clear all localStorage items
      try {
        localStorage.clear();
      } catch (err) {
        // Silently fail
      }

      // Clear all sessionStorage items
      try {
        sessionStorage.clear();
      } catch (err) {
        // Silently fail
      }

      // Clear all cookies
      try {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
          const eqPos = cookie.indexOf("=");
          const name =
            eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
          // Delete cookie by setting it to expire in the past
          // Try with different path and domain combinations
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${window.location.hostname}`;
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${window.location.hostname}`;
        }
      } catch (err) {
        // Silently fail
      }
    };

    onMounted(async () => {
      // Load timezone from config
      try {
        if (configApi && typeof configApi.getConfig === "function") {
          const configData = await configApi.getConfig();
          if (configData.timezone) {
            timezone.value = configData.timezone;
          }
        } else {
          // Fallback to direct fetch if configApi is not available
          const response = await fetch("/api/v2/config", {
            method: "GET",
            credentials: "same-origin",
          });
          if (response.ok) {
            const configData = await response.json();
            if (configData.timezone) {
              timezone.value = configData.timezone;
            }
          }
        }
      } catch (err) {
        logger.warn("Failed to load timezone, using UTC:", err);
      }

      // Clear all browser storage (cookies, localStorage, sessionStorage)
      // This ensures a clean state when accessing setup page
      // Important: This simulates a "fresh install" from browser perspective
      clearAllStorage();

      // Check if setup is already complete
      // If check fails (network error, database not available), allow user to proceed with setup
      try {
        const setupComplete = await auth.isSetupComplete();
        if (setupComplete) {
          // Setup already complete, redirect to login
          router.push("/login");
        }
      } catch (err) {
        // Network errors are expected on fresh install or when database is unavailable
        // Allow user to proceed with setup page
      }
    });

    const handleSetup = async () => {
      error.value = "";
      loading.value = true;

      try {
        // Validate passwords match
        if (password.value !== confirmPassword.value) {
          error.value = "Passwords do not match";
          loading.value = false;
          return;
        }

        const response = await auth.setup(
          email.value,
          password.value,
          confirmPassword.value,
        );

        // Check if email verification is required
        if (response.email_verification_required) {
          // Store user ID for verification page
          createdUserId.value = response.user?.id;

          // Clear password from memory
          password.value = "";
          confirmPassword.value = "";
          loading.value = false;

          // Slide to verification message
          currentSlide.value = 1;
          return;
        }

        // IMMEDIATELY check for and remove any token that might have been created
        // This must happen BEFORE any other operations
        let tokenCheck = localStorage.getItem("jwt_token");
        if (tokenCheck) {
          logger.warn("Token detected after setup! Removing immediately...");
          // Try multiple removal methods
          localStorage.removeItem("jwt_token");
          delete localStorage.jwt_token;
          // Verify removal
          tokenCheck = localStorage.getItem("jwt_token");
          if (tokenCheck) {
            logger.error(
              "Token persists after removal! Forcing complete clear...",
            );
            localStorage.clear();
          }
        }

        // Clear password fields before redirecting
        password.value = "";
        confirmPassword.value = "";
        loading.value = false;

        // AGGRESSIVE token removal: remove explicitly BEFORE clearing
        // This ensures token is gone even if clear() doesn't work
        try {
          localStorage.removeItem("jwt_token");
          delete localStorage.jwt_token;
        } catch (err) {
          // Ignore
        }

        // Completely clear all browser storage - this is a fresh setup
        // There's nothing to preserve, so clear everything
        try {
          localStorage.clear();
          sessionStorage.clear();
        } catch (err) {
          logger.error("Failed to clear browser storage:", err);
        }

        // AGGRESSIVE verification: check multiple times and force removal
        for (let i = 0; i < 5; i++) {
          const finalTokenCheck = localStorage.getItem("jwt_token");
          if (finalTokenCheck) {
            logger.error(
              `Token still exists after clear (attempt ${i + 1})! Forcing removal...`,
            );
            // Try every possible removal method
            try {
              localStorage.removeItem("jwt_token");
              delete localStorage.jwt_token;
              // If still exists, clear everything again
              if (localStorage.getItem("jwt_token")) {
                localStorage.clear();
                sessionStorage.clear();
              }
            } catch (e) {
              localStorage.clear();
            }
          } else {
            break; // Token is gone, exit loop
          }
        }

        // Final check: if token still exists, it's a critical error
        const ultimateCheck = localStorage.getItem("jwt_token");
        if (ultimateCheck) {
          logger.error(
            "CRITICAL: Token persists after all removal attempts! This is a bug.",
          );
          // Last resort: clear and log
          localStorage.clear();
          sessionStorage.clear();
        }

        // Explicitly delete session cookie (Flask session)
        // This must be done separately to ensure it's removed
        try {
          const expires = "Thu, 01 Jan 1970 00:00:00 GMT";
          const hostname = window.location.hostname;

          // Delete session cookie with all possible combinations
          document.cookie = `session=;expires=${expires};path=/`;
          document.cookie = `session=;expires=${expires};path=/;SameSite=Lax`;
          document.cookie = `session=;expires=${expires};path=/;SameSite=Strict`;
          if (hostname) {
            document.cookie = `session=;expires=${expires};path=/;domain=${hostname}`;
            if (hostname.indexOf(".") > 0) {
              document.cookie = `session=;expires=${expires};path=/;domain=.${hostname}`;
            }
          }
        } catch (err) {
          logger.error("Failed to clear session cookie:", err);
        }

        // FINAL check before setting flag: if token still exists, try one more aggressive removal
        const preRedirectCheck = localStorage.getItem("jwt_token");
        if (preRedirectCheck) {
          logger.error(
            "CRITICAL: Token exists right before redirect! Attempting final removal...",
          );
          // Try one last aggressive removal: save all keys except jwt_token, clear, restore
          try {
            const keysToKeep = {};
            for (let i = 0; i < localStorage.length; i++) {
              const key = localStorage.key(i);
              if (key && key !== "jwt_token") {
                keysToKeep[key] = localStorage.getItem(key);
              }
            }
            // Clear everything
            localStorage.clear();
            // Restore other keys (but NOT jwt_token)
            for (const [key, value] of Object.entries(keysToKeep)) {
              localStorage.setItem(key, value);
            }
            // Verify jwt_token is gone
            if (localStorage.getItem("jwt_token")) {
              // Still exists - clear everything as last resort
              logger.error(
                "Token still exists after selective clear! Clearing everything.",
              );
              localStorage.clear();
            }
          } catch (e) {
            localStorage.clear();
          }
        }

        // Set a flag in sessionStorage to indicate we're coming from setup
        // This must be set AFTER clearing, so it survives the redirect
        // This is more reliable than query params which can be lost
        try {
          sessionStorage.setItem("_setup_complete", "1");
        } catch (err) {
          logger.error("Failed to set setup flag:", err);
        }

        // Use window.location.replace instead of href to prevent back navigation
        // This ensures the login guard checks the actual state, not a stale one
        // Add a small delay to ensure storage operations complete
        setTimeout(() => {
          // One final check before redirect
          const finalPreRedirectCheck = localStorage.getItem("jwt_token");
          if (finalPreRedirectCheck) {
            logger.error(
              "Token exists at redirect time - guards must handle this",
            );
            // Try one more time
            localStorage.removeItem("jwt_token");
            delete localStorage.jwt_token;
            if (localStorage.getItem("jwt_token")) {
              localStorage.clear();
            }
          }
          window.location.replace("/login?setup=done");
        }, 100);
        return;
      } catch (err) {
        error.value = err.message || "Setup failed. Please try again.";
        logger.error("Setup error:", err);
        loading.value = false;
      }
    };

    const continueToLogin = () => {
      // Redirect to login
      setTimeout(() => {
        window.location.replace("/login?setup=done");
      }, 100);
    };

    const goToVerificationPage = () => {
      // Redirect to email verification page
      router.push({
        name: "EmailVerification",
        query: { email: email.value, user_id: createdUserId.value },
      });
    };

    const goToRestore = () => {
      currentSlide.value = 2;
      loadBackups();
    };

    const goBackToSetup = () => {
      currentSlide.value = 0;
      selectedBackupId.value = null;
      backupsError.value = null;
    };

    const loadBackups = async () => {
      loadingBackups.value = true;
      backupsError.value = null;
      try {
        // Ensure timezone is loaded before formatting dates
        if (timezone.value === "UTC") {
          try {
            if (configApi && typeof configApi.getConfig === "function") {
              const configData = await configApi.getConfig();
              if (configData.timezone) {
                timezone.value = configData.timezone;
              }
            } else {
              // Fallback to direct fetch if configApi is not available
              const response = await fetch("/api/v2/config", {
                method: "GET",
                credentials: "same-origin",
              });
              if (response.ok) {
                const configData = await response.json();
                if (configData.timezone) {
                  timezone.value = configData.timezone;
                }
              }
            }
          } catch (err) {
            // Use UTC as default if config fails
          }
        }
        const response = await admin.listDatabaseBackupsPublic();
        const allBackups = response.backups || [];

        // Filter duplicates by ID (keep first occurrence)
        // This handles cases where backups exist in both S3 and local storage
        const uniqueBackups = [];
        const seenIds = new Set();

        for (const backup of allBackups) {
          const backupId = String(backup.id);
          if (!seenIds.has(backupId)) {
            seenIds.add(backupId);
            uniqueBackups.push(backup);
          }
        }

        backups.value = uniqueBackups;
      } catch (err) {
        backupsError.value = err.message || "Failed to load backups";
        backups.value = [];
      } finally {
        loadingBackups.value = false;
      }
    };

    const selectBackup = (backupId) => {
      // Ensure we're comparing the same type and only select one backup
      // Convert both to string for consistent comparison
      const id = String(backupId);
      selectedBackupId.value = id;
    };

    const timezone = ref("UTC");

    const formatDate = (dateString) => {
      if (!dateString) return "Unknown";
      try {
        // Normalize the date string to ensure UTC interpretation
        let dateStr = String(dateString).trim();
        // Replace +00:00 with Z for better compatibility
        dateStr = dateStr.replace(/\+00:00$/, "Z");
        // If no timezone info, assume UTC
        if (!dateStr.endsWith("Z") && !dateStr.match(/[+-]\d{2}:\d{2}$/)) {
          dateStr = dateStr + "Z";
        }
        const date = new Date(dateStr);
        // Verify the date is valid
        if (isNaN(date.getTime())) {
          return "Invalid date";
        }
        // Format with the specified timezone
        return new Intl.DateTimeFormat("en-GB", {
          timeZone: timezone.value || "UTC",
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(date);
      } catch (err) {
        return "Invalid date";
      }
    };

    const formatSize = (bytes) => {
      if (!bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    const handleRestore = async () => {
      if (!selectedBackupId.value || restoring.value) return;

      restoring.value = true;
      restoreMessage.value = "Starting restore...";
      currentSlide.value = 3;

      try {
        await admin.restoreDatabaseBackupPublic(selectedBackupId.value);

        // Poll for restore completion
        restoreMessage.value = "Restoring database...";
        let attempts = 0;
        const maxAttempts = 120; // 2 minutes max

        const checkRestore = async () => {
          try {
            // First check restore status for errors
            try {
              const restoreStatus = await admin.getRestoreStatus();
              if (restoreStatus.error) {
                // Generic error message (backend error details are not exposed for security)
                throw new Error("Restore failed");
              }
              if (!restoreStatus.running) {
                // Restore finished, check if setup is complete
                const setupComplete = await auth.isSetupComplete();
                if (setupComplete) {
                  restoreMessage.value = "Restore completed successfully!";
                  setTimeout(() => {
                    window.location.replace("/login?restore=success");
                  }, 1500);
                  return;
                } else {
                  // Restore finished but setup not complete - likely failed
                  throw new Error("Restore failed");
                }
              }
            } catch (statusErr) {
              // If status check fails, it might be because restore is still running
              // Continue to check setup status as fallback
              if (statusErr.message && statusErr.message === "Restore failed") {
                throw statusErr;
              }
            }

            // Check if setup is complete (restore finished)
            const setupComplete = await auth.isSetupComplete();
            if (setupComplete) {
              restoreMessage.value = "Restore completed successfully!";
              setTimeout(() => {
                window.location.replace("/login?restore=success");
              }, 1500);
              return;
            }

            attempts++;
            if (attempts >= maxAttempts) {
              throw new Error("Restore timeout");
            }

            // Check again in 2 seconds
            setTimeout(checkRestore, 2000);
          } catch (err) {
            // Display generic error message (security: don't expose backend details)
            restoreMessage.value =
              "Restore failed. Please try again or select another backup.";
            setTimeout(() => {
              currentSlide.value = 2;
              restoring.value = false;
              restoreMessage.value = "Preparing restore...";
            }, 3000);
          }
        };

        // Start checking after a short delay
        setTimeout(checkRestore, 3000);
      } catch (err) {
        // Display generic error message (security: don't expose backend details)
        restoreMessage.value = "Failed to start restore. Please try again.";
        setTimeout(() => {
          currentSlide.value = 2;
          restoring.value = false;
          restoreMessage.value = "Preparing restore...";
        }, 3000);
      }
    };

    return {
      email,
      password,
      confirmPassword,
      error,
      loading,
      currentSlide,
      backups,
      loadingBackups,
      backupsError,
      selectedBackupId,
      restoring,
      restoreMessage,
      handleSetup,
      continueToLogin,
      goToVerificationPage,
      goToRestore,
      goBackToSetup,
      loadBackups,
      selectBackup,
      handleRestore,
      formatDate,
      formatSize,
      timezone,
    };
  },
};
</script>

<style scoped>
.setup-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  background: transparent;
}

.setup-container {
  width: 100%;
  max-width: 480px;
  padding: 3rem;

  overflow: hidden;
  position: relative;
}

.slides-container {
  position: relative;
  width: 100%;
  min-height: 400px;
}

.slide {
  width: 100%;
  animation-duration: 0.4s;
  animation-timing-function: ease-in-out;
}

.slide-form,
.slide-verification {
  display: flex;
  flex-direction: column;
}

/* Slide transitions */
.slide-enter-active {
  animation: slideInRight 0.4s ease-in-out;
}

.slide-leave-active {
  animation: slideOutLeft 0.4s ease-in-out;
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideOutLeft {
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(-100%);
    opacity: 0;
  }
}

.setup-header {
  text-align: center;
  margin-bottom: 2rem;
}

.setup-header h1 {
  margin: 0 0 0.5rem 0;
  color: #a9b7aa;
  font-size: 2rem;
  font-weight: 600;
}

.setup-subtitle {
  margin: 0;
  color: #a9b7aa;
  font-size: 1rem;
}

.setup-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.form-group label {
  color: #a9b7aa;
  font-size: 0.95rem;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.875rem 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: 1rem;
  transition: all 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: var(--accent);
  background: rgba(10, 10, 10, 0.8);
  box-shadow: 0 0 0 3px rgba(0, 66, 37, 0.1);
}

.form-group input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-hint {
  margin: 0;
  color: #a9b7aa;
  font-size: 0.85rem;
}

.error-message {
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

  color: #fca5a5;
  font-size: 0.95rem;
}

.btn-setup {
  width: 100%;
  padding: 1rem;
  margin-top: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
}

.btn-setup:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Password input wrapper styles */
.password-input-wrapper {
  position: relative;
  display: block;
  width: 100%;
  min-height: fit-content;
}

:deep(.password-input) {
  padding-right: 3rem !important;
  width: 100% !important;
  box-sizing: border-box !important;
  min-height: inherit;
  height: auto;
}

.password-toggle {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  margin-top: -12px;
  height: 24px;
  width: 24px;
  z-index: 10;
  transform: none !important;
}

.password-toggle:hover,
.password-toggle:active,
.password-toggle:focus {
  transform: none !important;
  margin-top: -12px !important;
}

/* Verification Slide Styles */
.verification-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  text-align: center;
}

.verification-icon {
  width: 64px;
  height: 64px;

  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  color: #a9b7aa;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.verification-info {
  width: 100%;
}

.verification-info p {
  color: #a9b7aa;
  line-height: 1.6;
  margin-bottom: 1rem;
  text-align: left;
}

.verification-info strong {
  color: #a9b7aa;
}

.verification-warning {
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);

  padding: 1rem;
  margin-top: 1rem;
  text-align: left;
}

.verification-warning strong {
  color: #fbbf24;
}

.verification-actions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
  margin-top: 1rem;
}

.btn-continue,
.btn-verify {
  width: 100%;
  padding: 0.875rem 1rem;

  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 1rem;
}

.btn-continue {
  background: transparent;
  color: #a9b7aa;
}

.btn-continue:hover {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.4);
}

.btn-verify {
  background: #004225;
  color: #a9b7aa;
}

.btn-verify:hover {
  background: #004225;
  color: #a9b7aa;
}

/* Restore Section Styles */
p {
  margin-top: 0rem;
  text-align: center;
  color: #a9b7aa;
}

p a {
  color: #d7d7d7;
  text-decoration: none;
}

p a:hover {
  text-decoration: underline;
}

.restore-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
  color: #a9b7aa;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #a9b7aa;
}

.empty-hint {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #a9b7aa;
}

.backups-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 400px;
  overflow-y: auto;
}

.backup-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid #004225;

  cursor: pointer;
  transition: all 0.2s;
}

.backup-item:hover {
  background: rgba(15, 23, 42, 0.7);
  border-color: rgba(56, 189, 248, 0.3);
}

.backup-item.selected {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.5);
}

.backup-info {
  flex: 1;
}

.backup-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.backup-type {
  font-size: 0.85rem;
  font-weight: 500;
  color: #a9b7aa;
  text-transform: capitalize;
}

.backup-status {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;

  font-weight: 500;
}

.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.backup-details {
  font-size: 0.85rem;
  color: #a9b7aa;
}

.backup-details div {
  margin: 0.25rem 0;
}

.backup-check {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #004225;
  font-size: 1.2rem;
  font-weight: bold;
}

.restore-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.btn-back,
.btn-restore-confirm {
  flex: 1;
  padding: 0.875rem 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1rem;
  border-radius: 4px;
}

.btn-back {
  background: transparent;
  color: #a9b7aa;
  border: 1px solid var(--border-color);
}

.btn-back:hover:not(:disabled) {
  background: rgba(15, 23, 42, 0.3);
  border-color: rgba(169, 183, 170, 0.5);
}

.btn-restore-confirm {
  background: #004225;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.btn-restore-confirm:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.9);
  border-color: rgba(0, 66, 37, 0.9);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 66, 37, 0.3);
}

.btn-back:disabled,
.btn-restore-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Restore Loading Styles */
.restore-loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
  padding: 3rem 2rem;
}

.spinner-large {
  width: 64px;
  height: 64px;
  border: 4px solid var(--accent);
  border-top-color: var(--ash-grey);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-message {
  color: #a9b7aa;
  font-size: 1.1rem;
  text-align: center;
}
</style>
