import { createApp } from "vue";
import { createPinia } from "pinia";
import router from "./router";
import App from "./App.vue";
import "./assets/styles.css";

// Polyfill Buffer for music-metadata library
import { Buffer } from "buffer";
if (typeof window !== "undefined") {
  window.Buffer = Buffer;
  // Also set global for libraries that check for global.Buffer
  if (typeof global === "undefined") {
    window.global = window;
  }
  global.Buffer = Buffer;
}

// Initialize global utilities
import { modalManager } from "./utils/ModalManager.js";
// Import encryption.js to initialize VaultCrypto wrapper for compatibility
import "./services/encryption.js";
import { decryptFileKey } from "./services/encryption.js";
// Import vault config service
import { getVaultBaseUrl } from "./services/vault-config.js";
// Import new icon system (replaces static icons.js)
import "./utils/icons.js";
// Import share modal composable to expose globally
import "./composables/useShareModal.js";

// Make available globally for non-module scripts
if (typeof window !== "undefined") {
  window.modalManager = modalManager;
  window.decryptFileKey = decryptFileKey;
  window.getVaultBaseUrl = getVaultBaseUrl;
}

// Note: The new icon system is imported above and automatically sets window.Icons
// The old static icons.js is still loaded in index.html for backward compatibility
// but will be replaced by the new system

// Patch Element.prototype.innerHTML and insertAdjacentHTML to use Trusted Types policies
// This ensures Vue's v-html directive and other HTML insertions work with Trusted Types
if (typeof Element !== "undefined" && Element.prototype) {
  // Patch innerHTML setter
  const originalInnerHTML = Object.getOwnPropertyDescriptor(
    Element.prototype,
    "innerHTML",
  );

  if (originalInnerHTML && originalInnerHTML.set) {
    Object.defineProperty(Element.prototype, "innerHTML", {
      set: function (value) {
        // If value is already a TrustedHTML, use it directly
        if (value && typeof value === "object" && value.toString) {
          try {
            originalInnerHTML.set.call(this, value);
            return;
          } catch (e) {
            // Fall through to policy wrapping
          }
        }

        // Try to use vaultHTMLPolicy first
        if (window.vaultHTMLPolicy && typeof value === "string") {
          try {
            const trustedHTML = window.vaultHTMLPolicy.createHTML(value);
            originalInnerHTML.set.call(this, trustedHTML);
            return;
          } catch (e) {
            // Fall through to next policy
          }
        }

        // Try defaultPolicy
        if (
          window.trustedTypes &&
          window.trustedTypes.defaultPolicy &&
          typeof value === "string"
        ) {
          try {
            const trustedHTML =
              window.trustedTypes.defaultPolicy.createHTML(value);
            originalInnerHTML.set.call(this, trustedHTML);
            return;
          } catch (e) {
            // Fall through to direct assignment
          }
        }

        // Last resort: direct assignment (will fail if Trusted Types is enforced)
        originalInnerHTML.set.call(this, value);
      },
      get: originalInnerHTML.get,
      configurable: true,
      enumerable: true,
    });
  }

  // Patch insertAdjacentHTML method
  const originalInsertAdjacentHTML = Element.prototype.insertAdjacentHTML;
  if (originalInsertAdjacentHTML) {
    Element.prototype.insertAdjacentHTML = function (position, text) {
      // If text is already a TrustedHTML, use it directly
      if (text && typeof text === "object" && text.toString) {
        try {
          return originalInsertAdjacentHTML.call(this, position, text);
        } catch (e) {
          // Fall through to policy wrapping
        }
      }

      // Try to use vaultHTMLPolicy first
      if (window.vaultHTMLPolicy && typeof text === "string") {
        try {
          const trustedHTML = window.vaultHTMLPolicy.createHTML(text);
          return originalInsertAdjacentHTML.call(this, position, trustedHTML);
        } catch (e) {
          // Fall through to next policy
        }
      }

      // Try defaultPolicy
      if (
        window.trustedTypes &&
        window.trustedTypes.defaultPolicy &&
        typeof text === "string"
      ) {
        try {
          const trustedHTML =
            window.trustedTypes.defaultPolicy.createHTML(text);
          return originalInsertAdjacentHTML.call(this, position, trustedHTML);
        } catch (e) {
          // Fall through to direct call
        }
      }

      // Last resort: direct call (will fail if Trusted Types is enforced)
      return originalInsertAdjacentHTML.call(this, position, text);
    };
  }
}

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

app.mount("#app");
