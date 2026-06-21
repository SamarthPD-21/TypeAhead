(() => {
  "use strict";

  // ── Config ──────────────────────────────────────────────
  const API_BASE = window.location.protocol === "file:" ? "http://localhost:8000" : ""; 
  const DEBOUNCE_DELAY_MS = 120; 
  const MAX_RECENTS_COUNT = 6;
  const METRICS_POLL_INTERVAL_MS = 2000;

  // ── DOM References ──────────────────────────────────────
  const $input = document.getElementById("search-input");
  const $dropdown = document.getElementById("dropdown");
  const $wrapper = document.getElementById("search-wrapper");
  const $trending = document.getElementById("trending-list");
  const $recentSec = document.getElementById("recent-section");
  const $recentList = document.getElementById("recent-list");
  const $logsContainer = document.getElementById("terminal-logs");
  
  // Telemetry DOM Refs
  const $mHits = document.getElementById("m-hits");
  const $mMisses = document.getElementById("m-misses");
  const $mDb = document.getElementById("m-db");
  const $mLatency = document.getElementById("m-latency");
  const $mHitRate = document.getElementById("m-hit-rate");
  const $mHitRateBar = document.getElementById("m-hit-rate-bar");

  // Redis Nodes DOM Refs
  const redisNodes = {
    redis1: {
      val: document.getElementById("m-redis1-val"),
      bar: document.getElementById("m-redis1-bar"),
      rack: document.getElementById("rack-redis1")
    },
    redis2: {
      val: document.getElementById("m-redis2-val"),
      bar: document.getElementById("m-redis2-bar"),
      rack: document.getElementById("rack-redis2")
    },
    redis3: {
      val: document.getElementById("m-redis3-val"),
      bar: document.getElementById("m-redis3-bar"),
      rack: document.getElementById("rack-redis3")
    }
  };

  // ── Application State ───────────────────────────────────
  let activeSelectionIndex = -1;
  let suggestionCandidates = [];
  let inputDebounceTimer = null;
  let recentQueries = JSON.parse(localStorage.getItem("core_ta_recent") || "[]");
  let suggestAbortController = null;

  // ── Escape HTML Helper ──────────────────────────────────
  const escapeHtml = (str) => 
    str.replace(/[&<>"']/g, char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    })[char]);

  // ── Match Highlight Helper ──────────────────────────────
  function computeHighlightedText(text, query) {
    if (!query) return escapeHtml(text);
    const index = text.toLowerCase().indexOf(query.toLowerCase());
    if (index === -1) return escapeHtml(text);
    
    return (
      escapeHtml(text.slice(0, index)) + 
      "<mark>" + 
      escapeHtml(text.slice(index, index + query.length)) + 
      "</mark>" + 
      escapeHtml(text.slice(index + query.length))
    );
  }

  // ── System Console Logger ───────────────────────────────
  function addConsoleLog(message, type = "system") {
    const timestamp = new Date().toLocaleTimeString();
    const logElement = document.createElement("div");
    logElement.className = `log-line ${type}`;
    logElement.innerHTML = `[${timestamp}] ${message}`;
    
    $logsContainer.appendChild(logElement);
    
    // Auto-scroll to bottom of console logs
    $logsContainer.scrollTop = $logsContainer.scrollHeight;
    
    // Limit logs length in memory
    while ($logsContainer.children.length > 50) {
      $logsContainer.removeChild($logsContainer.firstChild);
    }
  }

  // ── Query Cache Routing Debugger ────────────────────────
  async function streamCacheRoutingInfo(prefix) {
    if (!prefix) return;
    try {
      const response = await fetch(`${API_BASE}/cache/debug?prefix=${encodeURIComponent(prefix)}`);
      const debugData = await response.json();
      
      const { node, cache_hit } = debugData;
      const type = cache_hit ? "cache-hit" : "cache-miss";
      const statusText = cache_hit ? "HIT" : "MISS";
      
      addConsoleLog(`[ROUTING] Prefix "${escapeHtml(prefix)}" routed to <strong>${node}</strong> (Status: ${statusText})`, type);
      
      // Flash LED on active Redis node rack
      if (redisNodes[node]) {
        const led = redisNodes[node].rack.querySelector(".rack-led");
        if (led) {
          led.classList.remove("flash-activity");
          void led.offsetWidth; // Trigger reflow to restart CSS animation
          led.classList.add("flash-activity");
        }
      }
    } catch (e) {
      // Fail silently
    }
  }

  // ── Fetch Autocomplete Suggestions ──────────────────────
  async function performSuggestionsFetch(queryPhrase) {
    if (suggestAbortController) suggestAbortController.abort();
    suggestAbortController = new AbortController();

    try {
      const startTime = performance.now();
      const response = await fetch(
        `${API_BASE}/suggest?q=${encodeURIComponent(queryPhrase)}`,
        { signal: suggestAbortController.signal }
      );
      const data = await response.json();
      const latencyMs = performance.now() - startTime;
      
      suggestionCandidates = data.suggestions || [];
      renderSuggestionsDropdown(queryPhrase, latencyMs);
      
      // Stream hash ring routing details to console
      streamCacheRoutingInfo(queryPhrase);
    } catch (e) {
      if (e.name !== "AbortError") {
        console.error("Suggestions retrieval failed", e);
      }
    }
  }

  // ── Suggestions Dropdown Rendering ─────────────────────
  function renderSuggestionsDropdown(query, latency) {
    if (suggestionCandidates.length === 0) {
      closeDropdown();
      return;
    }

    activeSelectionIndex = -1;
    const searchIconSvg = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    `;

    // Normalize scores to draw a relative bar representation
    const maxScore = Math.max(...suggestionCandidates.map(item => item.score), 1.0);

    let dropdownHtml = suggestionCandidates.map((item, index) => {
      const percentageScore = (item.score / maxScore) * 100;
      return `
        <div class="dropdown-item" data-idx="${index}">
          <span class="item-icon">${searchIconSvg}</span>
          <div class="item-text-box">
            <span class="item-text">${computeHighlightedText(item.text, query)}</span>
            <div class="dropdown-score-box">
              <div class="dropdown-score-bar-outer">
                <div class="dropdown-score-bar-inner" style="width: ${percentageScore}%"></div>
              </div>
              <span class="item-score">${item.score.toFixed(1)}</span>
            </div>
          </div>
        </div>
      `;
    }).join("");

    const isOptimalLatency = latency < 10;
    dropdownHtml += `
      <div class="dropdown-footer">
        <span class="dropdown-nav-hint">Use ↑ ↓ Arrow Keys to Navigate</span>
        <span class="latency-badge ${isOptimalLatency ? "fast" : ""}">
          ${latency.toFixed(1)} ms ${isOptimalLatency ? "⚡" : ""}
        </span>
      </div>
    `;

    $dropdown.innerHTML = dropdownHtml;
    $dropdown.classList.remove("hidden");

    // Dynamic click binding
    $dropdown.querySelectorAll(".dropdown-item").forEach(itemElement => {
      itemElement.addEventListener("click", () => {
        const itemIdx = parseInt(itemElement.dataset.idx);
        applySuggestionSelection(itemIdx);
      });
    });
  }

  function closeDropdown() {
    $dropdown.classList.add("hidden");
    $dropdown.innerHTML = "";
    activeSelectionIndex = -1;
    suggestionCandidates = [];
  }

  // ── Apply Autocomplete Selection ────────────────────────
  function applySuggestionSelection(index) {
    const candidate = suggestionCandidates[index];
    if (!candidate) return;
    
    $input.value = candidate.text;
    closeDropdown();
    persistSearchRecord(candidate.text);
  }

  // ── Persist Search Log ──────────────────────────────────
  async function persistSearchRecord(phrase) {
    const trimmedPhrase = phrase.trim();
    if (!trimmedPhrase) return;

    // Local storage history update
    recentQueries = [trimmedPhrase, ...recentQueries.filter(q => q !== trimmedPhrase)].slice(0, MAX_RECENTS_COUNT);
    localStorage.setItem("core_ta_recent", JSON.stringify(recentQueries));
    renderRecentQueriesDeck();

    addConsoleLog(`[INGEST] Submitted search: "${escapeHtml(trimmedPhrase)}"`);

    // Asynchronous backend submission (write-back aggregation buffer)
    try {
      await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmedPhrase })
      });
    } catch (e) {
      console.error("Search submission buffer failed", e);
    }
  }

  // ── Recent Searches Deck ────────────────────────────────
  function renderRecentQueriesDeck() {
    if (recentQueries.length === 0) {
      $recentSec.classList.add("hidden");
      return;
    }
    
    $recentSec.classList.remove("hidden");
    const clockIconSvg = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
      </svg>
    `;

    $recentList.innerHTML = recentQueries.map(phrase => 
      `<div class="recent-chip" data-phrase="${escapeHtml(phrase)}">${clockIconSvg}${escapeHtml(phrase)}</div>`
    ).join("");

    $recentList.querySelectorAll(".recent-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const queryVal = chip.dataset.phrase;
        $input.value = queryVal;
        $input.focus();
        performSuggestionsFetch(queryVal);
      });
    });
  }

  // ── Global Trending Queries ─────────────────────────────
  async function queryTrendingSearches() {
    try {
      const response = await fetch(`${API_BASE}/trending?limit=10`);
      const payload = await response.json();
      const items = payload.suggestions || [];
      
      const fireIconSvg = `
        <svg class="trending-fire" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>
        </svg>
      `;

      if (items.length === 0) {
        $trending.innerHTML = `<div class="trending-skeleton">No trending queries recorded yet.</div>`;
        return;
      }

      $trending.innerHTML = items.map((item, index) => `
        <div class="trending-card-item" data-phrase="${escapeHtml(item.text)}">
          <div class="trending-card-top">
            <span class="trending-badge">${index + 1}</span>
            ${fireIconSvg}
          </div>
          <span class="trending-card-text">${escapeHtml(item.text)}</span>
          <span class="trending-card-score">${item.score.toFixed(1)} score</span>
        </div>
      `).join("");

      $trending.querySelectorAll(".trending-card-item").forEach(card => {
        card.addEventListener("click", () => {
          const phrase = card.dataset.phrase;
          $input.value = phrase;
          $input.focus();
          performSuggestionsFetch(phrase);
        });
      });
    } catch (e) {
      console.error("Trending queries fetch failed", e);
    }
  }

  // ── System Metrics & Cluster Health ─────────────────────
  async function fetchTelemetryMetrics() {
    try {
      const response = await fetch(`${API_BASE}/metrics`);
      const metrics = await response.json();
      
      // Update Core Counters
      $mHits.textContent = metrics.cache_hits ?? "0";
      $mMisses.textContent = metrics.cache_misses ?? "0";
      $mDb.textContent = metrics.db_queries ?? "0";
      
      const latencyVal = metrics.average_latency_ms;
      $mLatency.textContent = latencyVal != null ? `${latencyVal.toFixed(1)} ms` : "—";
      
      // Update Cache Hit Rate Gauge
      const hitRatePct = metrics.cache_hit_rate_pct ?? 0.0;
      $mHitRate.textContent = `${hitRatePct.toFixed(1)}%`;
      $mHitRateBar.style.width = `${hitRatePct}%`;
      
      // Update Redis Node Status & Key Counts
      if (metrics.redis_nodes) {
        // Find maximum key count to scale node occupancy bars relatively
        const nodeValues = Object.values(metrics.redis_nodes).filter(v => typeof v === "number");
        const maxKeys = Math.max(...nodeValues, 10); // Minimum scale floor of 10 keys
        
        for (const [nodeId, keyCount] of Object.entries(metrics.redis_nodes)) {
          const nodeDom = redisNodes[nodeId];
          if (nodeDom) {
            if (typeof keyCount === "number") {
              nodeDom.val.textContent = `${keyCount} ${keyCount === 1 ? "key" : "keys"}`;
              const barPercentage = Math.min((keyCount / maxKeys) * 100, 100);
              nodeDom.bar.style.width = `${barPercentage}%`;
              
              // Ensure LED active styling
              const led = nodeDom.rack.querySelector(".rack-led");
              if (led) {
                led.className = "rack-led node-active";
              }
            } else {
              nodeDom.val.textContent = "unreachable";
              nodeDom.bar.style.width = "0%";
              const led = nodeDom.rack.querySelector(".rack-led");
              if (led) {
                led.className = "rack-led"; // Turn off LED
              }
            }
          }
        }
      }
    } catch (e) {
      console.warn("Failed to fetch system telemetry", e);
    }
  }

  // ── DOM Listeners ───────────────────────────────────────
  
  // Real-time Input Debouncer
  $input.addEventListener("input", () => {
    clearTimeout(inputDebounceTimer);
    const query = $input.value.trim();
    if (query.length === 0) {
      closeDropdown();
      return;
    }
    inputDebounceTimer = setTimeout(() => performSuggestionsFetch(query), DEBOUNCE_DELAY_MS);
  });

  // Keyboard navigation inside dropdown list
  $input.addEventListener("keydown", (event) => {
    // If suggestions are closed, capture Enter key for raw search submission
    if ($dropdown.classList.contains("hidden")) {
      if (event.key === "Enter") {
        const query = $input.value.trim();
        if (query) persistSearchRecord(query);
      }
      return;
    }

    const dropdownItems = $dropdown.querySelectorAll(".dropdown-item");

    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeSelectionIndex = Math.min(activeSelectionIndex + 1, dropdownItems.length - 1);
      syncActiveDropdownSelection(dropdownItems);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeSelectionIndex = Math.max(activeSelectionIndex - 1, -1);
      syncActiveDropdownSelection(dropdownItems);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeSelectionIndex >= 0) {
        applySuggestionSelection(activeSelectionIndex);
      } else {
        const query = $input.value.trim();
        if (query) {
          closeDropdown();
          persistSearchRecord(query);
        }
      }
    } else if (event.key === "Escape") {
      closeDropdown();
    }
  });

  function syncActiveDropdownSelection(elements) {
    elements.forEach((el, idx) => el.classList.toggle("active", idx === activeSelectionIndex));
    if (activeSelectionIndex >= 0 && suggestionCandidates[activeSelectionIndex]) {
      $input.value = suggestionCandidates[activeSelectionIndex].text;
    }
  }

  // Close dropdown upon user clicking outside the search context wrapper
  document.addEventListener("click", (event) => {
    if (!$wrapper.contains(event.target)) {
      closeDropdown();
    }
  });

  // Keyboard Hotkey listener: Ctrl+K or Cmd+K focuses and selects search input
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "k") {
      event.preventDefault();
      $input.focus();
      $input.select();
      addConsoleLog("[HOTKEY] Terminal focus requested");
    }
  });

  // ── Initialization ──────────────────────────────────────
  renderRecentQueriesDeck();
  queryTrendingSearches();
  
  // Start metrics telemetry polling loop
  fetchTelemetryMetrics();
  setInterval(fetchTelemetryMetrics, METRICS_POLL_INTERVAL_MS);
  
  // Periodically refresh trending list (every 10s) to show live updates from background writes
  setInterval(queryTrendingSearches, 10000);
})();
