/**
 * Thumbnail API service for Leyzen Vault.
 *
 * Handles thumbnail requests.
 */

import { apiRequest, parseErrorResponse } from "./api";

/**
 * Thumbnail API methods
 */
export const thumbnails = {
  /**
   * Get thumbnail for a file.
   *
   * @param {string} fileId - File ID
   * @param {string} size - Thumbnail size (64x64, 128x128, 256x256) - default: 256x256
   * @returns {Promise<Blob>} Thumbnail image blob
   */
  async get(fileId, size = "256x256") {
    const response = await apiRequest(`/v2/thumbnails/${fileId}?size=${size}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get thumbnail");
    }
    return await response.blob();
  },

  /**
   * Get thumbnail URL for a file.
   *
   * @param {string} fileId - File ID
   * @param {string} size - Thumbnail size (64x64, 128x128, 256x256) - default: 256x256
   * @returns {string} Thumbnail URL
   */
  getUrl(fileId, size = "256x256") {
    const token = localStorage.getItem("token");
    return `/api/v2/thumbnails/${fileId}?size=${size}&token=${token}`;
  },

  /**
   * Generate thumbnail for a file.
   *
   * @param {string} fileId - File ID
   * @param {string} fileDataBase64 - Base64 encoded decrypted file data
   * @returns {Promise<object>} Thumbnail generation result
   */
  async generate(fileId, fileDataBase64) {
    const response = await apiRequest(`/v2/thumbnails/${fileId}/generate`, {
      method: "POST",
      body: JSON.stringify({ file_data: fileDataBase64 }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to generate thumbnail");
    }
    return await response.json();
  },

  /**
   * Delete thumbnails for a file.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<object>} Deletion result
   */
  async delete(fileId) {
    const response = await apiRequest(`/v2/thumbnails/${fileId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete thumbnails");
    }
    return await response.json();
  },
};
