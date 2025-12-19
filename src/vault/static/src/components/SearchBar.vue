<template>
  <div class="search-bar">
    <div class="search-input-wrapper">
      <input
        v-model="query"
        @input="handleSearch"
        @keydown.enter="performSearch"
        @keydown.esc="clearSearch"
        type="text"
        :placeholder="placeholder"
        class="search-input input"
        ref="searchInput"
        autocomplete="off"
      />
      <button
        v-if="query"
        @click="clearSearch"
        class="search-clear-btn"
        aria-label="Clear search"
      >
        ✕
      </button>
    </div>

    <!-- Search Results -->
    <div v-if="showResults && results.length > 0" class="search-results">
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
          <div class="result-info">
            <h4>{{ item.original_name }}</h4>
            <p v-if="item.full_path" class="result-path">
              {{ item.full_path }}
            </p>
            <p class="result-size">
              {{ formatSize(item.size) }}
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
      class="search-results"
    >
      <p class="no-results">No results found</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from "vue";
import { search as searchApi } from "../services/search";
import { useRouter } from "vue-router";
import CustomSelect from "./CustomSelect.vue";

export default {
  name: "SearchBar",
  components: {
    CustomSelect,
  },
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
    const hasMore = ref(false);
    const offset = ref(0);
    const limit = 20;

    const filters = ref({
      mimeType: "",
      minSize: null,
      maxSize: null,
      sortBy: "relevance",
      sortOrder: "desc",
      fileTypeFilter: "all",
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
      hasMore,
      handleSearch,
      performSearch,
      loadMore,
      clearSearch,
      closeResults,
      handleResultClick,
      formatSize,
      getIcon,
    };
  },
};
</script>

<style scoped>
.search-bar {
  position: relative;
  width: 100%;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid var(--slate-grey);
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

.search-clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: var(--text-secondary, #a9b7aa);
  font-size: 1rem;
  transition: color 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.3rem;
}

.search-clear-btn:hover {
  color: var(--text-primary, #a9b7aa);
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
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--slate-grey);
}

.results-header h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary, #a9b7aa);
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
  border-bottom: 1px solid var(--slate-grey);
}

.result-item:hover {
  background-color: rgba(0, 66, 37, 0.1);
}

.result-info {
  flex: 1;
  width: 100%;
}

.result-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 0.95rem;
  color: var(--text-primary, #a9b7aa);
}

.result-path {
  margin: 0.25rem 0;
  font-size: 0.8rem;
  color: var(--slate-grey);
  font-family: monospace;
}

.result-size {
  margin: 0.25rem 0 0 0;
  font-size: 0.8rem;
  color: var(--slate-grey);
}

.results-footer {
  padding: 1rem;
  text-align: center;
  border-top: 1px solid var(--slate-grey);
}

.no-results {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted, #a9b7aa);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #a9b7aa);
  font-size: 1rem;
  padding: 0.25rem;
}

.btn-icon:hover {
  color: var(--text-primary, #a9b7aa);
}
</style>
