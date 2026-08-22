/* ═══════════════════════════════════════════════════════════════
   Travora — Trip Calendar JS  (v2 — live data)
   ---------------------------------------------------------------
   Data source: GET /api/trips  (same endpoint as my-trips.html)
   Backend trip schema:
     { id, destination, from_city, start_date, end_date,
       travelers, budget, currency, status,
       itinerary: [{ day, date, activities: [{title,…}] }] }

   The calendar normalises each trip to a consistent internal shape
   and never touches hardcoded/mock data.
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Palette for assigning colors to trips in order ────────────
const TRIP_COLORS = ['purple', 'orange', 'teal', 'pink'];

// ── State ──────────────────────────────────────────────────────
const today     = new Date();
let   viewYear  = today.getFullYear();
let   viewMonth = today.getMonth();
let   liveTRIPS = [];          // populated after API fetch
let   isLoading = false;

// ── DOM refs ───────────────────────────────────────────────────
const monthTitleEl  = document.getElementById('calMonthTitle');
const calGridEl     = document.getElementById('calGrid');
const prevBtn       = document.getElementById('calPrev');
const nextBtn       = document.getElementById('calNext');
const todayBtn      = document.getElementById('calTodayBtn');
const tooltip       = document.getElementById('calTooltip');
const searchInput   = document.getElementById('calSearch');
const legendListEl  = document.getElementById('calLegendList');
const statsGrid     = document.getElementById('calStatsGrid');
const nextTripCard  = document.getElementById('calNextTrip');

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
];

// ── Helpers ────────────────────────────────────────────────────

function parseLocalDate(str) {
  // Parse "YYYY-MM-DD" as LOCAL midnight (avoids UTC off-by-one)
  if (!str) return null;
  const [y, m, d] = str.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth()    === b.getMonth()    &&
         a.getDate()     === b.getDate();
}

function fmtShort(date) {
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function esc(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/**
 * Normalise a raw backend trip into the internal calendar shape.
 * Backend uses: destination (string), start_date, end_date, itinerary[].activities[]
 */
function normaliseTrip(raw, colorIndex) {
  const start = parseLocalDate(raw.start_date);
  const end   = parseLocalDate(raw.end_date);

  // Count activities across all itinerary days
  const totalActivities = (raw.itinerary || [])
    .reduce((sum, day) => sum + (day.activities?.length || 0), 0);

  // Build a per-date activity count map for the sub-labels
  const actByDate = {};
  (raw.itinerary || []).forEach(day => {
    if (day.date) {
      actByDate[day.date] = (day.activities || []).length;
    }
  });

  return {
    id:         raw.id,
    name:       raw.destination || 'Untitled Trip',
    color:      TRIP_COLORS[colorIndex % TRIP_COLORS.length],
    start,
    end,
    startStr:   raw.start_date,
    endStr:     raw.end_date,
    status:     raw.status,
    activities: totalActivities,
    actByDate,
    // destinations is just the single destination string; wrap in array for display
    cities:     raw.destination ? [raw.destination] : [],
    fromCity:   raw.from_city   || '',
  };
}

/** Returns normalised trips that overlap a given calendar Date */
function tripsOnDate(date) {
  return liveTRIPS.filter(t => {
    if (!t.start || !t.end) return false;
    return date >= t.start && date <= t.end;
  });
}

