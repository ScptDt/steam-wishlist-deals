/* Globals */
let DATA = null;
let sortKey = 'discount', sortAsc = false;
let actionStatusTimer = null;
const STORE = 'https://store.steampowered.com/app/';
const CAP = 'https://cdn.akamai.steamstatic.com/steam/apps/';
const PD2_MASKS = Object.freeze([
  '/masks/heist_mask_blue.svg',
  '/masks/heist_mask_gold.svg',
  '/masks/heist_mask_red.svg',
  '/masks/heist_mask_shadow.svg',
]);
const LOCAL_CSRF_HEADER = 'X-Steam-Tools-Local-Token';

function $(id) { return document.getElementById(id); }
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function fmt(n) { return n.toLocaleString('en', { maximumFractionDigits: 0 }); }
function togglePw(btn) { const i = btn.previousElementSibling; i.type = i.type === 'password' ? 'text' : 'password'; }

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

function showActionStatus(message, kind = 'loading', {autoHide = false} = {}) {
  const el = $('action-status');
  if (!el) return;
  if (actionStatusTimer) {
    clearTimeout(actionStatusTimer);
    actionStatusTimer = null;
  }
  el.textContent = message;
  el.className = 'action-status action-status-' + kind;
  el.classList.remove('hidden');
  if (autoHide) {
    actionStatusTimer = setTimeout(() => {
      el.classList.add('hidden');
      actionStatusTimer = null;
    }, 3500);
  }
}

function setButtonBusy(btn, busy) {
  if (!btn) return;
  btn.disabled = !!busy;
  btn.classList.toggle('loading', !!busy);
}

function setRefreshButtonsBusy(busy) {
  setButtonBusy($('btn-refresh'), busy);
  setButtonBusy($('btn-force-refresh'), busy);
}

function renderRandomMask() {
  const img = $('pd2-mask-img');
  if (!img || PD2_MASKS.length === 0) return;
  const index = Math.floor(Math.random() * PD2_MASKS.length);
  img.src = PD2_MASKS[index];
}

async function loadData() {
  renderRandomMask();
  try {
    const r = await fetch('/api/data');
    DATA = await r.json();
    if (DATA.loaded) {
      $('empty-state').style.display = 'none';
      $('dashboard').style.display = 'block';
      renderAll();
    } else {
      $('empty-state').style.display = 'block';
      $('dashboard').style.display = 'none';
    }
  } catch (e) {
    showActionStatus('No se pudo cargar el estado del dashboard. Revisa que el servidor local siga abierto.', 'error');
  }

  try {
    const r = await fetch('/api/config');
    const cfg = await r.json();
    if (cfg.vanity) $('cfg-vanity').value = cfg.vanity;
    if (cfg.key) $('cfg-key').value = cfg.key;
    if (cfg.itad_key) $('cfg-itad').value = cfg.itad_key;
  } catch (e) {}
}

function renderAll() {
  if (!DATA) return;
  renderHeader();
  renderBanners();
  renderCacheStatus();
  renderStats();
  renderDonut();
  renderLegend();
  renderTable();
  renderBundles();
  renderOwned();
  renderSales();
  simulate();
  $('footer-date').textContent = new Date().toLocaleDateString('es-MX', { year: 'numeric', month: 'long', day: 'numeric' });
}

function renderHeader() {
  $('hdr-vanity').innerHTML = DATA.vanity ? ('&#128100; ' + esc(DATA.vanity)) : '';
  if (DATA.lastRefresh) {
    const d = new Date(DATA.lastRefresh);
    $('hdr-time').textContent = 'Actualizado: ' + d.toLocaleDateString('es-MX') + ' ' + d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
  }
}

function formatCacheAge(section) {
  if (!section || section.ageHours === null || section.ageHours === undefined) return 'sin cache';
  if (section.ageHours < 1) return '<1h';
  return section.ageHours + 'h';
}

