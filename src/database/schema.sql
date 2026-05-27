-- ============================================================
-- DeepTrender Database Schema
-- Three-Layer Architecture: Raw -> Structured -> Analysis
-- ============================================================

-- ========== RAW LAYER ==========
-- Preserves original data from all sources without interpretation

CREATE TABLE IF NOT EXISTS raw_papers (
    raw_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,  -- arxiv / openalex / s2 / openreview
    source_paper_id TEXT NOT NULL,
    title           TEXT,
    abstract        TEXT,
    authors         TEXT,           -- JSON array
    year            INTEGER,
    venue_raw       TEXT,           -- Original venue string (uninterpreted)
    journal_ref     TEXT,           -- arXiv journal reference
    comments        TEXT,           -- arXiv comments (for conference detection)
    categories      TEXT,           -- arXiv categories (cs.CV, cs.LG, etc.)
    doi             TEXT,
    raw_json        TEXT,           -- Complete original API response
    published_at    DATETIME,       -- Source publication timestamp (if available)
    retrieved_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_paper_id)
);

-- ========== STRUCTURED LAYER ==========
-- Normalized, deduplicated papers with venue identification

CREATE TABLE IF NOT EXISTS venues (
    venue_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name  TEXT UNIQUE NOT NULL,  -- CVPR, ICML, NeurIPS, etc.
    full_name       TEXT,
    domain          TEXT,  -- CV / NLP / ML / RL / Theory / Graphics / General
    tier            TEXT CHECK(tier IN ('A', 'B', 'C')) DEFAULT 'C',  -- Venue tier
    venue_type      TEXT CHECK(venue_type IN ('conference', 'journal', 'workshop')),
    openreview_ids  TEXT,  -- JSON array: ["ICLR.cc/2024/Conference", ...]
    years_available TEXT,  -- JSON array: [2024, 2023, 2022, ...]
    first_year      INTEGER,
    last_year       INTEGER,
    discovered_at   DATETIME,  -- First discovery time
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_title TEXT NOT NULL,
    abstract        TEXT,
    authors         TEXT,           -- JSON array
    year            INTEGER,
    venue_id        INTEGER REFERENCES venues(venue_id),
    venue_type      TEXT CHECK(venue_type IN ('conference', 'journal', 'preprint', 'unknown')),
    domain          TEXT,  -- CV / NLP / ML / RL / AI
    quality_flag    TEXT CHECK(quality_flag IN ('accepted', 'unknown', 'filtered')) DEFAULT 'unknown',
    doi             TEXT,
    url             TEXT,
    pdf_url         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Links structured papers back to raw sources (many-to-many)
CREATE TABLE IF NOT EXISTS paper_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    raw_id          INTEGER NOT NULL REFERENCES raw_papers(raw_id) ON DELETE CASCADE,
    source          TEXT NOT NULL,
    confidence      REAL DEFAULT 1.0,  -- Confidence of source-to-paper mapping
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, raw_id)
);

-- ========== ANALYSIS LAYER ==========
-- Derived data from analysis processes (keywords, trends, etc.)

CREATE TABLE IF NOT EXISTS paper_keywords (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    keyword         TEXT NOT NULL,
    method          TEXT NOT NULL,  -- yake / keybert / llm / author
    score           REAL DEFAULT 1.0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, keyword, method)
);

-- Persistent topic facts derived from structured papers, keywords, and taxonomy.
CREATE TABLE IF NOT EXISTS paper_topics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    topic_id        TEXT NOT NULL,
    canonical_topic TEXT NOT NULL,
    domain          TEXT,
    match_method    TEXT NOT NULL,
    confidence      REAL NOT NULL,
    evidence_keyword TEXT,
    evidence_source TEXT,
    taxonomy_version TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, topic_id, taxonomy_version)
);

-- Cache for trend queries (accelerates web visualization)
CREATE TABLE IF NOT EXISTS trend_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword         TEXT NOT NULL,
    venue_id        INTEGER REFERENCES venues(venue_id),
    year            INTEGER NOT NULL,
    count           INTEGER NOT NULL,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyword, venue_id, year)
);

-- ========== OPERATIONAL TABLES ==========
-- Ingestion tracking and system state

CREATE TABLE IF NOT EXISTS ingestion_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,  -- arxiv / openalex / s2 / openreview
    query_params    TEXT,           -- JSON of query parameters
    paper_count     INTEGER NOT NULL,
    started_at      DATETIME,
    completed_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    status          TEXT CHECK(status IN ('success', 'partial', 'failed')) DEFAULT 'success'
);

-- Legacy compatibility: scrape_logs (kept for migration)
CREATE TABLE IF NOT EXISTS scrape_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venue           TEXT NOT NULL,
    year            INTEGER NOT NULL,
    paper_count     INTEGER NOT NULL,
    scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ========== ANALYSIS CACHE TABLES ==========
-- Pre-computed analysis results for fast frontend access

