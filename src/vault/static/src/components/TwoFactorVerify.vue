<template>
  <div class="two-factor-verify-overlay" @click.self="$emit('cancel')">
    <div class="two-factor-verify-modal">
      <div class="fa-modal-title">
        <h3>Two-Factor Authentication</h3>
        <button
          @click="$emit('cancel')"
          class="close-button"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      <div class="modal-body">
        <p class="description">
          Enter the 6-digit code from your authenticator app
          <template v-if="!showBackupInput">
            or
            <button @click="showBackupInput = true" class="link-button">
              use a backup code
            </button>
          </template>
        </p>

        <div v-if="!showBackupInput" class="code-input-section">
          <input
            ref="codeInput"
            v-model="verificationCode"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            maxlength="6"
            placeholder="000000"
            class="verification-input"
            @input="formatVerificationCode"
            @keyup.enter="verify"
            autofocus
          />
        </div>

        <div v-else class="backup-input-section">
          <p class="backup-description">
            Enter one of your backup recovery codes:
          </p>
          <input
            ref="backupInput"
            v-model="backupCode"
            type="text"
            placeholder="XXXX-XXXX"
            class="backup-input"
            @input="formatBackupCode"
            @keyup.enter="verify"
            autofocus
          />
          <button @click="showBackupInput = false" class="link-button">
            Use authenticator app instead
          </button>
        </div>

        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </div>

      <div class="modal-footer">
        <button @click="$emit('cancel')" class="btn btn-secondary">
          Cancel
        </button>
        <button
          @click="verify"
          class="btn btn-primary"
          :disabled="!canVerify || isLoading"
        >
          {{ isLoading ? "Verifying..." : "Verify" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "TwoFactorVerify",
  props: {
    isLoading: {
      type: Boolean,
      default: false,
    },
    error: {
      type: String,
      default: "",
    },
  },
  emits: ["verify", "cancel"],
  data() {
    return {
      verificationCode: "",
      backupCode: "",
      showBackupInput: false,
      errorMessage: this.error,
    };
  },
  computed: {
    canVerify() {
      if (this.showBackupInput) {
        // Backup code format: XXXX-XXXX (9 chars with dash)
        const normalized = this.backupCode.replace(/\s/g, "");
        return normalized.length === 8 || normalized.length === 9;
      } else {
        return this.verificationCode.length === 6;
      }
    },
  },
  watch: {
    error(newVal) {
      this.errorMessage = newVal;
    },
    showBackupInput(newVal) {
      // Focus the appropriate input when switching
      this.$nextTick(() => {
        if (newVal) {
          this.$refs.backupInput?.focus();
        } else {
          this.$refs.codeInput?.focus();
        }
      });
    },
  },
  mounted() {
    // Auto-focus the code input
    this.$nextTick(() => {
      this.$refs.codeInput?.focus();
    });
  },
  methods: {
    formatVerificationCode(event) {
      // Only allow digits
      this.verificationCode = event.target.value.replace(/\D/g, "");
      this.errorMessage = "";
    },
    formatBackupCode(event) {
      // Allow digits and dashes
      let value = event.target.value.replace(/[^0-9-]/g, "");

      // Auto-format: XXXX-XXXX
      if (value.length > 4 && !value.includes("-")) {
        value = value.slice(0, 4) + "-" + value.slice(4, 8);
      }

      this.backupCode = value;
      this.errorMessage = "";
    },
    verify() {
      if (!this.canVerify || this.isLoading) {
        return;
      }

      const token = this.showBackupInput
        ? this.backupCode.replace(/\s/g, "")
        : this.verificationCode;

      this.$emit("verify", token);
    },
  },
};
</script>

<style scoped>
.two-factor-verify-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay-bg, rgba(0, 0, 0, 0.6));
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.two-factor-verify-modal {
  background: var(--bg-modal);
  border: 1px solid var(--border-color);
  max-width: 450px;
  width: 90%;
  overflow: hidden;
}

.fa-modal-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary);
  font-weight: 600;
}

.close-button {
  background: none;
  border: none;
  font-size: 1.75rem;
  line-height: 1;
  color: var(--text-primary);
  cursor: pointer;
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.close-button:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 2rem;
}

.description {
  margin-bottom: 1.5rem;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.5;
  font-size: 0.95rem;
}

.backup-description {
  margin-bottom: 1rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  text-align: center;
}

.code-input-section,
.backup-input-section {
  text-align: center;
}

.verification-input {
  max-width: 200px;
  width: 100%;
  padding: 0.75rem;
  margin-top: 1rem;
  font-size: 1.5rem;
  text-align: center;
  letter-spacing: 0.3em;
  border: 1px solid var(--border-color);
  font-family: "Courier New", monospace;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition:
    border-color 0.2s,
    background 0.2s;
  box-sizing: border-box;
}

.verification-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-primary);
}

.backup-input {
  max-width: 180px;
  width: 100%;
  padding: 0.75rem;
  font-size: 1.2rem;
  text-align: center;
  letter-spacing: 0.2em;
  border: 1px solid var(--border-color);
  font-family: "Courier New", monospace;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition:
    border-color 0.2s,
    background 0.2s;
  margin-bottom: 0;
  box-sizing: border-box;
}

.backup-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-primary);
}

.backup-input-section .link-button {
  margin-top: 1rem;
  display: block;
}

.link-button {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
  font-size: 0.9rem;
  text-decoration: underline;
  transition: color 0.2s;
}

.link-button:hover {
  color: var(--accent);
}

.error-message {
  color: var(--error);
  margin-top: 1rem;
  font-size: 0.9rem;
  text-align: center;
  background: rgba(239, 68, 68, 0.1);
  padding: 0.75rem;
  border: 1px solid var(--error);
}

.modal-footer {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding: 1.5rem;
  border-top: 1px solid var(--border-color);
}
</style>
