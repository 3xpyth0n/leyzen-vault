import { createRouter, createWebHistory } from "vue-router";
import { getUserMasterKey, getStoredSalt } from "../services/keyManager";
import { auth } from "../services/api";

/**
 * Clear all browser storage (cookies, localStorage, sessionStorage).
 * Used when accessing setup page to ensure a clean state.
 */
function clearAllStorage() {
  // Clear all localStorage items
  try {
    localStorage.clear();
  } catch (err) {
    // Silently fail
  }

  // Clear all sessionStorage items
  try {
    sessionStorage.clear();
  } catch (err) {
    // Silently fail
  }

  // Clear all cookies
  try {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      const eqPos = cookie.indexOf("=");
      const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
      if (name) {
        // Delete cookie by setting it to expire in the past
        // Try with different path and domain combinations
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
        const hostname = window.location.hostname;
        if (hostname) {
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${hostname}`;
          // Try with leading dot for subdomain cookies
          if (hostname.indexOf(".") > 0) {
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${hostname}`;
          }
        }
      }
    }
  } catch (err) {
    // Silently fail
  }
}

/**
 * Check if user is authenticated (has JWT token).
 *
 * @returns {boolean} True if authenticated
 */
function isAuthenticated() {
  return localStorage.getItem("jwt_token") !== null;
}

/**
 * Check if master key is available.
 * This is important for routes that need encryption/decryption.
 *
 * @returns {Promise<boolean>} True if master key is available
 */
async function hasMasterKey() {
  const masterKey = await getUserMasterKey();
  return masterKey !== null;
}

/**
 * Navigation guard to protect routes requiring authentication.
 * For routes that need encryption (like VaultSpaceView), also check for master key.
 *
 * @param {object} to - Target route
 * @param {object} from - Source route
 * @param {function} next - Next function
 */
async function requireAuth(to, from, next) {
  if (!isAuthenticated()) {
    next("/login");
    return;
  }

  // For routes that need encryption, check if master key is available
  if (
    to.name === "VaultSpaceView" ||
    to.name === "Trash" ||
    to.name === "Starred" ||
    to.name === "Recent"
  ) {
    const masterKeyAvailable = await hasMasterKey();
    if (!masterKeyAvailable) {
      // Check if salt exists - indicates master key is not available
      const storedSalt = getStoredSalt();
      if (storedSalt) {
        // User is authenticated (JWT valid) but master key is lost from memory
        // This is normal after page refresh - don't disconnect user
        // The component will handle showing appropriate message
        console.warn(
          "Master key lost but salt exists. This is normal after page refresh.",
        );
        console.warn(
          "User will need to re-enter password to access encrypted content.",
        );
        // Allow navigation - component will handle the missing master key
        next();
        return;
      }
    }
  }

  next();
}

/**
 * Navigation guard to redirect authenticated users away from login.
 *
 * @param {object} to - Target route
 * @param {object} from - Source route
 * @param {function} next - Next function
 */
function requireGuest(to, from, next) {
  if (!isAuthenticated()) {
    next();
  } else {
    next("/dashboard");
  }
}

/**
 * Navigation guard to protect admin routes.
 * Requires authentication and admin/superadmin role.
 *
 * @param {object} to - Target route
 * @param {object} from - Source route
 * @param {function} next - Next function
 */
async function requireAdmin(to, from, next) {
  // First check authentication
  if (!isAuthenticated()) {
    next("/login");
    return;
  }

  // Check user role
  try {
    const user = await auth.getCurrentUser();

    if (!user || !user.global_role) {
      // User info not available or missing role - redirect to dashboard
      next("/dashboard");
      return;
    }

    // Check if user is admin or superadmin
    if (user.global_role === "admin" || user.global_role === "superadmin") {
      // User has admin privileges - allow access
      next();
      return;
    } else {
      // User is not admin - redirect to dashboard
      next("/dashboard");
      return;
    }
  } catch (err) {
    // Error fetching user info (API error, token invalid, etc.)
    // Redirect to dashboard for security
    console.error("Failed to verify admin role:", err);
    next("/dashboard");
    return;
  }
}