function renderCachePill(label, section) {
  const count = section && Number.isFinite(section.count) ? section.count : 0;
  const stale = section && section.stale;
  const cls = stale ? 'cache-pill stale' : 'cache-pill';
  const ttl = section && section.ttlHours ? section.ttlHours + 'h TTL' : 'TTL n/d';
  return '<div class="' + cls + '"><span class="cache-label">' + esc(label) + '</span>' +
    count + ' items · edad ' + esc(formatCacheAge(section)) + ' · ' + esc(ttl) + '</div>';
}

function renderCacheStatus() {
  const el = $('cache-status-card');
  if (!el || !DATA) return;
  const status = DATA.cacheStatus || {};
  el.innerHTML = '<strong>Fuente/cache:</strong> ' + esc(status.source || 'Steam/cache local') +
    '<div class="cache-status-grid">' +
    renderCachePill('Catálogo DLC', status.catalog || {}) +
    renderCachePill('Nombres', status.names || {}) +
    renderCachePill('Precios', status.prices || {}) +
    renderCachePill('Bundles', status.bundles || {}) +
    '</div><div class="cache-diagnostic">' + esc(status.diagnostic || 'Usa “Forzar catálogo” solo si esperas DLCs nuevos o sospechas cache viejo.') + '</div>';
}

function renderBanners() {
  let html = '';
  const c = DATA.comparison || {};
  if (c.newSales || c.endedSales || c.priceDrops) {
    const parts = [];
    if (c.newSales) parts.push('<span class="comp-badge comp-green">' + c.newSales + ' nuevas ofertas</span>');
    if (c.endedSales) parts.push('<span class="comp-badge comp-red">' + c.endedSales + ' terminaron</span>');
    if (c.priceDrops) parts.push('<span class="comp-badge comp-blue">' + c.priceDrops + ' bajaron</span>');
    html += '<div class="comp-row">vs ' + esc(c.prevDate) + ': ' + parts.join(' ') + '</div>';
  }
  if (DATA.saleName) {
    html += '<div class="sale-banner">&#127991; ' + esc(DATA.saleName) + '</div>';
  }
  if (DATA.buyNow && DATA.buyNow.length > 0) {
    const items = DATA.buyNow.slice(0, 5).map(d =>
      '<a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name) + ' <small>-' + d.discount + '%</small></a>'
    ).join(' ');
    html += '<div class="rec-buy">&#128722; <strong>Comprar ahora:</strong> ' + items + '</div>';
  } else if (DATA.onSaleCount === 0 && DATA.missingCount > 0) {
    html += '<div class="rec-wait">&#9203; Sin ofertas activas &mdash; espera al <strong>Summer Sale</strong> (25 jun, ~75% off). Costo estimado: <strong>Mex$ ' + fmt(DATA.estSummer75) + '</strong></div>';
  }
  $('banners').innerHTML = html;
}

function renderStats() {
  const d = DATA;
  const savings = d.costOrig - d.costCurr;
  let html = '';
  html += '<div class="st gold"><div class="v">' + d.ownedCount + '/' + d.totalDlcs + '</div><div class="l">Posees</div></div>';
  html += '<div class="st"><div class="v">' + d.missingCount + '</div><div class="l">Faltan</div></div>';
  html += '<div class="st y"><div class="v">$' + fmt(d.costCurr) + '</div><div class="l">Costo actual</div></div>';
  if (savings > 0) {
    html += '<div class="st g"><div class="v">-$' + fmt(savings) + '</div><div class="l">Ahorro ofertas</div></div>';
  } else {
    html += '<div class="st"><div class="v">$' + fmt(d.costOrig) + '</div><div class="l">Precio normal</div></div>';
  }
  html += '<div class="st g"><div class="v">' + d.onSaleCount + '</div><div class="l">En oferta</div></div>';
  html += '<div class="st g"><div class="v">$' + fmt(d.estSummer75) + '</div><div class="l">Est. Summer 75%</div></div>';
  $('stats-grid').innerHTML = html;
}

