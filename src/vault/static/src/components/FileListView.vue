<template>
  <div
    class="file-list-view"
    @keydown="handleKeyDown"
    @click="handleViewClick"
    tabindex="0"
  >
    <div class="view-controls glass">
      <div class="view-controls-grid">
        <div class="view-toggle-panel" v-if="!isMobileView">
          <div class="view-toggle">
            <button
              @click="$emit('view-change', 'grid')"
              class="btn-icon"
              :class="{ active: viewMode !== 'list' }"
              title="Grid View"
            >
              <span v-html="getIcon('grid')"></span>
            </button>
            <button
              @click="$emit('view-change', 'list')"
              class="btn-icon"
              :class="{ active: viewMode === 'list' }"
              title="List View"
            >
              <span v-html="getIcon('list')"></span>
            </button>
          </div>
        </div>
        <div
          class="controls-right-panel"
          :class="{ 'mobile-full-width': isMobileView }"
        >
          <div class="sort-controls">
            <CustomSelect
              v-model="sortBy"
              :options="sortOptions"
              @change="handleSortChange"
              size="small"
              placeholder="Sort by"
            />
            <button
              @click="toggleSortOrder"
              class="btn-icon"
              :title="sortOrder === 'asc' ? 'Ascending' : 'Descending'"
            >
              <span v-html="getSortIcon()"></span>
            </button>
          </div>
          <div class="filter-controls">
            <CustomSelect
              v-model="filterType"
              :options="filterOptions"
              @change="handleFilterChange"
              size="small"
              placeholder="Filter"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-if="viewMode === 'list' && !isMobileView" class="list-view">
      <div
        ref="tableContainer"
        class="grid-container glass"
        :style="{ gridTemplateColumns: getGridTemplateColumns }"
      >
        <!-- Header Row -->
        <div class="grid-header-row">
          <div class="grid-cell grid-cell-checkbox">
            <input
              type="checkbox"
              :checked="allSelected"
              @change="handleSelectAll"
              class="select-all-checkbox"
            />
          </div>
          <div
            @click="handleHeaderClick('name', $event)"
            class="grid-cell grid-cell-name sortable resizable-header"
          >
            <span class="header-content">
              Name
              <span v-if="sortBy === 'name'" class="sort-indicator">
                <span v-html="getSortIcon()"></span>
              </span>
            </span>
            <div
              class="column-resizer"
              @mousedown.stop="handleResizeStart(1, $event)"
            ></div>
          </div>
          <div
            @click="handleHeaderClick('type', $event)"
            class="grid-cell grid-cell-type sortable resizable-header"
          >
            <span class="header-content">
              Type
              <span v-if="sortBy === 'type'" class="sort-indicator">
                <span v-html="getSortIcon()"></span>
              </span>
            </span>
            <div
              class="column-resizer"
              @mousedown.stop="handleResizeStart(2, $event)"
            ></div>
          </div>
          <div
            @click="handleHeaderClick('size', $event)"
            class="grid-cell grid-cell-size sortable resizable-header"
          >
            <span class="header-content">
              Size
              <span v-if="sortBy === 'size'" class="sort-indicator">
                <span v-html="getSortIcon()"></span>
              </span>
            </span>
            <div
              class="column-resizer"
              @mousedown.stop="handleResizeStart(3, $event)"
            ></div>
          </div>
          <div
            @click="handleHeaderClick('date', $event)"
            class="grid-cell grid-cell-date sortable resizable-header"
          >
            <span class="header-content">
              Modified
              <span v-if="sortBy === 'date'" class="sort-indicator">
                <span v-html="getSortIcon()"></span>
              </span>
            </span>
            <div
              class="column-resizer"
              @mousedown.stop="handleResizeStart(4, $event)"
            ></div>
          </div>
          <div class="grid-cell grid-cell-actions">Actions</div>
        </div>
        <!-- Data Rows -->
        <template
          v-for="(item, index) in sortedAndFilteredItems"
          :key="item.id"
        >
          <div
            :data-item-id="item.id"
            :data-row-index="index"
            class="grid-body-row"
            :class="{
              selected: isSelected(item.id),
              focused: focusedItemIndex === index,
              'drop-target':
                dropTargetId === item.id &&
                item.mime_type === 'application/x-directory',
              'file-row-new': isNewlyCreated(item.id),
            }"
            :data-folder-id="
              item.mime_type === 'application/x-directory' ? item.id : null
            "
            :data-file-id="
              item.mime_type !== 'application/x-directory' ? item.id : null
            "
            :draggable="true"
            @dragstart="handleDragStart(item, $event)"
            @dragover="handleDragOver(item, $event)"
            @dragleave="handleDragLeave(item, $event)"
            @drop="handleDrop(item, $event)"
            @click="handleRowClick(item, $event)"
            @dblclick="handleRowDoubleClick(item, $event)"
            @contextmenu="handleContextMenu(item, $event)"
          >
            <div class="grid-cell grid-cell-checkbox">
              <input
                type="checkbox"
                :checked="isSelected(item.id)"
                @click.stop="toggleSelection(item)"
                class="file-checkbox"
              />
            </div>
            <div class="grid-cell grid-cell-name file-name">
              <span
                class="file-icon-small"
                v-html="getFileIcon(item, 'large')"
              ></span>
              <span
                v-if="editingItemId === item.id"
                class="inline-edit-container"
              >
                <input
                  v-model="editingName"
                  @keydown.enter="saveRename(item)"
                  @keydown.esc="cancelRename"
                  @blur="saveRename(item)"
                  class="inline-edit-input"
                  ref="editInput"
                />
              </span>
              <span v-else class="file-name-text">{{
                item.original_name
              }}</span>
            </div>
            <div class="grid-cell grid-cell-type file-type">
              {{ getFileType(item) }}
            </div>
            <div class="grid-cell grid-cell-size file-size">
              {{ formatSize(item) }}
            </div>
            <div class="grid-cell grid-cell-date file-date">
              {{ formatDate(item.updated_at) }}
            </div>
            <div class="grid-cell grid-cell-actions file-actions">
              <button
                @click.stop="handleMenuClick(item, $event)"
                class="btn-icon btn-menu"
                title="More options"
              >
                <span v-html="getIcon('moreVertical')"></span>
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="grid-view">
      <div class="files-grid">
        <div
          v-for="(item, index) in sortedAndFilteredItems"
          :key="item.id"
          :data-item-id="item.id"
          class="file-card glass"
          :class="{
            selected: isSelected(item.id),
            focused: focusedItemIndex === index,
            folder: item.mime_type === 'application/x-directory',
            'drop-target':
              dropTargetId === item.id &&
              item.mime_type === 'application/x-directory',
            dragging: draggedItemId === item.id,
            'file-card-new': isNewlyCreated(item.id),
          }"
          :data-folder-id="
            item.mime_type === 'application/x-directory' ? item.id : null
          "
          :data-file-id="
            item.mime_type !== 'application/x-directory' ? item.id : null
          "
          :draggable="true"
          @dragstart="handleDragStart(item, $event)"
          @dragover="handleDragOver(item, $event)"
          @dragleave="handleDragLeave(item, $event)"
          @drop="handleDrop(item, $event)"
          @click="handleCardClick(item, $event)"
          @dblclick="handleCardDoubleClick(item, $event)"
          @contextmenu="handleContextMenu(item, $event)"
        >
          <input
            type="checkbox"
            :checked="isSelected(item.id)"
            @click.stop="toggleSelection(item)"
            class="file-checkbox"
          />
          <div class="file-icon-large">
            <img
              v-if="
                hasThumbnail(item) &&
                (isImageFile(item) || isAudioFile(item)) &&
                getThumbnailUrl(item.id)
              "
              :key="`thumb-${item.id}-${thumbnailUpdateTrigger}`"
              :src="getThumbnailUrl(item.id)"
              :alt="item.original_name"
              class="file-thumbnail"
              @error="handleThumbnailError"
            />
            <span v-else v-html="getFileIcon(item, 'large')"></span>
            <span
              v-if="item.is_starred"
              class="star-icon-large"
              v-html="getIcon('star')"
            ></span>
          </div>
          <div class="file-info">
            <div v-if="editingItemId === item.id" class="inline-edit-container">
              <input
                v-model="editingName"
                @keydown.enter="saveRename(item)"
                @keydown.esc="cancelRename"
                @blur="saveRename(item)"
                class="inline-edit-input"
                ref="editInput"
              />
            </div>
            <h3 v-else class="file-name-text">{{ item.original_name }}</h3>
            <p class="file-meta">
              {{ formatSize(item) }} • {{ formatDate(item.updated_at) }}
            </p>
          </div>
          <button
            @click.stop="handleMenuClick(item, $event)"
            class="btn-icon btn-menu btn-menu-grid"
            title="More options"
          >
            <span v-html="getIcon('moreVertical')"></span>
          </button>
        </div>
      </div>
    </div>

    <FileMenuDropdown
      v-if="showMenu"
      :key="menuItem?.id || 'menu'"
      :show="showMenu"
      :item="menuItem"
      :position="menuPosition"
      @close="showMenu = false"
      @action="handleMenuAction"
    />
  </div>
</template>

<script>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
import { thumbnails, files } from "../services/api";
import { debounce } from "../utils/debounce";
import { decryptFile, decryptFileKey } from "../services/encryption";
import { getCachedVaultSpaceKey } from "../services/keyManager";
import * as mm from "music-metadata";
import FileMenuDropdown from "./FileMenuDropdown.vue";
import CustomSelect from "./CustomSelect.vue";
import { isMobileMode } from "../utils/mobileMode";

