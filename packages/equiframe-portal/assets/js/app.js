/* EquiFrame Portal — SPA logic */
'use strict';

// ── Capa de datos (sintético ↔ API real) ─────────────────────────────────

const DS = {
  /** Indicadores principales */
  async indicadores(filtros = {}) {
    if (!EQ_CONFIG.useRealApi) return EQ.indicadores;
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, ...filtros });
    return _get(`/indicadores?${q}`);
  },
  /** Serie temporal mensual */
  async serieTemporal(filtros = {}) {
    if (!EQ_CONFIG.useRealApi) return EQ.serie_temporal;
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, ...filtros });
    return _get(`/serie-temporal?${q}`);
  },
  /** Top entidades por monto */
  async topEntidades(limit = 10) {
    if (!EQ_CONFIG.useRealApi) return EQ.top_entidades;
    return _get(`/entidades/top?snapshot=${EQ_CONFIG.snapshotId}&limit=${limit}`);
  },
  /** Lista paginada de adjudicaciones */
  async adjudicaciones(filtros = {}, page = 0, size = 50) {
    if (!EQ_CONFIG.useRealApi) {
      // Filtrar y paginar datos sintéticos igual que el backend haría
      let data = [...EQ.adjudicaciones];
      if (filtros.estado)    data = data.filter(a => a.estado    === filtros.estado);
      if (filtros.entidad)   data = data.filter(a => a.entidad   === filtros.entidad);
      if (filtros.modalidad) data = data.filter(a => a.modalidad === filtros.modalidad);
      return { total: data.length, page, size, items: data.slice(page*size, page*size+size) };
    }
    const q = new URLSearchParams({ snapshot: EQ_CONFIG.snapshotId, page, size, ...filtros });
    return _get(`/adjudicaciones?${q}`);
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

let paginaActual = 0;
const POR_PAGINA = 10;
let adjFiltradas = [...EQ.adjudicaciones];

async function initExplorar() {
  chartsInited = true;

  // Llenar select entidades
  try {
    const entidades = await DS.topEntidades(50);
    const sel = document.getElementById('f-entidad');
    entidades.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.entidad; opt.textContent = e.entidad;
      sel.appendChild(opt);
    });
  } catch (e) { _mostrarError(e.message); }

  // Filtros
  ['f-snapshot','f-periodo','f-entidad','f-estado','f-modalidad'].forEach(id => {
    document.getElementById(id).addEventListener('change', aplicarFiltros);
  });

  try {
    const ind = await DS.indicadores();
    renderKPIs(ind);
  } catch (e) { _mostrarError(e.message); }

  await renderCharts();
  await aplicarFiltros();
}

async function aplicarFiltros() {
  const estado    = document.getElementById('f-estado').value;
  const entidad   = document.getElementById('f-entidad').value;
  const modalidad = document.getElementById('f-modalidad').value;
  const periodo   = document.getElementById('f-periodo').value;

  const filtros = {};
  if (estado)    filtros.estado    = estado;
  if (entidad)   filtros.entidad   = entidad;
  if (modalidad) filtros.modalidad = modalidad;
  if (periodo)   filtros.periodo   = periodo;

  try {
    const resp = await DS.adjudicaciones(filtros, 0, POR_PAGINA);
    adjFiltradas = resp.items;
    _totalFiltrado = resp.total;
    paginaActual = 0;
    renderTabla();
  } catch (e) { _mostrarError(e.message); }
}

let _totalFiltrado = 0;

function renderKPIs(ind) {
  const grid = document.getElementById('kpi-grid');
  grid.innerHTML = `
    <div class="kpi">
      <div class="kpi-label">Total adjudicaciones</div>
      <div class="kpi-value">${fmtNum(ind.total_adjudicaciones)}</div>
      <div class="kpi-sub">Corpus 2025</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Monto total</div>
      <div class="kpi-value">${fmt(ind.monto_total_usd)}</div>
      <div class="kpi-sub">USD</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Entidades únicas</div>
      <div class="kpi-value">${fmtNum(ind.entidades_unicas)}</div>
      <div class="kpi-sub">Compradores</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Proveedores únicos</div>
      <div class="kpi-value">${fmtNum(ind.proveedores_unicos)}</div>
      <div class="kpi-sub">Adjudicatarios</div>
    </div>`;
}

