<template>
  <teleport to="body">
    <div v-if="show" class="file-preview-overlay" @click="close">
      <div class="file-preview-modal glass glass-card" @click.stop>
        <div class="preview-header">
          <h2>{{ fileName }}</h2>
          <div class="preview-actions">
            <button
              v-if="isZip"
              @click="handleUnzip"
              class="btn btn-primary"
              :disabled="unzipping"
            >
              {{ unzipping ? "Extracting..." : "Unzip" }}
            </button>
            <button @click="download" class="btn btn-secondary">
              Download
            </button>
            <button @click="close" class="btn-icon">✕</button>
          </div>
        </div>

        <div class="preview-content" v-if="loading">
          <div class="loading">Loading preview...</div>
        </div>

        <div class="preview-content" v-else-if="error">
          <div class="error-message glass">{{ error }}</div>
        </div>

        <div class="preview-content" v-else>
          <!-- Image Preview -->
          <div v-if="isImage" class="image-preview">
            <img :src="previewUrl" :alt="fileName" @load="onImageLoad" />
            <div v-if="imageLoading" class="loading-overlay">Loading...</div>
          </div>

          <!-- Video Preview -->
          <div v-else-if="isVideo" class="video-preview">
            <div
              ref="videoContainer"
              class="video-container"
              @mouseenter="showVideoControls"
              @mouseleave="hideVideoControls"
              @mousemove="showVideoControls"
            >
              <video
                ref="videoElement"
                :src="previewUrl"
                @timeupdate="updateVideoProgress"
                @loadedmetadata="onVideoLoadedMetadata"
                @play="isVideoPlaying = true"
                @pause="isVideoPlaying = false"
                @ended="isVideoPlaying = false"
                class="video-player"
              >
                Your browser does not support video playback.
              </video>
              <div
                class="video-player-controls"
                :class="{ 'video-player-controls--visible': showControls }"
              >
                <div class="video-player-controls__progress">
                  <p class="video-player-controls__time">
                    {{ formattedVideoCurrentTime }}
                  </p>
                  <span
                    class="video-player-controls__progress-bar"
                    @click="seekVideoByClick"
                    @mousedown="startVideoSeeking"
                  >
                    <span
                      class="video-player-controls__progress-filled"
                      :style="{ width: videoProgress + '%' }"
                    ></span>
                    <span
                      class="video-player-controls__progress-thumb"
                      :style="{ left: videoProgress + '%' }"
                    ></span>
                  </span>
                  <p class="video-player-controls__time">
                    {{ formattedVideoDuration }}
                  </p>
                </div>
                <div class="video-player-controls__bottom">
                  <div class="video-player-controls__left">
                    <svg
                      @click="seekVideoBackward"
                      viewBox="0 0 16 16"
                      class="video-player-controls__control-btn"
                    >
                      <path
                        d="M13 2.5L5 7.119V3H3v10h2V8.881l8 4.619z"
                        fill="currentColor"
                      />
                    </svg>
                    <svg
                      @click="toggleVideoPlay"
                      viewBox="0 0 16 16"
                      class="video-player-controls__control-btn video-player-controls__control-btn--play"
                      :class="{
                        'video-player-controls__control-btn--playing':
                          isVideoPlaying,
                      }"
                    >
                      <path
                        v-if="!isVideoPlaying"
                        d="M4.018 14L14.41 8 4.018 2z"
                        fill="currentColor"
                      />
                      <path
                        v-else
                        d="M3 2h3v12H3V2zm7 0h3v12h-3V2z"
                        fill="currentColor"
                      />
                    </svg>
                    <svg
                      @click="seekVideoForward"
                      viewBox="0 0 16 16"
                      class="video-player-controls__control-btn"
                    >
                      <path
                        d="M11 3v4.119L3 2.5v11l8-4.619V13h2V3z"
                        fill="currentColor"
                      />
                    </svg>
                  </div>
                  <p class="video-player-controls__song-name">{{ fileName }}</p>
                  <button
                    @click="toggleFullscreen"
                    class="video-player-controls__control-btn video-player-controls__control-btn--fullscreen"
                    :aria-label="
                      isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'
                    "
                  >
                    <svg
                      v-if="!isFullscreen"
                      viewBox="0 0 24 24"
                      width="16"
                      height="16"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M8 3H5C3.89543 3 3 3.89543 3 5V8M21 8V5C21 3.89543 20.1046 3 19 3H16M16 21H19C20.1046 21 21 20.1046 21 19V16M3 16V19C3 20.1046 3.89543 21 5 21H8"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                    <svg
                      v-else
                      viewBox="0 0 24 24"
                      width="16"
                      height="16"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M9 9L4 4M4 4V8M4 4H8M15 9L20 4M20 4V8M20 4H16M9 15L4 20M4 20V16M4 20H8M15 15L20 20M20 20V16M20 20H16"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Audio Preview -->
          <div v-else-if="isAudio" class="audio-preview">
            <div class="audio-player">
              <div class="audio-player__artwork">
                <img
                  v-if="hasAudioCover && audioCoverUrl"
                  :src="audioCoverUrl"
                  alt="Album cover"
                  class="audio-player__artwork-image"
                />
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"
                  />
                </svg>
              </div>
              <div class="audio-player__container">
                <p class="audio-player__song-name">{{ fileName }}</p>
                <div class="audio-player__progress">
                  <p class="audio-player__time">{{ formattedCurrentTime }}</p>
                  <span
                    class="audio-player__progress-bar"
                    @click="seekAudioByClick"
                    @mousedown="startSeeking"
                    @mousemove="updateProgressHover"
                    @mouseleave="hideProgressHover"
                  >
                    <span
                      class="audio-player__progress-filled"
                      :style="{ width: progress + '%' }"
                    ></span>
                    <span
                      class="audio-player__progress-thumb"
                      :style="{ left: progress + '%' }"
                    ></span>
                  </span>
                  <p class="audio-player__time">{{ formattedDuration }}</p>
                </div>
                <div class="audio-player__controls">
                  <svg
                    @click="seekBackward"
                    viewBox="0 0 16 16"
                    class="audio-player__control-btn"
                  >
                    <path
                      d="M13 2.5L5 7.119V3H3v10h2V8.881l8 4.619z"
                      fill="currentColor"
                    />
                  </svg>
                  <svg
                    @click="togglePlay"
                    viewBox="0 0 16 16"
                    class="audio-player__control-btn audio-player__control-btn--play"
                    :class="{ 'audio-player__control-btn--playing': isPlaying }"
                  >
                    <path
                      v-if="!isPlaying"
                      d="M4.018 14L14.41 8 4.018 2z"
                      fill="currentColor"
                    />
                    <path
                      v-else
                      d="M3 2h3v12H3V2zm7 0h3v12h-3V2z"
                      fill="currentColor"
                    />
                  </svg>
                  <svg
                    @click="seekForward"
                    viewBox="0 0 16 16"
                    class="audio-player__control-btn"
                  >
                    <path
                      d="M11 3v4.119L3 2.5v11l8-4.619V13h2V3z"
                      fill="currentColor"
                    />
                  </svg>
                </div>
              </div>
            </div>
            <audio
              ref="audioElement"
              :src="previewUrl"
              @timeupdate="updateProgress"
              @loadedmetadata="onLoadedMetadata"
              @play="isPlaying = true"
              @pause="isPlaying = false"
              @ended="isPlaying = false"
            ></audio>
          </div>

          <!-- Markdown Preview -->
          <div v-else-if="isMarkdown" class="markdown-preview">
            <div class="markdown-content" ref="markdownContentRef"></div>
          </div>

          <!-- Text Preview -->
          <div v-else-if="isText" class="text-preview">
            <pre class="text-content">{{ textContent }}</pre>
          </div>

          <!-- ZIP Preview -->
          <div v-else-if="isZip" class="zip-preview">
            <div v-if="zipLoading" class="loading">Loading ZIP contents...</div>
            <div v-else-if="zipFiles.length > 0" class="zip-content">
              <div class="zip-header">
                <h3>Archive Contents</h3>
                <p class="zip-info">
                  {{ zipFileCount }} {{ zipFileCount === 1 ? "file" : "files" }}
                  <span v-if="zipFolderCount > 0">
                    in {{ zipFolderCount }}
                    {{ zipFolderCount === 1 ? "folder" : "folders" }}
                  </span>
                </p>
              </div>
              <div class="zip-file-list">
                <div
                  v-for="(item, index) in zipFiles"
                  :key="index"
                  class="zip-file-item"
                  :class="{
                    'zip-folder-item': item.type === 'folder',
                    'zip-clickable': item.type === 'folder' && item.hasChildren,
                  }"
                  :style="{ paddingLeft: item.depth * 1.5 + 0.75 + 'rem' }"
                  @click="
                    item.type === 'folder' && item.hasChildren
                      ? toggleFolder(item.path)
                      : null
                  "
                >
                  <div
                    class="zip-expand-icon"
                    v-if="item.type === 'folder' && item.hasChildren"
                  >
                    <span
                      v-html="
                        getIcon(
                          isFolderExpanded(item.path)
                            ? 'chevronDown'
                            : 'chevronRight',
                          14,
                        )
                      "
                    ></span>
                  </div>
                  <div
                    class="zip-expand-placeholder"
                    v-else-if="item.type === 'folder' && !item.hasChildren"
                  ></div>
                  <div class="zip-file-icon">
                    <span
                      v-html="
                        getIcon(item.type === 'folder' ? 'folder' : 'file', 20)
                      "
                    ></span>
                  </div>
                  <div class="zip-file-info">
                    <div class="zip-file-name">{{ item.name }}</div>
                  </div>
                  <div class="zip-file-size" v-if="item.type === 'file'">
                    {{ formatFileSize(item.size) }}
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="zip-empty">
              <p>This ZIP file appears to be empty.</p>
            </div>
          </div>

          <!-- Unsupported Type -->
          <div v-else class="unsupported-preview">
            <div class="unsupported-icon" ref="defaultIconRef"></div>
            <p>Preview not available for this file type.</p>
            <p class="mime-type">{{ mimeType }}</p>
            <button @click="download" class="btn btn-primary">
              Download File
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
import { ref, computed, watch, nextTick } from "vue";
import { files } from "../services/api";
import {
  getUserMasterKey,
  getCachedVaultSpaceKey,
  decryptVaultSpaceKeyForUser,
} from "../services/keyManager";
import { decryptFile, decryptFileKey } from "../services/encryption";
import { normalizeMimeType } from "../utils/mimeType";
import * as mm from "music-metadata";
import JSZip from "jszip";

