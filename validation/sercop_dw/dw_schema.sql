-- SPDX-License-Identifier: MIT
-- Curated schema based on Jhair Alarcon's SERCOP DW contribution.
-- Schema only: no examples, data downloads, migrations or seed rows.
CREATE TABLE _sercop_dw_schema (version INTEGER PRIMARY KEY CHECK (version = 1));
INSERT INTO _sercop_dw_schema VALUES (1);
CREATE SEQUENCE entidad_seq START 1;
CREATE SEQUENCE proveedor_seq START 1;
CREATE SEQUENCE item_seq START 1;
CREATE SEQUENCE fact_seq START 1;
CREATE TABLE snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    snapshot_timestamp TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    input_sha256 VARCHAR NOT NULL
);
CREATE TABLE dim_entidad (
    entidad_surrogate_key BIGINT PRIMARY KEY,
    entidad_id VARCHAR UNIQUE NOT NULL,
    entidad_nombre VARCHAR,
    entidad_tipo VARCHAR,
    entidad_ubicacion VARCHAR
);
CREATE TABLE dim_proveedor (
    proveedor_surrogate_key BIGINT PRIMARY KEY,
    proveedor_id VARCHAR UNIQUE NOT NULL,
    proveedor_nombre VARCHAR,
    proveedor_pais VARCHAR
);
CREATE TABLE dim_item (
    item_surrogate_key BIGINT PRIMARY KEY,
    item_id VARCHAR UNIQUE NOT NULL,
    item_descripcion VARCHAR,
    item_unidad_medida VARCHAR
);
CREATE TABLE dim_fecha (
    fecha_surrogate_key BIGINT PRIMARY KEY,
    fecha DATE UNIQUE NOT NULL,
    anio INTEGER,
    mes INTEGER,
    dia INTEGER,
    trimestre INTEGER
);
CREATE TABLE fact_adjudicacion (
    fact_id BIGINT PRIMARY KEY,
    snapshot_id VARCHAR NOT NULL REFERENCES snapshot(snapshot_id),
    ocid VARCHAR NOT NULL,
    award_id VARCHAR NOT NULL,
    monto DECIMAL(18, 2) NOT NULL,
    moneda VARCHAR NOT NULL,
    estado VARCHAR,
    fecha_procedimiento DATE,
    fecha_adjudicacion DATE NOT NULL,
    modalidad VARCHAR,
    procedimiento VARCHAR,
    entidad_surrogate_key BIGINT REFERENCES dim_entidad(entidad_surrogate_key),
    proveedor_surrogate_key BIGINT REFERENCES dim_proveedor(proveedor_surrogate_key),
    item_surrogate_key BIGINT REFERENCES dim_item(item_surrogate_key),
    fecha_surrogate_key BIGINT REFERENCES dim_fecha(fecha_surrogate_key),
    UNIQUE (snapshot_id, ocid, award_id)
);
CREATE TABLE recon_excepciones (
    excepcion_id BIGINT PRIMARY KEY,
    snapshot_id VARCHAR NOT NULL,
    ocid VARCHAR,
    award_id VARCHAR,
    campo VARCHAR,
    valor_origen VARCHAR,
    valor_destino VARCHAR,
    diferencia DECIMAL(18, 2),
    descripcion VARCHAR
);
CREATE INDEX idx_fact_snapshot ON fact_adjudicacion(snapshot_id);
