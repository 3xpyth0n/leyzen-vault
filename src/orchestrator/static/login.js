(function () {
  "use strict";

  function withCacheBuster(urlString) {
    try {
      const url = new URL(urlString, window.location.origin);
      url.searchParams.set("cb", Date.now().toString());
      return url.toString();
    } catch (error) {
      const base = urlString.split("?")[0];
      return `${base}?cb=${Date.now()}`;
    }
  }

  function syncCaptchaOverlayImage(overlay, overlayImage, sourceImage) {
    if (
      overlay &&
      overlayImage &&
      overlay.classList.contains("captcha-overlay--visible") &&
      sourceImage &&
      sourceImage.src
    ) {
      overlayImage.src = sourceImage.src;
    }
  }

  function showCaptchaOverlay(overlay, overlayImage, sourceImage) {
    if (!overlay || !overlayImage || !sourceImage) {
      return;
    }

    overlayImage.src = sourceImage.src;
    overlay.classList.add("captcha-overlay--visible");
    overlay.removeAttribute("aria-hidden");
    document.body.classList.add("captcha-overlay-open");
  }

  function hideCaptchaOverlay(overlay) {
    if (!overlay) {
      return;
    }

    overlay.classList.remove("captcha-overlay--visible");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("captcha-overlay-open");
  }

  function requestCaptchaRefresh(
    image,
    nonceInput,
    captchaInput,
    loginCsrfInput,
    overlay,
    overlayImage,
  ) {
    if (!image) {
      return;
    }

    const headers = { Accept: "application/json" };
    if (loginCsrfInput && loginCsrfInput.value) {
      headers["X-Login-CSRF"] = loginCsrfInput.value;
    }

    fetch("/orchestrator/captcha-refresh", {
      method: "POST",
      credentials: "same-origin",
      headers,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to refresh captcha");
        }
        return response.json();
      })
      .then((data) => {
        if (data && data.nonce && nonceInput) {
          nonceInput.value = data.nonce;
        }
        if (data && data.image_url) {
          image.dataset.baseUrl = data.image_url;
          image.src = withCacheBuster(data.image_url);
        } else {
          const fallback = image.dataset.baseUrl || image.src;
          image.src = withCacheBuster(fallback);
        }
        syncCaptchaOverlayImage(overlay, overlayImage, image);
        if (captchaInput) {
          captchaInput.value = "";
          captchaInput.focus();
        }
      })
      .catch(() => {
        const fallback = image.dataset.baseUrl || image.src;
        image.src = withCacheBuster(fallback);
        syncCaptchaOverlayImage(overlay, overlayImage, image);
      });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.querySelector(".captcha-refresh");
    const captchaImage = document.querySelector(".captcha-image");
    const captchaInput = document.querySelector("#captcha");
    const nonceInput = document.querySelector("input[data-captcha-nonce]");
    const loginCsrfInput = document.querySelector("input[data-login-csrf]");
    const overlay = document.querySelector("[data-captcha-overlay]");
    const overlayImage = overlay
      ? overlay.querySelector("[data-captcha-overlay-image]")
      : null;
    const loginForm = document.querySelector("form[method='post']");
    const submitButton = document.getElementById("login-submit-btn");
    const btnText = submitButton?.querySelector(".btn-text");
    const btnSpinner = submitButton?.querySelector(".btn-spinner");

    if (captchaImage) {
      captchaImage.dataset.baseUrl = captchaImage.getAttribute("src") || "";
    }

    // Convert captcha input to uppercase automatically
    if (captchaInput) {
      captchaInput.addEventListener("input", function (event) {
        const input = event.target;
        const cursorPosition = input.selectionStart;
        input.value = input.value.toUpperCase();
        // Restore cursor position after converting to uppercase
        input.setSelectionRange(cursorPosition, cursorPosition);
      });
    }

    // Handle form submission with loading state
    if (loginForm && submitButton) {
      loginForm.addEventListener("submit", function (event) {
        if (submitButton.disabled) {
          event.preventDefault();
          return;
        }
        submitButton.disabled = true;
        if (btnText) btnText.classList.add("hidden");
        if (btnSpinner) btnSpinner.classList.remove("hidden");
      });
    }

    if (refreshButton && captchaImage) {
      refreshButton.addEventListener("click", (event) => {
        event.preventDefault();
        requestCaptchaRefresh(
          captchaImage,
          nonceInput,
          captchaInput,
          loginCsrfInput,
          overlay,
          overlayImage,
        );
      });
    }

    if (captchaImage && overlay && overlayImage) {
      captchaImage.addEventListener("click", (event) => {
        event.preventDefault();
        showCaptchaOverlay(overlay, overlayImage, captchaImage);
      });

      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
          hideCaptchaOverlay(overlay);
        }
      });

      overlayImage.addEventListener("click", (event) => {
        event.stopPropagation();
      });

      document.addEventListener("keydown", (event) => {
        if (
          event.key === "Escape" &&
          overlay.classList.contains("captcha-overlay--visible")
        ) {
          hideCaptchaOverlay(overlay);
        }
      });
    }
  });

  const passwordToggle = document.querySelector("[data-password-toggle]");
  const passwordInput = document.getElementById("password");

  if (passwordToggle && passwordInput) {
    const showIcon = passwordToggle.querySelector(
      ".password-toggle-icon--show",
    );
    const hideIcon = passwordToggle.querySelector(
      ".password-toggle-icon--hide",
    );

    if (showIcon && hideIcon) {
      passwordToggle.addEventListener("click", function (event) {
        event.preventDefault();
        const isPassword = passwordInput.type === "password";

        if (isPassword) {
          passwordInput.type = "text";
          passwordToggle.setAttribute("aria-label", "Hide password");
          passwordToggle.classList.add("is-visible");
        } else {
          passwordInput.type = "password";
          passwordToggle.setAttribute("aria-label", "Show password");
          passwordToggle.classList.remove("is-visible");
        }
      });
    }
  }
})();
