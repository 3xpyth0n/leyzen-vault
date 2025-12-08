<template>
  <nav
    class="bottom-navigation"
    :class="{ expanded: isExpanded }"
    @click="handleNavClick"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @touchstart="onTouchStart"
  >
    <!-- Collapsed indicator icon -->
    <div class="bottom-nav-collapsed-icon" v-if="!isExpanded">
      <span v-html="getIcon('map', 20)"></span>
    </div>

    <!-- Expanded content -->
    <div class="bottom-nav-content">
      <button
        @click.stop="handleNavClickToPath('/dashboard')"
        class="bottom-nav-item"
        data-path="/dashboard"
        :class="{ 'router-link-active': $route.path === '/dashboard' }"
        :disabled="!isClickable || isOffline"
        aria-label="Home"
      >
        <span v-html="getIcon('home', 24)" class="bottom-nav-icon"></span>
        <span class="bottom-nav-label">Home</span>
      </button>
      <button
        @click.stop="handleNavClickToPath('/starred')"
        class="bottom-nav-item"
        data-path="/starred"
        :class="{ 'router-link-active': $route.path === '/starred' }"
        :disabled="!isClickable || isOffline"
        aria-label="Starred"
      >
        <span v-html="getIcon('star', 24)" class="bottom-nav-icon"></span>
        <span class="bottom-nav-label">Starred</span>
      </button>
      <button
        @click.stop="handleNavClickToPath('/shared')"
        class="bottom-nav-item"
        data-path="/shared"
        :class="{ 'router-link-active': $route.path === '/shared' }"
        :disabled="!isClickable || isOffline"
        aria-label="Shared"
      >
        <span v-html="getIcon('link', 24)" class="bottom-nav-icon"></span>
        <span class="bottom-nav-label">Shared</span>
      </button>
      <button
        @click.stop="handleNavClickToPath('/recent')"
        class="bottom-nav-item"
        data-path="/recent"
        :class="{ 'router-link-active': $route.path === '/recent' }"
        :disabled="!isClickable || isOffline"
        aria-label="Recent"
      >
        <span v-html="getIcon('clock', 24)" class="bottom-nav-icon"></span>
        <span class="bottom-nav-label">Recent</span>
      </button>
      <button
        @click.stop="handleNavClickToPath('/trash')"
        class="bottom-nav-item"
        data-path="/trash"
        :class="{ 'router-link-active': $route.path === '/trash' }"
        :disabled="!isClickable || isOffline"
        aria-label="Trash"
      >
        <span v-html="getIcon('trash', 24)" class="bottom-nav-icon"></span>
        <span class="bottom-nav-label">Trash</span>
      </button>
    </div>
  </nav>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { useServerStatus } from "../composables/useServerStatus";

