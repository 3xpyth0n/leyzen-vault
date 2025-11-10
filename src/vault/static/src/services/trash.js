/**
 * Trash API service for Leyzen Vault.
 *
 * Handles trash/restore requests.
 */

import { apiRequest, parseErrorResponse } from "./api";

/**
 * Trash API methods
 */
export const trash = {
  /**
   * List all deleted files (trash).
   *
   * @param {string} vaultspaceId - Optional VaultSpace ID filter
   * @returns {Promise<object>} List of deleted files
   */
  async list(vaultspaceId = null) {
    const params = new URLSearchParams();
    if (vaultspaceId) {
      params.append("vaultspace_id", vaultspaceId);
    }

    const response = await apiRequest(`/v2/trash?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list trash");
    }
    return await response.json();
  },

  /**
   * Restore a deleted file from trash.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<object>} Restored file
   */
  async restore(fileId) {
    const response = await apiRequest(`/v2/trash/${fileId}/restore`, {
      method: "POST",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to restore file");
    }
    return await response.json();
  },

  /**
   * Permanently delete a file from trash.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<object>} Success message
   */
  async permanentlyDelete(fileId) {
    const response = await apiRequest(`/v2/trash/${fileId}/permanent`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to permanently delete file");
    }
    return await response.json();
  },
};