export default {
  name: "FileListView",
  components: {
    FileMenuDropdown,
    CustomSelect,
  },
  props: {
    folders: {
      type: Array,
      default: () => [],
    },
    files: {
      type: Array,
      default: () => [],
    },
    selectedItems: {
      type: Array,
      default: () => [],
    },
    viewMode: {
      type: String,
      default: "grid",
    },
    editingItemId: {
      type: [String, Number],
      default: null,
    },
    newlyCreatedItemId: {
      type: [String, Number, Array],
      default: null,
    },
    defaultSortBy: {
      type: String,
      default: "name",
    },
    defaultSortOrder: {
      type: String,
      default: "asc",
    },
    vaultspaceId: {
      type: String,
      default: null,
    },
  },
  emits: [
    "view-change",
    "item-click",
    "action",
    "selection-change",
    "item-context-menu",
    "rename",
    "drag-start",
    "drag-over",
    "drag-leave",
    "drop",
  ],
  setup(props, { emit }) {
    const isMobileView = ref(isMobileMode());
    const sortBy = ref(props.defaultSortBy);
    const sortOrder = ref(props.defaultSortOrder);
    const filterType = ref("all");
    const showMenu = ref(false);
    const menuItem = ref(null);
    const menuPosition = ref({ x: 0, y: 0 });
    const editingName = ref("");
    const editingExtension = ref(null); // Store extension separately during editing
    const dropTargetId = ref(null);
    const draggedItemId = ref(null);
    const focusedItemIndex = ref(-1); // Index of focused element for keyboard navigation

    // Helper functions to extract extension and name without extension
    const getExtension = (filename) => {
      if (!filename) return null;
      const lastDot = filename.lastIndexOf(".");
      if (lastDot === -1 || lastDot === 0) return null;
      return filename.substring(lastDot);
    };

    const getNameWithoutExtension = (filename) => {
      if (!filename) return filename;
      const lastDot = filename.lastIndexOf(".");
      if (lastDot === -1 || lastDot === 0) return filename;
      return filename.substring(0, lastDot);
    };

    // Listen for mobile mode changes
    const handleMobileModeChange = (event) => {
      isMobileView.value = event.detail?.mobileMode ?? isMobileMode();
    };

    // Force grid mode on mobile
    watch(
      [isMobileView, () => props.viewMode],
      ([mobile, mode]) => {
        if (mobile && mode === "list") {
          emit("view-change", "grid");
        }
      },
      { immediate: true },
    );

    // Expose newlyCreatedItemId for template access
    const newlyCreatedItemId = computed(() => props.newlyCreatedItemId);

    // Helper function to check if item is newly created
    // Supports both single ID and array of IDs
    const isNewlyCreated = (itemId) => {
      if (!newlyCreatedItemId.value) return false;
      if (Array.isArray(newlyCreatedItemId.value)) {
        return newlyCreatedItemId.value.includes(itemId);
      }
      return newlyCreatedItemId.value === itemId;
    };

    // Options for CustomSelect components
    const sortOptions = [
      { value: "name", label: "Name" },
      { value: "date", label: "Date" },
      { value: "size", label: "Size" },
      { value: "type", label: "Type" },
    ];

    const filterOptions = [
      { value: "all", label: "All" },
      { value: "files", label: "Files" },
      { value: "folders", label: "Folders" },
    ];

    // Column resizing state
    const columnWidths = ref({});
    const isResizing = ref(false);
    const resizingColumnIndex = ref(null);
    const startX = ref(0);
    const startWidth = ref(0);
    const tableContainer = ref(null);

    // Default column widths percentages (converted to pixels on mount)
    const defaultColumnPercentages = {
      0: 3, // Checkbox
      1: 40, // Name
      2: 18, // Type
      3: 12, // Size
      4: 18, // Modified
      5: 9, // Actions
    };

    // Column min widths (in pixels)
    const columnMinWidths = {
      0: 40, // Checkbox
      1: 200, // Name
      2: 120, // Type
      3: 100, // Size
      4: 120, // Modified
      5: 60, // Actions
    };

    // Load column widths from localStorage
    const loadColumnWidths = () => {
      try {
        const saved = localStorage.getItem("fileListView_columnWidths");
        if (saved) {
          const parsed = JSON.parse(saved);
          // Merge with defaults, only keeping valid saved values
          Object.keys(parsed).forEach((key) => {
            const index = parseInt(key);
            if (parsed[key] !== null && parsed[key] > 0) {
              columnWidths.value[index] = parsed[key];
            }
          });
        }
      } catch (e) {
        console.warn("Failed to load column widths from localStorage", e);
      }
    };

    // Save column widths to localStorage
    const saveColumnWidths = debounce(() => {
      try {
        localStorage.setItem(
          "fileListView_columnWidths",
          JSON.stringify(columnWidths.value),
        );
      } catch (e) {
        console.warn("Failed to save column widths to localStorage", e);
      }
    }, 300);

    // Calculate default width in pixels based on container width
    const calculateDefaultWidth = (index) => {
      if (defaultColumnPercentages[index] !== undefined) {
        // Get container width or use a default
        const container = tableContainer.value;
        if (container) {
          const containerWidth = container.offsetWidth;
          return Math.floor(
            (containerWidth * defaultColumnPercentages[index]) / 100,
          );
        }
        // Fallback: use percentage of a typical 1200px container
        const typicalWidth = 1200;
        return Math.floor(
          (typicalWidth * defaultColumnPercentages[index]) / 100,
        );
      }

      return null;
    };

    // Get computed width for a column (always in pixels)
    const getColumnWidth = (index) => {
      // If user has resized this column, use saved width
      if (columnWidths.value[index] !== undefined) {
        return columnWidths.value[index] + "px";
      }

      // Calculate default width in pixels
      const defaultWidth = calculateDefaultWidth(index);
      if (defaultWidth !== null) {
        return defaultWidth + "px";
      }

      return null;
    };

    // Get grid template columns string for CSS Grid
    const getGridTemplateColumns = computed(() => {
      const columns = [];
      const totalColumns = 6;

      // Use fixed widths for columns 0-4, and 1fr for the last column (Actions)
      // This ensures the last column always touches the right edge
      // When a column is resized, only that column changes width, others keep their size
      for (let i = 0; i < totalColumns - 1; i++) {
        const minWidth = columnMinWidths[i] || 80;
        let width;

        if (columnWidths.value[i] !== undefined) {
          // Use saved width for resized columns (fixed width)
          width = `${Math.max(minWidth, columnWidths.value[i])}px`;
        } else {
          // Use default percentage-based width (fixed width)
          const container = tableContainer.value;
          if (container && container.offsetWidth > 0) {
            const containerWidth = container.offsetWidth;
            width = `${Math.max(minWidth, Math.floor((containerWidth * defaultColumnPercentages[i]) / 100))}px`;
          } else {
            // Fallback: use percentage of typical 1200px container
            width = `${Math.max(minWidth, Math.floor((1200 * defaultColumnPercentages[i]) / 100))}px`;
          }
        }

        // Use fixed width - no minmax, just the fixed width
        columns.push(width);
      }

      // Last column (Actions) always uses 1fr to fill remaining space
      // This ensures it always touches the right edge
      const minWidth = columnMinWidths[totalColumns - 1] || 60;
      columns.push(`minmax(${minWidth}px, 1fr)`);

      return columns.join(" ");
    });

    // Handle resize start
    const handleResizeStart = (columnIndex, event) => {
      event.preventDefault();
      event.stopPropagation();

      // Don't allow resizing the last column (Actions)
      const totalColumns = 6;
      if (columnIndex >= totalColumns - 1) {
        return;
      }

      isResizing.value = true;
      resizingColumnIndex.value = columnIndex;
      startX.value = event.clientX;

      // Get current width of the column header from grid
      const container = tableContainer.value;
      if (container) {
        const headerRow = container.querySelector(".grid-header-row");
        if (headerRow) {
          const headerCell = headerRow.children[columnIndex];
          if (headerCell) {
            // Get computed width in pixels
            const computedStyle = window.getComputedStyle(headerCell);
            const widthValue = computedStyle.width;
            startWidth.value = parseFloat(widthValue) || headerCell.offsetWidth;

            // If column hasn't been resized yet, save current width
            if (columnWidths.value[columnIndex] === undefined) {
              columnWidths.value[columnIndex] = startWidth.value;
            }
          }
        }
      }

      // Prevent text selection during resize
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";

      // Add global event listeners
      document.addEventListener("mousemove", handleResizeMove);
      document.addEventListener("mouseup", handleResizeEnd);
    };

    // Handle resize move
    const handleResizeMove = (event) => {
      if (!isResizing.value || resizingColumnIndex.value === null) return;

      const diff = event.clientX - startX.value;
      const minWidth = columnMinWidths[resizingColumnIndex.value] || 50;
      let newWidth = Math.max(minWidth, startWidth.value + diff);

      // Calculate maximum width to ensure Actions column stays visible and never pushed out
      const container = tableContainer.value;
      if (container && container.offsetWidth > 0) {
        const containerWidth = container.offsetWidth;
        const totalColumns = 6;
        const actionsMinWidth = columnMinWidths[totalColumns - 1] || 60;

        // Calculate sum of all other fixed columns (0-4, excluding the one being resized)
        let totalOtherFixedWidth = 0;
        for (let i = 0; i < totalColumns - 1; i++) {
          if (i === resizingColumnIndex.value) {
            // Skip the column being resized
            continue;
          }

          if (columnWidths.value[i] !== undefined) {
            totalOtherFixedWidth += columnWidths.value[i];
          } else {
            // Use default width for non-resized columns
            const defaultWidth = calculateDefaultWidth(i);
            if (defaultWidth !== null) {
              totalOtherFixedWidth += defaultWidth;
            } else {
              // Fallback to min width if calculation fails
              totalOtherFixedWidth += columnMinWidths[i] || 80;
            }
          }
        }

        // Calculate maximum width: container width - other fixed columns - minimum Actions width
        // Actions column must always have at least its minimum width visible
        const maxWidth =
          containerWidth - totalOtherFixedWidth - actionsMinWidth;

        // Limit newWidth to maximum (ensure Actions column never gets pushed out)
        newWidth = Math.min(newWidth, Math.max(minWidth, maxWidth));
      }

      // Update column width
      columnWidths.value[resizingColumnIndex.value] = newWidth;
    };

    // Handle resize end
    const handleResizeEnd = () => {
      if (isResizing.value) {
        isResizing.value = false;
        resizingColumnIndex.value = null;

        // Restore cursor and selection
        document.body.style.userSelect = "";
        document.body.style.cursor = "";

        // Remove global event listeners
        document.removeEventListener("mousemove", handleResizeMove);
        document.removeEventListener("mouseup", handleResizeEnd);

        // Save to localStorage
        saveColumnWidths();
      }
    };

    // Watch for column width changes and save
    watch(
      columnWidths,
      () => {
        if (!isResizing.value) {
          saveColumnWidths();
        }
      },
      { deep: true },
    );

    // Initialize column widths on mount
    const initializeColumnWidths = () => {
      loadColumnWidths();
      // Don't initialize default widths - they will be calculated dynamically
      // Only use saved widths from localStorage
    };

    // Load column widths on mount
    onMounted(() => {
      // Setup mobile mode listener
      window.addEventListener("mobile-mode-changed", handleMobileModeChange);
      // Check on mount
      isMobileView.value = isMobileMode();

      initializeColumnWidths();
    });

    // Cleanup on unmount
    onUnmounted(() => {
      if (isResizing.value) {
        handleResizeEnd();
      }
    });

    const allItems = computed(() => {
      return [...props.folders, ...props.files];
    });

    const filteredItems = computed(() => {
      if (filterType.value === "files") {
        return allItems.value.filter(
          (item) => item.mime_type !== "application/x-directory",
        );
      } else if (filterType.value === "folders") {
        return allItems.value.filter(
          (item) => item.mime_type === "application/x-directory",
        );
      }
      return allItems.value;
    });

    const sortedAndFilteredItems = computed(() => {
      const items = [...filteredItems.value];
      items.sort((a, b) => {
        let aVal, bVal;

        if (sortBy.value === "name") {
          aVal = a.original_name.toLowerCase();
          bVal = b.original_name.toLowerCase();
        } else if (sortBy.value === "date") {
          aVal = new Date(a.updated_at || a.created_at);
          bVal = new Date(b.updated_at || b.created_at);
        } else if (sortBy.value === "size") {
          aVal = a.size || 0;
          bVal = b.size || 0;
        } else if (sortBy.value === "type") {
          aVal = a.mime_type || "";
          bVal = b.mime_type || "";
        }

        if (aVal < bVal) return sortOrder.value === "asc" ? -1 : 1;
        if (aVal > bVal) return sortOrder.value === "asc" ? 1 : -1;
        return 0;
      });

      return items;
    });

    const allSelected = computed(() => {
      return (
        sortedAndFilteredItems.value.length > 0 &&
        sortedAndFilteredItems.value.every((item) =>
          props.selectedItems.some((selected) => selected.id === item.id),
        )
      );
    });

    const getIcon = (iconName) => {
      if (!window.Icons) {
        console.warn("window.Icons not available");
        return "";
      }
      if (window.Icons[iconName]) {
        const iconFunction = window.Icons[iconName];
        if (typeof iconFunction === "function") {
          const icon = iconFunction.call(window.Icons, 16, "#ffffff");
          if (!icon || icon.trim() === "") {
            console.warn(`Icon ${iconName} returned empty string`);
          }
          return icon;
        }
      }
      console.warn(`Icon ${iconName} not found`);
      return "";
    };

    const getSortIcon = () => {
      return sortOrder.value === "asc" ? "↑" : "↓";
    };

    const getFileIcon = (item, size = "large") => {
      if (!window.Icons) {
        return item.mime_type === "application/x-directory" ? "📁" : "📄";
      }
      const iconSize = size === "large" ? 48 : 48;
      if (item.mime_type === "application/x-directory") {
        return window.Icons.folder(iconSize, "currentColor");
      }

      // Use the centralized icon helper function
      const iconName = window.Icons.getFileIconName
        ? window.Icons.getFileIconName(item.mime_type, item.original_name)
        : "file";

      // Get the icon function and call it with proper context
      const iconFunction = window.Icons[iconName];
      if (iconFunction && typeof iconFunction === "function") {
        return iconFunction.call(window.Icons, iconSize, "currentColor");
      }

      // Fallback to generic file icon
      return window.Icons.file(iconSize, "currentColor");
    };

    const handleSortChange = debounce(() => {
      emit("selection-change", {
        sortBy: sortBy.value,
        sortOrder: sortOrder.value,
      });
    }, 150);

    const handleFilterChange = debounce(() => {
      emit("selection-change", {
        filterType: filterType.value,
      });
    }, 150);

    const toggleSortOrder = () => {
      sortOrder.value = sortOrder.value === "asc" ? "desc" : "asc";
      handleSortChange();
    };

    const sortByColumn = (column) => {
      if (sortBy.value === column) {
        toggleSortOrder();
      } else {
        sortBy.value = column;
        sortOrder.value = "asc";
        handleSortChange();
      }
    };

    // Handle header click - only sort if not clicking on resizer
    const handleHeaderClick = (column, event) => {
      // Don't sort if clicking on the resizer
      if (event.target.classList.contains("column-resizer")) {
        return;
      }
      sortByColumn(column);
    };

    const isSelected = (itemId) => {
      return props.selectedItems.some((item) => item.id === itemId);
    };

    const toggleSelection = (item) => {
      emit("selection-change", {
        action: isSelected(item.id) ? "deselect" : "select",
        item,
      });
    };

    const handleSelectAll = (event) => {
      if (event.target.checked) {
        emit("selection-change", {
          action: "select-all",
          items: sortedAndFilteredItems.value,
        });
      } else {
        emit("selection-change", {
          action: "clear",
        });
      }
    };

    const handleRowClick = (item, event) => {
      if (
        event.target.type === "checkbox" ||
        event.target.closest(".btn-menu") ||
        event.target.closest(".inline-edit-input")
      ) {
        return;
      }

      // Close menu if open
      if (showMenu.value) {
        showMenu.value = false;
      }

      // Improve multiple selection with Ctrl/Cmd + click
      if (event.ctrlKey || event.metaKey) {
        toggleSelection(item);
      } else if (event.shiftKey) {
        // Range selection with Shift + click
        const currentIndex = sortedAndFilteredItems.value.findIndex(
          (i) => i.id === item.id,
        );
        if (
          focusedItemIndex.value >= 0 &&
          focusedItemIndex.value !== currentIndex
        ) {
          const start = Math.min(focusedItemIndex.value, currentIndex);
          const end = Math.max(focusedItemIndex.value, currentIndex);
          const itemsToSelect = sortedAndFilteredItems.value.slice(
            start,
            end + 1,
          );
          const newSelection = [...props.selectedItems];
          itemsToSelect.forEach((i) => {
            if (!newSelection.some((s) => s.id === i.id)) {
              newSelection.push(i);
            }
          });
          emit("selection-change", newSelection);
        } else {
          toggleSelection(item);
        }
      } else {
        // Simple click - select and open
        if (!isSelected(item.id)) {
          emit("selection-change", [item]);
        }
        emit("item-click", item, event);
      }
      focusedItemIndex.value = sortedAndFilteredItems.value.findIndex(
        (i) => i.id === item.id,
      );
    };

    const handleCardClick = (item, event) => {
      if (
        event.target.type === "checkbox" ||
        event.target.closest(".btn-menu") ||
        event.target.closest(".inline-edit-input")
      ) {
        return;
      }

      // Close menu if open
      if (showMenu.value) {
        showMenu.value = false;
      }

      // Improve multiple selection with Ctrl/Cmd + click
      if (event.ctrlKey || event.metaKey) {
        toggleSelection(item);
      } else if (event.shiftKey) {
        // Range selection with Shift + click
        const currentIndex = sortedAndFilteredItems.value.findIndex(
          (i) => i.id === item.id,
        );
        if (
          focusedItemIndex.value >= 0 &&
          focusedItemIndex.value !== currentIndex
        ) {
          const start = Math.min(focusedItemIndex.value, currentIndex);
          const end = Math.max(focusedItemIndex.value, currentIndex);
          const itemsToSelect = sortedAndFilteredItems.value.slice(
            start,
            end + 1,
          );
          const newSelection = [...props.selectedItems];
          itemsToSelect.forEach((i) => {
            if (!newSelection.some((s) => s.id === i.id)) {
              newSelection.push(i);
            }
          });
          emit("selection-change", newSelection);
        } else {
          toggleSelection(item);
        }
      } else {
        // Simple click - select and open
        if (!isSelected(item.id)) {
          emit("selection-change", [item]);
        }
        emit("item-click", item, event);
      }
      focusedItemIndex.value = sortedAndFilteredItems.value.findIndex(
        (i) => i.id === item.id,
      );
    };

    const handleRowDoubleClick = (item, event) => {
      event.stopPropagation();
      // Only preview files, not folders
      if (item.mime_type !== "application/x-directory") {
        emit("action", "preview", item);
      }
    };

    const handleCardDoubleClick = (item, event) => {
      event.stopPropagation();
      // Only preview files, not folders
      if (item.mime_type !== "application/x-directory") {
        emit("action", "preview", item);
      }
    };

    const handleMenuClick = (item, event) => {
      event.stopPropagation();
      event.preventDefault();

      // Close menu if already open for the same item
      if (showMenu.value && menuItem.value?.id === item.id) {
        showMenu.value = false;
        return;
      }

      // Open menu with exact click coordinates
      openMenuForItem(item, event);
    };

    const openMenuForItem = (item, event) => {
      // Capture exact click coordinates BEFORE any other operation
      const clickX = event.clientX;
      const clickY = event.clientY;

      // Update position and item
      menuPosition.value = {
        x: clickX,
        y: clickY,
      };

      menuItem.value = item;

      // Open menu in next tick to ensure DOM is ready
      nextTick(() => {
        showMenu.value = true;
      });
    };

    const handleMenuAction = (action, item) => {
      if (action === "rename") {
        editingName.value = item.original_name;
        emit("rename", item);
      } else {
        emit("action", action, item);
      }
    };

    const saveRename = (item) => {
      if (!editingName.value.trim()) {
        editingName.value = "";
        editingExtension.value = null;
        emit("action", "cancel-rename");
        return;
      }

      let finalName = editingName.value.trim();

      // For files (not folders), reattach extension if it existed
      if (
        item.mime_type !== "application/x-directory" &&
        editingExtension.value
      ) {
        finalName = finalName + editingExtension.value;
      }

      // Only emit rename if name actually changed
      if (finalName !== item.original_name) {
        emit("action", "rename", item, finalName);
      }

      editingName.value = "";
      editingExtension.value = null;
      emit("action", "cancel-rename");
    };

    const cancelRename = () => {
      editingName.value = "";
      editingExtension.value = null;
      emit("action", "cancel-rename");
    };

    const handleContextMenu = (item, event) => {
      event.preventDefault();
      emit("item-context-menu", item, event);
    };

    const handleDragStart = (item, event) => {
      draggedItemId.value = item.id;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData(
        "application/json",
        JSON.stringify({
          id: item.id,
          type:
            item.mime_type === "application/x-directory" ? "folder" : "file",
        }),
      );
      emit("drag-start", item, event);
    };

    const handleDragOver = (item, event) => {
      if (
        item.mime_type === "application/x-directory" &&
        draggedItemId.value !== item.id
      ) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        dropTargetId.value = item.id;
        emit("drag-over", item, event);
      }
    };

    const handleDragLeave = (item, event) => {
      if (dropTargetId.value === item.id) {
        dropTargetId.value = null;
        emit("drag-leave", item, event);
      }
    };

    const handleDrop = (item, event) => {
      event.preventDefault();
      if (
        item.mime_type === "application/x-directory" &&
        dropTargetId.value === item.id
      ) {
        dropTargetId.value = null;
        draggedItemId.value = null;
        emit("drop", item, event);
      }
    };

    const formatSize = (item) => {
      // For folders, use total_size if available, otherwise size
      const bytes =
        item.total_size !== undefined ? item.total_size : item.size || 0;
      if (!bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    const formatDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleDateString();
    };

    const getFileType = (item) => {
      if (item.mime_type === "application/x-directory") {
        return "Folder";
      }

      // Mapping of mime_types to readable names
      const mimeTypeMap = {
        // Images
        "image/png": "PNG Image",
        "image/jpeg": "JPEG Image",
        "image/jpg": "JPEG Image",
        "image/gif": "GIF Image",
        "image/webp": "WebP Image",
        "image/svg+xml": "SVG Image",
        "image/bmp": "BMP Image",
        "image/tiff": "TIFF Image",
        "image/x-icon": "Icon",
        // Documents
        "application/pdf": "PDF Document",
        "application/msword": "Word Document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
          "Word Document",
        "application/vnd.ms-excel": "Excel Spreadsheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
          "Excel Spreadsheet",
        "application/vnd.ms-powerpoint": "PowerPoint Presentation",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation":
          "PowerPoint Presentation",
        "application/vnd.oasis.opendocument.text": "OpenDocument Text",
        "application/vnd.oasis.opendocument.spreadsheet":
          "OpenDocument Spreadsheet",
        "application/vnd.oasis.opendocument.presentation":
          "OpenDocument Presentation",
        // Archives
        "application/zip": "ZIP Archive",
        "application/x-zip-compressed": "ZIP Archive",
        "application/x-rar-compressed": "RAR Archive",
        "application/x-rar": "RAR Archive",
        "application/x-7z-compressed": "7Z Archive",
        "application/x-tar": "TAR Archive",
        "application/gzip": "GZIP Archive",
        "application/x-gzip": "GZIP Archive",
        // Media
        "video/mp4": "MP4 Video",
        "video/mpeg": "MPEG Video",
        "video/quicktime": "QuickTime Video",
        "video/x-msvideo": "AVI Video",
        "video/webm": "WebM Video",
        "audio/mpeg": "MP3 Audio",
        "audio/mp3": "MP3 Audio",
        "audio/wav": "WAV Audio",
        "audio/x-wav": "WAV Audio",
        "audio/ogg": "OGG Audio",
        "audio/webm": "WebM Audio",
        "audio/flac": "FLAC Audio",
        // Text
        "text/plain": "Text File",
        "text/html": "HTML Document",
        "text/css": "CSS Stylesheet",
        "text/javascript": "JavaScript",
        "text/json": "JSON File",
        "application/json": "JSON File",
        "text/xml": "XML Document",
        "application/xml": "XML Document",
        "text/csv": "CSV File",
        "text/markdown": "Markdown",
        // Code
        "application/javascript": "JavaScript",
        "application/x-python": "Python Script",
        "text/x-python": "Python Script",
        "text/x-java": "Java Source",
        "text/x-c": "C Source",
        "text/x-c++": "C++ Source",
        "text/x-csharp": "C# Source",
        // Other
        "application/x-iso9660-image": "ISO Image",
        "application/x-cd-image": "ISO Image",
        "application/x-dmg": "DMG Image",
        "application/x-executable": "Executable",
        "application/x-sh": "Shell Script",
        "application/x-bash": "Bash Script",
      };

      // Check mime_type first
      if (item.mime_type && mimeTypeMap[item.mime_type]) {
        return mimeTypeMap[item.mime_type];
      }

      // If mime_type starts with "image/", "video/", "audio/", or "text/", use the subtype
      if (item.mime_type) {
        const [type, subtype] = item.mime_type.split("/");
        if (type === "image") {
          return `${subtype.toUpperCase()} Image`;
        } else if (type === "video") {
          return `${subtype.toUpperCase()} Video`;
        } else if (type === "audio") {
          return `${subtype.toUpperCase()} Audio`;
        } else if (type === "text") {
          return `${subtype.toUpperCase()} Text`;
        }
      }

      // Fallback: use file extension
      if (item.original_name) {
        const extension = item.original_name.split(".").pop()?.toLowerCase();
        if (extension) {
          const extensionMap = {
            png: "PNG Image",
            jpg: "JPEG Image",
            jpeg: "JPEG Image",
            gif: "GIF Image",
            webp: "WebP Image",
            svg: "SVG Image",
            bmp: "BMP Image",
            pdf: "PDF Document",
            doc: "Word Document",
            docx: "Word Document",
            xls: "Excel Spreadsheet",
            xlsx: "Excel Spreadsheet",
            ppt: "PowerPoint Presentation",
            pptx: "PowerPoint Presentation",
            zip: "ZIP Archive",
            rar: "RAR Archive",
            "7z": "7Z Archive",
            tar: "TAR Archive",
            gz: "GZIP Archive",
            iso: "ISO Image",
            dmg: "DMG Image",
            mp4: "MP4 Video",
            mpeg: "MPEG Video",
            avi: "AVI Video",
            webm: "WebM Video",
            mp3: "MP3 Audio",
            wav: "WAV Audio",
            ogg: "OGG Audio",
            flac: "FLAC Audio",
            txt: "Text File",
            html: "HTML Document",
            css: "CSS Stylesheet",
            js: "JavaScript",
            json: "JSON File",
            xml: "XML Document",
            csv: "CSV File",
            md: "Markdown",
            py: "Python Script",
            java: "Java Source",
            c: "C Source",
            cpp: "C++ Source",
            cs: "C# Source",
            sh: "Shell Script",
            bash: "Bash Script",
          };

          if (extensionMap[extension]) {
            return extensionMap[extension];
          }

          // If extension is not in mapping, return extension in uppercase
          return extension.toUpperCase();
        }
      }

      // Last fallback: use mime_type subtype
      if (item.mime_type) {
        const parts = item.mime_type.split("/");
        const subtype = parts[parts.length - 1];
        // If it's "octet-stream", try to guess from extension
        if (subtype === "octet-stream" && item.original_name) {
          const ext = item.original_name.split(".").pop()?.toUpperCase();
          return ext || "Binary File";
        }
        return subtype.toUpperCase();
      }

      return "Unknown";
    };

    // Initialize global thumbnail cache if not exists
    if (!window.__leyzenThumbnailUrls) {
      window.__leyzenThumbnailUrls = new Map();
    }

    const thumbnailUpdateTrigger = ref(0); // Force reactivity trigger

    const getThumbnailUrl = (fileId) => {
      // Access thumbnailUpdateTrigger to create dependency
      void thumbnailUpdateTrigger.value;
      // Return cached URL from global cache if available
      return window.__leyzenThumbnailUrls.get(fileId) || "";
    };

    // Load thumbnail URL - for images, load the image directly without checking for thumbnail
    // This avoids 404 errors in the network tab
    const loadThumbnailUrl = async (fileId, file = null) => {
      if (window.__leyzenThumbnailUrls.has(fileId)) {
        return; // Already loaded
      }

      // Find file object if not provided
      if (!file) {
        file = allItems.value.find((f) => f.id === fileId);
      }

      if (!file) {
        return;
      }

      // Load image thumbnail
      if (isImageFile(file)) {
        try {
          await loadImageAsThumbnail(file);
        } catch (imageError) {
          console.error(
            `Failed to load image as thumbnail for ${fileId}:`,
            imageError,
          );
        }
        return;
      }

      // Load audio cover as thumbnail
      if (isAudioFile(file)) {
        try {
          await loadAudioCoverAsThumbnail(file);
        } catch (audioError) {
          // Silently fail - no cover art available
          console.debug(
            `No cover art available for audio file ${fileId}:`,
            audioError,
          );
        }
        return;
      }
    };

    // Load image directly as thumbnail (fallback when thumbnail doesn't exist)
    const loadImageAsThumbnail = async (file) => {
      const vaultspaceId = props.vaultspaceId || file.vaultspace_id;
      if (!vaultspaceId) {
        return;
      }

      try {
        // Get VaultSpace key
        const vaultspaceKey = getCachedVaultSpaceKey(vaultspaceId);
        if (!vaultspaceKey) {
          return;
        }

        // Download encrypted file
        const encryptedData = await files.download(file.id, vaultspaceId);

        // Get file key
        const fileData = await files.get(file.id, vaultspaceId);
        if (!fileData.file_key) {
          return;
        }

        // Decrypt file key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create blob URL for the image
        const blob = new Blob([decryptedData], { type: file.mime_type });
        const blobUrl = URL.createObjectURL(blob);

        // Store in global cache
        window.__leyzenThumbnailUrls.set(file.id, blobUrl);

        // Force Vue to update
        thumbnailUpdateTrigger.value++;
        await nextTick();
      } catch (error) {
        console.error(
          `Failed to load image as thumbnail for ${file.id}:`,
          error,
        );
      }
    };

    // Load audio cover art as thumbnail
    const loadAudioCoverAsThumbnail = async (file) => {
      const vaultspaceId = props.vaultspaceId || file.vaultspace_id;
      if (!vaultspaceId) {
        return;
      }

      try {
        // Get VaultSpace key
        const vaultspaceKey = getCachedVaultSpaceKey(vaultspaceId);
        if (!vaultspaceKey) {
          return;
        }

        // Download encrypted file
        const encryptedData = await files.download(file.id, vaultspaceId);

        // Get file key
        const fileData = await files.get(file.id, vaultspaceId);
        if (!fileData.file_key) {
          return;
        }

        // Decrypt file key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create a Blob from the decrypted data
        const arrayBuffer =
          decryptedData instanceof ArrayBuffer
            ? decryptedData
            : decryptedData.buffer || new Uint8Array(decryptedData).buffer;

        const blob = new Blob([arrayBuffer], {
          type: file.mime_type || "audio/mpeg",
        });

        // Parse metadata using music-metadata
        // Convert blob to ArrayBuffer for parsing
        const audioArrayBuffer = await blob.arrayBuffer();
        const metadata = await mm.parseBuffer(
          new Uint8Array(audioArrayBuffer),
          blob.type,
        );

        // Check if there's a picture/cover art in the metadata
        if (metadata.common?.picture && metadata.common.picture.length > 0) {
          // Get the first picture (usually the album cover)
          const picture = metadata.common.picture[0];

          if (picture?.data) {
            // Convert picture.data to Uint8Array
            let pictureData;
            if (picture.data instanceof Uint8Array) {
              pictureData = picture.data;
            } else if (picture.data instanceof ArrayBuffer) {
              pictureData = new Uint8Array(picture.data);
            } else if (Buffer && Buffer.isBuffer(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else if (Array.isArray(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else {
              pictureData = new Uint8Array(Object.values(picture.data));
            }

            // Determine MIME type from format
            let pictureFormat = "image/jpeg"; // Default
            if (picture.format) {
              const format = picture.format.toLowerCase();
              if (format.startsWith("image/")) {
                pictureFormat = picture.format;
              } else {
                const formatMap = {
                  jpeg: "image/jpeg",
                  jpg: "image/jpeg",
                  png: "image/png",
                  gif: "image/gif",
                  bmp: "image/bmp",
                  webp: "image/webp",
                };
                pictureFormat = formatMap[format] || "image/jpeg";
              }
            }

            const pictureBlob = new Blob([pictureData], {
              type: pictureFormat,
            });
            const blobUrl = URL.createObjectURL(pictureBlob);

            // Store in global cache
            window.__leyzenThumbnailUrls.set(file.id, blobUrl);

            // Force Vue to update
            thumbnailUpdateTrigger.value++;
            await nextTick();
          }
        }
      } catch (error) {
        // Silently fail - no cover art available
        console.debug(
          `Failed to load audio cover as thumbnail for ${file.id}:`,
          error,
        );
      }
    };

    const hasThumbnail = (file) => {
      // For images, always try to show thumbnail (either from storage or load image directly)
      // For audio files, check if thumbnail URL is already cached (meaning cover was found)
      // The actual check is done when loading the thumbnail
      return (
        isImageFile(file) ||
        (isAudioFile(file) && window.__leyzenThumbnailUrls.has(file.id)) ||
        generatedThumbnails.value.has(file.id)
      );
    };

    // Check if file is an image based on mime_type or file extension
    const isImageFile = (file) => {
      // Check mime_type first
      if (file.mime_type?.startsWith("image/")) {
        return true;
      }

      // Fallback: check file extension for common image formats
      if (file.original_name) {
        const extension = file.original_name.split(".").pop()?.toLowerCase();
        const imageExtensions = [
          "png",
          "jpg",
          "jpeg",
          "gif",
          "webp",
          "bmp",
          "svg",
          "ico",
          "tiff",
          "tif",
        ];
        return imageExtensions.includes(extension);
      }

      return false;
    };

    // Check if file is an audio file based on mime_type or file extension
    const isAudioFile = (file) => {
      // Check mime_type first
      if (file.mime_type?.startsWith("audio/")) {
        return true;
      }

      // Fallback: check file extension for common audio formats
      if (file.original_name) {
        const extension = file.original_name.split(".").pop()?.toLowerCase();
        const audioExtensions = ["mp3", "wav", "flac", "ogg", "m4a", "aac"];
        return audioExtensions.includes(extension);
      }

      return false;
    };

    const handleThumbnailError = (event) => {
      event.target.style.display = "none";
    };

    watch(
      () => props.editingItemId,
      (newId) => {
        if (newId) {
          const item = allItems.value.find((i) => i.id === newId);
          if (item) {
            // For folders, show full name. For files, hide extension
            if (item.mime_type === "application/x-directory") {
              editingName.value = item.original_name;
              editingExtension.value = null;
            } else {
              editingExtension.value = getExtension(item.original_name);
              editingName.value = getNameWithoutExtension(item.original_name);
            }
            nextTick(() => {
              const input = document.querySelector(".inline-edit-input");
              if (input) {
                input.focus();
                input.select();
              }
            });
          }
        } else {
          editingName.value = "";
          editingExtension.value = null;
        }
      },
    );

    // Watch for changes to default sort props
    watch(
      () => [props.defaultSortBy, props.defaultSortOrder],
      ([newSortBy, newSortOrder]) => {
        sortBy.value = newSortBy;
        sortOrder.value = newSortOrder;
      },
    );

    // Keyboard navigation - local handler for when focus is on the component
    const handleKeyDown = (event) => {
      // Ignore if editing a name
      if (props.editingItemId) {
        return;
      }

      // Ignore if in an input or textarea
      if (
        event.target.tagName === "INPUT" ||
        event.target.tagName === "TEXTAREA" ||
        event.target.isContentEditable
      ) {
        return;
      }

      const items = sortedAndFilteredItems.value;
      if (items.length === 0) return;

      // Handle Ctrl+A / Cmd+A to select all files
      if ((event.ctrlKey || event.metaKey) && event.key === "a") {
        event.preventDefault();
        emit("selection-change", {
          action: "select-all",
          items: items,
        });
        return;
      }

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          if (focusedItemIndex.value < items.length - 1) {
            focusedItemIndex.value++;
          } else {
            focusedItemIndex.value = 0;
          }
          scrollToFocusedItem();
          break;

        case "ArrowUp":
          event.preventDefault();
          if (focusedItemIndex.value > 0) {
            focusedItemIndex.value--;
          } else {
            focusedItemIndex.value = items.length - 1;
          }
          scrollToFocusedItem();
          break;

        case "Enter":
          event.preventDefault();
          if (
            focusedItemIndex.value >= 0 &&
            focusedItemIndex.value < items.length
          ) {
            const item = items[focusedItemIndex.value];
            emit("item-click", item, event);
          }
          break;

        case " ":
          event.preventDefault();
          if (
            focusedItemIndex.value >= 0 &&
            focusedItemIndex.value < items.length
          ) {
            const item = items[focusedItemIndex.value];
            toggleSelection(item);
          }
          break;

        case "Home":
          event.preventDefault();
          focusedItemIndex.value = 0;
          scrollToFocusedItem();
          break;

        case "End":
          event.preventDefault();
          focusedItemIndex.value = items.length - 1;
          scrollToFocusedItem();
          break;
      }
    };

    // Global keyboard handler that works even without focus on the component
    const handleGlobalKeyDown = (event) => {
      // Only handle if the component is active (has items to display)
      const items = sortedAndFilteredItems.value;
      if (items.length === 0) return;

      // Ignore if editing a name
      if (props.editingItemId) {
        return;
      }

      // Check if we're in an editable element
      const isInEditableElement =
        event.target.tagName === "INPUT" ||
        event.target.tagName === "TEXTAREA" ||
        event.target.isContentEditable;

      // Check if we're within the file-list-view
      const isWithinFileListView = event.target.closest(".file-list-view");

      // Handle Ctrl+A / Cmd+A globally to select all files
      // This should work even when clicking on sidebar or other areas
      if ((event.ctrlKey || event.metaKey) && event.key === "a") {
        // If we're in a search input or textarea outside file-list-view, let it handle CTRL+A normally
        const isInSearchOrInput = isInEditableElement && !isWithinFileListView;
        if (isInSearchOrInput) {
          return;
        }

        // Otherwise, handle file selection
        event.preventDefault();
        event.stopPropagation();
        emit("selection-change", {
          action: "select-all",
          items: items,
        });
        return;
      }

      // For navigation keys (arrows, enter, space, home, end), only handle if within file-list-view
      // and not in an editable element
      if (!isWithinFileListView || isInEditableElement) {
        return;
      }

      // Handle navigation keys when appropriate
      switch (event.key) {
        case "ArrowDown":
        case "ArrowUp":
        case "Enter":
        case " ":
        case "Home":
        case "End":
          handleKeyDown(event);
          break;
      }
    };

    const scrollToFocusedItem = () => {
      if (focusedItemIndex.value < 0) return;
      const items = sortedAndFilteredItems.value;
      if (focusedItemIndex.value >= items.length) return;

      nextTick(() => {
        const item = items[focusedItemIndex.value];
        const element = document.querySelector(`[data-item-id="${item.id}"]`);
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "nearest" });
          // Select focused element if not already selected
          if (!isSelected(item.id)) {
            emit("selection-change", [item]);
          }
        }
      });
    };

    const handleViewClick = (event) => {
      // Check if clicking on a file item
      const clickedFileItem =
        event.target.closest(".file-card") ||
        event.target.closest(".file-row") ||
        event.target.closest(".grid-body-row");

      // Check if clicking on interactive elements
      const clickedInteractive =
        event.target.closest(".btn-menu") ||
        event.target.closest(".btn-menu-grid") ||
        event.target.closest(".file-menu-container") ||
        event.target.type === "checkbox" ||
        event.target.closest(".inline-edit-input") ||
        event.target.closest(".view-controls") ||
        event.target.closest(".grid-header-row") ||
        event.target.closest(".batch-actions-bar") ||
        event.target.closest(".batch-info") ||
        event.target.closest(".batch-buttons") ||
        event.target.closest(".modal-overlay") ||
        event.target.closest(".modal") ||
        event.target.closest(".confirmation-modal") ||
        event.target.closest(".alert-modal");

      // Close menu if clicking on view (but not on a specific element)
      if (showMenu.value && !clickedFileItem && !clickedInteractive) {
        showMenu.value = false;
      }

      // Deselect all items if clicking in empty space within file-list-view
      // (like clicking on the background, not on a file item)
      if (
        props.selectedItems.length > 0 &&
        !clickedFileItem &&
        !clickedInteractive &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.shiftKey
      ) {
        emit("selection-change", {
          action: "clear",
        });
      }
    };

    // Global click handler to close menu and deselect items when clicking outside
    const handleGlobalClick = (event) => {
      // Check if click is inside the menu
      const menuContainer = document.querySelector(".file-menu-container");
      const isInsideMenu =
        menuContainer && menuContainer.contains(event.target);

      // Check if click is inside file-list-view (handled by handleViewClick)
      const isInsideFileListView = event.target.closest(".file-list-view");

      // Check if click is on batch actions bar (Download, Delete buttons)
      const isInsideBatchActions = event.target.closest(
        ".batch-actions-bar, .batch-info, .batch-buttons",
      );

      // Check if click is on a modal (confirmation, alert, etc.)
      const isInsideModal = event.target.closest(
        ".modal-overlay, .modal, .confirmation-modal, .alert-modal",
      );

      // Check if it's a click on a menu button (3 dots) - don't close/deselect in this case
      const clickedButton = event.target.closest(".btn-menu, .btn-menu-grid");

      // Check if click is on a file/folder item (row or card)
      const clickedFileItem = event.target.closest(
        ".grid-body-row, .file-card",
      );

      // Check if click is on a checkbox
      const clickedCheckbox = event.target.type === "checkbox";

      // Check if click is inside an input or textarea (editing)
      const isInEditableElement =
        event.target.tagName === "INPUT" ||
        event.target.tagName === "TEXTAREA" ||
        event.target.isContentEditable;

      // Close menu if open and clicking outside
      if (showMenu.value && !isInsideMenu && !clickedButton) {
        showMenu.value = false;
      }

      // Deselect all items if clicking outside file-list-view (sidebar, header, etc.)
      // Only if there are selected items and we're not clicking on interactive elements
      // Note: Clicks inside file-list-view are handled by handleViewClick
      if (
        !isInsideFileListView &&
        props.selectedItems.length > 0 &&
        !clickedFileItem &&
        !clickedCheckbox &&
        !isInEditableElement &&
        !clickedButton &&
        !isInsideMenu &&
        !isInsideBatchActions &&
        !isInsideModal
      ) {
        // Don't deselect if Ctrl/Cmd or Shift is held (for multi-selection)
        if (!event.ctrlKey && !event.metaKey && !event.shiftKey) {
          emit("selection-change", {
            action: "clear",
          });
        }
      }
    };

    // Global scroll handler to close menu when scrolling
    // This uses event delegation - we listen on document/window/body which will
    // catch scroll events from all child elements due to event bubbling
    const handleGlobalScroll = (event) => {
      if (showMenu.value) {
        showMenu.value = false;
      }
    };

    // Thumbnail generation state
    const generatingThumbnails = ref(new Set());
    const failedThumbnails = ref(new Set());
    const generatedThumbnails = ref(new Set()); // Track successfully generated thumbnails
    const MAX_CONCURRENT_GENERATIONS = 2;
    let thumbnailObserver = null;

    // Generate thumbnail for a file
    const generateThumbnailForFile = async (file) => {
      // Check if file is an image without thumbnail
      if (
        !isImageFile(file) ||
        hasThumbnail(file) ||
        generatingThumbnails.value.has(file.id) ||
        failedThumbnails.value.has(file.id)
      ) {
        return;
      }

      // Get vaultspaceId from prop or file
      const vaultspaceId = props.vaultspaceId || file.vaultspace_id;
      if (!vaultspaceId) {
        return;
      }

      // Check if we're at max concurrent generations
      if (generatingThumbnails.value.size >= MAX_CONCURRENT_GENERATIONS) {
        return;
      }

      generatingThumbnails.value.add(file.id);

      try {
        // Get VaultSpace key
        const vaultspaceKey = getCachedVaultSpaceKey(vaultspaceId);
        if (!vaultspaceKey) {
          failedThumbnails.value.add(file.id);
          return;
        }

        // Download encrypted file
        let encryptedData;
        try {
          encryptedData = await files.download(file.id, vaultspaceId);
        } catch (downloadError) {
          // If file not found (404), it might be a new file that's not yet synced
          // Check if file was created recently (within last 5 minutes)
          const fileCreatedAt = file.created_at
            ? new Date(file.created_at)
            : null;
          const isRecentFile =
            fileCreatedAt &&
            Date.now() - fileCreatedAt.getTime() < 5 * 60 * 1000;

          if (
            downloadError.message?.includes("404") ||
            downloadError.message?.includes("not found")
          ) {
            if (isRecentFile) {
              // For recent files, don't mark as failed - might be syncing
              // Remove from generating set so it can be retried
              generatingThumbnails.value.delete(file.id);
              return;
            } else {
              // For older files, mark as failed
              failedThumbnails.value.add(file.id);
              return;
            }
          }
          throw downloadError;
        }

        // Get file key from server
        const fileData = await files.get(file.id, vaultspaceId);
        if (!fileData.file_key) {
          failedThumbnails.value.add(file.id);
          return;
        }

        // Decrypt file key with VaultSpace key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Decrypt file data
        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Convert to base64 efficiently (avoid stack overflow for large files)
        const uint8Array = new Uint8Array(decryptedData);
        let binary = "";
        const chunkSize = 8192; // Process in chunks to avoid stack overflow
        for (let i = 0; i < uint8Array.length; i += chunkSize) {
          const chunk = uint8Array.slice(i, i + chunkSize);
          // Convert chunk to array for apply
          const chunkArray = Array.from(chunk);
          binary += String.fromCharCode.apply(null, chunkArray);
        }
        const base64Data = btoa(binary);

        // Generate thumbnail
        await thumbnails.generate(file.id, base64Data);

        // Mark as generated to refresh display
        generatedThumbnails.value.add(file.id);

        // Wait a bit for database to be updated
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Load thumbnail URL for display
        try {
          await loadThumbnailUrl(file.id, file);
        } catch (error) {
          // Don't mark as failed, will retry later
        }

        // Trigger reactivity update
        nextTick(() => {
          // Re-setup observer to handle newly generated thumbnails
          if (props.viewMode === "grid") {
            setupThumbnailObserver();
          }
        });
      } catch (err) {
        console.error(
          `Failed to generate thumbnail for file ${file.id} (${file.original_name}):`,
          err,
        );
        failedThumbnails.value.add(file.id);
      } finally {
        generatingThumbnails.value.delete(file.id);
      }
    };

    // Setup Intersection Observer for lazy loading thumbnails
    const setupThumbnailObserver = () => {
      if (thumbnailObserver) {
        thumbnailObserver.disconnect();
      }

      thumbnailObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              // entry.target is the file-card element we're observing
              const fileCard = entry.target;
              const fileId = fileCard.dataset.fileId;
              if (fileId) {
                const file = allItems.value.find((f) => f.id === fileId);
                if (file) {
                  generateThumbnailForFile(file);
                }
              }
            }
          });
        },
        {
          rootMargin: "50px", // Start loading slightly before entering viewport
          threshold: 0.1,
        },
      );

      // Observe all file cards in grid view
      if (props.viewMode === "grid") {
        // Use a small delay to ensure DOM is ready
        setTimeout(() => {
          const fileCards = document.querySelectorAll(".file-card");
          fileCards.forEach((card) => {
            const fileId = card.dataset.fileId;
            if (fileId) {
              const file = allItems.value.find((f) => f.id === fileId);
              if (file) {
                if (
                  file &&
                  (isImageFile(file) || isAudioFile(file)) &&
                  !window.__leyzenThumbnailUrls.has(file.id) && // Thumbnail not loaded yet
                  !generatingThumbnails.value.has(file.id) &&
                  !failedThumbnails.value.has(file.id)
                ) {
                  // Try to load thumbnail first (will fallback to image/audio cover if needed)
                  loadThumbnailUrl(file.id, file);

                  // Also observe for thumbnail generation if needed (images only)
                  if (isImageFile(file)) {
                    thumbnailObserver.observe(card);

                    // Check if card is already visible and trigger generation immediately
                    const rect = card.getBoundingClientRect();
                    const isVisible =
                      rect.top < window.innerHeight + 50 && rect.bottom > -50;
                    if (isVisible) {
                      generateThumbnailForFile(file);
                    }
                  }
                }
              }
            }
          });
        }, 100);
      }
    };

    // Watch for view mode changes and file list changes to update observer
    watch(
      () => [props.viewMode, props.files, props.folders],
      () => {
        if (props.viewMode === "grid") {
          setupThumbnailObserver();
        }
      },
      { deep: true },
    );

    // Load existing thumbnails on mount
    const loadExistingThumbnails = async () => {
      // Load thumbnails for all image files (will fallback to image if thumbnail doesn't exist)
      const filesToLoad = allItems.value.filter(
        (file) => isImageFile(file) || isAudioFile(file),
      );

      // Wait for DOM to be ready
      await nextTick();
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Load thumbnails sequentially to avoid race conditions
      for (const file of filesToLoad) {
        await loadThumbnailUrl(file.id, file);
        // Small delay between loads to ensure reactivity
        await nextTick();
      }
    };

    // Setup observer on mount
    onMounted(() => {
      // Load existing thumbnails
      loadExistingThumbnails();

      if (props.viewMode === "grid") {
        // Delay to ensure DOM is fully rendered
        setTimeout(() => {
          setupThumbnailObserver();
        }, 200);
      }

      // Add global keyboard event listener
      document.addEventListener("keydown", handleGlobalKeyDown, true);

      // Add global click listener to close menu when clicking outside
      // Use capture phase and a small delay to ensure it runs after menu setup
      setTimeout(() => {
        document.addEventListener("mousedown", handleGlobalClick, true);
        document.addEventListener("click", handleGlobalClick, true);
        window.addEventListener("mousedown", handleGlobalClick, true);
        window.addEventListener("click", handleGlobalClick, true);
      }, 100);

      // Add global scroll listeners to close menu when scrolling
      // Using capture phase to catch events from all scrollable elements
      document.addEventListener("scroll", handleGlobalScroll, true);
      window.addEventListener("scroll", handleGlobalScroll, true);
      document.addEventListener("wheel", handleGlobalScroll, true);
      window.addEventListener("wheel", handleGlobalScroll, true);
      document.addEventListener("touchmove", handleGlobalScroll, true);
      window.addEventListener("touchmove", handleGlobalScroll, true);
      if (document.body) {
        document.body.addEventListener("scroll", handleGlobalScroll, true);
        document.body.addEventListener("wheel", handleGlobalScroll, true);
        document.body.addEventListener("touchmove", handleGlobalScroll, true);
      }
    });

    // Watch for new files with thumbnails
    watch(
      () => allItems.value,
      () => {
        loadExistingThumbnails();
      },
      { deep: true },
    );

    // Cleanup observer on unmount
    onUnmounted(() => {
      // Remove mobile mode listener
      window.removeEventListener("mobile-mode-changed", handleMobileModeChange);

      if (thumbnailObserver) {
        thumbnailObserver.disconnect();
        thumbnailObserver = null;
      }

      // Remove global keyboard event listener
      document.removeEventListener("keydown", handleGlobalKeyDown, true);

      // Remove global click listeners
      document.removeEventListener("mousedown", handleGlobalClick, true);
      document.removeEventListener("click", handleGlobalClick, true);
      window.removeEventListener("mousedown", handleGlobalClick, true);
      window.removeEventListener("click", handleGlobalClick, true);

      // Remove global scroll listeners
      document.removeEventListener("scroll", handleGlobalScroll, true);
      window.removeEventListener("scroll", handleGlobalScroll, true);
      document.removeEventListener("wheel", handleGlobalScroll, true);
      window.removeEventListener("wheel", handleGlobalScroll, true);
      document.removeEventListener("touchmove", handleGlobalScroll, true);
      window.removeEventListener("touchmove", handleGlobalScroll, true);
      if (document.body) {
        document.body.removeEventListener("scroll", handleGlobalScroll, true);
        document.body.removeEventListener("wheel", handleGlobalScroll, true);
        document.body.removeEventListener(
          "touchmove",
          handleGlobalScroll,
          true,
        );
      }
    });

    return {
      isMobileView,
      newlyCreatedItemId,
      isNewlyCreated,
      sortBy,
      sortOrder,
      filterType,
      sortOptions,
      filterOptions,
      sortedAndFilteredItems,
      allSelected,
      showMenu,
      menuItem,
      menuPosition,
      editingName,
      dropTargetId,
      draggedItemId,
      focusedItemIndex,
      handleSortChange,
      handleFilterChange,
      toggleSortOrder,
      sortByColumn,
      handleHeaderClick,
      isSelected,
      toggleSelection,
      handleSelectAll,
      handleRowClick,
      handleCardClick,
      handleRowDoubleClick,
      handleCardDoubleClick,
      handleMenuClick,
      openMenuForItem,
      handleMenuAction,
      saveRename,
      cancelRename,
      handleContextMenu,
      handleDragStart,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      formatSize,
      formatDate,
      getFileType,
      getThumbnailUrl,
      loadThumbnailUrl,
      hasThumbnail,
      isImageFile,
      isAudioFile,
      handleThumbnailError,
      getIcon,
      getSortIcon,
      getFileIcon,
      handleKeyDown,
      handleGlobalKeyDown,
      scrollToFocusedItem,
      handleViewClick,
      handleGlobalClick,
      handleGlobalScroll,
      // Column resizing
      tableContainer,
      columnWidths,
      columnMinWidths,
      isResizing,
      getColumnWidth,
      getGridTemplateColumns,
      handleResizeStart,
      handleResizeMove,
      handleResizeEnd,
    };
  },
};
</script>

