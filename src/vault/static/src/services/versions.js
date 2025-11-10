/**
 * Versions API service for Leyzen Vault.
 *
 * Handles file versioning requests.
 */

import { apiRequest, parseErrorResponse } from "./api";

/**
 * Versions API methods
 */
export const versions = {
  /**
   * Get version history for a file.
   *
   * @param {string} fileId - File ID
   * @param {object} options - Options
   * @param {string} options.branchName - Branch name (default: "main")
   * @param {number} options.limit - Maximum results (default: 50)
   * @param {number} options.offset - Offset for pagination (default: 0)
   * @returns {Promise<object>} Version history
   */
  async getHistory(fileId, options = {}) {
    const params = new URLSearchParams();
    if (options.branchName) params.append("branch_name", options.branchName);
    if (options.limit !== undefined)
      params.append("limit", options.limit.toString());
    if (options.offset !== undefined)
      params.append("offset", options.offset.toString());

    const response = await apiRequest(
      `/v2/versions/files/${fileId}?${params.toString()}`,
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get version history");
    }
    return await response.json();
  },

  /**
   * Get a specific version by ID.
   *
   * @param {string} versionId - Version ID
   * @returns {Promise<object>} Version details
   */
  async get(versionId) {
    const response = await apiRequest(`/v2/versions/${versionId}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get version");
    }
    const data = await response.json();
    return data.version;
  },

  /**
   * Restore a file to a previous version.
   *
   * @param {string} fileId - File ID
   * @param {string} versionId - Version ID to restore
   * @returns {Promise<object>} Updated file
   */
  async restore(fileId, versionId) {
    const response = await apiRequest(`/v2/versions/files/${fileId}/restore`, {
      method: "POST",
      body: JSON.stringify({ version_id: versionId }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to restore version");
    }
    const data = await response.json();
    return data.file;
  },

  /**
   * Compare two versions.
   *
   * @param {string} version1Id - First version ID
   * @param {string} version2Id - Second version ID
   * @returns {Promise<object>} Comparison results
   */
  async compare(version1Id, version2Id) {
    const response = await apiRequest("/v2/versions/compare", {
      method: "POST",
      body: JSON.stringify({
        version1_id: version1Id,
        version2_id: version2Id,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to compare versions");
    }
    return await response.json();
  },

  /**
   * Clean up old versions.
   *
   * @param {string} fileId - File ID
   * @param {object} options - Options
   * @param {number} options.keepCount - Number of versions to keep (default: 10)
   * @param {string} options.branchName - Branch name (default: "main")
   * @returns {Promise<object>} Cleanup results
   */
  async cleanup(fileId, options = {}) {
    const response = await apiRequest(`/v2/versions/files/${fileId}/cleanup`, {
      method: "POST",
      body: JSON.stringify({
        keep_count: options.keepCount || 10,
        branch_name: options.branchName || "main",
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to cleanup versions");
    }
    return await response.json();
  },
};
