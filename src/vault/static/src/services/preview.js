/**
 * Preview API service for Leyzen Vault.
 *
 * Handles file preview requests and metadata.
 */

import { apiRequest, parseErrorResponse } from "./api";
import { normalizeMimeType } from "../utils/mimeType";

/**
 * Preview API methods
 */
export const preview = {
  /**
   * Get preview information for a file.
   * Note: This method is deprecated. Preview info should be determined client-side
   * based on file MIME type using isPreviewAvailable() and getPreviewType() methods.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<object>} Preview information
   * @deprecated Use isPreviewAvailable() and getPreviewType() instead
   */
  async getPreviewInfo(fileId) {
    // Legacy endpoint - may not be available in v2 API
    // For now, try the legacy endpoint as fallback
    const response = await apiRequest(`/files/${fileId}/preview`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get preview info");
    }
    return await response.json();
  },

  /**
   * Get thumbnail for a file.
   *
   * @param {string} fileId - File ID
   * @param {string} size - Thumbnail size (e.g., "256x256", "128x128", "64x64") - default: "256x256"
   * @returns {Promise<Blob>} Thumbnail blob
   */
  async getThumbnail(fileId, size = "256x256") {
    const response = await apiRequest(`/v2/thumbnails/${fileId}?size=${size}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get thumbnail");
    }
    return await response.blob();
  },

  /**
   * Check if preview is available for a MIME type.
   *
   * @param {string} mimeType - MIME type
   * @param {string} filename - Optional filename for mime type normalization
   * @returns {boolean} True if preview is available
   */
  isPreviewAvailable(mimeType, filename = null) {
    // Normalize mime type from extension if filename is provided
    const normalizedMimeType = filename
      ? normalizeMimeType(filename, mimeType)
      : mimeType;

    if (!normalizedMimeType) return false;

    // Images
    if (normalizedMimeType.startsWith("image/")) return true;

    // PDFs
    if (normalizedMimeType === "application/pdf") return true;

    // Videos
    if (normalizedMimeType.startsWith("video/")) return true;

    // Audio
    if (normalizedMimeType.startsWith("audio/")) return true;

    // Text files
    if (
      normalizedMimeType.startsWith("text/") ||
      normalizedMimeType === "application/json" ||
      normalizedMimeType === "application/xml" ||
      normalizedMimeType.includes("javascript") ||
      normalizedMimeType.includes("css") ||
      normalizedMimeType.includes("html")
    ) {
      return true;
    }

    return false;
  },

  /**
   * Get preview type for a MIME type.
   *
   * @param {string} mimeType - MIME type
   * @param {string} filename - Optional filename for mime type normalization
   * @returns {string} Preview type (image, pdf, video, audio, text, unsupported)
   */
  getPreviewType(mimeType, filename = null) {
    // Normalize mime type from extension if filename is provided
    const normalizedMimeType = filename
      ? normalizeMimeType(filename, mimeType)
      : mimeType;

    if (!normalizedMimeType) return "unsupported";

    if (normalizedMimeType.startsWith("image/")) return "image";
    if (normalizedMimeType === "application/pdf") return "pdf";
    if (normalizedMimeType.startsWith("video/")) return "video";
    if (normalizedMimeType.startsWith("audio/")) return "audio";
    if (
      normalizedMimeType.startsWith("text/") ||
      normalizedMimeType === "application/json" ||
      normalizedMimeType === "application/xml" ||
      normalizedMimeType.includes("javascript") ||
      normalizedMimeType.includes("css") ||
      normalizedMimeType.includes("html")
    ) {
      return "text";
    }

    return "unsupported";
  },
};
