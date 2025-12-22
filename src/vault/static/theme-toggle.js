/** @file theme-toggle.js - Theme toggle functionality */

// Initialize theme from localStorage or system preference
function initTheme() {
  const savedTheme = localStorage.getItem("leyzen-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  let theme = savedTheme || (prefersDark ? "dark" : "light");

  document.documentElement.setAttribute("data-theme", theme);
  updateThemeIcon(theme);
}

// Toggle theme
function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  const newTheme = currentTheme === "dark" ? "light" : "dark";

  document.documentElement.setAttribute("data-theme", newTheme);
  localStorage.setItem("leyzen-theme", newTheme);
  updateThemeIcon(newTheme);
}

// Helper function to safely set innerHTML with Trusted Types
function setInnerHTML(element, html) {
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  element.innerHTML = html;
}

// Update theme icon
function updateThemeIcon(theme) {
  const icon = document.getElementById("theme-toggle-icon");
  if (icon && window.Icons) {
    const iconHTML =
      theme === "dark"
        ? window.Icons.moon(20, "currentColor")
        : window.Icons.sun(20, "currentColor");
    setInnerHTML(icon, iconHTML);
  }
}

// Listen for system theme changes
window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", (e) => {
    if (!localStorage.getItem("leyzen-theme")) {
      const newTheme = e.matches ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", newTheme);
      updateThemeIcon(newTheme);
    }
  });

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  initTheme();

  // Add theme toggle button to header if it doesn't exist
  const headerNav = document.querySelector(".header-nav");
  const themeToggle = document.getElementById("theme-toggle-btn");

  if (headerNav && !themeToggle) {
    const toggleBtn = document.createElement("button");
    toggleBtn.id = "theme-toggle-btn";
    toggleBtn.className = "btn btn-icon theme-toggle-btn";
    toggleBtn.setAttribute("aria-label", "Toggle theme");
    const iconSpan = document.createElement("span");
    iconSpan.id = "theme-toggle-icon";
    if (window.Icons && window.Icons.moon) {
      setInnerHTML(iconSpan, window.Icons.moon(20, "currentColor"));
    }
    toggleBtn.appendChild(iconSpan);
    toggleBtn.addEventListener("click", toggleTheme);

    // Insert before user menu
    const userMenuContainer = headerNav.querySelector(".user-menu-container");
    if (userMenuContainer) {
      headerNav.insertBefore(toggleBtn, userMenuContainer);
    } else {
      headerNav.appendChild(toggleBtn);
    }

    updateThemeIcon(
      document.documentElement.getAttribute("data-theme") || "dark",
    );
  } else if (themeToggle) {
    themeToggle.addEventListener("click", toggleTheme);
    updateThemeIcon(
      document.documentElement.getAttribute("data-theme") || "dark",
    );
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.initTheme = initTheme;
  window.toggleTheme = toggleTheme;
}
