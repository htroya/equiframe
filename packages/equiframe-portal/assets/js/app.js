/* EquiFrame Portal — SPA logic */
'use strict';

function copyInstall(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '¡Copiado!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copiar'; btn.classList.remove('copied'); }, 2000);
  }).catch(() => {
    btn.textContent = 'Error';
    setTimeout(() => { btn.textContent = 'Copiar'; }, 2000);
  });
}

// ── Capa de datos (sintético ↔ API real) ─────────────────────────────────

const DS = {
  async indicadores(filtros = {}) {
    if (!EQ_CONFIG.useRealApi) return EQ.indicadores;
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, ...filtros });
    return _get(`/indicadores?${q}`);
  },
  async serieTemporal(filtros = {}) {
    if (!EQ_CONFIG.useRealApi) return EQ.serie_temporal;
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, ...filtros });
    return _get(`/serie-temporal?${q}`);
  },
  async topEntidades(limit = 10) {
    if (!EQ_CONFIG.useRealApi) return EQ.top_entidades;
    return _get(`/entidades/top?snapshot=${EQ_CONFIG.snapshotId}&limit=${limit}`);
  },
  async adjudicaciones(filtros = {}, page = 0, size = 50) {
    if (!EQ_CONFIG.useRealApi) {
      let data = [...EQ.adjudicaciones];
      if (filtros.estado)      data = data.filter(a => a.estado    === filtros.estado);
      if (filtros.entidad)     data = data.filter(a => a.entidad   === filtros.entidad);
      if (filtros.modalidad)   data = data.filter(a => a.modalidad === filtros.modalidad);
      if (filtros.fecha_desde) data = data.filter(a => a.fecha >= filtros.fecha_desde);
      if (filtros.fecha_hasta) data = data.filter(a => a.fecha <= filtros.fecha_hasta);
      return { total: data.length, page, size, items: data.slice(page*size, page*size+size) };
    }
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, page, size, ...filtros });
    return _get(`/adjudicaciones?${q}`);
  },
  async procedimientos(filtros = {}, page = 0, size = 50) {
    if (!EQ_CONFIG.useRealApi) {
      let data = [...EQ.procedimientos];
      if (filtros.estado)      data = data.filter(p => p.estado    === filtros.estado);
      if (filtros.entidad)     data = data.filter(p => p.entidad   === filtros.entidad);
      if (filtros.modalidad)   data = data.filter(p => p.modalidad === filtros.modalidad);
      if (filtros.fecha_desde) data = data.filter(p => p.fecha_publicacion >= filtros.fecha_desde);
      if (filtros.fecha_hasta) data = data.filter(p => p.fecha_publicacion <= filtros.fecha_hasta);
      return { total: data.length, page, size, items: data.slice(page*size, page*size+size) };
    }
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, page, size, ...filtros });
    return _get(`/procedimientos?${q}`);
  },
  async montosPorMoneda(filtros = {}) {
    if (!EQ_CONFIG.useRealApi) return EQ.montos_por_moneda;
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, ...filtros });
    return _get(`/montos-por-moneda?${q}`);
  },
  async ejecutarComparacion(params) {
    if (!EQ_CONFIG.useRealApi) {
      await new Promise(r => setTimeout(r, 1800 + Math.random() * 1200));
      return _simularComparacion(params);
    }
    return _post('/comparaciones', params);
  },
  async estadoComparacion(runId) {
    if (!EQ_CONFIG.useRealApi) return null;
    return _get(`/comparaciones/${runId}`);
  },
};

async function _get(path) {
  const res = await fetch(EQ_CONFIG.apiUrl + path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.mensaje || `HTTP ${res.status}`);
  }
  return res.json();
}

async function _post(path, body) {
  const res = await fetch(EQ_CONFIG.apiUrl + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.mensaje || `HTTP ${res.status}: ${err.detail || res.statusText}`);
  }
  return res.json();
}

