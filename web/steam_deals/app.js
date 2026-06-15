// ── Helpers ──
function $(id) { return document.getElementById(id); }
const LOCAL_CSRF_HEADER = 'X-Steam-Tools-Local-Token';
const PAGE_QUERY = new URLSearchParams(window.location.search);
const IS_DESKTOP_NATIVE = PAGE_QUERY.get('desktop_native') === '1';
let pywebviewBridgeReady = !!(window.pywebview && window.pywebview.api);

window.addEventListener('pywebviewready', () => {
  pywebviewBridgeReady = true;
});

function getLocalSessionToken() {
  const meta = document.querySelector('meta[name="steam-tools-local-token"]');
  return meta ? meta.getAttribute('content') || '' : '';
}

function localMutableHeaders(headers = {}) {
  return Object.assign({}, headers, {[LOCAL_CSRF_HEADER]: getLocalSessionToken()});
}

function localMutableFetch(url, options = {}) {
  return fetch(url, Object.assign({}, options, {
    method: options.method || 'POST',
    headers: localMutableHeaders(options.headers || {}),
  }));
}

function togglePw(btn) {
  const inp = btn.previousElementSibling;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

function clearFieldError(inputEl) {
  if (!inputEl) return;
  inputEl.classList.remove('input-error');
  const field = inputEl.closest('.field') || inputEl.parentElement;
  if (!field) return;
  const msg = field.querySelector('.field-error');
  if (msg) msg.remove();
}

function formErrorSummaryEl() {
  return $('form-error-summary');
}

function hideFormErrorSummary() {
  const el = formErrorSummaryEl();
  if (!el) return;
  el.classList.add('hidden');
  el.innerHTML = '';
}

function showFormErrorSummary(messages) {
  const normalized = (messages || [])
    .map((item) => {
      if (!item) return null;
      if (typeof item === 'string') {
        return {message: item, fieldId: ''};
      }
      return {
        message: String(item.message || '').trim(),
        fieldId: String(item.fieldId || '').trim(),
      };
    })
    .filter((item) => item && item.message);

  const seen = new Set();
  const uniqueMessages = normalized.filter((item) => {
    const key = `${item.message}::${item.fieldId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const el = formErrorSummaryEl();
  if (!el || !uniqueMessages.length) {
    hideFormErrorSummary();
    return;
  }
  el.innerHTML = `
    <strong>Revisa estos campos antes de continuar:</strong>
    <ul>${uniqueMessages.map((item) => {
      const safeMsg = escapeHtml(item.message);
      const safeFieldId = escapeHtml(item.fieldId);
      if (!item.fieldId) {
        return `<li>${safeMsg}</li>`;
      }
      return `<li><button type="button" class="form-error-link" data-field-id="${safeFieldId}">${safeMsg}</button></li>`;
    }).join('')}</ul>
  `;

  el.querySelectorAll('.form-error-link').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.fieldId || '';
      const target = $(targetId);
      if (!target) return;
      target.scrollIntoView({behavior: 'smooth', block: 'center'});
      target.focus();
    });
  });

  el.classList.remove('hidden');
  try {
    el.focus();
  } catch (e) {}
}

function setFieldError(inputEl, message) {
  if (!inputEl) return;
  clearFieldError(inputEl);
  inputEl.classList.add('input-error');
  const field = inputEl.closest('.field') || inputEl.parentElement;
  if (!field) return;
  const msg = document.createElement('div');
  msg.className = 'field-error';
  msg.textContent = message;
  field.appendChild(msg);
}

function clearFieldErrorLater(inputEl) {
  if (!inputEl) return;
  const handler = () => clearFieldError(inputEl);
  inputEl.addEventListener('input', handler, {once: true});
}

function validateOptionalNumberRange(inputEl, {
  min = null,
  max = null,
  integer = false,
  label = 'Este campo',
} = {}) {
  if (!inputEl) return true;
  clearFieldError(inputEl);
  const raw = String(inputEl.value || '').trim();
  if (!raw) return true;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    setFieldError(inputEl, `${label}: ingresa un numero valido.`);
    clearFieldErrorLater(inputEl);
    return false;
  }
  if (integer && !Number.isInteger(value)) {
    setFieldError(inputEl, `${label}: usa un numero entero.`);
    clearFieldErrorLater(inputEl);
    return false;
  }
  if (min != null && value < min) {
    setFieldError(inputEl, `${label}: debe ser >= ${min}.`);
    clearFieldErrorLater(inputEl);
    return false;
  }
  if (max != null && value > max) {
    setFieldError(inputEl, `${label}: debe ser <= ${max}.`);
    clearFieldErrorLater(inputEl);
    return false;
  }
  return true;
}

function isLikelySteamProfileInput(value) {
  const raw = String(value || '').trim();
  if (!raw) return false;
  if (/\s/.test(raw)) return false;
  if (/^\d{16,}$/.test(raw)) return true;
  if (/^https?:\/\/steamcommunity\.com\/(id|profiles)\/.+/i.test(raw)) return true;
  if (/^(id|profiles)\/.+/i.test(raw)) return true;
  return /^[A-Za-z0-9_-]+$/.test(raw);
}

function parseCompareProfileInputs(value) {
  return String(value || '')
    .split(/[\n,]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

const SCHEDULER_INTERVAL_ERROR = 'Programación local: ingresa un intervalo en horas mayor que 0.';
const SCHEDULER_DEFAULT_CONFLICT_MESSAGE = 'Ya hay una ejecucion en curso.';

function getSchedulerControls() {
  return {
    enabledInput: $('schedule_enabled'),
    hoursInput: $('schedule_hours'),
  };
}

function syncSchedulerIntervalState() {
  const {enabledInput, hoursInput} = getSchedulerControls();
  const enabled = !!(enabledInput && enabledInput.checked);
  if (!hoursInput) return;
  hoursInput.disabled = !enabled;
  hoursInput.setAttribute('aria-disabled', enabled ? 'false' : 'true');
  if (!enabled) clearFieldError(hoursInput);
}

function bindSchedulerControls() {
  const {enabledInput, hoursInput} = getSchedulerControls();
  if (enabledInput) enabledInput.addEventListener('change', syncSchedulerIntervalState);
  if (hoursInput) hoursInput.addEventListener('input', () => clearFieldError(hoursInput));
  syncSchedulerIntervalState();
}

function getSchedulerFilters() {
  const {enabledInput, hoursInput} = getSchedulerControls();
  if (!enabledInput || !enabledInput.checked) return {};
  const rawScheduleHours = hoursInput ? String(hoursInput.value || '').trim() : '';
  return {schedule_enabled: true, schedule_hours: rawScheduleHours};
}

function schedulerHoursFromFilters(filters = {}) {
  const scheduleHours = Number(filters && filters.schedule_hours);
  return Number.isFinite(scheduleHours) && scheduleHours > 0 ? scheduleHours : null;
}

function isSchedulerEnabledFromFilters(filters = {}) {
  return !!(filters && filters.schedule_enabled === true && schedulerHoursFromFilters(filters) != null);
}

function schedulerIntervalLabel(filters = {}) {
  const scheduleHours = schedulerHoursFromFilters(filters);
  if (scheduleHours == null) return '';
  return String(scheduleHours);
}

function schedulerRunIntroMessage(filters = {}) {
  const interval = schedulerIntervalLabel(filters);
  if (!interval) return '';
  return `Programación local activada: intervalo elegido ${interval} hora(s). Primer plano y solo local: corre en primer plano local solo mientras esta Web/Desktop permanezca abierta; al cerrar Web/Desktop no continúa ni queda daemon/servicio/cron/Task Scheduler/proceso oculto/arranque automático. Usa Detener para cancelar la ejecución activa y evitar la siguiente repetición.`;
}

function schedulerRunConflictMessage(filters = {}) {
  if (!isSchedulerEnabledFromFilters(filters)) return SCHEDULER_DEFAULT_CONFLICT_MESSAGE;
  return 'Programación local: no se puede iniciar el ciclo programado porque ya hay una ejecución activa. Los ciclos programados no se solapan con una ejecución existente; espera a que termine o usa Detener.';
}

function validateSchedulerIntervalWhenEnabled() {
  const {enabledInput, hoursInput} = getSchedulerControls();
  if (!enabledInput || !enabledInput.checked) return true;
  if (!hoursInput) return false;
  clearFieldError(hoursInput);
  const rawScheduleHours = String(hoursInput.value || '').trim();
  const scheduleHours = Number(rawScheduleHours);
  if (!rawScheduleHours || !Number.isFinite(scheduleHours) || scheduleHours <= 0) {
    setFieldError(hoursInput, SCHEDULER_INTERVAL_ERROR);
    clearFieldErrorLater(hoursInput);
    return false;
  }
  return true;
}

function validateDealsFormBeforeRun() {
  const vanityInput = $('vanity');
  const compareInput = $('compare');
  const maxWorkersInput = $('max_workers');
  const topInput = $('top');
  const {hoursInput: scheduleHoursInput} = getSchedulerControls();
  const alertThresholds = [
    {input: $('alert_rise_pct'), min: 0, label: 'Subida mínima para alertar', message: 'Subida mínima para alertar: usa un numero mayor o igual a 0.'},
    {input: $('alert_global_margin_pct'), min: 0, label: 'Margen sobre mínimo global', message: 'Margen sobre mínimo global: usa un numero mayor o igual a 0.'},
    {input: $('alert_score_min'), min: 0, max: 100, label: 'Score mínimo para alertas', message: 'Score mínimo para alertas: usa un numero entre 0 y 100.'},
  ];
  const errors = [];

  clearFieldError(vanityInput);
  if (!vanityInput.value.trim()) {
    const msg = 'El perfil de Steam es obligatorio para ejecutar.';
    setFieldError(vanityInput, msg);
    errors.push({message: msg, fieldId: 'vanity'});
    vanityInput.focus();
    clearFieldErrorLater(vanityInput);
    showFormErrorSummary(errors);
    return false;
  }

  clearFieldError(compareInput);
  const compareProfiles = parseCompareProfileInputs(compareInput && compareInput.value);
  const invalidCompareProfile = compareProfiles.find(item => !isLikelySteamProfileInput(item));
  if (compareInput && invalidCompareProfile) {
    const msg = 'Comparar con: usa Vanity URL, Steam ID o URL valida; separa varios perfiles con coma o línea.';
    setFieldError(compareInput, msg);
    errors.push({message: msg, fieldId: 'compare'});
    compareInput.focus();
    clearFieldErrorLater(compareInput);
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateOptionalNumberRange(maxWorkersInput, { min: 1, max: 64, integer: true, label: 'Workers de enrichment' })) {
    errors.push({message: 'Workers de enrichment: usa un entero entre 1 y 64.', fieldId: 'max_workers'});
    maxWorkersInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateOptionalNumberRange(topInput, { min: 1, max: 50, integer: true, label: 'Top picks' })) {
    errors.push({message: 'Top picks: usa un entero entre 1 y 50.', fieldId: 'top'});
    topInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateSchedulerIntervalWhenEnabled()) {
    errors.push({message: SCHEDULER_INTERVAL_ERROR, fieldId: scheduleHoursInput ? scheduleHoursInput.id : ''});
    if (scheduleHoursInput) scheduleHoursInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  for (const threshold of alertThresholds) {
    if (!validateOptionalNumberRange(threshold.input, { min: threshold.min, max: threshold.max, label: threshold.label })) {
      errors.push({message: threshold.message, fieldId: threshold.input ? threshold.input.id : ''});
      if (threshold.input) threshold.input.focus();
      showFormErrorSummary(errors);
      return false;
    }
  }

  hideFormErrorSummary();
  return true;
}

function validatePd2FormBeforeRun() {
  const vanityInput = $('vanity');
  const budgetInput = $('pd2_budget');
  const alertInput = $('pd2_alert');
  const minDealInput = $('pd2_min_deal');
  const errors = [];

  clearFieldError(vanityInput);
  if (!vanityInput.value.trim()) {
    const msg = 'El perfil de Steam es obligatorio para ejecutar.';
    setFieldError(vanityInput, msg);
    errors.push({message: msg, fieldId: 'vanity'});
    vanityInput.focus();
    clearFieldErrorLater(vanityInput);
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateOptionalNumberRange(budgetInput, { min: 0, integer: false, label: 'Presupuesto MXN' })) {
    errors.push({message: 'Presupuesto MXN: usa un numero mayor o igual a 0.', fieldId: 'pd2_budget'});
    budgetInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateOptionalNumberRange(alertInput, { min: 0, integer: false, label: 'Alerta de precio' })) {
    errors.push({message: 'Alerta de precio: usa un numero mayor o igual a 0.', fieldId: 'pd2_alert'});
    alertInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  if (!validateOptionalNumberRange(minDealInput, { min: 0, max: 100, integer: true, label: 'Min. descuento para recomendar' })) {
    errors.push({message: 'Min. descuento para recomendar: usa un entero entre 0 y 100.', fieldId: 'pd2_min_deal'});
    minDealInput.focus();
    showFormErrorSummary(errors);
    return false;
  }

  hideFormErrorSummary();
  return true;
}

// ── Config fields (saveable) ──
const CONFIG_FIELDS = ['vanity','key','hltb','output','discount','genres','family_json','wishlist_external_matches_json','play_access_json','steam_access_json','player_preferences_json','itad_external_offers_cache','gg_deals_external_offers_cache','itad_key','compare','telegram_token','telegram_chat','discord_webhook'];
const FILTER_FIELDS = ['max_price','min_reviews','min_review_count','max_hours','top','sort','budget','max_workers','alert_rise_pct','alert_global_margin_pct','alert_score_min'];
const CHECK_FIELDS  = ['deck_only','deck_verified','new_only','csv','md_frontmatter','no_cache','free_weekend_live','free_weekend_lootscraper_live','itad_refresh_external_offers_cache'];
const GENRE_SUGGESTIONS = [
  'action', 'adventure', 'indie', 'rpg', 'strategy', 'simulation', 'casual', 'sports',
  'racing', 'puzzle', 'platformer', 'metroidvania', 'roguelike', 'roguelite', 'soulslike',
  'survival', 'horror', 'open world', 'sandbox', 'crafting', 'city builder', '4x', 'turn-based',
  'real-time strategy', 'deckbuilder', 'card game', 'tactical', 'shooter', 'fps', 'third-person',
  'co-op', 'multiplayer', 'singleplayer', 'visual novel', 'rhythm', 'bullet hell', 'tower defense'
];
const DESKTOP_FALLBACK_HINTS = {
  'forced-web-fallback': 'Fallback web forzado para validar el modo navegador sin intentar abrir la ventana nativa.',
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
    else if (f === 'compare') c[f] = parseCompareProfileInputs(el.value).join(', ') || null;
    else c[f] = el.value.trim() || null;
  });
  const pd2Output = $('pd2_output');
  const pd2Panel = $('panel-pd2');
  const pd2OutputValue = pd2Output ? pd2Output.value.trim() : '';
  if (pd2OutputValue && pd2Panel && pd2Panel.style.display !== 'none') {
    c.output = pd2OutputValue;
  }
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
  Object.assign(f, getSchedulerFilters());
  return f;
}

function fillForm(cfg) {
  if (!cfg) return;
  const outputValue = cfg.output_dir || cfg.output || '';
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    if (f === 'discount') {
      el.value = cfg[f];
      $('disc-val').textContent = cfg[f] + '%';
    } else if (f === 'genres') {
      el.value = Array.isArray(cfg[f]) ? cfg[f].join(', ') : (cfg[f] || '');
    } else if (f === 'output') {
      el.value = outputValue;
    } else {
      el.value = cfg[f] || '';
    }
  });
  const pd2Output = $('pd2_output');
  if (pd2Output) pd2Output.value = outputValue;
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

function applyDefaultTransientFilters() {
  const noCacheEl = $('no_cache');
  if (noCacheEl) noCacheEl.checked = false;
  const itadRefreshEl = $('itad_refresh_external_offers_cache');
  if (itadRefreshEl) itadRefreshEl.checked = false;
  const scheduleEnabledEl = $('schedule_enabled');
  if (scheduleEnabledEl) scheduleEnabledEl.checked = false;
  const scheduleHoursEl = $('schedule_hours');
  if (scheduleHoursEl) scheduleHoursEl.value = '';
  syncSchedulerIntervalState();
  const pd2NoCacheEl = $('pd2_no_cache');
  if (pd2NoCacheEl) pd2NoCacheEl.checked = false;
}

function enforceTransientFilterDefaults() {
  applyDefaultTransientFilters();
  const noCacheEl = $('no_cache');
  if (noCacheEl) {
    noCacheEl.defaultChecked = false;
    noCacheEl.removeAttribute('checked');
  }
  const itadRefreshEl = $('itad_refresh_external_offers_cache');
  if (itadRefreshEl) {
    itadRefreshEl.defaultChecked = false;
    itadRefreshEl.removeAttribute('checked');
  }
  const scheduleEnabledEl = $('schedule_enabled');
  if (scheduleEnabledEl) {
    scheduleEnabledEl.defaultChecked = false;
    scheduleEnabledEl.removeAttribute('checked');
  }
  const scheduleHoursEl = $('schedule_hours');
  if (scheduleHoursEl) {
    scheduleHoursEl.defaultValue = '';
    scheduleHoursEl.removeAttribute('value');
    scheduleHoursEl.disabled = true;
    scheduleHoursEl.setAttribute('aria-disabled', 'true');
  }
  const pd2NoCacheEl = $('pd2_no_cache');
  if (pd2NoCacheEl) {
    pd2NoCacheEl.defaultChecked = false;
    pd2NoCacheEl.removeAttribute('checked');
  }
}

bindSchedulerControls();

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
    setFieldError(inp, 'Ingresa tu Vanity URL, Steam ID o URL de perfil.');
    inp.focus();
    clearFieldErrorLater(inp);
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
  localMutableFetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg) }).catch(() => {});
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
  renderSteamOpenIdStatus({profile: cfg && cfg.steam_openid_profile});
  enforceTransientFilterDefaults();
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
    renderSteamOpenIdStatus({profile: cfg && cfg.steam_openid_profile});
    enforceTransientFilterDefaults();
    prefillWizard(cfg, false);
    setModeBanner(false, !!(cfg && cfg.vanity));
    announceDesktopFallback();
    setActivePreset('rapido');
    if (cfg && cfg.vanity) closeWizard();
    else openWizard();
  }).catch(() => {});
});

window.addEventListener('pageshow', () => {
  enforceTransientFilterDefaults();
});

const btnRun = $('btn-run');
const btnStop = $('btn-stop');
const btnPreflight = $('btn-preflight');
const btnDesktopDoctor = $('btn-desktop-doctor');
const btnDesktopAutofix = $('btn-desktop-autofix');
const btnClearCache = $('btn-clear-cache');
const btnOpenLast = $('btn-open-last');
const btnOpenOutputFolder = $('btn-open-output-folder');
const btnRunPd2 = $('btn-run-pd2');
const btnSteamOpenIdStart = $('btn-steam-openid-start');
const btnSteamOpenIdDisconnect = $('btn-steam-openid-disconnect');
const steamOpenIdStatus = $('steam-openid-status');
const steamOpenIdCard = document.querySelector('[data-steam-openid-card]');
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
const historySearchEmpty = $('history-search-empty');
const historySummary = $('history-summary');
const historySelectionSummary = $('history-selection-summary');
const historyStatusChart = $('history-status-chart');
const historyTopDeltas = $('history-top-deltas');
const historyTrend = $('history-trend');
const historyAnalyticsSummary = $('history-analytics-summary');
const historyGameDrilldown = $('history-game-drilldown');
const historyTableWrap = $('history-table-wrap');
const historyTableBody = $('history-table-body');
const consoleEl = $('console');
const btnCopyLog = $('btn-copy-log');
const btnDownloadLog = $('btn-download-log');
const progressBar = $('progress-bar');
const progressText = $('progress-text');
const progressContainer = progressBar ? progressBar.closest('.progress-container') : null;
const fileLinks = $('file-links');
let abortCtrl = null;
let shownErrorHints = new Set();
let latestHistoryRuns = [];
let latestFilteredRuns = [];
let executionLogEntries = [];
let runStatusHeartbeatTimer = null;
let runStatusHeartbeatOptions = null;
let runStatusHeartbeatStartedAt = 0;

function renderSteamOpenIdStatus(payload) {
  const profile = payload && payload.profile && typeof payload.profile === 'object'
    ? payload.profile
    : null;
  if (!steamOpenIdStatus) return;
  if (profile && profile.steamid) {
    const label = profile.persona_name || `SteamID ${profile.steamid}`;
    steamOpenIdStatus.textContent = `Conectado: ${label}. OpenID solo enlaza tu perfil; no entrega Steam Family, wishlist privada ni acceso a juegos propios privados (owned-private).`;
    if (steamOpenIdCard) steamOpenIdCard.dataset.steamOpenidState = 'connected';
    if (btnSteamOpenIdStart) btnSteamOpenIdStart.textContent = 'Reconectar Steam';
    if (btnSteamOpenIdDisconnect) btnSteamOpenIdDisconnect.classList.remove('hidden');
    const vanityInput = $('vanity');
    if (vanityInput && profile.profile_url && !vanityInput.value.trim()) {
      vanityInput.value = profile.profile_url;
    }
    return;
  }
  steamOpenIdStatus.textContent = 'Desconectado: puedes seguir usando el perfil manual. OpenID oficial solo enlaza tu SteamID/perfil; no da Steam Family, wishlist privada ni acceso a juegos propios privados (owned-private).';
  if (steamOpenIdCard) steamOpenIdCard.dataset.steamOpenidState = 'disconnected';
  if (btnSteamOpenIdStart) btnSteamOpenIdStart.textContent = 'Conectar con Steam';
  if (btnSteamOpenIdDisconnect) btnSteamOpenIdDisconnect.classList.add('hidden');
}

function safeSteamOpenIdUiError() {
  return 'No se pudo iniciar Steam Sign-in. Revisa que el servidor local tenga habilitado el endpoint protegido y vuelve a intentar.';
}

async function steamOpenIdJsonOrEmpty(resp) {
  try {
    return await resp.json();
  } catch (e) {
    return {};
  }
}

async function refreshSteamOpenIdStatus() {
  try {
    const resp = await fetch('/api/steam-openid/status');
    renderSteamOpenIdStatus(await resp.json());
  } catch (e) {
    renderSteamOpenIdStatus(null);
  }
}

async function startSteamOpenIdFlow() {
  if (!btnSteamOpenIdStart) return;
  btnSteamOpenIdStart.disabled = true;
  try {
    const resp = await localMutableFetch('/api/steam-openid/start', {method: 'POST'});
    const data = await steamOpenIdJsonOrEmpty(resp);
    if (!resp.ok || !data.login_url) {
      throw new Error(safeSteamOpenIdUiError());
    }
    window.location.href = data.login_url;
  } catch (e) {
    appendLine(safeSteamOpenIdUiError(), 'err');
    btnSteamOpenIdStart.disabled = false;
  }
}

async function disconnectSteamOpenIdProfile() {
  if (!btnSteamOpenIdDisconnect) return;
  btnSteamOpenIdDisconnect.disabled = true;
  try {
    const resp = await localMutableFetch('/api/steam-openid/disconnect', {method: 'POST'});
    const data = await steamOpenIdJsonOrEmpty(resp);
    if (!resp.ok) throw new Error('No se pudo desconectar Steam.');
    renderSteamOpenIdStatus(data);
    appendLine('Perfil Steam desconectado localmente.', 'ok');
  } catch (e) {
    appendLine('No se pudo desconectar Steam. No se muestran respuestas OpenID crudas.', 'err');
  } finally {
    btnSteamOpenIdDisconnect.disabled = false;
  }
}
let runStatusHeartbeatLastActivityAt = 0;
let historyPage = 1;
let latestHistoryComparisonPayload = null;
let selectedHistoryAppid = '';
const HISTORY_PAGE_SIZE = 20;
const HISTORY_DRILLDOWN_VISIBLE_CANDIDATES = 6;
const PRESET_MAX_WORKERS = Object.freeze({
  rapido: 12,
  completo: 16,
  ahorro: 8,
});

const HISTORY_FILTERS_STORAGE_KEY = 'steam_deals_history_filters_v1';
const HISTORY_DEFAULT_FILTERS = Object.freeze({
  include_same: false,
  status: 'all',
  sort_delta: 'default',
});
const HISTORY_NAV_STATE_STORAGE_KEY = 'steam_deals_history_nav_state_v1';

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

function saveHistoryNavState() {
  try {
    const payload = {
      page: historyPage,
      search: historySearch ? historySearch.value : '',
      left: historyLeft ? historyLeft.value : '',
      right: historyRight ? historyRight.value : '',
      appid: selectedHistoryAppid,
    };
    window.localStorage.setItem(HISTORY_NAV_STATE_STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {}
}

function loadHistoryNavState() {
  try {
    const raw = window.localStorage.getItem(HISTORY_NAV_STATE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      page: Number(parsed.page || 1) || 1,
      search: typeof parsed.search === 'string' ? parsed.search : '',
      left: typeof parsed.left === 'string' ? parsed.left : '',
      right: typeof parsed.right === 'string' ? parsed.right : '',
      appid: typeof parsed.appid === 'string' ? parsed.appid : '',
    };
  } catch (e) {
    return null;
  }
}

function getHistoryUrlState() {
  try {
    const params = new URLSearchParams(window.location.search || '');
    return {
      search: params.get('history_search') || '',
      left: params.get('history_left') || '',
      right: params.get('history_right') || '',
      appid: params.get('history_appid') || '',
      quick: params.get('history_quick') === '1',
    };
  } catch (e) {
    return {search: '', left: '', right: '', appid: '', quick: false};
  }
}

function replaceHistoryUrlState({search = '', left = '', right = '', appid = '', quick = false} = {}) {
  try {
    const url = new URL(window.location.href);
    if (search) url.searchParams.set('history_search', search);
    else url.searchParams.delete('history_search');
    if (left) url.searchParams.set('history_left', left);
    else url.searchParams.delete('history_left');
    if (right) url.searchParams.set('history_right', right);
    else url.searchParams.delete('history_right');
    if (appid) url.searchParams.set('history_appid', appid);
    else url.searchParams.delete('history_appid');
    if (quick) url.searchParams.set('history_quick', '1');
    else url.searchParams.delete('history_quick');
    window.history.replaceState({}, '', url.toString());
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
  saveHistoryNavState();
  replaceHistoryUrlState();
  latestFilteredRuns = filterHistoryRuns(latestHistoryRuns, '');
  refreshRunSelectorsFromState();
  clearHistoryComparison();
  if (announce) {
    appendLine('Filtros del histórico restablecidos.', 'ok');
  }
}

function formatHistoryRunLabel(run) {
  if (!run) return 'Ejecución desconocida';
  const datePart = run.timestamp || run.date || run.id;
  const dealCount = Number(run.deal_count || 0);
  const eventName = run.sale_name ? String(run.sale_name) : 'Sin evento detectado';
  return `${datePart} · ${eventName} · ${dealCount} ofertas`;
}

function findHistoryRunById(runId) {
  if (!runId) return null;
  return (latestHistoryRuns || []).find(run => run && run.id === runId) || null;
}

function renderHistorySelectionSummary(leftRun, rightRun, {quick = false} = {}) {
  if (!historySelectionSummary) return;
  historySelectionSummary.innerHTML = `
    <div class="history-selection-summary-title">${quick ? 'Comparación rápida activa' : 'Comparación activa'}</div>
    <div class="history-selection-summary-lines">
      <div><strong>Ejecución inicial:</strong> ${escapeHtml(formatHistoryRunLabel(leftRun))}</div>
      <div><strong>Ejecución comparada:</strong> ${escapeHtml(formatHistoryRunLabel(rightRun))}</div>
    </div>
  `;
  historySelectionSummary.classList.remove('hidden');
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
    const message = list.length === 0
      ? 'No hay ejecuciones que coincidan con esta búsqueda.'
      : 'Solo hay 1 ejecución visible; necesitas al menos 2 para comparar.';
    historyLeft.innerHTML = `<option value="">${message}</option>`;
    historyRight.innerHTML = `<option value="">${message}</option>`;
    return;
  }

  const optionsHtml = list.map(run => {
    const value = escapeHtml(run.id || '');
    const label = escapeHtml(formatHistoryRunLabel(run));
    return `<option value="${value}">${label}</option>`;
  }).join('');
  const previousLeft = historyLeft.value;
  const previousRight = historyRight.value;
  historyLeft.innerHTML = optionsHtml;
  historyRight.innerHTML = optionsHtml;
  const leftExists = list.some(run => run && run.id === previousLeft);
  const rightExists = list.some(run => run && run.id === previousRight);
  if (leftExists) historyLeft.value = previousLeft;
  else historyLeft.selectedIndex = 1;
  if (rightExists) historyRight.value = previousRight;
  else historyRight.selectedIndex = 0;
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
    historyPageInfo.textContent = `Página ${historyPage} de ${totalPages} · ${totalItems} ejecuciones`;
  }
  if (btnHistoryPrevPage) btnHistoryPrevPage.disabled = historyPage <= 1;
  if (btnHistoryNextPage) btnHistoryNextPage.disabled = historyPage >= totalPages;
}

function refreshRunSelectorsFromState() {
  const list = Array.isArray(latestFilteredRuns) ? latestFilteredRuns : [];
  const { totalPages, pageItems } = getHistoryPageSlice(list);
  setRunSelectorsFromList(pageItems);
  updateHistoryPaginationUi(list.length, totalPages);
  saveHistoryNavState();
}

function updateHistorySearchEmptyState(totalMatches) {
  if (!historySearchEmpty) return;
  const query = historySearch ? String(historySearch.value || '').trim() : '';
  if (!query) {
    historySearchEmpty.textContent = '';
    historySearchEmpty.classList.add('hidden');
    return;
  }
  if (totalMatches === 0) {
    historySearchEmpty.textContent = 'No hubo coincidencias para esa búsqueda. Prueba con una fecha, un evento o parte del perfil.';
    historySearchEmpty.classList.remove('hidden');
    return;
  }
  if (totalMatches === 1) {
    historySearchEmpty.textContent = 'Solo aparece 1 ejecución. Ajusta la búsqueda o usa menos filtros para poder comparar.';
    historySearchEmpty.classList.remove('hidden');
    return;
  }
  historySearchEmpty.textContent = `${totalMatches} ejecuciones coinciden con tu búsqueda.`;
  historySearchEmpty.classList.remove('hidden');
}

function resolveQuickCompareRuns() {
  const filteredRuns = Array.isArray(latestFilteredRuns) ? latestFilteredRuns : [];
  if (filteredRuns.length >= 2) {
    return {runs: filteredRuns, usedGlobalFallback: false};
  }
  const allRuns = Array.isArray(latestHistoryRuns) ? latestHistoryRuns : [];
  return {
    runs: allRuns,
    usedGlobalFallback: allRuns.length >= 2 && filteredRuns.length < 2,
  };
}

function prepareQuickCompareSelectors(quickCompare) {
  if (quickCompare.usedGlobalFallback) {
    if (historySearch) historySearch.value = '';
    latestFilteredRuns = quickCompare.runs;
    appendLine('La búsqueda actual no tiene 2 ejecuciones; comparando las 2 más recientes globales.', 'warn');
  }
  historyPage = 1;
  refreshRunSelectorsFromState();
  updateHistorySearchEmptyState(latestFilteredRuns.length);
}

function applyHistoryRunSearch() {
  latestFilteredRuns = filterHistoryRuns(latestHistoryRuns, historySearch ? historySearch.value : '');
  historyPage = 1;
  refreshRunSelectorsFromState();
  updateHistorySearchEmptyState(latestFilteredRuns.length);
  replaceHistoryUrlState({
    search: historySearch ? historySearch.value : '',
    left: historyLeft ? historyLeft.value : '',
    right: historyRight ? historyRight.value : '',
    quick: false,
  });
}

function applyHistoryRestoredState() {
  const urlState = getHistoryUrlState();
  const storedState = loadHistoryNavState();
  const mergedState = {
    search: urlState.search || (storedState && storedState.search) || '',
    left: urlState.left || (storedState && storedState.left) || '',
    right: urlState.right || (storedState && storedState.right) || '',
    appid: urlState.appid || (storedState && storedState.appid) || '',
    page: (storedState && storedState.page) || 1,
    quick: urlState.quick,
  };

  if (historySearch) historySearch.value = mergedState.search;
  historyPage = Math.max(1, Number(mergedState.page || 1) || 1);
  latestFilteredRuns = filterHistoryRuns(latestHistoryRuns, mergedState.search);
  refreshRunSelectorsFromState();
  updateHistorySearchEmptyState(latestFilteredRuns.length);

  if (historyLeft && mergedState.left) historyLeft.value = mergedState.left;
  if (historyRight && mergedState.right) historyRight.value = mergedState.right;
  selectedHistoryAppid = mergedState.appid;

  if (mergedState.quick && historyLeft && historyRight && historyLeft.value && historyRight.value) {
    compareHistoryRuns({quick: true}).catch(() => {});
    return;
  }

  if (historyLeft && historyRight && historyLeft.value && historyRight.value && mergedState.left && mergedState.right) {
    compareHistoryRuns().catch(() => {});
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
      ? 'Salió'
      : row.status === 'changed'
      ? 'Cambió'
      : 'Igual';
    return `
      <tr>
        <td title="AppID ${escapeHtml(row.appid)}"><div class="history-game-cell"><span>${escapeHtml(row.name || row.appid)}</span><button type="button" class="btn btn-ghost history-inline-btn" data-history-appid="${escapeHtml(row.appid)}">Ver historial</button></div></td>
        <td><span class="${statusClass}">${statusText}</span></td>
        <td>${escapeHtml(row.left_price || '?')}</td>
        <td>${escapeHtml(row.right_price || '?')}</td>
        <td class="${deltaClass}">${escapeHtml(formatDelta(row))}</td>
      </tr>
    `;
  }).join('');
  historyTableWrap.classList.remove('hidden');
}

function formatHistorySnapshotLabel(snapshot) {
  const eventName = snapshot && snapshot.sale_name ? ` · ${snapshot.sale_name}` : '';
  const dateText = snapshot && (snapshot.date || snapshot.timestamp) ? (snapshot.date || snapshot.timestamp) : 'Sin fecha';
  return `${dateText}${eventName}`;
}

function normalizeHistorySnapshots(snapshots) {
  const list = Array.isArray(snapshots) ? snapshots.slice() : [];
  return list.sort((a, b) => Date.parse((a && (a.timestamp || a.date)) || '') - Date.parse((b && (b.timestamp || b.date)) || ''));
}

function resolveHistoryDrilldownCandidates(payload) {
  const analytics = payload && payload.analytics ? payload.analytics : {};
  const candidates = [];
  const seen = new Set();
  const pushRows = (rows) => {
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      const appid = row && row.appid ? String(row.appid) : '';
      if (!appid || seen.has(appid)) return;
      seen.add(appid);
      candidates.push({appid, name: row.name || appid});
    });
  };
  pushRows(analytics.top_price_drops);
  pushRows(analytics.top_price_rises);
  pushRows(payload && payload.rows);
  return candidates;
}

function splitHistoryDrilldownCandidates(candidates, selectedAppid, limit = HISTORY_DRILLDOWN_VISIBLE_CANDIDATES) {
  const normalized = Array.isArray(candidates) ? candidates : [];
  const selected = normalized.find((item) => item.appid === selectedAppid);
  const visible = normalized.slice(0, limit);
  if (selected && !visible.some((item) => item.appid === selected.appid)) {
    visible.splice(Math.max(0, limit - 1), 1, selected);
  }
  const visibleIds = new Set(visible.map((item) => item.appid));
  return {
    visible,
    hidden: normalized.filter((item) => !visibleIds.has(item.appid)),
  };
}

function renderHistoryDrilldownButtons(items, selectedAppid) {
  return (Array.isArray(items) ? items : []).map((item) => `
    <button type="button" class="history-drilldown-btn${item.appid === selectedAppid ? ' is-active' : ''}" data-history-drilldown="${escapeHtml(item.appid)}">${escapeHtml(item.name)}</button>
  `).join('');
}

function renderHistoryAnalyticsSummary(payload) {
  if (!historyAnalyticsSummary) return;
  const analytics = payload && payload.analytics ? payload.analytics : {};
  const historyRuns = Array.isArray(analytics.history_runs) ? analytics.history_runs : [];
  const stateCounts = analytics.state_counts || {};
  if (!historyRuns.length) {
    historyAnalyticsSummary.innerHTML = '';
    historyAnalyticsSummary.classList.add('hidden');
    return;
  }
  historyAnalyticsSummary.innerHTML = `
    <div class="history-analytics-title">Contexto ampliado del historial</div>
    <div class="history-analytics-grid">
      <div class="history-analytics-card"><span>Ejecuciones analizadas</span><strong>${escapeHtml(historyRuns.length)}</strong></div>
      <div class="history-analytics-card"><span>Cambios</span><strong>${escapeHtml(stateCounts.changed || 0)}</strong></div>
      <div class="history-analytics-card"><span>Nuevos</span><strong>${escapeHtml(stateCounts.new || 0)}</strong></div>
      <div class="history-analytics-card"><span>Iguales</span><strong>${escapeHtml(stateCounts.same || 0)}</strong></div>
    </div>
    <div class="history-analytics-note">La tendencia general resume el volumen de ofertas por ejecución; el panel de abajo te deja bajar al historial de precio de un juego concreto.</div>
  `;
  historyAnalyticsSummary.classList.remove('hidden');
}

function renderHistoryGameDrilldown(payload, preferredAppid = '') {
  if (!historyGameDrilldown) return;
  latestHistoryComparisonPayload = payload;
  const analytics = payload && payload.analytics ? payload.analytics : {};
  const gameHistory = analytics.game_history || {};
  const candidates = resolveHistoryDrilldownCandidates(payload).filter((item) => Array.isArray(gameHistory[item.appid]) && gameHistory[item.appid].length > 0);
  if (!candidates.length) {
    historyGameDrilldown.innerHTML = '';
    historyGameDrilldown.classList.add('hidden');
    selectedHistoryAppid = '';
    saveHistoryNavState();
    replaceHistoryUrlState({
      search: historySearch ? historySearch.value : '',
      left: historyLeft ? historyLeft.value : '',
      right: historyRight ? historyRight.value : '',
      quick: false,
    });
    return;
  }

  const selected = candidates.find((item) => item.appid === preferredAppid)
    || candidates.find((item) => item.appid === selectedHistoryAppid)
    || candidates[0];
  const snapshots = normalizeHistorySnapshots(gameHistory[selected.appid]);
  const firstSnapshot = snapshots[0];
  const lastSnapshot = snapshots[snapshots.length - 1];
  const trendText = firstSnapshot && lastSnapshot && Number(firstSnapshot.price_raw) !== Number(lastSnapshot.price_raw)
    ? (Number(lastSnapshot.price_raw) < Number(firstSnapshot.price_raw)
      ? `Bajó de ${formatCurrencyFromRaw(firstSnapshot.price_raw)} a ${formatCurrencyFromRaw(lastSnapshot.price_raw)} entre ejecuciones recientes.`
      : `Subió de ${formatCurrencyFromRaw(firstSnapshot.price_raw)} a ${formatCurrencyFromRaw(lastSnapshot.price_raw)} entre ejecuciones recientes.`)
    : 'No hay suficiente cambio reciente para resumir un movimiento claro de precio.';
  const candidateGroups = splitHistoryDrilldownCandidates(candidates, selected.appid);
  const hiddenCount = candidateGroups.hidden.length;

  selectedHistoryAppid = selected.appid;
  saveHistoryNavState();
  replaceHistoryUrlState({
    search: historySearch ? historySearch.value : '',
    left: historyLeft ? historyLeft.value : '',
    right: historyRight ? historyRight.value : '',
    appid: selectedHistoryAppid,
    quick: false,
  });

  historyGameDrilldown.innerHTML = `
    <div class="history-drilldown-head">
      <div>
        <div class="history-drilldown-title">Historial por juego</div>
        <div class="history-drilldown-subtitle">Mostramos primero los juegos más relevantes para no saturar el panel. Usa “Ver más juegos” si necesitas revisar otros candidatos.</div>
      </div>
      <div class="history-drilldown-pill">${escapeHtml(selected.name)}</div>
    </div>
    <div class="history-drilldown-candidates">
      ${renderHistoryDrilldownButtons(candidateGroups.visible, selected.appid)}
    </div>
    ${hiddenCount ? `
      <details class="history-drilldown-more">
        <summary>Ver ${escapeHtml(hiddenCount)} juegos más</summary>
        <div class="history-drilldown-more-grid">
          ${renderHistoryDrilldownButtons(candidateGroups.hidden, selected.appid)}
        </div>
      </details>
    ` : ''}
    <div class="history-drilldown-summary">${escapeHtml(trendText)}</div>
    <div class="history-drilldown-list">
      ${snapshots.map((snapshot) => `
        <div class="history-drilldown-item">
          <strong>${escapeHtml(formatHistorySnapshotLabel(snapshot))}</strong>
          <span>${escapeHtml(snapshot.price || '?')} · -${escapeHtml(snapshot.discount || 0)}%</span>
        </div>
      `).join('')}
    </div>
  `;
  historyGameDrilldown.classList.remove('hidden');
  historyGameDrilldown.querySelectorAll('[data-history-drilldown]').forEach((btn) => {
    btn.addEventListener('click', () => renderHistoryGameDrilldown(latestHistoryComparisonPayload, btn.dataset.historyDrilldown || ''));
  });
  historyTableBody.querySelectorAll('[data-history-appid]').forEach((btn) => {
    btn.addEventListener('click', () => renderHistoryGameDrilldown(latestHistoryComparisonPayload, btn.dataset.historyAppid || ''));
  });
}

function renderHistorySummary(summary) {
  if (!historySummary) return;
  const safe = summary || {};
  historySummary.innerHTML = [
    ['Ejecución inicial', safe.left_total ?? 0],
    ['Ejecución comparada', safe.right_total ?? 0],
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
      ${includeSameActive ? 'Incluye juegos con precios sin cambio.' : 'Activa "Incluir precios sin cambio" para ver también los iguales.'}
    </div>
  `;
  historyStatusChart.classList.remove('hidden');
}

function clearHistoryComparison() {
  latestHistoryComparisonPayload = null;
  selectedHistoryAppid = '';
  if (historySelectionSummary) {
    historySelectionSummary.innerHTML = '';
    historySelectionSummary.classList.add('hidden');
  }
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
  if (historyAnalyticsSummary) {
    historyAnalyticsSummary.innerHTML = '';
    historyAnalyticsSummary.classList.add('hidden');
  }
  if (historyGameDrilldown) {
    historyGameDrilldown.innerHTML = '';
    historyGameDrilldown.classList.add('hidden');
  }
}

function parseHistoryRunTimestamp(run) {
  const raw = (run && (run.timestamp || run.date)) || '';
  const parsed = Date.parse(raw);
  if (!Number.isNaN(parsed)) return parsed;
  return 0;
}

function getHistoryTrendSignal(trendDelta) {
  const safeDelta = Number(trendDelta) || 0;
  const magnitude = Math.abs(safeDelta);
  if (magnitude === 0) {
    return {
      className: 'history-trend-signal-neutral',
      label: 'Volumen similar al inicio',
    };
  }
  if (safeDelta > 0) {
    return {
      className: 'history-trend-signal-up',
      label: `Más ofertas que al inicio (+${magnitude})`,
    };
  }
  return {
    className: 'history-trend-signal-down',
    label: `Menos ofertas que al inicio (-${magnitude})`,
  };
}

function renderHistoryTrend(runs) {
  if (!historyTrend) return;
  const source = Array.isArray(runs) ? runs : [];
  if (source.length < 2) {
    historyTrend.innerHTML = '<div class="history-trend-title">Tendencia general de ofertas</div><div class="history-trend-subtitle">Resume si el volumen total de ofertas sube, baja o se mantiene entre corridas. No representa el precio de un juego individual.</div><div class="history-trend-empty">Todavía no hay suficientes ejecuciones para leer una tendencia general.</div>';
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
    const title = `Ejecución ${idx + 1}: ${p.value} ofertas`;
    return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.8" fill="var(--accent)"><title>${escapeHtml(title)}</title></circle>`;
  }).join('');

  const firstValue = values[0];
  const lastValue = values[values.length - 1];
  const trendDelta = lastValue - firstValue;
  const trendSignal = getHistoryTrendSignal(trendDelta);

  historyTrend.innerHTML = `
    <div class="history-trend-title">Tendencia general de ofertas (últimas ${normalized.length} ejecuciones)</div>
    <div class="history-trend-subtitle">Te ayuda a ver si últimamente aparecieron más o menos ofertas en total. Si quieres revisar juegos concretos, usa la tabla y los cambios destacados.</div>
    <svg class="history-trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Tendencia general del volumen de ofertas por ejecución">
      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="var(--card-border)" stroke-width="1" />
      <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" stroke="var(--card-border)" stroke-width="1" />
      <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${polyline}" />
      ${dots}
    </svg>
    <div class="history-trend-meta">
      <span>Rango reciente: ${escapeHtml(minValue)} a ${escapeHtml(maxValue)} ofertas</span>
      <span class="${trendSignal.className}">Lectura rápida: ${escapeHtml(trendSignal.label)}</span>
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
    <div class="history-top-deltas-title">Cambios destacados de precio (ejecuciones comparadas)</div>
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
    throw new Error('No se pudo cargar el histórico de ejecuciones.');
  }
  const payload = await response.json();
  const runs = Array.isArray(payload.runs) ? payload.runs : [];
  latestHistoryRuns = runs;
  renderHistoryTrend(latestHistoryRuns);
  applyHistoryRestoredState();
  if (latestFilteredRuns.length < 2) {
    clearHistoryComparison();
  }
}

async function compareHistoryRuns(options = {}) {
  if (!historyLeft || !historyRight) return;
  const left = historyLeft.value;
  const right = historyRight.value;
  if (!left || !right) {
    appendLine('Selecciona dos ejecuciones válidas para comparar.', 'warn');
    return;
  }
  if (left === right) {
    appendLine('Selecciona ejecuciones distintas para la comparación.', 'warn');
    return;
  }

  const leftRun = findHistoryRunById(left);
  const rightRun = findHistoryRunById(right);

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
    throw new Error('No se pudieron comparar las ejecuciones seleccionadas.');
  }
  const payload = await response.json();
  const summary = payload.summary || {};
  if (summary.same == null && payload && payload.rows && Array.isArray(payload.rows)) {
    summary.same = payload.rows.filter(row => row && row.status === 'same').length;
  }
  latestHistoryComparisonPayload = payload;
  renderHistorySelectionSummary(leftRun, rightRun, {quick: !!options.quick});
  renderHistorySummary(summary);
  renderHistoryStatusChart(summary);
  renderHistoryRows(payload.rows || []);
  renderHistoryTopDeltas(payload.rows || []);
  renderHistoryAnalyticsSummary(payload);
  renderHistoryGameDrilldown(payload, selectedHistoryAppid);
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
    title.textContent = 'Modo: Actualización rápida';
    hint.textContent = hasConfig
      ? 'Se detectó caché local. Puedes ejecutar directo o ajustar presets.'
      : 'Hay caché local disponible. Revisa tu perfil y ejecuta cuando quieras.';
  } else {
    title.textContent = 'Modo: Primer setup';
    hint.textContent = 'No se detectó caché local. Usa el wizard y ejecuta tu primer análisis.';
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

function applyPresetMaxWorkers(name) {
  const input = $('max_workers');
  const value = PRESET_MAX_WORKERS[name];
  if (!input || !value) return null;
  input.value = String(value);
  return value;
}

function switchTab(name) {
  const dealsTab = $('tab-deals');
  const pd2Tab = $('tab-pd2');
  const dealsPanel = $('panel-deals');
  const dealsSecondaryPanel = $('panel-deals-secondary');
  const pd2Panel = $('panel-pd2');
  const isPd2 = name === 'pd2';

  dealsPanel.style.display = isPd2 ? 'none' : 'block';
  if (dealsSecondaryPanel) dealsSecondaryPanel.style.display = isPd2 ? 'none' : 'block';
  pd2Panel.style.display = isPd2 ? 'block' : 'none';

  if (btnRun) btnRun.style.display = isPd2 ? 'none' : '';
  if (btnRunPd2) btnRunPd2.style.display = isPd2 ? '' : 'none';

  dealsTab.classList.toggle('active', !isPd2);
  pd2Tab.classList.toggle('active', isPd2);
  dealsTab.setAttribute('aria-selected', isPd2 ? 'false' : 'true');
  pd2Tab.setAttribute('aria-selected', isPd2 ? 'true' : 'false');
}

function applyPreset(name) {
  const maxWorkers = applyPresetMaxWorkers(name);
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
  appendLine(
    'Preset aplicado: ' + name + (maxWorkers ? ` · workers ${maxWorkers}.` : '.'),
    'step'
  );
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

function updateHltbAutodetectSuggestion(suggestion) {
  const el = $('hltb-autodetect-suggestion');
  if (!el) return;
  const hltbInput = $('hltb');
  if (!suggestion || !suggestion.found || (hltbInput && hltbInput.value.trim())) {
    el.textContent = '';
    el.classList.add('hidden');
    return;
  }
  el.textContent = suggestion.message || 'Se detectó un posible export HLTB CSV local en [ruta]. No se usará automáticamente; confirma pegando la ruta completa en el campo HLTB si quieres usarlo.';
  el.classList.remove('hidden');
}

async function runPreflightUI(filtersOverride = null) {
  const filters = filtersOverride || getFilters();
  const pre = await localMutableFetch('/api/preflight', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({config: getConfig(), filters}),
  });
  const preData = await pre.json();
  updateHltbAutodetectSuggestion(preData.hltb_autodetect || null);
  appendLine('Preflight ejecutado.', preData.ok ? 'ok' : 'warn');
  (preData.warnings || []).forEach(w => appendLine('WARN: ' + w, 'warn'));
  (preData.issues || []).forEach(i => appendLine('ISSUE: ' + i, 'err'));
  return preData;
}

function buildWarmCacheContinueFilters() {
  const filters = Object.assign({}, getFilters());
  filters.warm_cache = true;
  filters.warm_cache_full = false;
  filters.no_cache = false;
  return filters;
}

function buildWarmCacheFullFilters() {
  const filters = Object.assign({}, getFilters());
  filters.warm_cache = false;
  filters.warm_cache_full = true;
  filters.no_cache = false;
  return filters;
}

function buildUpdatedCacheReportFilters() {
  const filters = Object.assign({}, getFilters());
  filters.warm_cache = false;
  filters.warm_cache_full = false;
  filters.no_cache = false;
  return filters;
}

function formatRunHeartbeatSeconds(ms) {
  return Math.max(0, Math.floor(Number(ms || 0) / 1000)) + 's';
}

function stopRunStatusHeartbeat() {
  if (runStatusHeartbeatTimer) window.clearInterval(runStatusHeartbeatTimer);
  runStatusHeartbeatTimer = null;
  runStatusHeartbeatOptions = null;
  if (progressContainer) progressContainer.classList.remove('progress-container-indeterminate');
}

function markRunStatusHeartbeatActivity() {
  if (runStatusHeartbeatOptions) runStatusHeartbeatLastActivityAt = Date.now();
}

function updateRunStatusHeartbeat() {
  if (!runStatusHeartbeatOptions) return;
  const options = runStatusHeartbeatOptions;
  const now = Date.now();
  const elapsed = formatRunHeartbeatSeconds(now - runStatusHeartbeatStartedAt);
  const quietFor = formatRunHeartbeatSeconds(now - runStatusHeartbeatLastActivityAt);
  const quietAfterMs = Number(options.quietAfterMs || 8000);
  const isQuiet = now - runStatusHeartbeatLastActivityAt >= quietAfterMs;
  const label = isQuiet
    ? `${options.quietLabel || options.label} · log sin novedades hace ${quietFor}`
    : `${options.label} · activo ${elapsed}`;
  if (progressText) progressText.textContent = label;
  if (options.bannerTitle) {
    const detail = isQuiet
      ? `${options.quietDetail || 'Sigue trabajando aunque el log no avance.'} Tiempo activo: ${elapsed}.`
      : `${options.detail || 'Esperando progreso del proceso.'} Tiempo activo: ${elapsed}.`;
    setWarmCacheBackgroundBanner('progress', options.bannerTitle, options.bannerMessage || label, detail);
  }
}

function startRunStatusHeartbeat(options = {}) {
  stopRunStatusHeartbeat();
  runStatusHeartbeatStartedAt = Date.now();
  runStatusHeartbeatLastActivityAt = runStatusHeartbeatStartedAt;
  runStatusHeartbeatOptions = Object.assign({label: 'Ejecución en curso'}, options);
  if (progressContainer && options.indeterminateProgress !== false) {
    progressContainer.classList.add('progress-container-indeterminate');
  }
  updateRunStatusHeartbeat();
  runStatusHeartbeatTimer = window.setInterval(updateRunStatusHeartbeat, 2500);
}

function warmCacheBackgroundBannerEl() {
  let el = $('warm-cache-background-banner');
  if (el) return el;
  const card = $('output-card');
  if (!card) return null;
  el = document.createElement('div');
  el.id = 'warm-cache-background-banner';
  el.className = 'warm-cache-background-banner hidden';
  el.setAttribute('data-warm-cache-background-banner', '');
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  const anchor = $('latest-report-card') || fileLinks;
  card.insertBefore(el, anchor || null);
  return el;
}

function bindWarmCacheBackgroundBannerActions(el) {
  if (!el) return;
  const btn = el.querySelector('[data-warm-cache-refresh-summary]');
  if (btn) btn.addEventListener('click', () => refreshLatestReportSummaryFromBanner(btn));
  const reportBtn = el.querySelector('[data-warm-cache-generate-report]');
  if (reportBtn) reportBtn.addEventListener('click', () => generateReportFromUpdatedCache(reportBtn));
}

function setWarmCacheBackgroundBanner(state, title, message, detail = '', options = {}) {
  const el = warmCacheBackgroundBannerEl();
  if (!el) return;
  const reportAction = options.showReportAction
    ? '<button type="button" class="file-link file-link-button warm-cache-background-refresh" data-warm-cache-generate-report>Generar reporte con caché actualizada</button>'
    : '';
  const refreshAction = options.showRefresh
    ? '<button type="button" class="file-link file-link-button warm-cache-background-refresh" data-warm-cache-refresh-summary>Refrescar resumen</button>'
    : '';
  el.className = `warm-cache-background-banner warm-cache-background-banner-${state}`;
  el.innerHTML = `
    <div class="warm-cache-background-copy">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
      ${detail ? `<small>${escapeHtml(detail)}</small>` : ''}
    </div>
    ${reportAction}
    ${refreshAction}
  `;
  bindWarmCacheBackgroundBannerActions(el);
}

function updateWarmCacheBackgroundBannerFromEvent(ev) {
  if (!ev) return;
  if (ev.type === 'done') {
    const ok = Number(ev.exit_code || 0) === 0;
    setWarmCacheBackgroundBanner(
      ok ? 'ok' : 'warn',
      ok ? 'Warm-cache finalizado' : 'Warm-cache no completado',
      ok
        ? 'La continuación terminó; genera un reporte normal para ver HTML/JSON con la caché actualizada.'
        : 'Revisa el log antes de reintentar la continuación warm-cache.',
      ok
        ? 'No se asume cobertura completa si todavía quedan pendientes/deferred.'
        : 'Se respetó el lock actual y no se usó --no-cache.',
      {showRefresh: ok, showReportAction: ok}
    );
    return;
  }
  if (ev.type !== 'progress') return;
  const current = Number(ev.current || 0);
  const total = Number(ev.total || 0);
  const label = String(ev.label || 'Warm-cache').trim();
  const progress = total > 0 ? `[${current}/${total}] ${label}` : label;
  setWarmCacheBackgroundBanner(
    'progress',
    'Warm-cache en segundo plano',
    progress,
    'Puedes seguir revisando el último reporte mientras se revalida con --warm-cache, sin --no-cache.'
  );
}

function updateFullWarmCacheBackgroundBannerFromEvent(ev) {
  if (!ev) return;
  if (ev.type === 'done') {
    const ok = Number(ev.exit_code || 0) === 0;
    setWarmCacheBackgroundBanner(
      ok ? 'ok' : 'warn',
      ok ? 'Full warm-cache finalizado' : 'Full warm-cache no completado',
      ok
        ? 'Las pasadas resumibles terminaron; genera un reporte normal para ver HTML/JSON con la caché actualizada.'
        : 'Revisa el log antes de reintentar Completar warm-cache.',
      ok
        ? 'No se generó reporte automáticamente y no se usó --no-cache.'
        : 'Se respetó el lock actual y la caché local se conserva.',
      {showRefresh: ok, showReportAction: ok}
    );
    return;
  }
  if (ev.type !== 'progress') return;
  const current = Number(ev.current || 0);
  const total = Number(ev.total || 0);
  const label = String(ev.label || 'Full warm-cache').trim();
  const progress = total > 0 ? `[${current}/${total}] ${label}` : label;
  setWarmCacheBackgroundBanner(
    'progress',
    'Full warm-cache en segundo plano',
    progress,
    'Repite pasadas con la misma caché usando --warm-cache-full, sin --no-cache y sin regenerar reportes automáticamente.'
  );
}

async function refreshLatestReportSummaryFromBanner(btn) {
  if (btn) btn.disabled = true;
  try {
    const refreshed = await syncLatestReportSummary();
    if (!refreshed) throw new Error('No hay JSON local disponible para refrescar.');
    setWarmCacheBackgroundBanner(
      'ok',
      'Resumen refrescado',
      'El último reporte visible se volvió a leer desde el JSON local.',
      'Si todavía aparece Caché parcial, puedes continuar otra tanda con la misma caché.',
      {showRefresh: true}
    );
  } catch (e) {
    setWarmCacheBackgroundBanner(
      'warn',
      'No se pudo refrescar el resumen',
      'Revisa el JSON técnico o vuelve a intentar desde el último reporte.',
      e && e.message ? e.message : '',
      {showRefresh: true}
    );
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function generateReportFromUpdatedCache(btn) {
  const originalLabel = btn ? btn.textContent : 'Generar reporte con caché actualizada';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Generando reporte...';
  }
  setWarmCacheBackgroundBanner(
    'progress',
    'Generando reporte con caché actualizada',
    'Ejecutando Steam Deals normal para regenerar HTML/JSON con la caché ya precalentada.',
    'No continúa warm-cache: solo usa la misma caché, sin --warm-cache y sin --no-cache.'
  );
  const completed = await runSteamDealsUI({
    filters: buildUpdatedCacheReportFilters(),
    startLabel: 'Generando reporte con caché actualizada...',
    introLine: 'Generando reporte normal con la caché actualizada (sin --warm-cache y sin --no-cache).',
    conflictMessage: 'Ya hay una ejecucion en curso. Espera a que termine antes de generar el reporte actualizado.',
    triggerButton: btn,
    heartbeat: {
      label: 'Generando reporte con caché actualizada',
      quietLabel: 'Sigue trabajando',
      bannerTitle: 'Generando reporte con caché actualizada',
      bannerMessage: 'HTML/JSON se están regenerando con la caché disponible; puede tardar aunque el log no avance.',
      detail: 'No está cacheando más juegos; está armando el reporte con la cobertura actual.',
      quietDetail: 'No está paralizado necesariamente: el generador puede pasar varios segundos sin escribir nuevas líneas.',
      quietAfterMs: 7000,
    },
    preserveOutputFiles: false,
    preserveLatestReportOnDone: false,
  });
  if (btn && btn.isConnected) {
    btn.textContent = originalLabel;
    btn.disabled = false;
  }
  setWarmCacheBackgroundBanner(
    completed ? 'ok' : 'warn',
    completed ? 'Reporte actualizado generado' : 'No se pudo generar reporte actualizado',
    completed
      ? 'El HTML/JSON se regeneró con la caché actualizada; revisa los enlaces y el último reporte.'
      : 'Revisa el log; no se usó --no-cache y la caché precalentada se conserva.',
    completed
      ? 'Si todavía queda Caché parcial, puedes continuar warm-cache y volver a generar el reporte.'
      : 'Puedes reintentar cuando no haya otra ejecución activa.',
    {showReportAction: !completed}
  );
}

function setWarmCacheContinueStatus(btn, message, state = 'progress') {
  if (!btn) return;
  const coverageCard = btn.closest('[data-latest-cache-coverage]');
  const statusEl = coverageCard ? coverageCard.querySelector('[data-latest-cache-continue-status]') : null;
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = `latest-cache-continue-status latest-cache-continue-status-${state}`;
}

async function streamSteamDealsRunResponse(resp, options = {}) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  const onEvent = typeof options.onEvent === 'function' ? options.onEvent : null;
  let buffer = '';
  let completedOk = false;
  let sawDone = false;

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
            handleEvent(ev, options);
            if (onEvent) onEvent(ev);
            if (ev.type === 'done') {
              sawDone = true;
              completedOk = Number(ev.exit_code || 0) === 0;
            }
          } catch(e) {}
        }
      }
    }
  }
  return sawDone && completedOk;
}

async function runSteamDealsUI(options = {}) {
  const filters = options.filters || getFilters();
  const startLabel = options.startLabel || 'Iniciando...';
  const schedulerEnabled = isSchedulerEnabledFromFilters(filters);
  const conflictMessage = schedulerEnabled
    ? schedulerRunConflictMessage(filters)
    : (options.conflictMessage || schedulerRunConflictMessage(filters));
  const triggerButton = options.triggerButton || null;

  if (options.validateForm !== false && !validateDealsFormBeforeRun()) {
    return false;
  }

  shownErrorHints = new Set();
  resetExecutionLog();
  if (options.introLine) appendLine(options.introLine, 'step');
  const schedulerIntroMessage = schedulerRunIntroMessage(filters);
  if (schedulerIntroMessage) appendLine(schedulerIntroMessage, 'step');
  if (options.heartbeat) startRunStatusHeartbeat(options.heartbeat);
  progressBar.style.width = '0%';
  progressText.textContent = startLabel;
  if (options.preserveOutputFiles !== true) {
    fileLinks.innerHTML = '';
    fileLinks.classList.add('hidden');
  }
  btnRun.disabled = true;
  if (triggerButton && triggerButton !== btnRun) triggerButton.disabled = true;
  resetStopUiState();
  btnStop.disabled = false;

  try {
    try {
      const preData = await runPreflightUI(filters);
      if (!preData.ok) {
        appendLine('Validacion previa fallida. Corrige lo siguiente:', 'err');
        progressText.textContent = 'Config invalida';
        progressBar.style.width = '0%';
        return false;
      }
    } catch(e) {
      appendLine('No se pudo ejecutar preflight: ' + e.message, 'warn');
    }

    abortCtrl = new AbortController();
    const resp = await localMutableFetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: getConfig(), filters}),
      signal: abortCtrl.signal,
    });

    if (!resp.ok && resp.status !== 409) {
      let msg = 'HTTP ' + resp.status;
      try {
        const body = await resp.json();
        if (body && body.error) msg = body.error;
      } catch(e) {}
      appendLine('Error del servidor: ' + msg, 'err');
      return false;
    }

    if (resp.status === 409) {
      appendLine(conflictMessage, 'warn');
      return false;
    }

    return await streamSteamDealsRunResponse(resp, {
      onEvent: options.onEvent,
      preserveLatestReportOnDone: options.preserveLatestReportOnDone === true,
    });
  } catch(e) {
    if (e.name !== 'AbortError') {
      appendLine('Error de conexion: ' + e.message, 'err');
    }
    return false;
  } finally {
    stopRunStatusHeartbeat();
    btnRun.disabled = false;
    if (triggerButton && triggerButton !== btnRun) triggerButton.disabled = false;
    resetStopUiState();
    abortCtrl = null;
  }
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
  const resp = await localMutableFetch('/api/desktop-doctor', {method: 'POST'});
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

  const resp = await localMutableFetch('/api/desktop-doctor/fix', {
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

if (btnSteamOpenIdStart) btnSteamOpenIdStart.addEventListener('click', startSteamOpenIdFlow);
if (btnSteamOpenIdDisconnect) btnSteamOpenIdDisconnect.addEventListener('click', disconnectSteamOpenIdProfile);
refreshSteamOpenIdStatus();

const hltbField = $('hltb');
if (hltbField) hltbField.addEventListener('input', () => {
  if (hltbField.value.trim()) updateHltbAutodetectSuggestion(null);
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
    const r = await localMutableFetch('/api/cache/clear', {method: 'POST'});
    const d = await r.json();
    appendLine('Cache limpiada: ' + (d.removed || 0) + ' archivo(s).', 'ok');
  } catch(e) {
    appendLine('No se pudo limpiar cache: ' + e.message, 'err');
  }
});

async function openOutputFolderUI(triggerBtn = null) {
  if (triggerBtn) triggerBtn.disabled = true;
  try {
    const resp = await localMutableFetch('/api/open-output-folder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: getConfig()}),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.message || data.error || ('HTTP ' + resp.status));
    }
    appendLine('Carpeta de salida abierta: ' + (data.label || data.path || 'output/'), 'ok');
  } catch(e) {
    appendLine('No se pudo abrir la carpeta de salida: ' + e.message, 'err');
  } finally {
    if (triggerBtn) triggerBtn.disabled = false;
  }
}

if (btnOpenOutputFolder) btnOpenOutputFolder.addEventListener('click', () => {
  openOutputFolderUI(btnOpenOutputFolder);
});

btnOpenLast.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/files');
    const files = await r.json();
    if (!files || !files.length) {
      appendLine('No hay reportes generados todavia.', 'warn');
      return;
    }
    const name = findLatestPrimaryHtmlReport(files);
    if (!name) {
      appendLine('No hay reporte HTML interactivo para abrir. Usa los enlaces generados para descargar Markdown, JSON o CSV.', 'warn');
      return;
    }
    window.open('/files/' + encodeURIComponent(name), '_blank');
    appendLine('Abriendo reporte HTML interactivo: ' + name, 'ok');
  } catch(e) {
    appendLine('No se pudo abrir último reporte HTML: ' + e.message, 'err');
  }
});

function appendLine(text, cls) {
  const safeText = normalizeRedactedPathMarkers(text);
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

function normalizeRedactedPathMarkers(text) {
  return String(text ?? '').replace(/(?:\[ruta\]){2,}/gi, '[ruta]');
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

async function exportExecutionLogText(text, {button = btnDownloadLog, successLabel = 'Guardado'} = {}) {
  const resp = await localMutableFetch('/api/log/export', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      text,
      filename: buildExecutionLogFilename(),
    }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error((data && data.message) || ('HTTP ' + resp.status));
  }
  appendLine('Log guardado en: ' + data.path, 'ok');
  flashButtonLabel(button, successLabel);
}

function getDesktopClipboardApi() {
  const bridge = window.pywebview && window.pywebview.api;
  if (bridge && typeof bridge.copy_text_to_clipboard === 'function') {
    return bridge;
  }
  return null;
}

function buildClipboardFailureMessage(error) {
  const message = error && error.message ? error.message : String(error || '');
  if (message.indexOf('Descargar log') !== -1) return message;
  return (message || 'Portapapeles no disponible') + ' Usa Descargar log (.txt).';
}

function markExecutionLogCopied() {
  appendLine('Log copiado al portapapeles.', 'ok');
  flashButtonLabel(btnCopyLog, 'Copiado');
}

async function copyExecutionLogText(text) {
  if (!text) throw new Error('No hay contenido de log para copiar.');

  const desktopApi = getDesktopClipboardApi();
  if (desktopApi) {
    await desktopApi.copy_text_to_clipboard(text);
    markExecutionLogCopied();
    return;
  }

  if (IS_DESKTOP_NATIVE || pywebviewBridgeReady) {
    throw new Error('Clipboard nativo no disponible. Usa Descargar log (.txt).');
  }

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    await navigator.clipboard.writeText(text);
    markExecutionLogCopied();
    return;
  }

  throw new Error('Portapapeles no disponible en este navegador. Usa Descargar log (.txt).');
}

async function copyExecutionLog() {
  const text = getExecutionLogText();
  if (!text) {
    flashButtonLabel(btnCopyLog, 'Sin log');
    return;
  }

  try {
    await copyExecutionLogText(text);
  } catch (e) {
    appendLine('No se pudo copiar log: ' + buildClipboardFailureMessage(e), 'err');
    flashButtonLabel(btnCopyLog, 'Error');
  }
}

async function downloadExecutionLog() {
  const text = getExecutionLogText();
  if (!text) {
    flashButtonLabel(btnDownloadLog, 'Sin log');
    return;
  }

  try {
    await exportExecutionLogText(text, {button: btnDownloadLog, successLabel: 'Guardado'});
  } catch (e) {
    appendLine('No se pudo guardar log: ' + e.message, 'err');
    flashButtonLabel(btnDownloadLog, 'Error');
  }
}

if (btnCopyLog) btnCopyLog.addEventListener('click', copyExecutionLog);
if (btnDownloadLog) btnDownloadLog.addEventListener('click', downloadExecutionLog);

btnRun.addEventListener('click', async () => {
  await runSteamDealsUI({filters: getFilters()});
});

btnStop.addEventListener('click', async () => {
  if (stopRequestInFlight) return;
  beginStopUiState();
  try {
    const resp = await localMutableFetch('/api/stop', {method: 'POST'});
    let payload = {};
    try {
      payload = await resp.json();
    } catch (e) {}
    if (!resp.ok) {
      appendLine((payload && payload.message) || ('No se pudo detener la ejecucion: HTTP ' + resp.status), 'err');
    } else if (payload && payload.status === 'stopped') {
      appendLine(payload.message || '--- Cancelado por el usuario ---', 'warn');
      if (abortCtrl) abortCtrl.abort();
    } else if (payload && payload.status === 'not_running') {
      appendLine(payload.message || 'No habia una ejecucion activa para detener.', 'dim');
      if (abortCtrl) abortCtrl.abort();
    } else if (payload && payload.status === 'stop_timeout') {
      appendLine(payload.message || 'La ejecucion no se pudo detener a tiempo.', 'err');
    } else {
      appendLine((payload && payload.message) || 'Estado de detener desconocido.', 'warn');
    }
  } catch(e) {
    appendLine('No se pudo detener la ejecucion: ' + e.message, 'err');
  } finally {
    completeStopUiState();
  }
});

if (btnRunPd2) btnRunPd2.addEventListener('click', async () => {
  if (!validatePd2FormBeforeRun()) {
    return;
  }
  shownErrorHints = new Set();
  resetExecutionLog();
  progressBar.style.width = '0%';
  progressBar.style.background = 'linear-gradient(90deg, #d4a84b, #b8922e)';
  progressText.textContent = 'PAYDAY 2 Tracker...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  btnRunPd2.disabled = true;
  resetStopUiState();
  btnStop.disabled = false;
  abortCtrl = new AbortController();
  try {
    const resp = await localMutableFetch('/api/run-pd2', {
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
  resetStopUiState();
  abortCtrl = null;
});

function handleEvent(ev, options = {}) {
  markRunStatusHeartbeatActivity();
  if (ev.type === 'line') {
    appendLine(ev.text, ev.cls || 'normal');
  }
  else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    progressBar.style.width = pct + '%';
    progressText.textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label;
  }
  else if (ev.type === 'done') {
    resetStopUiState();
    progressBar.style.width = '100%';
    if (ev.exit_code === 0) {
      progressText.textContent = 'Completado';
      progressBar.style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
    } else {
      progressText.textContent = 'Error (codigo ' + ev.exit_code + ')';
      progressBar.style.background = 'linear-gradient(90deg, var(--red), #a02020)';
    }
    const hasFiles = ev.files && ev.files.length;
    const preserveLatestReport = options.preserveLatestReportOnDone === true && !hasFiles;
    if (hasFiles) {
      showFiles(ev.files);
    }
    if (!preserveLatestReport) {
      syncLatestReportEmptyState(ev.files);
      syncLatestReportCard(ev.files);
    }
  }
}

function getGeneratedFileName(file) {
  if (typeof file === 'string') return file.split('/').pop() || '';
  return (file && file.name) || '';
}

function getGeneratedFileExtension(name) {
  const dot = (name || '').lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

function findLatestPrimaryHtmlReport(files) {
  return (Array.isArray(files) ? files : [])
    .map(getGeneratedFileName)
    .find(name => getGeneratedFileExtension(name) === '.html' && !isShareHtmlFile(name));
}

const GENERATED_FILE_ACTION_GROUPS = Object.freeze([
  {kind: 'report-html', label: 'HTML interactivo'},
  {kind: 'share-html', label: 'Share HTML'},
  {kind: 'markdown', label: 'Markdown'},
  {kind: 'json-offers', label: 'Ofertas JSON'},
  {kind: 'json-wishlist', label: 'Wishlist JSON'},
  {kind: 'json', label: 'JSON técnico'},
  {kind: 'csv', label: 'CSV'},
  {kind: 'other', label: 'Otros archivos'},
]);

const GENERATED_FILE_ACTION_ORDER = Object.freeze(
  GENERATED_FILE_ACTION_GROUPS.reduce((acc, group, index) => {
    acc[group.kind] = index;
    return acc;
  }, {})
);

function generatedFileHref(filePath) {
  return '/files/' + encodeURIComponent(getGeneratedFileName(filePath));
}

function buildGeneratedFileAction(filePath) {
  const name = getGeneratedFileName(filePath);
  const ext = getGeneratedFileExtension(name);
  const href = generatedFileHref(name);
  if (ext === '.html' && isShareHtmlFile(name)) {
    return {
      name,
      href,
      kind: 'share-html',
      label: 'Abrir Share HTML',
      icon: '&#128279;',
      openInTab: true,
      title: 'Abre la versión ligera lista para compartir',
    };
  }
  if (ext === '.html') {
    return {
      name,
      href,
      kind: 'report-html',
      label: 'Abrir reporte interactivo',
      icon: '&#128202;',
      openInTab: true,
      title: 'Abre el reporte completo con filtros y acciones',
    };
  }
  if (ext === '.md') {
    return {
      name,
      href,
      kind: 'markdown',
      label: 'Descargar Markdown',
      icon: '&#128196;',
      openInTab: false,
      title: 'Descarga el reporte en texto para abrirlo donde quieras',
    };
  }
  if (isOffersJsonExportFile(name)) {
    return {
      name,
      href,
      kind: 'json-offers',
      label: 'Descargar ofertas JSON',
      icon: '&#123;&#125;',
      openInTab: false,
      isJsonExport: true,
      title: 'Descarga solo las ofertas detectadas con la cobertura disponible',
    };
  }
  if (isWishlistJsonExportFile(name)) {
    return {
      name,
      href,
      kind: 'json-wishlist',
      label: 'Descargar wishlist JSON',
      icon: '&#128221;',
      openInTab: false,
      isJsonExport: true,
      title: 'Descarga la wishlist conocida; los precios pueden estar pendientes o parciales',
    };
  }
  if (ext === '.json') {
    return {
      name,
      href,
      kind: 'json',
      label: 'Descargar JSON',
      icon: '&#123;&#125;',
      openInTab: false,
      title: 'Descarga el JSON del run para automatización o revisión',
    };
  }
  if (ext === '.csv') {
    return {
      name,
      href,
      kind: 'csv',
      label: 'Descargar CSV',
      icon: '&#128203;',
      openInTab: false,
      title: 'Descarga el CSV para Excel o Google Sheets',
    };
  }
  return {
    name,
    href,
    kind: 'other',
    label: name,
    icon: '&#128196;',
    openInTab: true,
    title: 'Abrir archivo generado',
  };
}

function sortGeneratedFileActions(actions) {
  return [...actions].sort((a, b) => {
    const groupDelta = (GENERATED_FILE_ACTION_ORDER[a.kind] ?? 99) - (GENERATED_FILE_ACTION_ORDER[b.kind] ?? 99);
    if (groupDelta !== 0) return groupDelta;
    return a.name.localeCompare(b.name);
  });
}

function createGeneratedFileActionButton(action) {
  const a = document.createElement('a');
  a.className = 'file-link';
  a.href = action.href;
  a.title = action.title;
  if (action.openInTab) {
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
  } else {
    a.setAttribute('download', action.name);
  }
  if (action.isJsonExport) {
    a.classList.add('generated-json-export-action');
  }
  a.innerHTML = action.icon + ' ' + action.label;
  return a;
}

function appendGeneratedFileGroup(container, group, actions) {
  const groupedActions = actions.filter(action => action.kind === group.kind);
  if (!groupedActions.length) return;

  const section = document.createElement('div');
  section.className = 'file-link-group';

  const title = document.createElement('div');
  title.className = 'file-link-group-title';
  title.textContent = group.label;
  section.appendChild(title);

  groupedActions.forEach(action => section.appendChild(createGeneratedFileActionButton(action)));
  container.appendChild(section);
}

function createOpenOutputFolderActionButton() {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'file-link file-link-button';
  btn.title = 'Abre la carpeta local donde se guardaron los reportes';
  btn.innerHTML = '&#128193; Ver carpeta';
  btn.addEventListener('click', () => openOutputFolderUI(btn));
  return btn;
}

function showFiles(files) {
  fileLinks.innerHTML = '';
  const actions = sortGeneratedFileActions((Array.isArray(files) ? files : []).map(buildGeneratedFileAction));
  if (actions.length) {
    const hint = document.createElement('div');
    hint.className = 'file-links-hint';
    hint.textContent = 'Los artefactos se muestran por tipo: HTML interactivo y Share HTML se abren; Markdown, ofertas/wishlist JSON, JSON técnico y CSV se descargan para tu editor, Excel/Sheets o herramientas.';
    fileLinks.appendChild(hint);
  }
  GENERATED_FILE_ACTION_GROUPS.forEach(group => appendGeneratedFileGroup(fileLinks, group, actions));

  if (actions.length) {
    const folderGroup = document.createElement('div');
    folderGroup.className = 'file-link-group file-link-group-secondary';
    const title = document.createElement('div');
    title.className = 'file-link-group-title';
    title.textContent = 'Carpeta local';
    folderGroup.appendChild(title);
    folderGroup.appendChild(createOpenOutputFolderActionButton());
    fileLinks.appendChild(folderGroup);
    fileLinks.classList.remove('hidden');
  } else {
    fileLinks.classList.add('hidden');
  }
}

async function fetchGeneratedFilesList() {
  try {
    const resp = await fetch('/api/files');
    if (!resp.ok) return null;
    const files = await resp.json();
    return Array.isArray(files) ? files : null;
  } catch (e) {
    return null;
  }
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

function latestCoverageCount(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return 0;
  return Math.floor(parsed);
}

function formatLatestCoverageCount(value) {
  return latestCoverageCount(value).toLocaleString();
}

function parseShareMoney(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  const cleaned = String(value)
    .trim()
    .replace(/[^\d.,-]/g, '')
    .replace(/,/g, '');
  if (!cleaned) return null;
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatShareMoney(value) {
  const amount = parseShareMoney(value);
  if (amount == null) return '';
  const normalized = Math.abs(amount - Math.round(amount)) < 0.001
    ? amount.toFixed(0)
    : amount.toFixed(2);
  return `$${normalized}`;
}

function buildShareGamePayload(game, report = null) {
  const source = game && typeof game === 'object' ? game : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  if (!appid) return null;

  const reportDeals = Array.isArray(report && report.deals) ? report.deals : [];
  const fallbackDeal = reportDeals.find((deal) => String((deal && (deal.appid || deal.steam_appid)) || '') === appid) || {};
  const historicalLows = report && typeof report.historical_lows === 'object' ? (report.historical_lows || {}) : {};
  const historicalLow = historicalLows[appid] || null;

  const name = source.name || source.steam_name || fallbackDeal.name || fallbackDeal.steam_name || 'Juego desconocido';
  const currentPrice = parseShareMoney(source.price ?? source.price_final ?? fallbackDeal.price ?? fallbackDeal.price_final);
  const originalPrice = parseShareMoney(source.price_original ?? source.original_price ?? fallbackDeal.price_original ?? fallbackDeal.original_price) ?? currentPrice;
  const discount = Number(source.discount ?? fallbackDeal.discount ?? 0) || 0;
  const minHist = parseShareMoney(source.min_hist ?? source.historical_low ?? source.min_historical ?? fallbackDeal.min_hist ?? fallbackDeal.historical_low ?? fallbackDeal.min_historical ?? (historicalLow && historicalLow.price));
  const steamUrl = `https://store.steampowered.com/app/${appid}/`;

  const priceLabel = formatShareMoney(currentPrice);
  const originalLabel = formatShareMoney(originalPrice != null ? originalPrice : currentPrice);
  const minHistLabel = formatShareMoney(minHist);

  return {
    appid,
    name,
    discount,
    steamUrl,
    displayPrice: priceLabel ? `${priceLabel} MXN` : 'Precio no disponible',
    displayOriginalPrice: originalPrice != null && currentPrice != null && originalPrice > currentPrice ? `${originalLabel} MXN` : '',
    displayMinHist: minHistLabel ? `${minHistLabel} MXN` : '',
    payload: {
      v: Number(source.v || fallbackDeal.v || 1) || 1,
      name,
      steam_name: source.steam_name || fallbackDeal.steam_name || name,
      appid,
      steam_appid: appid,
      price: priceLabel || '',
      price_final: priceLabel || '',
      price_original: originalLabel || priceLabel || '',
      original_price: originalLabel || priceLabel || '',
      discount,
      min_hist: minHistLabel || '',
      min_historical: minHistLabel || '',
      historical_low: minHistLabel || '',
      steam_url: steamUrl,
      url: steamUrl,
    },
  };
}

function latestOfferAppid(item) {
  const source = item && typeof item === 'object' ? item : {};
  return String(source.appid || source.steam_appid || '').trim();
}

function latestReportDealForAppid(report, appid) {
  const key = String(appid || '').trim();
  if (!key) return {};
  const deals = Array.isArray(report && report.deals) ? report.deals : [];
  return deals.find((deal) => latestOfferAppid(deal) === key) || {};
}

function latestOfferScoreReasons(item, sourceDeal = null) {
  const reasons = [];
  [item, sourceDeal || {}].forEach((source) => {
    if (!source || typeof source !== 'object' || !Array.isArray(source.score_reasons)) return;
    source.score_reasons.forEach((reason) => {
      const text = String(reason || '').trim();
      if (text && !reasons.includes(text)) reasons.push(text);
    });
  });
  return reasons;
}

function latestOfferDiscount(item, sourceDeal = null) {
  for (const source of [item, sourceDeal || {}]) {
    if (!source || typeof source !== 'object') continue;
    const rawDiscount = source.discount;
    if (rawDiscount === null || rawDiscount === undefined || rawDiscount === '') continue;
    const discount = Number.parseInt(rawDiscount, 10);
    if (Number.isFinite(discount)) return discount;
  }
  return 0;
}

function latestOfferCurrentPrice(item, sourceDeal = null) {
  for (const source of [item, sourceDeal || {}]) {
    if (!source || typeof source !== 'object') continue;
    const price = parseShareMoney(source.price_final ?? source.price);
    if (price !== null) return price;
  }
  return null;
}

function latestOfferHistoricalLow(report, item, sourceDeal = null) {
  const appid = latestOfferAppid(item) || latestOfferAppid(sourceDeal);
  const lows = report && typeof report.historical_lows === 'object' ? report.historical_lows : {};
  return appid && lows ? (lows[appid] || null) : null;
}

function latestOfferNearHistoricalLow(item, minHist = null, sourceDeal = null) {
  if (!minHist || typeof minHist !== 'object') return false;
  const lowPrice = parseShareMoney(minHist.price ?? minHist.price_final ?? minHist.value);
  const currentPrice = latestOfferCurrentPrice(item, sourceDeal);
  return lowPrice !== null && currentPrice !== null && lowPrice > 0 && currentPrice > 0 && currentPrice <= lowPrice * 1.05;
}

function latestOfferHasActivePromoSignal(reasons, discount, activePromoContext = null) {
  if ((Array.isArray(reasons) ? reasons : []).some(reason => String(reason || '').toLowerCase().includes('promo'))) return true;
  if (!activePromoContext || typeof activePromoContext !== 'object' || discount < 75) return false;
  const categories = Array.isArray(activePromoContext.categories) ? activePromoContext.categories : [];
  return categories.some(category => ['major_sale', 'fest', 'next_fest', 'publisher_sale', 'themed'].includes(String(category || '').trim()));
}

function latestOfferHighlight(item, report = null) {
  const source = item && typeof item === 'object' ? item : {};
  const fallbackDeal = latestReportDealForAppid(report, latestOfferAppid(source));
  const recommendation = String(source.recommendation || fallbackDeal.recommendation || '').trim();
  const recommendationLower = recommendation.toLowerCase();
  const reasons = latestOfferScoreReasons(source, fallbackDeal);
  const reasonsLower = reasons.join(' · ').toLowerCase();
  const discount = latestOfferDiscount(source, fallbackDeal);
  const meta = report && typeof report === 'object' ? (report.meta || {}) : {};
  const activePromoContext = meta && typeof meta.active_promo_context === 'object' ? meta.active_promo_context : null;
  const nearMin = latestOfferNearHistoricalLow(source, latestOfferHistoricalLow(report, source, fallbackDeal), fallbackDeal);

  if (recommendationLower.includes('esper')) return { label: 'Esperar mejor oferta', reason: 'señal conservadora' };
  if (recommendationLower.includes('solo si')) return { label: 'Solo si ya estaba en tu radar', reason: 'señal conservadora' };
  if (recommendationLower.includes('comprar') || recommendationLower.includes('oferta destacada')) return { label: 'Oferta destacada', reason: 'score/oferta alta' };
  if (recommendationLower.includes('muy buena') || recommendationLower.includes('muy buen deal')) return { label: 'Muy buen deal', reason: 'score/oferta alta' };
  if (nearMin || reasonsLower.includes('mínimo') || reasonsLower.includes('minimo')) {
    return { label: 'Cerca de mínimo histórico', reason: 'precio cerca del mínimo conocido' };
  }
  if (latestOfferHasActivePromoSignal(reasons, discount, activePromoContext)) {
    return { label: 'Promo destacada', reason: 'contexto de promo activa' };
  }
  if (discount >= 85) return { label: 'Muy buen deal', reason: 'descuento fuerte' };
  if (recommendationLower.includes('vale la pena') || recommendationLower.includes('buena para revisar') || discount >= 70) {
    return { label: 'Buena para revisar hoy', reason: 'descuento alto' };
  }
  return null;
}

function renderLatestOfferHighlight(item, report = null) {
  const highlight = latestOfferHighlight(item, report);
  if (!highlight) return '';
  const reasonHtml = highlight.reason
    ? `<span class="latest-offer-highlight-reason">${escapeHtml(highlight.reason)}</span>`
    : '';
  return `
    <div class="latest-offer-highlight" data-latest-offer-highlight>
      <span class="latest-offer-highlight-label">${escapeHtml(highlight.label)}</span>
      ${reasonHtml}
    </div>
  `;
}

let latestBudgetUiState = null;

const LATEST_PROMO_CATEGORY_LABELS = Object.freeze({
  weeklong: 'Weeklong',
  midweek: 'Midweek',
  weekend: 'Weekend',
  launch: 'Lanzamiento',
  fest: 'Fest',
  major_sale: 'Oferta grande',
  publisher_sale: 'Publisher/Franquicia',
  themed: 'Oferta temática',
  unknown: 'Otra promo',
});

const LATEST_PROMO_CATEGORY_PRIORITY = Object.freeze({
  major_sale: 10,
  fest: 20,
  publisher_sale: 30,
  themed: 35,
  weekend: 40,
  midweek: 45,
  launch: 50,
  weeklong: 60,
  unknown: 80,
});

const LATEST_PROMO_PRIMARY_TYPES = Object.freeze([1, 11]);

const LATEST_FREE_WEEKEND_CONFIDENCE_LABELS = Object.freeze({
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
});

const LATEST_EXTERNAL_OFFER_CONFIDENCE_LABELS = Object.freeze({
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
});

const LATEST_EXTERNAL_OFFER_STORE_TYPE_LABELS = Object.freeze({
  official_store: 'Tienda oficial',
  authorized_key_reseller: 'Reseller autorizado',
});

const LATEST_EXTERNAL_OFFER_VISIBLE_STORE_TYPES = Object.freeze(['official_store', 'authorized_key_reseller']);
const LATEST_EXTERNAL_OFFER_VISIBLE_STATES = Object.freeze(['highlight', 'review']);
const LATEST_EXTERNAL_OFFER_BLOCKING_RISKS = Object.freeze([
  'appid_missing',
  'unknown_store',
  'marketplace_keyshop',
  'aggregator_source',
  'low_confidence',
  'checkout_like_url',
  'unsafe_url_scheme',
  'invalid_price',
  'currency_missing',
  'invalid_currency',
]);
const LATEST_EXTERNAL_OFFER_CHECKOUT_RE = /(^|[/?#&=._-])(cart|checkout|add-to-cart|addtocart|payment|purchase)s?([/?#&=._-]|$)/i;

const LATEST_TASTE_PRIORITY_CATEGORY_LABELS = Object.freeze({
  compra_inmediata: 'Prioridad alta para revisar',
  espera_oferta: 'Prioridad baja por gusto',
  riesgo_abandono: 'Riesgo de abandono',
  reemplaza_varios: 'Solapa con varios juegos',
  no_comprar_aun: 'No priorizar aún',
});

const LATEST_DECISION_SUPPORT_LABELS = Object.freeze({
  good_fit: 'Buen encaje',
  maybe: 'Podría encajar',
  weak_fit: 'Encaje débil / revisar',
});

const LATEST_DECISION_SUPPORT_FIT_REASON_LABELS = Object.freeze({
  profile_family_match: 'Familia alineada con tus gustos',
  profile_loop_match: 'Loop de juego que sueles preferir',
  profile_descriptor_match: 'Descriptor compatible con tus preferencias',
});

const LATEST_DECISION_SUPPORT_CAUTION_LABELS = Object.freeze({
  partial_player_profile: 'perfil parcial',
  low_confidence: 'confianza baja',
  limited_preference_match: 'match limitado',
});

const LATEST_DECISION_SUPPORT_CONFIDENCE_LABELS = Object.freeze({
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
  unknown: 'Sin dato',
});

const LATEST_DECISION_SUPPORT_FIT_LEVEL_LABELS = Object.freeze({
  strong: 'Fit fuerte',
  medium: 'Fit medio',
  weak: 'Fit débil',
});

const LATEST_RECOMMENDATION_DIAGNOSTIC_MODE_LABELS = Object.freeze({
  behavioral: 'Behavioral',
  mixed: 'Mixto',
  score_fallback: 'Score fallback',
});

const LATEST_RECOMMENDATION_DIAGNOSTIC_CONFIDENCE_LABELS = Object.freeze({
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
});

function latestPromoCategoryLabel(category) {
  const key = String(category || '').trim();
  return LATEST_PROMO_CATEGORY_LABELS[key] || key || 'Otra promo';
}

function latestPromoPrimaryTitle(context) {
  const primary = latestPromoPrimaryPromo(context);
  const primaryTitle = primary ? String(primary.title || '').trim() : '';
  return primaryTitle || String((context && context.sale_name) || '').trim();
}

function latestPromoPriority(promo, index) {
  const category = String((promo && promo.category) || '').trim() || 'unknown';
  const categoryPriority = Object.prototype.hasOwnProperty.call(LATEST_PROMO_CATEGORY_PRIORITY, category)
    ? LATEST_PROMO_CATEGORY_PRIORITY[category]
    : LATEST_PROMO_CATEGORY_PRIORITY.unknown;
  const promoType = Number(promo && promo.type);
  const isPrimaryType = Boolean(
    (promo && promo.is_primary_type) || LATEST_PROMO_PRIMARY_TYPES.includes(promoType)
  );
  const primaryTypePriority = isPrimaryType ? 0 : 1;
  return [categoryPriority, primaryTypePriority, index];
}

function latestPromoRankedPromos(context) {
  const promos = Array.isArray(context && context.promos) ? context.promos : [];
  return promos
    .map((promo, index) => ({ promo, index }))
    .filter(({ promo }) => promo && typeof promo === 'object' && String(promo.title || '').trim())
    .sort((left, right) => {
      const leftPriority = latestPromoPriority(left.promo, left.index);
      const rightPriority = latestPromoPriority(right.promo, right.index);
      return leftPriority[0] - rightPriority[0]
        || leftPriority[1] - rightPriority[1]
        || leftPriority[2] - rightPriority[2];
    })
    .map(({ promo }) => promo);
}

function latestPromoPrimaryPromo(context) {
  const rankedPromos = latestPromoRankedPromos(context);
  if (rankedPromos.length) return rankedPromos[0];
  return context && typeof context.primary === 'object' ? context.primary : null;
}

function latestPromoExtraTitles(context, primaryTitle) {
  const titles = [];
  latestPromoRankedPromos(context).forEach((promo) => {
    if (!promo || typeof promo !== 'object') return;
    const title = String(promo.title || '').trim();
    if (!title || title === primaryTitle || titles.includes(title)) return;
    titles.push(title);
  });
  return titles;
}

function latestPromoDisplayLabel(context, primaryTitle, extraTitles) {
  const explicitLabel = String((context && context.display_label) || '').trim();
  if (!primaryTitle) return '';
  if (Array.isArray(context && context.promos) && context.promos.length) {
    return extraTitles.length ? `${primaryTitle} + ${extraTitles.length} promos adicionales` : primaryTitle;
  }
  if (explicitLabel) return explicitLabel;
  return extraTitles.length ? `${primaryTitle} + ${extraTitles.length} promos adicionales` : primaryTitle;
}

function renderLatestPromoContext(report) {
  const meta = report && typeof report === 'object' ? (report.meta || {}) : {};
  const context = meta && typeof meta.active_promo_context === 'object'
    ? meta.active_promo_context
    : null;
  if (!context) return '';
  const primaryTitle = latestPromoPrimaryTitle(context);
  if (!primaryTitle) return '';
  const extraTitles = latestPromoExtraTitles(context, primaryTitle);
  const displayLabel = latestPromoDisplayLabel(context, primaryTitle, extraTitles);
  const categoryLabels = Array.isArray(context.categories)
    ? context.categories.filter(Boolean).map(latestPromoCategoryLabel).slice(0, 4)
    : [];
  const categoriesHtml = categoryLabels.length
    ? `<div class="latest-promo-pills">${categoryLabels.map(label => `<span>${escapeHtml(label)}</span>`).join('')}</div>`
    : '';
  const primaryHtml = displayLabel !== primaryTitle
    ? `<div class="latest-promo-extra">Promo destacada: ${escapeHtml(primaryTitle)}</div>`
    : '';
  const extrasHtml = extraTitles.length
    ? `<div class="latest-promo-extra">También activas: ${escapeHtml(extraTitles.slice(0, 3).join(', '))}</div>`
    : '';
  const simultaneousHint = String(context.simultaneous_hint || '').trim();
  const decisionHint = String(context.decision_hint || '').trim();
  const hintsHtml = [simultaneousHint, decisionHint]
    .filter(Boolean)
    .map((hint) => `<div class="latest-promo-hint">${escapeHtml(hint)}</div>`)
    .join('');
  return `
    <div class="latest-promo-section" data-latest-promo-context>
      <div class="latest-promo-head">
        <div class="latest-promo-title">Contexto de promo activa</div>
        <div class="latest-promo-subtitle">Contexto del último JSON local: ordena la promo destacada por jerarquía; no es predicción ni cambia el score.</div>
      </div>
      <div class="latest-promo-primary"><span>Promo detectada con más peso</span><strong>${escapeHtml(displayLabel)}</strong></div>
      ${categoriesHtml}
      ${primaryHtml}
      ${extrasHtml}
      ${hintsHtml}
    </div>
  `;
}

function latestPromoHighlightsPayload(report) {
  const payload = report && typeof report === 'object' ? report.promo_highlights : null;
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null;
}

function latestPromoHighlightsSections(payload) {
  return Array.isArray(payload && payload.sections)
    ? payload.sections.filter(section => section && typeof section === 'object')
    : [];
}

function latestPromoHighlightsItems(section) {
  return Array.isArray(section && section.items)
    ? section.items.filter(item => item && typeof item === 'object')
    : [];
}

function latestPromoHighlightsHasContract(report) {
  if (!report || typeof report !== 'object') return false;
  if (latestPromoHighlightsPayload(report)) return true;
  const summary = report.summary && typeof report.summary === 'object' ? report.summary : {};
  return Object.prototype.hasOwnProperty.call(summary, 'promo_highlights_count');
}

function latestPromoHighlightItemTitle(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = String(source.name || source.steam_name || (appid ? `AppID ${appid}` : 'Juego destacado')).trim();
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return {appid, safeAppid, nameHtml};
}

function latestPromoHighlightItemMeta(item) {
  const source = item && typeof item === 'object' ? item : {};
  const parts = [];
  const sourceLabel = String(source.source || '').trim();
  if (sourceLabel) parts.push(sourceLabel === 'top_pick' ? 'Top Pick' : sourceLabel.replace(/_/g, ' '));
  const recommendation = String(source.recommendation || '').trim();
  if (recommendation) parts.push(recommendation);
  const discount = Number(source.discount);
  if (Number.isFinite(discount) && discount > 0) parts.push(`-${discount.toFixed(0)}%`);
  const price = String(source.price_final || source.price || '').trim();
  if (price) parts.push(price);
  return parts.join(' · ');
}

function latestPromoHighlightReasons(item) {
  return Array.isArray(item && item.highlight_reasons)
    ? item.highlight_reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 3)
    : [];
}

function renderLatestPromoHighlightItem(item) {
  const title = latestPromoHighlightItemTitle(item);
  const meta = latestPromoHighlightItemMeta(item);
  const reasons = latestPromoHighlightReasons(item);
  return `
    <li class="latest-promo-highlight-item"${title.safeAppid ? ` data-latest-promo-highlight-appid="${escapeHtml(title.safeAppid)}"` : ''}>
      <div class="latest-promo-highlight-item-main">
        <strong>${title.nameHtml}</strong>
        ${meta ? `<span class="latest-promo-highlight-item-meta">${escapeHtml(meta)}</span>` : ''}
        <span class="latest-promo-highlight-item-reasons">${escapeHtml((reasons.length ? reasons : ['contexto local de promo activa']).join(' · '))}</span>
      </div>
    </li>
  `;
}

function renderLatestPromoHighlightSection(section) {
  const source = section && typeof section === 'object' ? section : {};
  const title = String(source.title || (source.promo_title ? `Highlights de ${source.promo_title}` : 'Highlights de promo')).trim();
  const category = String(source.category_label || latestPromoCategoryLabel(source.category) || 'Otra promo').trim();
  const items = latestPromoHighlightsItems(source);
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  if (!selectedItems.length) return '';
  return `
    <article class="latest-promo-highlight-section" data-latest-promo-highlight-section="${escapeHtml(source.id || source.promo_title || 'promo')}">
      <div class="latest-promo-highlight-section-head">
        <h4>${escapeHtml(title)}</h4>
        <span>${escapeHtml(category)}</span>
      </div>
      <ol class="latest-promo-highlight-list">
        ${selectedItems.map(renderLatestPromoHighlightItem).join('')}
      </ol>
      ${hiddenCount ? `<div class="latest-promo-highlight-more">${escapeHtml(formatLatestCoverageCount(hiddenCount))} más en el JSON completo</div>` : ''}
    </article>
  `;
}

function renderLatestPromoHighlights(report) {
  const payload = latestPromoHighlightsPayload(report);
  const sections = latestPromoHighlightsSections(payload);
  const sectionCards = sections.map(renderLatestPromoHighlightSection).filter(Boolean).slice(0, 4);
  const summary = payload && payload.summary && typeof payload.summary === 'object' ? payload.summary : {};
  const count = latestCoverageCount(summary.promos_count) || sectionCards.length;
  const subtitle = count > 0
    ? `${formatLatestCoverageCount(count)} promo(s) con highlights desde el JSON local. Advisory-only: no prueba pertenencia oficial por juego, no cambia score, ranking, Top Picks, cache ni fetching.`
    : 'Sin highlights por promo en este JSON local. Advisory-only: no prueba pertenencia oficial por juego; no cambia score, ranking, Top Picks, cache ni fetching.';
  if (!sectionCards.length && !latestPromoHighlightsHasContract(report)) return '';
  return `
    <div class="latest-promo-highlights-section" data-latest-promo-highlights>
      <div class="latest-promo-highlights-head">
        <div>
          <div class="latest-promo-highlights-title">Highlights por promo</div>
          <div class="latest-promo-highlights-subtitle">${escapeHtml(subtitle)}</div>
        </div>
        <span class="latest-promo-highlights-badge">Vista local</span>
      </div>
      ${sectionCards.length ? `<div class="latest-promo-highlights-grid">${sectionCards.join('')}</div>` : '<div class="latest-promo-highlights-empty">Sin grupos de promo con señales suficientes todavía.</div>'}
    </div>
  `;
}

function latestFreeWeekendPayload(report) {
  const payload = report && typeof report === 'object' ? report.free_weekend_now : null;
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null;
}

function latestFreeWeekendItems(payload) {
  return Array.isArray(payload && payload.items)
    ? payload.items.filter(item => item && typeof item === 'object')
    : [];
}

function latestFreeWeekendCount(payload, items) {
  const summary = payload && typeof payload.summary === 'object' ? payload.summary : {};
  const summaryCount = latestCoverageCount(summary.count);
  return Math.max(summaryCount, Array.isArray(items) ? items.length : 0);
}

function latestFreeWeekendConfidenceLabel(confidence) {
  const key = String(confidence || '').trim().toLowerCase();
  return LATEST_FREE_WEEKEND_CONFIDENCE_LABELS[key] || (key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Sin dato');
}

function latestFreeWeekendTitle(source) {
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = String(source.title || source.name || (appid ? `AppID ${appid}` : 'Candidato sin título')).trim();
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return {appid, safeAppid, nameHtml};
}

function latestFreeWeekendMeta(source) {
  const parts = [`Confianza ${latestFreeWeekendConfidenceLabel(source.confidence)}`];
  const validUntil = String(source.valid_until || '').trim();
  parts.push(validUntil ? `Vigente hasta ${validUntil}` : 'Sin vigencia estructurada');
  const observedAt = String(source.observed_at || '').trim();
  if (observedAt) parts.push(`Observado ${observedAt}`);
  return parts.join(' · ');
}

function latestFreeWeekendReason(source) {
  const reason = String(source.reason || '').trim();
  if (reason) return reason;
  const signals = source.signals && typeof source.signals === 'object' ? source.signals : {};
  const parts = [];
  if (signals.discount_percent !== null && signals.discount_percent !== undefined) parts.push(`descuento ${signals.discount_percent}%`);
  if (signals.final_price !== null && signals.final_price !== undefined) parts.push(`precio final ${signals.final_price}`);
  const matchedText = String(signals.matched_text || '').trim();
  if (matchedText) parts.push(`texto: ${matchedText}`);
  return parts.join(' · ') || 'Revisar disponibilidad en Steam';
}

function latestFreeWeekendSources(source) {
  const sources = Array.isArray(source.sources)
    ? source.sources.map(item => String(item || '').trim()).filter(Boolean).slice(0, 4)
    : [];
  return sources.join(', ') || 'Sin fuentes compactas';
}

function latestFreeWeekendCrossReasons(source) {
  const directReasons = Array.isArray(source.cross_reasons)
    ? source.cross_reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 4)
    : [];
  if (directReasons.length) return directReasons;
  const crossSignals = source.cross_signals && typeof source.cross_signals === 'object' ? source.cross_signals : {};
  const reasons = [];
  if (crossSignals.in_wishlist === true) reasons.push('en tu wishlist');
  const ownedOrFamily = String(crossSignals.owned_or_family || '').trim();
  if (ownedOrFamily === 'owned') reasons.push('ya en biblioteca');
  if (ownedOrFamily === 'family') reasons.push('disponible en biblioteca familiar');
  if (crossSignals.similar_to_profile === true) reasons.push('similar a tus gustos');
  return reasons.slice(0, 4);
}

function renderLatestFreeWeekendCross(source) {
  const reasons = latestFreeWeekendCrossReasons(source);
  if (!reasons.length) return '';
  return `<span class="latest-free-weekend-cross">${reasons.map(reason => `<em>${escapeHtml(reason)}</em>`).join('')}</span>`;
}

function renderLatestFreeWeekendItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const title = latestFreeWeekendTitle(source);
  return `
    <li class="latest-free-weekend-item"${title.safeAppid ? ` data-latest-free-weekend-appid="${escapeHtml(title.safeAppid)}"` : ''}>
      <div class="latest-free-weekend-item-main">
        <strong>${title.nameHtml}</strong>
        <span class="latest-free-weekend-meta">${escapeHtml(latestFreeWeekendMeta(source))}</span>
        <span class="latest-free-weekend-reason">${escapeHtml(latestFreeWeekendReason(source))}</span>
        ${renderLatestFreeWeekendCross(source)}
      </div>
      <span class="latest-free-weekend-sources">${escapeHtml(latestFreeWeekendSources(source))}</span>
    </li>
  `;
}

function renderLatestFreeWeekendNow(report) {
  const payload = latestFreeWeekendPayload(report);
  if (!payload) return '';
  const items = latestFreeWeekendItems(payload);
  const totalCount = latestFreeWeekendCount(payload, items);
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, totalCount - selectedItems.length);
  const sourcePolicy = String((payload && payload.source_policy) || '').trim();
  const policyHtml = sourcePolicy
    ? `<span class="latest-free-weekend-policy">Política: ${escapeHtml(sourcePolicy)}</span>`
    : '';
  const bodyHtml = selectedItems.length
    ? `<ol class="latest-free-weekend-list">${selectedItems.map(renderLatestFreeWeekendItem).join('')}</ol>${hiddenCount ? `<div class="latest-free-weekend-more">${escapeHtml(formatLatestCoverageCount(hiddenCount))} más en el JSON completo</div>` : ''}`
    : '<div class="latest-free-weekend-empty">Sin candidatos Free Weekend en el payload actual. Activa el opt-in Free Weekend al generar para consultar Store JSON; no recalcula score ni invalida caché de precios.</div>';
  const countCopy = totalCount > 0
    ? `${formatLatestCoverageCount(totalCount)} candidato(s) con señales Store/cache`
    : 'Sin candidatos con señales Store suficientes';
  return `
    <div class="latest-free-weekend-section" data-latest-free-weekend-now>
      <div class="latest-free-weekend-head">
        <div>
          <div class="latest-free-weekend-title">Free Weekend ahora</div>
          <div class="latest-free-weekend-subtitle">${escapeHtml(countCopy)}. Revisa confianza y vigencia antes de asumir disponibilidad; no cambia score, ranking ni caché de precios.</div>
        </div>
        <span class="latest-free-weekend-badge">Señales Store/cache</span>
      </div>
      ${policyHtml}
      ${bodyHtml}
    </div>
  `;
}

function latestExternalOffersPayload(report) {
  const payload = report && typeof report === 'object' ? report.external_offers : null;
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null;
}

function latestExternalOfferRiskFlags(source) {
  return Array.isArray(source && source.risk_flags)
    ? source.risk_flags.map(flag => String(flag || '').trim()).filter(Boolean)
    : [];
}

function latestExternalOfferPrice(source) {
  const price = Number(source && source.price);
  return Number.isFinite(price) && price >= 0 ? price : null;
}

function latestExternalOfferCurrency(source) {
  const currency = String((source && source.currency) || '').trim().toUpperCase();
  return /^[A-Z]{3}$/.test(currency) ? currency : '';
}

function latestExternalOfferIsVisible(source) {
  if (!source || typeof source !== 'object') return false;
  if (!LATEST_EXTERNAL_OFFER_VISIBLE_STATES.includes(String(source.visibility || '').trim())) return false;
  if (!LATEST_EXTERNAL_OFFER_VISIBLE_STORE_TYPES.includes(String(source.store_type || '').trim())) return false;
  const flags = new Set(latestExternalOfferRiskFlags(source));
  if (LATEST_EXTERNAL_OFFER_BLOCKING_RISKS.some(flag => flags.has(flag))) return false;
  return latestExternalOfferPrice(source) !== null && Boolean(latestExternalOfferCurrency(source));
}

function latestExternalOfferItems(payload) {
  return Array.isArray(payload && payload.items)
    ? payload.items.filter(latestExternalOfferIsVisible)
    : [];
}

function latestExternalOffersTotal(items) {
  return Array.isArray(items) ? items.length : 0;
}

function latestExternalOfferConfidenceLabel(confidence) {
  const key = String(confidence || '').trim().toLowerCase();
  return LATEST_EXTERNAL_OFFER_CONFIDENCE_LABELS[key] || (key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Sin dato');
}

function latestExternalOfferStoreTypeLabel(storeType) {
  const key = String(storeType || '').trim();
  return LATEST_EXTERNAL_OFFER_STORE_TYPE_LABELS[key] || (key ? key.replace(/_/g, ' ') : 'Tienda');
}

function latestExternalOfferSafeUrl(source) {
  if (!source || source.link_allowed !== true) return '';
  const rawUrl = String(source.url || '').trim();
  if (!rawUrl) return '';
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch (e) {
    return '';
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) return '';
  let decoded = rawUrl.toLowerCase();
  try {
    decoded = decodeURIComponent(rawUrl).toLowerCase();
  } catch (e) {}
  decoded = decoded.replace(/[\s_]+/g, '-');
  return LATEST_EXTERNAL_OFFER_CHECKOUT_RE.test(decoded) ? '' : rawUrl;
}

function latestExternalOfferTitle(source) {
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = String(source.name || source.steam_name || (appid ? `AppID ${appid}` : 'Oferta externa')).trim();
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return {appid, safeAppid, nameHtml};
}

function latestExternalOfferPriceText(source) {
  const price = latestExternalOfferPrice(source);
  const currency = latestExternalOfferCurrency(source);
  const parts = [price !== null && currency ? `${currency} ${price.toFixed(2)}` : 'Sin precio válido'];
  const discount = Number(source.discount_pct);
  if (Number.isFinite(discount) && discount) parts.push(`-${discount.toFixed(0)}%`);
  return parts.join(' · ');
}

function latestExternalOfferMeta(source) {
  const storeName = String(source.store_name || source.store_id || 'Tienda externa').trim();
  const storeType = latestExternalOfferStoreTypeLabel(source.store_type);
  return `${storeName} · ${storeType} · ${latestExternalOfferPriceText(source)}`;
}

function latestExternalOfferStatus(source) {
  const parts = [`Confianza ${latestExternalOfferConfidenceLabel(source.confidence)}`];
  const drm = String(source.drm || '').trim();
  const region = String(source.region || '').trim();
  const sourceName = String(source.source || '').trim();
  const expiresAt = String(source.expires_at || '').trim();
  if (drm) parts.push(`DRM ${drm}`);
  if (region) parts.push(`Región ${region}`);
  if (sourceName) parts.push(`fuente ${sourceName}`);
  if (expiresAt) parts.push(`vence ${expiresAt}`);
  return parts.join(' · ');
}

function latestExternalOfferChipLabels(source) {
  const visibility = String(source.visibility || '').trim();
  const storeType = String(source.store_type || '').trim();
  const flags = new Set(latestExternalOfferRiskFlags(source));
  const labels = [];
  if (visibility === 'highlight') labels.push('Mejor fuera de Steam');
  if (storeType === 'official_store') labels.push('Tienda oficial');
  else if (storeType === 'authorized_key_reseller') labels.push('Tienda autorizada');
  if (visibility === 'review' || flags.has('drm_unknown') || flags.has('region_unknown')) {
    labels.push('Revisar DRM/región');
  }
  return [...new Set(labels)];
}

function renderLatestExternalOfferChips(source) {
  const labels = latestExternalOfferChipLabels(source);
  if (!labels.length) return '';
  return `<span class="latest-external-offer-chips">${labels.map(label => `<span class="latest-external-offer-chip">${escapeHtml(label)}</span>`).join('')}</span>`;
}

function renderLatestExternalOfferItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const title = latestExternalOfferTitle(source);
  const safeUrl = latestExternalOfferSafeUrl(source);
  const actionHtml = safeUrl
    ? `<a class="latest-external-offer-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">Ver tienda (sin carrito)</a>`
    : '<span class="latest-external-offer-link latest-external-offer-link-disabled">Sin link seguro</span>';
  const badge = String(source.visibility || '').trim() === 'highlight' ? 'Destacada' : 'Revisión';
  return `
    <li class="latest-external-offer-item"${title.safeAppid ? ` data-latest-external-offer-appid="${escapeHtml(title.safeAppid)}"` : ''}>
      <div class="latest-external-offer-main">
        <strong>${title.nameHtml}</strong>
        <span class="latest-external-offer-meta">${escapeHtml(latestExternalOfferMeta(source))}</span>
        <span class="latest-external-offer-status">${escapeHtml(latestExternalOfferStatus(source))}</span>
        ${renderLatestExternalOfferChips(source)}
        <span class="latest-external-offer-note">Comparativa informativa: no prueba ownership, no abre carrito/checkout ni verifica stock final.</span>
      </div>
      <span class="latest-external-offer-side">
        <span class="latest-external-offer-badge">${escapeHtml(badge)}</span>
        ${actionHtml}
      </span>
    </li>
  `;
}

function renderLatestExternalOffers(report) {
  const payload = latestExternalOffersPayload(report);
  const items = latestExternalOfferItems(payload);
  const totalCount = latestExternalOffersTotal(items);
  if (!totalCount) return '';
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, totalCount - selectedItems.length);
  return `
    <div class="latest-external-offers-section" data-latest-external-offers>
      <div class="latest-external-offers-head">
        <div>
          <div class="latest-external-offers-title">Comparativa externa</div>
          <div class="latest-external-offers-subtitle">${escapeHtml(formatLatestCoverageCount(totalCount))} oferta(s) visible(s) desde el JSON local. Comparativa informativa: Steam Tools no compra, no abre carrito ni checkout, no verifica stock final, no prueba ownership y no cambia score, ranking ni wishlist hygiene.</div>
        </div>
        <span class="latest-external-offers-head-badge">Solo tiendas oficiales/autorizadas · sin checkout</span>
      </div>
      <ol class="latest-external-offers-list">${selectedItems.map(renderLatestExternalOfferItem).join('')}</ol>
      ${hiddenCount ? `<div class="latest-external-offers-more">${escapeHtml(formatLatestCoverageCount(hiddenCount))} más en el JSON completo</div>` : ''}
    </div>
  `;
}

