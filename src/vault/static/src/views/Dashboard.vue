<template>
  <div class="dashboard">
    <div class="dashboard-main">
      <QuotaDisplay />

      <div class="vaultspaces-section">
        <div class="vaultspaces-section-header">
          <h2>My VaultSpaces</h2>
          <button @click="createVaultSpaceDirect" class="create-vaultspace-btn">
            <span v-html="getIcon('plus', 18)"></span>
            <span>Create VaultSpace</span>
          </button>
        </div>

        <div v-if="loading" class="loading">Loading...</div>
        <div v-else-if="error" class="error">{{ error }}</div>
        <div v-else-if="vaultspaces.length === 0" class="empty-vaultspaces">
          <div class="empty-vaultspaces-content">
            <span v-html="getIcon('folder', 64)"></span>
            <h3>No VaultSpaces yet</h3>
            <p>Create your first VaultSpace to start organizing your files</p>
            <button
              @click="createVaultSpaceDirect"
              class="create-vaultspace-btn-empty"
            >
              <span v-html="getIcon('plus', 18)"></span>
              <span>Create VaultSpace</span>
            </button>
          </div>
        </div>
        <div v-else class="vaultspaces-grid-wrapper">
          <transition-group
            name="vaultspace"
            tag="div"
            class="vaultspaces-grid"
          >
            <div
              v-for="vaultspace in vaultspaces"
              :key="vaultspace.id"
              class="vaultspace-card"
              :class="{
                'vaultspace-card-new':
                  vaultspace.id === newlyCreatedVaultspaceId,
                'vaultspace-disintegrating': disintegratingVaultSpaces.has(
                  vaultspace.id,
                ),
                'vaultspace-icon-changing': animatingIconChanges.has(
                  vaultspace.id,
                ),
                'vaultspace-renaming': renamingVaultSpaces.has(vaultspace.id),
              }"
              :data-vaultspace-id="vaultspace.id"
            >
              <div
                @click="openVaultSpace(vaultspace.id)"
                class="vaultspace-card-content"
              >
                <div
                  class="vaultspace-icon"
                  v-html="getIcon(vaultspace.icon_name || 'folder', 40)"
                ></div>
                <div class="vaultspace-info">
                  <h3 v-if="editingVaultspaceId !== vaultspace.id">
                    {{ vaultspace.name }}
                  </h3>
                  <input
                    v-else
                    v-model="editingVaultspaceName"
                    @keyup.enter="saveVaultspaceRename(vaultspace.id)"
                    @keyup.esc="cancelVaultspaceRename"
                    @blur="saveVaultspaceRename(vaultspace.id)"
                    class="vaultspace-rename-input"
                    ref="renameInput"
                    autofocus
                  />
                  <p class="vaultspace-type">
                    Personal
                    <span
                      v-if="isPinned(vaultspace.id)"
                      class="vaultspace-pinned-indicator"
                    >
                      • Pinned
                    </span>
                  </p>
                  <p class="vaultspace-date">
                    Created: {{ formatDate(vaultspace.created_at) }}
                  </p>
                </div>
              </div>
              <div class="vaultspace-actions">
                <button
                  @click.stop="openVaultSpaceMenu(vaultspace, $event)"
                  class="vaultspace-action-btn vaultspace-menu-btn"
                  title="More options"
                >
                  <span v-html="getIcon('moreVertical', 18)"></span>
                </button>
              </div>
            </div>
          </transition-group>
        </div>
      </div>
    </div>
  </div>

  <!-- Delete Confirmation Modal -->

  <!-- Delete Confirmation Modal -->
  <ConfirmationModal
    :show="showDeleteConfirm"
    title="Delete VaultSpace"
    :message="`Are you sure you want to delete '${pendingDeleteVaultspaceName}'? This will permanently delete all files and folders in this VaultSpace. This action cannot be undone.`"
    confirm-text="Delete"
    :dangerous="true"
    @confirm="handleDeleteVaultspace"
    @close="showDeleteConfirm = false"
  />

  <!-- Alert Modal -->
  <AlertModal
    :show="showAlertModal"
    :type="alertModalConfig.type"
    :title="alertModalConfig.title"
    :message="alertModalConfig.message"
    @close="handleAlertModalClose"
    @ok="handleAlertModalClose"
  />

  <!-- Icon Picker Modal -->
  <IconPicker
    :show="showIconPicker"
    :current-icon="selectedVaultspaceIcon"
    @close="showIconPicker = false"
    @select="handleIconSelect"
  />

  <!-- VaultSpace Menu Dropdown -->
  <VaultSpaceMenuDropdown
    :show="showVaultSpaceMenu"
    :vaultspace="selectedVaultSpaceForMenu"
    :is-pinned="
      selectedVaultSpaceForMenu ? isPinned(selectedVaultSpaceForMenu.id) : false
    "
    :position="menuPosition"
    @close="showVaultSpaceMenu = false"
    @action="handleMenuAction"
  />
