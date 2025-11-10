/** @file animations.js - Animation utilities and helpers */

// Animation utilities for smooth transitions
const Animations = {
  /**
   * Fade in animation
   */
  fadeIn(element, duration = 200) {
    element.style.opacity = "0";
    element.style.display = "block";
    element.style.transition = `opacity ${duration}ms ease`;

    requestAnimationFrame(() => {
      element.style.opacity = "1";
    });

    return new Promise((resolve) => {
      setTimeout(resolve, duration);
    });
  },

  /**
   * Fade out animation
   */
  fadeOut(element, duration = 200) {
    element.style.transition = `opacity ${duration}ms ease`;
    element.style.opacity = "0";

    return new Promise((resolve) => {
      setTimeout(() => {
        element.style.display = "none";
        resolve();
      }, duration);
    });
  },

  /**
   * Slide down animation
   */
  slideDown(element, duration = 300) {
    element.style.maxHeight = "0";
    element.style.overflow = "hidden";
    element.style.display = "block";
    element.style.transition = `max-height ${duration}ms ease`;

    const height = element.scrollHeight;
    element.style.maxHeight = `${height}px`;

    return new Promise((resolve) => {
      setTimeout(() => {
        element.style.maxHeight = "";
        element.style.overflow = "";
        resolve();
      }, duration);
    });
  },

  /**
   * Slide up animation
   */
  slideUp(element, duration = 300) {
    element.style.maxHeight = `${element.scrollHeight}px`;
    element.style.overflow = "hidden";
    element.style.transition = `max-height ${duration}ms ease`;

    requestAnimationFrame(() => {
      element.style.maxHeight = "0";
    });

    return new Promise((resolve) => {
      setTimeout(() => {
        element.style.display = "none";
        element.style.maxHeight = "";
        element.style.overflow = "";
        resolve();
      }, duration);
    });
  },

  /**
   * Scale animation
   */
  scale(element, from = 0, to = 1, duration = 200) {
    element.style.transform = `scale(${from})`;
    element.style.transition = `transform ${duration}ms ease`;

    requestAnimationFrame(() => {
      element.style.transform = `scale(${to})`;
    });

    return new Promise((resolve) => {
      setTimeout(resolve, duration);
    });
  },

  /**
   * Skeleton loading animation
   */
  createSkeleton(type = "line", count = 1) {
    const skeleton = document.createElement("div");
    skeleton.className = "skeleton";

    if (type === "line") {
      skeleton.className += " skeleton-line";
    } else if (type === "circle") {
      skeleton.className += " skeleton-circle";
    } else if (type === "rect") {
      skeleton.className += " skeleton-rect";
    }

    const container = document.createElement("div");
    container.className = "skeleton-container";

    for (let i = 0; i < count; i++) {
      const clone = skeleton.cloneNode(true);
      if (i > 0 && type === "line") {
        clone.style.width = `${Math.random() * 40 + 60}%`;
      }
      container.appendChild(clone);
    }

    return container;
  },

  /**
   * Shake animation for errors
   */
  shake(element, duration = 500) {
    element.style.animation = "shake 0.5s ease-in-out";

    return new Promise((resolve) => {
      setTimeout(() => {
        element.style.animation = "";
        resolve();
      }, duration);
    });
  },

  /**
   * Ripple effect on click
   */
  ripple(event, element) {
    const ripple = document.createElement("span");
    const rect = element.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;

    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    ripple.className = "ripple";

    element.style.position = "relative";
    element.style.overflow = "hidden";
    element.appendChild(ripple);

    requestAnimationFrame(() => {
      ripple.style.transform = "scale(2)";
      ripple.style.opacity = "0";
    });

    setTimeout(() => {
      ripple.remove();
    }, 600);
  },
};

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.Animations = Animations;
}
