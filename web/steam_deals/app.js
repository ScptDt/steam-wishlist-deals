// ── Helpers ──
function $(id) { return document.getElementById(id); }
function togglePw(btn) {
  const inp = btn.previousElementSibling;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── Config fields (saveable) ──
const CONFIG_FIELDS = ['vanity','key','hltb','output','discount','genres','family_json','itad_key','compare','telegram_token','telegram_chat','discord_webhook'];
const FILTER_FIELDS = ['max_price','min_reviews','min_review_count','max_hours','top','sort','budget','max_workers'];
const CHECK_FIELDS  = ['deck_only','deck_verified','new_only','csv','no_cache'];
const GENRE_SUGGESTIONS = [
  'action', 'adventure', 'indie', 'rpg', 'strategy', 'simulation', 'casual', 'sports',
  'racing', 'puzzle', 'platformer', 'metroidvania', 'roguelike', 'roguelite', 'soulslike',
  'survival', 'horror', 'open world', 'sandbox', 'crafting', 'city builder', '4x', 'turn-based',
  'real-time strategy', 'deckbuilder', 'card game', 'tactical', 'shooter', 'fps', 'third-person',
  'co-op', 'multiplayer', 'singleplayer', 'visual novel', 'rhythm', 'bullet hell', 'tower defense'
];
const DESKTOP_FALLBACK_HINTS = {
  'missing-webview': 'No se encontro un backend nativo compatible para pywebview. Continuas en la misma Web UI desde tu navegador.',
  'window-timeout': 'La ventana nativa tardo demasiado en iniciar. Se abrio automaticamente la Web UI en el navegador.',
  'window-error': 'La ventana nativa fallo al iniciar. Se abrio automaticamente la Web UI en el navegador.',
};
const desktopFallback = getDesktopFallbackInfo();
let desktopFallbackAnnounced = false;

function getDesktopFallbackInfo() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('desktop_fallback') !== '1') return null;
  const reason = params.get('reason') || 'window-error';
  return {
    reason,
    title: 'Modo: Fallback web desde desktop',
    hint: DESKTOP_FALLBACK_HINTS[reason] || DESKTOP_FALLBACK_HINTS['window-error'],
  };
}

function getConfig() {
  const c = {};
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el) return;
    if (f === 'discount') c[f] = parseInt(el.value);
    else c[f] = el.value.trim() || null;
  });
  c.vanity = normalizeVanity(c.vanity);
  return c;
}

function normalizeVanity(value) {
  const v = (value || '').trim();
  if (!v) return '';
  if (v.startsWith('http://') || v.startsWith('https://')) return v;
  if (/^\d{16,}$/.test(v)) return `https://steamcommunity.com/profiles/${v}/`;
  if (v.startsWith('id/')) return `https://steamcommunity.com/${v.endsWith('/') ? v : v + '/'}`;
  if (v.startsWith('profiles/')) return `https://steamcommunity.com/${v.endsWith('/') ? v : v + '/'}`;
  return `https://steamcommunity.com/id/${v}/`;
}

function getFilters() {
  const f = {};
  FILTER_FIELDS.forEach(k => {
    const el = $(k);
    if (!el) return;
    const v = el.value.trim();
    if (k === 'sort') f[k] = v;
    else if (v) f[k] = parseFloat(v);
  });
  CHECK_FIELDS.forEach(k => {
    const el = $(k);
    if (el) f[k] = el.checked;
  });
  return f;
}

function fillForm(cfg) {
  if (!cfg) return;
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    if (f === 'discount') {
      el.value = cfg[f];
      $('disc-val').textContent = cfg[f] + '%';
    } else if (f === 'genres') {
      el.value = Array.isArray(cfg[f]) ? cfg[f].join(', ') : (cfg[f] || '');
    } else if (f === 'output') {
      el.value = cfg.output_dir || cfg.output || '';
    } else {
      el.value = cfg[f] || '';
    }
  });
  FILTER_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    el.value = String(cfg[f]);
  });
  CHECK_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    el.checked = !!cfg[f];
  });
}

const genresInput = $('genres');
const genresSuggestions = $('genres-suggestions');
let genresActiveIndex = -1;

function _genresSelectedSet() {
  const set = new Set();
  const parts = (genresInput.value || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
  parts.forEach(p => set.add(p));
  return set;
}

function _genresCurrentToken() {
  const raw = genresInput.value || '';
  const lastComma = raw.lastIndexOf(',');
  const tokenStartBase = lastComma === -1 ? 0 : lastComma + 1;
  const leadingSpaces = (raw.slice(tokenStartBase).match(/^\s*/) || [''])[0].length;
  const start = tokenStartBase + leadingSpaces;
  return {
    raw,
    start,
    token: raw.slice(start).trim().toLowerCase(),
  };
}

function hideGenreSuggestions() {
  genresActiveIndex = -1;
  genresSuggestions.classList.add('hidden');
  genresSuggestions.innerHTML = '';
}

function applyGenreSuggestion(genre) {
  const ctx = _genresCurrentToken();
  const before = ctx.raw.slice(0, ctx.start);
  genresInput.value = `${before}${genre}, `;
  hideGenreSuggestions();
  genresInput.focus();
}

function renderGenreSuggestions() {
  const ctx = _genresCurrentToken();
  if (!ctx.token) {
    hideGenreSuggestions();
    return;
  }
  const selected = _genresSelectedSet();
  const items = GENRE_SUGGESTIONS
    .filter(g => g.includes(ctx.token) && !selected.has(g.toLowerCase()))
    .slice(0, 8);

  if (!items.length) {
    hideGenreSuggestions();
    return;
  }

  genresSuggestions.innerHTML = items.map((g, i) =>
    `<button type="button" class="genre-suggestion${i === genresActiveIndex ? ' active' : ''}" data-genre="${g}">${g}</button>`
  ).join('');
  genresSuggestions.classList.remove('hidden');

  genresSuggestions.querySelectorAll('.genre-suggestion').forEach(btn => {
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      applyGenreSuggestion(btn.dataset.genre || '');
    });
  });
}

genresInput.addEventListener('input', renderGenreSuggestions);
genresInput.addEventListener('focus', renderGenreSuggestions);
genresInput.addEventListener('blur', () => setTimeout(hideGenreSuggestions, 120));
genresInput.addEventListener('keydown', (e) => {
  const buttons = Array.from(genresSuggestions.querySelectorAll('.genre-suggestion'));
  if (!buttons.length || genresSuggestions.classList.contains('hidden')) return;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    genresActiveIndex = (genresActiveIndex + 1) % buttons.length;
    renderGenreSuggestions();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    genresActiveIndex = genresActiveIndex <= 0 ? buttons.length - 1 : genresActiveIndex - 1;
    renderGenreSuggestions();
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    if (genresActiveIndex >= 0 && genresActiveIndex < buttons.length) {
      e.preventDefault();
      applyGenreSuggestion(buttons[genresActiveIndex].dataset.genre || '');
    }
  } else if (e.key === 'Escape') {
    hideGenreSuggestions();
  }
});

// ── Wizard ──
let wizStep = 0;
const WIZ_TOTAL = 4;

function wizUpdateDots() {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    const d = document.getElementById('dot-' + i);
    d.className = 'dot' + (i === wizStep ? ' active' : i < wizStep ? ' done' : '');
  }
}

function wizShowStep(n) {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    document.getElementById('wiz-step-' + i).classList.toggle('active', i === n);
  }
  wizStep = n;
  wizUpdateDots();
  if (n === 3) {
    document.getElementById('wiz-summary-vanity').textContent = document.getElementById('wiz-vanity').value.trim() || '(no configurado)';
    document.getElementById('wiz-summary-key').textContent = document.getElementById('wiz-key').value.trim() ? 'Configurada' : 'No (modo publico)';
    document.getElementById('wiz-summary-itad').textContent = document.getElementById('wiz-itad').value.trim() ? 'Configurada' : 'No';
  }
}

