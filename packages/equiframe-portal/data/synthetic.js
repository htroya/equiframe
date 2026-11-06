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
  monto:      Math.round((50000 + (i * 123456.78) % 4950000) * 100) / 100,
  moneda:     "USD",
  fecha:      `2025-${String((i % 12) + 1).padStart(2,"0")}-${String((i % 28) + 1).padStart(2,"0")}`,
  estado:     ["active","complete","cancelled","pending"][i % 4],
  modalidad:  ["Subasta Inversa","Cotización","Menor Cuantía","Licitación"][i % 4],
}));

EQ.procedimientos = Array.from({ length: 50 }, (_, i) => ({
  ocid:               `ocds-lcuori-${String(1000 + i).padStart(6,"0")}`,
  entidad:            EQ.top_entidades[i % 10].entidad,
  objeto:             ["Adquisición de medicamentos esenciales","Construcción de aulas modulares","Mantenimiento vial regional","Suministro de equipos TI","Servicios de limpieza institucional","Dotación de uniformes escolares","Obras de alcantarillado","Consultoría técnica especializada"][i % 8],
  modalidad:          ["Subasta Inversa","Cotización","Menor Cuantía","Licitación"][i % 4],
  monto_referencial:  Math.round((80000 + (i * 234567.89) % 5000000) * 100) / 100,
  estado:             ["active","complete","cancelled","pending"][i % 4],
  fecha_publicacion:  `2025-${String((i % 12) + 1).padStart(2,"0")}-${String((i % 15) + 1).padStart(2,"0")}`,
  fecha_adjudicacion: i % 4 !== 2 ? `2025-${String((i % 12) + 1).padStart(2,"0")}-${String((i % 28) + 1).padStart(2,"0")}` : null,
  num_adjudicaciones: i % 4 !== 2 ? (i % 3) + 1 : 0,
}));

