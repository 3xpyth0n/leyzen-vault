<template>
  <div id="app">
    <router-view v-slot="{ Component, route: currentRoute }">
      <transition name="page" mode="out-in">
        <AppLayout
          v-if="needsAppLayout"
          :key="'layout-authenticated'"
          @logout="handleLogout"
        >
          <component :is="Component" :key="currentRoute.path" />
        </AppLayout>
        <component
          v-else
          :is="Component"
          :key="'public-' + currentRoute.path"
        />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { auth } from "./services/api";
import AppLayout from "./components/AppLayout.vue";
import { initMobileMode } from "./utils/mobileMode";

const route = useRoute();

// Routes that require AppLayout (with sidebar)
const authenticatedRoutes = [
  "Dashboard",
  "VaultSpaceView",
  "Trash",
  "Starred",
  "Recent",
  "Shared",
  "Account",
  "Admin",
];

const needsAppLayout = computed(() => {
  return authenticatedRoutes.includes(route.name);
});

const handleLogout = () => {
  auth.logout();
};

onMounted(() => {
  initMobileMode();
});
</script>
<style>
/* Global styles */
</style>