const routes = [
  {
    path: "/setup",
    name: "Setup",
    component: () => import("../views/Setup.vue"),
    beforeEnter: async (to, from, next) => {
      // Clear all browser storage when accessing setup page
      // This ensures a clean state, simulating a "fresh install" from browser perspective
      // Important: This removes cookies, localStorage, and sessionStorage that might
      // contain authentication tokens or session data
      clearAllStorage();

      // Allow access to setup page - don't check authentication here
      // The setup page will handle showing confirmation and redirecting to login
      // We don't want to redirect authenticated users away from setup page
      // because they might be completing the setup process

      // Check if setup is already complete
      // If check fails (network error, database not available), allow access to setup page
      try {
        const setupComplete = await auth.isSetupComplete();
        if (setupComplete) {
          // Setup is complete, redirect to login
          next("/login");
          return;
        }
      } catch (err) {
        // Network errors are expected on fresh install or when database is unavailable
        // Always allow access to setup page if check fails
      }

      // Always allow access to setup page
      next();
    },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    beforeEnter: async (to, from, next) => {
      // If coming from setup, completely clear all localStorage
      // This is critical: setup should never leave any state, so clear everything
      // Check both query param and sessionStorage flag
      const comingFromSetup =
        to.query.setup === "done" ||
        sessionStorage.getItem("_setup_complete") === "1";
      if (comingFromSetup) {
        // AGGRESSIVE token removal: remove explicitly first
        try {
          localStorage.removeItem("jwt_token");
          delete localStorage.jwt_token;
        } catch (err) {
          // Ignore
        }

        // Completely clear all localStorage - this is a fresh setup
        // There's nothing to preserve, so clear everything
        try {
          localStorage.clear();
          // Clear the flag after using it
          sessionStorage.removeItem("_setup_complete");
        } catch (err) {
          // Ignore errors but try to clear flag anyway
          try {
            sessionStorage.removeItem("_setup_complete");
          } catch (e) {
            // Ignore
          }
        }

        // Final verification: if token still exists, it was recréé - remove it again
        const tokenAfterClear = localStorage.getItem("jwt_token");
        if (tokenAfterClear) {
          console.warn(
            "Token detected in login guard after clear! Removing again...",
          );
          localStorage.removeItem("jwt_token");
          delete localStorage.jwt_token;
          if (localStorage.getItem("jwt_token")) {
            localStorage.clear();
          }
        }

        // Always allow access when coming from setup, regardless of any state
        next();
        return;
      }

      // Check if user is authenticated
      if (isAuthenticated()) {
        next("/dashboard");
        return;
      }

      // Check if setup is complete
      try {
        const setupComplete = await auth.isSetupComplete();
        if (!setupComplete) {
          // Setup not complete, redirect to setup
          next("/setup");
          return;
        }
      } catch (err) {
        // Network errors are expected on fresh install - allow access
      }

      next();
    },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("../views/Register.vue"),
    beforeEnter: async (to, from, next) => {
      // Check if user is authenticated first
      if (isAuthenticated()) {
        next("/dashboard");
        return;
      }

      // Check if signup is enabled
      try {
        const signupEnabled = await auth.isSignupEnabled();
        if (!signupEnabled) {
          next("/login");
          return;
        }
      } catch (err) {
        console.error("Failed to check signup status:", err);
        // Allow access by default if check fails
      }

      next();
    },
  },
  {
    path: "/verify-email",
    name: "EmailVerification",
    component: () => import("../views/EmailVerification.vue"),
    beforeEnter: requireGuest,
  },
  {
    path: "/accept-invitation",
    name: "AcceptInvitation",
    component: () => import("../views/AcceptInvitation.vue"),
    beforeEnter: requireGuest,
  },
  {
    path: "/sso/callback/:providerId",
    name: "SSOCallback",
    component: () => import("../views/SSOCallback.vue"),
    beforeEnter: requireGuest,
    props: true,
  },
  {
    path: "/share/:token",
    name: "Share",
    component: () => import("../views/Share.vue"),
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("../views/Dashboard.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/vaultspace/:id",
    name: "VaultSpaceView",
    component: () => import("../views/VaultSpaceView.vue"),
    beforeEnter: requireAuth,
    props: true,
  },
  {
    path: "/trash",
    name: "Trash",
    component: () => import("../views/TrashView.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/starred",
    name: "Starred",
    component: () => import("../views/StarredView.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/recent",
    name: "Recent",
    component: () => import("../views/RecentView.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/shared",
    name: "Shared",
    component: () => import("../views/SharedView.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/account",
    name: "Account",
    component: () => import("../views/AccountView.vue"),
    beforeEnter: requireAuth,
  },
  {
    path: "/admin",
    name: "Admin",
    component: () => import("../views/AdminPanel.vue"),
    beforeEnter: requireAdmin,
  },
  {
    path: "/",
    name: "Root",
    beforeEnter: (to, from, next) => {
      // Setup check is handled by global beforeEach guard
      // If we reach here, setup is complete, redirect based on auth status
      if (isAuthenticated()) {
        next("/dashboard");
      } else {
        next("/login");
      }
    },
  },
];

const router = createRouter({
  history: createWebHistory("/"),
  routes,
});

// Global navigation guard to check setup status for protected routes
// NOTE: This runs BEFORE route-level beforeEnter guards
router.beforeEach(async (to, from, next) => {
  // Handle root path explicitly - check setup before any route-level guards
  if (to.path === "/" || to.path === "" || to.name === "Root") {
    // On fresh install, the API might not be ready yet
    // Try to check setup status, but redirect to setup if it fails
    try {
      const setupComplete = await auth.isSetupComplete();
      if (!setupComplete) {
        // Setup not complete, redirect to setup immediately
        next("/setup");
        return;
      }
    } catch (err) {
      // Network errors are expected on fresh install - redirect to setup
      // This handles the case where the database is not initialized yet
      next("/setup");
      return;
    }
    // Setup is complete, let the route's beforeEnter handle the redirect
    // (it will redirect to /dashboard or /login based on auth status)
    next();
    return;
  }

  // Skip setup check for other public routes
  // Special handling for Login with setup=done query param or sessionStorage flag
  const comingFromSetup =
    to.query.setup === "done" ||
    sessionStorage.getItem("_setup_complete") === "1";
  if (to.name === "Login" && comingFromSetup) {
    // Coming from setup - completely clear all localStorage
    // This is a fresh setup, there's nothing to preserve
    try {
      localStorage.clear();
      // Clear the flag after using it
      sessionStorage.removeItem("_setup_complete");
    } catch (err) {
      // Ignore errors but try to clear flag anyway
      try {
        sessionStorage.removeItem("_setup_complete");
      } catch (e) {
        // Ignore
      }
    }
    next();
    return;
  }

  if (
    to.name === "Setup" ||
    to.name === "Login" ||
    to.name === "Register" ||
    to.name === "EmailVerification" ||
    to.name === "AcceptInvitation" ||
    to.name === "Share"
  ) {
    next();
    return;
  }

  // Check setup status for all other routes
  try {
    const setupComplete = await auth.isSetupComplete();
    if (!setupComplete) {
      next("/setup");
      return;
    }
  } catch (err) {
    // Network errors are expected on fresh install - allow navigation
  }

  next();
});

export default router;
