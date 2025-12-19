<template>
  <div class="top-users-card">
    <div class="section-header">
      <h3>Top Users by Storage</h3>
      <button @click="$emit('view-all')" class="btn-link">View All</button>
    </div>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="users.length === 0" class="empty-state">
      <p>No users with storage</p>
    </div>
    <div v-else class="users-list">
      <div
        v-for="(user, index) in displayedUsers"
        :key="user.user_id"
        class="user-item"
      >
        <div class="user-rank">{{ index + 1 }}</div>
        <div class="user-info">
          <div class="user-email">{{ user.email }}</div>
          <div class="user-storage">{{ user.storage_gb }} GB</div>
        </div>
        <div class="user-bar">
          <div
            class="user-bar-fill"
            :style="{
              width: getPercentage(user.storage_bytes) + '%',
            }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "TopUsersCard",
  props: {
    users: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["view-all"],
  computed: {
    displayedUsers() {
      return this.users.slice(0, 3);
    },
  },
  methods: {
    getPercentage(bytes) {
      if (!this.users || this.users.length === 0) return 0;
      const maxBytes = this.users[0].storage_bytes;
      if (maxBytes === 0) return 0;
      return (bytes / maxBytes) * 100;
    },
  },
};
</script>

<style scoped>
.top-users-card {
  padding: 1.5rem;
  background: var(--bg-modal, #141414);
  border: 1px solid var(--border-color);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.mobile-mode .top-users-card {
  padding: 1rem;
  max-width: 100%;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.1rem;
  font-weight: 600;
}

.btn-link {
  background: none;
  border: none;
  color: #004225;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0;
  text-decoration: underline;
  transition: color 0.2s ease;
}

.btn-link:hover {
  color: #004225;
}

.loading,
.empty-state {
  padding: 2rem;
  text-align: center;
  color: #a9b7aa;
}

.users-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 0;
}

.mobile-mode .user-item {
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: flex-start;
}

.user-rank {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
  font-weight: 700;
  font-size: 1.3rem;
  font-family: "TT Alientz Serif";
  margin-top: 0.3rem;
}

.user-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.mobile-mode .user-info {
  flex: 1 1 auto;
  min-width: 0;
  max-width: calc(100% - 3rem);
  order: 2;
}

.user-email {
  color: #a9b7aa;
  font-size: 0.9rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-mode .user-email {
  font-size: 0.85rem;
  white-space: normal;
  word-break: break-word;
  line-height: 1.3;
}

.user-storage {
  color: #a9b7aa;
  font-size: 0.85rem;
}

.mobile-mode .user-storage {
  font-size: 0.8rem;
  margin-top: 0.125rem;
}

.user-bar {
  flex: 1;
  height: 6px;
  background: rgba(30, 41, 59, 0.6);

  overflow: hidden;
  min-width: 100px;
}

.mobile-mode .user-item {
  flex-wrap: wrap;
  flex-direction: row;
}

.mobile-mode .user-bar {
  flex: 0 0 100%;
  order: 3;
  margin-top: 0.5rem;
  min-width: 0;
  width: 100%;
}

.user-bar-fill {
  height: 100%;
  background: transparent;

  transition: width 0.3s ease;
}
</style>
