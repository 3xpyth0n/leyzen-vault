<template>
  <div class="search-bar">
    <div class="search-input-wrapper glass">
      <input
        v-model="query"
        @input="handleSearch"
        @keydown.enter="performSearch"
        @keydown.esc="clearSearch"
        type="text"
        :placeholder="placeholder"
        class="search-input input"
        ref="searchInput"
      />
      <button
        v-if="query"
        @click="clearSearch"
        class="search-clear-btn"
        aria-label="Clear search"
      >
        ✕
      </button>
      <button
        @click="showFilters = !showFilters"
        class="search-filter-btn"
        :class="{ active: showFilters }"
        aria-label="Toggle filters"
        v-html="getIcon('funnel', 20)"
      ></button>
    </div>

    <!-- Filters Panel -->
    <div v-if="showFilters" class="search-filters glass glass-card">
      <div class="filter-group">
        <label>Type:</label>
        <select
          v-model="filters.mimeType"
          @change="applyFiltersAuto"
          class="input"
        >
          <option value="">All types</option>
          <option value="image">Images</option>
          <option value="video">Videos</option>
          <option value="audio">Audio</option>
          <option value="application/pdf">PDFs</option>
          <option value="text">Text files</option>
          <option value="application/x-directory">Folders</option>
        </select>
      </div>

      <div class="filter-group">
        <label>Size:</label>
        <div class="size-range">
          <input
            v-model.number="filters.minSize"
            @input="applyFiltersAuto"
            type="number"
            placeholder="Min (bytes)"
            class="input"
          />
          <span>to</span>
          <input
            v-model.number="filters.maxSize"
            @input="applyFiltersAuto"
            type="number"
            placeholder="Max (bytes)"
            class="input"
          />
        </div>
      </div>

      <div class="filter-group">
        <label>Sort by:</label>
        <select
          v-model="filters.sortBy"
          @change="applyFiltersAuto"
          class="input"
        >
          <option value="relevance">Relevance</option>
          <option value="name">Name</option>
          <option value="date">Date</option>
          <option value="size">Size</option>
        </select>
        <select
          v-model="filters.sortOrder"
          @change="applyFiltersAuto"
          class="input"
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
      </div>

      <div class="filter-group">
        <label>Type filter:</label>
        <div class="toggle-switch">
          <button
            @click="
              filters.fileTypeFilter = 'folders';
              applyFiltersAuto();
            "
            :class="{ active: filters.fileTypeFilter === 'folders' }"
            class="toggle-option"
          >
            Folders only
          </button>
          <button
            @click="
              filters.fileTypeFilter = 'all';
              applyFiltersAuto();
            "
            :class="{ active: filters.fileTypeFilter === 'all' }"
            class="toggle-option"
          >
            All
          </button>
          <button
            @click="
              filters.fileTypeFilter = 'files';
              applyFiltersAuto();
            "
            :class="{ active: filters.fileTypeFilter === 'files' }"
            class="toggle-option"
          >
            Files only
          </button>
        </div>
      </div>

      <div class="filter-actions">
        <button @click="resetFilters" class="btn btn-secondary">Reset</button>
      </div>
    </div>

    <!-- Search Results -->
    <div
      v-if="showResults && results.length > 0"
      class="search-results glass glass-card"
    >
      <div class="results-header">
        <h3>{{ results.length }} result(s)</h3>
        <button @click="closeResults" class="btn-icon">✕</button>
      </div>
      <div class="results-list">
        <div
          v-for="item in results"
          :key="item.id"
          class="result-item"
          @click="handleResultClick(item)"
        >
          <div class="result-icon">
            {{ item.mime_type === "application/x-directory" ? "📁" : "📄" }}
          </div>
          <div class="result-info">
            <h4 v-html="highlightText(item.original_name, query)"></h4>
            <p
              v-if="item.full_path"
              class="result-path"
              v-html="highlightText(item.full_path, query)"
            ></p>
            <p class="result-meta">
              {{ formatSize(item.size) }} • {{ formatDate(item.created_at) }}
            </p>
          </div>
        </div>
      </div>
      <div v-if="hasMore" class="results-footer">
        <button @click="loadMore" class="btn btn-secondary">Load more</button>
      </div>
    </div>

    <div
      v-if="showResults && results.length === 0 && !searching"
      class="search-results glass glass-card"
    >
      <p class="no-results">No results found</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from "vue";
import { search as searchApi } from "../services/search";
import { useRouter } from "vue-router";

