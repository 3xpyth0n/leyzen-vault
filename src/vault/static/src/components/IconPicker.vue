<template>
  <teleport to="body">
    <div
      v-if="show"
      class="modal-overlay"
      @click="handleBackdropClick"
      role="dialog"
      aria-labelledby="icon-picker-title"
      aria-modal="true"
    >
      <div class="modal-container" @click.stop>
        <div class="modal-content-icon-picker">
          <h2 id="icon-picker-title" class="modal-title">Select Icon</h2>
          <div class="icon-grid">
            <button
              v-for="iconName in availableIcons"
              :key="iconName"
              class="icon-button"
              :class="{ 'icon-button-selected': iconName === currentIcon }"
              @click="selectIcon(iconName)"
              :title="iconName"
              :aria-label="`Select ${iconName} icon`"
            >
              <div class="icon-preview" v-html="getIcon(iconName, 32)"></div>
            </button>
          </div>
          <div class="modal-buttons">
            <button class="modal-btn modal-btn-cancel" @click="handleClose">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "IconPicker",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    currentIcon: {
      type: String,
      default: "folder",
    },
  },
  emits: ["select", "close"],
  computed: {
    availableIcons() {
      if (!window.Icons) {
        return [];
      }
      // Get all icon names from window.Icons, excluding helper functions
      const icons = [];
      for (const key in window.Icons) {
        if (
          typeof window.Icons[key] === "function" &&
          key !== "createSVG" &&
          key !== "chevron-down"
        ) {
          icons.push(key);
        }
      }
      return icons.sort();
    },
  },
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
    getIcon(iconName, size = 24) {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      // Use .call() to preserve the correct 'this' context for window.Icons
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
    selectIcon(iconName) {
      this.$emit("select", iconName);
      this.handleClose();
    },
    handleClose() {
      this.$emit("close");
    },
    handleBackdropClick(event) {
      if (event.target === event.currentTarget) {
        this.handleClose();
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
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
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
  max-width: 600px;
  max-height: 80vh;
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

.modal-content-icon-picker {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 2rem;
  padding: 2rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

.modal-content-icon-picker::before {
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

.modal-title {
  margin: 0 0 1.5rem 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
  gap: 0.75rem;
  max-height: 50vh;
  overflow-y: auto;
  padding: 0.5rem;
  margin-bottom: 1.5rem;
}

.icon-grid::-webkit-scrollbar {
  width: 8px;
}

.icon-grid::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.icon-grid::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.icon-grid::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.icon-button {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.75rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  color: #e6eef6;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(88, 166, 255, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.icon-button-selected {
  background: rgba(88, 166, 255, 0.2);
  border-color: rgba(88, 166, 255, 0.6);
  box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.3);
}

.icon-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.icon-preview :deep(svg) {
  width: 32px;
  height: 32px;
  color: currentColor;
}

.modal-buttons {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-btn-cancel {
  background: rgba(148, 163, 184, 0.2);
  color: #e6eef6;
}

.modal-btn-cancel:hover {
  background: rgba(148, 163, 184, 0.3);
}
</style>
