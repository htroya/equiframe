// Datos sintéticos — misma forma que la API real cuando Jhair publique el DW
// Reemplazar cambiando EQ.data por fetch('/api/v1/...')

const EQ = {};

EQ.snapshots = [
  { id: "20261012-v1", label: "12 oct 2026 — v1", fecha: "2026-10-12", registros: 183891 },
];

EQ.indicadores = {
  total_adjudicaciones: 183891,
  monto_total_usd: 4872340218.50,
  entidades_unicas: 1247,
  proveedores_unicos: 38902,
};

EQ.serie_temporal = [
  { mes: "Ene 2025", monto: 312400000, adjudicaciones: 12840 },
  { mes: "Feb 2025", monto: 287600000, adjudicaciones: 11230 },
  { mes: "Mar 2025", monto: 345800000, adjudicaciones: 14120 },
  { mes: "Abr 2025", monto: 398100000, adjudicaciones: 15670 },
  { mes: "May 2025", monto: 421300000, adjudicaciones: 16890 },
  { mes: "Jun 2025", monto: 389700000, adjudicaciones: 15340 },
  { mes: "Jul 2025", monto: 356200000, adjudicaciones: 14050 },
  { mes: "Ago 2025", monto: 412800000, adjudicaciones: 16200 },
  { mes: "Sep 2025", monto: 445600000, adjudicaciones: 17430 },
  { mes: "Oct 2025", monto: 503100000, adjudicaciones: 19280 },
  { mes: "Nov 2025", monto: 489900000, adjudicaciones: 18760 },
  { mes: "Dic 2025", monto: 509840218, adjudicaciones: 22079 },
];

EQ.top_entidades = [
  { entidad: "Ministerio de Salud Pública", monto: 892340000, adjudicaciones: 18230 },
  { entidad: "Ministerio de Educación",     monto: 743120000, adjudicaciones: 14870 },
  { entidad: "Ministerio de Obras Públicas",monto: 698450000, adjudicaciones: 9340  },
  { entidad: "IESS",                        monto: 612300000, adjudicaciones: 11230 },
  { entidad: "Ministerio de Defensa",       monto: 487600000, adjudicaciones: 7890  },
  { entidad: "Ministerio del Interior",     monto: 312400000, adjudicaciones: 6120  },
  { entidad: "Petroecuador",               monto: 298700000, adjudicaciones: 4230  },
  { entidad: "SENESCYT",                   monto: 213400000, adjudicaciones: 5670  },
  { entidad: "Municipio de Guayaquil",      monto: 198200000, adjudicaciones: 3840  },
  { entidad: "Municipio de Quito",          monto: 187600000, adjudicaciones: 3540  },
];

EQ.adjudicaciones = Array.from({ length: 50 }, (_, i) => ({
  ocid:       `ocds-lcuori-${String(1000 + i).padStart(6,"0")}`,
  award_id:   `AWD-2025-${String(10000 + i).padStart(6,"0")}`,
  entidad:    EQ.top_entidades[i % 10].entidad,
  proveedor:  `Proveedor S.A. ${1000 + (i * 7) % 900}`,
  monto:      Math.round((50000 + Math.random() * 4950000) * 100) / 100,
  moneda:     "USD",
  fecha:      `2025-${String((i % 12) + 1).padStart(2,"0")}-${String((i % 28) + 1).padStart(2,"0")}`,
  estado:     ["active","complete","cancelled","pending"][i % 4],
  modalidad:  ["Subasta Inversa","Cotización","Menor Cuantía","Licitación"][i % 4],
}));