function latestTastePriorityPayload(report) {
  const payload = report && typeof report === 'object' ? report.taste_priority : null;
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null;
}

function latestTastePriorityLabels(payload) {
  const labels = {...LATEST_TASTE_PRIORITY_CATEGORY_LABELS};
  const rawLabels = payload && payload.category_labels;
  if (rawLabels && typeof rawLabels === 'object' && !Array.isArray(rawLabels)) {
    Object.entries(rawLabels).forEach(([key, value]) => {
      labels[String(key)] = String(value);
    });
  }
  labels.espera_oferta = LATEST_TASTE_PRIORITY_CATEGORY_LABELS.espera_oferta;
  return labels;
}

function latestTastePriorityItems(payload) {
  return Array.isArray(payload && payload.items)
    ? payload.items.filter(item => item && typeof item === 'object')
    : [];
}

function latestTastePriorityTitle(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = String(source.name || source.steam_name || (appid ? `AppID ${appid}` : 'Juego')).trim();
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return {appid, safeAppid, nameHtml};
}

function latestTastePriorityCategory(item, labels) {
  const category = String((item && item.category) || '').trim();
  return labels[category] || (category ? category.replace(/_/g, ' ') : 'Sin categoría');
}

function latestTastePriorityScore(item) {
  const score = Number(item && item.taste_priority);
  return Number.isFinite(score) ? score.toFixed(1) : '—';
}

