<template>
  <div class="invitation-wrapper">
    <div class="invitation-container">
      <h1>Accept Invitation</h1>
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="success" class="success">{{ success }}</div>

      <div v-if="loading" class="loading">Loading invitation...</div>
      <div v-else-if="!invitation" class="error">
        Invitation not found or invalid.
      </div>
      <div v-else-if="!accepted">
        <p class="info-text">
          You have been invited to join Leyzen Vault. Please set a password to
          complete your account creation.
        </p>

        <form @submit.prevent="handleAcceptInvitation">
          <div class="form-group">
            <label for="password">Password:</label>
            <PasswordInput
              id="password"
              v-model="password"
              autocomplete="new-password"
              :minlength="12"
              required
              :disabled="accepting"
              placeholder="Enter password (min 12 characters)"
            />
          </div>
          <div class="form-group">
            <label for="confirm-password">Confirm Password:</label>
            <PasswordInput
              id="confirm-password"
              v-model="confirmPassword"
              autocomplete="new-password"
              required
              :disabled="accepting"
              placeholder="Confirm password"
            />
          </div>
          <button type="submit" :disabled="accepting" class="btn btn-primary">
            {{ accepting ? "Creating account..." : "Accept Invitation" }}
          </button>
        </form>
      </div>
      <div v-else class="accepted-section">
        <div class="success-icon">✓</div>
        <h2>Account created successfully!</h2>
        <p>
          Your account has been created. You will receive a verification email
          shortly. Please verify your email before logging in.
        </p>
        <router-link to="/login" class="btn btn-primary"
          >Go to Login</router-link
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { auth } from "../services/api";
import PasswordInput from "../components/PasswordInput.vue";

const router = useRouter();
const route = useRoute();

const token = ref(route.params.token || route.query.token || "");
const invitation = ref(null);
const password = ref("");
const confirmPassword = ref("");
const loading = ref(true);
const accepting = ref(false);
const error = ref("");
const success = ref("");
const accepted = ref(false);

onMounted(async () => {
  if (!token.value) {
    error.value = "Invalid invitation token";
    loading.value = false;
    return;
  }

  try {
    const response = await fetch(
      `/api/auth/invitations/accept/${token.value}`,
      {
        method: "GET",
      },
    );
    if (response.ok) {
      invitation.value = await response.json();
    } else {
      const errorData = await response.json();
      error.value = errorData.error || "Invalid invitation";
    }
  } catch (err) {
    error.value = "Failed to load invitation";
  } finally {
    loading.value = false;
  }
});

const handleAcceptInvitation = async () => {
  if (!token.value) {
    error.value = "Invalid invitation token";
    return;
  }

  if (password.value !== confirmPassword.value) {
    error.value = "Passwords do not match";
    return;
  }

  if (password.value.length < 12) {
    error.value = "Password must be at least 12 characters long";
    return;
  }

  accepting.value = true;
  error.value = "";
  success.value = "";

  try {
    const response = await fetch(
      `/api/auth/invitations/accept/${token.value}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password: password.value }),
      },
    );

    if (response.ok) {
      const data = await response.json();
      accepted.value = true;
      success.value = "Account created successfully!";
      password.value = "";
      confirmPassword.value = "";

      // Redirect to email verification page with email
      // The backend sends verification email automatically, so redirect to verification page
      if (data.user && data.user.email) {
        // Redirect to email verification page with email
        setTimeout(() => {
          router.push({
            name: "EmailVerification",
            query: { email: data.user.email },
          });
        }, 2000);
      } else if (invitation.value && invitation.value.email) {
        // Fallback: use email from invitation
        setTimeout(() => {
          router.push({
            name: "EmailVerification",
            query: { email: invitation.value.email },
          });
        }, 2000);
      }
    } else {
      const errorData = await response.json();
      error.value = errorData.error || "Failed to accept invitation";
    }
  } catch (err) {
    error.value = "Failed to accept invitation. Please try again.";
  } finally {
    accepting.value = false;
  }
};
</script>

<style scoped>
.invitation-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.invitation-container {
  max-width: 500px;
  width: 100%;
  padding: 2.5rem;
}

h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: #a9b7aa;
  font-size: 1.75rem;
  font-weight: 600;
}

h2 {
  text-align: center;
  margin-bottom: 1rem;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
}

.info-text {
  text-align: center;
  margin-bottom: 2rem;
  color: #a9b7aa;
  line-height: 1.6;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #a9b7aa;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
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

.btn {
  width: 100%;
  padding: 0.75rem 1.5rem;
  border: none;

  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 1rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: transparent;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.btn-primary:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
  border-color: #004225;
}

.accepted-section {
  text-align: center;
  padding: 2rem 0;
}

.success-icon {
  font-size: 4rem;
  color: #86efac;
  margin-bottom: 1rem;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

  margin-bottom: 1rem;
}

.success {
  color: #86efac;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);

  margin-bottom: 1rem;
}

.loading {
  color: #a9b7aa;
  text-align: center;
  padding: 2rem;
}

.accepted-section p {
  color: #a9b7aa;
  margin-bottom: 2rem;
  line-height: 1.6;
}
</style>
