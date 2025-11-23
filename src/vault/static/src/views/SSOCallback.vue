<template>
  <div class="callback-wrapper">
    <div class="callback-container glass glass-card">
      <div v-if="show2FAModal" class="two-factor-state">
        <h2>Two-Factor Authentication Required</h2>
        <p>Please verify your identity to complete the login.</p>
      </div>
      <div v-else-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Completing authentication...</p>
      </div>
      <div v-else-if="error" class="error-state">
        <h2>Authentication Failed</h2>
        <p class="error-message">{{ error }}</p>
        <router-link to="/login" class="back-link">
          Return to login
        </router-link>
      </div>
      <div v-else class="success-state">
        <h2>Authentication Successful</h2>
        <p>Redirecting to dashboard...</p>
      </div>
    </div>

    <!-- Two-Factor Authentication Modal -->
    <TwoFactorVerify
      v-if="show2FAModal"
      :isLoading="twoFactorLoading"
      :error="twoFactorError"
      @verify="handle2FAVerify"
      @cancel="cancel2FA"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { auth, sso } from "../services/api";
import { clearUserMasterKey } from "../services/keyManager";
import { logger } from "../utils/logger.js";
import TwoFactorVerify from "../components/TwoFactorVerify.vue";

const router = useRouter();
const route = useRoute();
const loading = ref(true);
const error = ref("");
const show2FAModal = ref(false);
const twoFactorLoading = ref(false);
const twoFactorError = ref("");

onMounted(async () => {
  try {
    // Check for error in query parameters (e.g., from SSO callback failure)
    if (route.query.error) {
      error.value = decodeURIComponent(route.query.error);
      loading.value = false;
      return;
    }

    // Check if 2FA is required
    const requires2FA = route.query.requires_2fa === "true";
    const userId = route.query.user_id;

    if (requires2FA) {
      // Show 2FA modal
      if (!userId) {
        error.value = "Missing user information. Please try logging in again.";
        loading.value = false;
        return;
      }
      show2FAModal.value = true;
      loading.value = false;
      return;
    }

    // Normal SSO flow - get token and user_id from query parameters
    const token = route.query.token;

    if (!token || !userId) {
      error.value =
        "Missing authentication token. Please try logging in again.";
      loading.value = false;
      return;
    }

    // Store token
    localStorage.setItem("jwt_token", token);

    // Clear any existing master key (SSO users don't have passwords)
    await clearUserMasterKey();

    // Get user info to verify authentication
    try {
      const user = await auth.getCurrentUser();
      if (!user || user.id !== userId) {
        throw new Error("User verification failed");
      }

      // For SSO users, we don't have a master key derived from password
      // They will need to set up their master key separately if needed
      // For now, just redirect to dashboard
      // The system will handle SSO users appropriately

      // Small delay to show success message
      setTimeout(() => {
        router.push("/dashboard");
      }, 1000);
    } catch (userErr) {
      logger.error("Failed to verify user after SSO:", userErr);
      error.value = "Failed to verify authentication. Please try again.";
      loading.value = false;
      // Clear token on error
      localStorage.removeItem("jwt_token");
    }
  } catch (err) {
    logger.error("SSO callback error:", err);
    error.value = err.message || "An error occurred during authentication.";
    loading.value = false;
    // Clear token on error
    localStorage.removeItem("jwt_token");
  }
});

const handle2FAVerify = async (totpToken) => {
  twoFactorError.value = "";
  twoFactorLoading.value = true;

  try {
    const response = await sso.verify2FA(totpToken);

    if (response.token) {
      show2FAModal.value = false;

      // Clear any existing master key (SSO users don't have passwords)
      await clearUserMasterKey();

      // Get user info to verify authentication
      try {
        const user = await auth.getCurrentUser();
        if (!user) {
          throw new Error("User verification failed");
        }

        // Small delay to show success message
        setTimeout(() => {
          router.push("/dashboard");
        }, 1000);
      } catch (userErr) {
        logger.error("Failed to verify user after SSO 2FA:", userErr);
        error.value = "Failed to verify authentication. Please try again.";
        twoFactorLoading.value = false;
        // Clear token on error
        localStorage.removeItem("jwt_token");
      }
    }
  } catch (err) {
    twoFactorError.value =
      err.message || "Verification failed. Please try again.";
    twoFactorLoading.value = false;
  }
};

const cancel2FA = () => {
  show2FAModal.value = false;
  twoFactorError.value = "";
  router.push("/login");
};
</script>

<style scoped>
.callback-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.callback-container {
  max-width: 400px;
  width: 100%;
  padding: 2.5rem;
  text-align: center;
}

.loading-state,
.error-state,
.success-state,
.two-factor-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(148, 163, 184, 0.2);
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

h2 {
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

p {
  color: #94a3b8;
  margin: 0;
}

.error-message {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin: 1rem 0;
}

.back-link {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.95rem;
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 6px;
  transition: all 0.2s;
}

.back-link:hover {
  background: rgba(88, 166, 255, 0.1);
  border-color: rgba(88, 166, 255, 0.5);
}
</style>
