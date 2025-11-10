/** @file user-menu.js - User menu dropdown functionality */

// Create dropdown HTML content
function createDropdownHTML() {
  const csrfToken =
    document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content") || "";
  const userIcon = window.Icons?.user
    ? window.Icons.user(16, "currentColor")
    : "👤";
  const lockIcon = window.Icons?.lock
    ? window.Icons.lock(16, "currentColor")
    : "🔒";
  const logoutIcon = window.Icons?.logout
    ? window.Icons.logout(16, "currentColor")
    : "🚪";

  return `
        <a href="/account" class="user-menu-item">
            <span class="user-menu-icon">${userIcon}</span>
            <span>Account Settings</span>
        </a>
        <a href="/security" class="user-menu-item">
            <span class="user-menu-icon">${lockIcon}</span>
            <span>Security</span>
        </a>
        <div class="user-menu-divider"></div>
        <button type="button" class="user-menu-item user-menu-item-logout" id="logout-btn">
            <span class="user-menu-icon">${logoutIcon}</span>
            <span>Logout</span>
        </button>
    `;
}

// Position dropdown relative to button using fixed positioning
function positionDropdown(button, dropdown) {
  const buttonRect = button.getBoundingClientRect();

  // Ensure dropdown is displayed (but don't override display here, it's set by caller)
  dropdown.style.setProperty("display", "flex", "important");
  dropdown.style.setProperty("visibility", "visible", "important");

  // Get dropdown dimensions
  const dropdownRect = dropdown.getBoundingClientRect();
  const dropdownWidth = dropdownRect.width || 200;
  const dropdownHeight = dropdownRect.height || 150;

  // Position below button, aligned to right edge of button
  let top = buttonRect.bottom + 8;
  let left = buttonRect.right - dropdownWidth;

  // Ensure dropdown stays within viewport bounds
  if (left < 16) {
    left = 16;
  }
  if (left + dropdownWidth > window.innerWidth - 16) {
    left = window.innerWidth - dropdownWidth - 16;
  }
  if (top + dropdownHeight > window.innerHeight - 16) {
    top = buttonRect.top - dropdownHeight - 8;
    if (top < 16) {
      top = 16;
    }
  }

  // Set position using inline styles with !important
  dropdown.style.setProperty("top", `${Math.round(top)}px`, "important");
  dropdown.style.setProperty("left", `${Math.round(left)}px`, "important");
  dropdown.style.setProperty("position", "fixed", "important");
  dropdown.style.setProperty("z-index", "2147483647", "important");
}

// Force dropdown to be in body - this is CRITICAL for z-index to work
function ensureDropdownInBody(dropdown) {
  if (!dropdown) return;

  // If dropdown exists but is NOT in body, move it
  if (dropdown.parentNode && dropdown.parentNode !== document.body) {
    console.warn(
      "[UserMenu] Dropdown is not in body! Moving it...",
      dropdown.parentNode,
    );
    const oldParent = dropdown.parentNode;
    oldParent.removeChild(dropdown);
    document.body.appendChild(dropdown);
  }

  // If dropdown has no parent, add it to body
  if (!dropdown.parentNode) {
    document.body.appendChild(dropdown);
  }

  // Force z-index
  dropdown.style.setProperty("z-index", "2147483647", "important");
  dropdown.style.setProperty("position", "fixed", "important");
}

