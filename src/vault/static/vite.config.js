import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

// Plugin to suppress warnings about static scripts served directly by Flask
// These scripts don't need to be bundled by Vite - they're served directly
function staticScriptsPlugin() {
  return {
    name: "static-scripts-plugin",
    order: "pre",
    transformIndexHtml: {
      order: "pre",
      handler(html, context) {
        // Don't remove scripts - just leave them as-is
        // Vite will warn but the build will succeed
        return html;
      },
    },
  };
}

export default defineConfig({
  plugins: [vue(), staticScriptsPlugin()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
      },
      onwarn(warning, warn) {
        // Suppress warnings about static scripts that are served by Flask
        if (
          warning.message &&
          typeof warning.message === "string" &&
          (warning.message.includes(
            'can\'t be bundled without type="module"',
          ) ||
            warning.message.includes("trusted-types-init") ||
            warning.message.includes("icons.js") ||
            warning.message.includes("cleanup-modal.js") ||
            warning.message.includes("sharing.js"))
        ) {
          return;
        }
        warn(warning);
      },
    },
  },
  customLogger: {
    warn(msg, options) {
      // Suppress warnings about static scripts that are served by Flask
      if (
        typeof msg === "string" &&
        msg.includes('can\'t be bundled without type="module"') &&
        (msg.includes("trusted-types-init") ||
          msg.includes("icons.js") ||
          msg.includes("cleanup-modal.js") ||
          msg.includes("sharing.js"))
      ) {
        // Suppress this warning
        return;
      }
      // Use default warn behavior for other warnings
      console.warn(msg);
    },
    info(msg) {
      console.info(msg);
    },
    error(msg, options) {
      console.error(msg);
    },
    warnOnce(msg) {
      // Suppress warnings about static scripts that are served by Flask
      if (
        typeof msg === "string" &&
        msg.includes('can\'t be bundled without type="module"') &&
        (msg.includes("trusted-types-init") ||
          msg.includes("icons.js") ||
          msg.includes("cleanup-modal.js") ||
          msg.includes("sharing.js"))
      ) {
        // Suppress this warning
        return;
      }
      // Use default warnOnce behavior for other warnings
      console.warn(msg);
    },
  },
  base: "/static/",
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