function wizNext() {
  if (wizStep === 0 && !document.getElementById('wiz-vanity').value.trim()) {
    const inp = document.getElementById('wiz-vanity');
    inp.style.borderColor = 'var(--red)';
    inp.focus();
    setTimeout(() => inp.style.borderColor = '', 2000);
    return;
  }
  if (wizStep < WIZ_TOTAL - 1) wizShowStep(wizStep + 1);
}

function wizPrev() {
  if (wizStep > 0) wizShowStep(wizStep - 1);
}

function wizFinish() {
  const vanity = document.getElementById('wiz-vanity').value.trim();
  const key = document.getElementById('wiz-key').value.trim();
  const itad = document.getElementById('wiz-itad').value.trim();
  document.getElementById('vanity').value = vanity;
  if (key) document.getElementById('key').value = key;
  if (itad) document.getElementById('itad_key').value = itad;
  const cfg = { vanity };
  if (key) cfg.key = key;
  if (itad) cfg.itad_key = itad;
  fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg) }).catch(() => {});
  closeWizard();
}

function prefillWizard(cfg, keepVanity=false) {
  const vanityInp = document.getElementById('wiz-vanity');
  vanityInp.value = '';
  vanityInp.placeholder = 'Ejemplo: https://steamcommunity.com/id/tu_usuario/';
  if (!cfg) return;
  if (keepVanity && cfg.vanity) vanityInp.value = cfg.vanity;
  if (cfg.key) document.getElementById('wiz-key').value = cfg.key;
  if (cfg.itad_key) document.getElementById('wiz-itad').value = cfg.itad_key;
}

function openWizard() {
  prefillWizard(getConfig(), false);
  wizShowStep(0);
  document.getElementById('wizard-overlay').style.display = 'block';
}

function closeWizard() {
  document.getElementById('wizard-overlay').style.display = 'none';
}

Promise.all([
  fetch('/api/config').then(r => r.json()),
  fetch('/api/ui-state').then(r => r.json()),
]).then(([cfg, state]) => {
  fillForm(cfg);
  prefillWizard(cfg, false);
  if (state) {
    setModeBanner(!!state.has_cache, !!state.has_config);
    announceDesktopFallback();
  }
  setActivePreset('rapido');
  if (state && state.has_cache) {
    closeWizard();
  } else {
    openWizard();
  }
}).catch(() => {
  fetch('/api/config').then(r => r.json()).then(cfg => {
    fillForm(cfg);
    prefillWizard(cfg, false);
    setModeBanner(false, !!(cfg && cfg.vanity));
    announceDesktopFallback();
    setActivePreset('rapido');
    if (cfg && cfg.vanity) closeWizard();
    else openWizard();
  }).catch(() => {});
});

const btnRun = $('btn-run');
const btnStop = $('btn-stop');
const btnPreflight = $('btn-preflight');
const btnDesktopDoctor = $('btn-desktop-doctor');
const btnDesktopAutofix = $('btn-desktop-autofix');
const btnClearCache = $('btn-clear-cache');
const btnOpenLast = $('btn-open-last');
const btnRunPd2 = $('btn-run-pd2');
const historyLeft = $('history-left');
const historyRight = $('history-right');
const historyIncludeSame = $('history-include-same');
const historyStatusFilter = $('history-status-filter');
const historySortDelta = $('history-sort-delta');
const historySearch = $('history-search');
const btnHistoryCompare = $('btn-history-compare');
const btnHistoryRefresh = $('btn-history-refresh');
const btnHistoryReset = $('btn-history-reset');
const btnHistoryQuickCompare = $('btn-history-quick-compare');
const btnHistoryPrevPage = $('btn-history-prev-page');
const btnHistoryNextPage = $('btn-history-next-page');
const historyPageInfo = $('history-page-info');
const historySummary = $('history-summary');
const historyStatusChart = $('history-status-chart');
const historyTopDeltas = $('history-top-deltas');
const historyTrend = $('history-trend');
const historyTableWrap = $('history-table-wrap');
const historyTableBody = $('history-table-body');
const consoleEl = $('console');
const btnCopyLog = $('btn-copy-log');
const btnDownloadLog = $('btn-download-log');
const progressBar = $('progress-bar');
const progressText = $('progress-text');
const fileLinks = $('file-links');
let abortCtrl = null;
let shownErrorHints = new Set();
let latestHistoryRuns = [];
let latestFilteredRuns = [];
let executionLogEntries = [];
let historyPage = 1;
const HISTORY_PAGE_SIZE = 20;

const HISTORY_FILTERS_STORAGE_KEY = 'steam_deals_history_filters_v1';
const HISTORY_DEFAULT_FILTERS = Object.freeze({
  include_same: false,
  status: 'all',
  sort_delta: 'default',
});

