<template>
  <Teleport to="body">
    <div v-if="selectedCount > 0" class="batch-actions-bar glass glass-card">
      <div class="batch-info">
        <span class="batch-count">{{ selectedCount }} item(s) selected</span>
      </div>
      <div class="batch-buttons">
        <button
          @click="handleRestore"
          class="btn btn-primary btn-sm"
          :disabled="processing"
        >
          {{
            processing && actionType === "restore"
              ? "Restoring..."
              : "Restore Selected"
          }}
        </button>
        <button
          @click="handleDelete"
          class="btn btn-danger btn-sm"
          :disabled="processing"
        >
          {{
            processing && actionType === "delete"
              ? "Deleting..."
              : "Delete Permanently"
          }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { ref, computed } from "vue";

export default {
  name: "BatchActionsTrash",
  props: {
    selectedItems: {
      type: Array,
      default: () => [],
    },
    processing: {
      type: Boolean,
      default: false,
    },
    actionType: {
      type: String,
      default: null, // 'restore' or 'delete'
    },
  },
  emits: ["restore", "delete", "clear"],
  setup(props, { emit }) {
    const selectedCount = computed(() => props.selectedItems.length);

    const handleRestore = () => {
      emit("restore");
    };

    const handleDelete = () => {
      emit("delete");
    };

    return {
      selectedCount,
      handleRestore,
      handleDelete,
    };
  },
};
</script>

<style scoped>
.batch-actions-bar {
  position: fixed !important;
  bottom: 2rem !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  padding: 1rem 1.5rem !important;
  border-radius: 2rem !important;
  z-index: 100001 !important;
  min-width: 500px !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5) !important;
  gap: 1.5rem !important;
  margin: 0 !important;
}

.mobile-mode .batch-actions-bar {
  min-width: auto !important;
  width: calc(100% - 2rem) !important;
  max-width: 100% !important;
  left: 1rem !important;
  right: 1rem !important;
  transform: none !important;
  padding: 0.75rem 1rem !important;
  gap: 1rem !important;
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
  flex-shrink: 0;
}

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}
</style>