</template>

<script>
import { vaultspaces, auth } from "../services/api";
import QuotaDisplay from "../components/QuotaDisplay.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import IconPicker from "../components/IconPicker.vue";
import VaultSpaceMenuDropdown from "../components/VaultSpaceMenuDropdown.vue";

export default {
  name: "Dashboard",
  components: {
    QuotaDisplay,
    ConfirmationModal,
    AlertModal,
    IconPicker,
    VaultSpaceMenuDropdown,
  },
  data() {
    return {
      vaultspaces: [],
      loading: false,
      error: null,
      editingVaultspaceId: null,
      editingVaultspaceName: "",
      showDeleteConfirm: false,
      pendingDeleteVaultspaceId: null,
      pendingDeleteVaultspaceName: "",
      showAlertModal: false,
      alertModalConfig: {
        type: "error",
        title: "Error",
        message: "",
      },
      newlyCreatedVaultspaceId: null,
      showIconPicker: false,
      selectedVaultspaceId: null,
      selectedVaultspaceIcon: "folder",
      pinnedVaultSpaceIds: new Set(),
      showVaultSpaceMenu: false,
      selectedVaultSpaceForMenu: null,
      menuPosition: { x: 0, y: 0 },
      disintegratingVaultSpaces: new Set(),
      animatingIconChanges: new Set(),
      renamingVaultSpaces: new Set(),
    };
  },
  async mounted() {
    await this.loadVaultSpaces();
    await this.loadPinnedStatus();
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
    async loadVaultSpaces() {
      this.loading = true;
      this.error = null;
      try {
        this.vaultspaces = await vaultspaces.list();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    generateUniqueVaultspaceName(baseName = "New VaultSpace") {
      // Get all existing vaultspace names
      const existingNames = this.vaultspaces.map((vs) => vs.name);

      // Check if base name is available
      if (!existingNames.includes(baseName)) {
        return baseName;
      }

      // Find the next available number
      let counter = 1;
      let newName = `${baseName}(${counter})`;

      while (existingNames.includes(newName)) {
        counter++;
        newName = `${baseName}(${counter})`;
      }

      return newName;
    },
    async createVaultSpaceDirect() {
      try {
        // Generate unique name
        const uniqueName = this.generateUniqueVaultspaceName("New VaultSpace");

        const vaultspace = await vaultspaces.create({
          name: uniqueName,
          type: "personal",
        });
        this.vaultspaces.push(vaultspace);
        // Trigger animation
        this.newlyCreatedVaultspaceId = vaultspace.id;
        this.$nextTick(() => {
          // Scroll to the newly created vaultspace smoothly
          setTimeout(() => {
            const element = document.querySelector(
              `[data-vaultspace-id="${vaultspace.id}"]`,
            );
            if (element) {
              element.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
            // Remove animation class after animation completes
            setTimeout(() => {
              this.newlyCreatedVaultspaceId = null;
            }, 600);
          }, 50);
        });
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to create VaultSpace: " + err.message,
        });
      }
    },
    openVaultSpace(vaultspaceId) {
      this.$router.push(`/vaultspace/${vaultspaceId}`);
    },
    formatDate(dateString) {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleDateString();
    },
    startVaultspaceRename(vaultspace) {
      this.editingVaultspaceId = vaultspace.id;
      this.editingVaultspaceName = vaultspace.name;
      this.$nextTick(() => {
        const input = this.$refs.renameInput;
        if (input && input[0]) {
          input[0].focus();
          input[0].select();
        }
      });
    },
    cancelVaultspaceRename() {
      this.editingVaultspaceId = null;
      this.editingVaultspaceName = "";
    },
    async saveVaultspaceRename(vaultspaceId) {
      if (!this.editingVaultspaceName.trim()) {
        this.cancelVaultspaceRename();
        return;
      }

      try {
        const updated = await vaultspaces.update(vaultspaceId, {
          name: this.editingVaultspaceName.trim(),
        });
        const index = this.vaultspaces.findIndex((v) => v.id === vaultspaceId);
        if (index >= 0) {
          this.vaultspaces[index] = updated;
        }

        // Trigger rename animation
        this.renamingVaultSpaces.add(vaultspaceId);
        setTimeout(() => {
          this.renamingVaultSpaces.delete(vaultspaceId);
        }, 300);

        this.cancelVaultspaceRename();

        // Notify sidebar to refresh pinned VaultSpaces
        const event = new CustomEvent("vaultspace-updated", {
          detail: { vaultspaceId, action: "rename", vaultspace: updated },
        });
        document.dispatchEvent(event);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to rename VaultSpace: " + err.message,
        });
        this.cancelVaultspaceRename();
      }
    },
    confirmDeleteVaultspace(vaultspace) {
      this.pendingDeleteVaultspaceId = vaultspace.id;
      this.pendingDeleteVaultspaceName = vaultspace.name;
      this.showDeleteConfirm = true;
    },
    async handleDeleteVaultspace() {
      const vaultspaceId = this.pendingDeleteVaultspaceId;
      this.pendingDeleteVaultspaceId = null;
      this.pendingDeleteVaultspaceName = "";
      this.showDeleteConfirm = false;

      try {
        // Start disintegration animation
        this.disintegratingVaultSpaces.add(vaultspaceId);

        // Wait for animation to complete (600ms)
        await new Promise((resolve) => setTimeout(resolve, 600));

        // Delete from backend
        await vaultspaces.delete(vaultspaceId);

        // Remove from list after animation
        this.vaultspaces = this.vaultspaces.filter(
          (v) => v.id !== vaultspaceId,
        );

        // Remove from pinned list
        this.pinnedVaultSpaceIds.delete(vaultspaceId);

        // Clean up animation state
        this.disintegratingVaultSpaces.delete(vaultspaceId);

        // Notify sidebar to refresh pinned VaultSpaces
        const event = new CustomEvent("vaultspace-deleted", {
          detail: { vaultspaceId },
        });
        document.dispatchEvent(event);
      } catch (err) {
        // Clean up animation state on error
        this.disintegratingVaultSpaces.delete(vaultspaceId);
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to delete VaultSpace: " + err.message,
        });
      }
    },
    showAlert(config) {
      this.alertModalConfig = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      this.showAlertModal = true;
    },
    handleAlertModalClose() {
      this.showAlertModal = false;
    },
    openIconPicker(vaultspace) {
      this.selectedVaultspaceId = vaultspace.id;
      this.selectedVaultspaceIcon = vaultspace.icon_name || "folder";
      this.showIconPicker = true;
    },
    async handleIconSelect(iconName) {
      if (!this.selectedVaultspaceId) {
        return;
      }

      try {
        const updated = await vaultspaces.update(this.selectedVaultspaceId, {
          icon_name: iconName,
        });
        const index = this.vaultspaces.findIndex(
          (v) => v.id === this.selectedVaultspaceId,
        );
        if (index >= 0) {
          this.vaultspaces[index] = updated;
        }
        const vaultspaceId = this.selectedVaultspaceId;
        this.showIconPicker = false;
        this.selectedVaultspaceId = null;
        this.selectedVaultspaceIcon = "folder";

        // Trigger icon change animation
        this.animatingIconChanges.add(vaultspaceId);
        setTimeout(() => {
          this.animatingIconChanges.delete(vaultspaceId);
        }, 300);

        // Notify sidebar to refresh pinned VaultSpaces
        const event = new CustomEvent("vaultspace-updated", {
          detail: { vaultspaceId, action: "icon", vaultspace: updated },
        });
        document.dispatchEvent(event);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to update icon: " + err.message,
        });
      }
    },
    async loadPinnedStatus() {
      try {
        const pinned = await vaultspaces.listPinned();
        this.pinnedVaultSpaceIds = new Set(pinned.map((vs) => vs.id));
      } catch (err) {
        console.error("Failed to load pinned status:", err);
        this.pinnedVaultSpaceIds = new Set();
      }
    },
    isPinned(vaultspaceId) {
      return this.pinnedVaultSpaceIds.has(vaultspaceId);
    },
    async togglePinVaultspace(vaultspace) {
      try {
        if (this.isPinned(vaultspace.id)) {
          await vaultspaces.unpin(vaultspace.id);
          this.pinnedVaultSpaceIds.delete(vaultspace.id);
        } else {
          await vaultspaces.pin(vaultspace.id);
          this.pinnedVaultSpaceIds.add(vaultspace.id);
        }
        // Update local state immediately
        await this.loadPinnedStatus();

        // Emit event on document immediately for instant sidebar refresh
        const event = new CustomEvent("pinned-vaultspaces-changed", {
          detail: { vaultspaceId: vaultspace.id },
        });
        document.dispatchEvent(event);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to toggle pin: " + err.message,
        });
      }
    },
    openVaultSpaceMenu(vaultspace, event) {
      event.stopPropagation();
      event.preventDefault();

      // Close menu if already open for the same vaultspace
      if (
        this.showVaultSpaceMenu &&
        this.selectedVaultSpaceForMenu?.id === vaultspace.id
      ) {
        this.showVaultSpaceMenu = false;
        return;
      }

      // Capture exact click coordinates
      this.menuPosition = {
        x: event.clientX,
        y: event.clientY,
      };

      this.selectedVaultSpaceForMenu = vaultspace;
      this.$nextTick(() => {
        this.showVaultSpaceMenu = true;
      });
    },
    async handleMenuAction(action, vaultspace) {
      switch (action) {
        case "pin":
          await this.togglePinVaultspace(vaultspace);
          break;
        case "unpin":
          await this.togglePinVaultspace(vaultspace);
          break;
        case "change-icon":
          this.openIconPicker(vaultspace);
          break;
        case "rename":
          this.startVaultspaceRename(vaultspace);
          break;
        case "delete":
          this.confirmDeleteVaultspace(vaultspace);
          break;
      }
    },
  },
};
</script>

