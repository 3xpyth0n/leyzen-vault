/**
 * ZIP service for creating and extracting ZIP files.
 *
 * Handles:
 * - Zipping folders (download, decrypt, zip, encrypt, upload)
 * - Extracting ZIP files (download, decrypt, extract, encrypt each file, upload)
 */

import JSZip from "jszip";
import { apiRequest, parseErrorResponse } from "./api.js";
import apiService from "./api.js";
import {
  decryptFileKey,
  encryptFileKey,
  encryptFile,
  decryptFile,
  generateFileKey,
} from "./encryption.js";
import { logger } from "../utils/logger.js";

/**
 * Zip a folder: download all files, decrypt, create ZIP, encrypt, and upload.
 *
 * @param {string} folderId - Folder ID to zip
 * @param {string} vaultspaceId - VaultSpace ID
 * @param {CryptoKey} vaultspaceKey - Decrypted VaultSpace key
 * @param {function} onProgress - Progress callback (current, total, message)
 * @param {string|null} zipFileName - Optional custom ZIP file name (without .zip extension)
 * @param {string|null} parentId - Optional parent folder ID for the ZIP file
 * @returns {Promise<string>} File ID of created ZIP file
 */
export async function zipFolder(
  folderId,
  vaultspaceId,
  vaultspaceKey,
  onProgress = null,
  zipFileName = null,
  parentId = null,
) {
  try {
    // Step 1: Get folder tree with file keys
    if (onProgress) onProgress(0, 100, "Preparing folder tree...");
    const prepareResponse = await apiRequest("/v2/files/zip/prepare", {
      method: "POST",
      body: JSON.stringify({
        folder_id: folderId,
        vaultspace_id: vaultspaceId,
      }),
    });

    if (!prepareResponse.ok) {
      const errorData = await parseErrorResponse(prepareResponse);
      throw new Error(errorData.error || "Failed to prepare folder tree");
    }

    const folderTree = await prepareResponse.json();
    const { files, folders, folder_name } = folderTree;

    if (files.length === 0 && folders.length === 0) {
      throw new Error("Folder is empty");
    }

    // Step 2: Download and decrypt all files
    const zip = new JSZip();
    const totalFiles = files.length;
    let processedFiles = 0;

    if (onProgress) {
      onProgress(0, totalFiles, `Downloading ${totalFiles} files...`);
    }

    for (const fileInfo of files) {
      try {
        // Download encrypted file
        const encryptedData = await downloadFileWithProgress(
          fileInfo.id,
          vaultspaceId,
          (loaded, total) => {
            if (onProgress) {
              const fileProgress = (loaded / total) * 100;
              const overallProgress =
                (processedFiles / totalFiles) * 100 + fileProgress / totalFiles;
              onProgress(
                overallProgress,
                totalFiles,
                `Downloading ${fileInfo.name}...`,
              );
            }
          },
        );

        // Decrypt file key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileInfo.encrypted_key,
        );

        // Decrypt file data
        // Encrypted format: IV (12 bytes) + encrypted data + tag (16 bytes)
        const encryptedArray = new Uint8Array(encryptedData);
        const iv = encryptedArray.slice(0, 12);
        const encrypted = encryptedArray.slice(12);

        const decryptedData = await decryptFile(fileKey, encrypted, iv);

        // Add to ZIP with preserved path structure
        zip.file(fileInfo.path, decryptedData);

        processedFiles++;
        if (onProgress) {
          onProgress(
            processedFiles,
            totalFiles,
            `Processed ${processedFiles}/${totalFiles} files...`,
          );
        }
      } catch (error) {
        logger.error(`Failed to process file ${fileInfo.name}:`, error);
        // Check for specific error types
        if (error.message && error.message.includes("quota")) {
          throw new Error(
            `Storage quota exceeded while processing ${fileInfo.name}. Please free up space and try again.`,
          );
        } else if (error.message && error.message.includes("network")) {
          throw new Error(
            `Network error while downloading ${fileInfo.name}. Please check your connection and try again.`,
          );
        } else if (error.message && error.message.includes("decrypt")) {
          throw new Error(
            `Failed to decrypt file ${fileInfo.name}. The file key may be missing or corrupted.`,
          );
        } else {
          throw new Error(
            `Failed to process file ${fileInfo.name}: ${
              error.message || "Unknown error"
            }`,
          );
        }
      }
    }

    // Step 3: Generate ZIP file
    if (onProgress) {
      onProgress(totalFiles, totalFiles, "Creating ZIP archive...");
    }
    const zipBlob = await zip.generateAsync(
      { type: "blob", compression: "DEFLATE" },
      (metadata) => {
        if (onProgress) {
          const zipProgress = totalFiles + (metadata.percent / 100) * 10; // Allocate 10% for ZIP creation
          onProgress(
            zipProgress,
            totalFiles + 10,
            `Creating ZIP: ${metadata.percent.toFixed(0)}%`,
          );
        }
      },
    );

    // Step 4: Encrypt ZIP file
    if (onProgress) {
      onProgress(totalFiles + 10, totalFiles + 10, "Encrypting ZIP file...");
    }

    // Generate file key for ZIP
    const zipFileKey = await generateFileKey();
    const zipFileKeyArrayBuffer = await crypto.subtle.exportKey(
      "raw",
      zipFileKey,
    );

    // Read ZIP blob as ArrayBuffer
    const zipArrayBuffer = await zipBlob.arrayBuffer();

    // Encrypt ZIP
    const { encrypted: encryptedZip, iv: zipIv } = await encryptFile(
      zipFileKey,
      zipArrayBuffer,
    );

    // Combine IV + encrypted data
    const ivArray = new Uint8Array(zipIv);
    const encryptedArray = new Uint8Array(encryptedZip);
    const combined = new Uint8Array(ivArray.length + encryptedArray.length);
    combined.set(ivArray, 0);
    combined.set(encryptedArray, ivArray.length);

    // Encrypt file key with VaultSpace key
    const encryptedZipFileKey = await encryptFileKey(vaultspaceKey, zipFileKey);

    // Step 5: Upload encrypted ZIP
    if (onProgress) {
      onProgress(totalFiles + 10, totalFiles + 10, "Uploading ZIP file...");
    }

    const finalZipFileName = zipFileName
      ? `${zipFileName}.zip`
      : `${folder_name}.zip`;
    const zipBlobForUpload = new Blob([combined], {
      type: "application/octet-stream",
    });

    const formData = new FormData();
    formData.append("file", zipBlobForUpload, finalZipFileName);
    formData.append("vaultspace_id", vaultspaceId);
    formData.append("encrypted_file_key", encryptedZipFileKey);
    formData.append("mime_type", "application/zip");
    formData.append("source_folder_id", folderId);
    if (parentId) {
      formData.append("parent_id", parentId);
    }

    try {
      // Use fetch directly instead of apiRequest to avoid Content-Type issues with FormData
      const token = localStorage.getItem("jwt_token");
      const url = `/api/v2/files`;

      const uploadResponse = await fetch(url, {
        method: "POST",
        body: formData,
        headers: {
          // Don't set Content-Type - let browser set it with boundary for FormData
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: "same-origin",
      });

      if (!uploadResponse.ok) {
        const errorData = await parseErrorResponse(uploadResponse);
        // Check for quota errors
        if (
          uploadResponse.status === 403 &&
          errorData.error &&
          errorData.error.includes("quota")
        ) {
          throw new Error(
            "Storage quota exceeded. Please free up space before creating ZIP files.",
          );
        }
        // Check for conflict errors (409)
        if (uploadResponse.status === 409) {
          const conflictError = new Error(
            errorData.error || "A file with this name already exists",
          );
          conflictError.statusCode = 409;
          conflictError.isConflict = true;
          throw conflictError;
        }
        throw new Error(errorData.error || "Failed to upload ZIP file");
      }

      const uploadData = await uploadResponse.json();
      return uploadData.file.id;
    } catch (error) {
      // Re-throw with more context if it's a network error
      if (error.message && error.message.includes("network")) {
        throw new Error(
          "Network error while uploading ZIP file. Please check your connection and try again.",
        );
      }
      throw error;
    }
  } catch (error) {
    logger.error("Failed to zip folder:", error);
    throw error;
  }
}