function _simularComparacion({ pareja, familia, muestra, snapshot }) {
  const ts = Date.now();
  const runId = `run-${snapshot}-${String(ts).slice(-6)}`;
  const filas = parseInt(muestra) || 183891;
  const seed = pareja.charCodeAt(0) + familia.charCodeAt(0);

  // Resultados deterministas por pareja+familia para reproducibilidad demostrativa
  const escenarios = {
    'pandas_polars:ausencias_tipos': { resultado: 'OK',            diferencias: 0, advertencias: [] },
    'pandas_polars:uniones':         { resultado: 'OK_CON_ADVERTENCIA', diferencias: 0,
      advertencias: ['Polars no garantiza orden de filas sin ORDER BY. Usar contrato con orden_explícito: true para validar.'] },
    'pandas_polars:agregaciones':    { resultado: 'OK',            diferencias: 0, advertencias: [] },
    'pandas_duckdb:ausencias_tipos': { resultado: 'DIVERGENCIA',   diferencias: 3,
      diffs: [
        { clave: 'ocds-lcuori-001012', campo: 'ocid',              tipo: 'tipo_dato',    origen: '"001012" (str)', destino: '1012 (int)' },
        { clave: 'ocds-lcuori-001012', campo: 'fecha_adjudicacion',tipo: 'zona_horaria', origen: '2025-03-15T00:00:00-05:00', destino: '2025-03-15T05:00:00Z' },
        { clave: 'ocds-lcuori-001035', campo: 'monto',             tipo: 'precision',    origen: '1234567.89', destino: '1234567.9' },
      ] },
    'pandas_duckdb:uniones':         { resultado: 'DIVERGENCIA',   diferencias: 1,
      diffs: [
        { clave: 'N/A', campo: 'conteo_filas', tipo: 'cardinalidad', origen: '183 891 (LEFT JOIN)', destino: '183 888 (INNER JOIN — 3 proveedores sin match)' },
      ] },
    'pandas_duckdb:agregaciones':    { resultado: 'DIVERGENCIA',   diferencias: 1,
      diffs: [
        { clave: 'IESS', campo: 'monto_sum', tipo: 'precision', origen: '612300000.00', destino: '612300000.01' },
      ] },
    'polars_duckdb:ausencias_tipos': { resultado: 'OK',            diferencias: 0, advertencias: [] },
    'polars_duckdb:uniones':         { resultado: 'OK',            diferencias: 0, advertencias: [] },
    'polars_duckdb:agregaciones':    { resultado: 'DIVERGENCIA',   diferencias: 1,
      diffs: [
        { clave: 'IESS', campo: 'monto_sum', tipo: 'precision', origen: '612300000.01', destino: '612300000.01' },
      ] },
  };

  const key = `${pareja}:${familia}`;
  const esc = escenarios[key] || { resultado: 'OK', diferencias: 0, advertencias: [] };
  const tiempo_s = +(2.1 + seed % 8 + Math.random() * 2).toFixed(2);

  return {
    run_id:      runId,
    snapshot:    snapshot,
    pareja:      pareja.replace('_', '→').replace('pandas', 'Pandas').replace('polars', 'Polars').replace('duckdb', 'DuckDB'),
    familia:     familia,
    muestra:     filas,
    filas:       filas,
    resultado:   esc.resultado,
    diferencias: esc.diferencias,
    advertencias: esc.advertencias || [],
    diffs:       esc.diffs || [],
    tiempo_s,
    memoria_mb:  +(seed % 120 + 40 + Math.random() * 30).toFixed(1),
    fecha:       new Date().toISOString().slice(0, 10),
  };
}

function _mostrarError(msg) {
  const banner = document.getElementById('api-error');
  if (!banner) return;
  banner.textContent = '⚠ ' + msg;
  banner.hidden = false;
  setTimeout(() => { banner.hidden = true; }, 8000);
}

// ── Router ────────────────────────────────────────────────────────────────

let currentPage = 'inicio';
let chartsInited = false;
let chartSerie, chartEntidades;

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  const link = document.querySelector(`[data-page="${name}"]`);
  if (link) link.classList.add('active');
  currentPage = name;
  window.location.hash = name;
  if (name === 'explorar' && !chartsInited) initExplorar();
  if (name === 'demos')      initDemos();
  if (name === 'resultados') initResultados();
  if (name === 'proyecto')   initProyecto();
}

document.querySelectorAll('.nav-link').forEach(btn => {
  btn.addEventListener('click', () => showPage(btn.dataset.page));
});

// Hash routing
window.addEventListener('hashchange', () => {
  const h = window.location.hash.replace('#', '') || 'inicio';
  showPage(h);
});

// ── Formateadores ─────────────────────────────────────────────────────────

function fmt(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + ' B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + ' M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + ' K';
  return n.toLocaleString('es-EC');
}
function fmtUSD(n) {
  return new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}
function fmtNum(n) {
  return new Intl.NumberFormat('es-EC').format(n);
}
function estadoBadge(e) {
  const map = { active:'badge-blue', complete:'badge-ok', cancelled:'badge-err', pending:'badge-warn' };
  const lbl = { active:'Activo', complete:'Completado', cancelled:'Cancelado', pending:'Pendiente' };
  return `<span class="badge ${map[e] || ''}">${lbl[e] || e}</span>`;
}
function resultadoBadge(r) {
  const map = { OK:'badge-ok', DIVERGENCIA:'badge-err', OK_CON_ADVERTENCIA:'badge-warn', DIVERGENCIA_PARCIAL:'badge-warn' };
  return `<span class="badge ${map[r] || 'badge-purple'}">${r.replace(/_/g,' ')}</span>`;
}

// ── EXPLORAR ─────────────────────────────────────────────────────────────

let paginaActual    = 0;
let paginaProc      = 0;
const POR_PAGINA    = 10;
let adjFiltradas    = [];
let procFiltradas   = [];
let _totalFiltrado  = 0;
let _totalProc      = 0;
let vistaActual     = 'adj';

async function initExplorar() {
  chartsInited = true;

  try {
    const entidades = await DS.topEntidades(50);
    const sel = document.getElementById('f-entidad');
    entidades.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.entidad; opt.textContent = e.entidad;
      sel.appendChild(opt);
    });
  } catch (e) { _mostrarError(e.message); }

  ['f-snapshot','f-entidad','f-estado','f-modalidad','f-fecha-desde','f-fecha-hasta'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', aplicarFiltros);
  });

  try {
    const ind = await DS.indicadores();
    renderKPIs(ind);
  } catch (e) { _mostrarError(e.message); }

  await renderCharts();
  await aplicarFiltros();
}

function _getFiltros() {
  const filtros = {};
  const estado    = document.getElementById('f-estado')?.value;
  const entidad   = document.getElementById('f-entidad')?.value;
  const modalidad = document.getElementById('f-modalidad')?.value;
  const desde     = document.getElementById('f-fecha-desde')?.value;
  const hasta     = document.getElementById('f-fecha-hasta')?.value;
  if (estado)    filtros.estado      = estado;
  if (entidad)   filtros.entidad     = entidad;
  if (modalidad) filtros.modalidad   = modalidad;
  if (desde)     filtros.fecha_desde = desde;
  if (hasta)     filtros.fecha_hasta = hasta;
  return filtros;
}

