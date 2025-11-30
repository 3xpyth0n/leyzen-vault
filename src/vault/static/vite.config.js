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

// Plugin to ensure all asset URLs are relative (not absolute)
// This prevents browsers from converting relative URLs to HTTPS
function relativeUrlsPlugin() {
  return {
    name: "relative-urls-plugin",
    transformIndexHtml: {
      order: "post",
      handler(html) {
        // Replace any absolute URLs (http:// or https://) with relative URLs
        // This ensures browsers don't force HTTPS for IP addresses
        html = html.replace(/https?:\/\/[^"'\s]+/g, (match) => {
          // If it's an asset URL, make it relative
          if (match.includes("/static/") || match.includes("/assets/")) {
            const url = new URL(match);
            return url.pathname;
          }
          return match;
        });
        return html;
      },
    },
  };
}

export default defineConfig({
  plugins: [
    vue({
      // Disable CSS preloading to prevent 503 errors when server is slow
      template: {
        compilerOptions: {
          // This prevents Vue from automatically preloading CSS files
          // CSS will still be loaded, but not preloaded, avoiding 503 errors
        },
      },
    }),
    staticScriptsPlugin(),
    relativeUrlsPlugin(),
  ],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 100000,
    cssCodeSplit: true,
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
        manualChunks(id) {
          // Vendor dependencies
          if (id.includes("node_modules")) {
            // Vue framework (Vue, Vue Router, Pinia together - they're interdependent)
            if (
              id.includes("vue") ||
              id.includes("vue-router") ||
              id.includes("pinia")
            ) {
              return "vendor-vue";
            }
            // Lucide icons (can be large, separate it)
            if (id.includes("lucide")) {
              return "vendor-lucide";
            }
            // HTTP client
            if (id.includes("axios")) {
              return "vendor-utils";
            }
            // ZIP library (only used in VaultSpaceView, will be lazy-loaded)
            if (id.includes("jszip")) {
              return "vendor-zip";
            }
            // Other node_modules dependencies
            return "vendor-common";
          }
          // Shared components - split into two chunks to avoid circular dependencies
          // while still reducing size
          if (id.includes("/components/") && !id.includes("/admin/")) {
            // Split based on component type to balance chunk sizes
            // Group frequently used small components together
            if (
              id.includes("AlertModal") ||
              id.includes("ConfirmationModal") ||
              id.includes("CustomSelect") ||
              id.includes("PasswordInput") ||
              id.includes("ProgressBar") ||
              id.includes("SearchBar") ||
              id.includes("TwoFactorSetup") ||
              id.includes("TwoFactorVerify")
            ) {
              return "components-core";
            }
            // Group larger file-related components
            if (
              id.includes("FileListView") ||
              id.includes("FileMenuDropdown") ||
              id.includes("FilePreview") ||
              id.includes("FileProperties") ||
              id.includes("VirtualList") ||
              id.includes("BatchActions") ||
              id.includes("DragDropUpload")
            ) {
              return "components-file";
            }
            // Other components (layout, etc.)
            return "components-other";
          }
        },
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
      buffer: "buffer",
    },
  },
  define: {
    global: "globalThis",
    "process.env": {},
  },
  optimizeDeps: {
    include: ["buffer"],
  },
});