export default {
  name: "FilePreview",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    fileId: {
      type: String,
      default: null,
    },
    fileName: {
      type: String,
      default: "",
    },
    mimeType: {
      type: String,
      default: "",
    },
    vaultspaceId: {
      type: String,
      required: true,
    },
  },
  emits: ["close", "download", "unzip"],
  setup(props, { emit }) {
    const loading = ref(false);
    const error = ref(null);
    const previewUrl = ref(null);
    const textContent = ref("");
    const markdownContent = ref("");
    const imageLoading = ref(false);
    const markdownContentRef = ref(null);
    const defaultIconRef = ref(null);

    // ZIP preview state
    const zipFiles = ref([]);
    const zipTree = ref({});
    const zipLoading = ref(false);
    const unzipping = ref(false);
    const expandedFolders = ref(new Set());

    // Audio player state
    const audioElement = ref(null);
    const isPlaying = ref(false);
    const currentTime = ref(0);
    const duration = ref(0);
    const progress = ref(0);
    const volume = ref(100);
    const audioCoverUrl = ref(null);
    const hasAudioCover = ref(false);

    // Video player state
    const videoElement = ref(null);
    const videoContainer = ref(null);
    const isVideoPlaying = ref(false);
    const videoCurrentTime = ref(0);
    const videoDuration = ref(0);
    const videoProgress = ref(0);
    const showControls = ref(false);
    const isFullscreen = ref(false);
    let videoControlsTimeout = null;

    // Normalize mime type from extension if needed
    const normalizedMimeType = computed(() => {
      return normalizeMimeType(props.fileName, props.mimeType);
    });

    const isImage = computed(() => {
      return (
        normalizedMimeType.value &&
        normalizedMimeType.value.startsWith("image/")
      );
    });

    const isVideo = computed(() => {
      return (
        normalizedMimeType.value &&
        normalizedMimeType.value.startsWith("video/")
      );
    });

    const isAudio = computed(() => {
      return (
        normalizedMimeType.value &&
        normalizedMimeType.value.startsWith("audio/")
      );
    });

    const isMarkdown = computed(() => {
      if (!props.fileName && !props.mimeType) return false;
      const fileName = props.fileName.toLowerCase();
      return (
        fileName.endsWith(".md") ||
        fileName.endsWith(".markdown") ||
        props.mimeType === "text/markdown" ||
        props.mimeType === "text/x-markdown"
      );
    });

    const isText = computed(() => {
      if (!props.fileName && !props.mimeType) return false;
      const fileName = props.fileName.toLowerCase();
      const textExtensions = [".txt", ".log", ".csv", ".ini", ".conf", ".cfg"];
      const hasTextExtension = textExtensions.some((ext) =>
        fileName.endsWith(ext),
      );
      return (
        hasTextExtension ||
        (props.mimeType &&
          (props.mimeType.startsWith("text/") ||
            props.mimeType === "application/json" ||
            props.mimeType === "application/xml" ||
            props.mimeType.includes("javascript") ||
            props.mimeType.includes("css") ||
            props.mimeType.includes("html")) &&
          !isMarkdown.value)
      );
    });

    const isZip = computed(() => {
      if (!props.fileName && !props.mimeType) return false;
      const fileName = props.fileName.toLowerCase();
      return (
        fileName.endsWith(".zip") ||
        normalizedMimeType.value === "application/zip" ||
        normalizedMimeType.value === "application/x-zip-compressed" ||
        props.mimeType === "application/zip" ||
        props.mimeType === "application/x-zip-compressed"
      );
    });

    // Count items recursively in tree
    const countItemsInTree = (tree, type) => {
      let count = 0;
      const traverse = (node) => {
        Object.values(node).forEach((item) => {
          if (item.type === type) {
            count++;
          }
          if (item.children && Object.keys(item.children).length > 0) {
            traverse(item.children);
          }
        });
      };
      traverse(tree);
      return count;
    };

    const zipFileCount = computed(() => {
      if (!zipTree.value || Object.keys(zipTree.value).length === 0) return 0;
      return countItemsInTree(zipTree.value, "file");
    });

    const zipFolderCount = computed(() => {
      if (!zipTree.value || Object.keys(zipTree.value).length === 0) return 0;
      return countItemsInTree(zipTree.value, "folder");
    });

    // Simple Markdown to HTML converter (basic implementation)
    const markdownToHtml = (markdown) => {
      if (!markdown) return "";
      // Ensure markdown is a string
      if (typeof markdown !== "string") {
        markdown = String(markdown);
      }
      let html = markdown;

      // Escape HTML to prevent XSS
      const escapeHtml = (text) => {
        const div = document.createElement("div");
        div.textContent = text;
        // Return as string (not TrustedHTML) so we can use .replace() on it
        return div.innerHTML;
      };

      // Escape URL to prevent XSS, but allow safe protocols
      const escapeUrl = (url) => {
        // Allow http, https, mailto, and relative URLs
        if (/^(https?|mailto|#|\/)/i.test(url.trim())) {
          return escapeHtml(url.trim());
        }
        // For unsafe protocols, return empty hash
        return "#";
      };

      // Step 1: Extract code blocks to avoid processing links inside them
      const codeBlockPlaceholders = [];
      html = html.replace(/```([\s\S]*?)```/gim, (match, code) => {
        const placeholder = `__CODE_BLOCK_${codeBlockPlaceholders.length}__`;
        codeBlockPlaceholders.push(code);
        return placeholder;
      });

      // Step 2: Extract inline code to avoid processing links inside them
      const inlineCodePlaceholders = [];
      html = html.replace(/`([^`]+)`/gim, (match, code) => {
        const placeholder = `__INLINE_CODE_${inlineCodePlaceholders.length}__`;
        inlineCodePlaceholders.push(code);
        return placeholder;
      });

      // Step 3: Escape HTML first (this escapes <, >, &, ", ' but NOT brackets and parentheses)
      html = escapeHtml(html);

      // Step 4: Process images FIRST (before links, to avoid conflicts)
      // Support ![alt text](url) and ![alt text](url "title") formats
      html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/gim, (match, alt, url) => {
        // Clean URL (remove title if present - handle both escaped and unescaped quotes)
        let cleanUrl = url.trim();
        // Remove title if present (format: url "title" or url &quot;title&quot;)
        cleanUrl = cleanUrl.replace(/\s+(&quot;|"|')[^"']*("|'|&quot;)$/, "");

        // Unescape common HTML entities in URL
        cleanUrl = cleanUrl
          .replace(/&amp;/g, "&")
          .replace(/&lt;/g, "<")
          .replace(/&gt;/g, ">")
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
          .replace(/&#x27;/g, "'");

        const safeUrl = escapeUrl(cleanUrl);
        const safeAlt = alt || "";
        // Return image tag with CSS class (no inline styles for CSP compliance)
        return `<img src="${safeUrl}" alt="${safeAlt}" class="markdown-image">`;
      });

      // Step 5: Process links AFTER images (brackets and parentheses are preserved)
      // Support both [text](url) and [text](url "title") formats
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/gim, (match, text, url) => {
        // Clean URL (remove title if present - handle both escaped and unescaped quotes)
        let cleanUrl = url.trim();
        // Remove title if present (format: url "title" or url &quot;title&quot;)
        cleanUrl = cleanUrl.replace(/\s+(&quot;|"|')[^"']*("|'|&quot;)$/, "");

        // Unescape common HTML entities in URL
        cleanUrl = cleanUrl
          .replace(/&amp;/g, "&")
          .replace(/&lt;/g, "<")
          .replace(/&gt;/g, ">")
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
          .replace(/&#x27;/g, "'");

        const safeUrl = escapeUrl(cleanUrl);
        // Text is already escaped by escapeHtml, so use it directly
        return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${text}</a>`;
      });

      // Step 6: Restore code blocks (already escaped in placeholder)
      codeBlockPlaceholders.forEach((code, index) => {
        const escapedCode = escapeHtml(code);
        html = html.replace(
          `__CODE_BLOCK_${index}__`,
          `<pre><code>${escapedCode}</code></pre>`,
        );
      });

      // Step 7: Restore inline code (already escaped in placeholder)
      inlineCodePlaceholders.forEach((code, index) => {
        const escapedCode = escapeHtml(code);
        html = html.replace(
          `__INLINE_CODE_${index}__`,
          `<code>${escapedCode}</code>`,
        );
      });

      // Step 7: Process headers (on escaped HTML, but links are already processed)
      html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
      html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
      html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");

      // Step 8: Process bold and italic (on escaped HTML)
      html = html.replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>");
      html = html.replace(/__(.*?)__/gim, "<strong>$1</strong>");

      // Italic (but not inside code blocks - already handled by placeholders)
      html = html.replace(
        /(?<!`)\*(?!`)([^*]+?)(?<!`)\*(?!`)/gim,
        "<em>$1</em>",
      );
      html = html.replace(/(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)/gim, "<em>$1</em>");

      // Process lists line by line
      const lines = html.split("\n");
      const processedLines = [];
      let inList = false;
      let listType = null;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const unorderedMatch = line.match(/^[\*\-\+] (.+)$/);
        const orderedMatch = line.match(/^\d+\. (.+)$/);

        if (unorderedMatch) {
          if (!inList || listType !== "ul") {
            if (inList && listType === "ol") {
              processedLines.push("</ol>");
            }
            processedLines.push("<ul>");
            inList = true;
            listType = "ul";
          }
          processedLines.push(`<li>${unorderedMatch[1]}</li>`);
        } else if (orderedMatch) {
          if (!inList || listType !== "ol") {
            if (inList && listType === "ul") {
              processedLines.push("</ul>");
            }
            processedLines.push("<ol>");
            inList = true;
            listType = "ol";
          }
          processedLines.push(`<li>${orderedMatch[1]}</li>`);
        } else {
          if (inList) {
            processedLines.push(listType === "ul" ? "</ul>" : "</ol>");
            inList = false;
            listType = null;
          }
          if (line.trim()) {
            processedLines.push(line);
          }
        }
      }

      if (inList) {
        processedLines.push(listType === "ul" ? "</ul>" : "</ol>");
      }

      html = processedLines.join("\n");

      // Convert double line breaks to paragraphs
      html = html
        .split(/\n\n+/)
        .map((para) => {
          para = para.trim();
          if (!para) return "";
          // Don't wrap if already a block element
          if (
            para.startsWith("<h") ||
            para.startsWith("<ul") ||
            para.startsWith("<ol") ||
            para.startsWith("<pre") ||
            para.startsWith("<p")
          ) {
            return para;
          }
          return `<p>${para.replace(/\n/g, "<br>")}</p>`;
        })
        .filter((p) => p)
        .join("\n");

      return html;
    };

    const loadPreview = async () => {
      if (!props.fileId || !props.vaultspaceId) return;

      loading.value = true;
      error.value = null;
      previewUrl.value = null;
      textContent.value = "";
      markdownContent.value = "";
      zipFiles.value = [];
      zipTree.value = {};
      zipLoading.value = false;
      expandedFolders.value.clear();

      // Clean up previous audio cover
      if (audioCoverUrl.value) {
        URL.revokeObjectURL(audioCoverUrl.value);
        audioCoverUrl.value = null;
      }
      hasAudioCover.value = false;

      try {
        // Get VaultSpace key
        const vaultspaceKey = getCachedVaultSpaceKey(props.vaultspaceId);
        if (!vaultspaceKey) {
          throw new Error("VaultSpace key not loaded");
        }

        // Download encrypted file
        const encryptedData = await files.download(
          props.fileId,
          props.vaultspaceId,
        );

        // Get file key from server
        const fileData = await files.get(props.fileId, props.vaultspaceId);
        if (!fileData.file_key) {
          throw new Error("File key not found");
        }

        // Decrypt file key with VaultSpace key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Decrypt file data
        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create preview based on file type
        if (isZip.value) {
          // For ZIP files, load archive contents
          await loadZipPreview(decryptedData);
        } else if (isImage.value || isVideo.value || isAudio.value) {
          // Create blob URL for media files using normalized mime type
          const blob = new Blob([decryptedData], {
            type: normalizedMimeType.value,
          });
          previewUrl.value = URL.createObjectURL(blob);

          // Extract cover art for audio files
          if (isAudio.value) {
            extractAudioCover(decryptedData).then((coverUrl) => {
              if (coverUrl) {
                audioCoverUrl.value = coverUrl;
                hasAudioCover.value = true;
              } else {
                hasAudioCover.value = false;
              }
            });
          }
        } else if (isMarkdown.value) {
          // For Markdown files, convert to HTML
          const decoder = new TextDecoder("utf-8");
          const markdownText = decoder.decode(decryptedData);
          const html = markdownToHtml(markdownText);
          markdownContent.value = html;

          // Set HTML using Trusted Types - wait for ref to be available
          await nextTick();
          await nextTick();
          await nextTick();
          let attempts = 0;
          while (!markdownContentRef.value && attempts < 20) {
            await new Promise((resolve) => setTimeout(resolve, 50));
            attempts++;
          }
          if (markdownContentRef.value) {
            if (window.vaultHTMLPolicy) {
              markdownContentRef.value.innerHTML =
                window.vaultHTMLPolicy.createHTML(html);
            } else {
              markdownContentRef.value.innerHTML = html;
            }
          }
        } else if (isText.value) {
          // For text files, decode and display
          const decoder = new TextDecoder("utf-8");
          textContent.value = decoder.decode(decryptedData);
        }
      } catch (err) {
        error.value = err.message || "Failed to load preview";
      } finally {
        loading.value = false;
      }
    };

    // Build hierarchical structure from paths
    const buildTreeStructure = (items) => {
      const tree = {};
      const seenPaths = new Set();

      items.forEach((item) => {
        const pathParts = item.path.split("/").filter((p) => p);
        if (pathParts.length === 0) return;

        let current = tree;

        // First, ensure all parent folders exist
        pathParts.forEach((part, index) => {
          const isLast = index === pathParts.length - 1;
          const currentPath = pathParts.slice(0, index + 1).join("/");

          if (!current[part]) {
            // Create folder entry if it doesn't exist
            current[part] = {
              name: part,
              type: isLast && item.type === "file" ? "file" : "folder",
              size: isLast && item.type === "file" ? item.size : 0,
              path: currentPath,
              children: {},
            };
            if (!isLast || item.type === "folder") {
              seenPaths.add(currentPath);
            }
          } else if (isLast && item.type === "file") {
            // Update existing entry if it's a file
            current[part].type = "file";
            current[part].size = item.size;
          }

          if (!isLast) {
            current = current[part].children;
          }
        });
      });

      // Sort tree children
      const sortTree = (node) => {
        const sorted = {};
        const entries = Object.entries(node).sort(([aKey, a], [bKey, b]) => {
          // Folders first, then files, both alphabetically
          if (a.type === "folder" && b.type !== "folder") return -1;
          if (a.type !== "folder" && b.type === "folder") return 1;
          return a.name.localeCompare(b.name);
        });

        entries.forEach(([key, item]) => {
          sorted[key] = { ...item };
          if (item.type === "folder" && Object.keys(item.children).length > 0) {
            sorted[key].children = sortTree(item.children);
          }
        });

        return sorted;
      };

      return sortTree(tree);
    };

    // Generate visible list from tree based on expanded folders
    const generateVisibleList = (tree, expanded, depth = 0) => {
      const visible = [];

      const traverse = (node, currentDepth = 0) => {
        const children = Object.values(node).sort((a, b) => {
          // Folders first, then files, both alphabetically
          if (a.type === "folder" && b.type !== "folder") return -1;
          if (a.type !== "folder" && b.type === "folder") return 1;
          return a.name.localeCompare(b.name);
        });

        children.forEach((item) => {
          visible.push({
            name: item.name,
            type: item.type,
            size: item.size,
            path: item.path,
            depth: currentDepth,
            hasChildren:
              item.type === "folder" &&
              Object.keys(item.children || {}).length > 0,
          });

          // If it's a folder and it's expanded, traverse its children
          if (
            item.type === "folder" &&
            expanded.has(item.path) &&
            Object.keys(item.children || {}).length > 0
          ) {
            traverse(item.children, currentDepth + 1);
          }
        });
      };

      traverse(tree, depth);
      return visible;
    };

    // Toggle folder expansion state
    const toggleFolder = (folderPath) => {
      if (expandedFolders.value.has(folderPath)) {
        expandedFolders.value.delete(folderPath);
      } else {
        expandedFolders.value.add(folderPath);
      }
      // Regenerate visible list
      zipFiles.value = generateVisibleList(
        zipTree.value,
        expandedFolders.value,
      );
    };

    // Check if folder is expanded
    const isFolderExpanded = (folderPath) => {
      return expandedFolders.value.has(folderPath);
    };

    // Load ZIP preview contents
    const loadZipPreview = async (decryptedData) => {
      zipLoading.value = true;
      zipFiles.value = [];

      try {
        // Load ZIP file using JSZip
        const zip = await JSZip.loadAsync(decryptedData);

        // Extract file and folder list
        const itemsList = [];
        const folderPaths = new Set();

        zip.forEach((relativePath, file) => {
          // Extract folder paths from file paths
          if (!file.dir && relativePath) {
            const pathParts = relativePath.split("/").filter((p) => p);
            // Create folder paths for all parent directories
            for (let i = 1; i < pathParts.length; i++) {
              const folderPath = pathParts.slice(0, i).join("/");
              folderPaths.add(folderPath);
            }
          }

          // Get file size from JSZip file object
          let fileSize = 0;
          if (file.dir) {
            // It's a directory entry
            const cleanPath = relativePath.endsWith("/")
              ? relativePath.slice(0, -1)
              : relativePath;
            itemsList.push({
              name:
                cleanPath
                  .split("/")
                  .filter((p) => p)
                  .pop() || cleanPath,
              path: cleanPath,
              type: "folder",
              size: 0,
            });
          } else {
            // It's a file
            if (file._data && file._data.uncompressedSize !== undefined) {
              fileSize = file._data.uncompressedSize;
            } else if (file._data && file._data.length !== undefined) {
              fileSize = file._data.length;
            }

            itemsList.push({
              name: relativePath.split("/").pop(),
              path: relativePath,
              type: "file",
              size: fileSize,
            });
          }
        });

        // Add missing folder entries
        folderPaths.forEach((folderPath) => {
          // Check if folder is already in itemsList
          const exists = itemsList.some(
            (item) => item.path === folderPath && item.type === "folder",
          );
          if (!exists) {
            itemsList.push({
              name: folderPath.split("/").pop(),
              path: folderPath,
              type: "folder",
              size: 0,
            });
          }
        });

        // Build hierarchical structure
        const treeStructure = buildTreeStructure(itemsList);
        zipTree.value = treeStructure;

        // Generate visible list from tree (all folders collapsed by default)
        zipFiles.value = generateVisibleList(
          treeStructure,
          expandedFolders.value,
        );
      } catch (err) {
        error.value = `Failed to load ZIP contents: ${err.message}`;
        zipFiles.value = [];
      } finally {
        zipLoading.value = false;
      }
    };

    // Format file size for display
    const formatFileSize = (bytes) => {
      if (!bytes || bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
    };

    // Handle unzip action
    const handleUnzip = () => {
      unzipping.value = true;
      emit("unzip", props.fileId);
    };

    // Get icon from Lucide library
    const getIcon = (iconName, size = 24) => {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      // Fallback to old method
      if (window.Icons[iconName]) {
        const iconFunction = window.Icons[iconName];
        if (typeof iconFunction === "function") {
          return iconFunction.call(window.Icons, size, "currentColor");
        }
      }
      return "";
    };

    // Default file icon SVG
    const defaultFileIcon = computed(() => {
      if (!window.Icons) {
        return `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
      }

      // Use the centralized icon helper function
      const iconName = window.Icons.getFileIconName
        ? window.Icons.getFileIconName(props.mimeType, props.fileName)
        : "file";

      // Get the icon function and call it with proper context
      const iconFunction = window.Icons[iconName];
      if (iconFunction && typeof iconFunction === "function") {
        return iconFunction.call(window.Icons, 64, "currentColor");
      }

      // Fallback to generic file icon
      return window.Icons.file(64, "currentColor");
    });

    const close = () => {
      // Clean up audio
      if (audioElement.value) {
        audioElement.value.pause();
        audioElement.value.src = "";
        audioElement.value.load();
        isPlaying.value = false;
        currentTime.value = 0;
        duration.value = 0;
        progress.value = 0;
      }
      // Clean up blob URLs
      if (previewUrl.value) {
        URL.revokeObjectURL(previewUrl.value);
        previewUrl.value = null;
      }
      // Clean up audio cover
      if (audioCoverUrl.value) {
        URL.revokeObjectURL(audioCoverUrl.value);
        audioCoverUrl.value = null;
      }
      hasAudioCover.value = false;
      // Clean up content
      textContent.value = "";
      markdownContent.value = "";
      // Clean up ZIP preview
      zipFiles.value = [];
      zipTree.value = {};
      unzipping.value = false;
      zipLoading.value = false;
      expandedFolders.value.clear();
      emit("close");
    };

    const download = () => {
      emit("download", props.fileId);
    };

    const onImageLoad = () => {
      imageLoading.value = false;
    };

    // Audio player functions
    const formatTime = (seconds) => {
      if (!isFinite(seconds) || isNaN(seconds)) return "0:00";
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    const formattedCurrentTime = computed(() => formatTime(currentTime.value));
    const formattedDuration = computed(() => formatTime(duration.value));

    const togglePlay = () => {
      if (!audioElement.value) return;
      if (isPlaying.value) {
        audioElement.value.pause();
      } else {
        audioElement.value.play().catch((err) => {
          error.value = "Failed to play audio: " + err.message;
        });
      }
    };

    const updateProgress = () => {
      if (!audioElement.value) return;
      currentTime.value = audioElement.value.currentTime;
      if (duration.value > 0) {
        progress.value = (currentTime.value / duration.value) * 100;
      }
    };

    const seekAudio = (event) => {
      if (!audioElement.value) return;
      const newProgress = parseFloat(event.target.value);
      progress.value = newProgress;
      if (duration.value > 0) {
        audioElement.value.currentTime = (newProgress / 100) * duration.value;
      }
    };

    const updateVolume = (event) => {
      if (!audioElement.value) return;
      const newVolume = parseFloat(event.target.value);
      volume.value = newVolume;
      audioElement.value.volume = newVolume / 100;
    };

    const onLoadedMetadata = () => {
      if (!audioElement.value) return;
      duration.value = audioElement.value.duration;
      audioElement.value.volume = volume.value / 100;
    };

    const seekBackward = () => {
      if (!audioElement.value) return;
      audioElement.value.currentTime = Math.max(
        0,
        audioElement.value.currentTime - 10,
      );
    };

    const seekForward = () => {
      if (!audioElement.value) return;
      audioElement.value.currentTime = Math.min(
        duration.value,
        audioElement.value.currentTime + 10,
      );
    };

    const isSeeking = ref(false);

    const seekAudioByClick = (event) => {
      if (!audioElement.value || !duration.value) return;
      const progressBar = event.currentTarget;
      const rect = progressBar.getBoundingClientRect();
      const clickX = event.clientX - rect.left;
      const percentage = (clickX / rect.width) * 100;
      const newTime = (percentage / 100) * duration.value;
      audioElement.value.currentTime = Math.max(
        0,
        Math.min(newTime, duration.value),
      );
    };

    const startSeeking = (event) => {
      if (!audioElement.value || !duration.value) return;
      event.preventDefault();
      isSeeking.value = true;
      const progressBar = event.currentTarget;
      progressBar.classList.add("seeking");
      const rect = progressBar.getBoundingClientRect();

      const updateSeek = (clientX) => {
        const moveX = clientX - rect.left;
        const movePercentage = Math.max(
          0,
          Math.min(100, (moveX / rect.width) * 100),
        );
        const moveTime = (movePercentage / 100) * duration.value;
        audioElement.value.currentTime = Math.max(
          0,
          Math.min(moveTime, duration.value),
        );
      };

      updateSeek(event.clientX);

      const handleMouseMove = (moveEvent) => {
        if (!isSeeking.value) return;
        updateSeek(moveEvent.clientX);
      };

      const handleMouseUp = () => {
        isSeeking.value = false;
        progressBar.classList.remove("seeking");
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    };

    const updateProgressHover = () => {
      // Can be used for hover effects if needed
    };

    const hideProgressHover = () => {
      // Can be used for hover effects if needed
    };

    // Extract audio cover art from MP3 metadata
    const extractAudioCover = async (decryptedData) => {
      try {
        // Create a Blob from the decrypted data
        // Use ArrayBuffer to ensure compatibility
        const arrayBuffer =
          decryptedData instanceof ArrayBuffer
            ? decryptedData
            : decryptedData.buffer || new Uint8Array(decryptedData).buffer;

        const mimeType =
          normalizedMimeType.value || props.mimeType || "audio/mpeg";
        const blob = new Blob([arrayBuffer], {
          type: mimeType,
        });

        // Parse metadata using music-metadata
        // Convert blob to ArrayBuffer for parsing
        const audioArrayBuffer = await blob.arrayBuffer();
        const metadata = await mm.parseBuffer(
          new Uint8Array(audioArrayBuffer),
          blob.type,
        );

        // Check if there's a picture/cover art in the metadata
        if (metadata.common?.picture && metadata.common.picture.length > 0) {
          // Get the first picture (usually the album cover)
          const picture = metadata.common.picture[0];

          if (picture?.data) {
            // Convert picture.data to Uint8Array
            let pictureData;
            if (picture.data instanceof Uint8Array) {
              pictureData = picture.data;
            } else if (picture.data instanceof ArrayBuffer) {
              pictureData = new Uint8Array(picture.data);
            } else if (Buffer && Buffer.isBuffer(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else if (Array.isArray(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else {
              pictureData = new Uint8Array(Object.values(picture.data));
            }

            // Determine MIME type from format
            let pictureFormat = "image/jpeg"; // Default
            if (picture.format) {
              const format = picture.format.toLowerCase();
              if (format.startsWith("image/")) {
                pictureFormat = picture.format;
              } else {
                const formatMap = {
                  jpeg: "image/jpeg",
                  jpg: "image/jpeg",
                  png: "image/png",
                  gif: "image/gif",
                  bmp: "image/bmp",
                  webp: "image/webp",
                };
                pictureFormat = formatMap[format] || "image/jpeg";
              }
            }

            const pictureBlob = new Blob([pictureData], {
              type: pictureFormat,
            });
            const blobUrl = URL.createObjectURL(pictureBlob);
            return blobUrl;
          }
        }
        return null;
      } catch (err) {
        // Log error for debugging but don't show to user
        return null;
      }
    };

    // Video player functions
    const formattedVideoCurrentTime = computed(() =>
      formatTime(videoCurrentTime.value),
    );
    const formattedVideoDuration = computed(() =>
      formatTime(videoDuration.value),
    );

    const toggleVideoPlay = () => {
      if (!videoElement.value) return;
      if (isVideoPlaying.value) {
        videoElement.value.pause();
        showControls.value = true; // Keep controls visible when paused
      } else {
        videoElement.value.play().catch((err) => {
          error.value = "Failed to play video: " + err.message;
        });
        showVideoControls(); // Show controls when starting to play
      }
    };

    const updateVideoProgress = () => {
      if (!videoElement.value) return;
      videoCurrentTime.value = videoElement.value.currentTime;
      if (videoDuration.value > 0) {
        videoProgress.value =
          (videoCurrentTime.value / videoDuration.value) * 100;
      }
    };

    const onVideoLoadedMetadata = () => {
      if (!videoElement.value) return;
      videoDuration.value = videoElement.value.duration;
      // Show controls initially when video is loaded
      showControls.value = true;
    };

    const seekVideoBackward = () => {
      if (!videoElement.value) return;
      videoElement.value.currentTime = Math.max(
        0,
        videoElement.value.currentTime - 10,
      );
    };

    const seekVideoForward = () => {
      if (!videoElement.value) return;
      videoElement.value.currentTime = Math.min(
        videoDuration.value,
        videoElement.value.currentTime + 10,
      );
    };

    const isVideoSeeking = ref(false);

    const seekVideoByClick = (event) => {
      if (!videoElement.value || !videoDuration.value) return;
      const progressBar = event.currentTarget;
      const rect = progressBar.getBoundingClientRect();
      const clickX = event.clientX - rect.left;
      const percentage = (clickX / rect.width) * 100;
      const newTime = (percentage / 100) * videoDuration.value;
      videoElement.value.currentTime = Math.max(
        0,
        Math.min(newTime, videoDuration.value),
      );
    };

    const startVideoSeeking = (event) => {
      if (!videoElement.value || !videoDuration.value) return;
      event.preventDefault();
      isVideoSeeking.value = true;
      const progressBar = event.currentTarget;
      progressBar.classList.add("seeking");
      const rect = progressBar.getBoundingClientRect();

      const updateSeek = (clientX) => {
        const moveX = clientX - rect.left;
        const movePercentage = Math.max(
          0,
          Math.min(100, (moveX / rect.width) * 100),
        );
        const moveTime = (movePercentage / 100) * videoDuration.value;
        videoElement.value.currentTime = Math.max(
          0,
          Math.min(moveTime, videoDuration.value),
        );
      };

      updateSeek(event.clientX);

      const handleMouseMove = (moveEvent) => {
        if (!isVideoSeeking.value) return;
        updateSeek(moveEvent.clientX);
      };

      const handleMouseUp = () => {
        isVideoSeeking.value = false;
        progressBar.classList.remove("seeking");
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    };

    const showVideoControls = () => {
      showControls.value = true;
      if (videoControlsTimeout) {
        clearTimeout(videoControlsTimeout);
      }
      videoControlsTimeout = setTimeout(() => {
        if (!isVideoPlaying.value) {
          // Keep controls visible if video is paused
          return;
        }
        showControls.value = false;
      }, 3000);
    };

    const hideVideoControls = () => {
      if (videoControlsTimeout) {
        clearTimeout(videoControlsTimeout);
      }
      // Only hide if video is playing
      if (isVideoPlaying.value) {
        showControls.value = false;
      }
    };

    const checkFullscreenState = () => {
      const fullscreenElement =
        document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement ||
        document.msFullscreenElement;

      isFullscreen.value = fullscreenElement === videoContainer.value;
      return isFullscreen.value;
    };

    const toggleFullscreen = async () => {
      if (!videoContainer.value) return;

      const isCurrentlyFullscreen = checkFullscreenState();

      try {
        if (!isCurrentlyFullscreen) {
          // Enter fullscreen
          if (videoContainer.value.requestFullscreen) {
            await videoContainer.value.requestFullscreen();
          } else if (videoContainer.value.webkitRequestFullscreen) {
            await videoContainer.value.webkitRequestFullscreen();
          } else if (videoContainer.value.mozRequestFullScreen) {
            await videoContainer.value.mozRequestFullScreen();
          } else if (videoContainer.value.msRequestFullscreen) {
            await videoContainer.value.msRequestFullscreen();
          }
        } else {
          // Exit fullscreen
          if (document.exitFullscreen) {
            await document.exitFullscreen();
          } else if (document.webkitExitFullscreen) {
            await document.webkitExitFullscreen();
          } else if (document.mozCancelFullScreen) {
            await document.mozCancelFullScreen();
          } else if (document.msExitFullscreen) {
            await document.msExitFullscreen();
          }
        }
      } catch (error) {}
    };

    const handleFullscreenChange = () => {
      checkFullscreenState();
    };

    const handleVideoKeydown = (event) => {
      // Only handle keys when video is focused or visible
      if (!props.show || !isVideo.value) return;

      // Prevent default behavior for video controls
      if (
        event.target.tagName === "INPUT" ||
        event.target.tagName === "TEXTAREA"
      ) {
        return;
      }

      switch (event.key) {
        case " ":
        case "Spacebar":
          event.preventDefault();
          toggleVideoPlay();
          break;
        case "ArrowLeft":
          event.preventDefault();
          seekVideoBackward();
          break;
        case "ArrowRight":
          event.preventDefault();
          seekVideoForward();
          break;
        case "Escape":
          if (checkFullscreenState()) {
            event.preventDefault();
            toggleFullscreen();
          }
          break;
        case "f":
        case "F":
          event.preventDefault();
          toggleFullscreen();
          break;
      }
    };

    // Watch for file changes
    watch(
      () => [props.show, props.fileId],
      async ([newShow, newFileId]) => {
        if (newShow && newFileId) {
          // Wait for DOM to be ready before loading preview
          // Use multiple nextTick to ensure Vue has rendered everything
          await nextTick();
          await nextTick();
          await nextTick();
          await new Promise((resolve) => setTimeout(resolve, 100));
          await loadPreview();

          // Add keyboard listeners for video controls after preview is loaded
          await nextTick();
          if (isVideo.value) {
            document.addEventListener("keydown", handleVideoKeydown);
            document.addEventListener(
              "fullscreenchange",
              handleFullscreenChange,
            );
            document.addEventListener(
              "webkitfullscreenchange",
              handleFullscreenChange,
            );
            document.addEventListener(
              "mozfullscreenchange",
              handleFullscreenChange,
            );
            document.addEventListener(
              "MSFullscreenChange",
              handleFullscreenChange,
            );
            // Check initial fullscreen state
            checkFullscreenState();
          }
        } else if (!newShow) {
          // Clean up when closing
          if (audioElement.value) {
            audioElement.value.pause();
            audioElement.value.src = "";
            audioElement.value.load();
            isPlaying.value = false;
            currentTime.value = 0;
            duration.value = 0;
            progress.value = 0;
          }
          if (videoElement.value) {
            videoElement.value.pause();
            videoElement.value.src = "";
            videoElement.value.load();
            isVideoPlaying.value = false;
            videoCurrentTime.value = 0;
            videoDuration.value = 0;
            videoProgress.value = 0;
          }
          if (videoControlsTimeout) {
            clearTimeout(videoControlsTimeout);
            videoControlsTimeout = null;
          }
          showControls.value = false;

          // Remove keyboard listeners
          document.removeEventListener("keydown", handleVideoKeydown);
          document.removeEventListener(
            "fullscreenchange",
            handleFullscreenChange,
          );
          document.removeEventListener(
            "webkitfullscreenchange",
            handleFullscreenChange,
          );
          document.removeEventListener(
            "mozfullscreenchange",
            handleFullscreenChange,
          );
          document.removeEventListener(
            "MSFullscreenChange",
            handleFullscreenChange,
          );

          // Exit fullscreen if active
          if (checkFullscreenState()) {
            (async () => {
              try {
                if (document.exitFullscreen) {
                  await document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                  await document.webkitExitFullscreen();
                } else if (document.mozCancelFullScreen) {
                  await document.mozCancelFullScreen();
                } else if (document.msExitFullscreen) {
                  await document.msExitFullscreen();
                }
              } catch (error) {}
            })();
          }
          if (previewUrl.value) {
            URL.revokeObjectURL(previewUrl.value);
            previewUrl.value = null;
          }
          // Clean up audio cover
          if (audioCoverUrl.value) {
            URL.revokeObjectURL(audioCoverUrl.value);
            audioCoverUrl.value = null;
          }
          hasAudioCover.value = false;
          textContent.value = "";
          markdownContent.value = "";
        }
      },
      { immediate: true },
    );

    // Watch for markdown content to be set
    watch(
      () => [props.show, markdownContent.value, markdownContentRef.value],
      async ([show, html, htmlRef]) => {
        if (show && html && htmlRef) {
          await nextTick();
          if (window.vaultHTMLPolicy) {
            htmlRef.innerHTML = window.vaultHTMLPolicy.createHTML(html);
          } else {
            htmlRef.innerHTML = html;
          }
        }
      },
    );

    // Watch for default icon to be set
    watch(
      () => [props.show, defaultFileIcon.value, defaultIconRef.value],
      async ([show, icon, iconRef]) => {
        if (show && icon && iconRef) {
          await nextTick();
          if (window.vaultHTMLPolicy) {
            iconRef.innerHTML = window.vaultHTMLPolicy.createHTML(icon);
          } else {
            iconRef.innerHTML = icon;
          }
        }
      },
    );

    return {
      loading,
      error,
      previewUrl,
      textContent,
      markdownContent,
      imageLoading,
      isImage,
      isVideo,
      isAudio,
      isMarkdown,
      isText,
      defaultFileIcon,
      markdownContentRef,
      defaultIconRef,
      audioElement,
      isPlaying,
      currentTime,
      duration,
      progress,
      volume,
      audioCoverUrl,
      hasAudioCover,
      formattedCurrentTime,
      formattedDuration,
      loadPreview,
      close,
      download,
      onImageLoad,
      togglePlay,
      updateProgress,
      seekAudio,
      updateVolume,
      onLoadedMetadata,
      seekBackward,
      seekForward,
      seekAudioByClick,
      startSeeking,
      updateProgressHover,
      hideProgressHover,
      videoElement,
      isVideoPlaying,
      videoCurrentTime,
      videoDuration,
      videoProgress,
      formattedVideoCurrentTime,
      formattedVideoDuration,
      toggleVideoPlay,
      updateVideoProgress,
      onVideoLoadedMetadata,
      seekVideoBackward,
      seekVideoForward,
      seekVideoByClick,
      startVideoSeeking,
      showVideoControls,
      hideVideoControls,
      showControls,
      videoContainer,
      isFullscreen,
      toggleFullscreen,
      isZip,
      zipFiles,
      zipLoading,
      unzipping,
      zipFileCount,
      zipFolderCount,
      formatFileSize,
      handleUnzip,
      getIcon,
      toggleFolder,
      isFolderExpanded,
    };
  },
};
</script>

<style scoped>
.file-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000;
  padding: 2rem;
}

.file-preview-modal {
  width: 100%;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 2rem;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.preview-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary, #f1f5f9);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.preview-content {
  flex: 1;
  overflow: visible;
  padding: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  background: transparent;
}

.image-preview {
  position: relative;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: var(--radius-md, 8px);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  color: white;
}

.video-preview {
  width: 100%;
  max-width: 900px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.video-container {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
  background: var(--bg-secondary, #141b2d);
}

.video-player {
  width: 100%;
  max-height: 70vh;
  display: block;
  border-radius: var(--radius-lg, 12px);
}

.video-player-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  padding-bottom: 1.5rem;
  background: linear-gradient(
    to top,
    rgba(0, 0, 0, 0.8) 0%,
    rgba(0, 0, 0, 0.6) 50%,
    transparent 100%
  );
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom-left-radius: var(--radius-lg, 12px);
  border-bottom-right-radius: var(--radius-lg, 12px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.video-player-controls--visible {
  opacity: 1;
  pointer-events: all;
}

.video-player-controls__progress {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
}

.video-player-controls__bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 1rem;
}

.video-player-controls__left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.video-player-controls__song-name {
  font-weight: 600;
  font-size: 0.875rem;
  margin: 0;
  color: var(--text-primary, #f1f5f9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  text-align: right;
}

.video-player-controls__time {
  font-size: 0.625rem;
  color: var(--text-secondary, #9ca3af);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.video-player-controls__progress-bar {
  width: 100%;
  height: 5px;
  position: relative;
  display: block;
  background-color: rgba(111, 111, 111, 0.9);
  margin: 0 0.3125rem;
  cursor: pointer;
  border-radius: 10px;
  user-select: none;
  -webkit-user-select: none;
}

.video-player-controls__progress-filled {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #38bdf8 0%, #8b5cf6 100%);
  border-radius: 10px;
  transition: width 0.1s linear;
}

.video-player-controls__progress-thumb {
  width: 10px;
  height: 10px;
  position: absolute;
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  opacity: 0;
  left: 0;
  top: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  transition: opacity 0.2s ease;
  pointer-events: none;
}

.video-player-controls--visible .video-player-controls__progress-thumb,
.video-player-controls__progress-bar.seeking
  .video-player-controls__progress-thumb,
.video-player-controls__progress-bar:active
  .video-player-controls__progress-thumb {
  opacity: 1;
}

.video-player-controls__control-btn {
  fill: var(--text-secondary, #9ca3af);
  border-radius: 50%;
  width: 14px;
  height: 14px;
  cursor: pointer;
  transition: fill 0.2s ease;
  flex-shrink: 0;
  padding: 0;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-player-controls__control-btn svg {
  width: 100%;
  height: 100%;
  display: block;
}

.video-player-controls__control-btn:hover {
  fill: #38bdf8;
}

.video-player-controls__control-btn--play {
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  fill: var(--text-primary, #f1f5f9);
  padding: 2px;
  width: 18px;
  height: 18px;
  transition:
    filter 0.2s ease,
    opacity 0.2s ease;
}

.video-player-controls__control-btn--play:hover {
  filter: brightness(0.7);
  opacity: 0.9;
}

.video-player-controls__control-btn--playing {
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  fill: var(--text-primary, #f1f5f9);
}

.video-player-controls__control-btn--playing:hover {
  filter: brightness(0.7);
  opacity: 0.9;
}

.video-player-controls__control-btn--fullscreen {
  margin-left: auto;
  width: 16px;
  height: 16px;
  padding: 0;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-player-controls__control-btn--fullscreen svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* Audio Player Styles */
.audio-preview {
  width: 100%;
  max-width: 600px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.audio-player {
  width: 100%;
  max-width: 100%;
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.65);
  border-radius: 1.25rem;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.audio-player__artwork {
  width: 70px;
  height: 70px;
  flex-shrink: 0;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary, #d1d5db);
}

.audio-player__artwork svg {
  width: 32px;
  height: 32px;
}

.audio-player__artwork-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0.5rem;
}

.audio-player__container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  min-width: 0;
}

.audio-player__song-name {
  font-weight: 600;
  font-size: 0.875rem;
  margin: 0;
  margin-top: 0;
  color: var(--text-primary, #f1f5f9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

.audio-player__progress {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.audio-player__time {
  font-size: 0.625rem;
  color: var(--text-secondary, #9ca3af);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.audio-player__progress-bar {
  width: 100%;
  height: 5px;
  position: relative;
  display: block;
  background-color: rgba(111, 111, 111, 0.9);
  margin: 0 0.3125rem;
  cursor: pointer;
  border-radius: 10px;
  user-select: none;
  -webkit-user-select: none;
}

.audio-player__progress-filled {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #38bdf8 0%, #8b5cf6 100%);
  border-radius: 10px;
  transition: width 0.1s linear;
}

.audio-player__progress-thumb {
  width: 10px;
  height: 10px;
  position: absolute;
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  opacity: 0;
  left: 0;
  top: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  transition: opacity 0.2s ease;
  pointer-events: none;
}

.audio-player:hover .audio-player__progress-thumb,
.audio-player__progress-bar.seeking .audio-player__progress-thumb,
.audio-player__progress-bar:active .audio-player__progress-thumb {
  opacity: 1;
}

.audio-player__controls {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 0.5rem;
  gap: 0.5rem;
}

.audio-player__control-btn {
  fill: var(--text-secondary, #9ca3af);
  border-radius: 50%;
  width: 14px;
  height: 14px;
  cursor: pointer;
  transition: fill 0.2s ease;
  flex-shrink: 0;
}

.audio-player__control-btn:hover {
  fill: #38bdf8;
}

.audio-player__control-btn--play {
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  fill: var(--text-primary, #f1f5f9);
  padding: 2px;
  width: 18px;
  height: 18px;
  transition:
    filter 0.2s ease,
    opacity 0.2s ease;
}

.audio-player__control-btn--play:hover {
  filter: brightness(0.7);
  opacity: 0.9;
}

.audio-player__control-btn--playing {
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  fill: var(--text-primary, #f1f5f9);
}

.audio-player__control-btn--playing:hover {
  filter: brightness(0.7);
  opacity: 0.9;
}

/* Hidden audio element */
.audio-preview audio {
  display: none;
}

.text-preview {
  width: 100%;
  max-width: 900px;
  max-height: 70vh;
  overflow: auto;
}

.text-content {
  margin: 0;
  padding: 1rem;
  background: var(--bg-secondary, #141b2d);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #f1f5f9);
  font-family: "Courier New", monospace;
  font-size: 0.9rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.markdown-preview {
  width: 100%;
  max-width: 900px;
  max-height: 70vh;
  overflow: auto;
}

.markdown-content {
  padding: 2rem;
  background: var(--bg-secondary, #141b2d);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #f1f5f9);
  line-height: 1.8;
  font-size: 1rem;
  overflow: visible;
}

.markdown-content :deep(h1) {
  font-size: 2rem;
  font-weight: 700;
  margin: 1.5rem 0 1rem 0;
  color: var(--text-primary, #f1f5f9);
  border-bottom: 2px solid var(--border-color, rgba(148, 163, 184, 0.2));
  padding-bottom: 0.5rem;
}

.markdown-content :deep(h2) {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 1.25rem 0 0.75rem 0;
  color: var(--text-primary, #f1f5f9);
}

.markdown-content :deep(h3) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 1rem 0 0.5rem 0;
  color: var(--text-primary, #f1f5f9);
}

.markdown-content :deep(p) {
  margin: 1rem 0;
  color: var(--text-secondary, #cbd5e1);
}

.markdown-content :deep(strong) {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(code) {
  background: rgba(0, 0, 0, 0.3);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: "Courier New", monospace;
  font-size: 0.9em;
  color: var(--accent-blue, #38bdf8);
}

.markdown-content :deep(pre) {
  background: rgba(0, 0, 0, 0.4);
  padding: 1rem;
  border-radius: var(--radius-md, 8px);
  overflow-x: auto;
  margin: 1rem 0;
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--text-primary, #f1f5f9);
  font-size: 0.9rem;
  line-height: 1.6;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 1rem 0;
  padding-left: 2rem;
}

.markdown-content :deep(li) {
  margin: 0.5rem 0;
  color: var(--text-secondary, #cbd5e1);
}

.markdown-content :deep(a) {
  color: var(--accent-blue, #38bdf8);
  text-decoration: none;
  border-bottom: 1px solid var(--accent-blue, #38bdf8);
  transition: opacity 0.2s;
}

.markdown-content :deep(a:hover) {
  opacity: 0.8;
}

.markdown-content :deep(img.markdown-image) {
  max-width: 100%;
  height: auto;
  vertical-align: middle;
  display: inline-block;
  margin: 0 2px;
}

.unsupported-preview {
  text-align: center;
  padding: 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.unsupported-icon {
  width: 64px;
  height: 64px;
  color: var(--text-muted, #94a3b8);
  opacity: 0.6;
  margin-bottom: 0.5rem;
}

.unsupported-preview p {
  margin: 0.5rem 0;
  color: var(--text-secondary, #cbd5e1);
}

.mime-type {
  font-family: monospace;
  font-size: 0.9rem;
  color: var(--text-muted, #94a3b8);
}

.loading {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary, #cbd5e1);
}

.error-message {
  padding: 1.5rem;
  text-align: center;
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md, 8px);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #cbd5e1);
  font-size: 1.5rem;
  padding: 0.5rem;
  line-height: 1;
}

.btn-icon:hover {
  color: var(--text-primary, #f1f5f9);
}

/* ZIP Preview Styles */
.zip-preview {
  width: 100%;
  max-width: 900px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
}

.zip-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.zip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  margin-bottom: 1rem;
}

.zip-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.zip-info {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-secondary, #cbd5e1);
}

.zip-file-list {
  flex: 1;
  overflow-y: auto;
  max-height: calc(70vh - 100px);
}

.zip-file-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md, 8px);
  margin-bottom: 0.25rem;
  background: rgba(148, 163, 184, 0.03);
  transition: background 0.2s ease;
  min-height: 40px;
}

.zip-file-item:hover {
  background: rgba(148, 163, 184, 0.08);
}

.zip-file-item.zip-folder-item {
  background: rgba(148, 163, 184, 0.05);
}

.zip-file-item.zip-folder-item:hover {
  background: rgba(148, 163, 184, 0.12);
}

.zip-file-item.zip-clickable {
  cursor: pointer;
  user-select: none;
}

.zip-file-item.zip-clickable:hover {
  background: rgba(148, 163, 184, 0.15);
}

.zip-expand-icon {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #cbd5e1);
  transition:
    transform 0.2s ease,
    color 0.2s ease;
}

.zip-expand-placeholder {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
}

.zip-file-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  color: var(--text-secondary, #cbd5e1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.zip-file-icon svg {
  width: 100%;
  height: 100%;
}

.zip-folder-item .zip-file-icon {
  color: var(--accent-blue, #38bdf8);
  opacity: 0.9;
}

.zip-file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.zip-file-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary, #f1f5f9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.zip-folder-item .zip-file-name {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.zip-file-path {
  font-size: 0.75rem;
  color: var(--text-secondary, #cbd5e1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.8;
}

.zip-file-size {
  flex-shrink: 0;
  font-size: 0.8125rem;
  color: var(--text-secondary, #cbd5e1);
  font-variant-numeric: tabular-nums;
  min-width: 60px;
  text-align: right;
}

.zip-empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary, #cbd5e1);
}

.zip-empty p {
  margin: 0;
  font-size: 0.875rem;
}

.btn-primary {
  background: linear-gradient(135deg, #38bdf8 0%, #8b5cf6 100%);
  color: var(--text-primary, #f1f5f9);
  border: none;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-md, 8px);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}
</style>
