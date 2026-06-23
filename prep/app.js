/* ============================================================
   Argus Interview Prep — interactivity
   - Auto-builds the sidebar nav from <section data-group>
   - Search filter, scroll-spy, smooth scroll
   - "Mark reviewed" with localStorage persistence + progress bar
   ============================================================ */

/* ---- Durable progress storage ----------------------------------------------
   localStorage is keyed by (origin, key-string) and is INDEPENDENT of the page's
   contents — editing/rebuilding the HTML never wipes it. Progress only vanishes if
   the KEY changes or a section `id` is renamed. So:
   - STORE_KEY is FROZEN. Never change this scheme again (a change orphans data).
   - We migrate the original global key ('argus-prep-reviewed') forward, once.
   - Every access is guarded so a disabled/blocked store (private mode, file://
     restrictions in some browsers) degrades gracefully instead of throwing. */

// per-page namespace so the two pages don't cross-contaminate (shared section ids)
const PAGE = (location.pathname.split('/').pop() || 'index.html');
const STORE_KEY = 'argus-prep-reviewed:' + PAGE;     // FROZEN — do not edit
const LEGACY_KEY = 'argus-prep-reviewed';            // the original v1 global key

function safeGet(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}
function safeSet(key, val) {
  try { localStorage.setItem(key, val); return true; } catch (_) { return false; }
}
function loadReviewed() {
  // current key wins; otherwise migrate the legacy global key forward (once)
  let raw = safeGet(STORE_KEY);
  if (raw == null) {
    const legacy = safeGet(LEGACY_KEY);
    if (legacy != null) { safeSet(STORE_KEY, legacy); raw = legacy; }
  }
  try { return new Set(JSON.parse(raw || '[]')); } catch (_) { return new Set(); }
}

const sections = Array.from(document.querySelectorAll('section[id]'));
const nav = document.getElementById('nav');
const reviewed = loadReviewed();
// if storage is unavailable, tell the user instead of silently losing checkmarks
const STORAGE_OK = safeSet('argus-prep-test', '1');

const CHECK = `<svg class="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
const MARK_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;

/* ---- Build nav grouped by data-group, in document order ---- */
function buildNav() {
  const groups = [];
  const byName = {};
  sections.forEach(sec => {
    const g = sec.dataset.group || 'More';
    if (!byName[g]) { byName[g] = []; groups.push(g); }
    byName[g].push(sec);
  });

  groups.forEach(g => {
    const wrap = document.createElement('div');
    wrap.className = 'nav-group';
    const title = document.createElement('div');
    title.className = 'nav-group-title';
    title.textContent = g;
    wrap.appendChild(title);

    byName[g].forEach(sec => {
      const h2 = sec.querySelector('h2');
      const link = document.createElement('a');
      link.className = 'nav-link';
      link.dataset.target = sec.id;
      link.href = '#' + sec.id;
      link.innerHTML = `<span class="dot"></span><span class="lbl">${h2 ? h2.textContent : sec.id}</span>${CHECK}`;
      if (reviewed.has(sec.id)) link.classList.add('reviewed');
      link.addEventListener('click', e => {
        e.preventDefault();
        document.getElementById(sec.id).scrollIntoView({ behavior: 'smooth', block: 'start' });
        document.querySelector('.sidebar').classList.remove('open');
        history.replaceState(null, '', '#' + sec.id);
      });
      wrap.appendChild(link);
    });
    nav.appendChild(wrap);
  });
}

/* ---- Inject a "Mark reviewed" button into each section head ---- */
function addMarkButtons() {
  sections.forEach(sec => {
    const head = sec.querySelector('.sec-head');
    if (!head) return;
    const btn = document.createElement('button');
    btn.className = 'mark-btn' + (reviewed.has(sec.id) ? ' done' : '');
    btn.innerHTML = MARK_ICON + `<span>${reviewed.has(sec.id) ? 'Reviewed' : 'Mark reviewed'}</span>`;
    btn.addEventListener('click', () => toggleReviewed(sec.id, btn));
    head.appendChild(btn);
  });
}

function toggleReviewed(id, btn) {
  const link = nav.querySelector(`[data-target="${id}"]`);
  if (reviewed.has(id)) {
    reviewed.delete(id);
    btn.classList.remove('done');
    btn.querySelector('span').textContent = 'Mark reviewed';
    link && link.classList.remove('reviewed');
  } else {
    reviewed.add(id);
    btn.classList.add('done');
    btn.querySelector('span').textContent = 'Reviewed';
    link && link.classList.add('reviewed');
  }
  safeSet(STORE_KEY, JSON.stringify([...reviewed]));
  updateProgress();
}

function updateProgress() {
  const total = sections.length;
  const done = sections.filter(s => reviewed.has(s.id)).length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressLabel').textContent =
    `${done} of ${total} sections reviewed · ${pct}%` +
    (STORAGE_OK ? '' : '  ⚠ browser is blocking storage — progress won’t persist (try a local server)');
}

/* ---- Scroll-spy: highlight active nav link ---- */
function setupScrollSpy() {
  const links = Array.from(nav.querySelectorAll('.nav-link'));
  const linkFor = id => links.find(l => l.dataset.target === id);
  const observer = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (en.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        const l = linkFor(en.target.id);
        if (l) l.classList.add('active');
      }
    });
  }, { rootMargin: '-15% 0px -75% 0px', threshold: 0 });
  sections.forEach(s => observer.observe(s));
}

/* ---- Search filter over section text + nav ---- */
function setupSearch() {
  const input = document.getElementById('search');
  const noResults = document.getElementById('noResults');
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    let anyVisible = false;
    sections.forEach(sec => {
      const match = !q || sec.textContent.toLowerCase().includes(q);
      sec.style.display = match ? '' : 'none';
      const link = nav.querySelector(`[data-target="${sec.id}"]`);
      if (link) link.classList.toggle('hidden', !match);
      if (match) anyVisible = true;
    });
    // hide empty nav groups
    nav.querySelectorAll('.nav-group').forEach(grp => {
      const visible = grp.querySelectorAll('.nav-link:not(.hidden)').length;
      grp.style.display = visible ? '' : 'none';
    });
    noResults.style.display = anyVisible ? 'none' : 'block';
  });

  // "/" focuses search
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== input) {
      e.preventDefault(); input.focus();
    }
    if (e.key === 'Escape') { input.value = ''; input.dispatchEvent(new Event('input')); input.blur(); }
  });
}

/* ---- internal anchor jumps used by goTo() in content ---- */
window.goTo = function (id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

buildNav();
addMarkButtons();
setupScrollSpy();
setupSearch();
updateProgress();

// open the section in the URL hash on load
if (location.hash) {
  const el = document.querySelector(location.hash);
  if (el) setTimeout(() => el.scrollIntoView({ block: 'start' }), 100);
}