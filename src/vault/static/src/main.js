import { createApp } from "vue";
import { createPinia } from "pinia";
import router from "./router";
import App from "./App.vue";
import "./assets/styles.css";

// Initialize global utilities
import { modalManager } from "./utils/ModalManager.js";
import { folderPicker } from "./utils/FolderPicker.js";
// Import encryption.js to initialize VaultCrypto wrapper for compatibility
import "./services/encryption.js";
import { decryptFileKey } from "./services/encryption.js";

// Make available globally for non-module scripts
if (typeof window !== "undefined") {
  window.modalManager = modalManager;
  window.folderPicker = folderPicker;
  window.decryptFileKey = decryptFileKey;
}

// Note: icons.js and trusted-types-init.js are loaded BEFORE main.js in index.html
// sharing.js is loaded after Vue app mounts
// Icons should be available immediately, but add a small check
if (!window.Icons) {
  console.warn(
    "window.Icons not available - icons.js may not be loaded. Some icons may not display.",
  );
}

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

app.mount("#app");
