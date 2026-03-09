-- BRO-ENGINE POSTGRES SCHEMA
-- Edge-first knowledge graph with geometric properties
-- Requires pgvector extension

-- Enable pgvector for geometric operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Main edges table (denormalized for speed)
CREATE TABLE IF NOT EXISTS edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Triple (subject, predicate, object)
    source TEXT NOT NULL,
    relationship TEXT NOT NULL,
    target TEXT NOT NULL,

    -- Epistemic geometry
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    via TEXT DEFAULT '', -- Provenance (reading session, etc.)

    -- Geometric properties
    vector vector(512),  -- Position in morpheme space (pgvector type)
    prime BIGINT,        -- Optional compact encoding

    -- Polymorphic edge kinds
    kind TEXT,           -- Edge kind (bayesian, causal, logical, etc.)
    properties JSONB DEFAULT '{}',  -- Kind-specific data

    -- Context
    qualifiers JSONB DEFAULT '[]',  -- Context tags

    -- Touch tracking (attention mechanism)
    touch_count INTEGER DEFAULT 0,
    last_touched_at TIMESTAMPTZ,
    signal REAL DEFAULT 0.0,
    hot REAL DEFAULT 0.0,

    -- Soft delete
    invalidated_at TIMESTAMPTZ,
    invalidation_reason TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_relationship ON edges(relationship) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_via ON edges(via) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_confidence ON edges(confidence) WHERE invalidated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_edges_hot ON edges(hot DESC) WHERE invalidated_at IS NULL;

-- Composite index for SPO queries
CREATE INDEX IF NOT EXISTS idx_edges_triple ON edges(source, relationship, target) WHERE invalidated_at IS NULL;

-- GIN index for JSONB properties
CREATE INDEX IF NOT EXISTS idx_edges_properties ON edges USING GIN(properties);
CREATE INDEX IF NOT EXISTS idx_edges_qualifiers ON edges USING GIN(qualifiers);

-- Vector similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS idx_edges_vector ON edges USING ivfflat (vector vector_cosine_ops)
WHERE invalidated_at IS NULL AND vector IS NOT NULL;

-- Semantic field vectors (reading sessions, contexts)
CREATE TABLE IF NOT EXISTS field_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,  -- e.g., "frankenstein_reading"
    vector vector(512) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edge_count INTEGER DEFAULT 0,  -- How many edges contributed to this field
    avg_confidence REAL DEFAULT 0.0,
    description TEXT
);

-- Index for field vector similarity
CREATE INDEX IF NOT EXISTS idx_field_vectors_vector ON field_vectors USING ivfflat (vector vector_cosine_ops);

-- Edge provenance (which edges produced this edge through composition)
CREATE TABLE IF NOT EXISTS edge_provenance (
    edge_id UUID NOT NULL REFERENCES edges(id),
    source_edge_id UUID NOT NULL REFERENCES edges(id),
    composition_rule TEXT,  -- How were they combined
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (edge_id, source_edge_id)
);

CREATE INDEX IF NOT EXISTS idx_edge_provenance_edge ON edge_provenance(edge_id);
CREATE INDEX IF NOT EXISTS idx_edge_provenance_source ON edge_provenance(source_edge_id);

-- View: Valid edges (not invalidated)
CREATE OR REPLACE VIEW edges_valid AS
SELECT
    id, ts, source, relationship, target,
    confidence, via, vector, prime, kind, properties, qualifiers,
    touch_count, last_touched_at, signal, hot
FROM edges
WHERE invalidated_at IS NULL;

-- View: Founding edges (high confidence, constitutional)
CREATE OR REPLACE VIEW edges_founding AS
SELECT *
FROM edges
WHERE invalidated_at IS NULL
  AND (kind = 'founding_edge' OR confidence >= 0.95);

-- View: Recent edges (last 7 days)
CREATE OR REPLACE VIEW edges_recent AS
SELECT *
FROM edges
WHERE invalidated_at IS NULL
  AND ts > NOW() - INTERVAL '7 days';

-- View: Stale edges (not touched in 90 days, need revalidation)
CREATE OR REPLACE VIEW edges_stale AS
SELECT *
FROM edges
WHERE invalidated_at IS NULL
  AND (last_touched_at IS NULL OR last_touched_at < NOW() - INTERVAL '90 days')
  AND confidence < 0.95;  -- Don't mark founding edges as stale

-- Function: Update touch tracking
CREATE OR REPLACE FUNCTION touch_edge(edge_uuid UUID)
RETURNS void AS $$
BEGIN
    UPDATE edges
    SET
        touch_count = touch_count + 1,
        last_touched_at = NOW(),
        hot = hot + 1.0  -- Recency boost
    WHERE id = edge_uuid;
END;
$$ LANGUAGE plpgsql;

-- Function: Decay hot scores (run periodically)
CREATE OR REPLACE FUNCTION decay_hot_scores()
RETURNS void AS $$
BEGIN
    UPDATE edges
    SET hot = hot * 0.95
    WHERE hot > 0.01 AND invalidated_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Function: Find similar edges (geometric)
CREATE OR REPLACE FUNCTION find_similar_edges(
    query_vector vector(512),
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

-- Function: Get edges resonating with field
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
    field_vec vector(512);
BEGIN
    -- Get field vector
    SELECT vector INTO field_vec
    FROM field_vectors
    WHERE name = field_name;

    IF field_vec IS NULL THEN
        RAISE EXCEPTION 'Field vector not found: %', field_name;
    END IF;

    -- Find resonating edges
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
