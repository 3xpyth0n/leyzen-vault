// Initialize Trusted Types policies before CSP enforcement
// This script must be loaded before any other scripts that use Trusted Types
if (window.trustedTypes && window.trustedTypes.createPolicy) {
  // Store policies globally so they can be accessed later
  window.vaultHTMLPolicy = window.trustedTypes.createPolicy("vault-html", {
    createHTML: (html) => {
      return html;
    },
  });
  window.notificationsHTMLPolicy = window.trustedTypes.createPolicy(
    "notifications-html",
    {
      createHTML: (html) => {
        return html;
      },
    },
  );
  window.vaultScriptURLPolicy = window.trustedTypes.createPolicy(
    "vault-script-url",
    {
      createScriptURL: (url) => {
        return url;
      },
    },
  );
}