<style scoped>
.dashboard {
  position: relative;
  z-index: 1;
}

.dashboard-main {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
  width: 100%;
  padding: 0 1rem;
  box-sizing: border-box;
}

.mobile-mode .dashboard-main {
  gap: 1rem;
  padding: 0 0.5rem;
}

.vaultspaces-section {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.55),
    rgba(15, 23, 42, 0.4)
  );
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 1.25rem;
  padding: 2rem;
  box-shadow: 0 12px 40px rgba(2, 6, 23, 0.35);
}

.mobile-mode .vaultspaces-section {
  padding: 1rem;
  border-radius: 1rem;
}

.vaultspaces-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.mobile-mode .vaultspaces-section-header {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.mobile-mode .vaultspaces-section-header h2 {
  font-size: 1.25rem;
}

.vaultspaces-section h2 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
}

.create-vaultspace-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #e6eef6;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.create-vaultspace-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(88, 166, 255, 0.3);
  transform: translateY(-1px);
}

.create-vaultspace-btn svg {
  display: block;
  color: currentColor;
}

.empty-vaultspaces {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 3rem;
}

.empty-vaultspaces-content {
  text-align: center;
  color: #94a3b8;
}

.empty-vaultspaces-content h3 {
  margin: 1.5rem 0 0.5rem 0;
  color: #e6eef6;
  font-size: 1.25rem;
  font-weight: 600;
}

