/** @file upload-enhanced.js - Advanced upload system with queue, per-file progress, and resume */

class UploadManager {
  constructor() {
    this.uploadQueue = [];
    this.activeUploads = new Map();
    this.completedUploads = [];
    this.failedUploads = [];
    this.chunkSize = 5 * 1024 * 1024; // 5MB chunks
    this.maxConcurrentUploads = 3;
    this.uploading = false;
    this.uploadResumeData = new Map(); // Store resume data for failed uploads

    this.init();
  }

  init() {
    // Load resume data from localStorage
    this.loadResumeData();

    // Create upload queue UI
    this.createUploadQueueUI();

    // Setup file input handler
    this.setupFileInput();

    // Setup drag & drop
    this.setupDragDrop();
  }

  /**
   * Create upload queue UI
   */
  createUploadQueueUI() {
    // Check if queue UI already exists
    if (document.getElementById("upload-queue-container")) return;

    const queueHTML = `
            <div id="upload-queue-container" class="upload-queue-container hidden">
                <div class="upload-queue-header">
                    <h3>Upload Queue</h3>
                    <button id="upload-queue-close" class="upload-queue-close" aria-label="Close queue">×</button>
                </div>
                <div class="upload-queue-list" id="upload-queue-list"></div>
                <div class="upload-queue-actions">
                    <button id="upload-queue-pause-all" class="btn btn-secondary btn-small">Pause All</button>
                    <button id="upload-queue-resume-all" class="btn btn-secondary btn-small">Resume All</button>
                    <button id="upload-queue-clear-completed" class="btn btn-secondary btn-small">Clear Completed</button>
                </div>
            </div>
        `;

    if (window.vaultHTMLPolicy) {
      try {
        document.body.insertAdjacentHTML(
          "beforeend",
          window.vaultHTMLPolicy.createHTML(queueHTML),
        );
      } catch (e) {
        document.body.insertAdjacentHTML("beforeend", queueHTML);
      }
    } else {
      document.body.insertAdjacentHTML("beforeend", queueHTML);
    }

    // Setup event listeners
    const closeBtn = document.getElementById("upload-queue-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.hideQueue());
    }

    const pauseAllBtn = document.getElementById("upload-queue-pause-all");
    if (pauseAllBtn) {
      pauseAllBtn.addEventListener("click", () => this.pauseAll());
    }

    const resumeAllBtn = document.getElementById("upload-queue-resume-all");
    if (resumeAllBtn) {
      resumeAllBtn.addEventListener("click", () => this.resumeAll());
    }

    const clearCompletedBtn = document.getElementById(
      "upload-queue-clear-completed",
    );
    if (clearCompletedBtn) {
      clearCompletedBtn.addEventListener("click", () => this.clearCompleted());
    }
  }