/** ISO date string "YYYY-MM-DD" from a Date object */
function toISO(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// ── Data Fetch ─────────────────────────────────────────────────

async function fetchAndInit() {
  if (!isLoggedIn()) {
    // Not logged in — show auth wall, render empty calendar
    renderAuthWall();
    renderCalendar(viewYear, viewMonth);
    renderSidebar([]);
    return;
  }

  showCalendarSkeleton();

  try {
    const raw = await apiGet('/trips');
    liveTRIPS = (raw || [])
      .filter(t => t.start_date && t.end_date)   // skip trips without dates
      .map((t, i) => normaliseTrip(t, i));
  } catch (err) {
    liveTRIPS = [];
    showToast('Could not load trips: ' + (err.message || 'Server error'), 'error');
  }

  renderCalendar(viewYear, viewMonth);
  renderSidebar(liveTRIPS);
}

// ── Calendar Skeleton ──────────────────────────────────────────

function showCalendarSkeleton() {
  calGridEl.innerHTML = Array.from({ length: 35 }, () =>
    `<div class="cal-day" style="opacity:.35;">
       <div class="cal-day-num" style="background:#E5E7EB;border-radius:50%;color:transparent;">0</div>
     </div>`
  ).join('');
}

// ── Render Calendar Grid ───────────────────────────────────────

function renderCalendar(year, month) {
  monthTitleEl.textContent = `${MONTH_NAMES[month]} ${year}`;

  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevDays    = new Date(year, month, 0).getDate();
  const totalCells  = Math.ceil((firstDay + daysInMonth) / 7) * 7;

  calGridEl.innerHTML = '';

  for (let i = 0; i < totalCells; i++) {
    let dayNum, cellDate, isOther = false;

    if (i < firstDay) {
      dayNum   = prevDays - firstDay + 1 + i;
      cellDate = new Date(year, month - 1, dayNum);
      isOther  = true;
    } else if (i >= firstDay + daysInMonth) {
      dayNum   = i - firstDay - daysInMonth + 1;
      cellDate = new Date(year, month + 1, dayNum);
      isOther  = true;
    } else {
      dayNum   = i - firstDay + 1;
      cellDate = new Date(year, month, dayNum);
    }

    const isToday   = sameDay(cellDate, today);
    const isWeekend = cellDate.getDay() === 0 || cellDate.getDay() === 6;
    const onTrips   = tripsOnDate(cellDate);

    const cell = document.createElement('div');
    cell.className = [
      'cal-day',
      isOther   ? 'cal-day--other-month' : '',
      isToday   ? 'cal-day--today'       : '',
      isWeekend && !isOther ? 'cal-day--weekend' : '',
    ].filter(Boolean).join(' ');

    cell.dataset.date = toISO(cellDate);

    // Day number bubble
    const numEl = document.createElement('div');
    numEl.className = 'cal-day-num';
    numEl.textContent = dayNum;
    cell.appendChild(numEl);

    // Trip bars (only if real trips exist)
    if (onTrips.length) {
      const tripsDiv = document.createElement('div');
      tripsDiv.className = 'cal-day__trips';

      onTrips.forEach(trip => {
        const bar = document.createElement('div');
        bar.className = `cal-trip-bar cal-trip-bar--${trip.color}`;

        // Show label at start of trip OR first day of month/week
        const showLabel = sameDay(cellDate, trip.start) ||
          (cellDate.getDate() === 1 && !isOther) ||
          (cellDate.getDay() === 0  && !isOther);

        bar.textContent = showLabel ? trip.name : '';

        bar.addEventListener('mouseenter', (e) => showTooltipFor(e, trip));
        bar.addEventListener('mousemove',  (e) => moveTooltip(e));
        bar.addEventListener('mouseleave', hideTooltip);

        tripsDiv.appendChild(bar);
      });

      cell.appendChild(tripsDiv);

      // Per-day activity count
      const dateStr = toISO(cellDate);
      const actCount = onTrips.reduce((sum, t) => sum + (t.actByDate[dateStr] || 0), 0);
      if (actCount > 0) {
        const actEl = document.createElement('div');
        actEl.className = 'cal-day__activities';
        actEl.textContent = `• ${actCount} act.`;
        cell.appendChild(actEl);
      }
    }

    cell.addEventListener('click', () => selectDay(cell));
    calGridEl.appendChild(cell);
  }

  // If no trips at all, show a subtle empty-month prompt
  if (liveTRIPS.length === 0) {
    renderEmptyCalendarHint();
  }
}

function renderEmptyCalendarHint() {
  // Find the 15th cell (middle of the grid) and inject a soft message
  const cells = calGridEl.querySelectorAll('.cal-day:not(.cal-day--other-month)');
  const targetIndex = Math.min(10, cells.length - 1);
  if (cells[targetIndex]) {
    const hint = document.createElement('div');
    hint.className = 'cal-empty-hint';
    hint.innerHTML = `<i class="fa-regular fa-calendar-plus"></i><span>No trips this month</span>`;
    hint.style.cssText = `
      position:absolute; bottom:4px; left:50%; transform:translateX(-50%);
      font-size:0.6rem; color:var(--color-text-light); white-space:nowrap;
      display:flex; align-items:center; gap:3px; pointer-events:none;`;
    // Don't render inside individual cells — instead add a full-width overlay row
  }
}

// ── Day Selection ──────────────────────────────────────────────

function selectDay(cell) {
  document.querySelectorAll('.cal-day--selected').forEach(el =>
    el.classList.remove('cal-day--selected')
  );
  cell.classList.add('cal-day--selected');
}

// ── Tooltip ────────────────────────────────────────────────────

function showTooltipFor(e, trip) {
  const cities = trip.cities.length ? trip.cities.join(', ') : trip.fromCity || '—';
  tooltip.innerHTML = `
    <strong>${esc(trip.name)}</strong><br>
    <span style="opacity:.82;font-size:0.72rem;">
      ${fmtShort(trip.start)} &ndash; ${fmtShort(trip.end)}&nbsp;&middot;&nbsp;${esc(cities)}
    </span>`;
  tooltip.classList.add('visible');
  moveTooltip(e);
}

function moveTooltip(e) {
  tooltip.style.left = `${e.clientX - tooltip.offsetWidth / 2}px`;
  tooltip.style.top  = `${e.clientY - tooltip.offsetHeight - 16}px`;
}

function hideTooltip() {
  tooltip.classList.remove('visible');
}

// ── Sidebar: Legend + Stats + Next Trip ────────────────────────

function renderSidebar(trips) {
  renderLegend(trips);
  renderStats(trips);
  renderNextTrip(trips);
}

// Legend card
function renderLegend(trips) {
  if (!legendListEl) return;

  if (trips.length === 0) {
    legendListEl.innerHTML = `
      <div class="cal-legend-empty">
        <i class="fa-regular fa-calendar" style="font-size:1.5rem;color:var(--color-text-light);margin-bottom:8px;"></i>
        <p style="font-size:0.875rem;color:var(--color-text-muted);text-align:center;line-height:1.5;margin:0;">
          No scheduled trips yet.<br>
          <a href="planner.html" style="color:var(--color-primary);font-weight:600;">+ Plan New Trip</a>
          to see your itineraries here.
        </p>
      </div>`;
    return;
  }

  legendListEl.innerHTML = trips.map(trip => {
    const startFmt = trip.start ? fmtShort(trip.start) : '—';
    const endFmt   = trip.end   ? fmtShort(trip.end)   : '—';
    const cities   = trip.cities.length ? trip.cities.join(', ') : trip.fromCity || '';
    return `
      <li class="cal-legend-item">
        <div class="cal-legend-dot cal-legend-dot--${trip.color}"></div>
        <div>
          <div class="cal-legend-name">${esc(trip.name)}</div>
          <div class="cal-legend-dates">${startFmt} &ndash; ${endFmt}${cities ? ' &middot; ' + esc(cities) : ''}</div>
        </div>
      </li>`;
  }).join('');
}

// Stats card
function renderStats(trips) {
  if (!statsGrid) return;

  const now          = new Date();
  const activeTrips  = trips.filter(t => t.end && t.end >= now).length;
  const totalActs    = trips.reduce((sum, t) => sum + t.activities, 0);
  const uniqueCities = new Set(trips.flatMap(t => t.cities)).size;

  statsGrid.innerHTML = `
    <div class="cal-stat-card cal-stat-card--purple">
      <div class="cal-stat-icon cal-stat-icon--purple">
        <i class="fa-solid fa-suitcase-rolling"></i>
      </div>
      <div class="cal-stat-value" id="statActiveTrips">${activeTrips}</div>
      <div class="cal-stat-label">Active Trips</div>
    </div>

    <div class="cal-stat-card cal-stat-card--amber">
      <div class="cal-stat-icon cal-stat-icon--amber">
        <i class="fa-solid fa-list-check"></i>
      </div>
      <div class="cal-stat-value" id="statActivities">${totalActs}</div>
      <div class="cal-stat-label">Activities</div>
    </div>

    <div class="cal-stat-card cal-stat-card--teal cal-stat-card--wide">
      <div class="cal-stat-icon cal-stat-icon--teal">
        <i class="fa-solid fa-city"></i>
      </div>
      <div class="cal-stat-value" id="statCities">${uniqueCities}</div>
      <div class="cal-stat-label">Cities Planned</div>
    </div>`;

  // Animate the numbers
  animateCounter('statActiveTrips', activeTrips);
  animateCounter('statActivities',  totalActs);
  animateCounter('statCities',      uniqueCities);
}

// Next trip widget
function renderNextTrip(trips) {
  if (!nextTripCard) return;

  const now      = new Date();
  const upcoming = trips
    .filter(t => t.start && t.start >= now)
    .sort((a, b) => a.start - b.start);

  if (upcoming.length === 0) {
    // Empty state
    nextTripCard.innerHTML = `
      <div style="text-align:center;padding:8px 0 4px;">
        <div style="font-size:2rem;margin-bottom:10px;">🗓️</div>
        <div style="font-size:0.9375rem;font-weight:700;color:var(--color-text);margin-bottom:6px;">No Upcoming Trips</div>
        <div style="font-size:0.8125rem;color:var(--color-text-muted);margin-bottom:16px;line-height:1.5;">
          Create an itinerary to see your schedule here.
        </div>
        <a href="planner.html" class="btn btn-primary btn-sm" style="width:100%;justify-content:center;">
          <i class="fa-solid fa-wand-magic-sparkles"></i> Plan with AI
        </a>
      </div>`;
    return;
  }

  const next   = upcoming[0];
  const cities = next.cities.length ? next.cities : [next.fromCity].filter(Boolean);

  nextTripCard.innerHTML = `
    <div style="font-size:0.75rem;font-weight:700;color:var(--color-primary);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">
      <i class="fa-solid fa-clock"></i>&nbsp; Next Trip
    </div>
    <div style="font-size:0.9rem;font-weight:600;color:var(--color-text);">${esc(next.name)}</div>
    <div style="font-size:0.78rem;color:var(--color-text-muted);margin-top:3px;">
      Starting <strong style="color:var(--color-primary);">${fmtShort(next.start)}</strong>
    </div>
    ${cities.length ? `
    <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;">
      ${cities.map(c => `
        <span style="background:#fff;border:1px solid #E0E7FF;color:#6366F1;font-size:0.72rem;font-weight:600;padding:3px 8px;border-radius:999px;">${esc(c)}</span>
      `).join('')}
      ${next.activities > 0 ? `
        <span style="background:#fff;border:1px solid #E0E7FF;color:#6366F1;font-size:0.72rem;font-weight:600;padding:3px 8px;border-radius:999px;">${next.activities} activities</span>
      ` : ''}
    </div>` : ''}`;
}

// Auth wall (not logged in)
function renderAuthWall() {
  if (!legendListEl) return;
  legendListEl.innerHTML = `
    <div class="cal-legend-empty">
      <i class="fa-solid fa-lock" style="font-size:1.4rem;color:var(--color-text-light);margin-bottom:8px;"></i>
      <p style="font-size:0.875rem;color:var(--color-text-muted);text-align:center;line-height:1.5;margin:0;">
        <a href="login.html?redirect=calendar.html" style="color:var(--color-primary);font-weight:600;">Sign in</a>
        to see your trips on the calendar.
      </p>
    </div>`;
}

// ── Animated Counter ───────────────────────────────────────────

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el || target === 0) return;
  let start   = 0;
  const step  = Math.ceil(target / 20);
  const timer = setInterval(() => {
    start = Math.min(start + step, target);
    el.textContent = start;
    if (start >= target) clearInterval(timer);
  }, 40);
}

