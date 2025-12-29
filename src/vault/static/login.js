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

  function requestCaptchaRefresh(
    image,
    nonceInput,
    captchaInput,
    loginCsrfInput,
  ) {
    if (!image) {
      return;
    }

    const headers = { Accept: "application/json" };
    const csrfToken =
      loginCsrfInput?.value ||
      document.querySelector('input[name="login_csrf_token"]')?.value ||
      document.querySelector("input[data-login-csrf]")?.value;

    if (csrfToken) {
      headers["X-Login-CSRF"] = csrfToken;
    }

    // Retry logic for captcha refresh
    let retryCount = 0;
    const maxRetries = 3;

    function attemptRefresh() {
      fetch("/api/auth/captcha-refresh", {
        method: "POST",
        credentials: "same-origin",
        headers,
      })
        .then((response) => {
          if (!response.ok) {
            if (response.status === 400 && retryCount < maxRetries) {
              retryCount++;

              setTimeout(attemptRefresh, 500);
              return;
            }
            throw new Error("Failed to refresh captcha");
          }
          return response.json();
        })
        .then((data) => {
          if (!data) return; // Skip if retry was triggered

          if (data && data.nonce && nonceInput) {
            nonceInput.value = data.nonce;
          }
          if (data && data.image_url) {
            image.dataset.baseUrl = data.image_url;
            image.src = withCacheBuster(data.image_url);
          } else if (data && data.nonce) {
            // Use nonce to build image URL if image_url not provided
            const imageUrl = `/api/auth/captcha-image?nonce=${data.nonce}`;
            image.dataset.baseUrl = imageUrl;
            image.src = withCacheBuster(imageUrl);
          } else {
            const fallback = image.dataset.baseUrl || image.src;
            image.src = withCacheBuster(fallback);
          }
          if (captchaInput) {
            captchaInput.value = "";
            captchaInput.focus();
          }
          retryCount = 0; // Reset retry count on success
        })
        .catch((error) => {
          // Only fallback if we've exhausted retries
          if (retryCount >= maxRetries) {
            const fallback = image.dataset.baseUrl || image.src;
            image.src = withCacheBuster(fallback);
          }
        });
    }

    attemptRefresh();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const captchaWrapper = document.querySelector("[data-captcha-wrapper]");
    const captchaImage = document.querySelector(".captcha-image");
    const captchaInput = document.querySelector("#captcha");
    const nonceInput = document.querySelector("input[data-captcha-nonce]");
    const loginCsrfInput = document.querySelector("input[data-login-csrf]");
    const loginForm = document.querySelector("form[method='post']");
    const submitButton = document.getElementById("login-submit-btn");
    const btnText = submitButton?.querySelector(".btn-text");
    const btnSpinner = submitButton?.querySelector(".btn-spinner");
    const toast = document.querySelector("[data-captcha-toast]");

    let pendingRefresh = false;
    let toastTimeout = null;
    let countdownInterval = null;
    let toastCountdown = 3;

    const hideToast = () => {
      if (toast) {
        toast.classList.remove("show");
        setTimeout(() => {
          if (toast) {
            toast.style.display = "none";
          }
        }, 500);
      }
      pendingRefresh = false;
      toastCountdown = 3;
      if (toast) {
        toast.textContent = "Tap again to refresh (3s)";
      }
      if (toastTimeout) {
        clearTimeout(toastTimeout);
        toastTimeout = null;
      }
      if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
      }
    };

    const startCountdown = () => {
      toastCountdown = 3;
      if (toast) {
        toast.textContent = `Tap again to refresh (${toastCountdown}s)`;
      }
      if (countdownInterval) {
        clearInterval(countdownInterval);
      }
      countdownInterval = setInterval(() => {
        toastCountdown--;
        if (toast) {
          toast.textContent = `Tap again to refresh (${toastCountdown}s)`;
        }
        if (toastCountdown <= 0) {
          hideToast();
        }
      }, 1000);
    };

    const showToast = () => {
      if (toast) {
        toast.style.display = "flex";
        requestAnimationFrame(() => {
          if (toast) {
            toast.classList.add("show");
          }
        });
      }
      pendingRefresh = true;
      startCountdown();
      toastTimeout = setTimeout(() => {
        hideToast();
      }, 3000);
    };

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

    // Handle captcha refresh on click/touch
    if (captchaWrapper && captchaImage) {
      const handleCaptchaClick = (event) => {
        event.preventDefault();
        event.stopPropagation();

        // Uniform behavior: double tap/click for everyone
        if (pendingRefresh) {
          // Second tap/click: confirm refresh
          hideToast();
          requestCaptchaRefresh(
            captchaImage,
            nonceInput,
            captchaInput,
            loginCsrfInput,
          );
        } else {
          // First tap/click: show toast with countdown
          showToast();
        }
      };

      captchaWrapper.addEventListener("click", handleCaptchaClick);

      // Show/hide hover overlay with fade
      const hoverOverlay = captchaWrapper.querySelector(
        ".captcha-hover-overlay",
      );
      if (hoverOverlay) {
        captchaWrapper.addEventListener("mouseenter", () => {
          hoverOverlay.style.opacity = "0";
          requestAnimationFrame(() => {
            hoverOverlay.style.opacity = "1";
          });
        });
        captchaWrapper.addEventListener("mouseleave", () => {
          hoverOverlay.style.opacity = "0";
        });
      }
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
