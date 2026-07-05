/**
 * trips.js — My Trips page + Trip Detail page logic.
 * Detects which page is active by checking for key DOM elements.
 */
document.addEventListener('DOMContentLoaded', function () {
  if (document.getElementById('tripsGrid')) {
    initMyTripsPage();
  } else if (document.getElementById('detailContent')) {
    initTripDetailPage();
  }
});

// ════════════════════════════════════════════════════════════════
// MY TRIPS PAGE
// ════════════════════════════════════════════════════════════════

let allTrips      = [];
let currentFilter = 'all';
let pendingDeleteId = null;

function initMyTripsPage() {
  if (!isLoggedIn()) {
    document.getElementById('authWall')?.style.setProperty('display','block');
    return;
  }
  loadTrips();
}

async function loadTrips() {
  document.getElementById('tripsLoading')?.style.setProperty('display','grid');
  document.getElementById('tripsGrid').innerHTML = '';

  try {
    allTrips = await apiGet('/trips');
    document.getElementById('tripsLoading')?.style.setProperty('display','none');
    renderTrips();

    // Update subtitle
    const user = getCurrentUser();
    if (user) {
      document.getElementById('heroSubtitle').textContent =
        `Welcome back, ${user.name?.split(' ')[0] || 'Traveler'}! You have ${allTrips.length} saved trip${allTrips.length !== 1 ? 's' : ''}.`;
    }
  } catch (err) {
    document.getElementById('tripsLoading')?.style.setProperty('display','none');
    document.getElementById('tripsGrid').innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;">
        <span class="empty-state__icon">⚠️</span>
        <h3>Failed to load trips</h3>
        <p>${escHtml(err.message)}</p>
        <button class="btn btn-primary" onclick="loadTrips()">Try Again</button>
      </div>`;
  }
}

function setStatusFilter(status, btn) {
  currentFilter = status;
  document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTrips();
}

function renderTrips() {
  const grid = document.getElementById('tripsGrid');
  let list = allTrips;
  if (currentFilter !== 'all') list = list.filter(t => t.status === currentFilter);

  if (!list.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;">
        <span class="empty-state__icon">🗺️</span>
        <h3>${currentFilter === 'all' ? "No trips yet" : `No ${currentFilter} trips`}</h3>
        <p>${currentFilter === 'all' ? "Start planning your first AI-powered adventure!" : "Try a different filter."}</p>
        <a href="planner.html" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Plan a Trip</a>
      </div>`;
    return;
  }

  grid.innerHTML = list.map(trip => buildTripCard(trip)).join('');
}

function buildTripCard(trip) {
  const days     = tripDays(trip.start_date, trip.end_date);
  const currency = trip.currency || 'INR';
  const statusMap = {
    generated: ['Generated', 'generated'],
    draft:     ['Draft',     'draft'],
    generating:['Generating…','generating'],
    booked:    ['Booked',    'booked'],
  };
  const [statusLabel, statusClass] = statusMap[trip.status] || ['Unknown', 'draft'];

  return `
    <div class="trip-card" onclick="openTrip('${trip.id}')">
      <div class="trip-card__header">
        <div class="trip-card__destination">
          <i class="fa-solid fa-location-dot" style="color:var(--color-primary);margin-right:6px;"></i>${escHtml(trip.destination)}
        </div>
        <div class="trip-card__dates">
          <i class="fa-solid fa-calendar"></i>
          ${formatDate(trip.start_date)} – ${formatDate(trip.end_date)}
        </div>
        <div class="trip-card__status">
          <span class="status-badge status-badge--${statusClass}">${statusLabel}</span>
        </div>
      </div>
      <div class="trip-card__body">
        <div class="trip-card__info">
          <div class="trip-card__info-item"><i class="fa-solid fa-plane"></i> From ${escHtml(trip.from_city)}</div>
          <div class="trip-card__info-item"><i class="fa-solid fa-sun"></i> ${days} day${days !== 1 ? 's' : ''}</div>
          <div class="trip-card__info-item"><i class="fa-solid fa-users"></i> ${trip.travelers} traveler${trip.travelers !== 1 ? 's' : ''}</div>
          <div class="trip-card__info-item"><i class="fa-solid fa-wallet"></i> ${formatCurrency(trip.budget, currency)}</div>
        </div>
        <div class="trip-card__actions" onclick="event.stopPropagation()">
          ${trip.status === 'generated' ? `
            <a href="trip-detail.html?id=${trip.id}" class="btn btn-primary btn-sm">
              <i class="fa-solid fa-eye"></i> View
            </a>` : ''}
          <a href="planner.html" class="btn btn-outline btn-sm" onclick="sessionStorage.setItem('regenerate_trip_id','${trip.id}')">
            <i class="fa-solid fa-rotate"></i> Regenerate
          </a>
          <button class="btn btn-ghost btn-sm" style="color:#EF4444;" onclick="confirmDelete('${trip.id}')">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>
    </div>`;
}