// ── Navigation ─────────────────────────────────────────────────

prevBtn.addEventListener('click', () => {
  viewMonth--;
  if (viewMonth < 0) { viewMonth = 11; viewYear--; }
  renderCalendar(viewYear, viewMonth);
});

nextBtn.addEventListener('click', () => {
  viewMonth++;
  if (viewMonth > 11) { viewMonth = 0; viewYear++; }
  renderCalendar(viewYear, viewMonth);
});

todayBtn.addEventListener('click', () => {
  viewYear  = today.getFullYear();
  viewMonth = today.getMonth();
  renderCalendar(viewYear, viewMonth);
});

// ── View Tab Switcher ──────────────────────────────────────────

document.querySelectorAll('.cal-view-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.cal-view-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
  });
});

// ── Search Filter ──────────────────────────────────────────────

if (searchInput) {
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase().trim();
    document.querySelectorAll('.cal-trip-bar').forEach(bar => {
      if (!q) { bar.style.opacity = ''; return; }
      const matches = liveTRIPS.some(t =>
        bar.classList.contains(`cal-trip-bar--${t.color}`) &&
        t.name.toLowerCase().includes(q)
      );
      bar.style.opacity = matches ? '1' : '0.18';
    });
    // Also filter legend items
    document.querySelectorAll('.cal-legend-item').forEach((item, i) => {
      if (!q) { item.style.opacity = ''; return; }
      const name = liveTRIPS[i]?.name || '';
      item.style.opacity = name.toLowerCase().includes(q) ? '1' : '0.3';
    });
  });
}

// ── Bootstrap ─────────────────────────────────────────────────
// theme.js  → navbar scroll, hamburger, dark-mode toggle
// api.js    → apiGet, showToast, formatDate
// auth.js   → isLoggedIn, syncAuthUI
// All three are loaded before this script in calendar.html.
fetchAndInit();
