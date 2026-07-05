/**
 * theme.js — Dark/light mode toggle
 * Persists preference in localStorage, applies on every page load.
 */
(function () {
  const STORAGE_KEY = 'travora_theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
      icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    }
  }

  function getPreferred() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  // Apply immediately (before paint)
  const current = getPreferred();
  applyTheme(current);

  // Wire toggle button after DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getPreferred()); // re-apply after DOM (icon might not exist yet above)

    const btn = document.getElementById('themeToggle');
    if (!btn) return;

    btn.addEventListener('click', function () {
      const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
    });

    // Navbar scroll shadow
    const navbar = document.getElementById('navbar');
    if (navbar) {
      window.addEventListener('scroll', function () {
        navbar.classList.toggle('scrolled', window.scrollY > 10);
      });
    }

    // Mobile hamburger
    const hamburger = document.getElementById('hamburger');
    const mobileMenu = document.getElementById('mobileMenu');
    if (hamburger && mobileMenu) {
      hamburger.addEventListener('click', function () {
        mobileMenu.classList.toggle('open');
        const spans = hamburger.querySelectorAll('span');
        const isOpen = mobileMenu.classList.contains('open');
        if (spans.length === 3) {
          spans[0].style.transform = isOpen ? 'rotate(45deg) translate(5px, 5px)' : '';
          spans[1].style.opacity  = isOpen ? '0' : '1';
          spans[2].style.transform = isOpen ? 'rotate(-45deg) translate(5px, -5px)' : '';
        }
      });
      // Close on outside click
      document.addEventListener('click', function (e) {
        if (!hamburger.contains(e.target) && !mobileMenu.contains(e.target)) {
          mobileMenu.classList.remove('open');
        }
      });
    }

    // Scroll-fade animations
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible'); }),
      { threshold: 0.1 }
    );
    document.querySelectorAll('.fade-up').forEach((el) => observer.observe(el));
  });
})();