  /**
   * Setup file input handler
   */
  setupFileInput() {
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
          this.queueFiles(files);
          // Reset input
          fileInput.value = "";
        }
      });
    }
  }

  /**
   * Setup drag & drop
   */
  setupDragDrop() {
    const uploadArea = document.getElementById("upload-area");
    if (!uploadArea) return;

    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        this.queueFiles(files);
      }
    });
  }

  /**
   * Add files to upload queue
   */
  async queueFiles(files, folderId = null) {
    const currentFolderId = window.Folders
      ? window.Folders.getCurrentFolderId()
      : null;
    const targetFolderId = folderId || currentFolderId;

    for (const file of files) {
      const uploadId = `${file.name}-${file.size}-${Date.now()}`;
      const upload = {
        id: uploadId,
        file,
        folderId: targetFolderId,
        status: "pending",
        progress: 0,
        speed: 0,
        timeRemaining: null,
        error: null,
        xhr: null,
        retryCount: 0,
        maxRetries: 3,
        paused: false,
        uploadedBytes: 0,
        totalBytes: file.size,
      };

      this.uploadQueue.push(upload);
    }

    this.showQueue();
    this.updateQueueUI();
    this.processQueue();
  }

  /**
   * Process upload queue
   */
  async processQueue() {
    if (this.uploading) return;

    // Filter pending uploads
    const pendingUploads = this.uploadQueue.filter(
      (u) => u.status === "pending" && !u.paused,
    );

    if (pendingUploads.length === 0) {
      // Check if all uploads are complete
      const allCompleted = this.uploadQueue.every(
        (u) => u.status === "completed" || u.status === "error" || u.paused,
      );

      if (allCompleted && this.activeUploads.size === 0) {
        this.uploading = false;
        return;
      }
    }

    this.uploading = true;

    // Start uploads up to max concurrent
    while (
      pendingUploads.length > 0 &&
      this.activeUploads.size < this.maxConcurrentUploads
    ) {
      const upload = pendingUploads.shift();
      if (upload && !upload.paused) {
        this.startUpload(upload);
      }
    }
  }

  /**
   * Start upload for a file
   */
  async startUpload(upload) {
    upload.status = "uploading";
    upload.paused = false;
    this.activeUploads.set(upload.id, upload);

    this.updateQueueUI();

    try {
      // Check if we have resume data
      const resumeData = this.uploadResumeData.get(upload.id);

      if (upload.file.size > this.chunkSize && resumeData) {
        await this.uploadChunkedWithResume(upload, resumeData);
      } else if (upload.file.size > this.chunkSize) {
        await this.uploadChunked(upload);
      } else {
        await this.uploadSingle(upload);
      }

      upload.status = "completed";
      upload.progress = 100;
      this.completedUploads.push(upload);

      // Remove from resume data
      this.uploadResumeData.delete(upload.id);
      this.saveResumeData();

      this.activeUploads.delete(upload.id);
      this.updateQueueUI();

      if (window.Notifications) {
        window.Notifications.success(
          `File "${upload.file.name}" uploaded successfully`,
        );
      }

      // Reload files list
      if (window.loadFiles) {
        await window.loadFiles();
      }
    } catch (error) {
      upload.status = "error";
      upload.error = error.message;

      if (upload.retryCount < upload.maxRetries) {
        upload.retryCount++;
        upload.status = "pending";
        upload.error = null;

        if (window.Notifications) {
          window.Notifications.info(
            `Retrying upload "${upload.file.name}" (${upload.retryCount}/${upload.maxRetries})`,
          );
        }

        // Retry after delay
        setTimeout(() => {
          if (!upload.paused) {
            this.processQueue();
          }
        }, 2000 * upload.retryCount); // Exponential backoff
      } else {
        this.failedUploads.push(upload);

        if (window.Notifications) {
          window.Notifications.error(
            `Upload failed: "${upload.file.name}" - ${error.message}`,
          );
        }
      }

      this.activeUploads.delete(upload.id);
      this.updateQueueUI();
    }

    // Continue processing queue
    this.processQueue();
  }

  /**
   * Upload single file (small files)
   */
  async uploadSingle(upload) {
    const { encryptedData, key } = await VaultCrypto.encryptFile(upload.file);

    const formData = new FormData();
    const encryptedBlob = new Blob([encryptedData], {
      type: "application/octet-stream",
    });
    formData.append("file", encryptedBlob, upload.file.name);
    formData.append("original_size", upload.file.size.toString());

    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");
    if (csrfToken) {
      formData.append("csrf_token", csrfToken);
    }

    if (upload.folderId) {
      formData.append("folder_id", upload.folderId);
    }

    const mimeType = upload.file.type || "application/octet-stream";
    formData.append("mime_type", mimeType);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      upload.xhr = xhr;

      const startTime = Date.now();
      let lastLoaded = 0;
      let lastTime = startTime;

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && !upload.paused) {
          upload.progress = Math.round((e.loaded / e.total) * 100);
          upload.uploadedBytes = e.loaded;

          // Calculate speed
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000;
          const loadedDiff = e.loaded - lastLoaded;

          if (timeDiff > 0) {
            upload.speed = loadedDiff / timeDiff;
            const remaining = e.total - e.loaded;
            upload.timeRemaining = remaining / upload.speed;
          }

          lastLoaded = e.loaded;
          lastTime = currentTime;

          this.updateQueueUI();
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            if (window.storeFileKey && response.file_id) {
              window.storeFileKey(response.file_id, key);
            }
            resolve(response);
          } catch (e) {
            reject(new Error("Invalid response"));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.error || "Upload failed"));
          } catch (e) {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () => reject(new Error("Network error")));
      xhr.addEventListener("abort", () =>
        reject(new Error("Upload cancelled")),
      );

      xhr.open("POST", "/api/files");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
      }
      xhr.send(formData);
    });
  }

  /**
   * Upload file in chunks (large files)
   */
  async uploadChunked(upload) {
    // For now, encrypt and upload as single file
    // Future: implement actual chunked upload with resume support
    return this.uploadSingle(upload);
  }

  /**
   * Upload file with resume support
   */
  async uploadChunkedWithResume(upload, resumeData) {
    // Future: implement resume from resumeData
    return this.uploadSingle(upload);
  }

  /**
   * Pause upload
   */
  pauseUpload(uploadId) {
    const upload = this.uploadQueue.find((u) => u.id === uploadId);
    if (!upload) return;

    upload.paused = true;
    if (upload.xhr) {
      upload.xhr.abort();
    }

    if (this.activeUploads.has(uploadId)) {
      this.activeUploads.delete(uploadId);

      // Save resume data
      if (upload.uploadedBytes > 0) {
        this.uploadResumeData.set(uploadId, {
          uploadedBytes: upload.uploadedBytes,
          timestamp: Date.now(),
        });
        this.saveResumeData();
      }
    }

    upload.status = "paused";
    this.updateQueueUI();
    this.processQueue();
  }

  /**
   * Resume upload
   */
  resumeUpload(uploadId) {
    const upload = this.uploadQueue.find((u) => u.id === uploadId);
    if (!upload) return;

    upload.paused = false;
    upload.status = "pending";
    this.updateQueueUI();
    this.processQueue();
  }

  /**
   * Cancel upload
   */
  cancelUpload(uploadId) {
    const upload = this.uploadQueue.find((u) => u.id === uploadId);
    if (!upload) return;

    if (upload.xhr) {
      upload.xhr.abort();
    }

    this.uploadQueue = this.uploadQueue.filter((u) => u.id !== uploadId);
    this.activeUploads.delete(uploadId);
    this.uploadResumeData.delete(uploadId);
    this.saveResumeData();
    this.updateQueueUI();
    this.processQueue();
  }

  /**
   * Pause all uploads
   */
  pauseAll() {
    this.uploadQueue.forEach((upload) => {
      if (upload.status === "uploading") {
        this.pauseUpload(upload.id);
      }
    });
  }

  /**
   * Resume all uploads
   */
  resumeAll() {
    this.uploadQueue.forEach((upload) => {
      if (upload.status === "paused" || upload.status === "error") {
        this.resumeUpload(upload.id);
      }
    });
  }

  /**
   * Clear completed uploads
   */
  clearCompleted() {
    this.uploadQueue = this.uploadQueue.filter((u) => u.status !== "completed");
    this.completedUploads = [];
    this.updateQueueUI();

    if (this.uploadQueue.length === 0) {
      this.hideQueue();
    }
  }

  /**
   * Update upload queue UI
   */
  updateQueueUI() {
    const queueList = document.getElementById("upload-queue-list");
    if (!queueList) return;

    // Clear and rebuild queue list
    while (queueList.firstChild) {
      queueList.removeChild(queueList.firstChild);
    }

    if (this.uploadQueue.length === 0) {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "upload-queue-empty";
      emptyDiv.textContent = "No files in queue";
      queueList.appendChild(emptyDiv);
      return;
    }

    this.uploadQueue.forEach((upload) => {
      const statusIcon = this.getStatusIcon(upload.status);
      const speedText =
        upload.speed > 0
          ? `${this.formatSpeed(upload.speed)} • ${this.formatTimeRemaining(upload.timeRemaining)}`
          : "";

      const item = document.createElement("div");
      item.className = `upload-queue-item ${upload.status}`;
      item.setAttribute("data-upload-id", upload.id);

      const iconDiv = document.createElement("div");
      iconDiv.className = "upload-queue-item-icon";
      iconDiv.textContent = statusIcon;

      const infoDiv = document.createElement("div");
      infoDiv.className = "upload-queue-item-info";

      const nameDiv = document.createElement("div");
      nameDiv.className = "upload-queue-item-name";
      nameDiv.textContent = upload.file.name;

      const detailsDiv = document.createElement("div");
      detailsDiv.className = "upload-queue-item-details";
      detailsDiv.textContent = `${this.formatFileSize(upload.file.size)}${speedText ? " • " + speedText : ""}`;

      if (upload.error) {
        const errorSpan = document.createElement("span");
        errorSpan.className = "upload-error";
        errorSpan.textContent = upload.error;
        detailsDiv.appendChild(errorSpan);
      }

      // Progress bar
      if (upload.status === "uploading" || upload.status === "completed") {
        const progressBarWrapper = document.createElement("div");
        progressBarWrapper.className = "upload-progress-bar";
        const progressFill = document.createElement("div");
        progressFill.className = "upload-progress-fill";
        progressFill.style.width = `${upload.progress}%`;
        progressBarWrapper.appendChild(progressFill);
        infoDiv.appendChild(progressBarWrapper);
      }

      infoDiv.appendChild(nameDiv);
      infoDiv.appendChild(detailsDiv);

      const actionsDiv = document.createElement("div");
      actionsDiv.className = "upload-queue-item-actions";

      if (upload.status === "uploading" || upload.status === "pending") {
        const pauseBtn = document.createElement("button");
        pauseBtn.className = "upload-action-btn";
        pauseBtn.title = "Pause";
        pauseBtn.textContent = "⏸";
        pauseBtn.onclick = () => window.uploadManager.pauseUpload(upload.id);
        actionsDiv.appendChild(pauseBtn);
      } else if (upload.status === "paused" || upload.status === "error") {
        const resumeBtn = document.createElement("button");
        resumeBtn.className = "upload-action-btn";
        resumeBtn.title = "Resume";
        resumeBtn.textContent = "▶";
        resumeBtn.onclick = () => window.uploadManager.resumeUpload(upload.id);
        actionsDiv.appendChild(resumeBtn);
      }

      const cancelBtn = document.createElement("button");
      cancelBtn.className = "upload-action-btn";
      cancelBtn.title = "Cancel";
      cancelBtn.textContent = "✕";
      cancelBtn.onclick = () => window.uploadManager.cancelUpload(upload.id);
      actionsDiv.appendChild(cancelBtn);

      item.appendChild(iconDiv);
      item.appendChild(infoDiv);
      item.appendChild(actionsDiv);
      queueList.appendChild(item);
    });

    if (this.uploadQueue.length === 0) {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "upload-queue-empty";
      emptyDiv.textContent = "No files in queue";
      queueList.appendChild(emptyDiv);
    }
  }

  /**
   * Get status icon
   */
  getStatusIcon(status) {
    switch (status) {
      case "pending":
        return "⏳";
      case "uploading":
        return "⬆️";
      case "paused":
        return "⏸";
      case "completed":
        return "✅";
      case "error":
        return "❌";
      default:
        return "📄";
    }
  }

  /**
   * Format speed
   */
  formatSpeed(bytesPerSecond) {
    if (bytesPerSecond < 1024) return `${Math.round(bytesPerSecond)} B/s`;
    if (bytesPerSecond < 1024 * 1024)
      return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
  }

  /**
   * Format time remaining
   */
  formatTimeRemaining(seconds) {
    if (!seconds || !isFinite(seconds)) return "";
    if (seconds < 60) return `${Math.round(seconds)}s remaining`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m remaining`;
    return `${Math.round(seconds / 3600)}h remaining`;
  }

  /**
   * Format file size
   */
  formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024)
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }

  /**
   * Escape HTML
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Show queue
   */
  showQueue() {
    const container = document.getElementById("upload-queue-container");
    if (container) {
      container.classList.remove("hidden");
      if (window.Animations) {
        window.Animations.fadeIn(container);
      }
    }
  }

  /**
   * Hide queue
   */
  hideQueue() {
    const container = document.getElementById("upload-queue-container");
    if (container) {
      if (window.Animations) {
        window.Animations.fadeOut(container).then(() => {
          container.classList.add("hidden");
        });
      } else {
        container.classList.add("hidden");
      }
    }
  }

  /**
   * Save resume data to localStorage
   */
  saveResumeData() {
    try {
      const data = Array.from(this.uploadResumeData.entries());
      localStorage.setItem("leyzen-upload-resume", JSON.stringify(data));
    } catch (e) {
      console.warn("Failed to save resume data:", e);
    }
  }

  /**
   * Load resume data from localStorage
   */
  loadResumeData() {
    try {
      const data = localStorage.getItem("leyzen-upload-resume");
      if (data) {
        const entries = JSON.parse(data);
        this.uploadResumeData = new Map(entries);
      }
    } catch (e) {
      console.warn("Failed to load resume data:", e);
    }
  }
}

// Initialize upload manager
let uploadManager = null;

document.addEventListener("DOMContentLoaded", () => {
  uploadManager = new UploadManager();

  // Export for use in other scripts
  if (typeof window !== "undefined") {
    window.UploadManager = UploadManager;
    window.uploadManager = uploadManager;
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.UploadManager = UploadManager;
}