/**
 * Extract a ZIP file: download, decrypt, extract, encrypt each file, and upload.
 *
 * @param {string} zipFileId - ZIP file ID
 * @param {string} vaultspaceId - VaultSpace ID
 * @param {CryptoKey} vaultspaceKey - Decrypted VaultSpace key
 * @param {string|null} targetParentId - Target parent folder ID (null for root)
 * @param {function} onProgress - Progress callback (current, total, message)
 * @param {string|null} rootFolderName - Optional custom root folder name (without .zip extension)
 * @returns {Promise<string>} Folder ID of created folder (or target parent ID)
 */
export async function extractZip(
  zipFileId,
  vaultspaceId,
  vaultspaceKey,
  targetParentId = null,
  onProgress = null,
  rootFolderName = null,
) {
  try {
    // Step 1: Get ZIP file info and key
    if (onProgress) onProgress(0, 100, "Preparing ZIP extraction...");
    const prepareResponse = await apiRequest("/v2/files/zip/extract", {
      method: "POST",
      body: JSON.stringify({
        zip_file_id: zipFileId,
        vaultspace_id: vaultspaceId,
        target_parent_id: targetParentId,
      }),
    });

    if (!prepareResponse.ok) {
      const errorData = await parseErrorResponse(prepareResponse);
      throw new Error(errorData.error || "Failed to prepare ZIP extraction");
    }

    const zipInfo = await prepareResponse.json();
    const { file: zipFile, file_key: zipFileKeyData } = zipInfo;

    // Step 2: Download encrypted ZIP
    if (onProgress) {
      onProgress(10, 100, "Downloading ZIP file...");
    }
    const encryptedZipData = await downloadFileWithProgress(
      zipFileId,
      vaultspaceId,
      (loaded, total) => {
        if (onProgress) {
          const progress = 10 + (loaded / total) * 20; // 10-30%
          onProgress(progress, 100, "Downloading ZIP file...");
        }
      },
    );

    // Step 3: Decrypt ZIP file
    if (onProgress) {
      onProgress(30, 100, "Decrypting ZIP file...");
    }

    // Decrypt file key
    const zipFileKey = await decryptFileKey(
      vaultspaceKey,
      zipFileKeyData.encrypted_key,
    );

    // Decrypt ZIP data
    const encryptedArray = new Uint8Array(encryptedZipData);
    const iv = encryptedArray.slice(0, 12);
    const encrypted = encryptedArray.slice(12);

    const decryptedZipData = await decryptFile(zipFileKey, encrypted, iv);

    // Step 4: Extract ZIP
    if (onProgress) {
      onProgress(40, 100, "Extracting ZIP archive...");
    }

    let zip;
    try {
      zip = await JSZip.loadAsync(decryptedZipData);
    } catch (error) {
      logger.error("Failed to load ZIP file:", error);
      throw new Error(
        "Failed to extract ZIP file. The file may be corrupted or not a valid ZIP archive.",
      );
    }

    // Get all files from ZIP
    const zipFiles = [];
    zip.forEach((relativePath, file) => {
      if (!file.dir) {
        zipFiles.push({ path: relativePath, file: file });
      }
    });

    // Step 5: Create folder structure and upload files
    const totalFiles = zipFiles.length;
    let processedFiles = 0;

    // Create a map to track created folders
    const createdFolders = new Map(); // path -> folderId

    // Determine root folder name from ZIP file name or use provided name
    const zipFileName =
      rootFolderName || zipFile.original_name.replace(/\.zip$/i, "");
    let rootFolderId = targetParentId;

    // Always create root folder with ZIP file name (even if ZIP is empty)
    if (onProgress) {
      onProgress(50, 100, `Creating folder "${zipFileName}"...`);
    }

    try {
      const createFolderResponse = await apiRequest("/v2/files/folders", {
        method: "POST",
        body: JSON.stringify({
          vaultspace_id: vaultspaceId,
          name: zipFileName,
          parent_id: targetParentId,
        }),
      });

      if (createFolderResponse.ok) {
        const folderData = await createFolderResponse.json();
        rootFolderId = folderData.folder.id;
        createdFolders.set("", rootFolderId);
      } else {
        const errorData = await parseErrorResponse(createFolderResponse);
        // Check if it's a conflict error (409)
        if (createFolderResponse.status === 409) {
          const conflictError = new Error(
            errorData.error || "A folder with this name already exists",
          );
          conflictError.statusCode = 409;
          conflictError.isConflict = true;
          throw conflictError;
        }
        // Other errors - cannot continue without creating the folder
        throw new Error(
          errorData.error || "Failed to create folder for ZIP extraction",
        );
      }
    } catch (error) {
      // If it's a conflict error, re-throw it
      if (error.isConflict) {
        throw error;
      }
      // For other errors, log and re-throw
      logger.error("Error creating root folder:", error);
      throw error;
    }

    // Verify that root folder was created successfully
    if (rootFolderId === targetParentId) {
      throw new Error(
        "Failed to create root folder for ZIP extraction. Cannot continue.",
      );
    }

    // Process each file (only if ZIP is not empty)
    if (zipFiles.length === 0) {
      // ZIP is empty, but folder is already created, return it
      return rootFolderId;
    }

    for (const zipFileEntry of zipFiles) {
      try {
        const { path, file: zipFileEntryObj } = zipFileEntry;

        // Extract file data
        const fileData = await zipFileEntryObj.async("arraybuffer");

        // Determine parent folder for this file
        const pathParts = path.split("/");
        const fileName = pathParts.pop();
        const folderPath = pathParts.join("/");

        let fileParentId = rootFolderId;

        // Create folder structure if needed
        if (folderPath) {
          if (createdFolders.has(folderPath)) {
            fileParentId = createdFolders.get(folderPath);
          } else {
            // Create folder path recursively
            const folderParts = folderPath.split("/");
            let currentPath = "";
            let currentParentId = rootFolderId;

            for (const folderName of folderParts) {
              currentPath = currentPath
                ? `${currentPath}/${folderName}`
                : folderName;

              if (createdFolders.has(currentPath)) {
                currentParentId = createdFolders.get(currentPath);
              } else {
                // Create folder
                try {
                  const createFolderResponse = await apiRequest(
                    "/v2/files/folders",
                    {
                      method: "POST",
                      body: JSON.stringify({
                        vaultspace_id: vaultspaceId,
                        name: folderName,
                        parent_id: currentParentId,
                      }),
                    },
                  );

                  if (createFolderResponse.ok) {
                    const folderData = await createFolderResponse.json();
                    currentParentId = folderData.folder.id;
                    createdFolders.set(currentPath, currentParentId);
                  } else {
                    // Folder might already exist, try to continue
                    logger.warn(
                      `Failed to create folder ${folderName}, continuing...`,
                    );
                  }
                } catch (error) {
                  logger.warn(`Error creating folder ${folderName}:`, error);
                }
              }
            }

            fileParentId = currentParentId;
          }
        }

        // Encrypt file
        const fileKey = await generateFileKey();
        const { encrypted, iv } = await encryptFile(fileKey, fileData);

        // Combine IV + encrypted data
        const ivArray = new Uint8Array(iv);
        const encryptedArray = new Uint8Array(encrypted);
        const combined = new Uint8Array(ivArray.length + encryptedArray.length);
        combined.set(ivArray, 0);
        combined.set(encryptedArray, ivArray.length);

        // Encrypt file key
        const encryptedFileKey = await encryptFileKey(vaultspaceKey, fileKey);

        // Upload file
        const fileBlob = new Blob([combined], {
          type: "application/octet-stream",
        });

        const formData = new FormData();
        formData.append("file", fileBlob, fileName);
        formData.append("vaultspace_id", vaultspaceId);
        formData.append("encrypted_file_key", encryptedFileKey);
        if (fileParentId) {
          formData.append("parent_id", fileParentId);
        }

        // Use fetch directly instead of apiRequest to avoid Content-Type issues with FormData
        const token = localStorage.getItem("jwt_token");
        const url = `/api/v2/files`;

        const uploadResponse = await fetch(url, {
          method: "POST",
          body: formData,
          headers: {
            // Don't set Content-Type - let browser set it with boundary for FormData
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          credentials: "same-origin",
        });

        if (!uploadResponse.ok) {
          const errorData = await parseErrorResponse(uploadResponse);
          // Check for quota errors
          if (
            uploadResponse.status === 403 &&
            errorData.error &&
            errorData.error.includes("quota")
          ) {
            throw new Error(
              `Storage quota exceeded while extracting ${fileName}. Please free up space and try again.`,
            );
          }
          throw new Error(
            `Failed to upload file ${fileName}: ${
              errorData.error || "Unknown error"
            }`,
          );
        }

        processedFiles++;
        if (onProgress) {
          const progress = 50 + (processedFiles / totalFiles) * 50; // 50-100%
          onProgress(
            progress,
            100,
            `Uploaded ${processedFiles}/${totalFiles} files...`,
          );
        }
      } catch (error) {
        logger.error(`Failed to process file ${zipFileEntry.path}:`, error);
        // Check for specific error types
        if (error.message && error.message.includes("quota")) {
          throw error; // Re-throw quota errors immediately
        } else if (error.message && error.message.includes("network")) {
          throw new Error(
            `Network error while extracting ${zipFileEntry.path}. Please check your connection and try again.`,
          );
        } else {
          throw new Error(
            `Failed to extract file ${zipFileEntry.path}: ${
              error.message || "Unknown error"
            }`,
          );
        }
      }
    }

    // Signal extraction completion to server
    try {
      const completeResponse = await apiRequest(
        "/v2/files/zip/extract/complete",
        {
          method: "POST",
          body: JSON.stringify({
            zip_file_id: zipFileId,
            vaultspace_id: vaultspaceId,
            extracted_folder_id: rootFolderId || targetParentId,
            files_count: totalFiles,
          }),
        },
      );

      if (!completeResponse.ok) {
        logger.warn("Failed to signal ZIP extraction completion");
      }
    } catch (error) {
      logger.warn("Error signaling ZIP extraction completion:", error);
    }

    return rootFolderId || targetParentId;
  } catch (error) {
    logger.error("Failed to extract ZIP:", error);
    throw error;
  }
}

/**
 * Download file with progress tracking.
 *
 * @param {string} fileId - File ID
 * @param {string} vaultspaceId - VaultSpace ID
 * @param {function} onProgress - Progress callback (loaded, total)
 * @returns {Promise<ArrayBuffer>} Encrypted file data
 */
async function downloadFileWithProgress(fileId, vaultspaceId, onProgress) {
  const params = new URLSearchParams({ vaultspace_id: vaultspaceId });
  const token = localStorage.getItem("jwt_token");
  const url = `/api/v2/files/${fileId}/download?${params.toString()}`;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.responseType = "arraybuffer";

    xhr.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(e.loaded, e.total);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        try {
          const errorText = new TextDecoder().decode(xhr.response);
          const errorData = JSON.parse(errorText);
          reject(new Error(errorData.error || "Failed to download file"));
        } catch (e) {
          reject(new Error(`Download failed: ${xhr.status}`));
        }
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network error during download"));
    });

    xhr.addEventListener("abort", () => {
      reject(new Error("Download cancelled"));
    });

    xhr.open("GET", url);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send();
  });
}

