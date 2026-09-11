const state = {
  data: null,
  type: 'all',
  domain: 'all',
  query: '',
  lens: true,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const cardGrid = $('#cardGrid');
const cardTemplate = $('#cardTemplate');
const domainFilter = $('#domainFilter');
const itemCount = $('#itemCount');
const emptyState = $('#emptyState');
const reader = $('#reader');
const readerBackdrop = $('#readerBackdrop');
const lensToggle = $('#lensToggle');

function pretty(value = '') {
  return value
    .replaceAll('-', ' ')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function nodeMap() {
  return new Map((state.data?.nodes || []).map((node) => [node.id, node]));
}

function relationLabel(relation, currentId, nodes) {
  const outgoing = relation.from === currentId;
  const otherId = outgoing ? relation.to : relation.from;
  const other = nodes.get(otherId);
  return {
    relation: outgoing ? relation.relation : `INVERSE ${relation.relation}`,
    name: other?.name || pretty(otherId),
    note: relation.note || '',
  };
}

function renderDomains() {
  const domains = [...new Set(state.data.items.map((item) => item.domain).filter(Boolean))].sort();
  domainFilter.innerHTML = '';
  ['all', ...domains].forEach((domain) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = domain === 'all' ? 'All domains' : pretty(domain);
    button.classList.toggle('is-active', state.domain === domain);
    button.addEventListener('click', () => {
      state.domain = domain;
      renderDomains();
      renderCards();
    });
    domainFilter.appendChild(button);
  });
}

function filteredItems() {
  const q = state.query.trim().toLowerCase();
  const nodes = nodeMap();
  return state.data.items.filter((item) => {
    if (state.type !== 'all' && item.kind !== state.type) return false;
    if (state.domain !== 'all' && item.domain !== state.domain) return false;
    if (!q) return true;
    const related = (item.relationships || [])
      .map((rel) => relationLabel(rel, item.node_id, nodes).name)
      .join(' ');
    return [item.title, item.summary, item.domain, item.maturity, related]
      .join(' ')
      .toLowerCase()
      .includes(q);
  });
}

function renderCards() {
  const items = filteredItems();
  cardGrid.innerHTML = '';
  itemCount.textContent = items.length;
  emptyState.hidden = items.length > 0;

  for (const item of items) {
    const fragment = cardTemplate.content.cloneNode(true);
    const card = fragment.querySelector('.knowledge-card');
    const kind = fragment.querySelector('.kind-badge');
    kind.textContent = item.kind.toUpperCase();
    kind.classList.toggle('lab', item.kind === 'lab');
    fragment.querySelector('.domain-label').textContent = pretty(item.domain);
    fragment.querySelector('h3').textContent = item.title;
    fragment.querySelector('.card-summary').textContent = item.summary;
    fragment.querySelector('.maturity').textContent = item.maturity;
    const open = () => openReader(item);
    card.addEventListener('click', open);
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
    fragment.querySelector('.read-link').addEventListener('click', (event) => {
      event.stopPropagation();
      open();
    });
    cardGrid.appendChild(fragment);
  }
}

function section(title, text, className = '') {
  if (!text) return '';
  return `
    <section class="read-section ${className}">
      <h4>${title}</h4>
      <p>${escapeHtml(text)}</p>
    </section>`;
}

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[char]);
}

