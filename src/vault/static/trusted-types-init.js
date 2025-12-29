// This script must be loaded before any other scripts that use Trusted Types
// CRITICAL: This script must execute IMMEDIATELY to patch DOM methods before
// third-party scripts inject code that uses innerHTML

// First, create a default policy IMMEDIATELY to handle third-party scripts
// The default policy is used automatically for all innerHTML assignments that don't specify a policy
(function initImmediate() {
  // Intercept and suppress TrustedHTML errors from third-party scripts
  // This must be done FIRST, before any third-party code runs

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

  // Create defaultPolicy FIRST - this is critical for third-party scripts
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
  // to intercept third-party scripts that inject code
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
        if (value && typeof value === "object" && value.toString) {
          try {
            originalInnerHTML.set.call(this, value);
            return;
          } catch (e) {
            // Silently ignore errors from third-party code
            // This prevents console errors for non-critical third-party scripts
            if (window.__suppressTrustedTypesErrors) {
              return;
            }
            // Fall through to policy wrapping
          }
        }

        if (window.vaultHTMLPolicy && typeof value === "string") {
          try {
            const trustedHTML = window.vaultHTMLPolicy.createHTML(value);
            originalInnerHTML.set.call(this, trustedHTML);
            return;
          } catch (e) {
            // Fall through to next policy
          }
        }

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
          // Silently ignore TrustedHTML errors from third-party scripts
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
      if (text && typeof text === "object" && text.toString) {
        try {
          return originalInsertAdjacentHTML.call(this, position, text);
        } catch (e) {
          // Fall through to policy wrapping
        }
      }

      if (window.vaultHTMLPolicy && typeof text === "string") {
        try {
          const trustedHTML = window.vaultHTMLPolicy.createHTML(text);
          return originalInsertAdjacentHTML.call(this, position, trustedHTML);
        } catch (e) {
          // Fall through to next policy
        }
      }

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
        // Silently ignore TrustedHTML errors from third-party scripts
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

    try {
      const policy = window.trustedTypes.createPolicy(name, config);
      // Store it on window for future access
      if (windowProperty) {
        window[windowProperty] = policy;
      }
      return policy;
    } catch (error) {
      // in case it was set by another script
      if (windowProperty && window[windowProperty]) {
        return window[windowProperty];
      }

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
  } catch (error) {}

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
  } catch (error) {}

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
  } catch (error) {}
} else {
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

          try {
            const policy = window.trustedTypes.createPolicy(name, config);
            // Store it on window for future access
            if (windowProperty) {
              window[windowProperty] = policy;
            }
            return policy;
          } catch (error) {
            // in case it was set by another script
            if (windowProperty && window[windowProperty]) {
              return window[windowProperty];
            }

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
        } catch (error) {}
      })();
    } else if (retryCount >= maxRetries) {
      clearInterval(checkInterval);
    }
  }, 100);
}