function latestTastePrioritySignals(item) {
  const source = item && typeof item === 'object' ? item : {};
  const reasons = Array.isArray(source.reasons)
    ? source.reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 2)
    : [];
  const clusters = Array.isArray(source.clusters)
    ? source.clusters
        .map(cluster => cluster && typeof cluster === 'object' ? String(cluster.label || cluster.id || '').trim() : '')
        .filter(Boolean)
        .slice(0, 2)
    : [];
  const parts = reasons.length ? reasons : clusters;
  return parts.length ? parts.join(' · ') : '—';
}

function renderLatestTastePriorityItem(item, labels) {
  const title = latestTastePriorityTitle(item);
  const category = latestTastePriorityCategory(item, labels);
  return `
    <li class="latest-taste-priority-item"${title.safeAppid ? ` data-latest-taste-priority-appid="${escapeHtml(title.safeAppid)}"` : ''}>
      <div class="latest-taste-priority-main">
        <strong>${title.nameHtml}</strong>
        <span class="latest-taste-priority-meta">${escapeHtml(category)} · Índice ${escapeHtml(latestTastePriorityScore(item))}</span>
        <span class="latest-taste-priority-signals">${escapeHtml(latestTastePrioritySignals(item))}</span>
        <span class="latest-taste-priority-note">Señal informativa: no cambia score, ranking ni Top Picks; no predice precio ni mínimo histórico.</span>
      </div>
      <span class="latest-taste-priority-badge">Advisory</span>
    </li>
  `;
}

