<template>
  <div id="app">
    <div class="background-bubbles">
      <div class="bubble bubble-1"></div>
      <div class="bubble bubble-2"></div>
      <div class="bubble bubble-3"></div>
      <div class="bubble bubble-4"></div>
      <div class="bubble bubble-5"></div>
    </div>
    <router-view v-slot="{ Component, route: currentRoute }">
      <transition name="page" mode="out-in">
        <AppLayout
          v-if="needsAppLayout"
          :key="'layout-' + currentRoute.path"
          @logout="handleLogout"
        >
          <component :is="Component" :key="currentRoute.path" />
        </AppLayout>
        <component v-else :is="Component" :key="currentRoute.path" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { auth } from "./services/api";
import AppLayout from "./components/AppLayout.vue";

const route = useRoute();

// Routes qui nécessitent AppLayout (avec sidebar)
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
</script>
<style>
/* Global styles */
</style>