function renderDonut() {
  const pct = DATA.totalDlcs > 0 ? Math.round(DATA.ownedCount / DATA.totalDlcs * 100) : 0;
  const offset = 440 - (440 * pct / 100);
  $('donut-fill').setAttribute('stroke-dashoffset', offset);
  $('donut-pct').textContent = pct + '%';
  $('donut-lbl').textContent = DATA.ownedCount + '/' + DATA.totalDlcs + ' DLCs';
}

function renderLegend() {
  const onSale = DATA.dlcs.filter(d => d.discount > 0).length;
  const fullPrice = DATA.dlcs.length - onSale;
  let html = '';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--accent)"></span>Poseidos: ' + DATA.ownedCount + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--green)"></span>En oferta: ' + onSale + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--text2)"></span>Precio normal: ' + fullPrice + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--red)"></span>Faltan: ' + DATA.missingCount + '</div>';
  $('legend').innerHTML = html;
}

function renderTable() {
  const sale = $('f-sale').value;
  const q = $('f-q').value.toLowerCase();

  let dlcs = DATA.dlcs.filter(d => {
    if (sale === 'y' && d.discount === 0) return false;
    if (sale === 'n' && d.discount > 0) return false;
    if (q && !d.name.toLowerCase().includes(q)) return false;
    return true;
  });

  dlcs.sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? (va - vb) : (vb - va);
  });

  document.querySelectorAll('.sort-arrow').forEach(el => { el.textContent = ''; });
  const arrow = $('sa-' + sortKey);
  if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';

  $('tbody').innerHTML = dlcs.map(d => {
    const disc = d.discount > 0 ? '<span class="sale-tag">-' + d.discount + '%</span>' : '&mdash;';
    const spark = sparkSvg(d.id);
    return '<tr data-id="' + d.id + '">' +
      '<td><input type="checkbox" class="chk" onchange="toggleOwned(\'' + d.id + '\')"></td>' +
      '<td><div class="dlc-cell"><img src="' + CAP + d.id + '/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\'none\'"><div class="dlc-info"><div class="dlc-name"><a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name) + '</a></div></div></div></td>' +
      '<td>' + esc(d.priceFmt) + '</td>' +
      '<td>' + disc + '</td>' +
      '<td>' + spark + '</td></tr>';
  }).join('');

  $('f-count').textContent = dlcs.length + '/' + DATA.dlcs.length + ' DLCs';
}

function doSort(key) {
  if (sortKey === key) sortAsc = !sortAsc;
  else { sortKey = key; sortAsc = (key === 'name'); }
  renderTable();
}

function sparkSvg(id) {
  const pts = DATA.history[id];
  if (!pts || pts.length < 2) return '';
  const max = Math.max(...pts);
  const min = Math.min(...pts);
  const range = max - min || 1;
  const w = 70;
  const h = 22;
  const step = w / (pts.length - 1);
  const coords = pts.map((p, i) => Math.round(i * step) + ',' + Math.round(h - 2 - (p - min) / range * (h - 4))).join(' ');
  return '<svg class="sparkline" viewBox="0 0 ' + w + ' ' + h + '"><polyline points="' + coords + '"/></svg>';
}

