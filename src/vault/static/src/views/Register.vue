<template>
  <div class="register-wrapper">
    <div class="register-content">
      <h1>Create Account</h1>
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="ssoRequired && ssoProvider" class="sso-required-message">
        <p>
          This email domain requires authentication via {{ ssoProvider.name }}.
          Please sign in with {{ ssoProvider.name }} instead.
        </p>
        <button
          type="button"
          class="sso-button"
          :disabled="ssoLoading"
          @click="handleSSOLogin(ssoProvider.id)"
        >
          {{
            ssoLoading ? "Connecting..." : `Sign in with ${ssoProvider.name}`
          }}
        </button>
      </div>
      <form v-if="!ssoRequired" @submit.prevent="handleRegister">
        <input
          v-model="email"
          type="email"
          placeholder="Email"
          autocomplete="email"
          required
          :disabled="loading"
        />
        <PasswordInput
          v-model="password"
          id="password"
          placeholder="Password (min 12 characters)"
          autocomplete="new-password"
          :minlength="12"
          required
          :disabled="loading"
        />
        <PasswordInput
          v-model="confirmPassword"
          id="confirm-password"
          placeholder="Confirm Password"
          autocomplete="new-password"
          required
          :disabled="loading"
        />
        <button type="submit" :disabled="loading">
          {{ loading ? "Creating account..." : "Register" }}
        </button>
      </form>
      <p>
        Already have an account?
        <router-link to="/login">Login here</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { auth, vaultspaces, sso } from "../services/api";
import {
  initializeUserMasterKey,
  createVaultSpaceKey,
  getUserMasterKey,
} from "../services/keyManager";
import { logger } from "../utils/logger.js";
import PasswordInput from "../components/PasswordInput.vue";

const router = useRouter();
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const loading = ref(false);
const ssoLoading = ref(false);
const error = ref("");
const ssoRequired = ref(false);
const ssoProvider = ref(null);

// Debounce function for email domain checking
let emailCheckTimeout = null;

// Watch email input to check for SSO requirement
watch(email, (newEmail) => {
  // Clear previous timeout
  if (emailCheckTimeout) {
    clearTimeout(emailCheckTimeout);
  }

  // Reset SSO state
  ssoRequired.value = false;
  ssoProvider.value = null;

  // Check if email is valid and contains @
  if (newEmail && newEmail.includes("@") && newEmail.length > 3) {
    // Debounce the check
    emailCheckTimeout = setTimeout(async () => {
      try {
        const domainInfo = await sso.checkDomain(newEmail);
        if (domainInfo.requires_sso && domainInfo.provider) {
          ssoRequired.value = true;
          ssoProvider.value = domainInfo.provider;
        }
      } catch (err) {
        // Don't show error, just log it
        logger.error("Failed to check domain for SSO:", err);
      }
    }, 500); // Wait 500ms after user stops typing
  }
});

onMounted(async () => {
  // Check if signup is enabled
  const signupEnabled = await auth.isSignupEnabled();
  if (!signupEnabled) {
    error.value =
      "Public registration is disabled. Contact an administrator for an invitation.";
    // Redirect to login after 3 seconds
    setTimeout(() => {
      router.push("/login");
    }, 3000);
  }
  // SSO providers are not shown on registration page
  // Users must register with password first, then can use SSO to login
});

