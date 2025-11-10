<template>
  <div
    class="file-list-view"
    @keydown="handleKeyDown"
    @click="handleViewClick"
    tabindex="0"
  >
    <div class="view-controls glass">
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

    <div v-if="viewMode === 'list'" class="list-view">
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
              <span class="file-icon-small" v-html="getFileIcon(item)"></span>
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
              v-if="item.has_thumbnail && item.mime_type?.startsWith('image/')"
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
import { thumbnails } from "../services/api";
import { debounce } from "../utils/debounce";
import FileMenuDropdown from "./FileMenuDropdown.vue";
import CustomSelect from "./CustomSelect.vue";

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
      type: [String, Number],
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
    const sortBy = ref("name");
    const sortOrder = ref("asc");
    const filterType = ref("all");
    const showMenu = ref(false);
    const menuItem = ref(null);
    const menuPosition = ref({ x: 0, y: 0 });
    const editingName = ref("");
    const dropTargetId = ref(null);
    const draggedItemId = ref(null);
    const focusedItemIndex = ref(-1); // Index of focused element for keyboard navigation

    // Expose newlyCreatedItemId for template access
    const newlyCreatedItemId = computed(() => props.newlyCreatedItemId);

    // Helper function to check if item is newly created
    const isNewlyCreated = (itemId) => {
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

      // Use fractions (fr) to ensure all columns fill available width
      // Default proportions based on percentages
      const defaultFractions = [0.03, 0.4, 0.18, 0.12, 0.18, 0.09];

      // If columns have been resized, calculate proportional fractions
      const hasResizedColumns = Object.keys(columnWidths.value).length > 0;

      if (hasResizedColumns) {
        // Calculate total of resized widths for proportion
        let totalResizedWidth = 0;
        const resizedWidths = [];

        for (let i = 0; i < totalColumns; i++) {
          if (columnWidths.value[i] !== undefined) {
            resizedWidths[i] = columnWidths.value[i];
            totalResizedWidth += columnWidths.value[i];
          } else {
            // Use default percentage for non-resized columns
            const defaultWidth = calculateDefaultWidth(i);
            resizedWidths[i] = defaultWidth || 200;
            totalResizedWidth += resizedWidths[i];
          }
        }

        // Convert to fractions
        for (let i = 0; i < totalColumns; i++) {
          const minWidth = columnMinWidths[i] || 80;
          const fraction = resizedWidths[i] / totalResizedWidth;
          columns.push(`minmax(${minWidth}px, ${fraction}fr)`);
        }
      } else {
        // No resizing: use default fractions
        for (let i = 0; i < totalColumns; i++) {
          const minWidth = columnMinWidths[i] || 80;
          const fraction = defaultFractions[i];
          columns.push(`minmax(${minWidth}px, ${fraction}fr)`);
        }
      }

      return columns.join(" ");
    });

    // Handle resize start
    const handleResizeStart = (columnIndex, event) => {
      event.preventDefault();
      event.stopPropagation();
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
      const newWidth = Math.max(minWidth, startWidth.value + diff);

      // Update column width (only th will be updated, td inherit automatically)
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

      // Calculate and set default widths for columns that haven't been resized
      nextTick(() => {
        if (tableContainer.value) {
          // Wait for table to be fully rendered
          setTimeout(() => {
            // Calculate default widths for all columns if not saved
            [0, 1, 2, 3, 4, 5].forEach((index) => {
              if (columnWidths.value[index] === undefined) {
                const defaultWidth = calculateDefaultWidth(index);
                if (defaultWidth !== null && defaultWidth > 0) {
                  columnWidths.value[index] = defaultWidth;
                }
              }
            });
          }, 100);
        }
      });
    };

    // Load column widths on mount
    onMounted(() => {
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
        const icon = window.Icons[iconName](16, "#ffffff");
        if (!icon || icon.trim() === "") {
          console.warn(`Icon ${iconName} returned empty string`);
        }
        return icon;
      }
      console.warn(`Icon ${iconName} not found`);
      return "";
    };

    const getSortIcon = () => {
      return sortOrder.value === "asc" ? "↑" : "↓";
    };

    const getFileIcon = (item, size = "small") => {
      if (!window.Icons) {
        return item.mime_type === "application/x-directory" ? "📁" : "📄";
      }
      const iconSize = size === "large" ? 48 : 20;
      if (item.mime_type === "application/x-directory") {
        return window.Icons.folder(iconSize, "currentColor");
      }
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
      if (
        editingName.value.trim() &&
        editingName.value !== item.original_name
      ) {
        emit("action", "rename", item, editingName.value.trim());
      }
      editingName.value = "";
      emit("action", "cancel-rename");
    };

    const cancelRename = () => {
      editingName.value = "";
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

    const getThumbnailUrl = (fileId) => {
      return thumbnails.getUrl(fileId, "256x256");
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
            editingName.value = item.original_name;
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
        }
      },
    );

    // Keyboard navigation
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
      // Close menu if clicking on view (but not on a specific element)
      if (
        showMenu.value &&
        !event.target.closest(".file-card") &&
        !event.target.closest(".file-row") &&
        !event.target.closest(".file-menu-container") &&
        !event.target.closest(".btn-menu") &&
        !event.target.closest(".btn-menu-grid")
      ) {
        showMenu.value = false;
      }
    };

    return {
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
      handleThumbnailError,
      getIcon,
      getSortIcon,
      getFileIcon,
      handleKeyDown,
      scrollToFocusedItem,
      handleViewClick,
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
  gap: 1rem;
}

.view-toggle {
  display: flex;
  gap: 0.5rem;
}

.view-toggle .btn-icon {
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  opacity: 0.8;
  transition: opacity 0.2s;
  min-width: 24px;
  min-height: 24px;
}

.view-toggle .btn-icon:hover {
  opacity: 1;
}

.view-toggle .btn-icon.active {
  background: transparent;
  opacity: 1;
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
}

/* CSS Grid Container */
.grid-container {
  width: 100%;
  min-width: 800px;
  display: grid;
  grid-auto-rows: min-content;
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

/* Grid Header Row */
.grid-header-row {
  display: contents;
}

.grid-header-row > .grid-cell {
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
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
  padding: 0.375rem 0.5rem;
}

/* Column Resizer */
.column-resizer {
  position: absolute;
  top: 0;
  right: 0;
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
}

.file-icon-large {
  font-size: 3.5rem;
  margin-bottom: 1rem;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-icon-large svg {
  width: 48px;
  height: 48px;
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
</style>