function limpiarFiltros() {
  ['f-entidad','f-estado','f-modalidad'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const desde = document.getElementById('f-fecha-desde');
  const hasta  = document.getElementById('f-fecha-hasta');
  if (desde) desde.value = '2025-01-01';
  if (hasta)  hasta.value  = '2025-12-31';
  aplicarFiltros();
}

async function aplicarFiltros() {
  const filtros = _getFiltros();
  try {
    if (vistaActual === 'adj' || vistaActual !== 'monedas') {
      const resp = await DS.adjudicaciones(filtros, 0, POR_PAGINA);
      adjFiltradas   = resp.items;
      _totalFiltrado = resp.total;
      paginaActual   = 0;
      renderTabla();
    }
    if (vistaActual === 'proc') {
      const resp = await DS.procedimientos(filtros, 0, POR_PAGINA);
      procFiltradas = resp.items;
      _totalProc    = resp.total;
      paginaProc    = 0;
      renderTablaProc();
    }
    if (vistaActual === 'monedas') {
      const data = await DS.montosPorMoneda(filtros);
      renderMonedas(data);
    }
  } catch (e) { _mostrarError(e.message); }
}

function switchView(v) {
  vistaActual = v;
  document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('vtab-' + v)?.classList.add('active');
  document.getElementById('view-' + v)?.classList.add('active');
  aplicarFiltros();
}

function renderKPIs(ind) {
  const grid = document.getElementById('kpi-grid');
  grid.innerHTML = `
    <div class="kpi kpi-blue">
      <span class="kpi-icon">📋</span>
      <div class="kpi-label">Total adjudicaciones</div>
      <div class="kpi-value">${fmtNum(ind.total_adjudicaciones)}</div>
      <div class="kpi-sub">Corpus SERCOP 2025</div>
    </div>
    <div class="kpi kpi-green">
      <span class="kpi-icon">💰</span>
      <div class="kpi-label">Monto total</div>
      <div class="kpi-value">${fmt(ind.monto_total_usd)}</div>
      <div class="kpi-sub">Dólares USD</div>
    </div>
    <div class="kpi kpi-purple">
      <span class="kpi-icon">🏛️</span>
      <div class="kpi-label">Entidades únicas</div>
      <div class="kpi-value">${fmtNum(ind.entidades_unicas)}</div>
      <div class="kpi-sub">Compradores públicos</div>
    </div>
    <div class="kpi kpi-orange">
      <span class="kpi-icon">🏢</span>
      <div class="kpi-label">Proveedores únicos</div>
      <div class="kpi-value">${fmtNum(ind.proveedores_unicos)}</div>
      <div class="kpi-sub">Adjudicatarios</div>
    </div>`;
}

async function renderCharts() {
  const accent = '#2563eb';
  const accentL = '#93c5fd';
  const gris = '#94a3b8';

  let serie, topEnt;
  try {
    [serie, topEnt] = await Promise.all([DS.serieTemporal(), DS.topEntidades(5)]);
  } catch (e) { _mostrarError(e.message); return; }

  // Destruir instancias previas si las hay (al re-aplicar filtros)
  if (chartSerie)    { chartSerie.destroy();    chartSerie    = null; }
  if (chartEntidades){ chartEntidades.destroy(); chartEntidades = null; }

  // Serie temporal
  const ctxSerie = document.getElementById('chart-serie').getContext('2d');
  chartSerie = new Chart(ctxSerie, {
    type: 'line',
    data: {
      labels: serie.map(d => d.mes),
      datasets: [{
        label: 'Monto USD',
        data: serie.map(d => d.monto),
        borderColor: accent,
        backgroundColor: 'rgba(37,99,168,.08)',
        tension: .3, fill: true,
        pointRadius: 3, pointBackgroundColor: accent,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, color: gris, maxRotation: 45 } },
        y: { grid: { color: 'rgba(0,0,0,.04)' }, ticks: { font: { size: 10 }, color: gris,
          callback: v => fmt(v) } }
      }
    }
  });

  // Top entidades
  const ctxEnt = document.getElementById('chart-entidades').getContext('2d');
  const top5 = topEnt.slice(0, 5);
  chartEntidades = new Chart(ctxEnt, {
    type: 'bar',
    data: {
      labels: top5.map(e => e.entidad.split(' ').slice(0,3).join(' ')),
      datasets: [{
        label: 'Monto USD',
        data: top5.map(e => e.monto),
        backgroundColor: [accent, accentL, '#1e40af','#3b82f6','#60a5fa'],
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(0,0,0,.04)' }, ticks: { font: { size: 10 }, color: gris,
          callback: v => fmt(v) } },
        y: { grid: { display: false }, ticks: { font: { size: 10 }, color: gris } }
      }
    }
  });
}

function renderTabla() {
  const tbody = document.getElementById('tbody-adj');
  if (!tbody) return;
  const fmtMonto = n => new Intl.NumberFormat('es-EC',{minimumFractionDigits:2}).format(n);
  tbody.innerHTML = adjFiltradas.map(a => `
    <tr>
      <td class="mono">${a.ocid}</td>
      <td>${a.entidad}</td>
      <td>${a.proveedor}</td>
      <td class="num">${fmtMonto(a.monto)}</td>
      <td>${a.moneda}</td>
      <td>${a.fecha}</td>
      <td>${estadoBadge(a.estado)}</td>
      <td>${a.modalidad}</td>
    </tr>`).join('') || '<tr><td colspan="8" style="text-align:center;color:var(--fg-3);padding:20px">Sin resultados</td></tr>';
  const countEl = document.getElementById('adj-count');
  if (countEl) countEl.textContent = `${fmtNum(_totalFiltrado)} adjudicaciones · snapshot ${EQ_CONFIG.snapshotId}`;
  renderPaginacion();
}

