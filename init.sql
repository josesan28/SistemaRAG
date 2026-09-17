-- Se ejecuta automáticamente la primera vez que se crea el volumen del contenedor
-- (docker-entrypoint-initdb.d). Si ya tenías el contenedor levantado antes de
-- agregar este archivo, corre este script a mano una vez (ver README).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS faqs (
    id          TEXT PRIMARY KEY,        -- p.ej. "FAQ-001"
    categoria   TEXT NOT NULL,
    pregunta    TEXT NOT NULL,
    respuesta   TEXT NOT NULL,
    metadata    JSONB,
    embedding   VECTOR(384) NOT NULL,    -- 384 dims = all-MiniLM-L6-v2
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice para búsquedas de similitud por coseno (ivfflat).
-- El corpus entregado tiene 120 filas; 10 listas evita particiones demasiado
-- pequeñas. La herramienta configura probes=10 para priorizar recall.
CREATE INDEX IF NOT EXISTS faqs_embedding_idx
    ON faqs
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

CREATE INDEX IF NOT EXISTS faqs_categoria_idx ON faqs (categoria);