EQ.montos_por_moneda = [
  { moneda: "USD", codigo: "USD", descripcion: "Dólar estadounidense", total_adjudicaciones: 183705, monto_total: 4869840218.50, porcentaje: 99.95 },
  { moneda: "EUR", codigo: "EUR", descripcion: "Euro",                 total_adjudicaciones: 152,    monto_total: 1980000.00,    porcentaje: 0.04 },
  { moneda: "GBP", codigo: "GBP", descripcion: "Libra esterlina",      total_adjudicaciones: 34,     monto_total: 520000.00,     porcentaje: 0.01 },
];

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
  {
    run_id: "run-20261012-001", pareja: "Pandas→Polars", familia: "ausencias_tipos",
    filas: 183891, tiempo_s: 4.2, memoria_mb: 98.4, fecha: "2026-10-12",
    resultado_R: "OK",          diferencias_R: 0,
    resultado_M: "OK",          diferencias_M: 0, puntuacion_anomalia: 0.08,
    resultado_B: "OK",          diferencias_B: 0,
    resultado:   "OK",          diferencias: 0,
    m_disponible: true,
    notas_R: "Sin infracciones de contrato detectadas.",
    notas_M: "Perfil dentro del rango normal. Puntuación de anomalía: 0.08 (umbral 0.5).",
    notas_B: "MAD = 0 — ninguna variable supera k=3 desviaciones.",
  },
  {
    run_id: "run-20261012-002", pareja: "Pandas→DuckDB", familia: "ausencias_tipos",
    filas: 183891, tiempo_s: 6.1, memoria_mb: 134.2, fecha: "2026-10-12",
    resultado_R: "DIVERGENCIA",  diferencias_R: 2,
    resultado_M: "DIVERGENCIA",  diferencias_M: 1, puntuacion_anomalia: 0.74,
    resultado_B: "OK",           diferencias_B: 0,
    resultado:   "DIVERGENCIA",  diferencias: 3,
    m_disponible: true,
    notas_R: "Campo 'ocid' leído como integer en DuckDB (pierde ceros iniciales). Campo 'fecha_adjudicacion' cambia zona horaria a UTC.",
    notas_M: "Puntuación de anomalía: 0.74 — perfil inusual en ratio nulos/tipos. Detectó diferencia en proporción de tipos de dato.",
    notas_B: "MAD dentro de rango normal para esta familia — no detectó diferencias.",
  },
  {
    run_id: "run-20261012-003", pareja: "Polars→DuckDB", familia: "uniones",
    filas: 183891, tiempo_s: 5.8, memoria_mb: 121.7, fecha: "2026-10-12",
    resultado_R: "OK",           diferencias_R: 0,
    resultado_M: "OK",           diferencias_M: 0, puntuacion_anomalia: 0.19,
    resultado_B: "OK",           diferencias_B: 0,
    resultado:   "OK",           diferencias: 0,
    m_disponible: true,
    notas_R: "LEFT JOIN preservado. Cardinalidad correcta. Claves huérfanas documentadas (3 adjudicaciones sin proveedor).",
    notas_M: "Puntuación de anomalía: 0.19 — perfil normal.",
    notas_B: "Sin anomalías estadísticas.",
  },
  {
    run_id: "run-20261012-004", pareja: "Pandas→Polars", familia: "agregaciones",
    filas: 183891, tiempo_s: 3.9, memoria_mb: 87.1, fecha: "2026-10-12",
    resultado_R: "OK",           diferencias_R: 0,
    resultado_M: null,           diferencias_M: null, puntuacion_anomalia: null,
    resultado_B: "OK",           diferencias_B: 0,
    resultado:   "OK",           diferencias: 0,
    m_disponible: false,
    notas_R: "Sumas y conteos por entidad coinciden exactamente.",
    notas_M: null,
    notas_B: "MAD dentro de rango. Variación de montos < 0.001 %.",
  },
  {
    run_id: "run-20261012-005", pareja: "Pandas→DuckDB", familia: "agregaciones",
    filas: 183891, tiempo_s: 7.2, memoria_mb: 148.9, fecha: "2026-10-12",
    resultado_R: "DIVERGENCIA",  diferencias_R: 1,
    resultado_M: null,           diferencias_M: null, puntuacion_anomalia: null,
    resultado_B: "DIVERGENCIA",  diferencias_B: 1,
    resultado:   "DIVERGENCIA",  diferencias: 1,
    m_disponible: false,
    notas_R: "Suma de montos para entidad 'IESS' difiere en 0.01 USD por acumulación de errores de punto flotante entre Python y DuckDB.",
    notas_M: null,
    notas_B: "MAD detectó anomalía en variable 'monto_sum' para IESS: |xi - mediana| > 3 × MAD.",
  },
];

EQ.componentes_estado = {
  R: {
    clave: "R", nombre: "Reglas deterministas", disponible: true,
    descripcion: "Verificaciones explícitas del contrato: ausencias, tipos, cardinalidad, claves, orden.",
    runs_completados: 5, runs_total: 9,
  },
  M: {
    clave: "M", nombre: "Isolation Forest", disponible: true,
    descripcion: "Detector de anomalías entrenado con 23 726 perfiles de ejecuciones canónicas.",
    runs_completados: 3, runs_total: 9,
    modelo_fecha: "2026-10-10", n_perfiles: 23726,
    familias_disponibles: ["ausencias_tipos", "uniones"],
    familias_pendientes: ["agregaciones"],
  },
  B: {
    clave: "B", nombre: "MAD (baseline estadístico)", disponible: true,
    descripcion: "Desviación absoluta de la mediana variable a variable. Referencia independiente.",
    runs_completados: 5, runs_total: 9,
  },
  H: {
    clave: "H", nombre: "Híbrido (R OR M)", disponible: true,
    descripcion: "Resultado final: alerta si R o M detectan divergencia. Si M no está disponible, H = R.",
    runs_completados: 5, runs_total: 9,
  },
};
