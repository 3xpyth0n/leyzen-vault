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
          <div class="icon-search-container">
            <input
              v-model="searchQuery"
              type="text"
              class="icon-search-input"
              placeholder="Search icons by name..."
              autofocus
              @input="handleSearch"
            />
          </div>
          <div class="icon-grid">
            <button
              v-for="iconName in filteredIcons"
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
          <div
            v-if="filteredIcons.length === 0 && searchQuery.trim().length >= 2"
            class="no-icons-message"
          >
            No icons found matching "{{ searchQuery }}"
          </div>
          <div
            v-else-if="
              filteredIcons.length === 0 &&
              (!searchQuery.trim() || searchQuery.trim().length < 2)
            "
            class="no-icons-message"
          >
            Type at least 2 characters to search for icons
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
  data() {
    return {
      searchQuery: "",
      allIcons: [],
    };
  },
  computed: {
    availableIcons() {
      if (!window.Icons) {
        return [];
      }
      // Use getAllIconNames if available (new system), otherwise fallback to old method
      if (
        window.Icons.getAllIconNames &&
        typeof window.Icons.getAllIconNames === "function"
      ) {
        const icons = window.Icons.getAllIconNames();
        return Array.isArray(icons) ? icons : [];
      }
      // Fallback: Get all icon names from window.Icons, excluding helper functions
      const icons = [];
      for (const key in window.Icons) {
        if (
          typeof window.Icons[key] === "function" &&
          key !== "createSVG" &&
          key !== "chevron-down" &&
          key !== "getIcon" &&
          key !== "getFileIconName" &&
          key !== "getAllIconNames" &&
          key !== "searchIcons"
        ) {
          icons.push(key);
        }
      }
      return icons.sort();
    },
    filteredIcons() {
      const query = this.searchQuery ? this.searchQuery.trim() : "";

      // Don't show any icons if search is empty or has less than 2 characters
      if (!query || query.length < 2) {
        return [];
      }

      // Use searchIcons if available (new system), otherwise filter manually
      if (
        window.Icons &&
        window.Icons.searchIcons &&
        typeof window.Icons.searchIcons === "function"
      ) {
        const results = window.Icons.searchIcons(query);
        return results || [];
      }
      // Fallback: manual filtering
      const lowerQuery = query.toLowerCase();
      return this.availableIcons.filter((iconName) =>
        iconName.toLowerCase().includes(lowerQuery),
      );
    },
  },
  mounted() {
    // Load all icons on mount
    this.allIcons = this.availableIcons;
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
      if (!window.Icons) {
        return "";
      }
      // Use getIcon if available (new system)
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      // Fallback: use direct function call
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
    handleSearch() {
      // Search is handled by computed property filteredIcons
      // This method can be used for additional search logic if needed
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
  padding-left: calc(1rem + 250px); /* Default: sidebar expanded (250px) */
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  animation: fadeIn 0.2s ease;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .modal-overlay {
  padding-left: 1rem !important;
  padding-right: 1rem !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(1rem + 70px); /* Sidebar collapsed (70px) */
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
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.icon-search-container {
  margin-bottom: 1.5rem;
}

.icon-search-input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: var(--bg-modal);
  border: 1px solid rgba(255, 255, 255, 0.1);

  color: #a9b7aa;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.icon-search-input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: var(--bg-modal);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.1);
}

.icon-search-input::placeholder {
  color: rgba(230, 238, 246, 0.5);
}

.no-icons-message {
  text-align: center;
  color: rgba(230, 238, 246, 0.6);
  padding: 2rem;
  font-size: 0.95rem;
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
}

.icon-grid::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
}

.icon-grid::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.icon-button {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);

  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  color: #a9b7aa;
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

  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-btn-cancel {
  background: #004225;
  color: #a9b7aa;
}

.modal-btn-cancel:hover {
  background: #004225;
}
</style>
