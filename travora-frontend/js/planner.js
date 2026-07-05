/**
 * planner.js — AI Planner page logic.
 * Handles: URL param pre-fill, interest tag selection,
 * form submission, animated loading steps, itinerary rendering.
 */

document.addEventListener('DOMContentLoaded', function () {
  prefillFromUrl();
  initInterestTags();
  setMinDates();
});

// ── URL pre-fill ──────────────────────────────────────────────
function prefillFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const set = (id, val) => { if (val && document.getElementById(id)) document.getElementById(id).value = val; };
  set('destination', params.get('destination'));
  set('fromCity',    params.get('from'));
  set('startDate',   params.get('date'));
  set('budget',      params.get('budget'));
  const t = params.get('travelers');
  if (t && document.getElementById('travelers')) {
    const opt = document.querySelector(`#travelers option[value="${t}"]`);
    if (opt) opt.selected = true;
  }
}

// ── Enforce min date = today ───────────────────────────────────
function setMinDates() {
  const today = new Date().toISOString().split('T')[0];
  ['startDate','endDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.min = today;
  });
  const startEl = document.getElementById('startDate');
  const endEl   = document.getElementById('endDate');
  if (startEl && endEl) {
    startEl.addEventListener('change', () => {
      endEl.min = startEl.value;
      if (endEl.value && endEl.value < startEl.value) endEl.value = startEl.value;
    });
  }
}

// ── Interest tags ─────────────────────────────────────────────
function initInterestTags() {
  document.querySelectorAll('.interest-tag').forEach(tag => {
    tag.addEventListener('click', function () {
      this.classList.toggle('selected');
    });
  });
}

function getSelectedInterests() {
  return [...document.querySelectorAll('.interest-tag.selected')]
    .map(t => t.dataset.interest);
}

// ── Form validation ───────────────────────────────────────────
function validateForm() {
  let valid = true;
  const clearErr = id => { const el = document.getElementById(id); if (el) el.textContent = ''; };
  const setErr   = (id, msg) => {
    const el = document.getElementById(id);
    if (el) el.textContent = msg;
    valid = false;
  };
  ['destError','fromError','startDateError','endDateError','budgetError'].forEach(clearErr);

  const dest   = document.getElementById('destination')?.value.trim();
  const from   = document.getElementById('fromCity')?.value.trim();
  const start  = document.getElementById('startDate')?.value;
  const end    = document.getElementById('endDate')?.value;
  const budget = document.getElementById('budget')?.value;

  if (!dest)   setErr('destError',      'Please enter a destination');
  if (!from)   setErr('fromError',      'Please enter your departure city');
  if (!start)  setErr('startDateError', 'Please select a start date');
  if (!end)    setErr('endDateError',   'Please select an end date');
  if (start && end && end < start) setErr('endDateError', 'End date must be after start date');
  if (!budget || Number(budget) <= 0) setErr('budgetError', 'Please enter a valid budget');

  return valid;
}

// ── Animated loading steps ────────────────────────────────────
const STEP_DURATIONS = [4000, 6000, 5000, 5000, 3000]; // ms per step (cosmetic)
let stepTimers = [];

function startLoadingAnimation() {
  const steps = ['step1','step2','step3','step4','step5'];
  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active','done'); }
  });

  let delay = 0;
  steps.forEach((id, i) => {
    // Mark previous as done, current as active
    const t1 = setTimeout(() => {
      if (i > 0) {
        const prev = document.getElementById(steps[i-1]);
        if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
      }
      const cur = document.getElementById(id);
      if (cur) cur.classList.add('active');
    }, delay);
    stepTimers.push(t1);
    delay += STEP_DURATIONS[i];
  });
}

function stopLoadingAnimation() {
  stepTimers.forEach(clearTimeout);
  stepTimers = [];
  // Mark all done
  ['step1','step2','step3','step4','step5'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active'); el.classList.add('done'); }
  });
}

// ── Show/hide panels ──────────────────────────────────────────
function showPanel(panelId) {
  ['promptState','loadingState','itineraryResult'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === panelId ? (id === 'itineraryResult' ? 'block' : 'flex') : 'none';
  });
}

