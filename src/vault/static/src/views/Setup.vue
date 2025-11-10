<template>
  <div class="setup-wrapper">
    <div class="setup-container glass glass-card">
      <div class="setup-header">
        <h1>Leyzen Vault Setup</h1>
        <p class="setup-subtitle">
          Welcome! Let's create your administrator account to get started.
        </p>
      </div>

      <form @submit.prevent="handleSetup" class="setup-form">
        <div v-if="error" class="error-message glass">
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
            Must be at least 12 characters with uppercase, lowercase, and digits
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
          {{ loading ? "Creating Account..." : "Create Administrator Account" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { auth } from "../services/api";
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

    onMounted(async () => {
      // Check if setup is already complete
      try {
        const setupComplete = await auth.isSetupComplete();
        if (setupComplete) {
          // Setup already complete, redirect to login
          router.push("/login");
        }
      } catch (err) {
        logger.error("Failed to check setup status:", err);
        // Continue with setup if check fails
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

        if (response.token) {
          // Setup successful, redirect to dashboard
          router.push("/dashboard");
        }
      } catch (err) {
        error.value = err.message || "Setup failed. Please try again.";
        logger.error("Setup error:", err);
      } finally {
        loading.value = false;
      }
    };

    return {
      email,
      password,
      confirmPassword,
      error,
      loading,
      handleSetup,
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
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
}

.setup-container {
  width: 100%;
  max-width: 480px;
  padding: 3rem;
  border-radius: 1.5rem;
}

.setup-header {
  text-align: center;
  margin-bottom: 2rem;
}

.setup-header h1 {
  margin: 0 0 0.5rem 0;
  color: #e6eef6;
  font-size: 2rem;
  font-weight: 600;
}

.setup-subtitle {
  margin: 0;
  color: #94a3b8;
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
}

.form-group label {
  color: #e6eef6;
  font-size: 0.95rem;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.875rem 1rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  color: #e6eef6;
  font-size: 1rem;
  transition: all 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: #38bdf8;
  background: rgba(15, 23, 42, 0.7);
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
}

.form-group input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-hint {
  margin: 0;
  color: #94a3b8;
  font-size: 0.85rem;
}

.error-message {
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.5rem;
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
</style>