export default {
  name: "SearchBar",
  props: {
    vaultspaceId: {
      type: String,
      default: null,
    },
    parentId: {
      type: String,
      default: null,
    },
    placeholder: {
      type: String,
      default: "Search files and folders...",
    },
    autoSearch: {
      type: Boolean,
      default: true,
    },
    debounceMs: {
      type: Number,
      default: 300,
    },
  },
  emits: ["result-click", "search-complete"],
  setup(props, { emit }) {
    const router = useRouter();
    const query = ref("");
    const results = ref([]);
    const searching = ref(false);
    const showResults = ref(false);
    const showFilters = ref(false);
    const hasMore = ref(false);
    const offset = ref(0);
    const limit = 20;

    const filters = ref({
      mimeType: "",
      minSize: null,
      maxSize: null,
      sortBy: "relevance",
      sortOrder: "desc",
      fileTypeFilter: "all", // "all", "files", "folders"
    });

    let searchTimeout = null;

    const handleSearch = () => {
      if (!props.autoSearch) return;

      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        if (query.value.trim()) {
          performSearch();
        } else {
          clearSearch();
        }
      }, props.debounceMs);
    };

    const performSearch = async () => {
      if (!query.value.trim()) {
        clearSearch();
        return;
      }

      searching.value = true;
      showResults.value = true;
      offset.value = 0;

      try {
        const searchOptions = {
          query: query.value.trim(),
          vaultspaceId: props.vaultspaceId,
          parentId: props.parentId,
          limit,
          offset: offset.value,
          sortBy: filters.value.sortBy,
          sortOrder: filters.value.sortOrder,
        };

        if (filters.value.mimeType) {
          searchOptions.mimeType = filters.value.mimeType;
        }
        if (filters.value.minSize !== null) {
          searchOptions.minSize = filters.value.minSize;
        }
        if (filters.value.maxSize !== null) {
          searchOptions.maxSize = filters.value.maxSize;
        }
        if (filters.value.fileTypeFilter === "files") {
          searchOptions.filesOnly = true;
        }
        if (filters.value.fileTypeFilter === "folders") {
          searchOptions.foldersOnly = true;
        }

        const response = await searchApi.searchFiles(searchOptions);
        results.value = response.results || [];
        hasMore.value = response.has_more || false;
        offset.value = response.offset || 0;

        emit("search-complete", response);
      } catch (error) {
        console.error("Search error:", error);
        results.value = [];
        hasMore.value = false;
      } finally {
        searching.value = false;
      }
    };

    const loadMore = async () => {
      if (searching.value || !hasMore.value) return;

      searching.value = true;
      offset.value += limit;

      try {
        const searchOptions = {
          query: query.value.trim(),
          vaultspaceId: props.vaultspaceId,
          parentId: props.parentId,
          limit,
          offset: offset.value,
          sortBy: filters.value.sortBy,
          sortOrder: filters.value.sortOrder,
        };

        if (filters.value.mimeType) {
          searchOptions.mimeType = filters.value.mimeType;
        }
        if (filters.value.minSize !== null) {
          searchOptions.minSize = filters.value.minSize;
        }
        if (filters.value.maxSize !== null) {
          searchOptions.maxSize = filters.value.maxSize;
        }
        if (filters.value.fileTypeFilter === "files") {
          searchOptions.filesOnly = true;
        }
        if (filters.value.fileTypeFilter === "folders") {
          searchOptions.foldersOnly = true;
        }

        const response = await searchApi.searchFiles(searchOptions);
        results.value = [...results.value, ...(response.results || [])];
        hasMore.value = response.has_more || false;
      } catch (error) {
        console.error("Load more error:", error);
      } finally {
        searching.value = false;
      }
    };

    const clearSearch = () => {
      query.value = "";
      results.value = [];
      showResults.value = false;
      hasMore.value = false;
      offset.value = 0;
      emit("search-complete", { results: [], total: 0 });
    };

    const closeResults = () => {
      showResults.value = false;
    };

    const applyFiltersAuto = () => {
      // Apply filters automatically when they change
      if (query.value.trim()) {
        performSearch();
      }
    };

    const resetFilters = () => {
      filters.value = {
        mimeType: "",
        minSize: null,
        maxSize: null,
        sortBy: "relevance",
        sortOrder: "desc",
        fileTypeFilter: "all",
      };
      if (query.value.trim()) {
        performSearch();
      }
    };

    const handleResultClick = (item) => {
      emit("result-click", item);

      // Close search results after clicking
      showResults.value = false;
    };

    const formatSize = (bytes) => {
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

    const highlightText = (text, query) => {
      if (!text || !query) return escapeHtml(text || "");
      const queryLower = query.toLowerCase();
      const textLower = text.toLowerCase();

      // Find all occurrences (case-insensitive)
      const parts = [];
      let lastIndex = 0;
      let index = textLower.indexOf(queryLower, lastIndex);

      while (index !== -1) {
        // Add text before match
        if (index > lastIndex) {
          parts.push(escapeHtml(text.substring(lastIndex, index)));
        }
        // Add highlighted match
        parts.push(
          `<mark class="search-highlight">${escapeHtml(text.substring(index, index + query.length))}</mark>`,
        );
        lastIndex = index + query.length;
        index = textLower.indexOf(queryLower, lastIndex);
      }

      // Add remaining text
      if (lastIndex < text.length) {
        parts.push(escapeHtml(text.substring(lastIndex)));
      }

      return parts.length > 0 ? parts.join("") : escapeHtml(text);
    };

    const escapeHtml = (text) => {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    };

    const getIcon = (iconName, size = 24) => {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      return window.Icons[iconName](size, "currentColor");
    };

    return {
      query,
      results,
      searching,
      showResults,
      showFilters,
      hasMore,
      filters,
      handleSearch,
      performSearch,
      loadMore,
      clearSearch,
      closeResults,
      applyFiltersAuto,
      resetFilters,
      handleResultClick,
      formatSize,
      formatDate,
      highlightText,
      getIcon,
    };
  },
};
</script>