function saveHistoryFilters() {
  try {
    const payload = {
      include_same: !!(historyIncludeSame && historyIncludeSame.checked),
      status: historyStatusFilter ? historyStatusFilter.value : HISTORY_DEFAULT_FILTERS.status,
      sort_delta: historySortDelta ? historySortDelta.value : HISTORY_DEFAULT_FILTERS.sort_delta,
    };
    window.localStorage.setItem(HISTORY_FILTERS_STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {}
}

function applyHistoryFilterControls(filters = {}) {
  const merged = {...HISTORY_DEFAULT_FILTERS, ...(filters || {})};
  if (historyIncludeSame) {
    historyIncludeSame.checked = !!merged.include_same;
  }
  if (historyStatusFilter) {
    historyStatusFilter.value = merged.status || HISTORY_DEFAULT_FILTERS.status;
  }
  if (historySortDelta) {
    historySortDelta.value = merged.sort_delta || HISTORY_DEFAULT_FILTERS.sort_delta;
  }
}

function loadHistoryFilters() {
  try {
    const raw = window.localStorage.getItem(HISTORY_FILTERS_STORAGE_KEY);
    if (!raw) {
      applyHistoryFilterControls();
      return;
    }
    const parsed = JSON.parse(raw);
    const includeSame = !!(parsed && parsed.include_same);
    const status = parsed && typeof parsed.status === 'string' ? parsed.status : HISTORY_DEFAULT_FILTERS.status;
    const sortDelta = parsed && typeof parsed.sort_delta === 'string' ? parsed.sort_delta : HISTORY_DEFAULT_FILTERS.sort_delta;

    const validStatus = new Set(['all', 'changed', 'new', 'removed', 'same']);
    const validSort = new Set(['default', 'delta_desc', 'delta_asc', 'abs_desc']);

    applyHistoryFilterControls({
      include_same: includeSame,
      status: validStatus.has(status) ? status : HISTORY_DEFAULT_FILTERS.status,
      sort_delta: validSort.has(sortDelta) ? sortDelta : HISTORY_DEFAULT_FILTERS.sort_delta,
    });
  } catch (e) {
    applyHistoryFilterControls();
  }
}

function resetHistoryFilters({announce = false} = {}) {
  if (historySearch) {
    historySearch.value = '';
  }
  historyPage = 1;
  applyHistoryFilterControls();
  saveHistoryFilters();
  latestFilteredRuns = filterHistoryRuns(latestHistoryRuns, '');
  refreshRunSelectorsFromState();
  clearHistoryComparison();
  if (announce) {
    appendLine('Filtros del historico restablecidos.', 'ok');
  }
}

function formatHistoryRunLabel(run) {
  if (!run) return 'Run desconocido';
  const datePart = run.timestamp || run.date || run.id;
  const dealCount = Number(run.deal_count || 0);
  const saleName = run.sale_name ? String(run.sale_name) : 'Steam Deals';
  return `${datePart} · ${saleName} · ${dealCount} deals`;
}

function normalizeSearchValue(value) {
  return String(value || '').toLowerCase().trim();
}

function filterHistoryRuns(runs, query) {
  const list = Array.isArray(runs) ? runs : [];
  const q = normalizeSearchValue(query);
  if (!q) return list;
  return list.filter(run => {
    const haystack = [
      run && run.id,
      run && run.timestamp,
      run && run.date,
      run && run.sale_name,
      run && run.steam_id,
      run && run.vanity,
    ]
      .map(normalizeSearchValue)
      .join(' ');
    return haystack.includes(q);
  });
}

function setRunSelectorsFromList(runs) {
  if (!historyLeft || !historyRight) return;
  const list = Array.isArray(runs) ? runs : [];
  if (list.length < 2) {
    const message = list.length === 0 ? 'No hay runs para este filtro' : 'Se requieren 2 runs';
    historyLeft.innerHTML = `<option value="">${message}</option>`;
    historyRight.innerHTML = `<option value="">${message}</option>`;
    return;
  }

  const optionsHtml = list.map(run => {
    const value = escapeHtml(run.id || '');
    const label = escapeHtml(formatHistoryRunLabel(run));
    return `<option value="${value}">${label}</option>`;
  }).join('');
  historyLeft.innerHTML = optionsHtml;
  historyRight.innerHTML = optionsHtml;
  historyLeft.selectedIndex = 1;
  historyRight.selectedIndex = 0;
}

function getHistoryPageSlice(runs) {
  const list = Array.isArray(runs) ? runs : [];
  const totalPages = Math.max(1, Math.ceil(list.length / HISTORY_PAGE_SIZE));
  if (historyPage > totalPages) historyPage = totalPages;
  if (historyPage < 1) historyPage = 1;
  const start = (historyPage - 1) * HISTORY_PAGE_SIZE;
  return {
    totalPages,
    pageItems: list.slice(start, start + HISTORY_PAGE_SIZE),
  };
}

function updateHistoryPaginationUi(totalItems, totalPages) {
  if (historyPageInfo) {
    historyPageInfo.textContent = `Pagina ${historyPage} de ${totalPages} · ${totalItems} runs`;
  }
  if (btnHistoryPrevPage) btnHistoryPrevPage.disabled = historyPage <= 1;
  if (btnHistoryNextPage) btnHistoryNextPage.disabled = historyPage >= totalPages;
}

function refreshRunSelectorsFromState() {
  const list = Array.isArray(latestFilteredRuns) ? latestFilteredRuns : [];
  const { totalPages, pageItems } = getHistoryPageSlice(list);
  setRunSelectorsFromList(pageItems);
  updateHistoryPaginationUi(list.length, totalPages);
}

function applyHistoryRunSearch() {
  latestFilteredRuns = filterHistoryRuns(latestHistoryRuns, historySearch ? historySearch.value : '');
  historyPage = 1;
  refreshRunSelectorsFromState();
  if (!latestFilteredRuns.length) {
    appendLine('Busqueda de runs sin resultados.', 'warn');
  }
}

function formatCurrencyFromRaw(cents) {
  const value = Number(cents || 0);
  if (!Number.isFinite(value) || value === 0) return '?';
  const pesos = value / 100;
  return Number.isInteger(pesos) ? `$${pesos}` : `$${pesos.toFixed(2)}`;
}

function formatDelta(row) {
  if (row.delta_raw == null) return '—';
  const delta = Number(row.delta_raw || 0);
  if (delta === 0) return '$0';
  const sign = delta > 0 ? '+' : '-';
  const amount = formatCurrencyFromRaw(Math.abs(delta));
  return `${sign}${amount}`;
}

function renderHistoryRows(rows) {
  if (!historyTableBody || !historyTableWrap) return;
  if (!Array.isArray(rows) || rows.length === 0) {
    historyTableBody.innerHTML = '<tr><td colspan="5" style="color:var(--text2)">Sin cambios para mostrar con los filtros actuales.</td></tr>';
    historyTableWrap.classList.remove('hidden');
    return;
  }

  historyTableBody.innerHTML = rows.map(row => {
    const statusClass = `history-status history-status-${row.status || 'same'}`;
    const deltaClass = row.direction === 'down'
      ? 'history-delta-down'
      : row.direction === 'up'
      ? 'history-delta-up'
      : 'history-delta-same';
    const statusText = row.status === 'new'
      ? 'Nuevo'
      : row.status === 'removed'
      ? 'Salio'
      : row.status === 'changed'
      ? 'Cambio'
      : 'Igual';
    return `
      <tr>
        <td title="AppID ${escapeHtml(row.appid)}">${escapeHtml(row.name || row.appid)}</td>
        <td><span class="${statusClass}">${statusText}</span></td>
        <td>${escapeHtml(row.left_price || '?')}</td>
        <td>${escapeHtml(row.right_price || '?')}</td>
        <td class="${deltaClass}">${escapeHtml(formatDelta(row))}</td>
      </tr>
    `;
  }).join('');
  historyTableWrap.classList.remove('hidden');
}

function renderHistorySummary(summary) {
  if (!historySummary) return;
  const safe = summary || {};
  historySummary.innerHTML = [
    ['Run A', safe.left_total ?? 0],
    ['Run B', safe.right_total ?? 0],
    ['Cambios', safe.changed ?? 0],
    ['Nuevos', safe.new ?? 0],
    ['Salieron', safe.removed ?? 0],
  ].map(([label, value]) => `
    <div class="history-summary-item">${escapeHtml(label)}<br><strong>${escapeHtml(value)}</strong></div>
  `).join('');
  historySummary.classList.remove('hidden');
}

function renderHistoryStatusChart(summary) {
  if (!historyStatusChart) return;
  const safe = summary || {};
  const items = [
    { key: 'changed', label: 'Cambios', value: Number(safe.changed || 0), className: 'changed' },
    { key: 'new', label: 'Nuevos', value: Number(safe.new || 0), className: 'new' },
    { key: 'removed', label: 'Salieron', value: Number(safe.removed || 0), className: 'removed' },
    { key: 'same', label: 'Iguales', value: Number(safe.same || 0), className: 'same' },
  ];
  const maxValue = items.reduce((max, item) => Math.max(max, item.value), 0);
  const includeSameActive = !!(historyIncludeSame && historyIncludeSame.checked);

  historyStatusChart.innerHTML = `
    <div class="history-status-chart-title">Resumen visual por estado</div>
    <div class="history-status-bars">
      ${items.map(item => {
        const pct = maxValue > 0 ? Math.max(6, Math.round((item.value / maxValue) * 100)) : 0;
        const width = item.value > 0 ? `${pct}%` : '0%';
        return `
          <div class="history-status-bar-row">
            <div class="history-status-bar-label">${escapeHtml(item.label)}</div>
            <div class="history-status-bar-track">
              <div class="history-status-bar-fill history-status-bar-fill-${item.className}" style="width:${width}"></div>
            </div>
            <div class="history-status-bar-value">${escapeHtml(item.value)}</div>
          </div>
        `;
      }).join('')}
    </div>
    <div class="history-status-chart-note">
      ${includeSameActive ? 'Incluye estado "Iguales" (include_same activo).' : '"Iguales" depende de activar include_same.'}
    </div>
  `;
  historyStatusChart.classList.remove('hidden');
}

function clearHistoryComparison() {
  if (historySummary) {
    historySummary.innerHTML = '';
    historySummary.classList.add('hidden');
  }
  if (historyTableBody) historyTableBody.innerHTML = '';
  if (historyTableWrap) historyTableWrap.classList.add('hidden');
  if (historyStatusChart) {
    historyStatusChart.innerHTML = '';
    historyStatusChart.classList.add('hidden');
  }
  if (historyTopDeltas) {
    historyTopDeltas.innerHTML = '';
    historyTopDeltas.classList.add('hidden');
  }
  if (historyTrend) {
    historyTrend.innerHTML = '';
    historyTrend.classList.add('hidden');
  }
}

function parseHistoryRunTimestamp(run) {
  const raw = (run && (run.timestamp || run.date)) || '';
  const parsed = Date.parse(raw);
  if (!Number.isNaN(parsed)) return parsed;
  return 0;
}

function renderHistoryTrend(runs) {
  if (!historyTrend) return;
  const source = Array.isArray(runs) ? runs : [];
  if (source.length < 2) {
    historyTrend.innerHTML = '<div class="history-trend-title">Tendencia temporal (deals por run)</div><div class="history-trend-empty">Se necesitan al menos 2 runs para mostrar tendencia.</div>';
    historyTrend.classList.remove('hidden');
    return;
  }

  const normalized = source
    .map((run, index) => ({
      run,
      index,
      dealCount: Number((run && run.deal_count) || 0),
      ts: parseHistoryRunTimestamp(run),
    }))
    .sort((a, b) => {
      if (a.ts !== b.ts) return a.ts - b.ts;
      return a.index - b.index;
    })
    .slice(-20);

  const values = normalized.map(item => item.dealCount);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = Math.max(1, maxValue - minValue);

  const width = 720;
  const height = 120;
  const padX = 18;
  const padY = 14;
  const innerW = width - (padX * 2);
  const innerH = height - (padY * 2);
  const step = normalized.length > 1 ? innerW / (normalized.length - 1) : innerW;

  const points = normalized.map((item, idx) => {
    const x = padX + (idx * step);
    const y = padY + innerH - (((item.dealCount - minValue) / span) * innerH);
    return { x, y, value: item.dealCount };
  });

  const polyline = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const dots = points.map((p, idx) => {
    const title = `Run ${idx + 1}: ${p.value} deals`;
    return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.8" fill="var(--accent)"><title>${escapeHtml(title)}</title></circle>`;
  }).join('');

  const firstValue = values[0];
  const lastValue = values[values.length - 1];
  const trendDelta = lastValue - firstValue;
  const trendLabel = trendDelta === 0
    ? 'sin cambio neto'
    : trendDelta > 0
    ? `+${trendDelta} vs primer run`
    : `${trendDelta} vs primer run`;

  historyTrend.innerHTML = `
    <div class="history-trend-title">Tendencia temporal (deals por run · ultimos ${normalized.length})</div>
    <svg class="history-trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Tendencia temporal de deals por run">
      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="var(--card-border)" stroke-width="1" />
      <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" stroke="var(--card-border)" stroke-width="1" />
      <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${polyline}" />
      ${dots}
    </svg>
    <div class="history-trend-meta">
      <span>Min: ${escapeHtml(minValue)} · Max: ${escapeHtml(maxValue)}</span>
      <span>Tendencia: ${escapeHtml(trendLabel)}</span>
    </div>
  `;
  historyTrend.classList.remove('hidden');
}

function renderHistoryTopDeltas(rows) {
  if (!historyTopDeltas) return;
  const sourceRows = Array.isArray(rows) ? rows : [];
  const candidates = sourceRows.filter(row => {
    if (!row || typeof row !== 'object') return false;
    const delta = Number(row.delta_raw);
    return Number.isFinite(delta) && delta !== 0;
  });

  const topDown = candidates
    .filter(row => row.direction === 'down')
    .sort((a, b) => Number(a.delta_raw) - Number(b.delta_raw))
    .slice(0, 5);
  const topUp = candidates
    .filter(row => row.direction === 'up')
    .sort((a, b) => Number(b.delta_raw) - Number(a.delta_raw))
    .slice(0, 5);

  const renderColumn = (title, list, isDown) => {
    if (!list.length) {
      return `
        <div>
          <div class="history-top-deltas-col-title">${escapeHtml(title)}</div>
          <div class="history-top-deltas-empty">Sin cambios en esta categoria.</div>
        </div>
      `;
    }
    return `
      <div>
        <div class="history-top-deltas-col-title">${escapeHtml(title)}</div>
        ${list.map(row => `
          <div class="history-delta-item" title="AppID ${escapeHtml(row.appid)}">
            <div class="history-delta-label">${escapeHtml(row.name || row.appid)}</div>
            <div class="history-delta-value ${isDown ? 'history-delta-value-down' : 'history-delta-value-up'}">${escapeHtml(formatDelta(row))}</div>
          </div>
        `).join('')}
      </div>
    `;
  };

  historyTopDeltas.innerHTML = `
    <div class="history-top-deltas-title">Top cambios de precio (runs comparados)</div>
    <div class="history-top-deltas-grid">
      ${renderColumn('Mayores bajadas', topDown, true)}
      ${renderColumn('Mayores subidas', topUp, false)}
    </div>
  `;
  historyTopDeltas.classList.remove('hidden');
}

async function loadHistoryRuns() {
  if (!historyLeft || !historyRight) return;
  const response = await fetch('/api/history/runs?limit=50');
  if (!response.ok) {
    throw new Error('No se pudo cargar el historico de runs.');
  }
  const payload = await response.json();
  const runs = Array.isArray(payload.runs) ? payload.runs : [];
  latestHistoryRuns = runs;
  renderHistoryTrend(latestHistoryRuns);
  latestFilteredRuns = filterHistoryRuns(runs, historySearch ? historySearch.value : '');
  historyPage = 1;
  if (latestFilteredRuns.length < 2) {
    refreshRunSelectorsFromState();
    clearHistoryComparison();
    return;
  }
  refreshRunSelectorsFromState();
}

async function compareHistoryRuns() {
  if (!historyLeft || !historyRight) return;
  const left = historyLeft.value;
  const right = historyRight.value;
  if (!left || !right) {
    appendLine('Selecciona dos runs validos para comparar.', 'warn');
    return;
  }
  if (left === right) {
    appendLine('Selecciona runs distintos para la comparacion.', 'warn');
    return;
  }

  const includeSame = historyIncludeSame && historyIncludeSame.checked;
  const statusFilter = historyStatusFilter ? historyStatusFilter.value : 'all';
  const sortDelta = historySortDelta ? historySortDelta.value : 'default';
  const query = new URLSearchParams({
    left,
    right,
    include_same: includeSame ? 'true' : 'false',
    status: statusFilter,
    sort_delta: sortDelta,
  });

  const response = await fetch('/api/history/compare?' + query.toString());
  if (!response.ok) {
    throw new Error('No se pudo comparar los runs seleccionados.');
  }
  const payload = await response.json();
  const summary = payload.summary || {};
  if (summary.same == null && payload && payload.rows && Array.isArray(payload.rows)) {
    summary.same = payload.rows.filter(row => row && row.status === 'same').length;
  }
  renderHistorySummary(summary);
  renderHistoryStatusChart(summary);
  renderHistoryRows(payload.rows || []);
  renderHistoryTopDeltas(payload.rows || []);
}

function setModeBanner(hasCache, hasConfig) {
  const banner = $('mode-banner');
  const title = $('mode-title');
  const hint = $('mode-hint');
  if (banner) {
    banner.classList.toggle('mode-banner-fallback', !!desktopFallback);
  }
  if (desktopFallback) {
    title.textContent = desktopFallback.title;
    hint.textContent = desktopFallback.hint;
    return;
  }
  if (hasCache) {
    title.textContent = 'Modo: Actualizacion rapida';
    hint.textContent = hasConfig
      ? 'Se detecto cache local. Puedes ejecutar directo o ajustar presets.'
      : 'Hay cache local disponible. Revisa tu perfil y ejecuta cuando quieras.';
  } else {
    title.textContent = 'Modo: Primer setup';
    hint.textContent = 'No se detecto cache local. Usa el wizard y ejecuta tu primer analisis.';
  }
}

function announceDesktopFallback() {
  if (!desktopFallback || desktopFallbackAnnounced) return;
  desktopFallbackAnnounced = true;
  appendLine('Desktop fallback activo: ' + desktopFallback.hint, 'warn');
}

function setActivePreset(name) {
  document.querySelectorAll('#preset-row .preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.preset === name);
  });
}

function switchTab(name) {
  const dealsTab = $('tab-deals');
  const pd2Tab = $('tab-pd2');
  const dealsPanel = $('panel-deals');
  const pd2Panel = $('panel-pd2');
  const isPd2 = name === 'pd2';

  dealsPanel.style.display = isPd2 ? 'none' : 'block';
  pd2Panel.style.display = isPd2 ? 'block' : 'none';

   if (btnRun) btnRun.style.display = isPd2 ? 'none' : '';
   if (btnRunPd2) btnRunPd2.style.display = isPd2 ? '' : 'none';

  dealsTab.classList.toggle('active', !isPd2);
  pd2Tab.classList.toggle('active', isPd2);
  dealsTab.style.background = isPd2 ? 'var(--card)' : 'var(--accent)';
  dealsTab.style.color = isPd2 ? 'var(--text2)' : '#fff';
  pd2Tab.style.background = isPd2 ? 'var(--accent)' : 'var(--card)';
  pd2Tab.style.color = isPd2 ? '#fff' : 'var(--text2)';
}

function applyPreset(name) {
  if (name === 'rapido') {
    $('top').value = 10;
    $('discount').value = 60;
    $('disc-val').textContent = '60%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = true;
    $('no_cache').checked = false;
  } else if (name === 'completo') {
    $('top').value = 20;
    $('discount').value = 45;
    $('disc-val').textContent = '45%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = false;
    $('no_cache').checked = true;
  } else if (name === 'ahorro') {
    $('top').value = 12;
    $('discount').value = 70;
    $('disc-val').textContent = '70%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = true;
    $('no_cache').checked = false;
    if (!$('budget').value) $('budget').value = '500';
    if (!$('max_price').value) $('max_price').value = '250';
  }
  setActivePreset(name);
  appendLine('Preset aplicado: ' + name + '.', 'step');
}

function detectErrorCategory(text) {
  const t = (text || '').toLowerCase();
  if (!t) return null;
  if (t.includes('429') || t.includes('rate limit') || t.includes('too many requests')) return 'rate-limit';
  if (t.includes('unicodeencodeerror') || t.includes('cp1252') || t.includes('codec can\'t encode') || t.includes('encoding')) return 'encoding';
  if (t.includes('failed to fetch') || t.includes('timeout') || t.includes('timed out') || t.includes('connection') || t.includes('dns') || t.includes('name or service not known')) return 'network';
  if (t.includes('vanity') || t.includes('steam id') || t.includes('config invalida') || t.includes('falta el perfil') || t.includes('no se encontr') || t.includes('api key') || t.includes('invalid')) return 'config';
  return null;
}

function errorHintForCategory(category) {
  if (category === 'network') {
    return 'SUGERENCIA [network]: revisa internet/VPN/firewall y vuelve a intentar en unos segundos.';
  }
  if (category === 'config') {
    return 'SUGERENCIA [config]: valida perfil Steam, rutas opcionales y API keys; usa "Probar config" antes de ejecutar.';
  }
  if (category === 'rate-limit') {
    return 'SUGERENCIA [rate-limit]: Steam/servicios limitaron solicitudes; espera 1-3 minutos y reintenta.';
  }
  if (category === 'encoding') {
    return 'SUGERENCIA [encoding]: se detecto problema de codificacion de salida; reinicia app y usa la version mas reciente del ejecutable.';
  }
  return null;
}

function maybeShowActionableHint(text, cls) {
  if (cls !== 'err' && cls !== 'warn') return;
  const category = detectErrorCategory(text);
  if (!category || shownErrorHints.has(category)) return;
  shownErrorHints.add(category);
  const hint = errorHintForCategory(category);
  if (hint) appendLine(hint, 'warn');
}

async function runPreflightUI() {
  const pre = await fetch('/api/preflight', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({config: getConfig(), filters: getFilters()}),
  });
  const preData = await pre.json();
  appendLine('Preflight ejecutado.', preData.ok ? 'ok' : 'warn');
  (preData.warnings || []).forEach(w => appendLine('WARN: ' + w, 'warn'));
  (preData.issues || []).forEach(i => appendLine('ISSUE: ' + i, 'err'));
  return preData;
}