.empty-vaultspaces-content p {
  margin: 0 0 2rem 0;
  color: #94a3b8;
  font-size: 0.95rem;
}

.create-vaultspace-btn-empty {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #e6eef6;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.create-vaultspace-btn-empty:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(88, 166, 255, 0.3);
  transform: translateY(-1px);
}

.create-vaultspace-btn-empty svg {
  display: block;
  color: currentColor;
}

.vaultspaces-grid-wrapper {
  position: relative;
}

.vaultspaces-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

.mobile-mode .vaultspaces-grid {
  grid-template-columns: 1fr;
  gap: 1rem;
}

.vaultspace-card {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 1rem;
  padding: 1.5rem;
  transition: all 0.3s ease;
  position: relative;
  display: flex;
  flex-direction: column;
}

.mobile-mode .vaultspace-card {
  padding: 1rem;
  width: 100%;
}

.vaultspace-card:hover {
  transform: translateY(-4px) scale(1);
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.5);
  border-color: rgba(88, 166, 255, 0.3);
}

.vaultspace-card-new {
  animation: vaultspaceCardNew 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

@keyframes vaultspaceCardNew {
  0% {
    opacity: 0;
    transform: translateY(30px) scale(0.8);
  }
  50% {
    transform: translateY(-5px) scale(1.05);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes vaultspaceDisintegrate {
  0% {
    opacity: 1;
    filter: blur(0px);
    transform: translateY(0) scale(1);
  }
  50% {
    opacity: 0.5;
    filter: blur(2px);
    transform: translateY(-10px) scale(0.95);
  }
  100% {
    opacity: 0;
    filter: blur(8px);
    transform: translateY(-30px) scale(0.8);
  }
}

@keyframes vaultspaceFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.9) translateY(10px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@keyframes vaultspaceRename {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}

.vaultspace-disintegrating {
  animation: vaultspaceDisintegrate 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  pointer-events: none;
  will-change: opacity, transform, filter;
}

.vaultspace-icon-changing {
  animation: vaultspaceRename 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  will-change: transform;
}

.vaultspace-renaming {
  animation: vaultspaceRename 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  will-change: transform;
}

.vaultspace-fade-in {
  animation: vaultspaceFadeIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: opacity, transform;
}

/* Transition group animations */
.vaultspace-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.vaultspace-leave-active {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.vaultspace-enter-from {
  opacity: 0;
  transform: scale(0.9) translateY(10px);
}

.vaultspace-leave-to {
  opacity: 0;
  filter: blur(8px);
  transform: translateY(-30px) scale(0.8);
}

.vaultspace-move {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.vaultspace-card-content {
  flex: 1;
  cursor: pointer;
}

.vaultspace-actions {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  display: flex;
  gap: 0.5rem;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.vaultspace-card:hover .vaultspace-actions {
  opacity: 1;
}

.vaultspace-action-btn {
  background: rgba(255, 255, 255, 0);
  padding: 0.5rem;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s ease;
  color: #e6eef6;
}

.vaultspace-action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(88, 166, 255, 0.3);
}

.vaultspace-action-btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
}

.vaultspace-rename-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.5);
  border-radius: 0.5rem;
  padding: 0.5rem;
  color: #e6eef6;
  font-size: 1.25rem;
  font-weight: 600;
  font-family: inherit;
}

.vaultspace-rename-input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.8);
  background: rgba(255, 255, 255, 0.15);
}