async function renderCharts() {
  const accent = '#2563a8';
  const accentL = '#93c5fd';
  const gris = '#64748b';

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
  const pagina = adjFiltradas;
  tbody.innerHTML = pagina.map(a => `
    <tr>
      <td class="mono">${a.ocid}</td>
      <td>${a.entidad}</td>
      <td>${a.proveedor}</td>
      <td class="num">${new Intl.NumberFormat('es-EC',{minimumFractionDigits:2}).format(a.monto)}</td>
      <td>${a.moneda}</td>
      <td>${a.fecha}</td>
      <td>${estadoBadge(a.estado)}</td>
      <td>${a.modalidad}</td>
    </tr>`).join('');
  renderPaginacion();
}

function renderPaginacion() {
  const total = Math.ceil(_totalFiltrado / POR_PAGINA);
  const pg = document.getElementById('paginacion');
  pg.innerHTML = `
    <button onclick="irPagina(${paginaActual-1})" ${paginaActual===0?'disabled':''}>‹ Ant.</button>
    <span>Página ${paginaActual+1} de ${total||1} · ${fmtNum(_totalFiltrado)} registros</span>
    <button onclick="irPagina(${paginaActual+1})" ${paginaActual>=total-1?'disabled':''}>Sig. ›</button>`;
}

async function irPagina(n) {
  const total = Math.ceil(_totalFiltrado / POR_PAGINA);
  if (n < 0 || n >= total) return;
  paginaActual = n;

  const estado    = document.getElementById('f-estado').value;
  const entidad   = document.getElementById('f-entidad').value;
  const modalidad = document.getElementById('f-modalidad').value;
  const periodo   = document.getElementById('f-periodo').value;
  const filtros   = {};
  if (estado)    filtros.estado    = estado;
  if (entidad)   filtros.entidad   = entidad;
  if (modalidad) filtros.modalidad = modalidad;
  if (periodo)   filtros.periodo   = periodo;

  try {
    const resp = await DS.adjudicaciones(filtros, n, POR_PAGINA);
    adjFiltradas = resp.items;
    renderTabla();
  } catch (e) { _mostrarError(e.message); }
}

async function exportCSV() {
  const cols = ['ocid','entidad','proveedor','monto','moneda','fecha','estado','modalidad'];

  let allRows;
  if (!EQ_CONFIG.useRealApi) {
    // Modo sintético: ya tenemos todos los datos en memoria
    allRows = EQ.adjudicaciones;
  } else {
    // Modo real: paginar hasta obtener todo
    try {
      const estado    = document.getElementById('f-estado').value;
      const entidad   = document.getElementById('f-entidad').value;
      const modalidad = document.getElementById('f-modalidad').value;
      const periodo   = document.getElementById('f-periodo').value;
      const filtros   = {};
      if (estado)    filtros.estado    = estado;
      if (entidad)   filtros.entidad   = entidad;
      if (modalidad) filtros.modalidad = modalidad;
      if (periodo)   filtros.periodo   = periodo;

      const PAGE_SIZE = 500;
      allRows = [];
      let page = 0;
      while (true) {
        const resp = await DS.adjudicaciones(filtros, page, PAGE_SIZE);
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

function initResultados() {
  const tbody = document.getElementById('tbody-resultados');
  if (tbody.dataset.inited) return;
  tbody.dataset.inited = '1';
  tbody.innerHTML = EQ.resultados.map(r => `
    <tr>
      <td class="mono">${r.run_id}</td>
      <td>${r.pareja}</td>
      <td>${r.familia.replace(/_/g,' ')}</td>
      <td>${resultadoBadge(r.resultado)}</td>
      <td class="num">${fmtNum(r.filas)}</td>
      <td class="num">${r.diferencias}</td>
      <td class="num">${r.tiempo_s}</td>
      <td>${r.fecha}</td>
    </tr>`).join('');
}

// ── Init ──────────────────────────────────────────────────────────────────

(function init() {
  const hash = window.location.hash.replace('#', '') || 'inicio';
  showPage(hash);
})();