async function toggleOwned(appid) {
  showActionStatus('Guardando cambio del DLC...', 'loading');
  try {
    const r = await localMutableFetch('/api/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ appid }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    await r.json();
    await loadData();
    showActionStatus('DLC actualizado.', 'ok', {autoHide: true});
  } catch (e) {
    showActionStatus('No se pudo guardar el cambio del DLC: ' + e.message, 'error');
  }
}

async function unmarkOwned(appid) {
  await toggleOwned(appid);
}

function renderBundles() {
  const card = $('bundles-card');
  const grid = $('bundles-grid');
  if (!DATA.bundles || !DATA.bundles.length) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  grid.innerHTML = DATA.bundles.map(b => {
    const ownedInBundle = b.dlcAppids.filter(id => DATA.owned.some(o => o.id === id)).length;
    const allOwned = ownedInBundle === b.count;
    let btns = '';
    if (allOwned) {
      btns = '<button class="bcard-btn done" disabled>&#9989; Marcado</button>' +
        '<button class="bcard-btn" style="background:var(--red);margin-left:.3rem" onclick="unmarkBundle(\'' + b.id + '\')">Deshacer</button>';
    } else if (ownedInBundle > 0) {
      btns = '<button class="bcard-btn" onclick="markBundle(\'' + b.id + '\')">Marcar restantes</button>' +
        '<button class="bcard-btn" style="background:var(--red);margin-left:.3rem" onclick="unmarkBundle(\'' + b.id + '\')">Deshacer</button>';
    } else {
      btns = '<button class="bcard-btn" onclick="markBundle(\'' + b.id + '\')">Tengo este bundle</button>';
    }
    return '<div class="bcard">' +
      '<div class="bcard-info"><div class="bcard-name">' + esc(b.name) + '</div>' +
      '<div class="bcard-meta">' + b.count + ' DLCs &middot; ' + ownedInBundle + ' marcados</div></div>' +
      '<div style="display:flex;flex-wrap:wrap">' + btns + '</div></div>';
  }).join('');
}

async function markBundle(bundleId) {
  showActionStatus('Marcando DLCs del bundle...', 'loading');
  try {
    const r = await localMutableFetch('/api/toggle-bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleId, action: 'mark' }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    await r.json();
    await loadData();
    showActionStatus('Bundle actualizado.', 'ok', {autoHide: true});
  } catch (e) {
    showActionStatus('No se pudo marcar el bundle: ' + e.message, 'error');
  }
}

async function unmarkBundle(bundleId) {
  showActionStatus('Deshaciendo marcado del bundle...', 'loading');
  try {
    const r = await localMutableFetch('/api/toggle-bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleId, action: 'unmark' }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    await r.json();
    await loadData();
    showActionStatus('Bundle actualizado.', 'ok', {autoHide: true});
  } catch (e) {
    showActionStatus('No se pudo deshacer el bundle: ' + e.message, 'error');
  }
}

function renderOwned() {
  const el = $('owned-grid');
  $('owned-count-badge').textContent = DATA.owned.length;
  if (!DATA.owned.length) {
    el.innerHTML = '<p style="color:var(--text2);font-size:.85rem">No has marcado ningun DLC como comprado aun. Usa los checkboxes en la tabla de DLCs.</p>';
    return;
  }
  el.innerHTML = DATA.owned.map(d =>
    '<div class="owned-item"><img src="' + CAP + d.id + '/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\'none\'"><span>' + esc(d.name.replace(/PAYDAY 2:\s*/, '')) + '</span><button class="remove-btn" onclick="unmarkOwned(\'' + d.id + '\')" title="Desmarcar">&#10005;</button></div>'
  ).join('');
}

function simulate() {
  if (!DATA) return;
  const pct = parseInt($('sim-slider').value, 10);
  $('sim-pct').textContent = pct + '%';
  let total = 0;
  DATA.dlcs.forEach(d => {
    if (d.discount > 0) total += d.price;
    else total += d.orig * (1 - pct / 100);
  });
  total /= 100;
  const orig = DATA.dlcs.reduce((s, d) => s + d.orig, 0) / 100;
  const count = DATA.dlcs.length;
  $('sim-cost').textContent = 'Mex$ ' + fmt(Math.round(total));
  $('sim-save').textContent = 'Mex$ ' + fmt(Math.round(orig - total));
  $('sim-avg').textContent = count > 0 ? ('~Mex$ ' + fmt(Math.round(total / count)) + '/DLC') : '--';
}

function calcBudget() {
  const budget = parseFloat($('budget-input').value) || 0;
  if (budget <= 0) {
    $('budget-result').innerHTML = '<div class="budget-result">Ingresa un presupuesto mayor a 0</div>';
    return;
  }

  const sorted = [...DATA.dlcs].sort((a, b) =>
    (b.valueScore || 0) - (a.valueScore || 0) ||
    (b.importanceScore || 0) - (a.importanceScore || 0) ||
    b.discount - a.discount ||
    a.price - b.price
  );
  let remaining = budget;
  const picks = [];
  sorted.forEach(d => {
    const price = d.price / 100;
    if (price > 0 && price <= remaining) {
      picks.push(d);
      remaining -= price;
    }
  });

  const totalSpent = budget - remaining;
  let html = '<div class="budget-result">Con <strong>Mex$ ' + fmt(budget) + '</strong> puedes comprar <span class="val">' + picks.length + ' DLCs</span> por <span class="val">Mex$ ' + fmt(Math.round(totalSpent)) + '</span>, priorizando importancia y valor';
  if (remaining > 0) html += ' (sobran $' + fmt(Math.round(remaining)) + ')';
  html += '</div>';

  if (picks.length) {
    html += '<div class="budget-list">';
    picks.forEach(d => {
      const disc = d.discount > 0 ? ' <small style="color:var(--green)">-' + d.discount + '%</small>' : '';
      const tier = d.importanceTier || 'B';
      const reasons = (d.valueReasons && d.valueReasons.length ? d.valueReasons : [d.importanceLabel || 'Valor estimado']).slice(0, 2).join(' · ');
      html += '<div class="budget-item"><span class="bi-tier tier-' + esc(tier) + '" title="Prioridad ' + esc(tier) + '">' + esc(tier) + '</span><span class="bi-copy"><a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name.replace(/PAYDAY 2:\s*/, '')) + disc + '</a><small class="bi-reason">' + esc(reasons) + '</small></span><span class="bi-price">' + esc(d.priceFmt) + '</span></div>';
    });
    html += '</div>';
  }
  $('budget-result').innerHTML = html;
}

function renderSales() {
  if (!DATA.upcomingSales) return;
  $('sales-table').innerHTML = '<tr style="color:var(--text2);font-weight:600"><td>Evento</td><td>Fecha</td><td>Desc.</td><td>Costo estimado</td></tr>' +
    DATA.upcomingSales.map(s =>
      '<tr><td>' + esc(s.event) + '</td><td style="color:var(--text2)">' + esc(s.date) + '</td><td style="color:var(--yellow)">-' + s.discount + '%</td><td class="est">Mex$ ' + fmt(s.est) + '</td></tr>'
    ).join('');
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t, i) => {
    const panels = ['dlcs', 'tools', 'owned', 'settings'];
    t.classList.toggle('active', panels[i] === name);
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const panel = $('panel-' + name);
  if (panel) panel.classList.add('active');
}

async function doRefresh(options = {}) {
  const force = !!options.force;
  setRefreshButtonsBusy(true);
  showActionStatus(force ? 'Forzando actualización del catálogo PAYDAY 2 con --no-cache...' : 'Actualizando datos de PAYDAY 2... esto puede tardar 1-3 min.', 'loading');
  window._refreshStart = Date.now();

  const panel = $('refresh-panel');
  const consoleEl = $('console');
  panel.classList.add('visible');
  consoleEl.innerHTML = '';
  $('prog-bar').style.width = '0%';
  $('prog-bar').style.background = 'linear-gradient(90deg, var(--gold), #b8922e)';
  $('prog-text').textContent = 'Iniciando... (puede tardar 1-3 min con cache vacio)';
  appendConsole(force ? 'Preparando actualización forzada de catálogo (--no-cache)...' : 'Preparando actualización de datos...', 'step');

  try {
    const resp = await localMutableFetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(force ? { force: true } : {}),
    });
    if (resp.status === 409) {
      appendConsole('Ya hay una actualizacion en curso.', 'warn');
      showActionStatus('Ya hay una actualización en curso.', 'warn');
      setRefreshButtonsBusy(false);
      return;
    }
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split('\n')) {
          if (line.startsWith('data: ')) {
            try { handleSSE(JSON.parse(line.slice(6))); } catch (e) {}
          }
        }
      }
    }
  } catch (e) {
    appendConsole('Error: ' + e.message, 'err');
    showActionStatus('No se pudo actualizar PAYDAY 2: ' + e.message, 'error');
  }

  setRefreshButtonsBusy(false);
  await loadData();
  if (!DATA || !DATA.totalDlcs) {
    location.reload();
  }
}