const handleRegister = async () => {
  error.value = "";

  // Validate password match
  if (password.value !== confirmPassword.value) {
    error.value = "Passwords do not match";
    return;
  }

  // Validate password length
  if (password.value.length < 12) {
    error.value = "Password must be at least 12 characters long";
    return;
  }

  // Validate password complexity
  const hasUpper = /[A-Z]/.test(password.value);
  const hasLower = /[a-z]/.test(password.value);
  const hasDigit = /[0-9]/.test(password.value);

  if (!hasUpper || !hasLower || !hasDigit) {
    error.value =
      "Password must contain at least one uppercase letter, one lowercase letter, and one digit";
    return;
  }

  loading.value = true;

  try {
    // Signup first to get the server-generated salt
    const response = await auth.signup(email.value, password.value);

    // Check if email verification is required
    if (response.email_verification_required) {
      // Clear password from memory
      password.value = "";
      confirmPassword.value = "";

      // Redirect to email verification page
      router.push({
        name: "EmailVerification",
        query: { email: email.value, user_id: response.user?.id },
      });
      return;
    }

    if (response.token) {
      // Get salt from server response (base64-encoded)
      // The server generates a persistent salt for this user
      const saltBase64 = response.user?.master_key_salt;
      let salt = null;

      if (saltBase64) {
        // Decode base64 salt to Uint8Array
        try {
          const saltStr = atob(saltBase64);
          salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));
        } catch (e) {
          logger.error("Failed to decode salt from server:", e);
          error.value = "Failed to decode salt from server";
          return;
        }
      } else {
        error.value = "Server did not return salt";
        return;
      }

      // Initialize user master key with the server's persistent salt
      // Pass JWT token so the key can be stored encrypted in IndexedDB
      await initializeUserMasterKey(password.value, salt, response.token);

      // Create Personal VaultSpace key and encrypt it with the correct master key
      const { encryptedKey } = await createVaultSpaceKey(
        await getUserMasterKey(),
      );

      // Store the encrypted VaultSpace key on the server
      if (response.personal_vaultspace?.id) {
        await vaultspaces.share(
          response.personal_vaultspace.id,
          response.user.id,
          encryptedKey,
        );
      }

      // Clear password from memory
      password.value = "";
      confirmPassword.value = "";

      // Redirect to dashboard after successful registration
      router.push("/dashboard");
    }
  } catch (err) {
    error.value = err.message || "Registration failed. Please try again.";
    // Check if error is about SSO requirement
    if (
      err.message &&
      (err.message.includes("requires SSO") ||
        err.message.includes("SSO authentication"))
    ) {
      // Try to get the provider info from the error or check domain again
      try {
        const domainInfo = await sso.checkDomain(email.value);
        if (domainInfo.requires_sso && domainInfo.provider) {
          ssoRequired.value = true;
          ssoProvider.value = domainInfo.provider;
        }
      } catch (checkErr) {
        logger.error("Failed to check domain after error:", checkErr);
      }
    }
  } finally {
    loading.value = false;
  }
};

const handleSSOLogin = async (providerId) => {
  error.value = "";
  ssoLoading.value = true;

  try {
    const returnUrl = window.location.origin + "/dashboard";
    const redirectUrl = await sso.initiateLogin(providerId, returnUrl);
    // Redirect to SSO provider
    window.location.href = redirectUrl;
  } catch (err) {
    error.value =
      err.message || "Failed to initiate SSO login. Please try again.";
    ssoLoading.value = false;
  }
};
</script>

<style scoped>
.register-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.register-content {
  max-width: 600px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

h1 {
  text-align: center;
  margin-bottom: 3rem;
  color: #e6eef6;
  font-size: 3rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  background: linear-gradient(135deg, #e6eef6 0%, #cbd5e1 50%, #94a3b8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: 0 4px 20px rgba(230, 238, 246, 0.3);
  margin-top: 0;
}

form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  background: rgba(13, 17, 23, 0.5);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

input:focus {
  outline: none;
  border-color: #58a6ff;
}

input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button[type="submit"] {
  width: 100%;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #8b5cf6 0%, #818cf8 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

button[type="submit"]:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.4);
}

button[type="submit"]:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

p {
  text-align: center;
  margin-top: 1.5rem;
  color: #94a3b8;
  width: 100%;
}

p a {
  color: #58a6ff;
  text-decoration: none;
}

p a:hover {
  text-decoration: underline;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
  width: 100%;
  text-align: center;
}

.sso-required-message {
  padding: 1rem;
  background: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 8px;
  margin-bottom: 1.5rem;
  text-align: center;
  width: 100%;
}

.sso-required-message p {
  color: #58a6ff;
  margin: 0 0 1rem 0;
  font-size: 0.95rem;
}

.sso-button {
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(88, 166, 255, 0.2);
  border: 1px solid rgba(88, 166, 255, 0.5);
  border-radius: 8px;
  color: #58a6ff;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.sso-button:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.3);
  border-color: rgba(88, 166, 255, 0.7);
}

.sso-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
