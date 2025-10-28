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
        if (captchaInput) {
          captchaInput.value = "";
          captchaInput.focus();
        }
      })
      .catch(() => {
        const fallback = image.dataset.baseUrl || image.src;
        image.src = withCacheBuster(fallback);
      });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.querySelector(".captcha-refresh");
    const captchaImage = document.querySelector(".captcha-image");
    const captchaInput = document.querySelector("#captcha");
    const nonceInput = document.querySelector("input[data-captcha-nonce]");
    const loginCsrfInput = document.querySelector("input[data-login-csrf]");

    if (captchaImage) {
      captchaImage.dataset.baseUrl = captchaImage.getAttribute("src") || "";
    }

    if (refreshButton && captchaImage) {
      refreshButton.addEventListener("click", (event) => {
        event.preventDefault();
        requestCaptchaRefresh(
          captchaImage,
          nonceInput,
          captchaInput,
          loginCsrfInput,
        );
      });
    }
  });
})();