function doctorLineClass(text, overall) {
  if (!text) return 'dim';
  if (text.startsWith('[OK]')) return 'ok';
  if (text.startsWith('[WARN]')) return 'warn';
  if (text.startsWith('[FAIL]')) return 'err';
  if (text.startsWith('[fix]')) return 'step';
  if (text.startsWith('[done]')) return 'ok';
  if (text.startsWith('[skip]')) return 'dim';
  if (text.startsWith('Resultado general:')) {
    if (overall === 'READY') return 'ok';
    if (overall === 'BLOCKED') return 'err';
    return 'warn';
  }
  if (text.startsWith('===') || text.startsWith('Platform:')) return 'step';
  if (text.trim().startsWith('-')) return 'dim';
  return 'normal';
}

function appendDoctorReport(data, introText='Desktop Doctor ejecutado.') {
  appendLine(introText, data.exit_code === 1 ? 'err' : data.overall === 'READY' ? 'ok' : 'warn');
  (data.lines || []).forEach(line => {
    if (!line) return;
    appendLine(line, doctorLineClass(line, data.overall));
  });
}

function renderDoctorFixPlan(fixes) {
  if (!fixes || !fixes.length) {
    appendLine('No hay autofixes seguros disponibles para este entorno.', 'ok');
    return;
  }
  appendLine('Autofixes seguros disponibles:', 'step');
  fixes.forEach((fix, index) => {
    appendLine(`${index + 1}. ${fix.title} — ${fix.summary}`, 'dim');
    (fix.commands || []).forEach(command => appendLine('  - ' + command, 'dim'));
  });
}

