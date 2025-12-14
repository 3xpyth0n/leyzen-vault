<template>
  <Teleport to="body">
    <div v-if="selectedCount > 0" class="batch-actions-bar glass glass-card">
      <div class="batch-info">
        <span class="batch-count">{{ selectedCount }} item(s) selected</span>
      </div>
      <div class="batch-buttons">
        <button
          @click="showDeleteConfirm = true"
          class="btn btn-danger btn-sm"
          :disabled="processing"
        >
          Delete
        </button>
        <button
          @click="handleDownload"
          class="btn btn-secondary btn-sm"
          :disabled="processing"
        >
          Download
        </button>
      </div>

      <!-- Delete Confirmation Modal -->
      <ConfirmationModal
        :show="showDeleteConfirm"
        title="Delete Selected Items"
        :message="`Are you sure you want to delete ${selectedCount} item(s)? This action cannot be undone.`"
        confirm-text="Delete"
        :dangerous="true"
        :disabled="processing"
        @confirm="confirmDelete"
        @close="showDeleteConfirm = false"
      />

      <!-- Alert Modal -->
      <AlertModal
        :show="showAlertModal"
        :type="alertModalConfig.type"
        :title="alertModalConfig.title"
        :message="alertModalConfig.message"
        @close="showAlertModal = false"
        @ok="showAlertModal = false"
      />
    </div>
  </Teleport>
</template>

<script>
import { ref, computed } from "vue";
import { files } from "../services/api";
import ConfirmationModal from "./ConfirmationModal.vue";
import AlertModal from "./AlertModal.vue";

export default {
  name: "BatchActions",
  components: {
    ConfirmationModal,
    AlertModal,
  },
  props: {
    selectedItems: {
      type: Array,
      default: () => [],
    },
    availableFolders: {
      type: Array,
      default: () => [],
    },
  },
  emits: ["delete", "download", "clear"],
  setup(props, { emit }) {
    const processing = ref(false);
    const showDeleteConfirm = ref(false);
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "error",
      title: "Error",
      message: "",
    });

    const selectedCount = computed(() => props.selectedItems.length);

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const confirmDelete = async () => {
      processing.value = true;
      showDeleteConfirm.value = false;
      try {
        const fileIds = props.selectedItems.map((item) => item.id);
        const result = await files.batchDelete(fileIds);
        emit("delete", result);
        emit("clear");
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to delete items: " + err.message,
        });
      } finally {
        processing.value = false;
      }
    };

    const handleDownload = async () => {
      // For now, download files individually
      // In the future, we could create a ZIP file on the server
      processing.value = true;
      try {
        emit("download", props.selectedItems);
        emit("clear");
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to download items: " + err.message,
        });
      } finally {
        processing.value = false;
      }
    };

    return {
      processing,
      showDeleteConfirm,
      selectedCount,
      showAlertModal,
      alertModalConfig,
      confirmDelete,
      handleDownload,
    };
  },
};
</script>

<style scoped>
.batch-actions-bar {
  position: fixed;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-radius: 2rem;
  z-index: 100001 !important;
  min-width: 500px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  gap: 1.5rem; /* Add gap between info and buttons */
}

.mobile-mode .batch-actions-bar {
  min-width: auto;
  width: calc(100% - 2rem);
  max-width: 100%;
  left: 1rem;
  right: 1rem;
  transform: none;
  padding: 0.75rem 1rem;
  gap: 1rem;
  z-index: 100001 !important;
}

.batch-info {
  flex: 1;
}

.batch-count {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.batch-buttons {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0; /* Prevent buttons from shrinking */
}

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
  padding-left: calc(0px + 250px); /* Default: sidebar expanded (250px) */
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .modal-overlay {
  padding-left: 0 !important;
  padding-right: 0 !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(0px + 70px); /* Sidebar collapsed (70px) */
}

.modal {
  padding: 2rem;
  min-width: 400px;
  max-width: 90vw;
  border-radius: 2rem;
}

.modal h2 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: var(--text-primary, #f1f5f9);
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary, #cbd5e1);
}

.form-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.error-message {
  padding: 1rem;
  margin-bottom: 1rem;
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md, 8px);
}
</style>
