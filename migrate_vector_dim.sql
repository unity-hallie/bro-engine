-- Migrate vector columns from 512 to 384 dimensions (all-MiniLM-L6-v2)
-- Safe to run: drops existing null vectors, can't cast between dimensions

-- edges table
ALTER TABLE edges DROP COLUMN IF EXISTS vector;
ALTER TABLE edges ADD COLUMN vector vector(384);

-- field_vectors table (nuclear — content was generated with 512-dim model)
ALTER TABLE field_vectors DROP COLUMN IF EXISTS vector;
ALTER TABLE field_vectors ADD COLUMN vector vector(384) NOT NULL DEFAULT array_fill(0, ARRAY[384])::vector(384);
ALTER TABLE field_vectors ALTER COLUMN vector DROP DEFAULT;

-- Recreate indexes
DROP INDEX IF EXISTS idx_edges_vector;
CREATE INDEX idx_edges_vector ON edges USING ivfflat (vector vector_cosine_ops)
WHERE invalidated_at IS NULL AND vector IS NOT NULL;

DROP INDEX IF EXISTS idx_field_vectors_vector;
CREATE INDEX idx_field_vectors_vector ON field_vectors USING ivfflat (vector vector_cosine_ops);

-- Recreate SQL functions with correct dimension
CREATE OR REPLACE FUNCTION find_similar_edges(
    query_vector vector(384),
    limit_count INTEGER DEFAULT 10,
    min_confidence REAL DEFAULT 0.0
)
RETURNS TABLE (
    id UUID,
    source TEXT,
    relationship TEXT,
    target TEXT,
    confidence REAL,
    similarity REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.source,
        e.relationship,
        e.target,
        e.confidence,
        1 - (e.vector <=> query_vector) AS similarity
    FROM edges e
    WHERE
        e.invalidated_at IS NULL
        AND e.vector IS NOT NULL
        AND e.confidence >= min_confidence
    ORDER BY e.vector <=> query_vector
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION edges_in_field(
    field_name TEXT,
    limit_count INTEGER DEFAULT 50,
    min_resonance REAL DEFAULT 0.3
)
RETURNS TABLE (
    id UUID,
    source TEXT,
    relationship TEXT,
    target TEXT,
    confidence REAL,
    resonance REAL
) AS $$
DECLARE
    field_vec vector(384);
BEGIN
    SELECT vector INTO field_vec
    FROM field_vectors
    WHERE name = field_name;

    IF field_vec IS NULL THEN
        RAISE EXCEPTION 'Field vector not found: %', field_name;
    END IF;

    RETURN QUERY
    SELECT
        e.id,
        e.source,
        e.relationship,
        e.target,
        e.confidence,
        1 - (e.vector <=> field_vec) AS resonance
    FROM edges e
    WHERE
        e.invalidated_at IS NULL
        AND e.vector IS NOT NULL
        AND 1 - (e.vector <=> field_vec) >= min_resonance
    ORDER BY resonance DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger: notify indexer when a new edge arrives without a vector
CREATE OR REPLACE FUNCTION notify_new_edge()
RETURNS trigger AS $$
BEGIN
    IF NEW.vector IS NULL THEN
        PERFORM pg_notify('bro_new_edge', NEW.id::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_new_edge ON edges;
CREATE TRIGGER trg_notify_new_edge
    AFTER INSERT ON edges
    FOR EACH ROW EXECUTE FUNCTION notify_new_edge();