function renderLens(item) {
  const nodes = nodeMap();
  const node = nodes.get(item.node_id);
  const relations = (item.relationships || []).map((rel) => relationLabel(rel, item.node_id, nodes));
  const labLinks = relations.filter((rel) => {
    const target = [...nodes.values()].find((candidate) => candidate.name === rel.name);
    return target?.type === 'project' || target?.type === 'lab';
  });
  const relationMarkup = relations.length
    ? `<div class="relation-list">${relations.map((rel) => `
        <div class="relation">
          <b>${escapeHtml(rel.relation)}</b>
          <span>${escapeHtml(rel.name)}</span>
        </div>`).join('')}</div>`
    : '<div class="lens-value">No curated relationship has been published yet.</div>';

  const evidence = (item.evidence || []).map((entry) => `
    <a class="lens-link" href="${entry.url}" target="_blank" rel="noreferrer">
      <strong>${escapeHtml(entry.label)}</strong>
      <small>${escapeHtml(entry.detail || entry.url)}</small>
    </a>`).join('');

  const provenance = (item.provenance || []).map((entry) => `
    <a class="lens-link" href="${entry.url}" target="_blank" rel="noreferrer">
      <strong>${escapeHtml(entry.label)}</strong>
      <small>${escapeHtml(entry.path || entry.url)}</small>
    </a>`).join('');

  $('#lensBody').innerHTML = `
    <div class="lens-group">
      <strong>Graph identity</strong>
      <div class="lens-value">${escapeHtml(item.node_id)} · ${escapeHtml(node?.type || item.kind)}</div>
      <div class="chip-list" style="margin-top:10px">
        <span class="chip">${escapeHtml(pretty(item.domain))}</span>
        <span class="chip">${escapeHtml(item.maturity)}</span>
      </div>
    </div>
    <div class="lens-group">
      <strong>Connected knowledge</strong>
      ${relationMarkup}
    </div>
    ${labLinks.length ? `<div class="lens-group"><strong>Demonstrated by</strong><div class="chip-list">${labLinks.map((lab) => `<span class="chip">${escapeHtml(lab.name)}</span>`).join('')}</div></div>` : ''}
    ${evidence ? `<div class="lens-group"><strong>Implementation / evidence</strong>${evidence}</div>` : ''}
    <div class="lens-group">
      <strong>Provenance</strong>
      ${provenance || '<div class="lens-value">Curated graph snapshot.</div>'}
    </div>`;
}

function openReader(item) {
  $('#readerKicker').textContent = `${item.kind} · ${pretty(item.domain)}`;
  $('#readerTitle').textContent = item.title;
  $('#readerSummary').textContent = item.summary;
  $('#readerMeta').innerHTML = `<span>2 minute read</span><span>${escapeHtml(item.maturity)}</span>`;
  const read = item.two_minute_read || {};
  $('#readerBody').innerHTML = [
    section('The problem', read.problem),
    section('Mental model', read.mental_model),
    section('How it works', read.how_it_works),
    section('Failure modes & trade-offs', read.tradeoffs),
    section('Takeaway', read.takeaway || item.summary, 'takeaway'),
  ].join('');
  renderLens(item);
  reader.hidden = false;
  readerBackdrop.hidden = false;
  document.body.style.overflow = 'hidden';
  history.replaceState(null, '', `#${item.slug}`);
}

function closeReader() {
  reader.hidden = true;
  readerBackdrop.hidden = true;
  document.body.style.overflow = '';
  history.replaceState(null, '', location.pathname + location.search);
}

function setType(type) {
  state.type = type;
  $$('.nav-link').forEach((button) => button.classList.toggle('is-active', button.dataset.filter === type));
  $('#feedTitle').textContent = type === 'lab' ? 'Portfolio labs' : type === 'article' ? 'Two-minute articles' : 'Architecture knowledge';
  renderCards();
}

async function load() {
  try {
    const response = await fetch('data/spine.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    renderDomains();
    renderCards();
    const hash = location.hash.slice(1);
    if (hash) {
      const item = state.data.items.find((candidate) => candidate.slug === hash);
      if (item) openReader(item);
    }
  } catch (error) {
    cardGrid.innerHTML = `<div class="empty-state"><strong>Knowledge Spine could not load.</strong><span>${escapeHtml(error.message)}. Serve this folder through a local HTTP server.</span></div>`;
  }
}

$$('.nav-link').forEach((button) => button.addEventListener('click', () => setType(button.dataset.filter)));
$('#searchInput').addEventListener('input', (event) => { state.query = event.target.value; renderCards(); });
$('#closeReader').addEventListener('click', closeReader);
readerBackdrop.addEventListener('click', closeReader);
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !reader.hidden) closeReader(); });
lensToggle.addEventListener('click', () => {
  state.lens = !state.lens;
  lensToggle.setAttribute('aria-pressed', String(state.lens));
  document.body.classList.toggle('lens-off', !state.lens);
});

load();