async function fetchDesktopDoctorReport() {
  const resp = await fetch('/api/desktop-doctor', {method: 'POST'});
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
  }
  return data;
}

async function runDesktopDoctorUI() {
  const data = await fetchDesktopDoctorReport();
  appendDoctorReport(data);
  return data;
}

async function runDesktopDoctorAutofixUI() {
  const report = await fetchDesktopDoctorReport();
  appendDoctorReport(report, 'Desktop Doctor ejecutado antes del autofix.');
  renderDoctorFixPlan(report.fixes || []);
  if (!report.fixes || !report.fixes.length) {
    return {status: 'noop', report};
  }

  const accepted = window.confirm('Se aplicarán solo autofixes seguros del proyecto (.venv local, deps desktop en .venv y/o build local). ¿Continuar?');
  if (!accepted) {
    appendLine('Autofix desktop cancelado por el usuario.', 'warn');
    return {status: 'cancelled', report};
  }

  const resp = await fetch('/api/desktop-doctor/fix', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({confirm: true}),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
  }

  appendLine('Autofix desktop ejecutado.', data.status === 'failed' ? 'err' : data.status === 'applied' ? 'ok' : 'warn');
  (data.lines || []).forEach(line => {
    if (!line) return;
    appendLine(line, doctorLineClass(line, data.report && data.report.overall));
  });
  if (data.report) {
    appendDoctorReport(data.report, 'Doctor desktop tras autofix.');
  }
  return data;
}

