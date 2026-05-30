PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY,
    canonical_title TEXT NOT NULL,
    english_title TEXT,
    work_type TEXT NOT NULL,
    language_code TEXT NOT NULL,
    default_citation TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS sections (
    section_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(work_id),
    parent_section_id TEXT REFERENCES sections(section_id),
    label TEXT NOT NULL,
    canonical_ref TEXT NOT NULL,
    sort_key INTEGER NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS persons (
    person_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    romanized_name TEXT,
    roles_json TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(work_id),
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    language_code TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    citation TEXT NOT NULL,
    source_url TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    processed_path TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    author_or_translator_ids_json TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(work_id),
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    segment_type TEXT NOT NULL,
    segment_order INTEGER NOT NULL,
    canonical_ref TEXT NOT NULL,
    text_original TEXT NOT NULL,
    text_normalized TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS alignments (
    alignment_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(work_id),
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    target_source_id TEXT NOT NULL REFERENCES sources(source_id),
    alignment_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    chinese_segment_ids_json TEXT NOT NULL,
    translation_segment_ids_json TEXT NOT NULL,
    alignment_granularity TEXT,
    section_unit TEXT,
    segment_type TEXT,
    is_coarse_alignment INTEGER NOT NULL DEFAULT 0,
    coarse_alignment_reason TEXT,
    source_segment_count INTEGER,
    target_segment_count INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    run_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    db_path TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sections_work_sort
    ON sections(work_id, sort_key);

CREATE INDEX IF NOT EXISTS idx_sources_work_section
    ON sources(work_id, section_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_segments_source_order
    ON segments(source_id, segment_order);

CREATE INDEX IF NOT EXISTS idx_segments_section
    ON segments(section_id, source_id);

CREATE INDEX IF NOT EXISTS idx_alignments_section
    ON alignments(section_id, source_id, target_source_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_kind
    ON agent_runs(run_kind, started_at);
