/**
 * auth.js — Auth state management.
 * Runs on every page to update the navbar (show/hide Login vs avatar),
 * and exposes helpers used across pages.
 */
document.addEventListener('DOMContentLoaded', function () {
  syncAuthUI();
});

/** Read current user from localStorage. Returns null if not logged in. */
function getCurrentUser() {
  try {
    const raw = localStorage.getItem('travora_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Returns true if a JWT token exists (does not validate expiry client-side). */
function isLoggedIn() {
  return !!localStorage.getItem('travora_token');
}

/** Sign out — clear storage and redirect home. */
function logout() {
  localStorage.removeItem('travora_token');
  localStorage.removeItem('travora_user');
  window.location.href = 'index.html';
}

/**
 * Update the navbar to reflect current auth state.
 * Shows avatar + user menu when logged in, Login/Sign Up buttons otherwise.
 */
function syncAuthUI() {
  const authNav   = document.getElementById('authNav');
  const userNav   = document.getElementById('userNav');
  const userAvatar = document.getElementById('userAvatar');
  const mobileAuthNav = document.getElementById('mobileAuthNav');

  const user = getCurrentUser();
  const loggedIn = isLoggedIn();

  if (loggedIn && user) {
    // Show avatar, hide buttons
    if (authNav)  authNav.style.display  = 'none';
    if (userNav)  userNav.style.display  = 'flex';
    if (mobileAuthNav) mobileAuthNav.style.display = 'none';

    if (userAvatar) {
      const initials = user.name
        ? user.name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
        : 'U';
      userAvatar.textContent = initials;
      userAvatar.title = user.name || 'My Account';

      // Avatar dropdown on click
      userAvatar.addEventListener('click', toggleUserDropdown);
    }
  } else {
    if (authNav)  authNav.style.display  = 'flex';
    if (userNav)  userNav.style.display  = 'none';
    if (mobileAuthNav) mobileAuthNav.style.display = 'flex';
  }
}

// ── User dropdown ──────────────────────────────────────────────
let dropdownEl = null;

function toggleUserDropdown(e) {
  e.stopPropagation();
  if (dropdownEl) { removeDropdown(); return; }

  const user = getCurrentUser();
  dropdownEl = document.createElement('div');
  dropdownEl.style.cssText = `
    position:absolute; top:calc(100% + 8px); right:0;
    background:var(--color-bg); border:1px solid var(--color-border);
    border-radius:var(--radius-md); box-shadow:var(--shadow-lg);
    min-width:200px; z-index:2000; overflow:hidden;
  `;
  dropdownEl.innerHTML = `
    <div style="padding:14px 16px;border-bottom:1px solid var(--color-border);">
      <div style="font-weight:700;color:var(--color-text);font-size:0.9375rem;">${escapeHtml(user?.name || 'Traveler')}</div>
      <div style="font-size:0.8125rem;color:var(--color-text-muted);margin-top:2px;">${escapeHtml(user?.email || '')}</div>
    </div>
    <a href="profile.html" style="display:flex;align-items:center;gap:10px;padding:12px 16px;color:var(--color-text);font-size:0.9rem;transition:background 0.15s;" onmouseover="this.style.background='var(--color-bg-secondary)'" onmouseout="this.style.background=''">
      <i class="fa-solid fa-user-pen" style="width:16px;color:var(--color-primary);"></i> My Profile
    </a>
    <a href="my-trips.html" style="display:flex;align-items:center;gap:10px;padding:12px 16px;color:var(--color-text);font-size:0.9rem;transition:background 0.15s;" onmouseover="this.style.background='var(--color-bg-secondary)'" onmouseout="this.style.background=''">
      <i class="fa-solid fa-suitcase" style="width:16px;color:var(--color-primary);"></i> My Trips
    </a>
    <a href="planner.html" style="display:flex;align-items:center;gap:10px;padding:12px 16px;color:var(--color-text);font-size:0.9rem;transition:background 0.15s;" onmouseover="this.style.background='var(--color-bg-secondary)'" onmouseout="this.style.background=''">
      <i class="fa-solid fa-wand-magic-sparkles" style="width:16px;color:var(--color-primary);"></i> Plan a Trip
    </a>
    <button onclick="logout()" style="display:flex;align-items:center;gap:10px;padding:12px 16px;color:#EF4444;font-size:0.9rem;width:100%;text-align:left;background:none;border:none;border-top:1px solid var(--color-border);cursor:pointer;transition:background 0.15s;font-family:inherit;" onmouseover="this.style.background='#FEF2F2'" onmouseout="this.style.background=''">
      <i class="fa-solid fa-right-from-bracket" style="width:16px;"></i> Sign Out
    </button>`;

  const avatar = document.getElementById('userAvatar');
  const wrapper = avatar.closest('.navbar__actions') || avatar.parentElement;
  wrapper.style.position = 'relative';
  wrapper.appendChild(dropdownEl);

  document.addEventListener('click', removeDropdown, { once: true });
}

function removeDropdown() {
  if (dropdownEl) { dropdownEl.remove(); dropdownEl = null; }
}

/**
 * Require auth — redirect to login if not signed in.
 * Call at top of pages that need auth.
 */
function requireAuth(redirectTo) {
  if (!isLoggedIn()) {
    const page = redirectTo || window.location.pathname.split('/').pop() || 'index.html';
    window.location.href = `login.html?redirect=${encodeURIComponent(page)}`;
    return false;
  }
  return true;
}
