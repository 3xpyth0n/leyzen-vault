<template>
  <div class="callback-wrapper">
    <div class="callback-container glass glass-card">
      <div v-if="loading" class="loading-state">
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
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { auth } from "../services/api";
import { clearUserMasterKey } from "../services/keyManager";
import { logger } from "../utils/logger.js";

const router = useRouter();
const route = useRoute();
const loading = ref(true);
const error = ref("");

onMounted(async () => {
  try {
    // Check for error in query parameters (e.g., from SSO callback failure)
    if (route.query.error) {
      error.value = decodeURIComponent(route.query.error);
      loading.value = false;
      return;
    }

    // Get token and user_id from query parameters
    const token = route.query.token;
    const userId = route.query.user_id;

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
.success-state {
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
