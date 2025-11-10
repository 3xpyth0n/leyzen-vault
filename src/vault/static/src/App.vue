<template>
  <div id="app">
    <div class="background-bubbles">
      <div class="bubble bubble-1"></div>
      <div class="bubble bubble-2"></div>
      <div class="bubble bubble-3"></div>
      <div class="bubble bubble-4"></div>
      <div class="bubble bubble-5"></div>
    </div>
    <transition name="page" mode="out-in">
      <router-view :key="$route.path" />
    </transition>
  </div>
</template>

<script setup>
// Main Vue app component
</script>

<style>
/* Global styles */
</style>