.vaultspace-icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #e6eef6;
}

.mobile-mode .vaultspace-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.vaultspace-icon :deep(svg) {
  width: 40px;
  height: 40px;
  color: currentColor;
}

.vaultspace-info h3 {
  margin: 0 0 0.5rem 0;
  color: #e6eef6;
  font-size: 1.25rem;
  font-weight: 600;
}

.vaultspace-type {
  color: #94a3b8;
  font-size: 0.9rem;
  margin: 0.25rem 0;
  text-transform: capitalize;
}

.vaultspace-pinned-indicator {
  color: #38bdf8;
  font-weight: 500;
}

.vaultspace-date {
  color: #64748b;
  font-size: 0.85rem;
  margin: 0.25rem 0;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.2);
  color: #e6eef6;
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.3);
}

.btn-outline {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.3);
  color: #e6eef6;
}

.btn-outline:hover:not(:disabled) {
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(88, 166, 255, 0.1);
}

.modal-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  background: rgba(7, 14, 28, 0.4) !important;
  backdrop-filter: blur(15px) !important;
  -webkit-backdrop-filter: blur(15px) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 10000 !important;
  padding: 2rem !important;
  padding-left: calc(
    2rem + 250px
  ) !important; /* Default: sidebar expanded (250px) */
  overflow-y: auto !important;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px) !important; /* Sidebar collapsed (70px) */
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
  padding: 2rem !important;
  border-radius: 2rem !important;
  min-width: 400px !important;
  max-width: 90vw !important;
  max-height: 90vh !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  position: relative !important;
  z-index: 10001 !important;
  display: flex !important;
  flex-direction: column !important;
  box-sizing: border-box !important;
  overflow-y: auto !important;
}

