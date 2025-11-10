/**
 * Quota API service for Leyzen Vault.
 *
 * Handles quota requests.
 */

import { apiRequest, parseErrorResponse } from "./api";

/**
 * Quota API methods
 */
export const quota = {
  /**
   * Get quota information for the current user.
   *
   * @returns {Promise<object>} Quota information
   */
  async get() {
    const response = await apiRequest("/v2/quota");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get quota");
    }
    return await response.json();
  },

  /**
   * Check if user has enough quota for additional storage.
   *
   * @param {number} additionalBytes - Additional bytes to check
   * @returns {Promise<object>} Quota check result
   */
  async check(additionalBytes = 0) {
    const response = await apiRequest("/v2/quota/check", {
      method: "POST",
      body: JSON.stringify({ additional_bytes: additionalBytes }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to check quota");
    }
    return await response.json();
  },
};
