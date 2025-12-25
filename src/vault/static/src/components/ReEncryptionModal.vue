<template>
  <teleport to="body">
    <div
      v-if="show"
      class="modal-overlay"
      role="dialog"
      aria-labelledby="reencryption-modal-title"
      aria-modal="true"
    >
      <div class="modal-container" @click.stop>
        <div class="modal-content">
          <!-- Main content -->
          <div class="modal-body">
            <!-- Spinner -->
            <div class="spinner-container" v-if="!error">
              <div class="spinner"></div>
            </div>

            <!-- Error icon -->
            <div class="error-icon" v-if="error">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>

            <!-- Title -->
            <h2 id="reencryption-modal-title" class="modal-title">
              {{ error ? "Re-encryption Failed" : "Re-encrypting Keys" }}
            </h2>

            <!-- Current step -->
            <p class="current-step">{{ currentStep }}</p>

            <!-- VaultSpace name (if available) -->
            <p class="vaultspace-name" v-if="vaultspaceName && !error">
              {{ vaultspaceName }}
            </p>

            <!-- Progress percentage -->
            <div class="progress-info" v-if="!error">
              <span class="progress-percentage">{{ progress }}%</span>
              <span class="progress-count" v-if="totalCount > 0">
                ({{ currentIndex + 1 }} / {{ totalCount }})
              </span>
            </div>

            <!-- Error message -->
            <p class="error-message" v-if="error">{{ error }}</p>

            <!-- Cancel button (only show if not in error state and not complete) -->
            <div class="modal-actions" v-if="!error && progress < 100">
              <button
                class="cancel-btn"
                @click="handleCancel"
                :disabled="progress >= 100"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "ReEncryptionModal",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    progress: {
      type: Number,
      default: 0,
      validator: (value) => value >= 0 && value <= 100,
    },
    currentStep: {
      type: String,
      default: "Processing...",
    },
    vaultspaceName: {
      type: String,
      default: null,
    },
    currentIndex: {
      type: Number,
      default: 0,
    },
    totalCount: {
      type: Number,
      default: 0,
    },
    error: {
      type: String,
      default: null,
    },
  },
  emits: ["cancel"],
  watch: {
    show(newVal) {
      if (newVal) {
        document.body.style.overflow = "hidden";
      } else {
        document.body.style.overflow = "";
      }
    },
  },
  methods: {
    handleCancel() {
      this.$emit("cancel");
    },
  },
  beforeUnmount() {
    document.body.style.overflow = "";
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.7);
  animation: fadeIn 0.3s ease;
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .modal-overlay {
  padding: 1rem !important;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-container {
  position: relative;
  width: 100%;
  max-width: 450px;
  animation: slideUp 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes slideUp {
  from {
    transform: scale(0.95) translateY(30px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-content {
  background: var(--bg-modal);
  border: 1px solid var(--border-color);
  padding: 2.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  border-radius: 0.5rem;
}

.modal-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.spinner-container {
  margin-bottom: 1.5rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-icon {
  margin-bottom: 1.5rem;
  color: #ef4444;
}

.modal-title {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.current-step {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 500;
  text-align: center;
  line-height: 1.5;
}

.vaultspace-name {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 0.95rem;
  font-style: italic;
  text-align: center;
  opacity: 0.8;
}

.progress-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.progress-percentage {
  color: var(--accent);
  font-size: 1.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.progress-count {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 500;
  opacity: 0.8;
}

.error-message {
  margin: 1rem 0 0 0;
  color: #fca5a5;
  font-size: 0.95rem;
  text-align: center;
  line-height: 1.5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  width: 100%;
}

.modal-actions {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
}

.cancel-btn {
  padding: 0.5rem 1.25rem;
  border: 1px solid #004225;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #004225;
  color: var(--text-primary);
  border-radius: 0.25rem;
}

.cancel-btn:hover:not(:disabled) {
  background: #004225;
  opacity: 0.9;
  transform: translateY(-1px);
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* Responsive design */
@media (max-width: 640px) {
  .modal-container {
    max-width: 100%;
  }

  .modal-content {
    padding: 2rem 1.5rem;
  }
}
</style>
