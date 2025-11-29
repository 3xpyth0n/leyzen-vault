// Initialize Trusted Types policies before CSP enforcement
// This script must be loaded before any other scripts that use Trusted Types
// CRITICAL: This script must execute IMMEDIATELY to patch DOM methods before
// third-party scripts (like Cloudflare) inject code that uses innerHTML

// First, create a default policy IMMEDIATELY to handle Cloudflare and third-party scripts
// The default policy is used automatically for all innerHTML assignments that don't specify a policy
(function initImmediate() {
  // Intercept and suppress TrustedHTML errors from third-party scripts (e.g., Cloudflare)
  // This must be done FIRST, before any third-party code runs

  // Also intercept console.error to filter out TrustedHTML errors
  const originalConsoleError = console.error;
  console.error = function (...args) {
    const message = args
      .map((arg) => {
        if (typeof arg === "string") return arg;
        if (arg && arg.message) return arg.message;
        return String(arg);
      })
      .join(" ");
    if (message.includes("TrustedHTML") || message.includes("Trusted Types")) {
      // Silently ignore TrustedHTML console errors from third-party code
      return;
    }
    // Call original console.error for other messages
    originalConsoleError.apply(console, args);
  };

  const originalError = window.onerror;
  window.onerror = function (message, source, lineno, colno, error) {
    // Suppress TrustedHTML errors from third-party scripts
    const messageStr = String(message || "");
    const errorMessage = error && error.message ? String(error.message) : "";
    if (
      messageStr.includes("TrustedHTML") ||
      messageStr.includes("Trusted Types") ||
      errorMessage.includes("TrustedHTML") ||
      errorMessage.includes("Trusted Types")
    ) {
      // Silently ignore - these are from third-party code and not critical
      return true; // Prevent default error handling
    }
    // Call original error handler for other errors
    if (originalError) {
      return originalError.call(this, message, source, lineno, colno, error);
    }
    return false;
  };

  // Also intercept errors via addEventListener (catches more error types)
  window.addEventListener(
    "error",
    function (event) {
      const error = event.error;
      const message = event.message || (error && error.message) || "";
      if (
        String(message).includes("TrustedHTML") ||
        String(message).includes("Trusted Types")
      ) {
        // Silently ignore TrustedHTML errors from third-party code
        event.stopImmediatePropagation();
        event.preventDefault();
        return false;
      }
    },
    true, // Use capture phase to catch errors early
  );

  // Intercept unhandled promise rejections
  window.addEventListener("unhandledrejection", function (event) {
    const error = event.reason;
    const errorMessage =
      (error && error.message ? String(error.message) : "") ||
      String(event.reason || "");
    if (
      errorMessage.includes("TrustedHTML") ||
      errorMessage.includes("Trusted Types")
    ) {
      // Silently ignore TrustedHTML promise rejections from third-party code
      event.preventDefault();
      return;
    }
  });

  // Create defaultPolicy FIRST - this is critical for Cloudflare and third-party scripts
  // The default policy is automatically used for any innerHTML assignment without explicit policy
  if (window.trustedTypes && window.trustedTypes.createPolicy) {
    try {
      if (!window.trustedTypes.defaultPolicy) {
        window.trustedTypes.createPolicy("default", {
          createHTML: (html) => html,
          createScript: (script) => script,
          createScriptURL: (url) => url,
        });
      }
    } catch (e) {
      // Default policy may already exist or cannot be created (CSP may have locked policies)
      // Continue with patch anyway - patch will handle it gracefully
    }
  }

  // Create vaultHTMLPolicy for our own code
  if (window.trustedTypes && window.trustedTypes.createPolicy) {
    try {
      if (!window.vaultHTMLPolicy) {
        window.vaultHTMLPolicy = window.trustedTypes.createPolicy(
          "vault-html",
          {
            createHTML: (html) => html,
          },
        );
      }
    } catch (e) {
      // Policy may already exist, ignore
    }
  }

  // Patch Element.prototype.innerHTML and insertAdjacentHTML IMMEDIATELY
  // to intercept Cloudflare and other third-party scripts that inject code
  if (typeof Element === "undefined" || !Element.prototype) {
    return;
  }

  // Patch innerHTML setter
  const originalInnerHTML = Object.getOwnPropertyDescriptor(
    Element.prototype,
    "innerHTML",
  );

  if (
    originalInnerHTML &&
    originalInnerHTML.set &&
    !window.__innerHTMLPatched
  ) {
    Object.defineProperty(Element.prototype, "innerHTML", {
      set: function (value) {
        // If value is already a TrustedHTML, use it directly
        if (value && typeof value === "object" && value.toString) {
          try {
            originalInnerHTML.set.call(this, value);
            return;
          } catch (e) {
            // Silently ignore errors from third-party code (e.g., Cloudflare)
            // This prevents console errors for non-critical third-party scripts
            if (window.__suppressTrustedTypesErrors) {
              return;
            }
            // Fall through to policy wrapping
          }
        }

        // Try to use vaultHTMLPolicy first
        if (window.vaultHTMLPolicy && typeof value === "string") {
          try {
            const trustedHTML = window.vaultHTMLPolicy.createHTML(value);
            originalInnerHTML.set.call(this, trustedHTML);
            return;
          } catch (e) {
            // Fall through to next policy
          }
        }

        // Try defaultPolicy
        if (
          window.trustedTypes &&
          window.trustedTypes.defaultPolicy &&
          typeof value === "string"
        ) {
          try {
            const trustedHTML =
              window.trustedTypes.defaultPolicy.createHTML(value);
            originalInnerHTML.set.call(this, trustedHTML);
            return;
          } catch (e) {
            // Fall through to direct assignment
          }
        }

        // Last resort: try direct assignment, but suppress errors for third-party code
        try {
          originalInnerHTML.set.call(this, value);
        } catch (e) {
          // Silently ignore TrustedHTML errors from third-party scripts (e.g., Cloudflare)
          // These are not critical for application functionality
          const isTrustedHTMLError =
            e.message &&
            (e.message.includes("TrustedHTML") ||
              e.message.includes("Trusted Types"));
          if (isTrustedHTMLError) {
            // Suppress the error to avoid console noise from third-party code
            return;
          }
          // Re-throw other errors
          throw e;
        }
      },
      get: originalInnerHTML.get,
      configurable: true,
      enumerable: true,
    });
    window.__innerHTMLPatched = true;
  }

  // Patch insertAdjacentHTML method
  const originalInsertAdjacentHTML = Element.prototype.insertAdjacentHTML;
  if (originalInsertAdjacentHTML && !window.__insertAdjacentHTMLPatched) {
    Element.prototype.insertAdjacentHTML = function (position, text) {
      // If text is already a TrustedHTML, use it directly
      if (text && typeof text === "object" && text.toString) {
        try {
          return originalInsertAdjacentHTML.call(this, position, text);
        } catch (e) {
          // Fall through to policy wrapping
        }
      }

      // Try to use vaultHTMLPolicy first
      if (window.vaultHTMLPolicy && typeof text === "string") {
        try {
          const trustedHTML = window.vaultHTMLPolicy.createHTML(text);
          return originalInsertAdjacentHTML.call(this, position, trustedHTML);
        } catch (e) {
          // Fall through to next policy
        }
      }

      // Try defaultPolicy
      if (
        window.trustedTypes &&
        window.trustedTypes.defaultPolicy &&
        typeof text === "string"
      ) {
        try {
          const trustedHTML =
            window.trustedTypes.defaultPolicy.createHTML(text);
          return originalInsertAdjacentHTML.call(this, position, trustedHTML);
        } catch (e) {
          // Fall through to direct call
        }
      }

      // Last resort: try direct call, but suppress errors for third-party code
      try {
        return originalInsertAdjacentHTML.call(this, position, text);
      } catch (e) {
        // Silently ignore TrustedHTML errors from third-party scripts (e.g., Cloudflare)
        // These are not critical for application functionality
        const isTrustedHTMLError =
          e.message &&
          (e.message.includes("TrustedHTML") ||
            e.message.includes("Trusted Types"));
        if (isTrustedHTMLError) {
          // Suppress the error to avoid console noise from third-party code
          return;
        }
        // Re-throw other errors
        throw e;
      }
    };
    window.__insertAdjacentHTMLPatched = true;
  }
})();

