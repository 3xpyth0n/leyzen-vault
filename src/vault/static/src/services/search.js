/**
 * Search API service for Leyzen Vault.
 *
 * Handles all search-related API requests.
 */

import { apiRequest, parseErrorResponse } from "./api";

/**
 * Search API methods
 */
export const search = {
  /**
   * Search files and folders.
   *
   * @param {object} options - Search options
   * @param {string} options.query - Search query (filename)
   * @param {string} options.vaultspaceId - Optional VaultSpace ID
   * @param {string} options.mimeType - Optional MIME type filter
   * @param {number} options.minSize - Optional minimum file size (bytes)
   * @param {number} options.maxSize - Optional maximum file size (bytes)
   * @param {string} options.createdAfter - Optional ISO date string
   * @param {string} options.createdBefore - Optional ISO date string
   * @param {string} options.updatedAfter - Optional ISO date string
   * @param {string} options.updatedBefore - Optional ISO date string
   * @param {boolean} options.filesOnly - Return only files
   * @param {boolean} options.foldersOnly - Return only folders
   * @param {string} options.sortBy - Sort field (relevance, name, date, size)
   * @param {string} options.sortOrder - Sort order (asc, desc)
   * @param {number} options.limit - Maximum results
   * @param {number} options.offset - Offset for pagination
   * @param {string} options.encryptedQuery - Optional encrypted query
   * @returns {Promise<object>} Search results
   */
  async searchFiles(options = {}) {
    const params = new URLSearchParams();

    if (options.query) params.append("q", options.query);
    if (options.vaultspaceId)
      params.append("vaultspace_id", options.vaultspaceId);
    if (options.mimeType) params.append("mime_type", options.mimeType);
    if (options.minSize !== undefined)
      params.append("min_size", options.minSize.toString());
    if (options.maxSize !== undefined)
      params.append("max_size", options.maxSize.toString());
    if (options.createdAfter)
      params.append("created_after", options.createdAfter);
    if (options.createdBefore)
      params.append("created_before", options.createdBefore);
    if (options.updatedAfter)
      params.append("updated_after", options.updatedAfter);
    if (options.updatedBefore)
      params.append("updated_before", options.updatedBefore);
    if (options.filesOnly) params.append("files_only", "true");
    if (options.foldersOnly) params.append("folders_only", "true");
    if (options.sortBy) params.append("sort_by", options.sortBy);
    if (options.sortOrder) params.append("sort_order", options.sortOrder);
    if (options.limit !== undefined)
      params.append("limit", options.limit.toString());
    if (options.offset !== undefined)
      params.append("offset", options.offset.toString());
    if (options.encryptedQuery)
      params.append("encrypted_query", options.encryptedQuery);

    const response = await apiRequest(`/search/files?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Search failed");
    }
    return await response.json();
  },

  /**
   * Get recently accessed or modified files.
   *
   * @param {object} options - Options
   * @param {number} options.days - Number of days to look back (default: 7)
   * @param {number} options.limit - Maximum results (default: 50)
   * @returns {Promise<object>} Recent files
   */
  async getRecentFiles(options = {}) {
    const params = new URLSearchParams();
    if (options.days !== undefined)
      params.append("days", options.days.toString());
    if (options.limit !== undefined)
      params.append("limit", options.limit.toString());

    const response = await apiRequest(`/search/recent?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get recent files");
    }
    return await response.json();
  },

  /**
   * Search files by encrypted tags.
   *
   * @param {object} options - Options
   * @param {string[]} options.tags - List of encrypted tags
   * @param {string} options.vaultspaceId - Optional VaultSpace ID
   * @returns {Promise<object>} Matching files
   */
  async searchByTags(options = {}) {
    const response = await apiRequest("/search/tags", {
      method: "POST",
      body: JSON.stringify({
        tags: options.tags || [],
        vaultspace_id: options.vaultspaceId,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Tag search failed");
    }
    return await response.json();
  },
};
