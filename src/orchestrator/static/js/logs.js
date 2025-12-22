// Elements - wait for DOM
let pre,
  refreshBtn,
  periodButtons,
  customRange,
  startDateEl,
  endDateEl,
  applyCustomBtn;
let linesMeta, searchInput, emptyState, searchResults, logArea;
let btnText, btnSpinner;

function initElements() {
  pre = document.getElementById("log");
  refreshBtn = document.getElementById("refreshBtn");
  periodButtons = document.querySelectorAll(".period-btn");
  customRange = document.getElementById("customRange");
  startDateEl = document.getElementById("startDate");
  endDateEl = document.getElementById("endDate");
  applyCustomBtn = document.getElementById("applyCustom");
  linesMeta = document.getElementById("linesMeta");
  searchInput = document.getElementById("searchInput");
  emptyState = document.getElementById("emptyState");
  searchResults = document.getElementById("searchResults");
  logArea = document.querySelector(".log-area");
  btnText = refreshBtn?.querySelector(".btn-text");
  btnSpinner = refreshBtn?.querySelector(".btn-spinner");
}

// Initialize elements immediately
initElements();

// State
let allLogs = pre && pre.textContent ? pre.textContent : "";
let selectedPeriod = "day"; // default
let isFetching = false;
let firstLoad = true;
let searchTerm = "";

// Helpers: parse date from a log line like: [2025-10-10 19:16:13]
function parseLogDate(line) {
  const m = line.match(/^\[(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})/);
  if (!m) return null;
  // create local date
  const s = m[1] + "T" + m[2];
  const d = new Date(s);
  if (isNaN(d)) return null;
  return d;
}

// Update metadata (lines count)
function updateMeta(count) {
  linesMeta.textContent = `Lines: ${count}`;
}

// Update log area padding based on whether there are logs
function updateLogAreaPadding(hasLogs) {
  const area = logArea || document.querySelector(".log-area");
  if (!area) {
    console.error("Could not find .log-area element in updateLogAreaPadding!");
    return;
  }
  if (hasLogs) {
    area.style.padding = "0px";
    area.classList.add("has-logs");
  } else {
    area.style.padding = "3rem";
    area.classList.remove("has-logs");
  }
}

// Display filtered logs (client-side)
function displayLogs(scrollBottom = false) {
  const lines = allLogs
    ? allLogs.split(/\r?\n/).filter((line) => line.length > 0)
    : [];
  const now = new Date();
  let filtered = [];

  if (selectedPeriod === "custom") {
    const startVal = startDateEl.value;
    const endVal = endDateEl.value;
    if (!startVal || !endVal) {
      // if custom but no dates set, show none and prompt user
      filtered = [];
    } else {
      const start = new Date(startVal + "T00:00:00");
      const end = new Date(endVal + "T23:59:59");
      filtered = lines.filter((line) => {
        const d = parseLogDate(line);
        return d && d >= start && d <= end;
      });
    }
  } else {
    filtered = lines.filter((line) => {
      const d = parseLogDate(line);
      if (!d) return false;
      if (selectedPeriod === "day") {
        return (
          d.getFullYear() === now.getFullYear() &&
          d.getMonth() === now.getMonth() &&
          d.getDate() === now.getDate()
        );
      } else if (selectedPeriod === "month") {
        return (
          d.getFullYear() === now.getFullYear() &&
          d.getMonth() === now.getMonth()
        );
      } else if (selectedPeriod === "year") {
        return d.getFullYear() === now.getFullYear();
      }
      return false;
    });
  }

  if (searchTerm) {
    const needle = searchTerm.toLowerCase();
    filtered = filtered.filter((line) => line.toLowerCase().includes(needle));
  }

  // Update search results counter
  if (searchResults) {
    if (searchTerm) {
      const totalMatches = filtered.length;
      searchResults.textContent = `${totalMatches} match${
        totalMatches !== 1 ? "es" : ""
      } found`;
      searchResults.classList.remove("hidden");
    } else {
      searchResults.textContent = "";
      searchResults.classList.add("hidden");
    }
  }

  if (filtered.length === 0) {
    pre.textContent = "";
    emptyState.classList.add("is-visible");
    pre.setAttribute("aria-hidden", "true");
    // Force padding to 3rem when no logs
    const area = document.querySelector(".log-area");
    if (area) {
      area.style.setProperty("padding", "3rem", "important");
      area.classList.remove("has-logs");
    } else {
      console.error("Could not find .log-area element!");
    }
    updateMeta(0);
    if (scrollBottom) {
      pre.scrollTop = 0;
    }
    return;
  }

  emptyState.classList.remove("is-visible");
  pre.removeAttribute("aria-hidden");
  pre.textContent = filtered.join("\n");
  // Force padding to 0 when logs are displayed
  const area = document.querySelector(".log-area");
  if (area) {
    area.style.setProperty("padding", "0px", "important");
    area.classList.add("has-logs");
  } else {
    console.error("Could not find .log-area element!");
  }
  updateMeta(filtered.length);

  if (scrollBottom) {
    pre.scrollTop = pre.scrollHeight;
  }
}