function openTrip(id) {
  window.location.href = `trip-detail.html?id=${id}`;
}

// Delete modal
function confirmDelete(tripId) {
  pendingDeleteId = tripId;
  const modal = document.getElementById('deleteModal');
  if (modal) modal.style.display = 'flex';
  const btn = document.getElementById('confirmDeleteBtn');
  if (btn) btn.onclick = () => deleteTrip(tripId);
}

function closeDeleteModal() {
  pendingDeleteId = null;
  const modal = document.getElementById('deleteModal');
  if (modal) modal.style.display = 'none';
}

async function deleteTrip(tripId) {
  closeDeleteModal();
  try {
    await apiDelete(`/trips/${tripId}`);
    allTrips = allTrips.filter(t => t.id !== tripId);
    renderTrips();
    showToast('Trip deleted', 'success');
  } catch (err) {
    showToast(err.message || 'Failed to delete trip', 'error');
  }
}

// ════════════════════════════════════════════════════════════════
// TRIP DETAIL PAGE
// ════════════════════════════════════════════════════════════════

async function initTripDetailPage() {
  if (!isLoggedIn()) {
    window.location.href = 'login.html?redirect=my-trips.html';
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const tripId = params.get('id');
  if (!tripId) { showError(); return; }

  try {
    const trip = await apiGet(`/trips/${tripId}`);
    renderTripDetail(trip);
  } catch (err) {
    showError();
  }
}

function showError() {
  document.getElementById('detailLoading')?.style.setProperty('display','none');
  document.getElementById('detailError')?.style.setProperty('display','block');
}

function renderTripDetail(trip) {
  document.getElementById('detailLoading').style.display  = 'none';
  document.getElementById('detailContent').style.display  = 'block';

  const currency = trip.currency || 'INR';
  const days     = tripDays(trip.start_date, trip.end_date);

  // Title
  document.title = `${trip.destination} Trip — Travora`;
  document.getElementById('tripTitle').textContent = `✈️ ${trip.destination}`;

  // Meta
  const metaEl = document.getElementById('tripMeta');
  if (metaEl) {
    metaEl.innerHTML = `
      <div class="itinerary-meta-item"><i class="fa-solid fa-calendar"></i> ${formatDate(trip.start_date)} – ${formatDate(trip.end_date)}</div>
      <div class="itinerary-meta-item"><i class="fa-solid fa-plane"></i> From ${escHtml(trip.from_city)}</div>
      <div class="itinerary-meta-item"><i class="fa-solid fa-users"></i> ${trip.travelers} traveler${trip.travelers !== 1 ? 's' : ''}</div>
      <div class="itinerary-meta-item"><i class="fa-solid fa-sun"></i> ${days} days</div>
      <div class="itinerary-meta-item"><i class="fa-solid fa-wallet"></i> ${formatCurrency(trip.budget, currency)}</div>`;
  }

  // Regenerate link
  const regenBtn = document.getElementById('regenerateBtn');
  if (regenBtn) regenBtn.href = `planner.html?destination=${encodeURIComponent(trip.destination)}&from=${encodeURIComponent(trip.from_city)}&budget=${trip.budget}`;

  // Days
  const daysList = document.getElementById('daysList');
  if (daysList && trip.itinerary?.length) {
    daysList.innerHTML = trip.itinerary.map((day, i) => buildDetailDay(day, i, currency)).join('');
  } else if (daysList) {
    daysList.innerHTML = `<div class="empty-state"><span class="empty-state__icon">📋</span><h3>No itinerary yet</h3><p>This trip hasn't been generated yet.</p><a href="planner.html" class="btn btn-primary">Plan Now</a></div>`;
  }

  // Budget sidebar
  renderBudgetSidebar(trip.budget_breakdown, currency);

  // Agent notes sidebar
  renderAgentNotes(trip.agent_notes);

  // Local tips
  renderLocalTips(trip.local_tips);
}

function buildDetailDay(day, index, currency) {
  const isOpen = index === 0;
  const activities = (day.activities || []).map(a => `
    <div class="activity-content">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:4px;">
        <h4>${escHtml(a.title)}</h4>
        ${a.time ? `<span style="font-size:0.8125rem;font-weight:700;color:var(--color-primary);white-space:nowrap;">${escHtml(a.time)}</span>` : ''}
      </div>
      ${a.description ? `<p>${escHtml(a.description)}</p>` : ''}
      <div class="activity-meta">
        ${a.location ? `<span><i class="fa-solid fa-location-dot"></i> ${escHtml(a.location)}</span>` : ''}
        ${a.estimated_cost > 0 ? `<span><i class="fa-solid fa-wallet"></i> ${formatCurrency(a.estimated_cost, currency)}</span>` : ''}
        ${a.category ? `<span><i class="fa-solid fa-tag"></i> ${escHtml(a.category)}</span>` : ''}
      </div>
    </div>`).join('');

  return `
    <div class="day-card ${isOpen ? 'open' : ''}" id="detail-day-${index}">
      <div class="day-card__header" onclick="toggleDetailDay(${index})">
        <div class="day-card__header-left">
          <div class="day-number">${day.day || index + 1}</div>
          <div>
            <div class="day-card__title">${escHtml(day.title || `Day ${day.day || index+1}`)}</div>
            ${day.date ? `<div class="day-card__date">${formatDate(day.date)}</div>` : ''}
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:var(--space-md);">
          ${day.estimated_cost > 0 ? `<div class="day-card__cost">${formatCurrency(day.estimated_cost, currency)}</div>` : ''}
          <i class="fa-solid fa-chevron-down day-card__chevron"></i>
        </div>
      </div>
      <div class="day-card__body">
        ${activities}
        ${day.notes ? `<div style="margin-top:var(--space-sm);padding:12px 14px;background:var(--color-primary-soft);border-radius:var(--radius-md);font-size:0.875rem;color:var(--color-primary);">
          <i class="fa-solid fa-lightbulb" style="margin-right:6px;"></i>${escHtml(day.notes)}
        </div>` : ''}
      </div>
    </div>`;
}

function toggleDetailDay(index) {
  const card = document.getElementById(`detail-day-${index}`);
  if (card) card.classList.toggle('open');
}

function renderBudgetSidebar(budget, currency) {
  if (!budget) return;
  const barsEl  = document.getElementById('budgetBars');
  const totalEl = document.getElementById('budgetTotal');
  const notesEl = document.getElementById('budgetNotes');
  if (!barsEl) return;

  const categories = [
    { key:'flights',    label:'Flights',    icon:'fa-plane' },
    { key:'hotels',     label:'Hotels',     icon:'fa-hotel' },
    { key:'food',       label:'Food',       icon:'fa-utensils' },
    { key:'activities', label:'Activities', icon:'fa-ticket' },
    { key:'transport',  label:'Transport',  icon:'fa-bus' },
    { key:'misc',       label:'Misc',       icon:'fa-bag-shopping' },
  ];
  const total = budget.total || 1;
  barsEl.innerHTML = categories.filter(c => budget[c.key] > 0).map(c => {
    const pct = Math.round((budget[c.key] / total) * 100);
    return `
      <div class="budget-bar">
        <div class="budget-bar__label"><i class="fa-solid ${c.icon}" style="color:var(--color-primary);width:14px;"></i> ${c.label}</div>
        <div class="budget-bar__track"><div class="budget-bar__fill" style="width:${pct}%"></div></div>
        <div class="budget-bar__amount">${formatCurrency(budget[c.key], currency)}</div>
      </div>`;
  }).join('');

  if (totalEl) totalEl.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <strong>Total</strong>
      <strong style="color:var(--color-primary);font-size:1.0625rem;">${formatCurrency(budget.total || 0, currency)}</strong>
    </div>
    <div style="margin-top:6px;font-size:0.8125rem;color:${budget.within_budget !== false ? '#22C55E' : '#EF4444'};">
      <i class="fa-solid fa-${budget.within_budget !== false ? 'check-circle' : 'triangle-exclamation'}"></i>
      ${budget.within_budget !== false ? 'Within budget' : 'Estimated cost exceeds budget'}
    </div>`;

  if (notesEl && budget.budget_notes) {
    notesEl.style.display = 'block';
    notesEl.innerHTML = `<i class="fa-solid fa-circle-info" style="color:var(--color-primary);margin-right:6px;"></i>${escHtml(budget.budget_notes)}`;
  }
}

function renderAgentNotes(notes) {
  const card = document.getElementById('agentNotesCard');
  const list = document.getElementById('agentNotesList');
  if (!card || !list || !notes) return;

  const items = [
    { key:'weather',        icon:'fa-cloud-sun',       label:'Weather' },
    { key:'visa',           icon:'fa-passport',         label:'Visa & Entry' },
    { key:'safety',         icon:'fa-shield-halved',    label:'Safety' },
    { key:'language',       icon:'fa-language',         label:'Language Tips' },
    { key:'currency_notes', icon:'fa-coins',            label:'Currency' },
  ];

  const rendered = items
    .filter(i => notes[i.key])
    .map(i => `
      <div style="padding:12px;background:var(--color-bg-secondary);border-radius:var(--radius-md);">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <i class="fa-solid ${i.icon}" style="color:var(--color-primary);width:16px;"></i>
          <strong style="font-size:0.875rem;">${i.label}</strong>
        </div>
        <p style="font-size:0.8125rem;line-height:1.6;">${escHtml(notes[i.key])}</p>
      </div>`)
    .join('');

  if (rendered) {
    list.innerHTML = rendered;
    card.style.display = 'block';
  }
}

function renderLocalTips(local) {
  const section = document.getElementById('localTipsSection');
  const grid    = document.getElementById('localTipsGrid');
  if (!section || !grid || !local) return;

  const mustEat = (local.must_eat || []).slice(0,5).map(m => `
    <li><strong>${escHtml(m.name)}</strong> — ${escHtml(m.description)}</li>`).join('');
  const tips = (local.cultural_tips || []).slice(0,5).map(t => `<li>${escHtml(t)}</li>`).join('');
  const gems = (local.hidden_gems || []).slice(0,3).map(g => `
    <li><strong>${escHtml(g.name)}</strong> — ${escHtml(g.description)}</li>`).join('');

  if (!mustEat && !tips && !gems) return;

  grid.innerHTML = `
    ${mustEat ? `<div class="local-tips-section"><h4><i class="fa-solid fa-utensils"></i> Must Eat</h4><ul>${mustEat}</ul></div>` : ''}
    ${tips    ? `<div class="local-tips-section"><h4><i class="fa-solid fa-circle-info"></i> Cultural Tips</h4><ul>${tips}</ul></div>` : ''}
    ${gems    ? `<div class="local-tips-section"><h4><i class="fa-solid fa-map-pin"></i> Hidden Gems</h4><ul>${gems}</ul></div>` : ''}
    ${local.shopping_tips ? `<div class="local-tips-section"><h4><i class="fa-solid fa-bag-shopping"></i> Shopping</h4><p style="font-size:0.875rem;">${escHtml(local.shopping_tips)}</p></div>` : ''}`;

  section.style.display = 'block';
}

function printTrip() {
  window.print();
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