function renderPaginacion() {
  const total = Math.ceil(_totalFiltrado / POR_PAGINA);
  const pg = document.getElementById('paginacion');
  if (!pg) return;
  pg.innerHTML = `
    <button onclick="irPagina(${paginaActual-1})" ${paginaActual===0?'disabled':''}>‹ Ant.</button>
    <span>Pág. ${paginaActual+1} / ${total||1}</span>
    <button onclick="irPagina(${paginaActual+1})" ${paginaActual>=total-1?'disabled':''}>Sig. ›</button>`;
}

async function irPagina(n) {
  const total = Math.ceil(_totalFiltrado / POR_PAGINA);
  if (n < 0 || n >= total) return;
  paginaActual = n;
  try {
    const resp = await DS.adjudicaciones(_getFiltros(), n, POR_PAGINA);
    adjFiltradas = resp.items;
    renderTabla();
  } catch (e) { _mostrarError(e.message); }
}

function renderTablaProc() {
  const tbody = document.getElementById('tbody-proc');
  if (!tbody) return;
  const fmtMonto = n => new Intl.NumberFormat('es-EC',{minimumFractionDigits:2}).format(n);
  tbody.innerHTML = procFiltradas.map(p => `
    <tr>
      <td class="mono">${p.ocid}</td>
      <td>${p.entidad}</td>
      <td>${p.objeto}</td>
      <td>${p.modalidad}</td>
      <td class="num">${fmtMonto(p.monto_referencial)}</td>
      <td>${p.fecha_publicacion}</td>
      <td>${p.fecha_adjudicacion || '—'}</td>
      <td>${estadoBadge(p.estado)}</td>
    </tr>`).join('') || '<tr><td colspan="8" style="text-align:center;color:var(--fg-3);padding:20px">Sin resultados</td></tr>';
  const countEl = document.getElementById('proc-count');
  if (countEl) countEl.textContent = `${fmtNum(_totalProc)} procedimientos · snapshot ${EQ_CONFIG.snapshotId}`;
  renderPaginacionProc();
}

function renderPaginacionProc() {
  const total = Math.ceil(_totalProc / POR_PAGINA);
  const pg = document.getElementById('paginacion-proc');
  if (!pg) return;
  pg.innerHTML = `
    <button onclick="irPaginaProc(${paginaProc-1})" ${paginaProc===0?'disabled':''}>‹ Ant.</button>
    <span>Pág. ${paginaProc+1} / ${total||1}</span>
    <button onclick="irPaginaProc(${paginaProc+1})" ${paginaProc>=total-1?'disabled':''}>Sig. ›</button>`;
}

async function irPaginaProc(n) {
  const total = Math.ceil(_totalProc / POR_PAGINA);
  if (n < 0 || n >= total) return;
  paginaProc = n;
  try {
    const resp = await DS.procedimientos(_getFiltros(), n, POR_PAGINA);
    procFiltradas = resp.items;
    renderTablaProc();
  } catch (e) { _mostrarError(e.message); }
}

