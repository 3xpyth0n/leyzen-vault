// Elements
const pre = document.getElementById("log");
const refreshBtn = document.getElementById("refreshBtn");
const periodButtons = document.querySelectorAll(".period-btn");
const customRange = document.getElementById("customRange");
const startDateEl = document.getElementById("startDate");
const endDateEl = document.getElementById("endDate");
const applyCustomBtn = document.getElementById("applyCustom");
const autoSwitch = document.getElementById("autoSwitch");
const linesMeta = document.getElementById("linesMeta");
const searchInput = document.getElementById("searchInput");
const emptyState = document.getElementById("emptyState");
const searchResults = document.getElementById("searchResults");
const btnText = refreshBtn?.querySelector(".btn-text");
const btnSpinner = refreshBtn?.querySelector(".btn-spinner");

// State
let allLogs = pre && pre.textContent ? pre.textContent : "";
let selectedPeriod = "day"; // default
let autoRefreshHandle = null;
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
      searchResults.textContent = `${totalMatches} match${totalMatches !== 1 ? "es" : ""} found`;
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
    updateMeta(0);
    if (scrollBottom) {
      pre.scrollTop = 0;
    }
    return;
  }

  emptyState.classList.remove("is-visible");
  pre.removeAttribute("aria-hidden");
  pre.textContent = filtered.join("\n");
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
  btn.addEventListener("click", () => {
    periodButtons.forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-pressed", "false");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-pressed", "true");

    selectedPeriod = btn.dataset.period;
    const shouldShowCustom = selectedPeriod === "custom";
    customRange.classList.toggle("is-hidden", !shouldShowCustom);
    // if switching to custom, prefill start/end with sensible defaults
    if (shouldShowCustom) {
      const now = new Date();
      const iso = (d) => d.toISOString().slice(0, 10);
      // default last 7 days
      startDateEl.value = iso(
        new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7),
      );
      endDateEl.value = iso(now);
    }

    // apply filter (does not refetch automatically except when you want latest data)
    displayLogs(true);
  });
});

applyCustomBtn.addEventListener("click", () => {
  displayLogs(true);
});

// Auto refresh toggle
autoSwitch.addEventListener("click", () => {
  autoSwitch.classList.toggle("on");
  if (autoSwitch.classList.contains("on")) {
    // start 1s polling without changing scroll position
    autoRefreshHandle = setInterval(() => fetchLogs(false), 1000);
  } else {
    clearInterval(autoRefreshHandle);
    autoRefreshHandle = null;
  }
});

searchInput.addEventListener("input", (event) => {
  searchTerm = event.target.value.trim();
  displayLogs(false);
});

// initial boot: ensure Day is active and fetch logs
(function init() {
  // mark default active
  periodButtons.forEach((b) => {
    if (b.dataset.period === "day") {
      b.classList.add("active");
      b.setAttribute("aria-pressed", "true");
    } else {
      b.setAttribute("aria-pressed", "false");
    }
  });
  // initial fetch (will scroll to bottom)
  fetchLogs(true);
})();