/**
 * Generate ZIP filename with current date in DDMMAAAA format using specified timezone.
 *
 * @param {string} timezone - Timezone string (e.g., "Europe/Paris", "UTC")
 * @returns {string} ZIP filename in format "export_DDMMAAAA.zip"
 */
export function generateZipFileName(timezone = "UTC") {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  const parts = formatter.formatToParts(now);
  const day = parts.find((p) => p.type === "day").value;
  const month = parts.find((p) => p.type === "month").value;
  const year = parts.find((p) => p.type === "year").value;

  return `export_${day}${month}${year}.zip`;
}

/**
 * Zip multiple files: download, decrypt, create ZIP, and return blob for download.
 *
 * @param {Array} fileItems - Array of file objects with id, vaultspace_id, original_name, file_key
 * @param {string|function} vaultspaceIdOrGetter - VaultSpace ID (if all files from same vaultspace) or function to get vaultspace key for a file
 * @param {CryptoKey|function} vaultspaceKeyOrGetter - Decrypted VaultSpace key (if all files from same vaultspace) or function to get vaultspace key for a file
 * @param {function} onProgress - Progress callback (current, total, message)
 * @param {string} timezone - Timezone for filename generation (default: "UTC")
 * @returns {Promise<Blob>} ZIP file blob ready for download
 */
