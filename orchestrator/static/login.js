(function () {
  "use strict";

  function updateCaptchaImage(image) {
    if (!image) {
      return;
    }
    try {
      const url = new URL(image.src, window.location.origin);
      url.searchParams.set("renew", "1");
      url.searchParams.set(
        "nonce",
        `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      );
      image.src = url.toString();
    } catch (error) {
      // Fallback for older browsers without URL support
      image.src = `${image.src.split("?")[0]}?renew=1&nonce=${Date.now()}`;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.querySelector(".captcha-refresh");
    const captchaImage = document.querySelector(".captcha-image");
    const captchaInput = document.querySelector("#captcha");

    if (refreshButton && captchaImage) {
      refreshButton.addEventListener("click", () => {
        updateCaptchaImage(captchaImage);
        if (captchaInput) {
          captchaInput.value = "";
          captchaInput.focus();
        }
      });
    }
  });
})();