<style scoped>
.file-list-view {
  width: 100%;
}

.view-controls {
  padding: 0.75rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
  display: block;
}

.view-controls-grid {
  display: grid;
  grid-template-columns: 0fr 1fr;
  grid-template-rows: 1fr;
  gap: 0.5rem;
  align-items: stretch;
  min-height: 100px;
  width: 100%;
}

.view-toggle-panel {
  grid-column: 1;
  grid-row: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  height: 100%;
}

.view-toggle {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  align-items: stretch;
  justify-content: stretch;
}

.controls-right-panel {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  height: 100%;
}

.view-toggle .btn-icon {
  padding: 0.75rem;
  background: rgba(30, 41, 59, 0.3);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 48px;
  opacity: 0.8;
  transition: all 0.2s;
  color: var(--text-secondary, #cbd5e1);
}

.view-toggle .btn-icon:first-child {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-bottom: none;
}

.view-toggle .btn-icon:last-child {
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.view-toggle .btn-icon:hover {
  background: rgba(30, 41, 59, 0.5);
  border-color: rgba(148, 163, 184, 0.4);
  opacity: 1;
}

.view-toggle .btn-icon.active {
  background: rgba(88, 166, 255, 0.15);
  border-color: rgba(88, 166, 255, 0.3);
  opacity: 1;
  color: #60a5fa;
}

.view-toggle .btn-icon svg {
  width: 18px;
  height: 18px;
  display: block;
  visibility: visible;
  opacity: 1;
}

.view-toggle .btn-icon span {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.sort-controls,
.filter-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  flex: 1;
}

.sort-controls .btn-icon {
  background: transparent;
  border: none;
  color: var(--text-secondary, #cbd5e1);
  padding: 0;
  width: auto;
  height: auto;
  min-width: auto;
  min-height: auto;
}

.sort-controls .btn-icon:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #f1f5f9);
  transform: none;
}

.input-sm {
  padding: 0.5rem;
  font-size: 0.85rem;
}

.list-view {
  width: 100%;
  overflow-x: auto;
  box-sizing: border-box;
}

/* CSS Grid Container */
.grid-container {
  width: 100%;
  min-width: 800px;
  display: grid;
  grid-auto-rows: min-content;
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* Grid Header Row */
.grid-header-row {
  display: contents;
}

.grid-header-row > .grid-cell {
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-right: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.grid-header-row > .grid-cell:last-child {
  border-right: none;
}

/* Grid Body Rows */
.grid-body-row {
  display: contents;
}

.grid-body-row > .grid-cell {
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.1));
  transition:
    background-color 0.2s,
    transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.grid-body-row.file-row-new > .grid-cell {
  animation: fileRowNew 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

/* Row states - apply to all cells in the row */
.grid-body-row:hover > .grid-cell {
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
}

.grid-body-row.selected > .grid-cell {
  background: rgba(56, 189, 248, 0.1);
}

.grid-body-row.focused > .grid-cell:first-child {
  outline: 2px solid var(--accent-blue, #38bdf8);
  outline-offset: -2px;
  border-radius: 2px 0 0 2px;
}

.grid-body-row.focused > .grid-cell:last-child {
  border-radius: 0 2px 2px 0;
}

.grid-body-row.drop-target > .grid-cell {
  background: rgba(56, 189, 248, 0.2);
  border: 2px dashed var(--accent-blue, #38bdf8);
}

.grid-body-row.dragging > .grid-cell {
  opacity: 0.5;
}

/* Grid Cells */
.grid-cell {
  padding: 0.375rem 0.75rem;
  display: flex;
  align-items: center;
  box-sizing: border-box;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-height: 2rem;
  line-height: 1.25;
}

/* Header Cells */
.grid-header-row .grid-cell {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  position: relative;
}

.grid-header-row .grid-cell.sortable {
  cursor: pointer;
  user-select: none;
}

.grid-header-row .grid-cell.sortable:hover {
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
}

.grid-header-row .grid-cell.resizable-header {
  position: relative;
}

.grid-header-row .grid-cell.resizable-header .header-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

/* Body Cells */
.grid-body-row .grid-cell {
  color: var(--text-secondary, #cbd5e1);
}

/* Column-specific styles */
.grid-cell-checkbox {
  justify-content: center;
  text-align: center;
  min-width: 40px;
  padding: 0.375rem 0.5rem;
}

.grid-cell-name {
  text-align: left;
}

.grid-cell-type {
  text-align: left;
}

.grid-cell-size {
  text-align: right;
}

.grid-cell-date {
  text-align: right;
}

.grid-cell-actions {
  justify-content: flex-end;
  text-align: center;
  min-width: 60px;
  padding: 0.375rem 0.75rem;
}

/* Column Resizer */
.column-resizer {
  position: absolute;
  top: 0;
  right: -2px;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  user-select: none;
  z-index: 10;
  background: transparent;
  transition: background-color 0.2s ease;
}

.column-resizer:hover {
  background: var(--accent-blue, #38bdf8);
  opacity: 0.6;
}

.column-resizer:active {
  background: var(--accent-blue, #38bdf8);
  opacity: 1;
}

.sort-indicator {
  margin-left: 0.5rem;
  color: var(--accent-blue, #38bdf8);
}

.file-name {
  font-weight: 500;
  color: var(--text-primary, #f1f5f9);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
  overflow: hidden;
  margin: 0;
  padding: 0;
  width: 100%;
}

.file-icon-small {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin: 0;
  padding: 0;
  vertical-align: middle;
}

.file-icon-small svg {
  width: 18px;
  height: 18px;
}

.file-name-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.inline-edit-container {
  flex: 1;
  display: flex;
}

.inline-edit-input {
  flex: 1;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border: 1px solid var(--accent-blue, #38bdf8);
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  color: var(--text-primary, #f1f5f9);
  font-size: inherit;
  font-family: inherit;
  font-weight: inherit;
}

.inline-edit-input:focus {
  outline: none;
  border-color: var(--accent-blue, #38bdf8);
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
}

.file-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-menu {
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  opacity: 0.8;
}

.btn-menu:hover {
  opacity: 1;
}

.btn-menu svg {
  width: 16px;
  height: 16px;
  display: block;
  visibility: visible;
  opacity: 1;
}

.btn-menu span {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.grid-view .files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.5rem;
}

.file-card {
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: var(--radius-md, 8px);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  transition: all var(--transition-base);
  cursor: grab;
}

.file-card.file-card-new {
  animation: fileCardNew 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

.file-card:hover {
  border-color: var(--border-color-hover, rgba(148, 163, 184, 0.4));
  box-shadow: var(--shadow-md);
  transform: translateY(-2px) scale(1);
}

.file-card.selected {
  border-color: var(--accent-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.1);
}

.file-card.drop-target {
  background: rgba(56, 189, 248, 0.2);
  border: 2px dashed var(--accent-blue, #38bdf8);
}

.file-card.dragging {
  opacity: 0.5;
  cursor: grabbing;
}

.file-card:active {
  cursor: grabbing;
}

.file-card .file-checkbox {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  z-index: 10;
}

.file-icon-large {
  font-size: 3.5rem;
  margin-bottom: 1.5rem;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  box-sizing: border-box;
}

.file-icon-large svg {
  width: 48px;
  height: 48px;
}

.file-thumbnail {
  max-height: 60px;
  max-width: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 8px;
  display: block;
  margin: 0 auto;
}

.star-icon-large {
  position: absolute;
  top: -0.5rem;
  right: -0.5rem;
  width: 24px;
  height: 24px;
  filter: drop-shadow(0 0 3px rgba(255, 215, 0, 0.8));
}

.star-icon-large svg {
  width: 24px;
  height: 24px;
  color: #ffd700;
}

.file-info {
  text-align: center;
  width: 100%;
}

.file-info h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  word-break: break-word;
  color: var(--text-primary, #f1f5f9);
}

.file-info .inline-edit-container {
  width: 100%;
  margin-bottom: 0.5rem;
}

.file-info .inline-edit-input {
  width: 100%;
  text-align: center;
}

.file-meta {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
}

.btn-menu-grid {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  opacity: 0.8;
}

.btn-menu-grid:hover {
  opacity: 1;
}

.btn-menu-grid svg {
  width: 16px;
  height: 16px;
  display: block;
  visibility: visible;
  opacity: 1;
}

.btn-menu-grid span {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.select-all-checkbox {
  cursor: pointer;
}

@keyframes fileCardNew {
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

@keyframes fileRowNew {
  0% {
    opacity: 0;
    transform: translateX(-30px);
    background-color: rgba(56, 189, 248, 0.4) !important;
  }
  50% {
    transform: translateX(8px);
    background-color: rgba(56, 189, 248, 0.2) !important;
  }
  100% {
    opacity: 1;
    transform: translateX(0);
    background-color: transparent;
  }
}

/* Mobile Mode Styles */
.mobile-mode .view-controls {
  padding: 0.75rem;
}

.mobile-mode .view-controls-grid {
  grid-template-columns: 1fr;
  grid-template-rows: auto;
  gap: 0.75rem;
}

.mobile-mode .view-toggle-panel {
  display: none !important;
}

.mobile-mode .controls-right-panel {
  grid-column: 1;
  grid-row: 1;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
}

.mobile-mode .controls-right-panel.mobile-full-width {
  grid-column: 1;
  grid-row: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.mobile-mode .sort-controls,
.mobile-mode .filter-controls {
  width: 100%;
  justify-content: space-between;
}

.mobile-mode .grid-container {
  min-width: 100%;
  font-size: 0.85rem;
}

.mobile-mode .grid-cell {
  padding: 0.5rem 0.5rem;
  font-size: 0.85rem;
}

.mobile-mode .grid-cell-type {
  display: none;
}

.mobile-mode .grid-cell-date {
  font-size: 0.75rem;
}

.mobile-mode .grid-cell-size {
  font-size: 0.75rem;
}

.mobile-mode .files-grid {
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
}

.mobile-mode .file-card {
  padding: 0.75rem;
}

.mobile-mode .file-thumbnail {
  width: 100%;
  height: 80px;
  margin-bottom: 0.5rem;
}

.mobile-mode .file-info h3 {
  font-size: 0.85rem;
}

.mobile-mode .file-meta {
  font-size: 0.75rem;
}

.mobile-mode .btn-menu-grid {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
}
</style>
