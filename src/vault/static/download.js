/** @file download.js - File download and decryption handling for Leyzen Vault */

async function downloadFile(fileId, key, linkToken = null) {
  if (!fileId || !key) {
    throw new Error("File ID and key are required");
  }

  const statusEl = document.getElementById("download-status");
  if (statusEl) {
    statusEl.className = "status info";
    statusEl.textContent = "Downloading encrypted file...";
    statusEl.classList.remove("hidden");
  }

  let downloadUrl = `/api/files/${fileId}`;
  if (linkToken) {
    downloadUrl += `?token=${encodeURIComponent(linkToken)}`;
  }

  // Download encrypted file
  const response = await fetch(downloadUrl);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("File not found");
    }
    if (response.status === 403) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || "Access denied");
    }
    throw new Error("Download failed");
  }

  const encryptedBlob = await response.blob();
  const encryptedArrayBuffer = await encryptedBlob.arrayBuffer();
  const encryptedData = new Uint8Array(encryptedArrayBuffer);

  if (statusEl) {
    statusEl.textContent = "Decrypting...";
  }

  // Decrypt the file client-side
  const decryptedBuffer = await VaultCrypto.decryptFile(encryptedData, key);

  // Get file metadata to determine original filename
  let originalName = "decrypted-file";
  try {
    const metadataResponse = await fetch(`/api/files/${fileId}/metadata`);
    if (metadataResponse.ok) {
      const metadata = await metadataResponse.json();
      originalName = metadata.original_name;
    }
  } catch (e) {}

  if (statusEl) {
    statusEl.className = "status success";
    statusEl.textContent = "Download successful!";
  }

  // Create download link
  const decryptedBlob = new Blob([decryptedBuffer]);
  const url = URL.createObjectURL(decryptedBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = originalName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function handleShareDownload() {
  const pathMatch = window.location.pathname.match(/\/share\/([^\/]+)/);
  const linkToken = pathMatch
    ? pathMatch[1]
    : new URLSearchParams(window.location.search).get("token");

  let fileId = null;
  let key = null;

  if (linkToken) {
    // New share link system with tokens
    try {
      const shareInfoResponse = await fetch(`/api/shares/${linkToken}`);
      if (!shareInfoResponse.ok) {
        showError("Invalid or expired share link.");
        return;
      }

      const shareInfo = await shareInfoResponse.json();
      if (!shareInfo.is_valid) {
        showError(shareInfo.error || "Share link is no longer valid.");
        return;
      }

      fileId = shareInfo.file_id;

      // For token-based shares, we need to get the key from the URL fragment
      // The key should still be in the URL fragment for E2EE
      const { fileId: urlFileId, key: urlKey } = VaultCrypto.parseShareUrl();
      if (urlFileId === fileId && urlKey) {
        key = urlKey;
      } else {
        showError("Decryption key missing from URL.");
        return;
      }
    } catch (error) {
      showError("Failed to validate share link.");
      return;
    }
  } else {
    // Alternative share URL format with key in fragment
    const parsed = VaultCrypto.parseShareUrl();
    fileId = parsed.fileId;
    key = parsed.key;
  }

  if (!fileId || !key) {
    showError("Invalid share URL. Please check the URL and try again.");
    return;
  }

  const downloadButton = document.getElementById("download-button");
  const downloadStatus = document.getElementById("download-status");

  try {
    if (downloadButton) downloadButton.disabled = true;
    if (downloadStatus) {
      downloadStatus.textContent = "Downloading and decrypting...";
      downloadStatus.className = "status info";
      downloadStatus.classList.remove("hidden");
    }

    await downloadFile(fileId, key, linkToken);

    if (downloadStatus) {
      downloadStatus.textContent = "Download successful!";
      downloadStatus.className = "status success";
    }
  } catch (error) {
    showError(`Download error: ${error.message}`);
  } finally {
    if (downloadButton) downloadButton.disabled = false;
  }
}

function showError(message) {
  const downloadStatus = document.getElementById("download-status");
  if (downloadStatus) {
    downloadStatus.textContent = message;
    downloadStatus.className = "status error";
    downloadStatus.classList.remove("hidden");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDownload);
} else {
  initDownload();
}

function initDownload() {
  const downloadButton = document.getElementById("download-button");

  const linkToken = window.SHARE_LINK_TOKEN || null;
  const fileId = window.SHARE_FILE_ID || null;

  if (linkToken && fileId) {
    // New token-based share link
    if (downloadButton) {
      downloadButton.addEventListener("click", handleShareDownload);
    }
  } else {
    // Alternative share URL format parsing
    const parsed = VaultCrypto.parseShareUrl();
    if (!parsed.fileId || !parsed.key) {
      showError("Invalid share URL. Please check the URL and try again.");
      return;
    }

    if (downloadButton) {
      downloadButton.addEventListener("click", handleShareDownload);
    }
  }
}