btnPreflight.addEventListener('click', async () => {
  try {
    await runPreflightUI();
  } catch(e) {
    appendLine('No se pudo ejecutar preflight: ' + e.message, 'err');
  }
});

btnDesktopDoctor.addEventListener('click', async () => {
  btnDesktopDoctor.disabled = true;
  try {
    await runDesktopDoctorUI();
  } catch(e) {
    appendLine('No se pudo ejecutar Desktop Doctor: ' + e.message, 'err');
  } finally {
    btnDesktopDoctor.disabled = false;
  }
});

if (btnDesktopAutofix) btnDesktopAutofix.addEventListener('click', async () => {
  btnDesktopAutofix.disabled = true;
  if (btnDesktopDoctor) btnDesktopDoctor.disabled = true;
  try {
    await runDesktopDoctorAutofixUI();
  } catch(e) {
    appendLine('No se pudo ejecutar Autofix desktop: ' + e.message, 'err');
  } finally {
    btnDesktopAutofix.disabled = false;
    if (btnDesktopDoctor) btnDesktopDoctor.disabled = false;
  }
});

btnClearCache.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/cache/clear', {method: 'POST'});
    const d = await r.json();
    appendLine('Cache limpiada: ' + (d.removed || 0) + ' archivo(s).', 'ok');
  } catch(e) {
    appendLine('No se pudo limpiar cache: ' + e.message, 'err');
  }
});

btnOpenLast.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/files');
    const files = await r.json();
    if (!files || !files.length) {
      appendLine('No hay reportes generados todavia.', 'warn');
      return;
    }
    const name = files[0].name;
    window.open('/files/' + encodeURIComponent(name), '_blank');
    appendLine('Abriendo reporte: ' + name, 'ok');
  } catch(e) {
    appendLine('No se pudo abrir ultimo reporte: ' + e.message, 'err');
  }
});

function appendLine(text, cls) {
  const safeText = String(text ?? '');
  const safeCls = cls || 'normal';
  const div = document.createElement('div');
  div.className = 'line line-' + safeCls;
  div.textContent = safeText;
  consoleEl.appendChild(div);
  consoleEl.scrollTop = consoleEl.scrollHeight;
  executionLogEntries.push({text: safeText, cls: safeCls});
  updateExecutionLogButtons();
  maybeShowActionableHint(safeText, safeCls);
}

function getExecutionLogText() {
  return executionLogEntries.map(entry => entry.text).join('\n').trim();
}

function updateExecutionLogButtons() {
  const hasLog = executionLogEntries.some(entry => (entry.text || '').trim());
  if (btnCopyLog) btnCopyLog.disabled = !hasLog;
  if (btnDownloadLog) btnDownloadLog.disabled = !hasLog;
}

function resetExecutionLog() {
  executionLogEntries = [];
  consoleEl.innerHTML = '';
  updateExecutionLogButtons();
}

function flashButtonLabel(btn, label) {
  if (!btn) return;
  const original = btn.dataset.originalLabel || btn.innerHTML;
  btn.dataset.originalLabel = original;
  btn.textContent = label;
  window.setTimeout(() => {
    btn.innerHTML = btn.dataset.originalLabel || original;
  }, 2000);
}

function buildExecutionLogFilename() {
  return 'steam-deals-log-' + new Date().toISOString().replace(/[:]/g, '-').replace(/\..+/, '') + '.txt';
}

function copyExecutionLog() {
  const text = getExecutionLogText();
  if (!text) {
    flashButtonLabel(btnCopyLog, 'Sin log');
    return;
  }

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(text).then(() => {
      flashButtonLabel(btnCopyLog, 'Copiado!');
    }).catch(() => {
      window.prompt('Copia este log:', text);
      flashButtonLabel(btnCopyLog, 'Listo');
    });
    return;
  }

  window.prompt('Copia este log:', text);
  flashButtonLabel(btnCopyLog, 'Listo');
}

function downloadExecutionLog() {
  const text = getExecutionLogText();
  if (!text) {
    flashButtonLabel(btnDownloadLog, 'Sin log');
    return;
  }

  const blob = new Blob([text + '\n'], {type: 'text/plain;charset=utf-8'});
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = buildExecutionLogFilename();
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  flashButtonLabel(btnDownloadLog, 'Descargado');
}

if (btnCopyLog) btnCopyLog.addEventListener('click', copyExecutionLog);
if (btnDownloadLog) btnDownloadLog.addEventListener('click', downloadExecutionLog);

btnRun.addEventListener('click', async () => {
  if (!$('vanity').value.trim()) {
    $('vanity').focus();
    $('vanity').style.borderColor = 'var(--red)';
    setTimeout(() => $('vanity').style.borderColor = '', 2000);
    return;
  }

  shownErrorHints = new Set();
  resetExecutionLog();
  progressBar.style.width = '0%';
  progressText.textContent = 'Iniciando...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  btnStop.disabled = false;

  try {
    const preData = await runPreflightUI();
    if (!preData.ok) {
      appendLine('Validacion previa fallida. Corrige lo siguiente:', 'err');
      btnRun.disabled = false;
      btnStop.disabled = true;
      progressText.textContent = 'Config invalida';
      progressBar.style.width = '0%';
      return;
    }
  } catch(e) {
    appendLine('No se pudo ejecutar preflight: ' + e.message, 'warn');
  }

  abortCtrl = new AbortController();

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: getConfig(), filters: getFilters()}),
      signal: abortCtrl.signal,
    });

    if (!resp.ok && resp.status !== 409) {
      let msg = 'HTTP ' + resp.status;
      try {
        const body = await resp.json();
        if (body && body.error) msg = body.error;
      } catch(e) {}
      appendLine('Error del servidor: ' + msg, 'err');
      return;
    }

    if (resp.status === 409) {
      appendLine('Ya hay una ejecucion en curso.', 'warn');
      btnRun.disabled = false;
      btnStop.disabled = true;
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const ev = JSON.parse(line.slice(6));
              handleEvent(ev);
            } catch(e) {}
          }
        }
      }
    }
  } catch(e) {
    if (e.name !== 'AbortError') {
      appendLine('Error de conexion: ' + e.message, 'err');
    }
  }

  btnRun.disabled = false;
  btnStop.disabled = true;
  abortCtrl = null;
});

btnStop.addEventListener('click', async () => {
  try { await fetch('/api/stop', {method: 'POST'}); } catch(e) {}
  appendLine('--- Cancelado por el usuario ---', 'warn');
  btnStop.disabled = true;
  if (abortCtrl) abortCtrl.abort();
});