function renderMonedas(data) {
  const grid = document.getElementById('monedas-grid');
  if (!grid) return;
  const fmtMonto = n => new Intl.NumberFormat('es-EC',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  grid.innerHTML = `
    <p class="monedas-snap">Snapshot: ${EQ_CONFIG.snapshotId}</p>
    ${data.map(m => `
    <div class="moneda-card">
      <div class="moneda-codigo">${m.codigo}</div>
      <div class="moneda-desc">${m.descripcion}</div>
      <div class="moneda-monto">${fmtMonto(m.monto_total)}</div>
      <div class="moneda-meta">
        <span>${fmtNum(m.total_adjudicaciones)} adjudicaciones</span>
        <span class="moneda-pct">${m.porcentaje.toFixed(2)} %</span>
      </div>
      <div class="moneda-bar"><div class="moneda-bar-fill" style="width:${m.porcentaje}%"></div></div>
    </div>`).join('')}`;
}

async function exportCSV() {
  const cols = ['ocid','entidad','proveedor','monto','moneda','fecha','estado','modalidad'];
  let allRows;
  if (!EQ_CONFIG.useRealApi) {
    allRows = EQ.adjudicaciones;
  } else {
    try {
      const PAGE_SIZE = 500;
      allRows = [];
      let page = 0;
      while (true) {
        const resp = await DS.adjudicaciones(_getFiltros(), page, PAGE_SIZE);
        allRows = allRows.concat(resp.items);
        if (allRows.length >= resp.total) break;
        page++;
      }
    } catch (e) { _mostrarError(e.message); return; }
  }

  const header = cols.join(',');
  const rows = allRows.map(a => cols.map(c => `"${a[c] ?? ''}"`).join(','));
  const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'adjudicaciones_sercop_2025.csv';
  a.click(); URL.revokeObjectURL(url);
}

async function exportProcCSV() {
  const cols = ['ocid','entidad','objeto','modalidad','monto_referencial','fecha_publicacion','fecha_adjudicacion','estado'];
  const allRows = EQ_CONFIG.useRealApi ? [] : EQ.procedimientos;
  const header = cols.join(',');
  const rows = allRows.map(p => cols.map(c => `"${p[c] ?? ''}"`).join(','));
  const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'procedimientos_sercop_2025.csv';
  a.click(); URL.revokeObjectURL(url);
}

// ── COMPARAR ─────────────────────────────────────────────────────────────

document.querySelectorAll('.cmp-radio input[type="radio"]').forEach(radio => {
  radio.addEventListener('change', () => {
    radio.closest('.cmp-radio-group')
         .querySelectorAll('.cmp-radio')
         .forEach(l => l.classList.toggle('active', l.querySelector('input') === radio));
  });
});

async function ejecutarComparacion() {
  const pareja   = document.querySelector('input[name="pareja"]:checked')?.value;
  const familia  = document.querySelector('input[name="familia"]:checked')?.value;
  const muestra  = document.getElementById('cmp-muestra')?.value;
  const snapshot = document.getElementById('cmp-snapshot')?.value || EQ_CONFIG.snapshotId;

  if (!pareja || !familia) { _mostrarError('Selecciona pareja y familia.'); return; }

  _setCmpEstado('spinner', 'Enviando solicitud…');
  const btn = document.getElementById('cmp-ejecutar');
  if (btn) btn.disabled = true;

  try {
    if (EQ_CONFIG.useRealApi) _setCmpEstado('spinner', 'Ejecutando en el backend…');
    const res = await DS.ejecutarComparacion({ pareja, familia, muestra, snapshot });
    renderResultadoComparacion(res);
  } catch (e) {
    renderResultadoComparacion({ resultado: 'ERROR', error: e.message, run_id: null });
  } finally {
    if (btn) btn.disabled = false;
  }
}

function _setCmpEstado(estado, msg) {
  const inicial  = document.getElementById('cmp-estado-inicial');
  const spinner  = document.getElementById('cmp-spinner');
  const resultado = document.getElementById('cmp-resultado');
  const spinMsg  = document.getElementById('cmp-spinner-msg');

  inicial.hidden   = true;
  spinner.hidden   = true;
  resultado.hidden = true;

  if (estado === 'spinner') { spinner.hidden = false; if (spinMsg) spinMsg.textContent = msg || 'Ejecutando…'; }
  if (estado === 'resultado') resultado.hidden = false;
  if (estado === 'inicial')  inicial.hidden   = false;
}

function renderResultadoComparacion(r) {
  _setCmpEstado('resultado');

  const cfgBanner = {
    OK:                 { cls: 'ok',      icono: '✓', titulo: 'Equivalencia confirmada',          sub: 'Las dos implementaciones producen resultados semánticamente equivalentes.' },
    OK_CON_ADVERTENCIA: { cls: 'warn',    icono: '⚠', titulo: 'Equivalente con advertencias',    sub: 'Los resultados son equivalentes pero hay comportamientos a revisar.' },
    DIVERGENCIA:        { cls: 'err',     icono: '✗', titulo: 'Divergencia detectada',           sub: 'Se encontraron diferencias semánticas entre las dos implementaciones.' },
    INCOMPLETO:         { cls: 'partial', icono: '◑', titulo: 'Evaluación incompleta',           sub: 'No fue posible completar la comparación. Ver motivo abajo.' },
    ERROR:              { cls: 'err',     icono: '!', titulo: 'Error durante la ejecución',      sub: 'EquiFrame no pudo completar la comparación. Revisa el mensaje de error.' },
  };
  const cfg = cfgBanner[r.resultado] || cfgBanner.ERROR;

  const banner = document.getElementById('cmp-banner');
  banner.className = `cmp-banner cmp-banner-${cfg.cls}`;
  document.getElementById('cmp-banner-icono').textContent  = cfg.icono;
  document.getElementById('cmp-banner-titulo').textContent = cfg.titulo;
  document.getElementById('cmp-banner-sub').textContent    = cfg.sub;

  // Métricas
  const metricas = document.getElementById('cmp-metricas');
  if (r.run_id) {
    metricas.innerHTML = [
      { label: 'Filas', val: r.filas ? fmtNum(r.filas) : '—' },
      { label: 'Diferencias', val: r.diferencias !== undefined ? fmtNum(r.diferencias) : '—' },
      { label: 'Tiempo', val: r.tiempo_s ? `${r.tiempo_s} s` : '—' },
      { label: 'Memoria', val: r.memoria_mb ? `${r.memoria_mb} MB` : '—' },
    ].map(m => `<div class="cmp-metrica"><div class="cmp-metrica-val">${m.val}</div><div class="cmp-metrica-lbl">${m.label}</div></div>`).join('');
  } else {
    metricas.innerHTML = '';
  }

  // Error comprensible
  const errBox = document.getElementById('cmp-error-box');
  if (r.error) {
    const msgs = {
      'Connection refused':      'No se pudo conectar con el backend. ¿Está la VM encendida y la API activa?',
      'HTTP 503':                'El servicio no está disponible en este momento. Intenta de nuevo en unos segundos.',
      'HTTP 422':                'Los parámetros enviados no son válidos. Revisa pareja y familia seleccionadas.',
      'snapshot no encontrado':  'El snapshot solicitado no existe en el DW. Verifica que Jhair haya cargado los datos.',
      'timeout':                 'La comparación tardó demasiado. Prueba con una muestra más pequeña.',
    };
    const key = Object.keys(msgs).find(k => r.error.includes(k));
    errBox.hidden = false;
    errBox.innerHTML = `<strong>Qué ocurrió:</strong> ${msgs[key] || r.error}<br><small style="color:var(--fg-3);margin-top:6px;display:block">Técnico: ${r.error}</small>`;
  } else {
    errBox.hidden = true;
  }

  // Advertencias
  const advBox = document.getElementById('cmp-advertencias');
  if (r.advertencias && r.advertencias.length) {
    advBox.hidden = false;
    advBox.innerHTML = '<strong>Advertencias:</strong><ul style="margin-top:6px;padding-left:18px">' +
      r.advertencias.map(a => `<li style="font-size:13px;margin-bottom:4px">${a}</li>`).join('') + '</ul>';
  } else {
    advBox.hidden = true;
  }

  // Tabla de diferencias
  const diffsSection = document.getElementById('cmp-diffs-section');
  const diffsTbody   = document.getElementById('cmp-diffs-tbody');
  if (r.diffs && r.diffs.length) {
    diffsSection.hidden = false;
    diffsTbody.innerHTML = r.diffs.map(d => `
      <tr>
        <td class="mono">${d.clave}</td>
        <td class="mono">${d.campo}</td>
        <td><span class="badge ${d.tipo === 'cardinalidad' ? 'badge-err' : d.tipo === 'precision' ? 'badge-warn' : 'badge-purple'}">${d.tipo}</span></td>
        <td style="color:var(--ok)">${d.origen}</td>
        <td style="color:var(--err)">${d.destino}</td>
      </tr>`).join('');
  } else {
    diffsSection.hidden = true;
  }

  // Trazabilidad
  const trace = document.getElementById('cmp-trace');
  if (r.run_id) {
    trace.innerHTML = `
      <span>run_id: <code>${r.run_id}</code></span>
      <span>snapshot: <code>${r.snapshot || EQ_CONFIG.snapshotId}</code></span>
      ${r.pareja  ? `<span>pareja: <code>${r.pareja}</code></span>` : ''}
      ${r.familia ? `<span>familia: <code>${r.familia}</code></span>` : ''}
      ${r.fecha   ? `<span>fecha: <code>${r.fecha}</code></span>` : ''}`;
  } else {
    trace.innerHTML = '';
  }
}

// ── DEMOS ─────────────────────────────────────────────────────────────────

function initDemos() {
  const grid = document.getElementById('demo-grid');
  if (grid.dataset.inited) return;
  grid.dataset.inited = '1';

  const casos = Object.entries(EQ.demos);
  grid.innerHTML = casos.map(([key, d]) => `
    <div class="demo-card" data-key="${key}" onclick="selectDemo('${key}')">
      <h3>${d.titulo}</h3>
      <p>${d.descripcion.slice(0, 90)}…</p>
      <div style="margin-top:8px;display:flex;gap:6px">
        ${resultadoBadge(d.resultado)}
        <span class="badge badge-purple">${d.tipo_datos}</span>
      </div>
    </div>`).join('');
}

function selectDemo(key) {
  document.querySelectorAll('.demo-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector(`[data-key="${key}"]`);
  if (card) card.classList.add('selected');

  const d = EQ.demos[key];
  const det = document.getElementById('demo-detail');
  det.style.display = 'block';
  det.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  document.getElementById('demo-titulo').textContent = d.titulo;
  document.getElementById('demo-tipo-badge').innerHTML =
    `<span class="badge badge-purple">${d.tipo_datos}</span>`;
  document.getElementById('demo-resultado-badge').innerHTML = resultadoBadge(d.resultado);
  document.getElementById('demo-desc').textContent = d.descripcion;

  // Tabs
  const tabNames = ['Resumen','Datos','Contrato','Diferencias','Detalle técnico'];
  const tabs  = document.getElementById('demo-tabs');
  const panels = document.getElementById('demo-panels');
  tabs.innerHTML   = tabNames.map((t,i) =>
    `<button class="tab ${i===0?'active':''}" onclick="switchTab(this,${i})">${t}</button>`).join('');
  panels.innerHTML = tabNames.map((t,i) =>
    `<div class="tab-panel ${i===0?'active':''}" id="dp-${i}"></div>`).join('');

  // Resumen
  document.getElementById('dp-0').innerHTML = `
    <p><b>Motor origen:</b> ${d.motor_origen} &nbsp;→&nbsp; <b>Destino:</b> ${d.motor_destino || d.motor_destino || (d.parejas ? d.parejas.join(', ') : '—')}</p>
    <p style="margin-top:8px"><b>Resultado:</b> ${resultadoBadge(d.resultado)}</p>
    ${d.resumen ? `<div style="margin-top:12px">${renderResumenParejas(d.resumen)}</div>` : ''}`;

  // Datos entrada
  const entrada = d.entrada || [];
  if (entrada.length) {
    const cols = Object.keys(entrada[0]);
    document.getElementById('dp-1').innerHTML = `
      <p style="margin-bottom:8px;font-size:12px;color:var(--fg-3)">Datos de entrada (${entrada.length} filas)</p>
      <div class="table-wrap">${buildTable(cols, entrada)}</div>
      ${d.salida_pandas ? buildSalidaCompar(d) : ''}`;
  } else {
    document.getElementById('dp-1').innerHTML = '<p>Ver tabla de resumen en la pestaña Resumen.</p>';
  }

  // Contrato
  document.getElementById('dp-2').innerHTML = `
    <p style="margin-bottom:8px;font-size:12px;color:var(--fg-3)">Requisitos del contrato de transformación</p>
    <pre style="background:var(--bg-2);border:1px solid var(--border);border-radius:6px;padding:12px;font-size:12px;overflow-x:auto">${JSON.stringify(d.contrato, null, 2)}</pre>`;

  // Diferencias
  const diffs = d.diferencias || [];
  if (diffs.length) {
    const cols = Object.keys(diffs[0]);
    document.getElementById('dp-3').innerHTML = `
      <p style="margin-bottom:8px;font-size:12px;color:var(--fg-3)">${diffs.length} diferencia(s) detectada(s)</p>
      <div class="table-wrap">${buildTable(cols, diffs, true)}</div>`;
  } else {
    document.getElementById('dp-3').innerHTML = '<p style="color:var(--ok)">✓ Sin diferencias detectadas.</p>';
  }

  // Detalle técnico
  document.getElementById('dp-4').innerHTML = `
    <pre style="background:var(--bg-2);border:1px solid var(--border);border-radius:6px;padding:12px;font-size:11px;overflow-x:auto">${JSON.stringify(d, null, 2)}</pre>`;
}

function renderResumenParejas(resumen) {
  const cols = Object.keys(resumen[0]);
  return buildTable(cols, resumen);
}

function buildTable(cols, rows, highlight) {
  const thead = `<thead><tr>${cols.map(c =>
    `<th${typeof rows[0]?.[c]==='number'?' class="num"':''}>${c}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows.map(r => {
    const cls = highlight && (r.tipo?.includes('incorrecto') || r.tipo?.includes('valor')) ? ' class="diff-row-err"' : '';
    return `<tr${cls}>${cols.map(c => {
      const v = r[c] ?? '—';
      const isNum = typeof v === 'number';
      return `<td${isNum?' class="num"':''}>${isNum ? new Intl.NumberFormat('es-EC',{minimumFractionDigits:typeof v==='number'&&String(v).includes('.')?2:0}).format(v) : v}</td>`;
    }).join('')}</tr>`;
  }).join('')}</tbody>`;
  return `<table>${thead}${tbody}</table>`;
}

function buildSalidaCompar(d) {
  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
      <div>
        <p style="font-size:12px;color:var(--fg-3);margin-bottom:6px">Salida ${d.motor_origen}</p>
        <div class="table-wrap">${buildTable(Object.keys(d.salida_pandas[0]), d.salida_pandas)}</div>
      </div>
      <div>
        <p style="font-size:12px;color:var(--fg-3);margin-bottom:6px">Salida ${d.motor_destino || 'destino'}</p>
        <div class="table-wrap">${buildTable(
          Object.keys((d.salida_polars||d.salida_duckdb||[])[0]||{}),
          d.salida_polars||d.salida_duckdb||[])}</div>
      </div>
    </div>`;
}

function switchTab(btn, idx) {
  btn.closest('.tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('dp-' + idx).classList.add('active');
}

// ── RESULTADOS ────────────────────────────────────────────────────────────

const _COMP_META = {
  R: { label: 'R', nombre: 'Reglas',            color: 'blue'   },
  M: { label: 'M', nombre: 'Isolation Forest',  color: 'purple' },
  B: { label: 'B', nombre: 'MAD baseline',      color: 'green'  },
  H: { label: 'H', nombre: 'Híbrido R OR M',    color: 'orange' },
};

function _compBadge(resultado, disponible) {
  if (!disponible) return `<span class="comp-badge comp-badge-na" title="No disponible">—</span>`;
  const cls = resultado === 'OK' ? 'ok' : resultado?.startsWith('DIVERGENCIA') ? 'err' : 'warn';
  const ico = resultado === 'OK' ? '✓' : resultado?.startsWith('DIVERGENCIA') ? '✗' : '⚠';
  return `<span class="comp-badge comp-badge-${cls}" title="${resultado || ''}">${ico}</span>`;
}

function initResultados() {
  const tbody = document.getElementById('tbody-resultados');
  if (!tbody || tbody.dataset.inited) return;
  tbody.dataset.inited = '1';

  const runs = EQ.resultados;
  const comps = EQ.componentes_estado;

  // ── Panel de disponibilidad de componentes
  const compGrid = document.getElementById('comp-status-grid');
  if (compGrid && comps) {
    compGrid.innerHTML = Object.values(comps).map(c => {
      const pct = Math.round((c.runs_completados / c.runs_total) * 100);
      const extra = c.modelo_fecha
        ? `<div class="comp-extra">Modelo: ${c.modelo_fecha} · ${fmtNum(c.n_perfiles)} perfiles</div>
           ${c.familias_pendientes?.length ? `<div class="comp-pending">Pendiente: ${c.familias_pendientes.join(', ')}</div>` : ''}`
        : `<div class="comp-extra">${c.runs_completados} / ${c.runs_total} estratos completados</div>`;
      return `
        <div class="comp-status-card comp-${c.clave.toLowerCase()}">
          <div class="comp-status-top">
            <span class="comp-status-letra">${c.clave}</span>
            <span class="comp-status-nombre">${c.nombre}</span>
            <span class="comp-status-dot ${c.disponible ? 'dot-ok' : 'dot-na'}"></span>
          </div>
          <p class="comp-status-desc">${c.descripcion}</p>
          ${extra}
          <div class="comp-progress"><div class="comp-progress-fill" style="width:${pct}%"></div></div>
        </div>`;
    }).join('');
  }

  // ── Estadísticas resumen
  const ok  = runs.filter(r => r.resultado === 'OK').length;
  const div = runs.filter(r => r.resultado?.startsWith('DIVERGENCIA')).length;
  const statsEl = document.getElementById('resultados-stats');
  if (statsEl) {
    statsEl.innerHTML = `
      <div class="res-stat"><span class="badge badge-ok">✓ OK</span> ${ok} runs</div>
      <div class="res-stat"><span class="badge badge-err">✗ Divergencia</span> ${div} runs</div>
      <div class="res-stat" style="margin-left:auto;font-size:12px;color:var(--fg-3)">
        ${runs.length} ejecuciones · snapshot ${EQ_CONFIG.snapshotId}
      </div>`;
  }

  // ── Tabla
  tbody.innerHTML = runs.map((r, i) => `
    <tr class="run-row" onclick="selectRun(${i})" data-idx="${i}" style="cursor:pointer">
      <td class="mono" style="font-size:11px">${r.run_id}</td>
      <td>${r.pareja}</td>
      <td>${r.familia.replace(/_/g,' ')}</td>
      <td class="num">${fmtNum(r.filas)}</td>
      <td style="text-align:center">${_compBadge(r.resultado_R, true)}</td>
      <td style="text-align:center">${_compBadge(r.resultado_M, r.m_disponible)}</td>
      <td style="text-align:center">${_compBadge(r.resultado_B, true)}</td>
      <td style="text-align:center">${_compBadge(r.resultado,   true)}</td>
      <td style="font-size:12px;color:var(--fg-3)">${r.fecha}</td>
    </tr>`).join('');
}

function selectRun(idx) {
  const r = EQ.resultados[idx];
  if (!r) return;

  document.querySelectorAll('.run-row').forEach(row =>
    row.classList.toggle('run-row-selected', parseInt(row.dataset.idx) === idx));

  const panel = document.getElementById('run-detail');
  panel.hidden = false;
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  document.getElementById('run-detail-id').textContent = r.run_id;
  document.getElementById('run-detail-meta').textContent =
    `${r.pareja} · ${r.familia.replace(/_/g,' ')} · ${fmtNum(r.filas)} filas · ${r.tiempo_s} s · ${r.memoria_mb} MB · ${r.fecha}`;

  const grid = document.getElementById('run-comp-grid');

  const componentes = [
    { key: 'R', resultado: r.resultado_R, diffs: r.diferencias_R, notas: r.notas_R, disponible: true },
    { key: 'M', resultado: r.resultado_M, diffs: r.diferencias_M, notas: r.notas_M, disponible: r.m_disponible,
      extra: r.puntuacion_anomalia != null ? `Puntuación anomalía: <strong>${r.puntuacion_anomalia}</strong> (umbral 0.5)` : null },
    { key: 'B', resultado: r.resultado_B, diffs: r.diferencias_B, notas: r.notas_B, disponible: true },
    { key: 'H', resultado: r.resultado,   diffs: r.diferencias,   notas: 'Resultado final: H = R OR M. Si M no está disponible, H = R.', disponible: true },
  ];

  grid.innerHTML = componentes.map(c => {
    const meta = _COMP_META[c.key];
    if (!c.disponible) {
      return `
        <div class="run-comp-card run-comp-na">
          <div class="run-comp-top">
            <span class="run-comp-letra">${c.key}</span>
            <span class="run-comp-nombre">${meta.nombre}</span>
          </div>
          <div class="run-comp-unavail">
            <span>⚠ No disponible</span>
            <p>El modelo Isolation Forest no ha sido entrenado para la familia <strong>${r.familia.replace(/_/g,' ')}</strong>.<br>
            Se requieren ≥ 10 000 perfiles canónicos. El resultado H se calcula solo con R.</p>
          </div>
        </div>`;
    }
    const cls = c.resultado === 'OK' ? 'ok' : c.resultado?.startsWith('DIVERGENCIA') ? 'err' : 'warn';
    const ico = c.resultado === 'OK' ? '✓' : c.resultado?.startsWith('DIVERGENCIA') ? '✗' : '⚠';
    return `
      <div class="run-comp-card run-comp-${cls}">
        <div class="run-comp-top">
          <span class="run-comp-letra">${c.key}</span>
          <span class="run-comp-nombre">${meta.nombre}</span>
          <span class="run-comp-badge run-comp-badge-${cls}">${ico} ${c.resultado?.replace(/_/g,' ') || ''}</span>
        </div>
        <div class="run-comp-diffs">${c.diffs !== null ? `${c.diffs} diferencia(s)` : '—'}</div>
        ${c.extra ? `<div class="run-comp-extra">${c.extra}</div>` : ''}
        <p class="run-comp-notas">${c.notas || ''}</p>
      </div>`;
  }).join('');
}

function cerrarDetalle() {
  document.getElementById('run-detail').hidden = true;
  document.querySelectorAll('.run-row').forEach(r => r.classList.remove('run-row-selected'));
}

// ── Proyecto (tesis) ─────────────────────────────────────────────────────

function initProyecto() {
  const tbody = document.getElementById('strata-tbody');
  if (!tbody || tbody.dataset.inited) return;
  tbody.dataset.inited = '1';

  const PAIRS    = ['Pandas→Polars', 'Pandas→DuckDB', 'Polars→DuckDB'];
  const FAMILIES = ['ausencias_tipos', 'uniones', 'agregaciones'];

  const lookup = {};
  (EQ.resultados || []).forEach(r => { lookup[`${r.pareja}:${r.familia}`] = r; });

  tbody.innerHTML = PAIRS.map(pareja => {
    const cells = FAMILIES.map(familia => {
      const r = lookup[`${pareja}:${familia}`];
      if (!r) return `<td class="strata-cell strata-pend">⏳ Pendiente</td>`;
      if (r.resultado === 'OK') return `<td class="strata-cell strata-ok">✓ OK</td>`;
      return `<td class="strata-cell strata-div">✗ Divergencia</td>`;
    }).join('');
    return `<tr><td class="strata-row-header">${pareja}</td>${cells}</tr>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────────

(function init() {
  const hash = window.location.hash.replace('#', '') || 'inicio';
  showPage(hash);
})();