<style scoped>
.search-bar {
  position: relative;
  width: 85%;
  max-width: 90%;
  margin: 0 auto;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 0.5rem;
  font-size: 1rem;
}

.search-input:focus {
  outline: none;
}

.search-clear-btn,
.search-filter-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: var(--text-secondary, #cbd5e1);
  font-size: 1rem;
  transition: color 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.3rem;
}

.search-filter-btn svg {
  display: block;
  vertical-align: middle;
}

.search-clear-btn:hover,
.search-filter-btn:hover {
  color: var(--text-primary, #f1f5f9);
}

.search-filter-btn.active {
  color: var(--accent-blue, #38bdf8);
}

.search-filters {
  margin-top: 1rem;
  padding: 1.5rem;
  border-radius: var(--radius-md, 8px);
}

.filter-group {
  margin-bottom: 1rem;
}

.filter-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary, #cbd5e1);
  font-size: 0.9rem;
}

.filter-group select,
.filter-group input[type="number"] {
  width: 100%;
  margin-bottom: 0.5rem;
}

.size-range {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.size-range input {
  flex: 1;
}

.filter-group label input[type="checkbox"] {
  margin-right: 0.5rem;
}

.toggle-switch {
  display: flex;
  gap: 0.5rem;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: var(--radius-md, 8px);
  padding: 0.25rem;
}

.toggle-option {
  flex: 1;
  padding: 0.5rem 1rem;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm, 6px);
  color: var(--text-secondary, #cbd5e1);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.9rem;
  font-weight: 500;
}

.toggle-option:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #f1f5f9);
}

.toggle-option.active {
  background: var(--accent-blue, #38bdf8);
  color: var(--text-primary, #f1f5f9);
  box-shadow: 0 2px 8px rgba(56, 189, 248, 0.3);
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.search-results {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 0.5rem;
  max-height: 500px;
  overflow-y: auto;
  z-index: 1000;
  border-radius: var(--radius-md, 8px);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.results-header h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary, #f1f5f9);
}

.results-list {
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.1));
}

.result-item:hover {
  background-color: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
}

.result-icon {
  font-size: 1.5rem;
}

.result-info {
  flex: 1;
}

.result-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 0.95rem;
  color: var(--text-primary, #f1f5f9);
}

.result-path {
  margin: 0.25rem 0;
  font-size: 0.8rem;
  color: var(--text-secondary, #cbd5e1);
  font-family: monospace;
  opacity: 0.8;
}

.result-meta {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
}

.results-footer {
  padding: 1rem;
  text-align: center;
  border-top: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.no-results {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted, #94a3b8);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #cbd5e1);
  font-size: 1rem;
  padding: 0.25rem;
}

.btn-icon:hover {
  color: var(--text-primary, #f1f5f9);
}

.search-highlight {
  background-color: var(--accent-blue, #38bdf8);
  color: var(--text-primary, #f1f5f9);
  padding: 0.1em 0.2em;
  border-radius: 0.2em;
  font-weight: 600;
}
</style>