export async function zipFiles(
  fileItems,
  vaultspaceIdOrGetter,
  vaultspaceKeyOrGetter,
  onProgress = null,
  timezone = "UTC",
) {
  try {
    if (!fileItems || fileItems.length === 0) {
      throw new Error("No files to zip");
    }

    // Filter out directories
    const files = fileItems.filter(
      (item) => item.mime_type !== "application/x-directory",
    );

    if (files.length === 0) {
      throw new Error("No files to zip (only directories selected)");
    }

    const zip = new JSZip();
    const totalFiles = files.length;
    let processedFiles = 0;

    if (onProgress) {
      onProgress(0, 1.0, `Downloading ${totalFiles} files...`);
    }

    for (const fileItem of files) {
      try {
        // Get vaultspace ID and key for this file
        const fileVaultspaceId =
          typeof vaultspaceIdOrGetter === "function"
            ? fileItem.vaultspace_id
            : vaultspaceIdOrGetter;
        const fileVaultspaceKey =
          typeof vaultspaceKeyOrGetter === "function"
            ? await vaultspaceKeyOrGetter(fileItem.vaultspace_id)
            : vaultspaceKeyOrGetter;

        if (!fileVaultspaceKey) {
          throw new Error(
            `VaultSpace key not found for file ${
              fileItem.original_name || fileItem.name
            }`,
          );
        }

        // Download encrypted file
        const encryptedData = await downloadFileWithProgress(
          fileItem.id,
          fileVaultspaceId,
          (loaded, total) => {
            if (onProgress) {
              // Calculate file progress as a fraction (0-1)
              const fileProgressFraction = total > 0 ? loaded / total : 0;
              // Calculate overall progress: base progress for completed files + current file progress
              // Each file represents 1/totalFiles of the total progress
              const baseProgress = processedFiles / totalFiles;
              const currentFileProgress = fileProgressFraction / totalFiles;
              const overallProgress = baseProgress + currentFileProgress;
              // Ensure progress doesn't exceed 1.0 (100%)
              const normalizedProgress = Math.min(overallProgress, 1.0);
              onProgress(
                normalizedProgress,
                1.0,
                `Downloading ${fileItem.original_name || fileItem.name}...`,
              );
            }
          },
        );

        // Get file data with encrypted key
        const fileInfo = await apiService.files.get(
          fileItem.id,
          fileVaultspaceId,
        );

        if (!fileInfo || !fileInfo.file_key) {
          throw new Error(
            `File key not found for ${fileItem.original_name || fileItem.name}`,
          );
        }

        // Decrypt file key
        const fileKey = await decryptFileKey(
          fileVaultspaceKey,
          fileInfo.file_key.encrypted_key,
        );

        // Decrypt file data
        const encryptedArray = new Uint8Array(encryptedData);
        const iv = encryptedArray.slice(0, 12);
        const encrypted = encryptedArray.slice(12);

        const decryptedData = await decryptFile(fileKey, encrypted, iv);

        // Add to ZIP with original filename
        const fileName = fileItem.original_name || fileItem.name || "file";
        zip.file(fileName, decryptedData);

        processedFiles++;
        if (onProgress) {
          const progress = processedFiles / totalFiles;
          const normalizedProgress = Math.min(progress, 1.0);
          onProgress(
            normalizedProgress,
            1.0,
            `Processed ${processedFiles}/${totalFiles} files...`,
          );
        }
      } catch (error) {
        logger.error(
          `Failed to process file ${fileItem.original_name || fileItem.name}:`,
          error,
        );
        // Check for specific error types
        if (error.message && error.message.includes("quota")) {
          throw new Error(
            `Storage quota exceeded while processing ${
              fileItem.original_name || fileItem.name
            }. Please free up space and try again.`,
          );
        } else if (error.message && error.message.includes("network")) {
          throw new Error(
            `Network error while downloading ${
              fileItem.original_name || fileItem.name
            }. Please check your connection and try again.`,
          );
        } else if (error.message && error.message.includes("decrypt")) {
          throw new Error(
            `Failed to decrypt file ${
              fileItem.original_name || fileItem.name
            }. The file key may be missing or corrupted.`,
          );
        } else {
          throw new Error(
            `Failed to process file ${
              fileItem.original_name || fileItem.name
            }: ${error.message || "Unknown error"}`,
          );
        }
      }
    }

    // Generate ZIP file
    if (onProgress) {
      onProgress(1.0, 1.0, "Creating ZIP archive...");
    }
    const zipBlob = await zip.generateAsync(
      { type: "blob", compression: "DEFLATE" },
      (metadata) => {
        if (onProgress) {
          // ZIP creation is the final step, so progress should be 100%
          // We keep it at 100% since all files are already processed
          onProgress(1.0, 1.0, `Creating ZIP: ${metadata.percent.toFixed(0)}%`);
        }
      },
    );

    return zipBlob;
  } catch (error) {
    logger.error("Failed to zip files:", error);
    throw error;
  }
}
