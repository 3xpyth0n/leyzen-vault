<template>
  <div class="register-wrapper">
    <div class="register-container glass glass-card">
      <h1>Create Account</h1>
      <div v-if="error" class="error">{{ error }}</div>
      <form @submit.prevent="handleRegister">
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
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { auth, vaultspaces } from "../services/api";
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
const error = ref("");

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
  } finally {
    loading.value = false;
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

.register-container {
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

p {
  text-align: center;
  margin-top: 1.5rem;
  color: #94a3b8;
}
</style>