-- A) Analysis metadata for determining whether analysis should rerun
CREATE TABLE IF NOT EXISTS analysis_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- B) Venue summary cache for frontend reads
CREATE TABLE IF NOT EXISTS analysis_venue_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    year INTEGER DEFAULT 0,  -- 0 means all years
    paper_count INTEGER DEFAULT 0,
    top_keywords_json TEXT,  -- JSON: [{"keyword": "x", "count": 10}, ...]
    emerging_keywords_json TEXT,  -- JSON array
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (venue, year)
);

-- C) General keyword trend cache
CREATE TABLE IF NOT EXISTS analysis_keyword_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,  -- 'venue' / 'overall' / 'arxiv'
    venue TEXT DEFAULT '',  -- empty string for overall; arxiv scope stores category here
    keyword TEXT NOT NULL,
    granularity TEXT NOT NULL,  -- 'year'/'month'/'week'/'day'
    bucket TEXT NOT NULL,  -- year="2024", month="2024-02", week="2024-W05", day="2024-02-03"
    count INTEGER DEFAULT 0,
    relative_frequency REAL DEFAULT 0.0,
    rank INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scope, venue, keyword, granularity, bucket)
);

-- D) arXiv timeseries cache
CREATE TABLE IF NOT EXISTS analysis_arxiv_timeseries (
    category TEXT NOT NULL,  -- cs.LG/cs.CL/cs.CV/cs.AI/ALL
    granularity TEXT NOT NULL,  -- 'year'/'month'/'week'/'day'
    bucket TEXT NOT NULL,  -- ISO format
    paper_count INTEGER DEFAULT 0,
    top_keywords_json TEXT,  -- JSON array
    warnings_json TEXT,  -- JSON array of data-quality warning codes/messages
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (category, granularity, bucket)
);

-- E) arXiv emerging topic cache
CREATE TABLE IF NOT EXISTS analysis_arxiv_emerging (
    category TEXT NOT NULL,
    keyword TEXT NOT NULL,
    growth_rate REAL DEFAULT 0.0,  -- Growth rate
    first_seen TEXT,  -- First seen bucket
    recent_count INTEGER DEFAULT 0,  -- Recent occurrence count
    trend TEXT CHECK(trend IN ('rising', 'stable', 'declining')) DEFAULT 'stable',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (category, keyword)
);


-- ========== INDEXES ==========
-- Optimized for common query patterns

-- Raw Layer indexes
CREATE INDEX IF NOT EXISTS idx_raw_papers_source ON raw_papers(source, source_paper_id);
CREATE INDEX IF NOT EXISTS idx_raw_papers_year ON raw_papers(year);
CREATE INDEX IF NOT EXISTS idx_raw_papers_categories ON raw_papers(categories);
CREATE INDEX IF NOT EXISTS idx_raw_papers_retrieved_at ON raw_papers(retrieved_at DESC);  -- Time-series query optimization
-- Structured Layer indexes
CREATE INDEX IF NOT EXISTS idx_papers_venue_year ON papers(venue_id, year);
CREATE INDEX IF NOT EXISTS idx_papers_canonical_title ON papers(LOWER(canonical_title));  -- Title dedupe optimization
CREATE INDEX IF NOT EXISTS idx_papers_domain ON papers(domain);
CREATE INDEX IF NOT EXISTS idx_papers_quality ON papers(quality_flag);
CREATE INDEX IF NOT EXISTS idx_paper_sources_paper ON paper_sources(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_sources_raw ON paper_sources(raw_id);
CREATE INDEX IF NOT EXISTS idx_venues_domain_tier ON venues(domain, tier);  -- Venue query optimization
-- Analysis Layer indexes
CREATE INDEX IF NOT EXISTS idx_paper_keywords_paper ON paper_keywords(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_keywords_keyword ON paper_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_paper_keywords_method ON paper_keywords(method);
CREATE INDEX IF NOT EXISTS idx_paper_keywords_keyword_paper ON paper_keywords(keyword, paper_id);  -- Keyword join optimization
CREATE INDEX IF NOT EXISTS idx_paper_topics_paper ON paper_topics(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_topics_topic_version ON paper_topics(topic_id, taxonomy_version);
CREATE INDEX IF NOT EXISTS idx_paper_topics_domain ON paper_topics(domain);
CREATE INDEX IF NOT EXISTS idx_trend_cache_keyword_year ON trend_cache(keyword, year);

-- Operational indexes
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_source ON ingestion_logs(source, completed_at);
CREATE INDEX IF NOT EXISTS idx_scrape_logs_venue_year ON scrape_logs(venue, year);

-- Analysis Cache indexes
CREATE INDEX IF NOT EXISTS idx_analysis_venue_summary_venue ON analysis_venue_summary(venue);
CREATE INDEX IF NOT EXISTS idx_analysis_keyword_trends_scope ON analysis_keyword_trends(scope, granularity);
CREATE INDEX IF NOT EXISTS idx_analysis_keyword_trends_keyword ON analysis_keyword_trends(keyword);
CREATE INDEX IF NOT EXISTS idx_analysis_arxiv_category ON analysis_arxiv_timeseries(category, granularity);

