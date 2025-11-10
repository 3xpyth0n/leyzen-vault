<template>
  <div class="login-wrapper">
    <div class="login-container glass glass-card">
      <h1>Leyzen Vault Login</h1>
      <div v-if="error" class="error">
        {{ error }}
        <div v-if="showVerificationLink" class="verification-link">
          <router-link
            :to="{
              name: 'EmailVerification',
              query: { email: emailForVerification },
            }"
          >
            Verify my email
          </router-link>
        </div>
      </div>
      <form @submit.prevent="handleLogin">
        <input
          v-model="username"
          type="text"
          placeholder="Username or Email"
          autocomplete="username"
          required
          :disabled="loading"
        />
        <PasswordInput
          v-model="password"
          id="password"
          placeholder="Password"
          autocomplete="current-password"
          required
          :disabled="loading"
        />
        <div class="captcha-section">
          <div class="captcha-image-wrapper">
            <img
              :src="captchaImageUrl"
              alt="CAPTCHA"
              class="captcha-image"
              @click="refreshCaptcha"
            />
            <button
              type="button"
              class="captcha-refresh"
              @click="refreshCaptcha"
              :disabled="loading"
            >
              ↻
            </button>
          </div>
          <input
            v-model="captchaResponse"
            type="text"
            placeholder="Enter CAPTCHA"
            required
            :disabled="loading"
            class="captcha-input"
          />
        </div>
        <button type="submit" :disabled="loading">
          {{ loading ? "Logging in..." : "Login" }}
        </button>
      </form>
      <p v-if="signupEnabled">
        Don't have an account?
        <router-link to="/register">Register here</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { auth } from "../services/api";
import {
  initializeUserMasterKey,
  clearUserMasterKey,
} from "../services/keyManager";
import { logger } from "../utils/logger.js";
import PasswordInput from "../components/PasswordInput.vue";

const router = useRouter();
const username = ref("");
const password = ref("");
const captchaResponse = ref("");
const captchaNonce = ref("");
const loading = ref(false);
const error = ref("");
const showVerificationLink = ref(false);
const emailForVerification = ref("");
const signupEnabled = ref(true);

const captchaImageUrl = ref("");

const refreshCaptcha = async () => {
  try {
    // Request a new captcha using the refresh endpoint to get the nonce
    const response = await fetch("/api/auth/captcha-refresh", {
      method: "POST",
      credentials: "same-origin", // Include cookies (session) in request
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      if (data.nonce) {
        captchaNonce.value = data.nonce;
      }
      if (data.image_url) {
        // Append cache-busting parameter using & if URL already has params, ? otherwise
        const separator = data.image_url.includes("?") ? "&" : "?";
        captchaImageUrl.value = `${data.image_url}${separator}t=${Date.now()}`;
      } else {
        // Fallback: use default captcha image URL with nonce if available
        if (captchaNonce.value) {
          captchaImageUrl.value = `/api/auth/captcha-image?nonce=${captchaNonce.value}&t=${Date.now()}`;
        } else {
          captchaImageUrl.value = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
        }
      }
    } else {
      // Fallback: use default captcha image URL if refresh fails
      if (captchaNonce.value) {
        captchaImageUrl.value = `/api/auth/captcha-image?nonce=${captchaNonce.value}&t=${Date.now()}`;
      } else {
        captchaImageUrl.value = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
        captchaNonce.value = ""; // Clear nonce on error
      }
    }
  } catch (error) {
    // Fallback: use default captcha image URL on error
    captchaImageUrl.value = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
    captchaNonce.value = ""; // Clear nonce on error
    logger.error("Failed to refresh CAPTCHA:", error);
  }
  // Clear the captcha response input
  captchaResponse.value = "";
};

onMounted(async () => {
  refreshCaptcha();
  // Check if signup is enabled
  signupEnabled.value = await auth.isSignupEnabled();
});

const handleLogin = async () => {
  error.value = "";
  loading.value = true;

  try {
    // Pass the nonce if available, otherwise backend will use session-based captcha
    const response = await auth.login(
      username.value,
      password.value,
      captchaNonce.value || "", // Use nonce if available, otherwise empty (session-based)
      captchaResponse.value,
    );
    if (response.token) {
      // Clear any existing master key and salt before initializing a new one
      // This ensures a clean state after logout/login
      await clearUserMasterKey();

      // Get salt from server response (base64-encoded)
      // The salt is persistent per user and ensures the same master key is derived each session
      const saltBase64 = response.user?.master_key_salt;
      let salt = null;

      if (saltBase64) {
        // Decode base64 salt to Uint8Array
        try {
          const saltStr = atob(saltBase64);
          salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));
        } catch (e) {
          logger.error("Failed to decode salt from server:", e);
          // Fallback: generate new salt (but this will cause issues with existing VaultSpace keys)
          salt = null;
        }
      }

      // Initialize user master key from password using the salt from server
      // Pass JWT token so the key can be stored encrypted in IndexedDB
      // This ensures the same master key is derived each session and persists across page refreshes
      await initializeUserMasterKey(password.value, salt, response.token);

      // Clear password from memory
      password.value = "";

      // Redirect to dashboard after successful login
      router.push("/dashboard");
    }
  } catch (err) {
    error.value = err.message || "Login failed. Please try again.";
    // Check if error is about unverified email
    if (err.message && err.message.includes("not verified")) {
      showVerificationLink.value = true;
      emailForVerification.value = username.value;
    } else {
      showVerificationLink.value = false;
    }
    refreshCaptcha();
    captchaResponse.value = "";
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.login-container {
  max-width: 400px;
  width: 100%;
  padding: 2.5rem;
}

h1 {
  text-align: center;
  margin-bottom: 2rem;
  color: #e6eef6;
  font-size: 1.75rem;
  font-weight: 600;
}

form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

input {
  width: 100%;
  box-sizing: border-box;
}

.captcha-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.captcha-image-wrapper {
  position: relative;
  display: inline-block;
  cursor: pointer;
}

.captcha-image {
  width: 100%;
  height: auto;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.captcha-refresh {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: rgba(0, 0, 0, 0.6);
  color: #e6eef6;
  border: none;
  border-radius: 4px;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.25rem;
  padding: 0;
}

.captcha-refresh:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.8);
}

.captcha-input {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: monospace;
}

p {
  text-align: center;
  margin-top: 1.5rem;
  color: #94a3b8;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.verification-link {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(239, 68, 68, 0.3);
}

.verification-link a {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.9rem;
}

.verification-link a:hover {
  text-decoration: underline;
}
</style>