function doForceRefresh() {
  return doRefresh({ force: true });
}

function handleSSE(ev) {
  if (ev.type === 'line') {
    appendConsole(ev.text, ev.cls || 'normal');
  } else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    $('prog-bar').style.width = pct + '%';
    let eta = '';
    if (ev.current > 1 && window._refreshStart) {
      const elapsed = (Date.now() - window._refreshStart) / 1000;
      const remaining = (elapsed / ev.current) * (ev.total - ev.current);
      if (remaining > 60) eta = ' ~' + Math.round(remaining / 60) + 'min';
      else if (remaining > 5) eta = ' ~' + Math.round(remaining) + 's';
    }
    $('prog-text').textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label + eta;
  } else if (ev.type === 'done') {
    $('prog-bar').style.width = '100%';
    if (ev.exit_code === 0) {
      $('prog-text').textContent = 'Completado!';
      $('prog-bar').style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
      showActionStatus('Actualización completada.', 'ok', {autoHide: true});
      setTimeout(() => { $('refresh-panel').classList.remove('visible'); }, 3000);
    } else {
      $('prog-text').textContent = 'Error (codigo ' + ev.exit_code + ')';
      $('prog-bar').style.background = 'linear-gradient(90deg, var(--red), #a02020)';
      showActionStatus('La actualización terminó con error. Revisa el log del panel.', 'error');
    }
  }
}