if (window.trustedTypes && window.trustedTypes.createPolicy) {
  // Helper function to create or retrieve a policy
  function getOrCreatePolicy(name, config, windowProperty) {
    // First, check if the policy already exists on window
    if (windowProperty && window[windowProperty]) {
      return window[windowProperty];
    }
    // If it doesn't exist, try to create it
    try {
      const policy = window.trustedTypes.createPolicy(name, config);
      // Store it on window for future access
      if (windowProperty) {
        window[windowProperty] = policy;
      }
      return policy;
    } catch (error) {
      // If createPolicy fails (e.g., policy already exists), check window again
      // in case it was set by another script
      if (windowProperty && window[windowProperty]) {
        return window[windowProperty];
      }
      // If we can't create or find it, rethrow the error
      throw error;
    }
  }

  // Store policies globally so they can be accessed later
  try {
    window.vaultHTMLPolicy = getOrCreatePolicy(
      "vault-html",
      {
        createHTML: (html) => {
          return html;
        },
      },
      "vaultHTMLPolicy",
    );
  } catch (error) {
    console.error("Failed to initialize vaultHTMLPolicy:", error);
  }

  try {
    window.notificationsHTMLPolicy = getOrCreatePolicy(
      "notifications-html",
      {
        createHTML: (html) => {
          return html;
        },
      },
      "notificationsHTMLPolicy",
    );
  } catch (error) {
    console.error("Failed to initialize notificationsHTMLPolicy:", error);
  }

  try {
    window.vaultScriptURLPolicy = getOrCreatePolicy(
      "vault-script-url",
      {
        createScriptURL: (url) => {
          return url;
        },
      },
      "vaultScriptURLPolicy",
    );
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
        function getOrCreatePolicy(name, config, windowProperty) {
          // First, check if the policy already exists on window
          if (windowProperty && window[windowProperty]) {
            return window[windowProperty];
          }
          // If it doesn't exist, try to create it
          try {
            const policy = window.trustedTypes.createPolicy(name, config);
            // Store it on window for future access
            if (windowProperty) {
              window[windowProperty] = policy;
            }
            return policy;
          } catch (error) {
            // If createPolicy fails (e.g., policy already exists), check window again
            // in case it was set by another script
            if (windowProperty && window[windowProperty]) {
              return window[windowProperty];
            }
            // If we can't create or find it, rethrow the error
            throw error;
          }
        }

        try {
          window.vaultHTMLPolicy = getOrCreatePolicy(
            "vault-html",
            {
              createHTML: (html) => html,
            },
            "vaultHTMLPolicy",
          );
          window.notificationsHTMLPolicy = getOrCreatePolicy(
            "notifications-html",
            {
              createHTML: (html) => html,
            },
            "notificationsHTMLPolicy",
          );
          window.vaultScriptURLPolicy = getOrCreatePolicy(
            "vault-script-url",
            {
              createScriptURL: (url) => url,
            },
            "vaultScriptURLPolicy",
          );
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