// ── Main submit handler ───────────────────────────────────────
async function startPlanning(e) {
  e.preventDefault();
  if (!validateForm()) return;

  // Require auth to save trip
  if (!isLoggedIn()) {
    showToast('Sign in to save your trip — redirecting to login…', 'info', 2000);
    setTimeout(() => { window.location.href = 'login.html?redirect=planner.html'; }, 2000);
    return;
  }

  const payload = {
    destination: document.getElementById('destination').value.trim(),
    from_city:   document.getElementById('fromCity').value.trim(),
    start_date:  document.getElementById('startDate').value,
    end_date:    document.getElementById('endDate').value,
    travelers:   parseInt(document.getElementById('travelers').value) || 2,
    budget:      parseFloat(document.getElementById('budget').value),
    currency:    document.getElementById('currency').value,
    interests:   getSelectedInterests(),
  };

  // Disable form
  const planBtn = document.getElementById('planBtn');
  planBtn.disabled = true;
  planBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;"></span> Generating…';

  showPanel('loadingState');
  startLoadingAnimation();

  try {
    const result = await apiPost('/planner/generate', payload);
    stopLoadingAnimation();
    renderItinerary(result, payload);
    showPanel('itineraryResult');
    showToast(`Your ${payload.destination} itinerary is ready! 🎉`, 'success');
    // Scroll result into view on mobile
    document.getElementById('resultPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    stopLoadingAnimation();
    showPanel('promptState');
    showToast(err.message || 'Failed to generate itinerary. Please try again.', 'error');
  } finally {
    planBtn.disabled = false;
    planBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate My Itinerary';
  }
}

// ── Render itinerary ──────────────────────────────────────────
function renderItinerary(data, payload) {
  const container = document.getElementById('itineraryResult');
  if (!container) return;

  const currency   = payload.currency || 'INR';
  const itinerary  = data.itinerary   || [];
  const budget     = data.budget_breakdown || {};
  const notes      = data.agent_notes || {};
  const days       = itinerary.length;

  container.innerHTML = `
    ${buildItineraryHeader(payload, days, budget, currency, notes)}
    ${buildBudgetCard(budget, currency)}
    ${buildDayCards(itinerary, currency)}
    ${buildLocalTipsCard(data.local_tips)}
    ${buildSavingTips(budget)}
    <div style="text-align:center;margin-top:var(--space-xl);">
      <a href="my-trips.html" class="btn btn-outline">
        <i class="fa-solid fa-suitcase"></i> View All My Trips
      </a>
      ${data.trip_id ? `<a href="trip-detail.html?id=${data.trip_id}" class="btn btn-primary" style="margin-left:var(--space-md);">
        <i class="fa-solid fa-expand"></i> Full Detail View
      </a>` : ''}
    </div>`;
}

function buildItineraryHeader(payload, days, budget, currency, notes) {
  const withinBudget = budget.within_budget !== false;
  return `
    <div class="itinerary-header">
      <h2>✈️ ${escHtml(payload.destination)} — ${days}-Day Itinerary</h2>
      <p>${escHtml(notes.research || `Your personalised trip from ${payload.from_city}`)}</p>
      <div class="itinerary-meta">
        <div class="itinerary-meta-item"><i class="fa-solid fa-calendar"></i> ${formatDate(payload.start_date)} – ${formatDate(payload.end_date)}</div>
        <div class="itinerary-meta-item"><i class="fa-solid fa-users"></i> ${payload.travelers} traveler${payload.travelers > 1 ? 's' : ''}</div>
        <div class="itinerary-meta-item"><i class="fa-solid fa-wallet"></i> ${formatCurrency(payload.budget, currency)} budget</div>
        <div class="itinerary-meta-item" style="${withinBudget ? 'background:rgba(34,197,94,0.2)' : 'background:rgba(239,68,68,0.2)'}">
          <i class="fa-solid fa-${withinBudget ? 'check' : 'triangle-exclamation'}"></i>
          ${withinBudget ? 'Within budget' : 'Over budget'}
        </div>
      </div>
    </div>`;
}

function buildBudgetCard(budget, currency) {
  const categories = [
    { key: 'flights',    label: 'Flights',    icon: 'fa-plane' },
    { key: 'hotels',     label: 'Hotels',     icon: 'fa-hotel' },
    { key: 'food',       label: 'Food',       icon: 'fa-utensils' },
    { key: 'activities', label: 'Activities', icon: 'fa-ticket' },
    { key: 'transport',  label: 'Transport',  icon: 'fa-bus' },
    { key: 'misc',       label: 'Misc',       icon: 'fa-bag-shopping' },
  ];
  const total = budget.total || 1;
  const bars  = categories
    .filter(c => budget[c.key] > 0)
    .map(c => {
      const pct = Math.round((budget[c.key] / total) * 100);
      return `
        <div class="budget-bar">
          <div class="budget-bar__label"><i class="fa-solid ${c.icon}" style="color:var(--color-primary);width:14px;"></i> ${c.label}</div>
          <div class="budget-bar__track"><div class="budget-bar__fill" style="width:${pct}%"></div></div>
          <div class="budget-bar__amount">${formatCurrency(budget[c.key], currency)}</div>
        </div>`;
    }).join('');

  return `
    <div class="budget-card" style="margin-top:var(--space-lg);">
      <h3><i class="fa-solid fa-piggy-bank" style="color:var(--color-primary);margin-right:8px;"></i>Budget Breakdown</h3>
      <div class="budget-bars">${bars}</div>
      <div style="margin-top:var(--space-lg);padding-top:var(--space-md);border-top:1px solid var(--color-border);display:flex;justify-content:space-between;align-items:center;">
        <strong style="color:var(--color-text);">Total Estimated</strong>
        <strong style="font-size:1.125rem;color:var(--color-primary);">${formatCurrency(budget.total || 0, currency)}</strong>
      </div>
    </div>`;
}

function buildDayCards(itinerary, currency) {
  if (!itinerary.length) return '<p style="color:var(--color-text-muted);text-align:center;padding:var(--space-xl);">No itinerary generated.</p>';

  return `
    <div style="margin-top:var(--space-xl);">
      <h3 style="margin-bottom:var(--space-lg);"><i class="fa-solid fa-calendar-days" style="color:var(--color-primary);margin-right:8px;"></i>Day-by-Day Plan</h3>
      <div style="display:flex;flex-direction:column;gap:var(--space-md);">
        ${itinerary.map((day, i) => buildSingleDay(day, i, currency)).join('')}
      </div>
    </div>`;
}

function buildSingleDay(day, index, currency) {
  const activities = (day.activities || []).map(a => `
    <div class="activity-content">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:var(--space-md);margin-bottom:4px;">
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

  // Open first day by default
  const isOpen = index === 0;
  return `
    <div class="day-card ${isOpen ? 'open' : ''}" id="day-${index}">
      <div class="day-card__header" onclick="toggleDay(${index})">
        <div class="day-card__header-left">
          <div class="day-number">${day.day || index + 1}</div>
          <div>
            <div class="day-card__title">${escHtml(day.title || `Day ${day.day || index + 1}`)}</div>
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

function toggleDay(index) {
  const card = document.getElementById(`day-${index}`);
  if (card) card.classList.toggle('open');
}

function buildLocalTipsCard(local) {
  if (!local || (!local.must_eat?.length && !local.cultural_tips?.length)) return '';

  const mustEat = (local.must_eat || []).slice(0, 5).map(m => `
    <li><strong>${escHtml(m.name)}</strong> — ${escHtml(m.description)} <span style="color:var(--color-primary);font-size:0.75rem;">(${escHtml(m.price_range || '')})</span></li>`).join('');

  const tips = (local.cultural_tips || []).slice(0, 5).map(t => `<li>${escHtml(t)}</li>`).join('');

  const gems = (local.hidden_gems || []).slice(0, 3).map(g => `
    <li><strong>${escHtml(g.name)}</strong> — ${escHtml(g.description)}</li>`).join('');

  return `
    <div class="local-tips-card" style="margin-top:var(--space-xl);">
      <h3><i class="fa-solid fa-gem"></i> Local Insider Tips</h3>
      <div class="local-tips-grid">
        ${mustEat ? `<div class="local-tips-section"><h4><i class="fa-solid fa-utensils"></i> Must Eat</h4><ul>${mustEat}</ul></div>` : ''}
        ${tips    ? `<div class="local-tips-section"><h4><i class="fa-solid fa-circle-info"></i> Cultural Tips</h4><ul>${tips}</ul></div>` : ''}
        ${gems    ? `<div class="local-tips-section"><h4><i class="fa-solid fa-map-pin"></i> Hidden Gems</h4><ul>${gems}</ul></div>` : ''}
        ${local.shopping_tips ? `<div class="local-tips-section"><h4><i class="fa-solid fa-bag-shopping"></i> Shopping</h4><p style="font-size:0.875rem;">${escHtml(local.shopping_tips)}</p></div>` : ''}
      </div>
    </div>`;
}

function buildSavingTips(budget) {
  const tips = budget.saving_tips || [];
  if (!tips.length) return '';
  return `
    <div style="margin-top:var(--space-xl);padding:var(--space-xl);background:var(--color-bg-secondary);border-radius:var(--radius-xl);border:1px solid var(--color-border);">
      <h3 style="margin-bottom:var(--space-md);"><i class="fa-solid fa-lightbulb" style="color:#F59E0B;margin-right:8px;"></i>Money-Saving Tips</h3>
      <ul style="display:flex;flex-direction:column;gap:10px;">
        ${tips.map(t => `<li style="display:flex;gap:10px;font-size:0.9rem;color:var(--color-text-muted);">
          <i class="fa-solid fa-check" style="color:#22C55E;margin-top:3px;flex-shrink:0;"></i>${escHtml(t)}
        </li>`).join('')}
      </ul>
    </div>`;
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