export default {
  name: "BottomNavigation",
  setup() {
    const router = useRouter();
    const { isOffline } = useServerStatus();
    const isExpanded = ref(false);
    const isClickable = ref(false); // Buttons become clickable 0.5s after expansion
    let lastScrollY = 0;
    let scrollTimeout = null;
    let autoCollapseTimeout = null;
    let clickableTimeout = null;

    const handleNavClick = (event) => {
      // Check if click is on a navigation button
      const navButton = event.target.closest(".bottom-nav-item");

      if (navButton) {
        // Only allow navigation if buttons are clickable (0.5s after expansion)
        if (!isClickable.value) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        // Click is on a navigation button - handle navigation
        const path = navButton.getAttribute("data-path");
        if (path) {
          handleNavClickToPath(path);
        }
        return;
      }

      // Click is on the nav container itself (not on a button)
      // If collapsed, expand it
      if (!isExpanded.value) {
        event.preventDefault();
        event.stopPropagation();
        isExpanded.value = true;
        isClickable.value = false; // Buttons not clickable yet
        // Clear any pending auto-collapse
        if (autoCollapseTimeout) {
          clearTimeout(autoCollapseTimeout);
          autoCollapseTimeout = null;
        }
        // Clear any pending clickable timeout
        if (clickableTimeout) {
          clearTimeout(clickableTimeout);
          clickableTimeout = null;
        }
        // Make buttons clickable after 0.5 seconds
        clickableTimeout = setTimeout(() => {
          isClickable.value = true;
        }, 500);
        // Auto-collapse after 5 seconds
        autoCollapseTimeout = setTimeout(() => {
          isExpanded.value = false;
          isClickable.value = false;
        }, 5000);
      }
    };

    const toggleExpanded = () => {
      // Toggle expanded state (for desktop hover behavior)
      isExpanded.value = !isExpanded.value;
      if (isExpanded.value) {
        // Clear any pending auto-collapse
        if (autoCollapseTimeout) {
          clearTimeout(autoCollapseTimeout);
          autoCollapseTimeout = null;
        }
      }
    };

    const onMouseEnter = () => {
      // Always expand on hover (desktop)
      isExpanded.value = true;
      isClickable.value = true; // On desktop, buttons are immediately clickable
      // Clear auto-collapse when mouse enters
      if (autoCollapseTimeout) {
        clearTimeout(autoCollapseTimeout);
        autoCollapseTimeout = null;
      }
      // Clear any pending clickable timeout
      if (clickableTimeout) {
        clearTimeout(clickableTimeout);
        clickableTimeout = null;
      }
    };

    const onMouseLeave = () => {
      // Auto-collapse after 3 seconds when mouse leaves
      if (autoCollapseTimeout) {
        clearTimeout(autoCollapseTimeout);
      }
      autoCollapseTimeout = setTimeout(() => {
        isExpanded.value = false;
        isClickable.value = false;
      }, 3000);
    };

    const handleScroll = () => {
      // Disable scroll activation in mobile mode
      const isMobile =
        window.matchMedia("(max-width: 768px)").matches ||
        document.body.classList.contains("mobile-mode");
      if (isMobile) {
        return;
      }

      const currentScrollY = window.scrollY || window.pageYOffset;

      // Expand on any scroll (up or down)
      isExpanded.value = true;
      // Buttons are immediately clickable when expanded via scroll
      isClickable.value = true;

      // Clear any existing auto-collapse timeout
      if (autoCollapseTimeout) {
        clearTimeout(autoCollapseTimeout);
      }
      // Clear any pending clickable timeout
      if (clickableTimeout) {
        clearTimeout(clickableTimeout);
        clickableTimeout = null;
      }

      // Auto-collapse after 5 seconds of no scrolling
      if (scrollTimeout) {
        clearTimeout(scrollTimeout);
      }

      scrollTimeout = setTimeout(() => {
        // After scroll stops, wait 5 seconds then collapse
        autoCollapseTimeout = setTimeout(() => {
          isExpanded.value = false;
          isClickable.value = false;
        }, 5000);
      }, 150); // Small delay to detect when scrolling stops

      lastScrollY = currentScrollY;
    };

    const handleClickOutside = (event) => {
      // Check if click is outside the bottom navigation
      const navElement = event.target.closest(".bottom-navigation");
      if (!navElement && isExpanded.value) {
        // On mobile, collapse immediately on outside click
        // On desktop, also collapse immediately
        isExpanded.value = false;
        isClickable.value = false;
        // Clear any pending timeouts
        if (autoCollapseTimeout) {
          clearTimeout(autoCollapseTimeout);
          autoCollapseTimeout = null;
        }
        if (clickableTimeout) {
          clearTimeout(clickableTimeout);
          clickableTimeout = null;
        }
      }
    };

    onMounted(() => {
      lastScrollY = window.scrollY || window.pageYOffset;
      window.addEventListener("scroll", handleScroll, { passive: true });
      // Add click outside listener
      document.addEventListener("click", handleClickOutside);
    });

    onBeforeUnmount(() => {
      window.removeEventListener("scroll", handleScroll);
      document.removeEventListener("click", handleClickOutside);
      if (scrollTimeout) {
        clearTimeout(scrollTimeout);
      }
      if (autoCollapseTimeout) {
        clearTimeout(autoCollapseTimeout);
      }
      if (clickableTimeout) {
        clearTimeout(clickableTimeout);
      }
    });

    const handleNavClickToPath = (path) => {
      // Block navigation if server is offline
      if (isOffline.value) {
        return;
      }
      // Navigate
      if (router) {
        router.push(path);
      }
      // On mobile, keep the bar open for a bit to show navigation happened
      // On desktop, collapse immediately
      const isMobile =
        window.matchMedia("(max-width: 768px)").matches ||
        document.body.classList.contains("mobile-mode");
      if (isMobile) {
        // Clear any pending auto-collapse and set a new one for 2 seconds
        if (autoCollapseTimeout) {
          clearTimeout(autoCollapseTimeout);
        }
        autoCollapseTimeout = setTimeout(() => {
          isExpanded.value = false;
        }, 2000);
      } else {
        // Desktop: collapse immediately
        setTimeout(() => {
          isExpanded.value = false;
        }, 500);
      }
    };

    const onTouchStart = (event) => {
      // On touch when collapsed, expand and keep open for 5 seconds
      if (!isExpanded.value) {
        event.preventDefault();
        event.stopPropagation();
        isExpanded.value = true;
        isClickable.value = false; // Buttons not clickable yet
        // Clear any pending auto-collapse
        if (autoCollapseTimeout) {
          clearTimeout(autoCollapseTimeout);
          autoCollapseTimeout = null;
        }
        // Clear any pending clickable timeout
        if (clickableTimeout) {
          clearTimeout(clickableTimeout);
          clickableTimeout = null;
        }
        // Make buttons clickable after 0.5 seconds
        clickableTimeout = setTimeout(() => {
          isClickable.value = true;
        }, 500);
        // Auto-collapse after 5 seconds
        autoCollapseTimeout = setTimeout(() => {
          isExpanded.value = false;
          isClickable.value = false;
        }, 5000);
      }
    };

    return {
      isExpanded,
      isClickable,
      isOffline,
      toggleExpanded,
      onMouseEnter,
      onMouseLeave,
      onTouchStart,
      handleNavClick,
      handleNavClickToPath,
    };
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    },
  },
};
</script>

