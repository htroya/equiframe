-- DW Schema for SERCOP-OCDS (Jhair)
-- Version 1.0
-- Grano de fact_adjudicacion: (snapshot_id, ocid, award_id)

-- Snapshot metadata
CREATE TABLE IF NOT EXISTS snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    snapshot_timestamp TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    version VARCHAR
);

-- Entidad (Entidad contratante) - natural key: entidad_id
CREATE TABLE IF NOT EXISTS dim_entidad (
    entidad_surrogate_key BIGINT PRIMARY KEY,
    entidad_id VARCHAR NOT NULL,
    entidad_nombre VARCHAR,
    entidad_tipo VARCHAR,
    entidad_ubicación VARCHAR,
    UNIQUE (entidad_id)
);

-- Proveedor (Proveedor) - natural key: proveedor_id
CREATE TABLE IF NOT EXISTS dim_proveedor (
    proveedor_surrogate_key BIGINT PRIMARY KEY,
    proveedor_id VARCHAR NOT NULL,
    proveedor_nombre VARCHAR,
    proveedor_tipo VARCHAR,
    proveedor_país VARCHAR,
    UNIQUE (proveedor_id)
);

-- Bien/Servicio (Item) - natural key: item_id
CREATE TABLE IF NOT EXISTS dim_item (
    item_surrogate_key BIGINT PRIMARY KEY,
    item_id VARCHAR NOT NULL,
    item_descripcion VARCHAR,
    item_unidad_medida VARCHAR,
    UNIQUE (item_id)
);

-- Fecha (Date dimension)
CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha_surrogate_key BIGINT PRIMARY KEY,
    fecha DATE NOT NULL,
    año INTEGER,
    mes INTEGER,
    día INTEGER,
    trimestre INTEGER,
    UNIQUE (fecha)
);

-- Fact table: adjudicaciones
CREATE TABLE IF NOT EXISTS fact_adjudicacion (
    fact_id BIGINT PRIMARY KEY,
    snapshot_id VARCHAR NOT NULL REFERENCES snapshot(snapshot_id),
    ocid VARCHAR NOT NULL,
    award_id VARCHAR NOT NULL,
    monto DECIMAL(18, 2),
    moneda VARCHAR(3),
    estado VARCHAR(50),
    fecha_procedimiento DATE,
    fecha_adjudicacion DATE,
    entidad_surrogate_key BIGINT REFERENCES dim_entidad(entidad_surrogate_key),
    proveedor_surrogate_key BIGINT REFERENCES dim_proveedor(proveedor_surrogate_key),
    item_surrogate_key BIGINT REFERENCES dim_item(item_surrogate_key),
    fecha_surrogate_key BIGINT REFERENCES dim_fecha(fecha_surrogate_key),
    UNIQUE (snapshot_id, ocid, award_id)
);

-- Table for reconciliation exceptions
CREATE TABLE IF NOT EXISTS recon_excepciones (
    excepción_id BIGINT PRIMARY KEY,
    snapshot_id VARCHAR NOT NULL,
    ocid VARCHAR,
    award_id VARCHAR,
    campo VARCHAR,
    valor_origen VARCHAR,
    valor_destino VARCHAR,
    diferencia DECIMAL(18,2),
    descripción VARCHAR
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fact_snapshot ON fact_adjudicacion(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_fact_ocid ON fact_adjudicacion(ocid);
CREATE INDEX IF NOT EXISTS idx_fact_award ON fact_adjudicacion(award_id);
