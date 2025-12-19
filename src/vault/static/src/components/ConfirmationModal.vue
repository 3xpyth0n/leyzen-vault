<template>
  <teleport to="body">
    <div
      v-if="show"
      ref="modalOverlay"
      class="modal-overlay"
      :aria-hidden="!show"
      @click="handleBackdropClick"
      role="dialog"
      aria-labelledby="modal-title"
      aria-modal="true"
    >
      <div class="modal-container" @click.stop>
        <div class="modal-content-confirm">
          <div class="modal-icon" id="modal-icon">
            <span v-if="icon" v-html="icon"></span>
            <span v-else v-html="getDefaultIcon()"></span>
          </div>
          <h2 id="modal-title" class="modal-title">{{ title }}</h2>
          <p id="modal-message" class="modal-message">{{ message }}</p>
          <div class="modal-buttons">
            <button
              id="modal-cancel"
              class="modal-btn modal-btn-cancel"
              @click="handleCancel"
              :disabled="disabled"
            >
              Cancel
            </button>
            <button
              id="modal-confirm"
              class="modal-btn modal-btn-confirm"
              :class="{ 'modal-btn-danger': dangerous }"
              @click="handleConfirm"
              :disabled="disabled"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "ConfirmationModal",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    title: {
      type: String,
      default: "Confirm Action",
    },
    message: {
      type: String,
      default: "Are you sure you want to proceed?",
    },
    confirmText: {
      type: String,
      default: "Confirm",
    },
    icon: {
      type: String,
      default: null,
    },
    dangerous: {
      type: Boolean,
      default: false,
    },
    closeOnBackdrop: {
      type: Boolean,
      default: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["confirm", "cancel", "close"],
  watch: {
    show(newVal) {
      if (newVal) {
        document.body.style.overflow = "hidden";
        // Focus on cancel button for accessibility
        this.$nextTick(() => {
          const cancelBtn = document.getElementById("modal-cancel");
          if (cancelBtn) {
            cancelBtn.focus();
          }
        });
      } else {
        document.body.style.overflow = "";
      }
    },
  },
  methods: {
    getDefaultIcon() {
      if (!window.Icons || !window.Icons.warning) {
        return "";
      }
      // Always use SVG icons, never emojis
      // Use .call() to preserve the correct 'this' context for window.Icons
      const iconFn = window.Icons.warning;
      return typeof iconFn === "function"
        ? iconFn.call(window.Icons, 48, "currentColor")
        : "";
    },
    handleConfirm() {
      this.$emit("confirm");
      this.$emit("close");
    },
    handleCancel() {
      this.$emit("cancel");
      this.$emit("close");
    },
    handleBackdropClick(event) {
      if (this.closeOnBackdrop && event.target === event.currentTarget) {
        this.handleCancel();
      }
    },
  },
  beforeUnmount() {
    document.body.style.overflow = "";
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed !important;
  inset: 0 !important;
  z-index: 100000 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 1rem !important;
  background: rgba(10, 10, 10, 0.8) !important;
  opacity: 1 !important;
  visibility: visible !important;
  animation: fadeIn 0.2s ease;
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
  max-width: 420px;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.mobile-mode .modal-container {
  max-width: 90vw;
}

@keyframes slideUp {
  from {
    transform: scale(0.95) translateY(20px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-content-confirm {
  background: var(--bg-modal) !important;
  border: 1px solid var(--border-color) !important;
  padding: 2rem;
  position: relative;
  overflow: hidden;
}

.modal-icon {
  font-size: 3rem;
  text-align: center;
  margin-bottom: 1rem;
}

.modal-title {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.modal-message {
  margin: 0 0 2rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  text-align: center;
  line-height: 1.5;
}

.modal-buttons {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;

  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.modal-btn-cancel {
  background: var(--bg-primary);
  color: var(--ash-grey);
  border: solid 1px var(--slate-grey);
}

.modal-btn-cancel:hover:not(:disabled) {
  background: var(--bg-secondary);
}

.modal-btn-confirm {
  background: transparent;
  color: var(--text-primary);
}

.modal-btn-confirm:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-confirm.modal-btn-danger {
  background: transparent;
  border: 1px solid var(--error, #ef4444);
  color: var(--error, #ef4444);
}

.modal-btn-confirm.modal-btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--error, #ef4444);
  color: var(--error, #ef4444);
  transform: translateY(-1px);
}
</style>