function renderLatestTastePriority(report) {
  const payload = latestTastePriorityPayload(report);
  const items = latestTastePriorityItems(payload);
  if (!items.length) return '';
  const labels = latestTastePriorityLabels(payload);
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  return `
    <div class="latest-taste-priority-section" data-latest-taste-priority>
      <div class="latest-taste-priority-head">
        <div>
          <div class="latest-taste-priority-title">Prioridad por gustos</div>
          <div class="latest-taste-priority-subtitle">${escapeHtml(formatLatestCoverageCount(items.length))} juego(s) desde taste_priority local. Advisory-only: no cambia score, ranking, Top Picks, defaults, cache ni fetching. No es predicción de precio ni mínimo histórico.</div>
        </div>
        <span class="latest-taste-priority-head-badge">Sin impacto en ranking</span>
      </div>
      <ol class="latest-taste-priority-list">${selectedItems.map(item => renderLatestTastePriorityItem(item, labels)).join('')}</ol>
      ${hiddenCount ? `<div class="latest-taste-priority-more">${escapeHtml(formatLatestCoverageCount(hiddenCount))} más en el JSON completo</div>` : ''}
    </div>
  `;
}

function latestDecisionSupportPayload(report) {
  const payload = report && typeof report === 'object' ? report.decision_support : null;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  if (payload.schema !== 'decision_support_v1') return null;
  if (!['available', 'partial'].includes(String(payload.status || '').trim())) return null;
  if (payload.advisory_only !== true || String(payload.ranking_impact || '').trim() !== 'none') return null;
  const sourceSchemas = Array.isArray(payload.source_schemas) ? payload.source_schemas : [];
  if (sourceSchemas.join('|') !== 'player_behavior_profile_v1|player_behavior_fit_v1') return null;
  return payload;
}

function latestDecisionSupportAppid(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  return /^\d+$/.test(appid) ? appid : '';
}

function latestDecisionSupportLabel(label) {
  const key = String(label || '').trim();
  return LATEST_DECISION_SUPPORT_LABELS[key] || '';
}

function latestDecisionSupportCodeLabel(code, labels) {
  const key = String(code || '').trim();
  return labels[key] || '';
}

function latestDecisionSupportPreferenceLabels(item) {
  const source = item && typeof item === 'object' ? item : {};
  return Array.isArray(source.matched_preferences)
    ? source.matched_preferences
      .map(preference => preference && typeof preference === 'object' ? String(preference.label || '').trim() : '')
      .filter(Boolean)
      .slice(0, 2)
    : [];
}

function latestDecisionSupportReasonLabels(item) {
  const source = item && typeof item === 'object' ? item : {};
  const fitReasons = Array.isArray(source.fit_reasons)
    ? source.fit_reasons
      .map(reason => latestDecisionSupportCodeLabel(reason, LATEST_DECISION_SUPPORT_FIT_REASON_LABELS))
      .filter(Boolean)
    : [];
  const cautions = Array.isArray(source.caution_reasons)
    ? source.caution_reasons
      .map(reason => latestDecisionSupportCodeLabel(reason, LATEST_DECISION_SUPPORT_CAUTION_LABELS))
      .filter(Boolean)
      .map(label => `Cuidado: ${label}`)
    : [];
  return [...fitReasons, ...cautions].slice(0, 2);
}

function latestDecisionSupportHasVisibleSignals(item) {
  return latestDecisionSupportPreferenceLabels(item).length > 0 || latestDecisionSupportReasonLabels(item).length > 0;
}