if (btnRunPd2) btnRunPd2.addEventListener('click', async () => {
  if (!$('vanity').value.trim()) { $('vanity').focus(); return; }
  shownErrorHints = new Set();
  resetExecutionLog();
  progressBar.style.width = '0%';
  progressBar.style.background = 'linear-gradient(90deg, #d4a84b, #b8922e)';
  progressText.textContent = 'PAYDAY 2 Tracker...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  btnRunPd2.disabled = true;
  btnStop.disabled = false;
  abortCtrl = new AbortController();
  try {
    const resp = await fetch('/api/run-pd2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        config: getConfig(),
        filters: {
          no_cache: $('pd2_no_cache').checked,
          csv: $('pd2_csv').checked,
          budget: $('pd2_budget').value ? parseFloat($('pd2_budget').value) : null,
          alert_price: $('pd2_alert').value ? parseFloat($('pd2_alert').value) : null,
          min_deal: $('pd2_min_deal').value ? parseInt($('pd2_min_deal').value) : null,
        }
      }),
      signal: abortCtrl.signal,
    });
    if (resp.status === 409) { appendLine('Ya hay una ejecucion en curso.', 'warn'); }
    else {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          for (const line of block.split('\n')) {
            if (line.startsWith('data: ')) {
              try { handleEvent(JSON.parse(line.slice(6))); } catch(e) {}
            }
          }
        }
      }
    }
  } catch(e) { if (e.name !== 'AbortError') appendLine('Error: ' + e.message, 'err'); }
  btnRun.disabled = false;
  btnRunPd2.disabled = false;
  btnStop.disabled = true;
  abortCtrl = null;
});

function handleEvent(ev) {
  if (ev.type === 'line') {
    appendLine(ev.text, ev.cls || 'normal');
  }
  else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    progressBar.style.width = pct + '%';
    progressText.textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label;
  }
  else if (ev.type === 'done') {
    progressBar.style.width = '100%';
    if (ev.exit_code === 0) {
      progressText.textContent = 'Completado';
      progressBar.style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
    } else {
      progressText.textContent = 'Error (codigo ' + ev.exit_code + ')';
      progressBar.style.background = 'linear-gradient(90deg, var(--red), #a02020)';
    }
    if (ev.files && ev.files.length) {
      showFiles(ev.files);
      appendQuickOpenButtons(ev.files);
    }
    syncLatestReportEmptyState(ev.files);
    syncLatestReportCard(ev.files);
  }
}

function showFiles(files) {
  fileLinks.innerHTML = '';
  const icons = {'.html': '&#128202;', '.md': '&#128196;', '.csv': '&#128203;', '.json': '&#123;&#125;'};
  files.forEach(f => {
    const name = f.split('/').pop();
    const ext = name.slice(name.lastIndexOf('.'));
    const icon = icons[ext] || '&#128196;';
    const a = document.createElement('a');
    a.className = 'file-link';
    a.href = '/files/' + encodeURIComponent(name);
    a.target = '_blank';
    a.innerHTML = icon + ' ' + name;
    fileLinks.appendChild(a);
  });
  fileLinks.classList.remove('hidden');
}

