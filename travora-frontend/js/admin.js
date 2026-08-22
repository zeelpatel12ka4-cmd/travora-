/**
 * admin.js — Admin Dashboard Controller
 * Manages stats overview, engagement chart (Chart.js), top destinations/interests,
 * user management (search, paginate, soft-deactivate), and platform trips table.
 */

let engagementChartInstance = null;

// User management state
let userState = {
  search: '',
  status: '',
  page: 1,
  limit: 10,
  total: 0,
  totalPages: 1,
};

// Trip management state
let tripState = {
  search: '',
  status: 'all',
  page: 1,
  limit: 10,
  total: 0,
  totalPages: 1,
};

document.addEventListener('DOMContentLoaded', async function () {
  // 1. Guard check: Require Auth + Admin privileges
  if (!requireAuth('admin.html')) return;
  const user = getCurrentUser();
  if (!user || !user.is_admin) {
    showToast('Admin privileges required. Redirecting…', 'error');
    setTimeout(() => {
      window.location.href = 'index.html';
    }, 1200);
    return;
  }

  // Update subtitle greeting
  const subTitle = document.getElementById('heroSubtitle');
  if (subTitle && user.name) {
    subTitle.textContent = `Logged in as ${user.name} (${user.email}) — full platform access.`;
  }

  // 2. Initialize components
  initSearchAndFilters();
  
  // 3. Load all dashboard data in parallel
  loadDashboardData();

  // 4. Listen to theme changes to adjust chart colors
  const themeObserver = new MutationObserver(() => {
    if (engagementChartInstance) {
      updateChartTheme();
    }
  });
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
});

async function loadDashboardData() {
  await Promise.allSettled([
    loadOverviewStats(),
    loadEngagementChart(),
    loadTopDestinations(),
    loadTopInterests(),
    loadUsers(),
    loadTrips(),
  ]);
}

// ════════════════════════════════════════════════════════════════
// 1. OVERVIEW STATS
// ════════════════════════════════════════════════════════════════
async function loadOverviewStats() {
  try {
    const data = await apiGet('/admin/stats/overview');
    if (!data) return;

    document.getElementById('statTotalUsers').textContent = (data.total_users ?? 0).toLocaleString();
    const activeSub = document.getElementById('statActiveUsersSub');
    if (activeSub) {
      activeSub.innerHTML = `<i class="fa-solid fa-circle-check" style="color:#22C55E;"></i> ${data.active_users ?? 0} active accounts`;
    }

    document.getElementById('statTotalTrips').textContent = (data.total_trips ?? 0).toLocaleString();
    document.getElementById('statTripsThisWeek').textContent = (data.trips_this_week ?? 0).toLocaleString();
    document.getElementById('statTripsThisMonth').textContent = (data.trips_this_month ?? 0).toLocaleString();
    document.getElementById('statGeneratedTrips').textContent = (data.generated_trips ?? 0).toLocaleString();
    document.getElementById('statBookedTrips').textContent = (data.booked_trips ?? 0).toLocaleString();
  } catch (err) {
    console.error('Failed to load overview stats:', err);
    showToast(err.message || 'Failed to load overview stats', 'error');
  }
}