EQ.demos = {
  montos_intercambiados: {
    titulo: "Montos intercambiados",
    descripcion: "Dos adjudicaciones conservan un total de 300,00 USD. La salida intercambia los valores: el total es correcto pero los montos individuales están asignados a la entidad equivocada.",
    tipo_datos: "sintéticos",
    entrada: [
      { ocid: "ocds-001", entidad: "Entidad A", monto: 100.00 },
      { ocid: "ocds-002", entidad: "Entidad B", monto: 200.00 },
    ],
    salida_pandas: [
      { ocid: "ocds-001", entidad: "Entidad A", monto: 100.00 },
      { ocid: "ocds-002", entidad: "Entidad B", monto: 200.00 },
    ],
    salida_polars: [
      { ocid: "ocds-001", entidad: "Entidad A", monto: 200.00 },
      { ocid: "ocds-002", entidad: "Entidad B", monto: 100.00 },
    ],
    diferencias: [
      { campo: "monto", ocid: "ocds-001", esperado: 100.00, obtenido: 200.00, tipo: "valor_incorrecto" },
      { campo: "monto", ocid: "ocds-002", esperado: 200.00, obtenido: 100.00, tipo: "valor_incorrecto" },
    ],
    contrato: { suma_total: 300.00, igualdad_exacta_por_clave: true },
    resultado: "DIVERGENCIA",
    motor_origen: "Pandas", motor_destino: "Polars",
  },
  duplicados_orden: {
    titulo: "Duplicados y orden",
    descripcion: "Un JOIN puede multiplicar filas si hay claves duplicadas. La suma de montos cambia aunque el esquema sea idéntico.",
    tipo_datos: "sintéticos",
    entrada: [
      { award_id: "A1", monto: 500.00, proveedor_id: "P1" },
      { award_id: "A1", monto: 500.00, proveedor_id: "P2" },
    ],
    salida_pandas: [
      { award_id: "A1", monto: 500.00, proveedor_id: "P1", nombre: "Empresa X" },
      { award_id: "A1", monto: 500.00, proveedor_id: "P2", nombre: "Empresa Y" },
    ],
    salida_polars: [
      { award_id: "A1", monto: 500.00, proveedor_id: "P2", nombre: "Empresa Y" },
      { award_id: "A1", monto: 500.00, proveedor_id: "P1", nombre: "Empresa X" },
    ],
    diferencias: [
      { campo: "orden_filas", descripcion: "Polars no garantiza orden sin ORDER BY explícito", tipo: "orden" },
    ],
    contrato: { filas_esperadas: 2, duplicados_permitidos: false },
    resultado: "OK_CON_ADVERTENCIA",
    motor_origen: "Pandas", motor_destino: "Polars",
  },
  tipos_fechas: {
    titulo: "Tipos y fechas",
    descripcion: "Identificadores leídos como entero pierden ceros iniciales. Zonas horarias distintas producen fechas diferentes al comparar.",
    tipo_datos: "sintéticos",
    entrada: [
      { ocid: "0012345", fecha_adjudicacion: "2025-03-15T00:00:00-05:00", monto: 1234.56 },
    ],
    salida_pandas: [
      { ocid: "0012345", fecha_adjudicacion: "2025-03-15T00:00:00-05:00", monto: 1234.56 },
    ],
    salida_duckdb: [
      { ocid: 12345, fecha_adjudicacion: "2025-03-15T05:00:00Z", monto: 1234.56 },
    ],
    diferencias: [
      { campo: "ocid", tipo: "tipo_dato", pandas: "string '0012345'", duckdb: "integer 12345" },
      { campo: "fecha_adjudicacion", tipo: "zona_horaria", pandas: "-05:00", duckdb: "UTC" },
    ],
    contrato: { ocid_tipo: "string", fecha_con_zona: true },
    resultado: "DIVERGENCIA",
    motor_origen: "Pandas", motor_destino: "DuckDB",
  },
  migracion_motores: {
    titulo: "Migración entre motores",
    descripcion: "Misma transformación de agregación ejecutada en Pandas, Polars y DuckDB. Se compara el resultado por clave.",
    tipo_datos: "sintéticos",
    parejas: ["Pandas→Polars", "Pandas→DuckDB", "Polars→DuckDB"],
    resumen: [
      { pareja: "Pandas→Polars",  resultado: "OK",         diferencias: 0, filas: 183891 },
      { pareja: "Pandas→DuckDB",  resultado: "DIVERGENCIA",diferencias: 3, filas: 183891 },
      { pareja: "Polars→DuckDB",  resultado: "DIVERGENCIA",diferencias: 3, filas: 183891 },
    ],
    contrato: { agrupacion: ["entidad_id"], suma: "monto", moneda_separada: true },
    resultado: "DIVERGENCIA_PARCIAL",
    motor_origen: "Pandas",
  },
};

EQ.resultados = [
  { run_id: "run-20261012-001", pareja: "Pandas→Polars",  familia: "ausencias_tipos",  resultado: "OK",          filas: 183891, diferencias: 0,  tiempo_s: 4.2,  fecha: "2026-10-12" },
  { run_id: "run-20261012-002", pareja: "Pandas→DuckDB",  familia: "ausencias_tipos",  resultado: "DIVERGENCIA", filas: 183891, diferencias: 3,  tiempo_s: 6.1,  fecha: "2026-10-12" },
  { run_id: "run-20261012-003", pareja: "Polars→DuckDB",  familia: "uniones",          resultado: "OK",          filas: 183891, diferencias: 0,  tiempo_s: 5.8,  fecha: "2026-10-12" },
  { run_id: "run-20261012-004", pareja: "Pandas→Polars",  familia: "agregaciones",     resultado: "OK",          filas: 183891, diferencias: 0,  tiempo_s: 3.9,  fecha: "2026-10-12" },
  { run_id: "run-20261012-005", pareja: "Pandas→DuckDB",  familia: "agregaciones",     resultado: "DIVERGENCIA", filas: 183891, diferencias: 1,  tiempo_s: 7.2,  fecha: "2026-10-12" },
];