.modal h2 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center !important;
}

.form-group {
  margin-bottom: 1.25rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  box-sizing: border-box;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.loading {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
}

.error {
  padding: 1rem;
  text-align: center;
  color: #f85149;
  background-color: rgba(248, 81, 73, 0.1);
  border: 1px solid rgba(248, 81, 73, 0.3);
  border-radius: 8px;
}
</style>

<!-- Global styles for modals -->
<style>
.modal-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  background: rgba(7, 14, 28, 0.4) !important;
  backdrop-filter: blur(15px) !important;
  -webkit-backdrop-filter: blur(15px) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 10000 !important;
  visibility: visible !important;
  opacity: 1 !important;
  padding: 2rem !important;
  padding-left: calc(
    2rem + 250px
  ) !important; /* Default: sidebar expanded (250px) */
  overflow-y: auto !important;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px) !important; /* Sidebar collapsed (70px) */
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
  padding: 2rem !important;
  border-radius: 2rem !important;
  min-width: 400px !important;
  max-width: 90vw !important;
  max-height: 90vh !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  position: relative !important;
  z-index: 10001 !important;
  visibility: visible !important;
  opacity: 1 !important;
  color: var(--text-primary, #f1f5f9) !important;
  display: flex !important;
  flex-direction: column !important;
  box-sizing: border-box !important;
  overflow-y: auto !important;
}

.modal-header {
  padding: 0 0 1.5rem 0 !important;
  margin-bottom: 1.5rem !important;
  border-bottom: 1px solid var(--border-color) !important;
  flex-shrink: 0 !important;
}

.modal-form {
  padding: 0 !important;
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 1.25rem !important;
}

.modal h2 {
  margin: 0 !important;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center !important;
}

.modal .form-group {
  margin-bottom: 1.25rem;
}

.modal .form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-weight: 500;
}

.modal .form-group input,
.modal .form-group select {
  width: 100%;
  box-sizing: border-box;
}

.modal .form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 0px !important;
  flex-shrink: 0;
}
</style>