<style scoped>
.bottom-navigation {
  position: fixed;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  height: auto;
  min-height: 64px;
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.15),
    rgba(15, 23, 42, 0.12)
  );
  backdrop-filter: blur(30px) saturate(180%);
  -webkit-backdrop-filter: blur(30px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 2rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 99999 !important; /* Above encryption overlay (9999) but below modals (100000) */
  padding: 0;
  padding-bottom: env(safe-area-inset-bottom, 0px);
  width: 95%;
  max-width: none;
  min-width: auto;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  position: fixed; /* Ensure it's in the correct stacking context */
}

.bottom-navigation:not(.expanded) {
  width: 80px;
  height: 40px;
  min-height: 40px;
  border-radius: 20px;
  padding: 0;
  z-index: 99999 !important; /* Ensure z-index is applied in collapsed state */
}

.bottom-navigation.expanded {
  width: 95%;
  min-height: 64px;
  border-radius: 2rem;
  padding: 0.75rem 1rem;
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px));
  z-index: 99999 !important; /* Ensure z-index is applied in expanded state */
}

.bottom-nav-content {
  display: flex;
  align-items: center;
  justify-content: space-around;
  width: 100%;
  height: 100%;
  opacity: 0;
  transition: opacity 0.3s ease 0.1s;
  pointer-events: none;
}

.bottom-navigation:not(.expanded) .bottom-nav-content {
  pointer-events: none !important; /* Prevent clicks on nav items when collapsed */
}

.bottom-navigation.expanded .bottom-nav-content {
  opacity: 1;
  pointer-events: auto;
  transition: opacity 0.3s ease 0.1s;
}

.bottom-navigation:not(.expanded) .bottom-nav-content {
  opacity: 0;
  pointer-events: none;
}

.bottom-nav-collapsed-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
  z-index: 1;
}

.bottom-navigation:not(.expanded) .bottom-nav-collapsed-icon {
  opacity: 1;
  pointer-events: none;
}

.bottom-navigation.expanded .bottom-nav-collapsed-icon {
  opacity: 0;
  pointer-events: none;
}

.bottom-nav-collapsed-icon span {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #94a3b8;
  transition: color 0.2s ease;
}

.bottom-navigation:hover .bottom-nav-collapsed-icon span {
  color: #e6eef6;
}

.mobile-mode .bottom-navigation {
  display: flex !important;
  z-index: 99999 !important; /* Ensure z-index is applied when displayed in mobile mode */
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: none;
  border-radius: 12px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  font-size: 0.75rem;
  min-width: 50px;
  min-height: 50px;
  flex: 0 1 auto;
  max-width: 100px;
}

.bottom-nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e6eef6;
}

.bottom-nav-item.router-link-active {
  background: rgba(88, 166, 255, 0.15);
  color: #60a5fa;
}

.bottom-nav-item:disabled {
  pointer-events: none !important;
  opacity: 0.5;
  cursor: not-allowed;
}

.bottom-nav-item:disabled:hover {
  background: transparent;
  color: #94a3b8;
}

.bottom-nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.bottom-nav-label {
  font-size: 0.7rem;
  font-weight: 500;
  line-height: 1;
  text-align: center;
}
</style>