// Fetch logs from backend (raw endpoint)
async function fetchLogs(scrollBottom = false) {
  if (isFetching) return;
  isFetching = true;

  // Show loading state
  if (refreshBtn) {
    refreshBtn.disabled = true;
    if (btnText) btnText.classList.add("hidden");
    if (btnSpinner) btnSpinner.classList.remove("hidden");
  }

  try {
    const resp = await fetch("/orchestrator/logs/raw", {
      cache: "no-store",
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const text = await resp.text();
    allLogs = text;
    // first load: scroll bottom
    if (firstLoad) {
      displayLogs(true);
      firstLoad = false;
    } else {
      displayLogs(scrollBottom);
    }
  } catch (err) {
    console.error("Failed to fetch logs:", err);
  } finally {
    isFetching = false;
    // Hide loading state
    if (refreshBtn) {
      refreshBtn.disabled = false;
      if (btnText) btnText.classList.remove("hidden");
      if (btnSpinner) btnSpinner.classList.add("hidden");
    }
  }
}

// UI wiring
refreshBtn.addEventListener("click", () => {
  fetchLogs(true);
});

periodButtons.forEach((btn) => {
  btn.addEventListener("click", (e) => {
    const isCustom = btn.dataset.period === "custom";

    // If clicking on custom, toggle dropdown instead of immediately selecting
    if (isCustom) {
      e.stopPropagation();
      const isActive = btn.classList.contains("active");
      const isDropdownVisible = !customRange.classList.contains("is-hidden");

      if (!isActive) {
        // Activate custom period and show dropdown
        periodButtons.forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        selectedPeriod = "custom";
        customRange.classList.remove("is-hidden");

        // Prefill dates if not already set
        if (!startDateEl.value || !endDateEl.value) {
          const now = new Date();
          const iso = (d) => d.toISOString().slice(0, 10);
          startDateEl.value = iso(
            new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7),
          );
          endDateEl.value = iso(now);
        }
      } else if (isDropdownVisible) {
        // If already active and dropdown visible, close it
        customRange.classList.add("is-hidden");
      } else {
        // If active but dropdown hidden, show it
        customRange.classList.remove("is-hidden");
      }
    } else {
      // For other periods, normal behavior
      periodButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      selectedPeriod = btn.dataset.period;
      customRange.classList.add("is-hidden");

      // apply filter (does not refetch automatically except when you want latest data)
      displayLogs(true);
    }
  });
});

// Close dropdown when clicking outside
document.addEventListener("click", (e) => {
  const customWrapper = document.querySelector(".custom-period-wrapper");
  if (customWrapper && !customWrapper.contains(e.target)) {
    customRange.classList.add("is-hidden");
  }
});

applyCustomBtn.addEventListener("click", () => {
  displayLogs(true);
  // Close dropdown after applying
  customRange.classList.add("is-hidden");
});

searchInput.addEventListener("input", (event) => {
  searchTerm = event.target.value.trim();
  displayLogs(false);
});

// initial boot: ensure Day is active and fetch logs
function init() {
  // Ensure elements are initialized
  initElements();

  // mark default active
  periodButtons.forEach((b) => {
    if (b.dataset.period === "day") {
      b.classList.add("active");
      b.setAttribute("aria-pressed", "true");
    } else {
      b.setAttribute("aria-pressed", "false");
    }
  });

  // Set initial state based on existing content
  setTimeout(() => {
    const area = document.querySelector(".log-area");
    if (area) {
      if (allLogs && allLogs.trim().length > 0) {
        area.style.padding = "0px";
        area.classList.add("has-logs");
      } else {
        area.style.padding = "3rem";
        area.classList.remove("has-logs");
      }
    }
  }, 100);

  // initial fetch (will scroll to bottom)
  fetchLogs(true);
}

// Run init when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

setTimeout(() => {
  const testArea = document.querySelector(".log-area");
  if (testArea) {
    const hasContent = allLogs && allLogs.trim().length > 0;
    updateLogAreaPadding(hasContent);
  }
}, 1000);
