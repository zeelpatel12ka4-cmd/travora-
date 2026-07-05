/**
 * home.js — Home page logic.
 * Loads popular destinations from the API and renders them into #destinationsGrid.
 */
document.addEventListener('DOMContentLoaded', async function () {
  await loadPopularDestinations();
});

async function loadPopularDestinations() {
  const grid = document.getElementById('destinationsGrid');
  if (!grid) return;

  try {
    const destinations = await apiGet('/destinations?popular=true&limit=8');
    renderDestinationCards(grid, destinations);
  } catch (err) {
    // Fallback: show static cards using Unsplash images
    grid.innerHTML = buildFallbackCards();
    // Still trigger fade-up
    triggerFadeIn();
  }
}

function renderDestinationCards(grid, destinations) {
  if (!destinations || destinations.length === 0) {
    grid.innerHTML = buildFallbackCards();
    triggerFadeIn();
    return;
  }

  grid.innerHTML = destinations.slice(0, 8).map((d, i) => `
    <div class="dest-card fade-up${i > 0 ? ` fade-up-delay-${Math.min(i, 5)}` : ''}"
         onclick="goToPlanner('${escapeHtml(d.name)}')"
         style="cursor:pointer;"
         role="button"
         tabindex="0"
         aria-label="Plan a trip to ${escapeHtml(d.name)}">
      <div class="dest-card__img-wrap">
        <img
          src="${escapeHtml(d.image_url)}"
          alt="${escapeHtml(d.name)}, ${escapeHtml(d.country)}"
          loading="lazy"
          onerror="this.src='https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=400'"
        />
        <div class="dest-card__rating">
          <i class="fa-solid fa-star"></i> ${Number(d.rating).toFixed(1)}
        </div>
      </div>
      <div class="dest-card__body">
        <div class="dest-card__location">
          <i class="fa-solid fa-location-dot"></i> ${escapeHtml(d.country)}
        </div>
        <div class="dest-card__name">${escapeHtml(d.name)}</div>
        <div class="dest-card__tags">
          ${d.tags.slice(0, 3).map(t => `<span class="dest-card__tag">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>
    </div>
  `).join('');

  // Keyboard accessibility
  grid.querySelectorAll('.dest-card').forEach(card => {
    card.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' || e.key === ' ') card.click();
    });
  });

  triggerFadeIn();
}

function buildFallbackCards() {
  const cards = [
    { name: 'Bali',      country: 'Indonesia', rating: 4.9, tags: ['Beaches','Culture'], img: 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=400' },
    { name: 'Goa',       country: 'India',     rating: 4.7, tags: ['Beaches','Nightlife'], img: 'https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=400' },
    { name: 'Dubai',     country: 'UAE',       rating: 4.8, tags: ['Luxury','Modern'], img: 'https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=400' },
    { name: 'Tokyo',     country: 'Japan',     rating: 4.9, tags: ['Culture','Food'], img: 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400' },
    { name: 'Santorini', country: 'Greece',    rating: 4.9, tags: ['Romance','Views'], img: 'https://images.unsplash.com/photo-1613395877344-13d4a8e0d49e?w=400' },
    { name: 'Paris',     country: 'France',    rating: 4.8, tags: ['Romance','Art'], img: 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400' },
    { name: 'Maldives',  country: 'Maldives',  rating: 5.0, tags: ['Beaches','Luxury'], img: 'https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=400' },
    { name: 'Bangkok',   country: 'Thailand',  rating: 4.6, tags: ['Culture','Food'], img: 'https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=400' },
  ];

  return cards.map((d, i) => `
    <div class="dest-card fade-up${i > 0 ? ` fade-up-delay-${Math.min(i,5)}` : ''}"
         onclick="goToPlanner('${escapeHtml(d.name)}')" style="cursor:pointer;">
      <div class="dest-card__img-wrap">
        <img src="${d.img}" alt="${d.name}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=400'" />
        <div class="dest-card__rating"><i class="fa-solid fa-star"></i> ${d.rating}</div>
      </div>
      <div class="dest-card__body">
        <div class="dest-card__location"><i class="fa-solid fa-location-dot"></i> ${d.country}</div>
        <div class="dest-card__name">${d.name}</div>
        <div class="dest-card__tags">${d.tags.map(t => `<span class="dest-card__tag">${t}</span>`).join('')}</div>
      </div>
    </div>`).join('');
}

function triggerFadeIn() {
  // Re-observe new elements after render
  const observer = new IntersectionObserver(
    (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible'); }),
    { threshold: 0.05 }
  );
  document.querySelectorAll('.fade-up:not(.visible)').forEach((el) => observer.observe(el));
}

function goToPlanner(destination) {
  window.location.href = `planner.html?destination=${encodeURIComponent(destination)}`;
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
