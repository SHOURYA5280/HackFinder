const DATA = __HACKATHON_DATA__;

const ACTIVE_DATA = DATA.filter(
  (hackathon) => hackathon.status === "open" || hackathon.status === "running",
);

const state = { status: "all", mode: "all", date: "" };

function formatSource(h) {
  return h.source || "Unknown";
}

const MONTHS = {
  jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
  jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
};

function eventStartTime(eventDates) {
  const range = eventDateRange(eventDates);
  return range ? range.start.getTime() : Number.POSITIVE_INFINITY;
}

function eventDateRange(eventDates, fallbackYear = new Date().getFullYear()) {
  const text = eventDates || "";
  const monthPattern = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?";
  const rangeMatch = text.match(new RegExp(String.raw`\b(${monthPattern})\s+(\d{1,2})\s*[-\u2010\u2013\u2014\uFFFD]\s*(?:(${monthPattern})\s+)?(\d{1,2})`, "i"));
  const singleMatch = text.match(new RegExp(`\\b(${monthPattern})\\s+(\\d{1,2})`, "i"));
  const match = rangeMatch || singleMatch;
  if (!match) return null;

  const yearMatch = text.match(/\b(20\d{2})\b/);
  const year = yearMatch ? Number(yearMatch[1]) : fallbackYear;
  const startMonth = MONTHS[match[1].slice(0, 3).toLowerCase()];
  const startDay = Number(match[2]);
  const endMonth = rangeMatch && match[3]
    ? MONTHS[match[3].slice(0, 3).toLowerCase()]
    : startMonth;
  const endDay = rangeMatch ? Number(match[4]) : startDay;
  const start = new Date(year, startMonth, startDay);
  const end = new Date(year + (endMonth < startMonth ? 1 : 0), endMonth, endDay);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return { start, end };
}

function runsOnSelectedDate(eventDates, selectedDate) {
  if (!selectedDate) return true;
  const [year, month, day] = selectedDate.split("-").map(Number);
  const selected = new Date(year, month - 1, day);
  const eventHasYear = /\b20\d{2}\b/.test(eventDates || "");
  const candidateYears = eventHasYear ? [year] : [year - 1, year, year + 1];
  return candidateYears.some((candidateYear) => {
    const range = eventDateRange(eventDates, candidateYear);
    return range && selected >= range.start && selected <= range.end;
  });
}

function sortByEventDate(hackathons) {
  return [...hackathons].sort((a, b) => {
    const timeDifference = eventStartTime(a.event_dates) - eventStartTime(b.event_dates);
    return timeDifference || a.title.localeCompare(b.title);
  });
}

function render() {
  const grid = document.getElementById("grid");
  const emptyState = document.getElementById("empty-state");
  grid.innerHTML = "";

  const filtered = sortByEventDate(ACTIVE_DATA.filter((h) => {
    if (state.status !== "all" && h.status !== state.status) return false;
    if (state.mode !== "all") {
      const m = (h.modes || "").toLowerCase();
      if (state.mode === "remote" && m !== "remote") return false;
      if (state.mode === "in-person" && !["in-person", "in person"].includes(m) && !(m === "" && h.location && h.location.toLowerCase() !== "online")) return false;
      if (state.mode === "hybrid" && m !== "hybrid") return false;
    }
    if (!runsOnSelectedDate(h.event_dates, state.date)) return false;
    return true;
  }));

  document.getElementById("result-count").textContent = filtered.length;
  emptyState.style.display = filtered.length === 0 ? "block" : "none";

  filtered.forEach((h) => {
    const card = document.createElement("div");
    card.className = "card";

    const desc =
      h.description && h.description.trim()
        ? h.description.trim()
        : "No description scraped for this one yet — check the official page for details.";

    card.innerHTML = `
      <div class="card-top">
        <h3>${escapeHtml(h.title)}</h3>
        <span class="status-tag ${h.status}">${h.status}</span>
      </div>
      <p class="card-desc">${escapeHtml(truncate(desc, 130))}</p>
      <div class="receipt">
        <div class="receipt-row"><span>Date</span><span>${escapeHtml(h.event_dates || "—")}</span></div>
        <div class="receipt-row"><span>Mode</span><span>${escapeHtml(h.modes || h.location || "—")}</span></div>
        <div class="receipt-row"><span>Source</span><span>${escapeHtml(formatSource(h))}</span></div>
      </div>
      <div class="card-footer">
        <span class="prize">${escapeHtml(truncate(h.prize_amount || "", 40))}</span>
        <a class="view-link" href="${h.hackathon_page_url}" target="_blank" rel="noopener">
          ${h.status === "open" ? "View & register →" : h.status === "running" ? "View — happening now →" : "View page →"}
        </a>
      </div>
    `;
    grid.appendChild(card);
  });
}

function truncate(str, n) {
  return str.length > n ? str.slice(0, n - 1).trim() + "…" : str;
}
function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

document.getElementById("filter-row").addEventListener("click", (e) => {
  const btn = e.target.closest(".chip");
  if (!btn) return;
  const group = btn.closest(".filter-group");
  const key = group.getAttribute("data-filter");
  state[key] = btn.getAttribute("data-value");
  group.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  btn.classList.add("active");
  render();
});

const eventDateInput = document.getElementById("event-date");
const clearDateButton = document.getElementById("clear-date");
eventDateInput.addEventListener("change", () => {
  state.date = eventDateInput.value;
  clearDateButton.hidden = !state.date;
  render();
});
clearDateButton.addEventListener("click", () => {
  eventDateInput.value = "";
  state.date = "";
  clearDateButton.hidden = true;
  render();
});

// Header stats
document.getElementById("last-checked-date").textContent = "__LAST_CHECKED__";
document.getElementById("open-total").textContent = ACTIVE_DATA.filter(
  (h) => h.status === "open" || h.status === "running",
).length;

render();
