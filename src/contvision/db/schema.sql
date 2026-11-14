-- Esquema de la base de datos de ContVision (plan_interfaz_bd §1).
-- Idempotente: se puede ejecutar sobre una BD existente.

-- Ubicaciones físicas (puertos, terminales, depósitos)
CREATE TABLE IF NOT EXISTS almacen (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    tipo        TEXT NOT NULL CHECK (tipo IN ('puerto','terminal','deposito','ferroviario')),
    lat         REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon         REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    capacidad   INTEGER CHECK (capacidad IS NULL OR capacidad > 0),
    descripcion TEXT
);

-- Cámaras / puntos de lectura. nombre == Lectura.fuente
CREATE TABLE IF NOT EXISTS fuente (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    almacen_id  INTEGER NOT NULL REFERENCES almacen(id),
    tipo        TEXT NOT NULL CHECK (tipo IN ('entrada','salida','interior')),
    activa      INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0,1))
);

-- Una fila por contenedor
CREATE TABLE IF NOT EXISTS contenedor (
    id                INTEGER PRIMARY KEY,
    codigo            TEXT NOT NULL UNIQUE,
    propietario       TEXT NOT NULL,
    categoria         TEXT NOT NULL,
    primera_vez       TEXT NOT NULL,
    ultima_vez        TEXT NOT NULL,
    n_avistamientos   INTEGER NOT NULL DEFAULT 0,
    almacen_actual_id INTEGER REFERENCES almacen(id)
);

-- El histórico: una fila por lectura
CREATE TABLE IF NOT EXISTS avistamiento (
    id             INTEGER PRIMARY KEY,
    contenedor_id  INTEGER REFERENCES contenedor(id),
    fuente_id      INTEGER NOT NULL REFERENCES fuente(id),
    timestamp      TEXT NOT NULL,
    lectura_ocr    TEXT NOT NULL,
    confianza      REAL NOT NULL,
    estado         TEXT NOT NULL CHECK (estado IN ('valida','corregida','dudosa')),
    orientacion    TEXT NOT NULL CHECK (orientacion IN ('horizontal','vertical')),
    ruta_recorte   TEXT,
    revisado       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alternativa (
    avistamiento_id INTEGER NOT NULL REFERENCES avistamiento(id) ON DELETE CASCADE,
    codigo          TEXT NOT NULL,
    puntuacion      REAL NOT NULL,
    PRIMARY KEY (avistamiento_id, codigo)
);

CREATE TABLE IF NOT EXISTS correccion (
    id               INTEGER PRIMARY KEY,
    avistamiento_id  INTEGER NOT NULL REFERENCES avistamiento(id) ON DELETE CASCADE,
    codigo_anterior  TEXT,
    codigo_nuevo     TEXT NOT NULL,
    usuario          TEXT,
    timestamp        TEXT NOT NULL
);

-- Periodo en que un contenedor está dentro de un almacén (dato DERIVADO de avistamientos)
CREATE TABLE IF NOT EXISTS estancia (
    id                       INTEGER PRIMARY KEY,
    contenedor_id            INTEGER NOT NULL REFERENCES contenedor(id),
    almacen_id               INTEGER NOT NULL REFERENCES almacen(id),
    entrada_ts               TEXT NOT NULL,
    salida_ts                TEXT,
    avistamiento_entrada_id  INTEGER REFERENCES avistamiento(id),
    avistamiento_salida_id   INTEGER REFERENCES avistamiento(id),
    entrada_inferida         INTEGER NOT NULL DEFAULT 0,  -- la entrada se dedujo de una cámara interior
    salida_inferida          INTEGER NOT NULL DEFAULT 0   -- la salida se dedujo al aparecer en otro almacén
);

-- Log de actividad (Inicio e Historial)
CREATE TABLE IF NOT EXISTS evento (
    id               INTEGER PRIMARY KEY,
    timestamp        TEXT NOT NULL,
    tipo             TEXT NOT NULL,
    nivel            TEXT NOT NULL CHECK (nivel IN ('info','aviso','error')),
    contenedor_id    INTEGER REFERENCES contenedor(id),
    almacen_id       INTEGER REFERENCES almacen(id),
    avistamiento_id  INTEGER REFERENCES avistamiento(id),
    mensaje          TEXT NOT NULL,
    datos            TEXT
);

-- Índices (§1.2)
CREATE INDEX IF NOT EXISTS ix_fuente_almacen          ON fuente(almacen_id);
CREATE INDEX IF NOT EXISTS ix_contenedor_propietario  ON contenedor(propietario);
CREATE INDEX IF NOT EXISTS ix_contenedor_almacen      ON contenedor(almacen_actual_id);
CREATE INDEX IF NOT EXISTS ix_avist_contenedor_ts     ON avistamiento(contenedor_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_avist_fuente_ts         ON avistamiento(fuente_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_avist_ts                ON avistamiento(timestamp);
CREATE INDEX IF NOT EXISTS ix_avist_estado            ON avistamiento(estado) WHERE revisado = 0;
CREATE INDEX IF NOT EXISTS ix_estancia_contenedor     ON estancia(contenedor_id, entrada_ts);
CREATE INDEX IF NOT EXISTS ix_estancia_almacen_entrada ON estancia(almacen_id, entrada_ts);
CREATE INDEX IF NOT EXISTS ix_estancia_almacen_salida  ON estancia(almacen_id, salida_ts) WHERE salida_ts IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_estancia_almacen_abierta ON estancia(almacen_id) WHERE salida_ts IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_estancia_abierta ON estancia(contenedor_id) WHERE salida_ts IS NULL;
CREATE INDEX IF NOT EXISTS ix_evento_ts               ON evento(timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_evento_tipo_ts          ON evento(tipo, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_evento_almacen_ts       ON evento(almacen_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_evento_contenedor       ON evento(contenedor_id);