// ════════════════════════════════════════════════════════════════
// 6. ENGAGEMENT CHART (Chart.js)
// ════════════════════════════════════════════════════════════════
async function loadEngagementChart() {
  try {
    const data = await apiGet('/admin/stats/engagement');
    if (!Array.isArray(data)) return;

    const ctx = document.getElementById('engagementChart');
    if (!ctx) return;

    const labels = data.map((d) => {
      // Format YYYY-MM-DD to "DD MMM"
      const parts = d.date.split('-');
      if (parts.length === 3) {
        const dt = new Date(parts[0], parts[1] - 1, parts[2]);
        return dt.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
      }
      return d.date;
    });
    const counts = data.map((d) => d.count);

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#94A3B8' : '#6B7280';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';

    if (engagementChartInstance) {
      engagementChartInstance.destroy();
    }

    engagementChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Trips Created',
            data: counts,
            backgroundColor: isDark ? 'rgba(129, 140, 248, 0.7)' : 'rgba(99, 102, 241, 0.8)',
            hoverBackgroundColor: isDark ? '#A5B4FC' : '#4F46E5',
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDark ? '#1E293B' : '#111827',
            titleColor: '#F9FAFB',
            bodyColor: '#F9FAFB',
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: function (context) {
                return ` ${context.parsed.y} trip${context.parsed.y !== 1 ? 's' : ''}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: textColor,
              font: { family: 'Inter', size: 11 },
              maxRotation: 45,
              autoSkip: true,
              maxTicksLimit: 15,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: textColor,
              font: { family: 'Inter', size: 11 },
              stepSize: 1,
              precision: 0,
            },
            grid: {
              color: gridColor,
            },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to load engagement chart:', err);
  }
}

function updateChartTheme() {
  if (!engagementChartInstance) return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#94A3B8' : '#6B7280';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';

  engagementChartInstance.data.datasets[0].backgroundColor = isDark
    ? 'rgba(129, 140, 248, 0.7)'
    : 'rgba(99, 102, 241, 0.8)';
  engagementChartInstance.options.scales.x.ticks.color = textColor;
  engagementChartInstance.options.scales.y.ticks.color = textColor;
  engagementChartInstance.options.scales.y.grid.color = gridColor;
  engagementChartInstance.update();
}

// ════════════════════════════════════════════════════════════════
// 2. TOP DESTINATIONS
// ════════════════════════════════════════════════════════════════
async function loadTopDestinations() {
  const container = document.getElementById('topDestinationsList');
  if (!container) return;

  try {
    const list = await apiGet('/admin/stats/top-destinations');
    if (!Array.isArray(list) || !list.length) {
      container.innerHTML = '<div style="text-align:center;padding:var(--space-md);color:var(--color-text-muted);">No destinations recorded yet.</div>';
      return;
    }

    container.innerHTML = list.map((item, index) => {
      const rank = index + 1;
      const rankClass = rank <= 3 ? `rank-badge--${rank}` : '';
      return `
        <div class="top-list-item">
          <div class="top-list-left">
            <span class="rank-badge ${rankClass}">${rank}</span>
            <span class="top-list-name" title="${escapeHtml(item.destination)}">
              <i class="fa-solid fa-location-dot" style="color:var(--color-primary);margin-right:6px;font-size:0.85rem;"></i>${escapeHtml(item.destination)}
            </span>
          </div>
          <span class="top-list-count">
            <i class="fa-solid fa-suitcase" style="font-size:0.75rem;"></i> ${item.trip_count} trip${item.trip_count !== 1 ? 's' : ''}
          </span>
        </div>`;
    }).join('');
  } catch (err) {
    console.error('Failed to load top destinations:', err);
    container.innerHTML = `<div style="text-align:center;padding:var(--space-md);color:#EF4444;">${escapeHtml(err.message || 'Failed to load')}</div>`;
  }
}

// ════════════════════════════════════════════════════════════════
// 3. TOP INTERESTS
// ════════════════════════════════════════════════════════════════
async function loadTopInterests() {
  const container = document.getElementById('topInterestsList');
  if (!container) return;

  try {
    const list = await apiGet('/admin/stats/top-interests');
    if (!Array.isArray(list) || !list.length) {
      container.innerHTML = '<div style="text-align:center;padding:var(--space-md);color:var(--color-text-muted);">No interests recorded yet.</div>';
      return;
    }

    container.innerHTML = list.map((item, index) => {
      const rank = index + 1;
      const rankClass = rank <= 3 ? `rank-badge--${rank}` : '';
      return `
        <div class="top-list-item">
          <div class="top-list-left">
            <span class="rank-badge ${rankClass}">${rank}</span>
            <span class="top-list-name" title="${escapeHtml(item.interest)}">
              <i class="fa-solid fa-tag" style="color:var(--color-primary);margin-right:6px;font-size:0.85rem;"></i>${escapeHtml(item.interest)}
            </span>
          </div>
          <span class="top-list-count">
            ${item.count} selection${item.count !== 1 ? 's' : ''}
          </span>
        </div>`;
    }).join('');
  } catch (err) {
    console.error('Failed to load top interests:', err);
    container.innerHTML = `<div style="text-align:center;padding:var(--space-md);color:#EF4444;">${escapeHtml(err.message || 'Failed to load')}</div>`;
  }
}

// ════════════════════════════════════════════════════════════════
// 4. USER MANAGEMENT (Search, Paginate, Deactivate)
// ════════════════════════════════════════════════════════════════
async function loadUsers() {
  const tbody = document.getElementById('userTableBody');
  if (!tbody) return;

  try {
    const params = new URLSearchParams({
      page: userState.page,
      limit: userState.limit,
    });
    if (userState.search) params.append('search', userState.search);
    if (userState.status) params.append('status', userState.status);

    const data = await apiGet(`/admin/users?${params.toString()}`);
    if (!data) return;

    userState.total = data.total || 0;
    userState.totalPages = data.total_pages || 1;

    renderUsersTable(data.users || []);
    renderUserPagination();
  } catch (err) {
    console.error('Failed to load users:', err);
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty-row" style="color:#EF4444;">${escapeHtml(err.message || 'Failed to load users')}</td></tr>`;
  }
}

function renderUsersTable(users) {
  const tbody = document.getElementById('userTableBody');
  if (!tbody) return;

  if (!users.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="table-empty-row">
          <div style="font-size:1.5rem;margin-bottom:6px;">🔍</div>
          <div>No users found matching your criteria.</div>
        </td>
      </tr>`;
    return;
  }

  const currentUser = getCurrentUser();

  tbody.innerHTML = users.map((u) => {
    const isSelf = currentUser && currentUser.email === u.email;
    const isActive = u.is_active !== false;
    const statusBadge = isActive
      ? `<span class="admin-badge-status admin-badge-status--active"><i class="fa-solid fa-circle-check"></i> Active</span>`
      : `<span class="admin-badge-status admin-badge-status--inactive"><i class="fa-solid fa-ban"></i> Deactivated</span>`;

    const roleBadge = u.is_admin
      ? `<span style="font-size:0.75rem;font-weight:700;color:var(--color-primary);background:var(--color-primary-soft);padding:2px 8px;border-radius:var(--radius-full);">Admin</span>`
      : `<span style="font-size:0.75rem;color:var(--color-text-muted);">Traveler</span>`;

    let actionBtn = '';
    if (isSelf) {
      actionBtn = `<span style="font-size:0.75rem;color:var(--color-text-light);">Current User</span>`;
    } else if (isActive) {
      actionBtn = `
        <button class="btn-action-deactivate" onclick="handleDeactivateUser('${u.id}', '${escapeHtml(u.name)}')">
          <i class="fa-solid fa-user-xmark"></i> Deactivate
        </button>`;
    } else {
      actionBtn = `
        <button class="btn-action-reactivate" onclick="handleReactivateUser('${u.id}', '${escapeHtml(u.name)}')">
          <i class="fa-solid fa-user-check"></i> Reactivate
        </button>`;
    }

    return `
      <tr>
        <td>
          <div style="font-weight:600;color:var(--color-text);">${escapeHtml(u.name)}</div>
          <div style="font-size:0.8125rem;color:var(--color-text-muted);">${escapeHtml(u.email)}</div>
        </td>
        <td>${roleBadge}</td>
        <td style="white-space:nowrap;">${formatDate(u.created_at)}</td>
        <td>
          <span style="font-weight:600;color:var(--color-primary);">${u.trip_count ?? 0}</span> trip${(u.trip_count ?? 0) !== 1 ? 's' : ''}
        </td>
        <td>${statusBadge}</td>
        <td style="text-align:right;">${actionBtn}</td>
      </tr>`;
  }).join('');
}

function renderUserPagination() {
  const info = document.getElementById('userPaginationInfo');
  const pageNum = document.getElementById('userPageNumber');
  const prevBtn = document.getElementById('userPrevBtn');
  const nextBtn = document.getElementById('userNextBtn');

  const start = userState.total === 0 ? 0 : (userState.page - 1) * userState.limit + 1;
  const end = Math.min(userState.page * userState.limit, userState.total);

  if (info) info.textContent = `Showing ${start} to ${end} of ${userState.total} users`;
  if (pageNum) pageNum.textContent = `Page ${userState.page} of ${userState.totalPages}`;
  if (prevBtn) prevBtn.disabled = userState.page <= 1;
  if (nextBtn) nextBtn.disabled = userState.page >= userState.totalPages;
}

function changeUserPage(delta) {
  const newPage = userState.page + delta;
  if (newPage >= 1 && newPage <= userState.totalPages) {
    userState.page = newPage;
    loadUsers();
  }
}

async function handleDeactivateUser(userId, userName) {
  if (!confirm(`Are you sure you want to deactivate the account for "${userName}"? They will no longer be able to log in.`)) {
    return;
  }

  try {
    await apiPatch(`/admin/users/${userId}/deactivate`);
    showToast(`User "${userName}" deactivated`, 'success');
    await Promise.all([loadUsers(), loadOverviewStats()]);
  } catch (err) {
    showToast(err.message || 'Failed to deactivate user', 'error');
  }
}

async function handleReactivateUser(userId, userName) {
  try {
    await apiPatch(`/admin/users/${userId}/reactivate`);
    showToast(`User "${userName}" reactivated`, 'success');
    await Promise.all([loadUsers(), loadOverviewStats()]);
  } catch (err) {
    showToast(err.message || 'Failed to reactivate user', 'error');
  }
}

// ════════════════════════════════════════════════════════════════
// 5. ALL TRIPS LIST (Search, Filter, Paginate, Read-Only View)
// ════════════════════════════════════════════════════════════════
async function loadTrips() {
  const tbody = document.getElementById('tripTableBody');
  if (!tbody) return;

  try {
    const params = new URLSearchParams({
      page: tripState.page,
      limit: tripState.limit,
    });
    if (tripState.search) params.append('search', tripState.search);
    if (tripState.status && tripState.status !== 'all') params.append('status', tripState.status);

    const data = await apiGet(`/admin/trips?${params.toString()}`);
    if (!data) return;

    tripState.total = data.total || 0;
    tripState.totalPages = data.total_pages || 1;

    renderTripsTable(data.trips || []);
    renderTripPagination();
  } catch (err) {
    console.error('Failed to load trips:', err);
    tbody.innerHTML = `<tr><td colspan="7" class="table-empty-row" style="color:#EF4444;">${escapeHtml(err.message || 'Failed to load trips')}</td></tr>`;
  }
}

function renderTripsTable(trips) {
  const tbody = document.getElementById('tripTableBody');
  if (!tbody) return;

  if (!trips.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty-row">
          <div style="font-size:1.5rem;margin-bottom:6px;">🗺️</div>
          <div>No platform trips found matching your criteria.</div>
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = trips.map((t) => {
    const days = tripDays(t.start_date, t.end_date);
    const currency = t.currency || 'INR';

    const statusBadge = `<span class="admin-badge-status admin-badge-status--${t.status || 'draft'}">${escapeHtml(t.status || 'Draft')}</span>`;

    return `
      <tr>
        <td>
          <div style="font-weight:700;color:var(--color-text);">
            <i class="fa-solid fa-location-dot" style="color:var(--color-primary);margin-right:6px;"></i>${escapeHtml(t.destination)}
          </div>
          <div style="font-size:0.8125rem;color:var(--color-text-muted);"><i class="fa-solid fa-plane-departure" style="font-size:0.75rem;"></i> From ${escapeHtml(t.from_city)}</div>
        </td>
        <td>
          <div style="font-weight:600;color:var(--color-text);">${escapeHtml(t.owner_name || 'Unknown')}</div>
          <div style="font-size:0.8125rem;color:var(--color-text-muted);">${escapeHtml(t.owner_email || '—')}</div>
        </td>
        <td style="white-space:nowrap;">
          <div>${formatDate(t.start_date)} – ${formatDate(t.end_date)}</div>
          <div style="font-size:0.8125rem;color:var(--color-text-muted);">${days} day${days !== 1 ? 's' : ''}</div>
        </td>
        <td>
          <i class="fa-solid fa-users" style="color:var(--color-text-muted);margin-right:4px;"></i>${t.travelers}
        </td>
        <td style="font-weight:600;white-space:nowrap;">
          ${formatCurrency(t.budget, currency)}
        </td>
        <td>${statusBadge}</td>
        <td style="text-align:right;">
          <a href="trip-detail.html?id=${t.id}" class="btn-action-view" title="View read-only itinerary">
            <i class="fa-solid fa-eye"></i> View
          </a>
        </td>
      </tr>`;
  }).join('');
}

function renderTripPagination() {
  const info = document.getElementById('tripPaginationInfo');
  const pageNum = document.getElementById('tripPageNumber');
  const prevBtn = document.getElementById('tripPrevBtn');
  const nextBtn = document.getElementById('tripNextBtn');

  const start = tripState.total === 0 ? 0 : (tripState.page - 1) * tripState.limit + 1;
  const end = Math.min(tripState.page * tripState.limit, tripState.total);

  if (info) info.textContent = `Showing ${start} to ${end} of ${tripState.total} trips`;
  if (pageNum) pageNum.textContent = `Page ${tripState.page} of ${tripState.totalPages}`;
  if (prevBtn) prevBtn.disabled = tripState.page <= 1;
  if (nextBtn) nextBtn.disabled = tripState.page >= tripState.totalPages;
}

function changeTripPage(delta) {
  const newPage = tripState.page + delta;
  if (newPage >= 1 && newPage <= tripState.totalPages) {
    tripState.page = newPage;
    loadTrips();
  }
}

// ════════════════════════════════════════════════════════════════
// SEARCH & FILTERS CONTROLS (Debounced)
// ════════════════════════════════════════════════════════════════
function initSearchAndFilters() {
  // User Search
  const userSearch = document.getElementById('userSearchInput');
  if (userSearch) {
    userSearch.addEventListener(
      'input',
      debounce((e) => {
        userState.search = e.target.value.trim();
        userState.page = 1;
        loadUsers();
      }, 300)
    );
  }

  // User Status Filter
  const userStatus = document.getElementById('userStatusFilter');
  if (userStatus) {
    userStatus.addEventListener('change', (e) => {
      userState.status = e.target.value;
      userState.page = 1;
      loadUsers();
    });
  }

  // Trip Search
  const tripSearch = document.getElementById('tripSearchInput');
  if (tripSearch) {
    tripSearch.addEventListener(
      'input',
      debounce((e) => {
        tripState.search = e.target.value.trim();
        tripState.page = 1;
        loadTrips();
      }, 300)
    );
  }

  // Trip Status Filter
  const tripStatus = document.getElementById('tripStatusFilter');
  if (tripStatus) {
    tripStatus.addEventListener('change', (e) => {
      tripState.status = e.target.value;
      tripState.page = 1;
      loadTrips();
    });
  }
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