function latestDecisionSupportItems(payload) {
  return Array.isArray(payload && payload.items)
    ? payload.items.filter(item => item && typeof item === 'object')
      .filter(item => latestDecisionSupportAppid(item) && latestDecisionSupportLabel(item.decision_label) && latestDecisionSupportHasVisibleSignals(item))
    : [];
}

function latestDecisionSupportConfidenceLabel(confidence) {
  const key = String(confidence || '').trim().toLowerCase();
  return LATEST_DECISION_SUPPORT_CONFIDENCE_LABELS[key] || LATEST_DECISION_SUPPORT_CONFIDENCE_LABELS.unknown;
}

function latestDecisionSupportFitLevelLabel(fitLevel) {
  const key = String(fitLevel || '').trim().toLowerCase();
  return LATEST_DECISION_SUPPORT_FIT_LEVEL_LABELS[key] || '';
}

function renderLatestDecisionSupportItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = latestDecisionSupportAppid(source);
  const decisionLabel = String(source.decision_label || '').trim();
  const label = latestDecisionSupportLabel(decisionLabel);
  const name = String(source.name || source.steam_name || (appid ? `AppID ${appid}` : 'Juego')).trim();
  const nameHtml = appid
    ? `<a href="${latestSteamStoreUrl(appid)}" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  const preferences = latestDecisionSupportPreferenceLabels(source);
  const reasons = latestDecisionSupportReasonLabels(source);
  const meta = [
    latestDecisionSupportFitLevelLabel(source.fit_level),
    `Confianza ${latestDecisionSupportConfidenceLabel(source.confidence)}`,
  ].filter(Boolean).join(' · ');
  return `
    <li class="latest-decision-support-item latest-decision-support-item-${escapeHtml(decisionLabel)}" data-latest-decision-support-item="${escapeHtml(appid)}">
      <div class="latest-decision-support-main">
        <div class="latest-decision-support-heading">
          <strong>${nameHtml}</strong>
          <span class="latest-decision-support-badge">${escapeHtml(label)}</span>
        </div>
        <span class="latest-decision-support-meta">${escapeHtml(meta)}</span>
        ${preferences.length ? `<span class="latest-decision-support-preferences"><strong>Preferencias:</strong> ${escapeHtml(preferences.join(' · '))}</span>` : ''}
        ${reasons.length ? `<span class="latest-decision-support-reasons"><strong>Razones:</strong> ${escapeHtml(reasons.join(' · '))}</span>` : ''}
        <span class="latest-decision-support-note">Advisory-only: sin impacto en ranking.</span>
      </div>
    </li>
  `;
}

function renderLatestDecisionSupport(report) {
  const payload = latestDecisionSupportPayload(report);
  const items = latestDecisionSupportItems(payload);
  if (!items.length) return '';
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  return `
    <div class="latest-decision-support-section" data-latest-decision-support>
      <div class="latest-decision-support-head">
        <div>
          <div class="latest-decision-support-title">Ayuda para decidir</div>
          <div class="latest-decision-support-subtitle">${escapeHtml(formatLatestCoverageCount(items.length))} juego(s) desde decision_support_v1 del JSON local. Advisory-only: no cambia score, ranking, Top Picks, defaults, cache ni fetching.</div>
        </div>
        <span class="latest-decision-support-head-badge">Sin impacto en ranking</span>
      </div>
      <ol class="latest-decision-support-list">${selectedItems.map(renderLatestDecisionSupportItem).join('')}</ol>
      ${hiddenCount ? `<div class="latest-decision-support-more">${escapeHtml(formatLatestCoverageCount(hiddenCount))} más en el JSON completo</div>` : ''}
    </div>
  `;
}

function latestRecommendationDiagnosticsPayload(report) {
  const payload = report && typeof report === 'object' ? report.recommendation_diagnostics : null;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  const mode = String(payload.recommendation_mode || '').trim();
  if (!Object.prototype.hasOwnProperty.call(LATEST_RECOMMENDATION_DIAGNOSTIC_MODE_LABELS, mode)) return null;
  return {...payload, recommendation_mode: mode};
}

function latestRecommendationDiagnosticPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(0)}%` : '—';
}

function latestRecommendationDiagnosticConfidence(payload) {
  const confidence = payload && payload.recommendation_confidence && typeof payload.recommendation_confidence === 'object'
    ? payload.recommendation_confidence
    : {};
  const level = String(confidence.level || '').trim().toLowerCase();
  const label = LATEST_RECOMMENDATION_DIAGNOSTIC_CONFIDENCE_LABELS[level] || (level ? level.charAt(0).toUpperCase() + level.slice(1) : '—');
  const score = Number(confidence.score);
  return Number.isFinite(score) && label !== '—' ? `${label} (${(score * 100).toFixed(0)}%)` : label;
}

function latestRecommendationDiagnosticSources(payload) {
  return Array.isArray(payload && payload.signal_sources)
    ? payload.signal_sources.map(source => String(source || '').trim().replace(/_/g, ' ')).filter(Boolean).slice(0, 5)
    : [];
}

function renderLatestRecommendationDiagnostics(report) {
  const payload = latestRecommendationDiagnosticsPayload(report);
  if (!payload) return '';
  const modeLabel = LATEST_RECOMMENDATION_DIAGNOSTIC_MODE_LABELS[payload.recommendation_mode];
  const metrics = [
    ['Fuerza conductual', latestRecommendationDiagnosticPercent(payload.behavioral_signal_strength)],
    ['Dependencia score fallback', latestRecommendationDiagnosticPercent(payload.fallback_dependence)],
    ['Impacto ranking', String(payload.ranking_impact || 'none')],
  ];
  const sources = latestRecommendationDiagnosticSources(payload);
  const hints = Array.isArray(payload.improve_recommendations)
    ? payload.improve_recommendations.map(hint => String(hint || '').trim()).filter(Boolean).slice(0, 4)
    : [];
  const sourcesHtml = sources.length
    ? `<div class="latest-recommendation-diagnostics-sources"><strong>Fuentes usadas</strong><div>${sources.map(source => `<span>${escapeHtml(source)}</span>`).join('')}</div></div>`
    : '';
  const hintsHtml = hints.length
    ? `<ul class="latest-recommendation-diagnostics-hints">${hints.map(hint => `<li>${escapeHtml(hint)}</li>`).join('')}</ul>`
    : '';
  return `
    <div class="latest-recommendation-diagnostics-section" data-latest-recommendation-diagnostics>
      <div class="latest-recommendation-diagnostics-head">
        <div>
          <div class="latest-recommendation-diagnostics-title">Diagnóstico de recomendaciones</div>
          <div class="latest-recommendation-diagnostics-subtitle">Modo ${escapeHtml(modeLabel)} · Confianza ${escapeHtml(latestRecommendationDiagnosticConfidence(payload))}. Advisory-only: no cambia score, ranking, Top Picks, defaults, cache ni fetching.</div>
        </div>
        <span class="latest-recommendation-diagnostics-badge">Sin impacto en ranking</span>
      </div>
      <div class="latest-recommendation-diagnostics-grid">
        ${metrics.map(([label, value]) => `<div class="latest-recommendation-diagnostics-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}
      </div>
      ${sourcesHtml}
      ${hintsHtml}
    </div>
  `;
}

function latestSmartAlertSections(payload) {
  if (!payload || typeof payload !== 'object') return [];
  if (payload.dry_run !== true || payload.send_ready !== false) return [];
  return Array.isArray(payload.sections)
    ? payload.sections.filter(section => section && typeof section === 'object')
    : [];
}

function latestSmartAlertItemTitle(item) {
  const source = item && typeof item === 'object' ? item : {};
  const title = String(source.title || '').trim();
  if (title) return {label: title, appid: ''};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const name = String(source.name || source.steam_name || (appid ? `AppID ${appid}` : 'Señal')).trim();
  return {label: name, appid: /^\d+$/.test(appid) ? appid : ''};
}

function formatLatestSignedPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '';
  const rounded = Math.round(number);
  if (rounded > 0) return `+${rounded}%`;
  return `${rounded}%`;
}

function latestSmartAlertItemMeta(item) {
  const source = item && typeof item === 'object' ? item : {};
  const parts = [];
  const changePct = Number(source.change_pct);
  const currentPrice = Number(source.current_price);
  const historicalLow = Number(source.historical_low);
  const gamesCount = Number(source.games_count);
  if (Number.isFinite(changePct)) parts.push(formatLatestSignedPercent(changePct));
  if (Number.isFinite(currentPrice)) parts.push(`actual $${currentPrice.toFixed(0)}`);
  if (Number.isFinite(historicalLow)) parts.push(`mín. $${historicalLow.toFixed(0)}`);
  if (Number.isFinite(gamesCount)) parts.push(`${gamesCount.toFixed(0)} juegos`);
  const reason = String(source.reason || '').trim();
  if (reason) parts.push(reason);
  return parts.join(' · ');
}

function renderLatestSmartAlertItem(item) {
  const title = latestSmartAlertItemTitle(item);
  const meta = latestSmartAlertItemMeta(item);
  const labelHtml = title.appid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(title.appid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(title.label)}</a>`
    : `<span>${escapeHtml(title.label)}</span>`;
  return `
    <li class="latest-smart-alert-item">
      <strong>${labelHtml}</strong>
      ${meta ? `<small>${escapeHtml(meta)}</small>` : ''}
    </li>
  `;
}

function renderLatestSmartAlertSection(section) {
  const items = Array.isArray(section && section.items)
    ? section.items.filter(item => item && typeof item === 'object').slice(0, 3)
    : [];
  const hiddenCount = Math.max(0, Number(section && section.hidden_count) || 0);
  const count = Math.max(0, Number(section && section.count) || 0);
  return `
    <article class="latest-smart-alert-section" data-latest-smart-alert-section="${escapeHtml(String((section && section.id) || ''))}">
      <div class="latest-smart-alert-section-head">
        <strong>${escapeHtml(String((section && (section.label || section.id)) || 'Sección'))}</strong>
        <span>${escapeHtml(count.toFixed(0))}</span>
      </div>
      ${items.length ? `<ol class="latest-smart-alert-list">${items.map(renderLatestSmartAlertItem).join('')}</ol>` : '<div class="latest-smart-alert-empty">Ver JSON completo</div>'}
      ${hiddenCount ? `<div class="latest-smart-alert-more">+${escapeHtml(hiddenCount.toFixed(0))} más en el JSON</div>` : ''}
    </article>
  `;
}

function renderLatestSmartAlertDigest(report) {
  const payload = report && typeof report === 'object' ? (report.smart_alert_digest || null) : null;
  const sections = latestSmartAlertSections(payload);
  if (!sections.length) return '';
  const totalCount = Math.max(0, Number(payload.total_count) || 0);
  return `
    <div class="latest-smart-alert-digest" data-latest-smart-alert-digest>
      <div class="latest-smart-alert-head">
        <div>
          <div class="latest-smart-alert-title">Alertas inteligentes — preview local</div>
          <div class="latest-smart-alert-subtitle">${escapeHtml(totalCount.toFixed(0))} señales agrupadas en digest dry-run. No envía Telegram/Discord ni activa notificaciones por juego.</div>
        </div>
        <span class="latest-smart-alert-badge">Dry-run</span>
      </div>
      <div class="latest-smart-alert-grid">
        ${sections.map(renderLatestSmartAlertSection).join('')}
      </div>
    </div>
  `;
}

function toBudgetNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function formatBudgetCurrency(value) {
  return `$${toBudgetNumber(value).toFixed(0)} MXN`;
}

function estimateBudgetSavingsFromPicks(picks) {
  return (Array.isArray(picks) ? picks : []).reduce((total, pick) => {
    const price = toBudgetNumber(pick && pick.price_raw) / 100;
    const discount = toBudgetNumber(pick && pick.discount);
    if (price <= 0 || discount <= 0 || discount >= 100) return total;
    const original = price * 100 / (100 - discount);
    return total + (original - price);
  }, 0);
}

function cloneBudgetPickForUi(pick) {
  const source = pick && typeof pick === 'object' ? pick : {};
  return {
    ...source,
    score_reasons: Array.isArray(source.score_reasons) ? [...source.score_reasons] : [],
    replacement_candidates: Array.isArray(source.replacement_candidates)
      ? source.replacement_candidates.map(candidate => ({
        ...candidate,
        score_reasons: Array.isArray(candidate.score_reasons) ? [...candidate.score_reasons] : [],
      }))
      : [],
  };
}

function buildFallbackBudgetVariant(budgetResult) {
  if (!budgetResult || typeof budgetResult !== 'object') return null;
  return {
    id: budgetResult.selected_variant || 'primary',
    label: 'Lista actual',
    description: 'Selección principal guardada en el último run.',
    selected: Array.isArray(budgetResult.selected) ? budgetResult.selected : [],
    total_spent: toBudgetNumber(budgetResult.total_spent),
    remaining: toBudgetNumber(budgetResult.remaining),
    total_savings: toBudgetNumber(budgetResult.total_savings),
    games_count: toBudgetNumber(budgetResult.games_count),
    budget: toBudgetNumber(budgetResult.budget),
  };
}

function budgetVariantRawRows(variant) {
  if (!variant || typeof variant !== 'object') return [];
  if (Array.isArray(variant.selected) && variant.selected.length) return variant.selected;
  if (Array.isArray(variant.items) && variant.items.length) return variant.items;
  return [];
}

function shouldUseRootBudgetRowsForVariant(budgetResult, variant) {
  if (!budgetResult || typeof budgetResult !== 'object' || !variant) return false;
  const rootRows = Array.isArray(budgetResult.selected) ? budgetResult.selected : [];
  if (!rootRows.length || budgetVariantRawRows(variant).length) return false;
  const variants = Array.isArray(budgetResult.variants) ? budgetResult.variants : [];
  const selectedVariant = String(budgetResult.selected_variant || '').trim();
  const variantId = String(variant.id || '').trim();
  return (selectedVariant && variantId === selectedVariant) || (!selectedVariant && variants.length === 1);
}

function budgetVariantRowsForUi(budgetResult, variant) {
  const rows = budgetVariantRawRows(variant);
  if (rows.length) return rows;
  if (shouldUseRootBudgetRowsForVariant(budgetResult, variant)) return budgetResult.selected;
  return [];
}

function findBudgetVariant(budgetResult, variantId) {
  const variants = Array.isArray(budgetResult && budgetResult.variants) ? budgetResult.variants : [];
  if (!variants.length) return buildFallbackBudgetVariant(budgetResult);
  return variants.find(variant => variant && variant.id === variantId)
    || variants.find(variant => variant && variant.id === budgetResult.selected_variant)
    || variants[0];
}

function createLatestBudgetUiState(report) {
  const budgetResult = report && typeof report === 'object' ? (report.budget_result || null) : null;
  const fallbackVariant = findBudgetVariant(budgetResult, budgetResult && budgetResult.selected_variant);
  return {
    report,
    budgetResult,
    selectedVariantId: (fallbackVariant && fallbackVariant.id) || '',
    openReplacementFor: '',
    appliedReplacement: null,
  };
}

function getActiveBudgetPreview() {
  if (!latestBudgetUiState || !latestBudgetUiState.budgetResult) return null;
  const budgetResult = latestBudgetUiState.budgetResult;
  const variant = findBudgetVariant(budgetResult, latestBudgetUiState.selectedVariantId);
  if (!variant) return null;

  const budget = toBudgetNumber(budgetResult.budget || variant.budget);
  let selected = budgetVariantRowsForUi(budgetResult, variant).map(cloneBudgetPickForUi);
  let totalSpent = toBudgetNumber(variant.total_spent ?? budgetResult.total_spent);
  let remaining = toBudgetNumber(variant.remaining ?? budgetResult.remaining);

  const replacementState = latestBudgetUiState.appliedReplacement;
  let replacementSourceAppid = '';
  let replacementCandidateAppid = '';

  if (replacementState && replacementState.variantId === (variant.id || '')) {
    const sourceIndex = selected.findIndex(item => item && item.appid === replacementState.sourceAppid);
    if (sourceIndex >= 0) {
      const sourcePick = selected[sourceIndex];
      const candidate = (sourcePick.replacement_candidates || []).find(item => item && item.appid === replacementState.candidateAppid);
      if (candidate) {
        replacementSourceAppid = replacementState.sourceAppid;
        replacementCandidateAppid = replacementState.candidateAppid;
        selected[sourceIndex] = {
          ...cloneBudgetPickForUi(candidate),
          replacement_preview: true,
          replacement_source_name: sourcePick.name || '',
        };
        if (Number.isFinite(Number(candidate.swap_total_spent))) {
          totalSpent = Number(candidate.swap_total_spent);
        }
        if (Number.isFinite(Number(candidate.swap_remaining))) {
          remaining = Number(candidate.swap_remaining);
        } else {
          remaining = Math.max(0, budget - totalSpent);
        }
      }
    }
  }

  return {
    report: latestBudgetUiState.report,
    budget,
    variant,
    selected,
    gamesCount: selected.length,
    totalSpent,
    remaining,
    totalSavings: estimateBudgetSavingsFromPicks(selected),
    emptyMessage: selected.length
      ? ''
      : 'Esta variante no trae filas de juegos en el JSON local. Revisa el JSON técnico o regenera el reporte; no se muestra una tabla vacía.',
    replacementSourceAppid,
    replacementCandidateAppid,
  };
}

function renderLatestBudgetVariantButtons(budgetResult, preview) {
  const variants = Array.isArray(budgetResult && budgetResult.variants) ? budgetResult.variants : [];
  if (!variants.length) return '';
  return `
    <div class="latest-budget-section">
      <div class="latest-budget-section-title">Probar otra lista</div>
      <div class="latest-budget-section-subtitle">Las tres variantes vienen del último JSON generado; no cambian tu techo de presupuesto.</div>
      <div class="latest-budget-variant-grid">
        ${variants.map((variant) => {
          const isActive = preview.variant && variant.id === preview.variant.id;
          const btnClass = isActive ? 'btn btn-primary latest-budget-variant-btn is-active' : 'btn btn-ghost latest-budget-variant-btn';
          return `
            <button type="button" class="${btnClass}" data-budget-variant="${escapeHtml(variant.id || '')}">
              <span class="latest-budget-variant-label">${escapeHtml(variant.label || variant.id || 'Variante')}</span>
              <span class="latest-budget-variant-meta">${escapeHtml(variant.games_count || 0)} juegos · ${escapeHtml(formatBudgetCurrency(variant.total_spent || 0))}</span>
              <span class="latest-budget-variant-copy">${escapeHtml(variant.description || '')}</span>
            </button>
          `;
        }).join('')}
      </div>
    </div>
  `;
}

function renderLatestBudgetReplacementOptions(pick, preview) {
  const replacements = Array.isArray(pick && pick.replacement_candidates) ? pick.replacement_candidates : [];
  if (!replacements.length) return '';
  const isOpen = latestBudgetUiState && latestBudgetUiState.openReplacementFor === pick.appid;
  const isPreview = preview && preview.replacementSourceAppid === pick.appid;
  const triggerLabel = isPreview ? 'Cambiar otra vez' : 'Cambiar este juego';
  const resetButton = isPreview
    ? `<button type="button" class="btn btn-ghost latest-budget-inline-btn" data-budget-reset-replacement="${escapeHtml(pick.appid)}">Volver al original</button>`
    : '';
  const optionsHtml = isOpen ? `
    <div class="latest-budget-replacement-list">
      ${replacements.map((candidate) => {
        const isSelected = preview && preview.replacementSourceAppid === pick.appid && preview.replacementCandidateAppid === candidate.appid;
        return `
          <button type="button" class="latest-budget-replacement-option${isSelected ? ' is-selected' : ''}" data-budget-replacement-source="${escapeHtml(pick.appid)}" data-budget-replacement-candidate="${escapeHtml(candidate.appid || '')}">
            <strong>${escapeHtml(candidate.name || '')}</strong>
            <span>${escapeHtml(candidate.price_final || '—')} · Score ${escapeHtml(candidate.score || '—')} · Nuevo total ${escapeHtml(formatBudgetCurrency(candidate.swap_total_spent || 0))}</span>
          </button>
        `;
      }).join('')}
    </div>
  ` : '';
  return `
    <div class="latest-budget-replacements-wrap">
      <div class="latest-budget-replacements-actions">
        <button type="button" class="btn btn-ghost latest-budget-inline-btn" data-budget-toggle-replacement="${escapeHtml(pick.appid)}">${triggerLabel}</button>
        ${resetButton}
      </div>
      ${optionsHtml}
    </div>
  `;
}

function renderLatestBudgetSelection(preview) {
  const selected = Array.isArray(preview && preview.selected) ? preview.selected : [];
  const report = preview && preview.report;
  if (!selected.length) {
    return `<div class="latest-budget-empty">${escapeHtml((preview && preview.emptyMessage) || 'No hubo juegos que entraran en el presupuesto de este run.')}</div>`;
  }
  return `
    <div class="latest-budget-selection-grid">
      ${selected.map((pick, index) => {
        const reasons = Array.isArray(pick.score_reasons) && pick.score_reasons.length
          ? `<div class="latest-budget-pick-reasons">${escapeHtml(pick.score_reasons.join(' · '))}</div>`
          : '';
        const replacementBadge = pick.replacement_preview
          ? `<span class="latest-budget-preview-badge">Reemplazo de ${escapeHtml(pick.replacement_source_name || 'otro juego')}</span>`
          : '';
        return `
          <div class="latest-budget-pick-card">
            <div class="latest-budget-pick-head">
              <div>
                <div class="latest-budget-pick-index">Juego ${index + 1}</div>
                <div class="latest-budget-pick-name">${escapeHtml(pick.name || '')}</div>
              </div>
              ${replacementBadge}
            </div>
            <div class="latest-budget-pick-meta">${escapeHtml(pick.price_final || '—')} · Score ${escapeHtml(pick.score || '—')} · -${escapeHtml(pick.discount || 0)}%</div>
            <div class="latest-budget-pick-recommendation">${escapeHtml(pick.recommendation || 'Selección del modo presupuesto')}</div>
            ${reasons}
            ${renderLatestOfferHighlight(pick, report)}
            <div class="latest-budget-pick-actions">
              <button type="button" class="btn btn-ghost latest-budget-inline-btn" data-share-budget-pick="${escapeHtml(pick.appid || '')}">Compartir</button>
            </div>
            ${renderLatestBudgetReplacementOptions(pick, preview)}
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderLatestShareTopPicks(report) {
  const topPicks = Array.isArray(report && report.top_picks) ? report.top_picks.slice(0, 4) : [];
  if (!topPicks.length) return '';
  const accessNotesByAppid = latestWishlistAccessNotesByAppid(report);
  const cards = topPicks.map((pick) => {
    const shareGame = buildShareGamePayload(pick, report);
    if (!shareGame) return '';
    const highlightHtml = renderLatestOfferHighlight(pick, report);
    const accessNoteHtml = renderLatestTopPickAccessNote(pick, accessNotesByAppid);
    const minHistText = shareGame.displayMinHist
      ? `Mín. histórico: ${shareGame.displayMinHist}`
      : 'Sin mínimo histórico en este reporte';
    return `
      <div class="latest-share-card">
        <div class="latest-share-card-title">${escapeHtml(shareGame.name)}</div>
        <div class="latest-share-card-price">${escapeHtml(shareGame.displayPrice)}${shareGame.discount ? ` · -${escapeHtml(shareGame.discount)}%` : ''}</div>
        <div class="latest-share-card-meta">${escapeHtml(minHistText)}</div>
        ${highlightHtml}
        ${accessNoteHtml}
        <div class="latest-share-card-actions">
          <button type="button" class="btn btn-ghost latest-share-trigger" data-share-top-pick="${escapeHtml(shareGame.appid)}">Compartir</button>
          <a class="file-link latest-share-open-link" href="${escapeHtml(shareGame.steamUrl)}" target="_blank" rel="noopener noreferrer">Abrir en Steam</a>
        </div>
      </div>
    `;
  }).filter(Boolean).join('');
  if (!cards) return '';
  return `
    <div class="latest-share-section">
      <div class="latest-share-section-title">Compartir juegos destacados</div>
      <div class="latest-share-section-subtitle">Abre el modal desde aquí para copiar el link <code>steamtools://share</code> o el link de Steam con la información del reporte más reciente.</div>
      <div class="latest-share-grid">${cards}</div>
    </div>
  `;
}

function latestRecommendedCollectionItemKey(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  if (appid) return `appid:${appid}`;
  const name = String(source.name || source.steam_name || '').trim().toLowerCase();
  return name ? `name:${name}` : '';
}

function latestSteamStoreUrl(appid) {
  return `https://store.steampowered.com/app/${escapeHtml(appid)}/`;
}

function latestSteamCapsuleUrl(appid) {
  return `https://cdn.akamai.steamstatic.com/steam/apps/${escapeHtml(appid)}/capsule_231x87.jpg`;
}

const SCORE_DISCOVERY_FALLBACK_REASON = 'sin señal personal suficiente; aparece por score del reporte';
const PERSONALIZED_REASON_FALLBACK = 'señal personal positiva del reporte';

function latestIsScoreDiscoveryReason(reason) {
  const normalized = String(reason || '').trim().toLowerCase();
  return normalized === 'score base del reporte' || normalized === SCORE_DISCOVERY_FALLBACK_REASON;
}

function latestPersonalizedSignalReasons(item) {
  const source = item && typeof item === 'object' ? item : {};
  const reasons = Array.isArray(source.reasons) ? source.reasons : [];
  return reasons
    .map(reason => String(reason || '').trim())
    .filter(reason => reason && !latestIsScoreDiscoveryReason(reason));
}

function latestHasPositiveAffinity(item) {
  const source = item && typeof item === 'object' ? item : {};
  const affinity = Number(source.affinity_score);
  return Number.isFinite(affinity) && affinity > 0;
}

function latestHasPersonalizedSignal(item) {
  return latestHasPositiveAffinity(item) || latestPersonalizedSignalReasons(item).length > 0;
}

function latestVisiblePersonalizedItems(items) {
  return (Array.isArray(items) ? items : [])
    .filter(item => item && typeof item === 'object' && latestHasPersonalizedSignal(item));
}

function renderLatestRecommendedCollectionItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = source.name || source.steam_name || 'Juego desconocido';
  const reason = source.reason || 'Destacado por señales del último reporte.';
  const score = source.score;
  const discount = Number(source.discount || 0) || 0;
  const price = source.price_final || source.price || '';
  const meta = [];
  if (score !== null && score !== undefined && score !== '') meta.push(`Score ${score}`);
  if (discount > 0) meta.push(`-${discount}%`);
  if (price) meta.push(price);
  const nameHtml = safeAppid
    ? `<a href="${latestSteamStoreUrl(safeAppid)}" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  const thumbHtml = safeAppid
    ? `<a class="latest-game-thumb latest-collection-item-thumb" href="${latestSteamStoreUrl(safeAppid)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir ${escapeHtml(name)} en Steam"><img src="${latestSteamCapsuleUrl(safeAppid)}" alt="" loading="lazy" onerror="this.style.display='none'"></a>`
    : '';
  return `
    <li class="latest-collection-item">
      ${thumbHtml}
      <div class="latest-collection-item-main">
        <strong>${nameHtml}</strong>
        <span>${escapeHtml(reason)}</span>
      </div>
      ${meta.length ? `<div class="latest-collection-item-meta">${escapeHtml(meta.join(' · '))}</div>` : ''}
    </li>
  `;
}

function renderLatestRecommendedCollections(report) {
  const collections = Array.isArray(report && report.recommended_collections)
    ? report.recommended_collections
    : [];
  if (!collections.length) return '';
  const seenItemKeys = new Set();
  const cards = collections.slice(0, 4).map((collection) => {
    const source = collection && typeof collection === 'object' ? collection : {};
    const items = Array.isArray(source.items) ? source.items.filter(item => item && typeof item === 'object') : [];
    const visibleItems = [];
    items.forEach((item) => {
      const itemKey = latestRecommendedCollectionItemKey(item);
      if (itemKey && seenItemKeys.has(itemKey)) return;
      visibleItems.push(item);
    });
    const selectedItems = visibleItems.slice(0, 3);
    selectedItems.forEach((item) => {
      const itemKey = latestRecommendedCollectionItemKey(item);
      if (itemKey) seenItemKeys.add(itemKey);
    });
    if (!selectedItems.length) return '';
    const title = source.title || source.label || 'Colección';
    const description = source.description || 'Señales agrupadas desde el último reporte.';
    const hiddenCount = Math.max(0, visibleItems.length - selectedItems.length);
    return `
      <article class="latest-collection-card" data-latest-recommended-collection="${escapeHtml(source.id || 'collection')}">
        <h4>${escapeHtml(title)}</h4>
        <p>${escapeHtml(description)}</p>
        <ol>${selectedItems.map(renderLatestRecommendedCollectionItem).join('')}</ol>
        ${hiddenCount ? `<div class="latest-collection-more">${escapeHtml(hiddenCount)} más en el reporte interactivo</div>` : ''}
      </article>
    `;
  }).filter(Boolean).join('');
  if (!cards) return '';
  return `
    <div class="latest-collections-section" data-latest-recommended-collections>
      <div class="latest-collections-head">
        <div class="latest-collections-title">Colecciones destacadas</div>
        <div class="latest-collections-subtitle">Atajos discovery/oferta desde el último reporte: score, ahorro, Steam Deck, reviews y géneros disponibles.</div>
      </div>
      <div class="latest-collections-grid">${cards}</div>
    </div>
  `;
}

function renderLatestPersonalizedRecommendationItem(item, index, report = null, behavioralExplanation = null) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = source.name || source.steam_name || 'Juego desconocido';
  const reasons = latestPersonalizedSignalReasons(source).slice(0, 2);
  const meta = [];
  if (Number.isFinite(Number(source.personalized_score))) meta.push(`Personal ${source.personalized_score}`);
  if (Number.isFinite(Number(source.affinity_score))) meta.push(`Afinidad +${source.affinity_score}`);
  const discount = Number(source.discount || 0) || 0;
  if (discount > 0) meta.push(`-${discount}%`);
  const price = source.price_final || source.price || '';
  if (price) meta.push(price);
  const nameHtml = safeAppid
    ? `<a href="${latestSteamStoreUrl(safeAppid)}" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  const thumbHtml = safeAppid
    ? `<a class="latest-game-thumb latest-personalized-item-thumb" href="${latestSteamStoreUrl(safeAppid)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir ${escapeHtml(name)} en Steam"><img src="${latestSteamCapsuleUrl(safeAppid)}" alt="" loading="lazy" onerror="this.style.display='none'"></a>`
    : '';
  return `
    <li class="latest-personalized-item"${safeAppid ? ` data-latest-personalized-recommendation="${escapeHtml(safeAppid)}"` : ''}>
      <div class="latest-personalized-item-rank">#${escapeHtml(index)}</div>
      ${thumbHtml}
      <div class="latest-personalized-item-main">
        <strong>${nameHtml}</strong>
        ${meta.length ? `<span class="latest-personalized-item-meta">${escapeHtml(meta.join(' · '))}</span>` : ''}
        <span class="latest-personalized-item-reasons">${escapeHtml((reasons.length ? reasons : [PERSONALIZED_REASON_FALLBACK]).join(' · '))}</span>
        ${renderLatestOfferHighlight(source, report)}
        ${renderLatestPersonalizedBehavioralExplanation(behavioralExplanation)}
      </div>
    </li>
  `;
}

