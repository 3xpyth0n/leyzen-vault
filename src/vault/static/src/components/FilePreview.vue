<template>
  <div v-if="show" class="file-preview-overlay" @click="close">
    <div class="file-preview-modal glass glass-card" @click.stop>
      <div class="preview-header">
        <h2>{{ fileName }}</h2>
        <div class="preview-actions">
          <button @click="download" class="btn btn-secondary">Download</button>
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
  emits: ["close", "download"],
  setup(props, { emit }) {
    // Watch for sidebar state changes to adjust padding
    const updatePadding = () => {
      const sidebar = document.querySelector(".sidebar");
      const overlay = document.querySelector(".file-preview-overlay");
      if (overlay && sidebar) {
        // Check if mobile mode is active
        const isMobileMode = document.body.classList.contains("mobile-mode");
        if (isMobileMode) {
          // In mobile mode, don't account for sidebar
          overlay.style.paddingLeft = "2rem";
        } else {
          // In desktop mode, account for sidebar
          const isCollapsed = sidebar.classList.contains("collapsed");
          const padding = isCollapsed
            ? "calc(2rem + 70px)"
            : "calc(2rem + 250px)";
          overlay.style.paddingLeft = padding;
        }
      }
    };

    // Set up observer for sidebar changes when component is mounted
    let sidebarObserver = null;
    let resizeHandler = null;
    let mobileModeHandler = null;

    if (typeof window !== "undefined") {
      watch(
        () => props.show,
        (isShowing) => {
          if (isShowing) {
            // Wait for DOM to be ready, then update padding
            // Use multiple nextTick to ensure overlay is in DOM
            nextTick(() => {
              nextTick(() => {
                updatePadding();
                // Set up observer for sidebar changes
                const sidebar = document.querySelector(".sidebar");
                if (sidebar && window.MutationObserver) {
                  sidebarObserver = new MutationObserver(updatePadding);
                  sidebarObserver.observe(sidebar, {
                    attributes: true,
                    attributeFilter: ["class"],
                  });
                }
                // Also listen for resize events
                resizeHandler = updatePadding;
                window.addEventListener("resize", resizeHandler);

                // Listen for mobile mode changes
                mobileModeHandler = () => updatePadding();
                window.addEventListener(
                  "mobile-mode-changed",
                  mobileModeHandler,
                );
              });
            });
          } else {
            // Clean up observer when preview is closed
            if (sidebarObserver) {
              sidebarObserver.disconnect();
              sidebarObserver = null;
            }
            if (resizeHandler) {
              window.removeEventListener("resize", resizeHandler);
              resizeHandler = null;
            }
            if (mobileModeHandler) {
              window.removeEventListener(
                "mobile-mode-changed",
                mobileModeHandler,
              );
              mobileModeHandler = null;
            }
          }
        },
        { immediate: true },
      );
    }
    const loading = ref(false);
    const error = ref(null);
    const previewUrl = ref(null);
    const textContent = ref("");
    const markdownContent = ref("");
    const imageLoading = ref(false);
    const markdownContentRef = ref(null);
    const defaultIconRef = ref(null);

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
        if (isImage.value || isVideo.value || isAudio.value) {
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
        console.warn("Failed to extract audio cover:", err);
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
      } catch (error) {
        console.error("Error toggling fullscreen:", error);
      }
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
              } catch (error) {
                console.error("Error exiting fullscreen:", error);
              }
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
  z-index: 10000;
  padding: 2rem;
  /* Default padding - will be adjusted dynamically based on sidebar state */
  /* Start with collapsed state (70px) as default, will be updated on mount */
  padding-left: calc(2rem + 70px);
  transition: padding-left 0.3s ease;
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .file-preview-overlay {
  padding-left: 2rem !important;
  padding-right: 2rem !important;
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
</style>
