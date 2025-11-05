/** @file security.js - Security dashboard functionality */

let statsData = null;

// Escape HTML to prevent XSS attacks
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Format file size
function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

// Format date
function formatDate(dateString) {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

// Load statistics
async function loadStats() {
  try {
    const response = await fetch("/security/api/stats");
    if (!response.ok) throw new Error("Failed to fetch stats");

    const data = await response.json();
    statsData = data;

    // Update storage stats
    document.getElementById("stat-total-files").textContent =
      data.storage.total_files;
    document.getElementById("stat-total-size").textContent = formatFileSize(
      data.storage.total_size,
    );
    document.getElementById("stat-encrypted-size").textContent = formatFileSize(
      data.storage.total_encrypted_size,
    );
    document.getElementById("stat-avg-size").textContent = formatFileSize(
      data.storage.average_size,
    );

    // Update activity stats
    document.getElementById("stat-total-actions").textContent =
      data.activity.recent_actions;
    document.getElementById("stat-successful").textContent =
      data.activity.successful_actions;
    document.getElementById("stat-failed").textContent =
      data.activity.failed_actions;

    // Update activity breakdown
    renderActivityBreakdown(data.activity.by_action);

    // Update audit logs
    renderAuditLogs(data.recent_logs);
  } catch (error) {
    console.error("Error loading stats:", error);
    if (window.Notifications) {
      window.Notifications.error("Failed to load security statistics");
    }
  }
}

// Render activity breakdown
function renderActivityBreakdown(byAction) {
  const container = document.getElementById("activity-breakdown");
  if (!container) return;

  if (Object.keys(byAction).length === 0) {
    container.innerHTML = '<div class="files-loading">No recent activity</div>';
    return;
  }

  const actionLabels = {
    upload: "Uploads",
    download: "Downloads",
    delete: "Deletions",
    share: "Shares",
    access_denied: "Access Denied",
  };

  container.innerHTML = Object.entries(byAction)
    .map(([action, count]) => {
      // Escape user data to prevent XSS attacks
      const escapedAction = escapeHtml(action);
      const label =
        actionLabels[action] ||
        escapedAction.charAt(0).toUpperCase() + escapedAction.slice(1);
      return `
        <div class="activity-item">
          <span class="activity-label">${label}</span>
          <span class="activity-count">${count}</span>
        </div>
      `;
    })
    .join("");
}

// Render audit logs
function renderAuditLogs(logs) {
  const container = document.getElementById("audit-logs");
  if (!container) return;

  if (logs.length === 0) {
    container.innerHTML = '<div class="files-loading">No audit logs</div>';
    return;
  }

  const actionIcons = {
    upload: "⬆️",
    download: "⬇️",
    delete: "🗑️",
    share: "🔗",
    access_denied: "🚫",
  };

  container.innerHTML = logs
    .map((log) => {
      const icon = actionIcons[log.action] || "📋";
      const successClass = log.success ? "log-success" : "log-error";
      const successText = log.success ? "✓" : "✗";

      // Escape user data to prevent XSS attacks
      const escapedAction = escapeHtml(log.action);
      const escapedIp = escapeHtml(log.user_ip);
      const escapedFileId = log.file_id
        ? escapeHtml(log.file_id.substring(0, 8)) + "..."
        : "";
      const escapedDetails =
        Object.keys(log.details).length > 0
          ? escapeHtml(JSON.stringify(log.details))
          : "";

      return `
        <div class="audit-log-item ${successClass}">
          <div class="log-icon">${icon}</div>
          <div class="log-content">
            <div class="log-header">
              <span class="log-action">${escapedAction}</span>
              <span class="log-status">${successText}</span>
              <span class="log-time">${formatDate(log.timestamp)}</span>
            </div>
            <div class="log-details">
              <span class="log-ip">IP: ${escapedIp}</span>
              ${escapedFileId ? `<span class="log-file-id">File: ${escapedFileId}</span>` : ""}
            </div>
            ${escapedDetails ? `<div class="log-extra">${escapedDetails}</div>` : ""}
          </div>
        </div>
      `;
    })
    .join("");
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  loadStats();

  const refreshBtn = document.getElementById("refresh-logs-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadStats();
      if (window.Notifications) {
        window.Notifications.info("Statistics refreshed");
      }
    });
  }
});