function latestBehavioralExplanationAppid(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  return /^\d+$/.test(appid) ? appid : '';
}

function latestBehavioralExplanationsByAppid(report) {
  const payload = report && typeof report === 'object' ? report.behavioral_explanations : null;
  if (!payload || typeof payload !== 'object' || payload.schema !== 'behavioral_explanations_v1') return new Map();
  const items = Array.isArray(payload.items) ? payload.items : [];
  const byAppid = new Map();
  items.forEach((item) => {
    if (!item || typeof item !== 'object') return;
    const appid = latestBehavioralExplanationAppid(item);
    if (appid && !byAppid.has(appid)) byAppid.set(appid, item);
  });
  return byAppid;
}

function latestBehavioralCueKindLabel(kind) {
  const normalizedKind = String(kind || '').trim().toLowerCase();
  if (normalizedKind === 'family') return 'Patrón principal';
  if (normalizedKind === 'behavioral_loop') return 'Loop de juego';
  if (normalizedKind === 'descriptor') return 'Contexto de decisión';
  return 'Señal behavioral';
}

function latestBehavioralCueKindHelp(kind) {
  const normalizedKind = String(kind || '').trim().toLowerCase();
  if (normalizedKind === 'family') return 'familia amplia del tipo de experiencia que ofrece el juego.';
  if (normalizedKind === 'behavioral_loop') return 'forma recurrente de jugar o engancharse que la taxonomía detectó.';
  if (normalizedKind === 'descriptor') return 'contexto práctico como duración, presión, online/social o fricción.';
  return 'pista derivada de la taxonomía local del juego.';
}

function latestBehavioralCueTooltip(cue) {
  const source = cue && typeof cue === 'object' ? cue : {};
  const label = String(source.label || '').trim() || 'Señal behavioral';
  const kindLabel = latestBehavioralCueKindLabel(source.kind);
  const kindHelp = latestBehavioralCueKindHelp(source.kind);
  return `${kindLabel}: ${label}. Es ${kindHelp} Sale de tags/géneros del juego y no cambia score ni ranking.`;
}

function renderLatestPersonalizedBehavioralExplanation(explanation) {
  const source = explanation && typeof explanation === 'object' ? explanation : null;
  if (!source) return '';
  const confidence = String(source.confidence || '').trim().toLowerCase();
  const title = ['medium', 'high'].includes(confidence) ? 'Por qué podría gustarte' : 'Señales de estilo del juego';
  const headline = String(source.headline || '').trim();
  const reasons = Array.isArray(source.reasons)
    ? source.reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 2)
    : [];
  const cues = Array.isArray(source.supporting_cues)
    ? source.supporting_cues
      .filter(cue => cue && typeof cue === 'object')
      .map(cue => ({
        label: String(cue.label || '').trim(),
        tooltip: latestBehavioralCueTooltip(cue),
      }))
      .filter(cue => cue.label)
      .filter(Boolean)
      .slice(0, 3)
    : [];
  if (!headline && !reasons.length && !cues.length) return '';
  return `
    <div class="latest-personalized-behavioral-note" data-latest-personalized-behavioral-explanation>
      <strong>${escapeHtml(title)}</strong>
      <span class="latest-personalized-behavioral-help" data-latest-personalized-behavioral-help>¿Por qué está aquí? Son patrones de la taxonomía local activados por tags/géneros del juego; sirven para explicar estilo, no para predecir precio ni cambiar ranking.</span>
      ${headline ? `<span class="latest-personalized-behavioral-headline">${escapeHtml(headline)}</span>` : ''}
      ${reasons.length ? `<ul>${reasons.map(reason => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>` : ''}
      ${cues.length ? `<div class="latest-personalized-behavioral-cues">${cues.map(cue => `<span tabindex="0" title="${escapeHtml(cue.tooltip)}" aria-label="${escapeHtml(cue.tooltip)}">${escapeHtml(cue.label)}</span>`).join('')}</div>` : ''}
      <small>Señal advisory: no cambia score ni ranking.</small>
    </div>
  `;
}

function renderLatestPersonalizedProfile(profile) {
  const source = profile && typeof profile === 'object' ? profile : {};
  const librarySummary = source.library_summary && typeof source.library_summary === 'object'
    ? source.library_summary
    : {};
  const activitySummary = source.activity_summary && typeof source.activity_summary === 'object'
    ? source.activity_summary
    : {};
  const activityTerms = Array.isArray(source.activity_terms)
    ? source.activity_terms.map(term => term && term.term).filter(Boolean).slice(0, 2)
    : [];
  const libraryTerms = Array.isArray(librarySummary.top_terms)
    ? librarySummary.top_terms.map(term => term && term.term).filter(Boolean).slice(0, 2)
    : [];
  const chips = [];
  if (activityTerms.length) chips.push(`Actividad: ${activityTerms.join(', ')}`);
  chips.push(...latestActivitySummaryChips(activitySummary));
  if (libraryTerms.length) chips.push(`Biblioteca: ${libraryTerms.join(', ')}`);
  if (Number(librarySummary.total_hltb_hours) > 0) chips.push(`HLTB: ${librarySummary.total_hltb_hours}h`);
  if (Number.isFinite(Number(librarySummary.average_price))) chips.push(`Precio prom.: $${librarySummary.average_price}`);
  if (!chips.length) return '';
  return `<div class="latest-personalized-profile">${chips.map(chip => `<span>${escapeHtml(chip)}</span>`).join('')}</div>`;
}

function positiveActivityNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function latestActivitySummaryChips(summary) {
  const source = summary && typeof summary === 'object' ? summary : {};
  const chips = [];
  const recentHours = positiveActivityNumber(source.recent_hours);
  const totalHours = positiveActivityNumber(source.total_hours);
  if (recentHours || totalHours) {
    const hoursParts = [];
    if (recentHours) hoursParts.push(`${recentHours.toFixed(1)}h recientes`);
    if (totalHours) hoursParts.push(`${totalHours.toFixed(1)}h total`);
    chips.push(`Actividad local: ${hoursParts.join(' · ')}`);
  }
  const topPlayed = Array.isArray(source.top_played) ? source.top_played : [];
  const topItem = topPlayed.find(item => item && typeof item === 'object' && String(item.name || '').trim());
  const topHours = topItem ? positiveActivityNumber(topItem.total_hours) : null;
  if (topItem && topHours) chips.push(`Más jugado: ${String(topItem.name).trim()} (${topHours.toFixed(1)}h)`);
  return chips;
}

function renderLatestPersonalizedRecommendations(report, files = null) {
  const payload = report && typeof report === 'object' ? (report.personalized_recommendations || null) : null;
  const items = latestVisiblePersonalizedItems(payload && payload.items);
  if (!items.length) return '';
  const selectedItems = items.slice(0, 3);
  const explanationsByAppid = latestBehavioralExplanationsByAppid(report);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  const htmlName = findLatestPrimaryHtmlReport(files);
  const htmlLink = htmlName
    ? `<a class="file-link latest-personalized-detail-link" href="${generatedFileHref(htmlName)}" target="_blank" rel="noopener noreferrer">Ver detalle HTML</a>`
    : '';
  return `
    <div class="latest-personalized-section" data-latest-personalized-recommendations>
      <div class="latest-personalized-head">
        <div class="latest-personalized-title">Recomendaciones personalizadas</div>
        <div class="latest-personalized-subtitle">Hasta 3 juegos con señales personales reales. Abre el HTML o JSON para revisar el detalle completo.</div>
      </div>
      ${renderLatestPersonalizedProfile(payload.profile || {})}
      <ol class="latest-personalized-list">
        ${selectedItems.map((item, index) => renderLatestPersonalizedRecommendationItem(item, index + 1, report, explanationsByAppid.get(latestBehavioralExplanationAppid(item)))).join('')}
      </ol>
      <div class="latest-personalized-footer">
        ${htmlLink}
        <a class="file-link latest-personalized-detail-link" href="${latestReportUrl()}" target="_blank" rel="noopener noreferrer">Ver JSON completo</a>
        ${hiddenCount ? `<span class="latest-personalized-more">${escapeHtml(hiddenCount)} más en el reporte completo</span>` : ''}
      </div>
    </div>
  `;
}

function latestGiftIdeaReasons(item) {
  const source = item && typeof item === 'object' ? item : {};
  const reasons = Array.isArray(source.social_reasons)
    ? source.social_reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 2)
    : [];
  return reasons.length ? reasons : ['lo tiene en wishlist y está en oferta'];
}

function renderLatestGiftIdeaItem(item, index) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = source.name || source.steam_name || 'Juego desconocido';
  const meta = [];
  const discount = Number(source.discount || 0) || 0;
  if (discount > 0) meta.push(`-${discount}%`);
  const price = source.price_final || source.price || '';
  if (price) meta.push(price);
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return `
    <li class="latest-gift-item"${safeAppid ? ` data-latest-gift-idea="${escapeHtml(safeAppid)}"` : ''}>
      <div class="latest-gift-item-rank">#${escapeHtml(index)}</div>
      <div class="latest-gift-item-main">
        <strong>${nameHtml}</strong>
        ${meta.length ? `<span class="latest-gift-item-meta">${escapeHtml(meta.join(' · '))}</span>` : ''}
        <span class="latest-gift-item-reasons">${escapeHtml(latestGiftIdeaReasons(source).join(' · '))}</span>
      </div>
    </li>
  `;
}

function latestGiftItems(value) {
  return Array.isArray(value) ? value.filter(item => item && typeof item === 'object') : [];
}

function renderLatestGiftGroup(title, items, options = {}) {
  const visibleItems = latestGiftItems(items).slice(0, options.limit || 3);
  if (!visibleItems.length) return '';
  const hiddenCount = Math.max(0, latestGiftItems(items).length - visibleItems.length);
  return `
    <div class="latest-gift-group"${options.shared ? ' data-latest-shared-gift-ideas' : ' data-latest-gift-group'}>
      <div class="latest-gift-group-title">${escapeHtml(title)}</div>
      <ol class="latest-gift-list">
        ${visibleItems.map((item, index) => renderLatestGiftIdeaItem(item, index + 1)).join('')}
      </ol>
      ${hiddenCount ? `<div class="latest-gift-more">${escapeHtml(hiddenCount)} más en el reporte completo</div>` : ''}
    </div>
  `;
}

function renderLatestGiftIdeas(report) {
  const sharedItems = latestGiftItems(report && report.shared_gift_ideas);
  const friendGroups = Array.isArray(report && report.gift_ideas_by_friend)
    ? report.gift_ideas_by_friend.filter(group => group && typeof group === 'object' && latestGiftItems(group.items).length)
    : [];
  const items = latestGiftItems(report && report.gift_ideas);
  if (!items.length && !sharedItems.length && !friendGroups.length) return '';
  const compareData = report && typeof report === 'object' ? (report.compare_data || {}) : {};
  const friend = String((compareData && (compareData.friend_name || compareData.friend_vanity)) || '').trim();
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  const friendCopy = friend ? ` para ${friend}` : '';
  const multiProfileHtml = [
    renderLatestGiftGroup('Ideas compartidas', sharedItems, {shared: true, limit: 3}),
    ...friendGroups.slice(0, 3).map(group => {
      const label = String(group.friend_label || group.friend_key || 'amigo').trim();
      return renderLatestGiftGroup(`Ideas para ${label}`, group.items, {limit: 2});
    }),
  ].join('');
  return `
    <div class="latest-gift-section" data-latest-gift-ideas>
      <div class="latest-gift-head">
        <div class="latest-gift-title">${multiProfileHtml ? 'Regalos grupales' : `Regalos${escapeHtml(friendCopy)}`}</div>
        <div class="latest-gift-subtitle">Hasta 3 ideas desde la wishlist comparada, con razones sociales compactas. No abre carrito ni compra nada.</div>
      </div>
      ${multiProfileHtml || `<ol class="latest-gift-list">
        ${selectedItems.map((item, index) => renderLatestGiftIdeaItem(item, index + 1)).join('')}
      </ol>${hiddenCount ? `<div class="latest-gift-more">${escapeHtml(hiddenCount)} más en el reporte completo</div>` : ''}`}
    </div>
  `;
}


function latestWishlistHygieneSignalLabel(signal) {
  const labels = {
    owned: 'Ya lo tienes',
    family: 'Disponible por Steam Family',
    probable_family_shared: 'Probable acceso local',
    playable_without_buying: 'Jugable sin compra local',
    library_match: 'Match biblioteca local',
    hltb_match: 'HLTB local',
    other_store: 'Otra tienda',
    catalog_removed: 'Retirado del catálogo',
    catalog_missing: 'No está en catálogo local',
    invalid_appid: 'AppID inválido',
  };
  const key = String(signal || '').trim();
  return labels[key] || key.replace(/_/g, ' ');
}

function latestWishlistAccessDecisionDetail(code) {
  const details = {
    owned: 'Comprar solo si quieres otra copia o soporte adicional.',
    family: 'Comprar solo si quieres copia propia.',
    probable_family_shared: 'Revisa el acceso local antes de comprar.',
    playable_without_buying: 'Revisa el acceso local antes de comprar.',
  };
  return details[String(code || '').trim()] || '';
}

function latestExplicitWishlistAccessDecision(item) {
  const source = item && typeof item === 'object' ? item : {};
  const explicit = source.access_decision && typeof source.access_decision === 'object'
    ? source.access_decision
    : null;
  if (!explicit) return null;
  const code = String(explicit.code || '').trim();
  const label = String(explicit.label || '').trim();
  const rankingImpact = String(explicit.ranking_impact || 'none').trim().toLowerCase();
  if (!code || !label || explicit.advisory_only === false || rankingImpact !== 'none') return null;
  return {
    code,
    label,
    detail: String(explicit.detail || latestWishlistAccessDecisionDetail(code)).trim(),
  };
}

function latestWishlistAccessNotesByAppid(report) {
  const payload = report && typeof report === 'object' ? report.wishlist_hygiene : null;
  const items = Array.isArray(payload && payload.items) ? payload.items : [];
  return items.reduce((notes, item) => {
    const source = item && typeof item === 'object' ? item : {};
    const appid = String(source.appid || source.steam_appid || '').trim();
    if (!/^\d+$/.test(appid) || notes[appid]) return notes;
    const decision = latestExplicitWishlistAccessDecision(source);
    if (decision) notes[appid] = decision;
    return notes;
  }, {});
}

function renderLatestTopPickAccessNote(pick, accessNotesByAppid) {
  const source = pick && typeof pick === 'object' ? pick : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const decision = /^\d+$/.test(appid) && accessNotesByAppid
    ? accessNotesByAppid[appid]
    : null;
  if (!decision) return '';
  const detail = decision.detail || 'Revisa el acceso local antes de comprar.';
  return `
    <div class="latest-share-access-note" data-latest-top-pick-access-note="${escapeHtml(appid)}">
      <span class="latest-share-access-note-label">Acceso: ${escapeHtml(decision.label)}</span>
      <span class="latest-share-access-note-detail">${escapeHtml(detail)}</span>
      <span class="latest-share-access-note-guardrail">Solo revisión · advisory-only: no cambia score, ranking, orden, defaults, cache ni fetching.</span>
    </div>
  `;
}

function latestWishlistAccessDecision(item) {
  const source = item && typeof item === 'object' ? item : {};
  const explicit = source.access_decision && typeof source.access_decision === 'object'
    ? source.access_decision
    : null;
  if (explicit) {
    const code = String(explicit.code || '').trim();
    const label = String(explicit.label || '').trim();
    if (code && label) {
      return {
        code,
        label,
        detail: String(explicit.detail || latestWishlistAccessDecisionDetail(code)).trim(),
      };
    }
  }
  const signals = Array.isArray(source.signals)
    ? source.signals.map(signal => String(signal || '').trim()).filter(Boolean)
    : [];
  const priority = ['owned', 'family', 'probable_family_shared', 'playable_without_buying'];
  const code = priority.find(signal => signals.includes(signal)) || '';
  if (!code) return null;
  return {
    code,
    label: latestWishlistHygieneSignalLabel(code),
    detail: latestWishlistAccessDecisionDetail(code),
  };
}

function latestWishlistHygieneCounts(payload, items) {
  const summary = payload && typeof payload === 'object' && payload.summary && typeof payload.summary === 'object'
    ? payload.summary
    : {};
  const reviewItems = latestCoverageCount(summary.review_items_count) || (Array.isArray(items) ? items.length : 0);
  const totalWishlistItems = latestCoverageCount(summary.total_wishlist_items);
  return { reviewItems, totalWishlistItems };
}

function latestWishlistHygieneCountLabel(payload, items) {
  const { reviewItems, totalWishlistItems } = latestWishlistHygieneCounts(payload, items);
  const formattedReviewItems = formatLatestCoverageCount(reviewItems);
  const baseCopy = reviewItems === 1
    ? `${formattedReviewItems} sugerencia para revisar`
    : `${formattedReviewItems} sugerencias para revisar`;
  if (totalWishlistItems > 0) {
    return `${baseCopy} de ${formatLatestCoverageCount(totalWishlistItems)} juegos en wishlist`;
  }
  return `${baseCopy} en la wishlist`;
}

function renderLatestWishlistHygieneItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const rawName = String(source.name || source.steam_name || '').trim();
  const isAppidOnly = Boolean(appid && (source.missing_local_name === true || !rawName));
  const name = rawName || (appid ? `AppID ${appid}` : 'Entrada sin appid');
  const reasons = Array.isArray(source.reasons)
    ? source.reasons.map(reason => String(reason || '').trim()).filter(Boolean).slice(0, 2)
    : [];
  const missingNameReason = 'No tenemos nombre local para este AppID; revisa si quieres mantenerlo en wishlist';
  if (isAppidOnly && !reasons.some(reason => reason.includes('No tenemos nombre local'))) {
    reasons.unshift(missingNameReason);
  }
  const visibleReasons = reasons.slice(0, 2);
  const signals = Array.isArray(source.signals)
    ? source.signals.map(latestWishlistHygieneSignalLabel).filter(Boolean).slice(0, 3)
    : [];
  const accessDecision = latestWishlistAccessDecision(source);
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  const steamLinkHtml = safeAppid
    ? `<a class="latest-wishlist-steam-link" href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">Abrir en Steam</a>`
    : '';
  const appidMeta = safeAppid ? `AppID ${safeAppid}` : 'Sin AppID numérico seguro';
  const placeholderText = safeAppid ? 'ID' : 'REV';
  return `
    <li class="latest-wishlist-item"${safeAppid ? ` data-latest-wishlist-hygiene-item="${escapeHtml(safeAppid)}"` : ''}>
      <div class="latest-wishlist-item-placeholder" aria-hidden="true">${escapeHtml(placeholderText)}</div>
      <div class="latest-wishlist-item-main">
        <div class="latest-wishlist-item-heading">
          <strong class="latest-wishlist-item-name">${nameHtml}</strong>
          <span class="latest-wishlist-item-badge">Solo revisión</span>
        </div>
        <span class="latest-wishlist-item-meta">${escapeHtml(appidMeta)}</span>
        ${signals.length ? `<span class="latest-wishlist-item-signals">${signals.map(signal => `<em>${escapeHtml(signal)}</em>`).join('')}</span>` : ''}
        ${accessDecision ? `<span class="latest-wishlist-access-decision"><strong>${escapeHtml(accessDecision.label)}:</strong> ${escapeHtml(accessDecision.detail)}</span>` : ''}
        <span class="latest-wishlist-item-reason-label">Razón para revisar</span>
        <span class="latest-wishlist-item-reasons">${escapeHtml((visibleReasons.length ? visibleReasons : ['revisar manualmente antes de limpiar']).join(' · '))}</span>
        <div class="latest-wishlist-item-actions">
          ${steamLinkHtml || '<span class="latest-wishlist-steam-note">Sin link Steam seguro</span>'}
        </div>
      </div>
    </li>
  `;
}

function renderLatestWishlistHygiene(report) {
  const payload = report && typeof report === 'object' ? (report.wishlist_hygiene || null) : null;
  const items = Array.isArray(payload && payload.items)
    ? payload.items.filter(item => item && typeof item === 'object')
    : [];
  if (!items.length) return '';
  const selectedItems = items.slice(0, 3);
  const hiddenCount = Math.max(0, items.length - selectedItems.length);
  const countLabel = latestWishlistHygieneCountLabel(payload, items);
  const visibleCopy = hiddenCount
    ? `Mostramos ${formatLatestCoverageCount(selectedItems.length)} aquí; ${formatLatestCoverageCount(hiddenCount)} más en el JSON completo.`
    : `Mostramos ${formatLatestCoverageCount(selectedItems.length)} aquí; el JSON completo mantiene el contexto.`;
  return `
    <div class="latest-wishlist-section" data-latest-wishlist-hygiene>
      <div class="latest-wishlist-head">
        <div class="latest-wishlist-heading-copy">
          <div class="latest-wishlist-eyebrow">Higiene local</div>
          <div class="latest-wishlist-title-row">
            <div class="latest-wishlist-title">Revisar wishlist</div>
            <span class="latest-wishlist-badge">Solo revisión</span>
          </div>
          <div class="latest-wishlist-count">${escapeHtml(countLabel)}</div>
          <div class="latest-wishlist-subtitle">Advisory-only: No borra ni auto-excluye juegos, y no cambia el score. Las señales de acceso pueden indicar Ya lo tienes, Disponible por Steam Family o Probable acceso local.</div>
        </div>
      </div>
      <ol class="latest-wishlist-list">
        ${selectedItems.map(renderLatestWishlistHygieneItem).join('')}
      </ol>
      <div class="latest-wishlist-more">${escapeHtml(visibleCopy)}</div>
    </div>
  `;
}


function latestSelectionCandidateKey(item) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  return /^\d+$/.test(appid) ? appid : '';
}

function latestSelectionCandidate(item, sourceLabel) {
  const source = item && typeof item === 'object' ? item : {};
  const appid = latestSelectionCandidateKey(source);
  if (!appid) return null;
  const meta = [];
  if (Number.isFinite(Number(source.personalized_score))) meta.push(`Personal ${source.personalized_score}`);
  if (Number.isFinite(Number(source.score ?? source.base_score))) meta.push(`Score ${source.score ?? source.base_score}`);
  if (Number.isFinite(Number(source.affinity_score))) meta.push(`Afinidad +${source.affinity_score}`);
  const discount = Number(source.discount || 0) || 0;
  if (discount > 0) meta.push(`-${discount}%`);
  return {
    appid,
    name: source.name || source.steam_name || `App ${appid}`,
    sourceLabel,
    meta: meta.join(' · '),
  };
}

function latestSelectionCollectionItems(report) {
  const collections = Array.isArray(report && report.recommended_collections)
    ? report.recommended_collections
    : [];
  const items = [];
  collections.forEach((collection) => {
    const source = collection && typeof collection === 'object' ? collection : {};
    (Array.isArray(source.items) ? source.items : []).forEach((item) => {
      if (item && typeof item === 'object') items.push(item);
    });
  });
  return items;
}

function buildLatestSelectionCandidates(report) {
  const candidates = [];
  const seen = new Set();
  const addCandidates = (items, sourceLabel, limit) => {
    (Array.isArray(items) ? items : []).slice(0, limit).forEach((item) => {
      const candidate = latestSelectionCandidate(item, sourceLabel);
      if (!candidate || seen.has(candidate.appid)) return;
      seen.add(candidate.appid);
      candidates.push(candidate);
    });
  };
  const personalized = report && report.personalized_recommendations;
  addCandidates(latestVisiblePersonalizedItems(personalized && personalized.items), 'Personalizado', 4);
  addCandidates(report && report.top_picks, 'Top Picks', 6);
  addCandidates(latestSelectionCollectionItems(report), 'Colección', 6);
  addCandidates(report && report.deals, 'Oferta', 8);
  return candidates.slice(0, 8);
}

function renderLatestSelectionCandidate(candidate) {
  return `
    <label class="latest-selection-candidate">
      <input type="checkbox" data-selection-candidate="${escapeHtml(candidate.appid)}" data-selection-name="${escapeHtml(candidate.name)}">
      <span>
        <strong>${escapeHtml(candidate.name)}</strong>
        <small>${escapeHtml([candidate.sourceLabel, candidate.meta].filter(Boolean).join(' · '))}</small>
      </span>
    </label>
  `;
}

function renderLatestSelectionReviewPanel(report) {
  const candidates = buildLatestSelectionCandidates(report);
  const candidateList = candidates.length
    ? `<div class="latest-selection-candidates">${candidates.map(renderLatestSelectionCandidate).join('')}</div>`
    : '<div class="latest-selection-empty">No hay candidatos marcables en el último reporte; pega AppIDs o URLs de Steam.</div>';
  return `
    <div class="latest-selection-section" data-latest-selection-review>
      <div class="latest-selection-head">
        <div class="latest-selection-title">Evalúa mi selección</div>
        <div class="latest-selection-subtitle">Simulador local: marca juegos o pega AppIDs/URLs para recibir conservar, dudar o quitar. No abre carrito ni compra nada.</div>
      </div>
      ${candidateList}
      <textarea class="latest-selection-input" rows="3" data-selection-input placeholder="Pega AppIDs o URLs de Steam, uno por línea"></textarea>
      <div class="latest-selection-actions">
        <button type="button" class="btn btn-ghost latest-selection-evaluate" data-selection-evaluate>Evaluar selección</button>
        <span class="latest-selection-status" data-selection-status>Usa datos del último JSON local.</span>
      </div>
      <div class="latest-selection-results" data-selection-results></div>
    </div>
  `;
}

function renderLatestSelectionReviewTools(report) {
  const panel = renderLatestSelectionReviewPanel(report);
  if (!panel) return '';
  return `
    <section class="latest-selection-tools" data-latest-selection-tools aria-label="Herramienta Evalúa mi selección">
      <div class="latest-selection-tools-head">
        <div>
          <div class="latest-selection-tools-eyebrow">Herramienta local</div>
          <div class="latest-selection-tools-title">Evalúa mi selección</div>
          <div class="latest-selection-tools-copy">Separado del resumen para comparar picks sin llenar el desplegable de acciones. Usa el último JSON local y no cambia tu wishlist.</div>
        </div>
        <div class="latest-selection-tools-tabs" role="toolbar" aria-label="Herramientas de recomendaciones">
          <button type="button" class="latest-selection-tools-tab is-active" aria-current="true">Evalúa mi selección</button>
        </div>
      </div>
      ${panel}
    </section>
  `;
}

function latestSelectionRecordsFromText(text) {
  const seen = new Set();
  const records = [];
  String(text || '').split(/\n+/).forEach((line) => {
    const match = String(line).match(/(?:store\.steampowered\.com\/app\/|\bapp\/)?(\d{1,12})(?!\d)/i);
    const appid = match ? match[1] : '';
    if (!appid || seen.has(appid)) return;
    seen.add(appid);
    records.push({appid});
  });
  return records;
}

function latestSelectionRecordsFromPanel(panel) {
  const seen = new Set();
  const records = [];
  panel.querySelectorAll('[data-selection-candidate]:checked').forEach((input) => {
    const appid = input.dataset.selectionCandidate || '';
    if (!appid || seen.has(appid)) return;
    seen.add(appid);
    records.push({appid, name: input.dataset.selectionName || ''});
  });
  latestSelectionRecordsFromText(panel.querySelector('[data-selection-input]')?.value || '').forEach((record) => {
    if (!record.appid || seen.has(record.appid)) return;
    seen.add(record.appid);
    records.push(record);
  });
  return records.slice(0, 50);
}

function latestSelectionSignalLabel(signal) {
  const labels = {
    invalid_appid: 'Entrada inválida',
    owned: 'Ya lo tienes',
    family: 'Biblioteca familiar',
    personalized_score: 'Score personal',
    affinity: 'Afinidad',
    report_score: 'Score reporte',
    discount: 'Descuento',
    price: 'Precio',
    reasons: 'Razones',
    recommended_collection: 'Colección recomendada',
    selection_only: 'Solo selección',
  };
  const key = String(signal || '').trim();
  return labels[key] || key.replace(/_/g, ' ');
}

function latestSelectionConfidenceLabel(confidence) {
  const labels = {high: 'Alta', medium: 'Media', low: 'Baja'};
  const key = String(confidence || '').trim().toLowerCase();
  return labels[key] || '';
}

function latestSelectionWhyItems(why, key) {
  if (!why || typeof why !== 'object') return [];
  return Array.isArray(why[key])
    ? why[key].map(item => String(item || '').trim()).filter(Boolean).slice(0, 3)
    : [];
}

function renderLatestSelectionWhyGroup(label, items, key) {
  if (!items.length) return '';
  return `
    <span class="latest-selection-result-why-group" data-selection-why="${escapeHtml(key)}">
      <strong>${escapeHtml(label)}:</strong> ${escapeHtml(items.join(' · '))}
    </span>
  `;
}

function renderLatestSelectionReviewItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const decision = ['conservar', 'dudar', 'quitar'].includes(source.decision) ? source.decision : 'dudar';
  const labels = {conservar: 'Conservar', dudar: 'Dudar', quitar: 'Quitar'};
  const appid = String(source.appid || '').trim();
  const safeAppid = /^\d+$/.test(appid) ? appid : '';
  const name = source.name || (appid ? `App ${appid}` : 'Entrada inválida');
  const reasons = Array.isArray(source.reasons) && source.reasons.length
    ? source.reasons.slice(0, 2).join(' · ')
    : 'Sin razones disponibles';
  const meta = [];
  if (Number.isFinite(Number(source.personalized_score))) meta.push(`Personal ${source.personalized_score}`);
  if (Number.isFinite(Number(source.base_score))) meta.push(`Score ${source.base_score}`);
  if (Number.isFinite(Number(source.affinity_score))) meta.push(`Afinidad +${source.affinity_score}`);
  if (Number.isFinite(Number(source.discount))) meta.push(`-${Math.round(Number(source.discount))}%`);
  if (source.price_final) meta.push(source.price_final);
  const signals = Array.isArray(source.signals)
    ? source.signals.map(latestSelectionSignalLabel).filter(Boolean).slice(0, 4)
    : [];
  const confidence = latestSelectionConfidenceLabel(source.confidence);
  const nextStep = String(source.next_step || '').trim();
  const whyGroups = [
    renderLatestSelectionWhyGroup('A favor', latestSelectionWhyItems(source.why, 'positive'), 'positive'),
    renderLatestSelectionWhyGroup('Cuidado', latestSelectionWhyItems(source.why, 'caution'), 'caution'),
    renderLatestSelectionWhyGroup('Contexto', latestSelectionWhyItems(source.why, 'context'), 'context'),
  ].filter(Boolean).join('');
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`
    : `<span>${escapeHtml(name)}</span>`;
  return `
    <article class="latest-selection-result latest-selection-result-${escapeHtml(decision)}" data-selection-decision="${escapeHtml(decision)}">
      <div class="latest-selection-result-badge">${escapeHtml(labels[decision])}</div>
      <div class="latest-selection-result-main">
        <strong>${nameHtml}</strong>
        ${meta.length ? `<span class="latest-selection-result-meta">${escapeHtml(meta.join(' · '))}</span>` : ''}
        ${confidence ? `<span class="latest-selection-result-confidence">Confianza: ${escapeHtml(confidence)}</span>` : ''}
        ${signals.length ? `<span class="latest-selection-result-signals">Señales: ${escapeHtml(signals.join(' · '))}</span>` : ''}
        <span class="latest-selection-result-reasons">${escapeHtml(reasons)}</span>
        ${nextStep ? `<span class="latest-selection-result-next-step"><strong>Siguiente paso:</strong> ${escapeHtml(nextStep)}</span>` : ''}
        ${whyGroups ? `<span class="latest-selection-result-why">${whyGroups}</span>` : ''}
      </div>
    </article>
  `;
}

function renderLatestSelectionReviewResults(panel, review) {
  const resultsEl = panel.querySelector('[data-selection-results]');
  if (!resultsEl) return;
  const items = Array.isArray(review && review.items) ? review.items : [];
  if (!items.length) {
    resultsEl.innerHTML = '<div class="latest-selection-empty">No hubo juegos válidos para evaluar.</div>';
    return;
  }
  const summary = review.summary || {};
  const duplicateCopy = summary.duplicate_count ? `<span>Duplicados omitidos: ${escapeHtml(summary.duplicate_count)}</span>` : '';
  resultsEl.innerHTML = `
    <div class="latest-selection-summary">
      <span>Conservar: ${escapeHtml(summary.conservar || 0)}</span>
      <span>Dudar: ${escapeHtml(summary.dudar || 0)}</span>
      <span>Quitar: ${escapeHtml(summary.quitar || 0)}</span>
      ${duplicateCopy}
    </div>
    <div class="latest-selection-result-list">${items.map(renderLatestSelectionReviewItem).join('')}</div>
  `;
}

async function evaluateLatestSelectionReview(panel, button) {
  const statusEl = panel.querySelector('[data-selection-status]');
  const records = latestSelectionRecordsFromPanel(panel);
  if (!records.length) {
    if (statusEl) statusEl.textContent = 'Marca al menos un juego o pega un AppID/URL.';
    return;
  }
  const originalLabel = button ? button.textContent : '';
  if (button) {
    button.disabled = true;
    button.textContent = 'Evaluando...';
  }
  if (statusEl) statusEl.textContent = `Evaluando ${records.length} juego(s) localmente...`;
  try {
    const resp = await localMutableFetch('/api/selection-review', {
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({selection: records}),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.message || 'No se pudo evaluar la selección.');
    renderLatestSelectionReviewResults(panel, data.review || {});
    const total = data.review && data.review.summary ? data.review.summary.total_items : records.length;
    if (statusEl) statusEl.textContent = `Evaluación local lista: ${total} juego(s).`;
  } catch (error) {
    if (statusEl) statusEl.textContent = error.message || 'No se pudo evaluar la selección.';
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel || 'Evaluar selección';
    }
  }
}

function bindLatestSelectionReviewActions() {
  const el = latestReportCardEl();
  if (!el) return;
  el.querySelectorAll('[data-latest-selection-review]').forEach((panel) => {
    const button = panel.querySelector('[data-selection-evaluate]');
    if (!button) return;
    button.addEventListener('click', () => evaluateLatestSelectionReview(panel, button));
  });
}

function renderLatestBudgetPanel(report) {
  const budgetResult = report && typeof report === 'object' ? (report.budget_result || null) : null;
  if (!budgetResult) return '';
  const preview = getActiveBudgetPreview();
  if (!preview) return '';
  return `
    <div class="latest-budget-panel">
      <div class="latest-budget-head">
        <div>
          <div class="latest-budget-title">Modo Presupuesto</div>
          <div class="latest-budget-subtitle">Techo activo del último run: ${escapeHtml(formatBudgetCurrency(preview.budget))}. Puedes alternar variantes o probar un reemplazo sin perder ese límite.</div>
        </div>
        <div class="latest-budget-current">${escapeHtml(preview.variant.label || 'Lista actual')}</div>
      </div>
      <div class="latest-budget-summary-grid">
        <div class="latest-budget-summary-item"><span>Total</span><strong>${escapeHtml(formatBudgetCurrency(preview.totalSpent))}</strong></div>
        <div class="latest-budget-summary-item"><span>Restante</span><strong>${escapeHtml(formatBudgetCurrency(preview.remaining))}</strong></div>
        <div class="latest-budget-summary-item"><span>Juegos</span><strong>${escapeHtml(preview.gamesCount)}</strong></div>
        <div class="latest-budget-summary-item"><span>Ahorro</span><strong>${escapeHtml(formatBudgetCurrency(preview.totalSavings))}</strong></div>
      </div>
      ${renderLatestBudgetVariantButtons(budgetResult, preview)}
      <div class="latest-budget-section">
        <div class="latest-budget-section-title">Selección activa</div>
        <div class="latest-budget-section-subtitle">Usa la variante actual como base y, si quieres, prueba un cambio puntual por juego.</div>
        ${renderLatestBudgetSelection(preview)}
      </div>
    </div>
  `;
}

function bindLatestBudgetActions() {
  const el = latestReportCardEl();
  if (!el || !latestBudgetUiState || !latestBudgetUiState.budgetResult) return;

  el.querySelectorAll('[data-budget-variant]').forEach((btn) => {
    btn.addEventListener('click', () => {
      latestBudgetUiState.selectedVariantId = btn.dataset.budgetVariant || '';
      latestBudgetUiState.openReplacementFor = '';
      latestBudgetUiState.appliedReplacement = null;
      renderLatestReportCard();
    });
  });

  el.querySelectorAll('[data-budget-toggle-replacement]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const sourceAppid = btn.dataset.budgetToggleReplacement || '';
      latestBudgetUiState.openReplacementFor = latestBudgetUiState.openReplacementFor === sourceAppid ? '' : sourceAppid;
      renderLatestReportCard();
    });
  });

  el.querySelectorAll('[data-budget-replacement-source]').forEach((btn) => {
    btn.addEventListener('click', () => {
      latestBudgetUiState.appliedReplacement = {
        variantId: latestBudgetUiState.selectedVariantId,
        sourceAppid: btn.dataset.budgetReplacementSource || '',
        candidateAppid: btn.dataset.budgetReplacementCandidate || '',
      };
      latestBudgetUiState.openReplacementFor = btn.dataset.budgetReplacementSource || '';
      renderLatestReportCard();
    });
  });

  el.querySelectorAll('[data-budget-reset-replacement]').forEach((btn) => {
    btn.addEventListener('click', () => {
      latestBudgetUiState.appliedReplacement = null;
      latestBudgetUiState.openReplacementFor = btn.dataset.budgetResetReplacement || '';
      renderLatestReportCard();
    });
  });
}

function bindLatestShareActions() {
  const el = latestReportCardEl();
  if (!el || !latestBudgetUiState || !latestBudgetUiState.report) return;
  const report = latestBudgetUiState.report;

  el.querySelectorAll('[data-share-top-pick]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const appid = btn.dataset.shareTopPick || '';
      const topPick = (Array.isArray(report.top_picks) ? report.top_picks : []).find(
        (item) => String((item && item.appid) || '') === appid,
      );
      openShareModal(topPick, report);
    });
  });

  el.querySelectorAll('[data-share-budget-pick]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const appid = btn.dataset.shareBudgetPick || '';
      const preview = getActiveBudgetPreview();
      const pick = preview && Array.isArray(preview.selected)
        ? preview.selected.find((item) => String((item && item.appid) || '') === appid)
        : null;
      openShareModal(pick, report);
    });
  });
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
  latestBudgetUiState = null;
  el.classList.add('hidden');
  el.innerHTML = '';
}

function findLatestShareHtmlReport(files) {
  return (Array.isArray(files) ? files : [])
    .map(getGeneratedFileName)
    .find(name => isShareHtmlFile(name));
}

function findLatestJsonReport(files) {
  return (Array.isArray(files) ? files : [])
    .map(getGeneratedFileName)
    .find(name => getGeneratedFileExtension(name) === '.json' && !isJsonExportFile(name));
}

function isOffersJsonExportFile(name) {
  return /^Steam Deals Offers \d{4}-\d{2}-\d{2}\.json$/.test(String(name || ''));
}

function isWishlistJsonExportFile(name) {
  return /^Steam Deals Wishlist \d{4}-\d{2}-\d{2}\.json$/.test(String(name || ''));
}

function isJsonExportFile(name) {
  return isOffersJsonExportFile(name) || isWishlistJsonExportFile(name);
}

function findLatestOffersJsonExport(files) {
  return (Array.isArray(files) ? files : [])
    .map(getGeneratedFileName)
    .find(name => isOffersJsonExportFile(name));
}

function findLatestWishlistJsonExport(files) {
  return (Array.isArray(files) ? files : [])
    .map(getGeneratedFileName)
    .find(name => isWishlistJsonExportFile(name));
}

function jsonExportCoverageCopy(report) {
  const coverage = report && typeof report === 'object' ? report.cache_coverage : null;
  const isPartial = coverage && typeof coverage === 'object' && (coverage.status === 'partial' || coverage.is_partial === true);
  if (isPartial) {
    return 'Cobertura parcial: exporta con la información disponible. Warm-cache puede mejorar cobertura, pero no es requisito para descargar.';
  }
  return 'Exporta con la cobertura disponible en este reporte. Si luego completas warm-cache, genera otro reporte para refrescar estos JSON.';
}

function renderJsonExportDownloadActions(files = null, report = null) {
  const offersName = findLatestOffersJsonExport(files);
  const wishlistName = findLatestWishlistJsonExport(files);
  if (!offersName && !wishlistName) return '';
  const offersAction = offersName ? `
    <a class="file-link latest-report-action latest-json-export-action" href="${generatedFileHref(offersName)}" download="${escapeHtml(offersName)}" title="Descarga solo las ofertas detectadas con la cobertura disponible">&#123;&#125; Descargar ofertas JSON</a>
  ` : '';
  const wishlistAction = wishlistName ? `
    <a class="file-link latest-report-action latest-json-export-action" href="${generatedFileHref(wishlistName)}" download="${escapeHtml(wishlistName)}" title="Descarga la wishlist conocida con cache_state por juego">&#128221; Descargar wishlist JSON</a>
  ` : '';
  return `
    <div class="latest-json-export-actions" data-latest-json-export-actions>
      <div class="latest-json-export-copy">
        <strong>Exports JSON separados</strong>
        <span>Ofertas JSON incluye solo ofertas detectadas con la cobertura disponible. Wishlist JSON incluye la wishlist conocida, pero no promete precios completos.</span>
        <small>${escapeHtml(jsonExportCoverageCopy(report))}</small>
      </div>
      <div class="latest-report-action-row latest-json-export-action-row" aria-label="Descargas JSON separadas">
        ${offersAction}
        ${wishlistAction}
      </div>
    </div>
  `;
}

function renderLatestReportActions(files = null, report = null) {
  const htmlName = findLatestPrimaryHtmlReport(files);
  const shareName = findLatestShareHtmlReport(files);
  const jsonName = findLatestJsonReport(files);
  const htmlAction = htmlName ? `
    <a class="file-link latest-report-action latest-report-action-primary" href="${generatedFileHref(htmlName)}" target="_blank" rel="noopener noreferrer">&#128202; Abrir reporte interactivo</a>
  ` : '';
  const shareAction = shareName ? `
    <a class="file-link latest-report-action" href="${generatedFileHref(shareName)}" target="_blank" rel="noopener noreferrer">&#128279; Abrir Share HTML</a>
  ` : '';
  const jsonLabel = jsonName ? 'Abrir JSON técnico' : 'Abrir JSON técnico';

  return `
    <div class="latest-report-actions" aria-label="Acciones rápidas del último reporte">
      <div class="latest-report-actions-copy">
        <strong>Siguiente mejor paso</strong>
        <span>Acciones del último reporte: abre el HTML interactivo para revisar ofertas. Share sirve para compartir; JSON y carpeta quedan como opciones técnicas.</span>
      </div>
      ${renderJsonExportDownloadActions(files, report)}
      <div class="latest-report-action-row">
        ${htmlAction}
        ${shareAction}
      </div>
      <div class="latest-report-action-row latest-report-action-row-secondary" aria-label="Opciones técnicas del último reporte">
        <a class="file-link latest-report-action" href="${latestReportUrl()}" target="_blank" rel="noopener noreferrer">&#123;&#125; ${jsonLabel}</a>
        <button type="button" class="file-link file-link-button latest-report-action" data-latest-action="copy-json-url">&#128203; Copiar URL JSON</button>
        <button type="button" class="file-link file-link-button latest-report-action" data-latest-action="open-folder">&#128193; Carpeta de reportes</button>
      </div>
    </div>
  `;
}

function renderLatestReportActionsPanel(files = null, report = null) {
  const body = renderLatestReportActions(files, report);
  if (!body) return '';
  return `
    <details class="latest-report-details latest-report-actions-panel">
      <summary>
        <span>Acciones del reporte</span>
        <span class="latest-report-details-hint">HTML interactivo, Share, JSON técnico, exports separados y carpeta</span>
      </summary>
      <div class="latest-report-details-body">${body}</div>
    </details>
  `;
}

function renderLatestRecommendationsPanel(report, files = null) {
  const body = [
    renderLatestPromoContext(report),
    renderLatestPromoHighlights(report),
    renderLatestExternalOffers(report),
    renderLatestFreeWeekendNow(report),
    renderLatestSmartAlertDigest(report),
    renderLatestRecommendedCollections(report),
    renderLatestPersonalizedRecommendations(report, files),
    renderLatestDecisionSupport(report),
    renderLatestRecommendationDiagnostics(report),
    renderLatestTastePriority(report),
    renderLatestGiftIdeas(report),
    renderLatestWishlistHygiene(report),
    renderLatestShareTopPicks(report),
  ].filter(Boolean).join('');
  if (!body) return '';
  return `
    <details class="latest-report-details latest-report-recommendations-panel">
      <summary>
        <span>Recomendaciones y señales</span>
        <span class="latest-report-details-hint">Picks, colecciones, alertas, regalos y wishlist hygiene</span>
      </summary>
      <div class="latest-report-details-body">${body}</div>
    </details>
  `;
}

function renderLatestReportToolsPanel(report) {
  const body = [
    renderLatestBudgetPanel(report),
  ].filter(Boolean).join('');
  if (!body) return '';
  return `
    <details class="latest-report-details latest-report-tools-panel">
      <summary>
        <span>Herramientas del reporte</span>
        <span class="latest-report-details-hint">Presupuesto y simuladores locales</span>
      </summary>
      <div class="latest-report-details-body">${body}</div>
    </details>
  `;
}

function renderLatestReportDetails(report, files = null) {
  const panels = [
    renderLatestReportActionsPanel(files, report),
    renderLatestRecommendationsPanel(report, files),
    renderLatestReportToolsPanel(report),
  ].filter(Boolean).join('');
  if (!panels) return '';
  return `
    <div class="latest-report-sections" data-latest-report-sections>
      ${panels}
    </div>
  `;
}

function renderLatestHistoryContinueCard(hasCacheCoverage) {
  const cacheCopy = hasCacheCoverage
    ? 'Si hay pendientes, Continuar warm-cache usa la misma caché y mantiene --no-cache apagado.'
    : 'No hay pendientes warm-cache visibles en este JSON local; usa el histórico para comparar corridas anteriores.';
  return `
    <div class="latest-report-history-card" data-latest-report-history-continue>
      <div class="latest-report-history-card-copy">
        <strong>Histórico y continuidad</strong>
        <span>Compara ejecuciones anteriores o continúa una cola warm-cache solo cuando el reporte indique cobertura parcial.</span>
        <small>${escapeHtml(cacheCopy)}</small>
      </div>
      <a class="file-link latest-report-history-link" href="#history-card">Ir al histórico</a>
    </div>
  `;
}

function latestReportIntentToolbarItem(intent, index) {
  const isActive = index === 0;
  const panelId = `latest-report-intent-${intent.key}`;
  const tabId = `latest-report-intent-tab-${intent.key}`;
  return `
    <a class="latest-report-intent-tab${isActive ? ' is-active' : ''}" href="#${escapeHtml(panelId)}" id="${escapeHtml(tabId)}" role="tab" aria-selected="${isActive ? 'true' : 'false'}" aria-controls="${escapeHtml(panelId)}" data-latest-report-intent-tab="${escapeHtml(intent.key)}"${isActive ? ' aria-current="true"' : ''}>
      <strong>${escapeHtml(intent.label)}</strong>
      <span>${escapeHtml(intent.hint)}</span>
    </a>
  `;
}

function latestReportIntentKeyFromHash(hash = window.location.hash) {
  const value = String(hash || '');
  const prefix = '#latest-report-intent-';
  if (!value.startsWith(prefix)) return '';
  try {
    return decodeURIComponent(value.slice(prefix.length));
  } catch (e) {
    return value.slice(prefix.length);
  }
}

function isLatestReportIntentHash(hash = window.location.hash) {
  return String(hash || '').startsWith('#latest-report-intent-');
}

function setLatestReportIntentHash(key) {
  const hash = `#latest-report-intent-${encodeURIComponent(key)}`;
  if (window.history && typeof window.history.replaceState === 'function') {
    window.history.replaceState(null, '', hash);
  } else {
    window.location.hash = hash;
  }
}

function activateLatestReportIntentTab(tab, options = {}) {
  if (!tab) return;
  const key = tab.dataset.latestReportIntentTab || '';
  if (!key) return;
  syncLatestReportIntentActiveState(key);
  setLatestReportIntentHash(key);
  if (options.focus && typeof tab.focus === 'function') tab.focus();
}

function handleLatestReportIntentTabKeydown(event, tabs, index) {
  const key = event.key;
  const count = tabs.length;
  if (!count) return;
  let nextIndex = -1;
  if (key === 'ArrowRight' || key === 'ArrowDown') nextIndex = (index + 1) % count;
  if (key === 'ArrowLeft' || key === 'ArrowUp') nextIndex = (index - 1 + count) % count;
  if (key === 'Home') nextIndex = 0;
  if (key === 'End') nextIndex = count - 1;
  if (nextIndex < 0) return;
  event.preventDefault();
  activateLatestReportIntentTab(tabs[nextIndex], { focus: true });
}

function syncLatestReportIntentActiveState(requestedKey = '') {
  const card = latestReportCardEl();
  const wrapper = card ? card.querySelector('[data-latest-report-intent-wrapper]') : null;
  if (!wrapper) return;
  const tabs = Array.from(wrapper.querySelectorAll('[data-latest-report-intent-tab]'));
  const panels = Array.from(wrapper.querySelectorAll('[data-latest-report-intent-section]'));
  if (!tabs.length) return;
  const keys = tabs.map(tab => tab.dataset.latestReportIntentTab || '').filter(Boolean);
  const key = requestedKey || latestReportIntentKeyFromHash();
  const activeKey = keys.includes(key) ? key : keys[0];
  tabs.forEach((tab) => {
    const isActive = tab.dataset.latestReportIntentTab === activeKey;
    tab.classList.toggle('is-active', isActive);
    if (isActive) {
      tab.setAttribute('aria-current', 'true');
      tab.setAttribute('aria-selected', 'true');
    } else {
      tab.removeAttribute('aria-current');
      tab.setAttribute('aria-selected', 'false');
    }
  });
  panels.forEach((panel) => {
    const isActive = panel.dataset.latestReportIntentSection === activeKey;
    panel.classList.toggle('is-active', isActive);
    panel.hidden = !isActive;
    panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
  });
}

let latestReportIntentHashListenerBound = false;

function bindLatestReportIntentToolbarActions() {
  const card = latestReportCardEl();
  const wrapper = card ? card.querySelector('[data-latest-report-intent-wrapper]') : null;
  if (!wrapper) return;
  const tabs = Array.from(wrapper.querySelectorAll('[data-latest-report-intent-tab]'));
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', (event) => {
      event.preventDefault();
      activateLatestReportIntentTab(tab);
    });
    tab.addEventListener('keydown', (event) => {
      handleLatestReportIntentTabKeydown(event, tabs, index);
    });
  });
  if (!latestReportIntentHashListenerBound) {
    latestReportIntentHashListenerBound = true;
    window.addEventListener('hashchange', () => {
      if (isLatestReportIntentHash()) syncLatestReportIntentActiveState();
    });
  }
  syncLatestReportIntentActiveState();
}

function renderLatestReportIntentSection(intent, index) {
  const isActive = index === 0;
  const titleId = `latest-report-intent-title-${intent.key}`;
  const tabId = `latest-report-intent-tab-${intent.key}`;
  return `
    <section class="latest-report-intent-section${isActive ? ' is-active' : ''}" id="latest-report-intent-${escapeHtml(intent.key)}" data-latest-report-intent-section="${escapeHtml(intent.key)}" role="tabpanel" tabindex="0" aria-labelledby="${escapeHtml(tabId)}" aria-hidden="${isActive ? 'false' : 'true'}"${isActive ? '' : ' hidden'}>
      <div class="latest-report-intent-section-head">
        <div>
          <div class="latest-report-intent-eyebrow">${escapeHtml(intent.eyebrow)}</div>
          <h3 class="latest-report-intent-title" id="${escapeHtml(titleId)}">${escapeHtml(intent.label)}</h3>
          <div class="latest-report-intent-copy">${escapeHtml(intent.copy)}</div>
        </div>
      </div>
      <div class="latest-report-intent-body">${intent.body}</div>
    </section>
  `;
}

function renderLatestReportIntentIntro() {
  return `
    <div class="latest-report-intent-intro" data-latest-report-intent-intro>
      <div>
        <div class="latest-report-intent-intro-eyebrow">Selector del último reporte</div>
        <div class="latest-report-intent-intro-title">Elige qué quieres revisar</div>
        <div class="latest-report-intent-intro-copy" id="latest-report-intent-help">Cambia de vista sin recalcular nada: todo usa el último JSON local y mantiene intactas tus recomendaciones, caché y wishlist. Atajo: usa ←/→, Home o End para moverte entre vistas.</div>
      </div>
      <span class="latest-report-intent-intro-badge">Sin cambios de datos</span>
    </div>
  `;
}

function latestReportIntents(report, meta = {}, summary = {}, files = null) {
  const cacheCoverage = renderLatestCacheCoverage(report);
  const intents = [
    {
      key: 'review',
      label: 'Revisar reporte',
      hint: 'HTML, Share y JSON',
      eyebrow: 'Vista recomendada',
      copy: 'Empieza por el resumen rápido y abre el HTML interactivo; Share, JSON y carpeta quedan como acciones técnicas.',
      body: [
        renderLatestReportQuickSummary(meta, summary, files),
        renderLatestReportActionsPanel(files, report),
      ].filter(Boolean).join(''),
    },
    {
      key: 'recommendations',
      label: 'Recomendaciones',
      hint: 'Picks y señales',
      eyebrow: 'Decidir qué revisar',
      copy: 'Agrupa promo activa, highlights por promo, alertas dry-run, colecciones, recomendaciones personales, regalos, wishlist hygiene y picks compartibles.',
      body: renderLatestRecommendationsPanel(report, files),
    },
    {
      key: 'tools',
      label: 'Herramientas',
      hint: 'Presupuesto y simuladores',
      eyebrow: 'Simulación local',
      copy: 'Herramientas locales para probar presupuesto o evaluar una selección; no abren carrito ni cambian tu wishlist.',
      body: [
        renderLatestReportToolsPanel(report),
        renderLatestSelectionReviewTools(report),
      ].filter(Boolean).join(''),
    },
    {
      key: 'history',
      label: 'Histórico/continuar',
      hint: 'Comparar y warm-cache',
      eyebrow: 'Seguimiento',
      copy: 'Usa el histórico para comparar corridas y continúa warm-cache solo con cobertura parcial, siempre con la misma caché.',
      body: [
        cacheCoverage,
        renderLatestHistoryContinueCard(Boolean(cacheCoverage)),
      ].filter(Boolean).join(''),
    },
  ];
  return intents.filter(intent => intent.body);
}

function renderLatestReportIntentWrapper(report, meta = {}, summary = {}, files = null) {
  const intents = latestReportIntents(report, meta, summary, files);
  if (!intents.length) return '';
  return `
    <section class="latest-report-intent-wrapper" data-latest-report-intent-wrapper aria-label="Secciones del último reporte por intención">
      ${renderLatestReportIntentIntro()}
      <nav class="latest-report-intent-toolbar" data-latest-report-intent-toolbar role="tablist" aria-label="Navegar secciones del último reporte" aria-describedby="latest-report-intent-help">
        ${intents.map(latestReportIntentToolbarItem).join('')}
      </nav>
      <div class="latest-report-intent-sections">
        ${intents.map(renderLatestReportIntentSection).join('')}
      </div>
    </section>
  `;
}

function latestReportSummarySentence(summary) {
  const source = summary && typeof summary === 'object' ? summary : {};
  const deals = Number(source.deals_count || 0) || 0;
  const topPicks = Number(source.top_picks_count || 0) || 0;
  const alerts = Number(source.watchlist_alerts_count || 0) || 0;
  const gifts = Number(source.gift_ideas_count || 0) || 0;
  const parts = [`${deals} oferta(s)`, `${topPicks} top pick(s)`];
  if (alerts > 0) parts.push(`${alerts} alerta(s)`);
  if (gifts > 0) parts.push(`${gifts} idea(s) de regalo`);
  return `Resultado rápido: ${parts.join(' · ')}. Abre el HTML interactivo para revisar tablas, rankings y detalle completo.`;
}

function renderLatestPrimaryReportAction(files = null) {
  const htmlName = findLatestPrimaryHtmlReport(files);
  if (htmlName) {
    return `<a class="file-link latest-report-primary-action" href="${generatedFileHref(htmlName)}" target="_blank" rel="noopener noreferrer">Abrir reporte interactivo</a>`;
  }
  return `<a class="file-link latest-report-primary-action" href="${latestReportUrl()}" target="_blank" rel="noopener noreferrer">Abrir JSON técnico</a>`;
}

function renderLatestReportQuickSummary(meta = {}, summary = {}, files = null) {
  const safeMeta = meta && typeof meta === 'object' ? meta : {};
  const safeSummary = summary && typeof summary === 'object' ? summary : {};
  const subtitleParts = [];
  if (safeMeta.profile) subtitleParts.push(`Perfil: ${escapeHtml(safeMeta.profile)}`);
  subtitleParts.push(escapeHtml(formatLatestReportTimestamp(safeMeta.generated_at)));
  const saleBadge = safeMeta.sale_name ? `<span class="latest-report-badge">${escapeHtml(safeMeta.sale_name)}</span>` : '';
  const stats = [
    ['Ofertas', safeSummary.deals_count ?? 0],
    ['Top picks', safeSummary.top_picks_count ?? 0],
    ['Alerts', safeSummary.watchlist_alerts_count ?? 0],
    ['Regalos', safeSummary.gift_ideas_count ?? 0],
  ];
  return `
    <section class="latest-report-quick-summary" data-latest-report-quick-summary>
      <div class="latest-report-head">
        <div>
          <div class="latest-report-eyebrow">Resumen rápido</div>
          <div class="latest-report-title">Última ejecución</div>
          <div class="latest-report-subtitle">${subtitleParts.join(' · ')}</div>
        </div>
        ${saleBadge}
      </div>
      <div class="latest-report-quick-copy">${escapeHtml(latestReportSummarySentence(safeSummary))}</div>
      <div class="latest-report-quick-actions">
        ${renderLatestPrimaryReportAction(files)}
      </div>
      <div class="latest-report-stats" aria-label="Métricas principales del último reporte">
        ${stats.map(([label, value]) => `
          <div class="latest-report-stat">
            <div class="latest-report-stat-label">${escapeHtml(label)}</div>
            <div class="latest-report-stat-value">${escapeHtml(value)}</div>
          </div>
        `).join('')}
      </div>
    </section>
  `;
}

function latestCacheStateItems(coverage) {
  const rawItems = Array.isArray(coverage && coverage.state_summary)
    ? coverage.state_summary
    : [];
  return rawItems
    .map((item) => ({
      label: String((item && item.label) || '').trim(),
      count: latestCoverageCount(item && item.count),
    }))
    .filter((item) => item.label && item.count > 0);
}

const LATEST_NO_PRICE_CLASSIFICATION_LABELS = {
  coming_soon: 'Juegos por salir',
  free_or_no_normal_price: 'Gratis o sin precio normal',
  unavailable_or_removed_review: 'Revisar disponibilidad',
  temporary_unconfirmed: 'No confirmado todavía',
  unknown_no_price: 'Sin precio confirmado',
};

