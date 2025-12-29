/** @file upload.js - File upload handling for Leyzen Vault */

async function uploadFile(file) {
  if (!file) {
    throw new Error("No file selected");
  }

  // Encrypt the file client-side
  const { encryptedData, key } = await VaultCrypto.encryptFile(file);

  // Create FormData with encrypted file
  const formData = new FormData();
  const encryptedBlob = new Blob([encryptedData], {
    type: "application/octet-stream",
  });
  formData.append("file", encryptedBlob, file.name);
  formData.append("original_size", file.size.toString());

  // Upload encrypted file
  const response = await fetch("/api/files", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ error: "Upload failed" }));
    throw new Error(error.error || "Upload failed");
  }

  const result = await response.json();
  const fileId = result.file_id;

  // Create shareable URL with key in fragment
  const shareUrl = await VaultCrypto.createShareUrl(fileId, key);

  return {
    fileId,
    shareUrl,
    originalName: file.name,
  };
}

async function handleFileUpload(event) {
  event.preventDefault();
  const fileInput = document.getElementById("file-input");
  const file = fileInput?.files[0];

  if (!file) {
    showError("Please select a file");
    return;
  }

  const uploadButton = document.getElementById("upload-button");
  const uploadStatus = document.getElementById("upload-status");

  try {
    uploadButton.disabled = true;
    uploadStatus.textContent = `Encrypting and uploading ${file.name}...`;
    uploadStatus.className = "status";

    const result = await uploadFile(file);

    uploadStatus.textContent = "Upload successful!";
    uploadStatus.className = "status success";

    const shareUrlInput = document.getElementById("share-url");
    const shareUrlContainer = document.getElementById("share-url-container");
    if (shareUrlInput && shareUrlContainer) {
      shareUrlInput.value = result.shareUrl;
      shareUrlContainer.style.display = "block";
    }

    // Reset file input
    if (fileInput) {
      fileInput.value = "";
    }
  } catch (error) {
    showError(`Upload failed: ${error.message}`);
  } finally {
    uploadButton.disabled = false;
  }
}

function showError(message) {
  const uploadStatus = document.getElementById("upload-status");
  if (uploadStatus) {
    uploadStatus.textContent = message;
    uploadStatus.className = "status error";
  }
}

function copyShareUrl() {
  const shareUrlInput = document.getElementById("share-url");
  if (shareUrlInput) {
    shareUrlInput.select();
    document.execCommand("copy");
    const copyButton = document.getElementById("copy-button");
    if (copyButton) {
      const originalText = copyButton.textContent;
      copyButton.textContent = "Copied!";
      setTimeout(() => {
        copyButton.textContent = originalText;
      }, 2000);
    }
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initUpload);
} else {
  initUpload();
}

function initUpload() {
  const uploadForm = document.getElementById("upload-form");
  const copyButton = document.getElementById("copy-button");

  if (uploadForm) {
    uploadForm.addEventListener("submit", handleFileUpload);
  }

  if (copyButton) {
    copyButton.addEventListener("click", copyShareUrl);
  }
}
