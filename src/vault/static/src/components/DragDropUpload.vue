<template>
  <div
    class="drag-drop-zone"
    :class="{ 'drag-over': isDragOver }"
    @drop="handleDrop"
    @dragover.prevent="handleDragOver"
    @dragenter.prevent="handleDragEnter"
    @dragleave.prevent="handleDragLeave"
  >
    <div v-if="!isDragOver" class="drop-zone-content">
      <div class="drop-icon" v-html="uploadIcon"></div>
      <p class="drop-text">Drag and drop files here</p>
      <p class="drop-hint">or click to browse</p>
    </div>
    <div v-else class="drop-zone-active">
      <div class="drop-icon">⬇️</div>
      <p class="drop-text">Drop files here</p>
    </div>
    <input
      ref="fileInput"
      type="file"
      multiple
      @change="handleFileSelect"
      style="display: none"
    />
  </div>
</template>

<script>
export default {
  name: "DragDropUpload",
  emits: ["files-selected"],
  data() {
    return {
      isDragOver: false,
    };
  },
  computed: {
    uploadIcon() {
      if (window.Icons && typeof window.Icons.upload === "function") {
        return window.Icons.upload(48, "currentColor");
      }
      return "";
    },
  },
  methods: {
    handleDragOver(event) {
      event.preventDefault();
      this.isDragOver = true;
    },

    handleDragEnter(event) {
      event.preventDefault();
      this.isDragOver = true;
    },

    handleDragLeave(event) {
      // Only set isDragOver to false if we're leaving the drop zone
      if (!event.currentTarget.contains(event.relatedTarget)) {
        this.isDragOver = false;
      }
    },

    handleDrop(event) {
      event.preventDefault();
      this.isDragOver = false;

      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        this.$emit("files-selected", files);
      }
    },

    handleFileSelect(event) {
      const files = Array.from(event.target.files);
      if (files.length > 0) {
        this.$emit("files-selected", files);
      }
      // Reset input
      event.target.value = "";
    },

    openFileDialog() {
      this.$refs.fileInput?.click();
    },
  },
  mounted() {
    // Make the drop zone clickable
    this.$el.addEventListener("click", () => {
      this.openFileDialog();
    });
  },
};
</script>

<style scoped>
.drag-drop-zone {
  border: 2px dashed var(--border-color, #004225);

  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  backdrop-filter: var(--blur, blur(16px));
}

.drag-drop-zone:hover {
  border-color: var(--accent, #004225);
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
}

.drag-drop-zone.drag-over {
  border-color: var(--accent, #004225);
  background: rgba(56, 189, 248, 0.1);
  transform: scale(1.02);
}

.drop-zone-content,
.drop-zone-active {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.drop-icon {
  font-size: 3rem;
  margin-bottom: 0.5rem;
}

.drop-text {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary, #a9b7aa);
  margin: 0;
}

.drop-hint {
  font-size: 0.9rem;
  color: var(--text-muted, #a9b7aa);
  margin: 0;
}
</style>