const LATEST_NO_PRICE_CLASSIFICATION_ORDER = [
  'coming_soon',
  'free_or_no_normal_price',
  'unavailable_or_removed_review',
  'temporary_unconfirmed',
  'unknown_no_price',
];

const LATEST_FINAL_CACHE_STATE_LABELS = {
  resumable_queue_finished: 'Cola resumible terminada',
  resumable_queue_pending: 'Cola resumible pendiente',
  price_confirmed: 'Precio confirmado/cache válido',
  temporary_unconfirmed: 'Fallos temporales/cooldown',
  no_price_confirmed: 'Sin precio confirmado',
  missing_or_unclassified: 'Sin clasificar todavía',
};

function latestNoPriceClassificationLabel(category, fallback = '') {
  const key = String(category || '').trim();
  const label = String(fallback || '').trim();
  return LATEST_NO_PRICE_CLASSIFICATION_LABELS[key] || label || key.replace(/_/g, ' ');
}

function latestNoPriceClassificationItems(coverage) {
  const counts = coverage && typeof coverage.no_price_classification_counts === 'object'
    ? coverage.no_price_classification_counts
    : {};
  const categories = LATEST_NO_PRICE_CLASSIFICATION_ORDER.concat(
    Object.keys(counts).sort().filter((category) => !LATEST_NO_PRICE_CLASSIFICATION_ORDER.includes(category))
  );
  return categories
    .map((category) => ({
      category,
      label: latestNoPriceClassificationLabel(category),
      count: latestCoverageCount(counts[category]),
    }))
    .filter((item) => item.category && item.count > 0);
}

function latestNoPriceClassificationSamples(coverage) {
  const samples = Array.isArray(coverage && coverage.no_price_classification_samples)
    ? coverage.no_price_classification_samples
    : [];
  return samples.slice(0, 5).map((sample) => {
    const category = String((sample && sample.category) || '').trim();
    const appid = String((sample && sample.appid) || '').trim();
    const name = String((sample && sample.name) || '').trim();
    return {
      appid,
      name,
      category,
      label: latestNoPriceClassificationLabel(category, sample && sample.label),
      reason: String((sample && sample.reason) || '').trim(),
      failureReason: String((sample && sample.failure_reason) || '').trim(),
    };
  }).filter((sample) => sample.category || sample.name || sample.appid);
}

function latestFinalCacheStateItems(coverage) {
  const rawItems = Array.isArray(coverage && coverage.final_state_summary)
    ? coverage.final_state_summary
    : [];
  return rawItems.map((item) => ({
    state: String((item && item.state) || '').trim(),
    label: String(
      (item && item.label) ||
      LATEST_FINAL_CACHE_STATE_LABELS[String((item && item.state) || '').trim()] ||
      ''
    ).trim(),
    count: latestCoverageCount(item && item.count),
  })).filter((item) => item.state && item.label);
}

function latestFinalFailureActionItems(coverage) {
  const rawItems = Array.isArray(coverage && coverage.final_failure_actions)
    ? coverage.final_failure_actions
    : [];
  return rawItems.map((item) => ({
    action: String((item && item.action) || '').trim(),
    label: String((item && item.label) || '').trim(),
    count: latestCoverageCount(item && item.count),
    detail: String((item && item.detail) || '').trim(),
    canRetry: item && item.can_retry === true,
    destructive: item && item.destructive === true,
  })).filter((item) => item.action && item.label && item.count > 0);
}

function latestFinalFailureActionHint(item) {
  const action = String((item && item.action) || '').trim();
  if (action === 'wait_cooldown') return 'Espera antes de reintentar';
  if (action === 'retry_failed_eligible') return 'Retry seguro con warm-cache';
  if (action === 'review_no_price') return 'Solo revisión manual';
  return item && item.canRetry ? 'Retry seguro con warm-cache' : 'Acción advisory';
}

function renderLatestFinalCacheStates(coverage) {
  const items = latestFinalCacheStateItems(coverage);
  if (!items.length) return '';
  const queueStatus = String((coverage && coverage.resumable_queue_status) || '').trim();
  const finished = queueStatus === 'finished';
  return `
    <div class="latest-cache-final-states" data-latest-cache-final-states>
      <div class="latest-cache-final-title">${finished ? 'Cola resumible terminada' : 'Estado de cobertura warm-cache'}</div>
      <div class="latest-cache-final-copy">${finished ? 'deferred=0 indica que la cola resumible terminó; no significa cobertura perfecta. Fallos/cooldown y juegos sin precio confirmado se revisan por separado.' : 'La cola resumible todavía tiene pendientes; las ofertas pueden no incluir juegos no verificados.'}</div>
      <div class="latest-cache-final-pills" aria-label="Estados finales de cobertura warm-cache">
        ${items.map((item) => {
          const countCopy = item.count > 0 ? `: ${formatLatestCoverageCount(item.count)}` : '';
          return `<strong data-final-cache-state="${escapeHtml(item.state)}">${escapeHtml(item.label)}${escapeHtml(countCopy)}</strong>`;
        }).join('')}
      </div>
    </div>
  `;
}

function renderLatestFinalFailureActions(coverage) {
  const items = latestFinalFailureActionItems(coverage);
  if (!items.length) return '';
  return `
    <div class="latest-cache-final-actions" data-latest-cache-final-actions>
      <div class="latest-cache-final-actions-title">Acciones para fallidos finales</div>
      <div class="latest-cache-final-actions-copy">Cierre seguro de warm-cache: separa qué esperar, qué reintentar con la misma caché y qué revisar manualmente. No borra juegos, no excluye de la wishlist, no cambia ranking y no usa --no-cache.</div>
      <ul class="latest-cache-final-actions-list">
        ${items.map((item) => `
          <li data-final-failure-action="${escapeHtml(item.action)}">
            <strong>${escapeHtml(item.label)}: ${escapeHtml(formatLatestCoverageCount(item.count))}</strong>
            <em>${escapeHtml(latestFinalFailureActionHint(item))}</em>
            <span>${escapeHtml(item.detail)}</span>
          </li>
        `).join('')}
      </ul>
    </div>
  `;
}

function renderLatestNoPriceClassification(coverage) {
  const items = latestNoPriceClassificationItems(coverage);
  const samples = latestNoPriceClassificationSamples(coverage);
  if (!items.length && !samples.length) return '';
  const sampleList = samples.length
    ? `
      <ul class="latest-cache-no-price-samples">
        ${samples.map((sample) => {
          const title = sample.name || (sample.appid ? `App ${sample.appid}` : sample.label);
          const reason = sample.failureReason
            ? `${sample.reason || 'No confirmado todavía'} (${sample.failureReason})`
            : sample.reason;
          return `
            <li>
              <strong>${escapeHtml(sample.label)}</strong>
              <span>${escapeHtml(title)}</span>
              ${reason ? `<small>${escapeHtml(reason)}</small>` : ''}
            </li>
          `;
        }).join('')}
      </ul>
    `
    : '';
  return `
    <div class="latest-cache-no-price" data-latest-no-price-classification>
      <div class="latest-cache-no-price-title">Juegos sin precio clasificados</div>
      <div class="latest-cache-no-price-copy">Solo revisión: estas categorías no eliminan juegos, no cambian ranking y no prueban que un juego esté retirado.</div>
      ${items.length ? `
        <div class="latest-cache-no-price-pills" aria-label="Categorías sin precio">
          ${items.map((item) => `<strong data-no-price-category="${escapeHtml(item.category)}">${escapeHtml(item.label)}: ${escapeHtml(formatLatestCoverageCount(item.count))}</strong>`).join('')}
        </div>
      ` : ''}
      ${sampleList}
    </div>
  `;
}

function latestWarmCacheBlockProgress(coverage) {
  const progress = coverage && typeof coverage.block_progress === 'object'
    ? coverage.block_progress
    : null;
  if (!progress) return null;
  const label = String(progress.label || '').trim();
  const initial = latestCoverageCount(progress.initial_candidate_count);
  const accumulated = latestCoverageCount(progress.processed_accumulated_count);
  if (!label || !initial) return null;
  return {
    label,
    initial,
    accumulated,
    pendingDynamic: latestCoverageCount(progress.pending_dynamic_count),
    currentRunProcessed: latestCoverageCount(progress.current_run_processed_count),
    currentRunDeferred: latestCoverageCount(progress.current_run_deferred_count),
    nextHint: String(progress.next_resume_hint || '').trim(),
    isEstimated: progress.is_estimated === true,
  };
}

function renderLatestWarmCacheBlockProgress(coverage) {
  const progress = latestWarmCacheBlockProgress(coverage);
  if (!progress) return '';
  const pendingCopy = progress.pendingDynamic > 0
    ? `Pendientes dinámicos por presupuesto/stale/cooldown: ${formatLatestCoverageCount(progress.pendingDynamic)}.`
    : 'Sin pendientes dinámicos por presupuesto; revisa estados finales para cooldown/no-price.';
  const hintCopy = progress.nextHint
    ? ` Última pista de continuación: ${escapeHtml(progress.nextHint)}.`
    : '';
  const estimateCopy = progress.isEstimated ? ' aproximado' : '';
  return `
    <div class="latest-cache-block-progress" data-latest-cache-block-progress>
      <div class="latest-cache-block-title">Avance por bloques warm-cache</div>
      <div class="latest-cache-block-main">${escapeHtml(progress.label)}${escapeHtml(estimateCopy)}</div>
      <div class="latest-cache-block-copy">Cobertura acumulada: ${escapeHtml(formatLatestCoverageCount(progress.accumulated))}/${escapeHtml(formatLatestCoverageCount(progress.initial))} juegos revisados. ${escapeHtml(pendingCopy)}${hintCopy}</div>
      <div class="latest-cache-block-pills" aria-label="Detalle del bloque warm-cache">
        <strong>Último bloque procesó ${escapeHtml(formatLatestCoverageCount(progress.currentRunProcessed))}</strong>
        <strong>Diferidos del último bloque ${escapeHtml(formatLatestCoverageCount(progress.currentRunDeferred))}</strong>
      </div>
    </div>
  `;
}

function renderLatestCacheStateSummary(coverage) {
  const items = latestCacheStateItems(coverage);
  if (!items.length) return '';
  return `
    <div class="latest-cache-state-summary" aria-label="Estados derivados de caché">
      <span>Estados derivados:</span>
      ${items.map((item) => `<strong>${escapeHtml(item.label)}: ${escapeHtml(formatLatestCoverageCount(item.count))}</strong>`).join('')}
    </div>
  `;
}

function renderLatestCacheCoverage(report) {
  const coverage = report && typeof report === 'object' ? (report.cache_coverage || null) : null;
  if (!coverage || typeof coverage !== 'object') return '';
  const deferred = latestCoverageCount(coverage.deferred_count);
  const isPartial = coverage.is_partial === true || coverage.status === 'partial' || deferred > 0;
  const hasDeferred = isPartial && deferred > 0;
  const blockProgress = renderLatestWarmCacheBlockProgress(coverage);
  const finalStates = renderLatestFinalCacheStates(coverage);
  const finalFailureActionItems = latestFinalFailureActionItems(coverage);
  const finalFailureActions = renderLatestFinalFailureActions(coverage);
  const noPriceClassification = renderLatestNoPriceClassification(coverage);
  const technicalDetails = [
    blockProgress,
    renderLatestCacheStateSummary(coverage),
    finalStates,
    finalFailureActions,
    noPriceClassification,
  ].filter(Boolean).join('');
  if (!hasDeferred && !blockProgress && !finalStates && !finalFailureActions && !noPriceClassification) return '';
  const hasRetryableFinalFailures = finalFailureActionItems.some((item) => item.canRetry);
  const showWarmCacheAction = hasDeferred || hasRetryableFinalFailures;
  const warmCacheActionLabel = hasDeferred ? 'Continuar warm-cache' : 'Reintentar fallidos elegibles';
  const warmCacheActionHint = hasDeferred
    ? '<div class="latest-cache-coverage-action-hint">Completar warm-cache repite pasadas con la misma caché usando --warm-cache-full, sin --no-cache y sin regenerar reportes automáticamente. Al terminar, genera un reporte normal con la caché actualizada.</div>'
    : '<div class="latest-cache-coverage-action-hint">Reintenta solo fallidos elegibles con la caché actual; sin --no-cache y sin eliminar juegos.</div>';
  const processed = latestCoverageCount(coverage.processed_count);
  const total = latestCoverageCount(coverage.refresh_candidate_count) || processed + deferred;
  const coverageLabel = String(coverage.coverage_label || '').trim() || `${formatLatestCoverageCount(processed)}/${formatLatestCoverageCount(total)}`;
  const nextHint = String(coverage.next_resume_hint || '').trim();
  const resumeCopy = nextHint
    ? ` Usa Continuar warm-cache para revisar otra tanda con la misma caché (pista ${escapeHtml(nextHint)}), en una corrida normal con --warm-cache y sin --no-cache.`
    : ' Usa Continuar warm-cache para revisar otra tanda con la misma caché, en una corrida normal con --warm-cache y sin --no-cache.';
  return `
    <div class="latest-cache-coverage ${isPartial ? 'latest-cache-coverage-partial' : 'latest-cache-coverage-complete'}" data-latest-cache-coverage>
      <div class="latest-cache-coverage-title">${isPartial ? 'Caché parcial' : 'Cola resumible terminada'}</div>
      <div class="latest-cache-coverage-main">${escapeHtml(coverageLabel)} juegos revisados</div>
      <div class="latest-cache-coverage-copy">${hasDeferred ? `Quedan ${escapeHtml(formatLatestCoverageCount(deferred))} pendientes por confirmar. Las ofertas mostradas pueden no incluir juegos aún no verificados.${resumeCopy}` : 'Sin pendientes por presupuesto; eso no implica cobertura perfecta si quedan fallos/cooldown o juegos sin precio confirmado.'}</div>
      ${technicalDetails ? `
        <details class="latest-cache-details">
          <summary>
            <span>Ver detalles de caché</span>
            <span class="latest-cache-details-hint">Estados, bloques y juegos sin precio</span>
          </summary>
          <div class="latest-cache-details-body">${technicalDetails}</div>
        </details>
      ` : ''}
      ${showWarmCacheAction ? `
        <div class="latest-cache-coverage-actions">
          <button type="button" class="file-link file-link-button latest-cache-coverage-action" data-latest-action="continue-warm-cache">${escapeHtml(warmCacheActionLabel)}</button>
          ${hasDeferred ? '<button type="button" class="file-link file-link-button latest-cache-coverage-action" data-latest-action="complete-warm-cache">Completar warm-cache</button>' : ''}
        </div>
        ${warmCacheActionHint}
        <div class="latest-cache-continue-status hidden" data-latest-cache-continue-status role="status" aria-live="polite"></div>
      ` : ''}
    </div>
  `;
}

async function continueWarmCacheFromLatestReport(btn) {
  const originalLabel = btn ? btn.textContent : 'Continuar warm-cache';
  if (btn) {
    btn.textContent = 'Continuando warm-cache...';
    btn.setAttribute('aria-busy', 'true');
    btn.classList.add('is-running');
  }
  setWarmCacheContinueStatus(
    btn,
    'Continuando con la misma caché: revalidando otra tanda con --warm-cache, sin --no-cache.',
    'progress'
  );
  setWarmCacheBackgroundBanner(
    'progress',
    'Warm-cache en segundo plano',
    'Revalidando otra tanda con la misma caché.',
    'Puedes seguir revisando el último reporte; se usa --warm-cache, sin --no-cache.'
  );
  const completed = await runSteamDealsUI({
    filters: buildWarmCacheContinueFilters(),
    startLabel: 'Continuando warm-cache...',
    introLine: 'Continuando warm-cache con la caché actual (sin --no-cache).',
    conflictMessage: 'Ya hay una ejecucion en curso. Espera a que termine antes de continuar warm-cache.',
    triggerButton: btn,
    preserveOutputFiles: true,
    preserveLatestReportOnDone: true,
    onEvent: updateWarmCacheBackgroundBannerFromEvent,
  });
  let refreshed = false;
  let refreshError = '';
  if (completed) {
    setWarmCacheContinueStatus(
      btn,
      'Continuación warm-cache finalizada. Actualizando el resumen visible desde el JSON local...',
      'progress'
    );
    try {
      refreshed = await syncLatestReportSummary();
      if (!refreshed) throw new Error('No hay JSON local disponible para refrescar.');
    } catch (e) {
      refreshError = e && e.message ? e.message : 'No se pudo refrescar el resumen visible.';
    }
  }
  if (btn && btn.isConnected) {
    btn.textContent = originalLabel;
    btn.removeAttribute('aria-busy');
    btn.classList.remove('is-running');
    setWarmCacheContinueStatus(
      btn,
      completed && refreshed
        ? 'Continuación warm-cache finalizada y resumen actualizado. Si todavía queda Caché parcial, puedes continuar otra tanda con la misma caché.'
        : completed
          ? 'Continuación warm-cache finalizada, pero no se pudo refrescar el resumen automáticamente. Usa Refrescar resumen.'
          : 'No se pudo continuar warm-cache. Revisa el log; si ya hay una ejecución activa, espera a que termine.',
      completed && refreshed ? 'ok' : 'warn'
    );
  }
  setWarmCacheBackgroundBanner(
    completed && refreshed ? 'ok' : 'warn',
    completed && refreshed ? 'Resumen warm-cache actualizado' : completed ? 'Warm-cache finalizado; genera reporte actualizado' : 'No se pudo actualizar caché',
    completed && refreshed
      ? 'La continuación terminó. Genera un reporte normal para que HTML/JSON usen la caché actualizada.'
      : completed
        ? 'La continuación terminó, pero warm-cache no genera HTML/JSON por sí mismo.'
        : 'Revisa el log; si ya hay una ejecución activa, espera a que termine antes de reintentar.',
    completed && refreshed
      ? 'Usa el reporte actualizado para ver nuevas ofertas, Top Picks y recomendaciones recalculadas.'
      : completed
        ? refreshError || 'Genera un reporte normal con la caché actualizada para ver los cambios.'
        : 'Se respetó el lock actual y no se usó --no-cache.',
    {showRefresh: completed, showReportAction: completed}
  );
}

async function completeWarmCacheFromLatestReport(btn) {
  const originalLabel = btn ? btn.textContent : 'Completar warm-cache';
  if (btn) {
    btn.textContent = 'Completando warm-cache...';
    btn.setAttribute('aria-busy', 'true');
    btn.classList.add('is-running');
  }
  setWarmCacheContinueStatus(
    btn,
    'Completando warm-cache: repitiendo pasadas con --warm-cache-full, misma caché y sin --no-cache.',
    'progress'
  );
  setWarmCacheBackgroundBanner(
    'progress',
    'Full warm-cache en segundo plano',
    'Repitiendo pasadas resumibles con la misma caché.',
    'Usa --warm-cache-full, no fuerza --no-cache y no genera reportes automáticamente.'
  );
  const completed = await runSteamDealsUI({
    filters: buildWarmCacheFullFilters(),
    startLabel: 'Completando warm-cache...',
    introLine: 'Completando warm-cache con pasadas resumibles (misma caché, sin --no-cache, sin reporte automático).',
    conflictMessage: 'Ya hay una ejecucion en curso. Espera a que termine antes de completar warm-cache.',
    triggerButton: btn,
    preserveOutputFiles: true,
    preserveLatestReportOnDone: true,
    onEvent: updateFullWarmCacheBackgroundBannerFromEvent,
  });
  if (btn && btn.isConnected) {
    btn.textContent = originalLabel;
    btn.removeAttribute('aria-busy');
    btn.classList.remove('is-running');
    setWarmCacheContinueStatus(
      btn,
      completed
        ? 'Full warm-cache finalizado. Genera un reporte normal con la caché actualizada para ver ofertas, Top Picks y recomendaciones recalculadas.'
        : 'No se pudo completar warm-cache. Revisa el log; si ya hay una ejecución activa, espera a que termine.',
      completed ? 'ok' : 'warn'
    );
  }
  setWarmCacheBackgroundBanner(
    completed ? 'ok' : 'warn',
    completed ? 'Full warm-cache finalizado' : 'No se pudo completar warm-cache',
    completed
      ? 'Warm-cache no genera HTML/JSON por sí mismo; usa Generar reporte con caché actualizada.'
      : 'Revisa el log; no se usó --no-cache y la caché local se conserva.',
    completed
      ? 'El reporte final debe ser una corrida normal separada para recalcular la vista con la caché actualizada.'
      : 'Puedes reintentar cuando no haya otra ejecución activa.',
    {showRefresh: completed, showReportAction: completed}
  );
}

function bindLatestReportQuickActions() {
  const el = latestReportCardEl();
  if (!el) return;
  el.querySelectorAll('[data-latest-action="copy-json-url"]').forEach((btn) => {
    btn.addEventListener('click', () => copyLatestReportUrl(btn));
  });
  el.querySelectorAll('[data-latest-action="open-folder"]').forEach((btn) => {
    btn.addEventListener('click', () => openOutputFolderUI(btn));
  });
  el.querySelectorAll('[data-latest-action="continue-warm-cache"]').forEach((btn) => {
    btn.addEventListener('click', () => continueWarmCacheFromLatestReport(btn));
  });
  el.querySelectorAll('[data-latest-action="complete-warm-cache"]').forEach((btn) => {
    btn.addEventListener('click', () => completeWarmCacheFromLatestReport(btn));
  });
}

function renderLatestReportCard(report, files = null) {
  if (report) {
    latestBudgetUiState = createLatestBudgetUiState(report);
  }
  const activeReport = report || (latestBudgetUiState && latestBudgetUiState.report);
  if (!activeReport) {
    hideLatestReportCard();
    return;
  }
  const el = latestReportCardEl();
  if (!el) return;
  const meta = activeReport && typeof activeReport === 'object' ? (activeReport.meta || {}) : {};
  const summary = activeReport && typeof activeReport === 'object' ? (activeReport.summary || {}) : {};
  el.innerHTML = `
    ${renderLatestReportIntentWrapper(activeReport, meta, summary, files)}
  `;
  el.classList.remove('hidden');
  bindLatestReportIntentToolbarActions();
  bindLatestReportQuickActions();
  bindLatestSelectionReviewActions();
  bindLatestShareActions();
  bindLatestBudgetActions();
}

async function syncLatestReportCard(files = null) {
  if (Array.isArray(files) && !hasJsonArtifact(files)) {
    hideLatestReportCard();
    return false;
  }
  try {
    const reportFiles = Array.isArray(files) ? files : await fetchGeneratedFilesList();
    if (Array.isArray(reportFiles) && !hasJsonArtifact(reportFiles)) {
      hideLatestReportCard();
      return false;
    }
    const resp = await fetch('/api/latest-report');
    if (!resp.ok) {
      hideLatestReportCard();
      return false;
    }
    renderLatestReportCard(await resp.json(), reportFiles);
    return true;
  } catch (e) {
    hideLatestReportCard();
    return false;
  }
}

async function syncLatestReportSummary() {
  const files = await fetchGeneratedFilesList();
  await syncLatestReportEmptyState(files);
  return syncLatestReportCard(files);
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
  el.innerHTML = `<strong>Sin reporte listo todavía.</strong><span>${message}</span>`;
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
    showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar el resumen, las descargas y las acciones rápidas.');
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
  showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar el resumen, las descargas y las acciones rápidas.');
}

function isShareHtmlFile(filePath) {
  return /steam deals share .*\.html$/i.test((filePath || '').split('/').pop() || '');
}

function copyLatestReportUrl(btn) {
  const url = latestReportUrl();
  const resetLabel = btn.innerHTML;
  const showCopied = () => {
    btn.textContent = '¡Copiado!';
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
    openHtmlBtn.innerHTML = '&#128202; Abrir último reporte interactivo';
    btnContainer.appendChild(openHtmlBtn);
  }

  if (shareHtmlFile) {
    const openShareBtn = document.createElement('a');
    openShareBtn.href = '/files/' + encodeURIComponent(shareHtmlFile.split('/').pop());
    openShareBtn.target = '_blank';
    openShareBtn.className = 'file-link';
    openShareBtn.innerHTML = '&#128279; Abrir último Share HTML';
    btnContainer.appendChild(openShareBtn);
  }

  if (jsonFile) {
    const openJsonBtn = document.createElement('a');
    openJsonBtn.href = '/api/latest-report';
    openJsonBtn.target = '_blank';
    openJsonBtn.className = 'file-link';
    openJsonBtn.innerHTML = '&#123;&#125; Abrir JSON técnico del último reporte';
    btnContainer.appendChild(openJsonBtn);

    const copyJsonBtn = document.createElement('button');
    copyJsonBtn.type = 'button';
    copyJsonBtn.className = 'file-link';
    copyJsonBtn.style.cursor = 'pointer';
    copyJsonBtn.style.fontFamily = 'inherit';
    copyJsonBtn.innerHTML = '&#128203; Copiar URL del JSON del último reporte';
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
    const r = await localMutableFetch('/api/watchlist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid, name, target_price:price})});
    const d = await r.json(); renderWatchlist(d.items);
    document.getElementById('wl-appid').value = '';
    document.getElementById('wl-name').value = '';
    document.getElementById('wl-price').value = '';
  } catch(e) {}
}
async function removeWatchlist(appid) {
  try {
    const r = await localMutableFetch('/api/watchlist/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid})});
    const d = await r.json(); renderWatchlist(d.items);
  } catch(e) {}
}

let currentShareData = null;
let currentSteamUrl = '';
let stopRequestInFlight = false;
let stopMessageShown = false;

function resetStopUiState() {
  stopRequestInFlight = false;
  stopMessageShown = false;
  if (btnStop) btnStop.disabled = true;
}

function beginStopUiState() {
  stopRequestInFlight = true;
  if (btnStop) btnStop.disabled = true;
  if (!stopMessageShown) {
    appendLine('Solicitando detener ejecucion...', 'warn');
    stopMessageShown = true;
  }
}

function completeStopUiState() {
  stopRequestInFlight = false;
}

function encodeSharePayload(data) {
  const json = JSON.stringify(data || {});
  try {
    return btoa(unescape(encodeURIComponent(json)));
  } catch (e) {
    try {
      return btoa(json);
    } catch (e2) {
      return '';
    }
  }
}

function copyTextWithFallback(text) {
  if (!text) return Promise.reject(new Error('empty-text'));
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      const ok = document.execCommand('copy');
      textarea.remove();
      if (ok) resolve();
      else reject(new Error('copy-failed'));
    } catch (err) {
      textarea.remove();
      reject(err);
    }
  });
}

function flashShareButton(button, successLabel, defaultLabel) {
  if (!button) return;
  button.textContent = successLabel;
  setTimeout(() => {
    button.textContent = defaultLabel;
  }, 2000);
}

function openShareModal(game, report = null) {
  const shareGame = buildShareGamePayload(game, report || (latestBudgetUiState && latestBudgetUiState.report));
  if (!shareGame) {
    appendLine('No se pudo preparar el deal para compartir.', 'warn');
    return;
  }

  currentShareData = shareGame.payload;
  currentSteamUrl = shareGame.steamUrl;

  document.getElementById('share-name').textContent = shareGame.name;
  document.getElementById('share-price').innerHTML = `${shareGame.displayOriginalPrice ? `<span>${escapeHtml(shareGame.displayOriginalPrice)} </span>` : ''}${escapeHtml(shareGame.displayPrice)}${shareGame.discount ? ` (${escapeHtml(shareGame.discount)}% OFF)` : ''}`;
  document.getElementById('share-minhist').innerHTML = shareGame.displayMinHist
    ? `Mínimo histórico en Steam: <span>${escapeHtml(shareGame.displayMinHist)}</span> · Te ayuda a ver si la oferta actual está cerca de su mejor precio.`
    : 'Sin dato de mínimo histórico. Si agregas ITAD tendrás esa referencia en más reportes.';

  document.getElementById('share-modal').classList.add('active');
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
  currentSteamUrl = '';
}

function copyShareLink() {
  if (!currentShareData) return;
  const encoded = encodeSharePayload(currentShareData);
  if (!encoded) {
    appendLine('No se pudo generar link para compartir.', 'err');
    return;
  }
  const shareUrl = 'steamtools://share?data=' + encoded;
  copyTextWithFallback(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    flashShareButton(btn, '¡Copiado!', 'Copiar link steamtools://');
  }).catch(() => {
    window.prompt('Copia este link:', shareUrl);
  });
}

function copySteamLink() {
  if (!currentSteamUrl) return;
  copyTextWithFallback(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    flashShareButton(btn, '¡Copiado!', 'Copiar link de Steam');
  }).catch(() => {
    window.prompt('Copia este link de Steam:', currentSteamUrl);
  });
}

function openInSteam() {
  if (currentSteamUrl) {
    window.open(currentSteamUrl, '_blank');
  }
}

function bindShareModalInteractions() {
  const modal = $('share-modal');
  if (!modal || modal.dataset.bound === '1') return;
  modal.dataset.bound = '1';
  modal.addEventListener('click', (ev) => {
    if (ev.target === modal) closeShareModal();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && modal.classList.contains('active')) {
      closeShareModal();
    }
  });
}

bindShareModalInteractions();
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
      appendLine('Histórico recargado.', 'ok');
    } catch (e) {
      appendLine('No se pudo recargar histórico: ' + e.message, 'err');
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
      appendLine('Comparación de ejecuciones completada.', 'ok');
    } catch (e) {
      appendLine('No se pudieron comparar ejecuciones: ' + e.message, 'err');
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
    const quickCompare = resolveQuickCompareRuns();
    const source = quickCompare.runs;
    if (!source || source.length < 2) {
      appendLine('No hay suficientes ejecuciones para la comparación rápida.', 'warn');
      return;
    }
    prepareQuickCompareSelectors(quickCompare);
    if (historyLeft && historyRight) {
      historyLeft.value = source[1].id || '';
      historyRight.value = source[0].id || '';
    }
    try {
      await compareHistoryRuns({quick: true});
      appendLine(
        quickCompare.usedGlobalFallback
          ? 'Comparación rápida: últimas 2 ejecuciones globales.'
          : 'Comparación rápida: últimas 2 ejecuciones.',
        'ok'
      );
    } catch (e) {
      appendLine('No se pudo ejecutar la comparación rápida: ' + e.message, 'err');
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
