// ── Helpers ──
function $(id) { return document.getElementById(id); }
function togglePw(btn) {
  const inp = btn.previousElementSibling;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── Config fields (saveable) ──
const CONFIG_FIELDS = ['vanity','key','hltb','output','discount','genres','family_json','itad_key','compare','telegram_token','telegram_chat','discord_webhook'];
const FILTER_FIELDS = ['max_price','min_reviews','min_review_count','max_hours','top','sort','budget'];
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
const btnClearCache = $('btn-clear-cache');
const btnOpenLast = $('btn-open-last');
const btnRunPd2 = $('btn-run-pd2');
const consoleEl = $('console');
const progressBar = $('progress-bar');
const progressText = $('progress-text');
const fileLinks = $('file-links');
let abortCtrl = null;
let shownErrorHints = new Set();

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

btnPreflight.addEventListener('click', async () => {
  try {
    await runPreflightUI();
  } catch(e) {
    appendLine('No se pudo ejecutar preflight: ' + e.message, 'err');
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
  const div = document.createElement('div');
  div.className = 'line line-' + cls;
  div.textContent = text;
  consoleEl.appendChild(div);
  consoleEl.scrollTop = consoleEl.scrollHeight;
  maybeShowActionableHint(text, cls);
}

btnRun.addEventListener('click', async () => {
  if (!$('vanity').value.trim()) {
    $('vanity').focus();
    $('vanity').style.borderColor = 'var(--red)';
    setTimeout(() => $('vanity').style.borderColor = '', 2000);
    return;
  }

  shownErrorHints = new Set();
  consoleEl.innerHTML = '';
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
  consoleEl.innerHTML = '';
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
    }
    const htmlFile = ev.files ? ev.files.find(f => f.endsWith('.html')) : null;
    if (htmlFile) {
      const btnContainer = document.createElement('div');
      btnContainer.style.cssText = 'margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap';
      const openHtmlBtn = document.createElement('a');
      openHtmlBtn.href = '/files/' + encodeURIComponent(htmlFile.split('/').pop());
      openHtmlBtn.target = '_blank';
      openHtmlBtn.className = 'file-link';
      openHtmlBtn.innerHTML = '&#128202; Abrir reporte interactivo (con botones compartir)';
      btnContainer.appendChild(openHtmlBtn);
      fileLinks.appendChild(btnContainer);
      fileLinks.classList.remove('hidden');
    }
  }
}

function showFiles(files) {
  fileLinks.innerHTML = '';
  const icons = {'.html': '&#128202;', '.md': '&#128196;', '.csv': '&#128203;'};
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