function appendConsole(text, cls) {
  const div = document.createElement('div');
  div.className = 'line line-' + (cls || 'normal');
  div.textContent = text;
  $('console').appendChild(div);
  $('console').scrollTop = $('console').scrollHeight;
}

async function saveConfig() {
  const btn = $('btn-save-config');
  const cfg = {};
  const v = $('cfg-vanity').value.trim(); if (v) cfg.vanity = v;
  const k = $('cfg-key').value.trim(); if (k) cfg.key = k;
  const i = $('cfg-itad').value.trim(); if (i) cfg.itad_key = i;
  setButtonBusy(btn, true);
  showActionStatus('Guardando configuración...', 'loading');
  try {
    const resp = await localMutableFetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    $('cfg-status').textContent = 'Guardado! Haz click en "Actualizar datos" para aplicar.';
    showActionStatus('Configuración guardada. Usa “Actualizar datos” para refrescar.', 'ok', {autoHide: true});
    setTimeout(() => { $('cfg-status').textContent = ''; }, 4000);
  } catch (e) {
    $('cfg-status').textContent = 'Error al guardar';
    $('cfg-status').style.color = 'var(--red)';
    showActionStatus('No se pudo guardar configuración: ' + e.message, 'error');
  } finally {
    setButtonBusy(btn, false);
  }
}

async function quickSetup() {
  const btn = $('btn-setup');
  const v = $('setup-vanity').value.trim();
  const k = $('setup-key').value.trim();
  if (!v) {
    $('setup-vanity').style.borderColor = 'var(--red)';
    $('setup-vanity').focus();
    showActionStatus('Ingresa tu perfil de Steam para cargar los DLCs.', 'warn');
    setTimeout(() => { $('setup-vanity').style.borderColor = ''; }, 2000);
    return;
  }
  const cfg = { vanity: v };
  if (k) cfg.key = k;
  setButtonBusy(btn, true);
  showActionStatus('Guardando perfil y preparando carga de datos...', 'loading');
  try {
    const resp = await localMutableFetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    $('cfg-vanity').value = v;
    if (k) $('cfg-key').value = k;
    $('empty-state').style.display = 'none';
    $('dashboard').style.display = 'block';
    await doRefresh();
  } catch (e) {
    showActionStatus('No se pudo iniciar la carga: ' + e.message, 'error');
  } finally {
    setButtonBusy(btn, false);
  }
}

loadData();
