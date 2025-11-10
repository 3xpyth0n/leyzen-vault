/**
 * Preview API service for Leyzen Vault.
 *
 * Handles file preview requests and metadata.
 */

import { apiRequest, parseErrorResponse } from "./api";

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
   * @returns {boolean} True if preview is available
   */
  isPreviewAvailable(mimeType) {
    if (!mimeType) return false;

    // Images
    if (mimeType.startsWith("image/")) return true;

    // PDFs
    if (mimeType === "application/pdf") return true;

    // Videos
    if (mimeType.startsWith("video/")) return true;

    // Audio
    if (mimeType.startsWith("audio/")) return true;

    // Text files
    if (
      mimeType.startsWith("text/") ||
      mimeType === "application/json" ||
      mimeType === "application/xml" ||
      mimeType.includes("javascript") ||
      mimeType.includes("css") ||
      mimeType.includes("html")
    ) {
      return true;
    }

    return false;
  },

  /**
   * Get preview type for a MIME type.
   *
   * @param {string} mimeType - MIME type
   * @returns {string} Preview type (image, pdf, video, audio, text, unsupported)
   */
  getPreviewType(mimeType) {
    if (!mimeType) return "unsupported";

    if (mimeType.startsWith("image/")) return "image";
    if (mimeType === "application/pdf") return "pdf";
    if (mimeType.startsWith("video/")) return "video";
    if (mimeType.startsWith("audio/")) return "audio";
    if (
      mimeType.startsWith("text/") ||
      mimeType === "application/json" ||
      mimeType === "application/xml" ||
      mimeType.includes("javascript") ||
      mimeType.includes("css") ||
      mimeType.includes("html")
    ) {
      return "text";
    }

    return "unsupported";
  },
};
