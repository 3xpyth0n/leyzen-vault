// Initialize Trusted Types policies before CSP enforcement
// This script must be loaded before any other scripts that use Trusted Types
if (window.trustedTypes && window.trustedTypes.createPolicy) {
  // Helper function to create or retrieve a policy
  function getOrCreatePolicy(name, config) {
    try {
      // First, try to get existing policy
      const existingPolicy = window.trustedTypes.getPolicy(name);
      if (existingPolicy) {
        return existingPolicy;
      }
      // If it doesn't exist, create it
      return window.trustedTypes.createPolicy(name, config);
    } catch (error) {
      // If createPolicy fails (e.g., policy already exists), try to get it
      try {
        const existingPolicy = window.trustedTypes.getPolicy(name);
        if (existingPolicy) {
          return existingPolicy;
        }
      } catch (getError) {
        console.error(
          `Failed to retrieve Trusted Types policy '${name}':`,
          getError.message,
        );
      }
      throw error;
    }
  }

  // Store policies globally so they can be accessed later
  try {
    window.vaultHTMLPolicy = getOrCreatePolicy("vault-html", {
      createHTML: (html) => {
        return html;
      },
    });
  } catch (error) {
    console.error("Failed to initialize vaultHTMLPolicy:", error);
  }

  try {
    window.notificationsHTMLPolicy = getOrCreatePolicy("notifications-html", {
      createHTML: (html) => {
        return html;
      },
    });
  } catch (error) {
    console.error("Failed to initialize notificationsHTMLPolicy:", error);
  }

  try {
    window.vaultScriptURLPolicy = getOrCreatePolicy("vault-script-url", {
      createScriptURL: (url) => {
        return url;
      },
    });
  } catch (error) {
    console.error("Failed to initialize vaultScriptURLPolicy:", error);
  }
} else {
  // Try to wait for Trusted Types to become available (in case it's loaded asynchronously)
  let retryCount = 0;
  const maxRetries = 10;
  const checkInterval = setInterval(() => {
    retryCount++;
    if (window.trustedTypes && window.trustedTypes.createPolicy) {
      clearInterval(checkInterval);
      // Re-execute the initialization logic
      (function initPolicies() {
        // Helper function to create or retrieve a policy
        function getOrCreatePolicy(name, config) {
          try {
            const existingPolicy = window.trustedTypes.getPolicy(name);
            if (existingPolicy) {
              return existingPolicy;
            }
            return window.trustedTypes.createPolicy(name, config);
          } catch (error) {
            try {
              const existingPolicy = window.trustedTypes.getPolicy(name);
              if (existingPolicy) {
                return existingPolicy;
              }
            } catch (getError) {
              console.error(
                `Failed to retrieve Trusted Types policy '${name}':`,
                getError.message,
              );
            }
            throw error;
          }
        }

        try {
          window.vaultHTMLPolicy = getOrCreatePolicy("vault-html", {
            createHTML: (html) => html,
          });
          window.notificationsHTMLPolicy = getOrCreatePolicy(
            "notifications-html",
            {
              createHTML: (html) => html,
            },
          );
          window.vaultScriptURLPolicy = getOrCreatePolicy("vault-script-url", {
            createScriptURL: (url) => url,
          });
        } catch (error) {
          console.error(
            "Failed to initialize Trusted Types policies (delayed):",
            error,
          );
        }
      })();
    } else if (retryCount >= maxRetries) {
      clearInterval(checkInterval);
    }
  }, 100);
}