function latestReportUrl() {
  return new URL('/api/latest-report', window.location.origin).href;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatLatestReportTimestamp(value) {
  if (!value) return 'Fecha desconocida';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function latestReportCardEl() {
  let el = $('latest-report-card');
  if (el) return el;
  const card = $('output-card');
  if (!card) return null;
  el = document.createElement('div');
  el.id = 'latest-report-card';
  el.className = 'latest-report-card hidden';
  card.insertBefore(el, fileLinks);
  return el;
}

function hideLatestReportCard() {
  const el = latestReportCardEl();
  if (!el) return;
  el.classList.add('hidden');
  el.innerHTML = '';
}

function renderLatestReportCard(report) {
  const el = latestReportCardEl();
  if (!el) return;
  const meta = report && typeof report === 'object' ? (report.meta || {}) : {};
  const summary = report && typeof report === 'object' ? (report.summary || {}) : {};
  const subtitleParts = [];
  if (meta.profile) subtitleParts.push(`Perfil: ${escapeHtml(meta.profile)}`);
  subtitleParts.push(escapeHtml(formatLatestReportTimestamp(meta.generated_at)));
  const saleBadge = meta.sale_name ? `<span class="latest-report-badge">${escapeHtml(meta.sale_name)}</span>` : '';
  const stats = [
    ['Deals', summary.deals_count ?? 0],
    ['Top picks', summary.top_picks_count ?? 0],
    ['Alerts', summary.watchlist_alerts_count ?? 0],
    ['Regalos', summary.gift_ideas_count ?? 0],
  ];
  el.innerHTML = `
    <div class="latest-report-head">
      <div>
        <div class="latest-report-title">Ultimo reporte</div>
        <div class="latest-report-subtitle">${subtitleParts.join(' · ')}</div>
      </div>
      ${saleBadge}
    </div>
    <div class="latest-report-stats">
      ${stats.map(([label, value]) => `
        <div class="latest-report-stat">
          <div class="latest-report-stat-label">${escapeHtml(label)}</div>
          <div class="latest-report-stat-value">${escapeHtml(value)}</div>
        </div>
      `).join('')}
    </div>
  `;
  el.classList.remove('hidden');
}

async function syncLatestReportCard(files = null) {
  if (Array.isArray(files) && !hasJsonArtifact(files)) {
    hideLatestReportCard();
    return;
  }
  try {
    const resp = await fetch('/api/latest-report');
    if (!resp.ok) {
      hideLatestReportCard();
      return;
    }
    renderLatestReportCard(await resp.json());
  } catch (e) {
    hideLatestReportCard();
  }
}

function latestReportEmptyStateEl() {
  let el = $('latest-report-empty-state');
  if (el) return el;
  const card = $('output-card');
  if (!card) return null;
  el = document.createElement('div');
  el.id = 'latest-report-empty-state';
  el.className = 'latest-report-empty-state hidden';
  card.appendChild(el);
  return el;
}

function hasJsonArtifact(files) {
  return Array.isArray(files) && files.some(file => {
    const name = typeof file === 'string' ? file.split('/').pop() : (file && file.name) || '';
    return /\.json$/i.test(name || '');
  });
}

function showLatestReportEmptyState(message) {
  const el = latestReportEmptyStateEl();
  if (!el) return;
  el.innerHTML = `<strong>Sin reporte JSON todavia.</strong><span>${message}</span>`;
  el.classList.remove('hidden');
}

function hideLatestReportEmptyState() {
  const el = latestReportEmptyStateEl();
  if (!el) return;
  el.classList.add('hidden');
  el.innerHTML = '';
}

async function syncLatestReportEmptyState(files = null) {
  if (hasJsonArtifact(files)) {
    hideLatestReportEmptyState();
    return;
  }
  if (Array.isArray(files)) {
    showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar Abrir/Copiar JSON.');
    return;
  }
  try {
    const resp = await fetch('/api/files');
    const listedFiles = await resp.json();
    if (hasJsonArtifact(listedFiles)) {
      hideLatestReportEmptyState();
      return;
    }
  } catch (e) {}
  showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar Abrir/Copiar JSON.');
}

function isShareHtmlFile(filePath) {
  return /steam deals share .*\.html$/i.test((filePath || '').split('/').pop() || '');
}

function copyLatestReportUrl(btn) {
  const url = latestReportUrl();
  const resetLabel = btn.innerHTML;
  const showCopied = () => {
    btn.textContent = 'Copiado!';
    setTimeout(() => { btn.innerHTML = resetLabel; }, 2000);
  };

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(url).then(showCopied).catch(() => {
      window.prompt('Copia esta URL:', url);
    });
    return;
  }

  window.prompt('Copia esta URL:', url);
}

function appendQuickOpenButtons(files) {
  const htmlFile = files ? files.find(f => f.endsWith('.html') && !isShareHtmlFile(f)) : null;
  const shareHtmlFile = files ? files.find(isShareHtmlFile) : null;
  const jsonFile = files ? files.find(f => f.endsWith('.json')) : null;
  if (!htmlFile && !shareHtmlFile && !jsonFile) return;

  const btnContainer = document.createElement('div');
  btnContainer.style.cssText = 'margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap';

  if (htmlFile) {
    const openHtmlBtn = document.createElement('a');
    openHtmlBtn.href = '/files/' + encodeURIComponent(htmlFile.split('/').pop());
    openHtmlBtn.target = '_blank';
    openHtmlBtn.className = 'file-link';
    openHtmlBtn.innerHTML = '&#128202; Abrir reporte interactivo (con botones compartir)';
    btnContainer.appendChild(openHtmlBtn);
  }

  if (shareHtmlFile) {
    const openShareBtn = document.createElement('a');
    openShareBtn.href = '/files/' + encodeURIComponent(shareHtmlFile.split('/').pop());
    openShareBtn.target = '_blank';
    openShareBtn.className = 'file-link';
    openShareBtn.innerHTML = '&#128279; Abrir ultimo Share HTML';
    btnContainer.appendChild(openShareBtn);
  }

  if (jsonFile) {
    const openJsonBtn = document.createElement('a');
    openJsonBtn.href = '/api/latest-report';
    openJsonBtn.target = '_blank';
    openJsonBtn.className = 'file-link';
    openJsonBtn.innerHTML = '&#123;&#125; Abrir ultimo JSON';
    btnContainer.appendChild(openJsonBtn);

    const copyJsonBtn = document.createElement('button');
    copyJsonBtn.type = 'button';
    copyJsonBtn.className = 'file-link';
    copyJsonBtn.style.cursor = 'pointer';
    copyJsonBtn.style.fontFamily = 'inherit';
    copyJsonBtn.innerHTML = '&#128203; Copiar URL del ultimo JSON';
    copyJsonBtn.addEventListener('click', () => copyLatestReportUrl(copyJsonBtn));
    btnContainer.appendChild(copyJsonBtn);
  }

  fileLinks.appendChild(btnContainer);
  fileLinks.classList.remove('hidden');
}

function renderWatchlist(items) {
  const el = document.getElementById('wl-list');
  if (!items.length) { el.innerHTML = '<div style="color:var(--text2);font-size:.85rem">Watchlist vacia</div>'; return; }
  el.innerHTML = '<div style="font-size:.85rem;color:var(--text2);margin-bottom:.3rem">' + items.length + ' juegos en watchlist</div>' +
    items.map(w => '<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--card-border)">' +
      '<span style="flex:1;font-size:.85rem">' + w.name + ' <span style="color:var(--text2)">(AppID ' + w.appid + ')</span></span>' +
      '<span style="font-size:.85rem;color:var(--accent)">$' + w.target_price + '</span>' +
      '<button onclick="removeWatchlist(\'' + w.appid + '\')" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:1rem">&times;</button>' +
    '</div>').join('');
}
async function loadWatchlist() {
  try { const r = await fetch('/api/watchlist'); renderWatchlist(await r.json()); } catch(e) {}
}
async function addWatchlist() {
  const appid = document.getElementById('wl-appid').value.trim();
  const name = document.getElementById('wl-name').value.trim() || appid;
  const price = parseFloat(document.getElementById('wl-price').value);
  if (!appid || !price) return;
  try {
    const r = await fetch('/api/watchlist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid, name, target_price:price})});
    const d = await r.json(); renderWatchlist(d.items);
    document.getElementById('wl-appid').value = '';
    document.getElementById('wl-name').value = '';
    document.getElementById('wl-price').value = '';
  } catch(e) {}
}
async function removeWatchlist(appid) {
  try {
    const r = await fetch('/api/watchlist/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid})});
    const d = await r.json(); renderWatchlist(d.items);
  } catch(e) {}
}

let currentShareData = null;
let currentSteamUrl = '';

function openShareModal(game) {
  const name = game.name || game.steam_name || 'Unknown';
  const price = game.price || 0;
  const original = game.price_original || price;
  const discount = game.discount || 0;
  const minHist = game.min_hist || game.min_historical || null;
  const appid = game.appid;

  currentShareData = {
    name: name,
    appid: appid,
    price: price,
    original_price: original,
    discount: discount,
    min_hist: minHist,
    url: 'https://store.steampowered.com/app/' + appid + '/'
  };

  currentSteamUrl = 'https://store.steampowered.com/app/' + appid + '/';

  document.getElementById('share-name').textContent = name;
  document.getElementById('share-price').innerHTML = (original > price ? `<span>$${original} MXN </span>` : '') + `$${price} MXN (${discount}% OFF)`;
  document.getElementById('share-minhist').innerHTML = minHist ? `Minimo historico: <span>$${minHist} MXN</span>` : '';

  document.getElementById('share-modal').classList.add('active');
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
}

function copyShareLink() {
  if (!currentShareData) return;
  const encoded = btoa(JSON.stringify(currentShareData));
  const shareUrl = 'steamtools://share?data=' + encoded;
  navigator.clipboard.writeText(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link steamtools://', 2000);
  });
}

function copySteamLink() {
  if (!currentSteamUrl) return;
  navigator.clipboard.writeText(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link de Steam', 2000);
  });
}

function openInSteam() {
  if (currentSteamUrl) {
    window.open(currentSteamUrl, '_blank');
  }
}

loadWatchlist();
syncLatestReportEmptyState();
syncLatestReportCard();
loadHistoryFilters();
updateExecutionLogButtons();

if (historyIncludeSame) {
  historyIncludeSame.addEventListener('change', saveHistoryFilters);
}
if (historyStatusFilter) {
  historyStatusFilter.addEventListener('change', saveHistoryFilters);
}
if (historySortDelta) {
  historySortDelta.addEventListener('change', saveHistoryFilters);
}

if (btnHistoryRefresh) {
  btnHistoryRefresh.addEventListener('click', async () => {
    btnHistoryRefresh.disabled = true;
    try {
      await loadHistoryRuns();
      appendLine('Historico recargado.', 'ok');
    } catch (e) {
      appendLine('No se pudo recargar historico: ' + e.message, 'err');
    } finally {
      btnHistoryRefresh.disabled = false;
    }
  });
}

if (btnHistoryReset) {
  btnHistoryReset.addEventListener('click', () => {
    resetHistoryFilters({announce: true});
  });
}

if (btnHistoryCompare) {
  btnHistoryCompare.addEventListener('click', async () => {
    btnHistoryCompare.disabled = true;
    try {
      await compareHistoryRuns();
      appendLine('Comparacion de runs completada.', 'ok');
    } catch (e) {
      appendLine('No se pudo comparar runs: ' + e.message, 'err');
    } finally {
      btnHistoryCompare.disabled = false;
    }
  });
}

if (historySearch) {
  historySearch.addEventListener('input', () => {
    applyHistoryRunSearch();
  });
}

if (btnHistoryQuickCompare) {
  btnHistoryQuickCompare.addEventListener('click', async () => {
    const source = latestFilteredRuns.length >= 2 ? latestFilteredRuns : latestHistoryRuns;
    if (!source || source.length < 2) {
      appendLine('No hay suficientes runs para quick compare.', 'warn');
      return;
    }
    historyPage = 1;
    refreshRunSelectorsFromState();
    if (historyLeft && historyRight) {
      historyLeft.value = source[1].id || '';
      historyRight.value = source[0].id || '';
    }
    try {
      await compareHistoryRuns();
      appendLine('Quick compare: ultimos 2 runs.', 'ok');
    } catch (e) {
      appendLine('No se pudo ejecutar quick compare: ' + e.message, 'err');
    }
  });
}

if (btnHistoryPrevPage) {
  btnHistoryPrevPage.addEventListener('click', () => {
    historyPage -= 1;
    refreshRunSelectorsFromState();
  });
}

if (btnHistoryNextPage) {
  btnHistoryNextPage.addEventListener('click', () => {
    historyPage += 1;
    refreshRunSelectorsFromState();
  });
}

loadHistoryRuns().catch(() => {
  clearHistoryComparison();
});
