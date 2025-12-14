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
          <p v-if="remainingCount !== null" class="modal-remaining">
            {{ remainingCount }} file{{ remainingCount !== 1 ? "s" : "" }}
            remaining
          </p>
          <div v-if="showApplyToAll" class="modal-apply-to-all">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="applyToAll"
                class="checkbox-input"
              />
              <span>Apply to all</span>
            </label>
          </div>
          <div class="modal-buttons">
            <button
              id="modal-skip"
              class="modal-btn modal-btn-cancel"
              @click="handleSkip"
              :disabled="disabled"
            >
              Skip
            </button>
            <button
              id="modal-keep-both"
              class="modal-btn modal-btn-secondary"
              @click="handleKeepBoth"
              :disabled="disabled"
            >
              Keep both
            </button>
            <button
              id="modal-replace"
              class="modal-btn modal-btn-confirm modal-btn-danger"
              @click="handleReplace"
              :disabled="disabled"
            >
              Replace
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "ConflictResolutionModal",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    title: {
      type: String,
      default: "File Already Exists",
    },
    message: {
      type: String,
      default: "A file with this name already exists.",
    },
    icon: {
      type: String,
      default: null,
    },
    closeOnBackdrop: {
      type: Boolean,
      default: false,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    showApplyToAll: {
      type: Boolean,
      default: false,
    },
    remainingCount: {
      type: Number,
      default: null,
    },
  },
  emits: ["replace", "keep-both", "skip", "close"],
  data() {
    return {
      applyToAll: false,
    };
  },
  watch: {
    show(newVal) {
      if (newVal) {
        document.body.style.overflow = "hidden";
        this.applyToAll = false;
        // Focus on Replace button for accessibility
        this.$nextTick(() => {
          const replaceBtn = document.getElementById("modal-replace");
          if (replaceBtn) {
            replaceBtn.focus();
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
      const iconFn = window.Icons.warning;
      return typeof iconFn === "function"
        ? iconFn.call(window.Icons, 48, "currentColor")
        : "";
    },
    handleReplace() {
      this.$emit("replace", this.applyToAll);
      this.$emit("close");
    },
    handleKeepBoth() {
      this.$emit("keep-both", this.applyToAll);
      this.$emit("close");
    },
    handleSkip() {
      this.$emit("skip", this.applyToAll);
      this.$emit("close");
    },
    handleBackdropClick(event) {
      if (this.closeOnBackdrop && event.target === event.currentTarget) {
        this.handleSkip();
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
  padding-left: calc(
    1rem + 250px
  ) !important; /* Default: sidebar expanded (250px) */
  background: rgba(7, 14, 28, 0.4) !important;
  backdrop-filter: blur(15px) !important;
  -webkit-backdrop-filter: blur(15px) !important;
  opacity: 1 !important;
  visibility: visible !important;
  animation: fadeIn 0.2s ease;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(1rem + 70px) !important; /* Sidebar collapsed (70px) */
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
  max-width: 500px;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1);
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
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
  border-radius: 2rem !important;
  padding: 2rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  position: relative;
  overflow: hidden;
}

.modal-content-confirm::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
}

.modal-icon {
  font-size: 3rem;
  text-align: center;
  margin-bottom: 1rem;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
}

.modal-title {
  margin: 0 0 1rem 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.modal-message {
  margin: 0 0 1rem 0;
  color: #cbd5e1;
  font-size: 1rem;
  text-align: center;
  line-height: 1.5;
  word-break: break-word;
}

.modal-remaining {
  margin: 0 0 1rem 0;
  color: #94a3b8;
  font-size: 0.9rem;
  text-align: center;
}

.modal-apply-to-all {
  margin: 0 0 1.5rem 0;
  display: flex;
  justify-content: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #cbd5e1;
  font-size: 0.95rem;
  user-select: none;
}

.checkbox-input {
  width: 1.2rem;
  height: 1.2rem;
  cursor: pointer;
  accent-color: #8b5cf6;
}

.modal-buttons {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  flex: 1;
  min-width: 100px;
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.modal-btn-cancel {
  background: rgba(148, 163, 184, 0.2);
  color: #e6eef6;
}

.modal-btn-cancel:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.3);
}

.modal-btn-secondary {
  background: linear-gradient(135deg, #64748b 0%, #475569 100%);
  color: white;
}

.modal-btn-secondary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-confirm {
  background: linear-gradient(135deg, #8b5cf6 0%, #818cf8 100%);
  color: white;
}

.modal-btn-confirm:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.modal-btn-danger:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
</style>