document.addEventListener("DOMContentLoaded", () => {
  const userMenuBtn = document.getElementById("user-menu-btn");
  const userMenuContainer = document.querySelector(".user-menu-container");

  if (!userMenuBtn) {
    console.warn("[UserMenu] Button not found");
    return;
  }

  let dropdown = null;
  let cleanupListeners = null;
  let parentCheckInterval = null;

  // Remove any existing dropdowns from wrong locations
  function cleanupExistingDropdowns() {
    // Remove from container
    const existingInContainer = userMenuContainer?.querySelector(
      ".user-menu-dropdown",
    );
    if (existingInContainer) {
      console.warn("[UserMenu] Removing dropdown from container");
      existingInContainer.remove();
    }
    // Remove any with same ID that's not in body
    const existing = document.getElementById("user-menu-dropdown");
    if (existing && existing.parentNode !== document.body) {
      console.warn(
        "[UserMenu] Removing dropdown from wrong location:",
        existing.parentNode,
      );
      existing.remove();
    }
  }

  // Toggle dropdown
  userMenuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();

    // Clean up existing dropdowns first
    cleanupExistingDropdowns();

    if (!dropdown) {
      // Create dropdown
      dropdown = document.createElement("div");
      dropdown.className = "user-menu-dropdown";
      dropdown.id = "user-menu-dropdown";
      dropdown.classList.add("hidden");

      // Set styles BEFORE adding to DOM
      dropdown.style.cssText =
        "position: fixed !important; z-index: 2147483647 !important; top: 0; left: 0; display: none !important;";

      // Add content
      if (window.vaultHTMLPolicy) {
        try {
          dropdown.innerHTML =
            window.vaultHTMLPolicy.createHTML(createDropdownHTML());
        } catch (e) {
          dropdown.innerHTML = createDropdownHTML();
        }
      } else {
        dropdown.innerHTML = createDropdownHTML();
      }

      // CRITICAL: Append to body, NOT container
      document.body.appendChild(dropdown);

      // Verify it's in body
      ensureDropdownInBody(dropdown);

      // Start monitoring to ensure it stays in body
      parentCheckInterval = setInterval(() => {
        ensureDropdownInBody(dropdown);
      }, 100);

      // Attach logout button listener
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();

          if (typeof window.showConfirmationModal === "function") {
            const logoutIcon = window.Icons?.logout
              ? window.Icons.logout(20, "currentColor")
              : "🚪";
            window.showConfirmationModal({
              icon: logoutIcon,
              title: "Logout",
              message: "Are you sure you want to logout?",
              confirmText: "Logout",
              dangerous: false,
              onConfirm: () => {
                if (
                  "serviceWorker" in navigator &&
                  navigator.serviceWorker.controller
                ) {
                  navigator.serviceWorker.controller.postMessage({
                    type: "CLEAR_CACHE",
                  });
                }
                window.location.href = "/login?t=" + Date.now();
              },
            });
          } else {
            window.location.href = "/login?t=" + Date.now();
          }
        });
      }
    }

    const isHidden = dropdown.classList.contains("hidden");

    if (isHidden) {
      // CRITICAL: Ensure dropdown is in body before showing
      ensureDropdownInBody(dropdown);

      userMenuContainer.classList.add("active");

      // Remove hidden class FIRST
      dropdown.classList.remove("hidden");

      // Force styles with !important to override .hidden
      dropdown.style.setProperty("display", "flex", "important");
      dropdown.style.setProperty("visibility", "hidden", "important");
      dropdown.style.setProperty("z-index", "2147483647", "important");
      dropdown.style.setProperty("position", "fixed", "important");

      // Position after render
      requestAnimationFrame(() => {
        // Double-check location
        ensureDropdownInBody(dropdown);

        // Position it
        positionDropdown(userMenuBtn, dropdown);

        // Make visible
        dropdown.style.setProperty("visibility", "visible", "important");
      });

      // Reposition on scroll/resize
      const reposition = () => {
        if (dropdown && !dropdown.classList.contains("hidden")) {
          ensureDropdownInBody(dropdown);
          positionDropdown(userMenuBtn, dropdown);
        }
      };

      window.addEventListener("scroll", reposition, true);
      window.addEventListener("resize", reposition);

      cleanupListeners = () => {
        window.removeEventListener("scroll", reposition, true);
        window.removeEventListener("resize", reposition);
        if (parentCheckInterval) {
          clearInterval(parentCheckInterval);
          parentCheckInterval = null;
        }
      };
    } else {
      // Hide dropdown
      dropdown.style.setProperty("display", "none", "important");
      dropdown.classList.add("hidden");
      userMenuContainer.classList.remove("active");
      if (cleanupListeners) {
        cleanupListeners();
        cleanupListeners = null;
      }
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (dropdown && !dropdown.classList.contains("hidden")) {
      if (
        !userMenuContainer.contains(e.target) &&
        !dropdown.contains(e.target)
      ) {
        dropdown.style.setProperty("display", "none", "important");
        dropdown.classList.add("hidden");
        userMenuContainer.classList.remove("active");
        if (cleanupListeners) {
          cleanupListeners();
          cleanupListeners = null;
        }
      }
    }
  });

  // Close dropdown on Escape key
  document.addEventListener("keydown", (e) => {
    if (
      dropdown &&
      e.key === "Escape" &&
      !dropdown.classList.contains("hidden")
    ) {
      dropdown.style.setProperty("display", "none", "important");
      dropdown.classList.add("hidden");
      userMenuContainer.classList.remove("active");
      if (cleanupListeners) {
        cleanupListeners();
        cleanupListeners = null;
      }
    }
  });
});
