import { createRouter, createWebHistory } from "vue-router";
import Login from "../views/Login.vue";
import Setup from "../views/Setup.vue";
import Dashboard from "../views/Dashboard.vue";
import VaultSpaceView from "../views/VaultSpaceView.vue";
import TrashView from "../views/TrashView.vue";
import StarredView from "../views/StarredView.vue";
import RecentView from "../views/RecentView.vue";
import Share from "../views/Share.vue";
import SharedView from "../views/SharedView.vue";
import Register from "../views/Register.vue";
import AccountView from "../views/AccountView.vue";
import EmailVerification from "../views/EmailVerification.vue";
import AcceptInvitation from "../views/AcceptInvitation.vue";
import AdminPanel from "../views/AdminPanel.vue";
import { getUserMasterKey, getStoredSalt } from "../services/keyManager";
import { auth } from "../services/api";

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
      // Check if salt exists - this means master key was lost (likely after page refresh)
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
    component: Setup,
    beforeEnter: async (to, from, next) => {
      // Check if user is authenticated
      if (isAuthenticated()) {
        next("/dashboard");
        return;
      }

      // Check if setup is already complete
      try {
        const setupComplete = await auth.isSetupComplete();
        if (setupComplete) {
          next("/login");
          return;
        }
      } catch (err) {
        console.error("Failed to check setup status:", err);
        // Allow access if check fails
      }

      next();
    },
  },
  {
    path: "/login",
    name: "Login",
    component: Login,
    beforeEnter: async (to, from, next) => {
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
        console.error("Failed to check setup status:", err);
        // Allow access if check fails
      }

      next();
    },
  },
  {
    path: "/register",
    name: "Register",
    component: Register,
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
    component: EmailVerification,
    beforeEnter: requireGuest,
  },
  {
    path: "/accept-invitation",
    name: "AcceptInvitation",
    component: AcceptInvitation,
    beforeEnter: requireGuest,
  },
  {
    path: "/share/:token",
    name: "Share",
    component: Share,
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: Dashboard,
    beforeEnter: requireAuth,
  },
  {
    path: "/vaultspace/:id",
    name: "VaultSpaceView",
    component: VaultSpaceView,
    beforeEnter: requireAuth,
    props: true,
  },
  {
    path: "/trash",
    name: "Trash",
    component: TrashView,
    beforeEnter: requireAuth,
  },
  {
    path: "/starred",
    name: "Starred",
    component: StarredView,
    beforeEnter: requireAuth,
  },
  {
    path: "/recent",
    name: "Recent",
    component: RecentView,
    beforeEnter: requireAuth,
  },
  {
    path: "/shared",
    name: "Shared",
    component: SharedView,
    beforeEnter: requireAuth,
  },
  {
    path: "/account",
    name: "Account",
    component: AccountView,
    beforeEnter: requireAuth,
  },
  {
    path: "/admin",
    name: "Admin",
    component: AdminPanel,
    beforeEnter: requireAdmin,
  },
  {
    path: "/",
    name: "Root",
    beforeEnter: async (to, from, next) => {
      // Check if setup is complete first
      try {
        const setupComplete = await auth.isSetupComplete();
        if (!setupComplete) {
          // Setup not complete, redirect to setup
          next("/setup");
          return;
        }
      } catch (err) {
        console.error("[Router] Failed to check setup status:", err);
        // If check fails, redirect to setup (secure default)
        next("/setup");
        return;
      }

      // Setup is complete, redirect based on auth status
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
    try {
      const setupComplete = await auth.isSetupComplete();
      if (!setupComplete) {
        // Setup not complete, redirect to setup immediately
        next("/setup");
        return;
      }
    } catch (err) {
      console.error("Failed to check setup status for root:", err);
      // If check fails, redirect to setup (secure default)
      next("/setup");
      return;
    }
    // Setup is complete, let the route's beforeEnter handle the redirect
    // (it will redirect to /dashboard or /login based on auth status)
    next();
    return;
  }

  // Skip setup check for other public routes
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
    console.error("Failed to check setup status:", err);
    // If check fails, allow navigation (setup might be complete)
  }

  next();
});

export default router;
