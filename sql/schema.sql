-- The whole database. Safe to run on every start: nothing here drops data.

-- One company career page on one job platform.
CREATE TABLE IF NOT EXISTS boards (
    board_id   INTEGER PRIMARY KEY,
    platform   TEXT NOT NULL,
    board      TEXT NOT NULL,
    company    TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,   -- still listed in config/boards.csv
    etag       TEXT,                         -- lets the next run skip a board that hasn't changed
    listed     INTEGER,                      -- postings on the board at the last read
    in_us      INTEGER,                      -- how many of those are in the US
    checked_at TEXT,                         -- date of the last successful read
    failures   INTEGER NOT NULL DEFAULT 0,   -- failed reads in a row
    UNIQUE (platform, board)
);

-- One row for every matching posting ever seen. Closed postings are kept so their lifetime can be
-- measured.
CREATE TABLE IF NOT EXISTS postings (
    posting_id  INTEGER PRIMARY KEY,
    board_id    INTEGER NOT NULL REFERENCES boards (board_id),
    source_id   TEXT NOT NULL,               -- the platform's own id
    role_id     INTEGER,                     -- postings for the same job share a role_id
    title       TEXT NOT NULL,
    title_key   TEXT NOT NULL,               -- title without the city, level of detail, etc.
    family      TEXT NOT NULL,
    location    TEXT NOT NULL,
    feed_workplace TEXT,                     -- remote, hybrid or onsite, when the feed says so
    workplace   TEXT,                        -- the feed's answer, else read from the text
    department  TEXT,
    url         TEXT NOT NULL,
    posted_at   TEXT,
    updated_at  TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    closed_at   TEXT,
    description TEXT,
    feed_pay_min REAL,                       -- pay listed as data in the feed, yearly dollars
    feed_pay_max REAL,
    pay_min     REAL,                        -- pay used for scoring: the feed's, else from the text
    pay_max     REAL,
    years_min   INTEGER,                     -- least experience asked for; NULL = not stated
    score       INTEGER,
    reasons     TEXT,                        -- JSON list explaining the score
    UNIQUE (board_id, source_id)
);

CREATE TABLE IF NOT EXISTS posting_markets (
    posting_id INTEGER NOT NULL REFERENCES postings (posting_id) ON DELETE CASCADE,
    market     TEXT NOT NULL,
    PRIMARY KEY (posting_id, market)
);

CREATE TABLE IF NOT EXISTS posting_skills (
    posting_id INTEGER NOT NULL REFERENCES postings (posting_id) ON DELETE CASCADE,
    skill      TEXT NOT NULL,
    level      TEXT NOT NULL CHECK (level IN ('required', 'preferred')),
    PRIMARY KEY (posting_id, skill)
);

-- One row per run, so a bad day shows up.
CREATE TABLE IF NOT EXISTS runs (
    run_id       INTEGER PRIMARY KEY,
    run_date     TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    seconds      REAL,
    boards_read  INTEGER,                    -- downloaded
    boards_same  INTEGER,                    -- unchanged since last time, so not downloaded
    boards_failed INTEGER,
    listed       INTEGER,                    -- postings on all boards
    in_us        INTEGER,
    matched      INTEGER,                    -- open postings that match the profile
    new          INTEGER,
    closed       INTEGER,
    details      INTEGER                     -- descriptions fetched one at a time
);

-- Answers from the optional AI step, kept by content so the same text is never sent twice.
CREATE TABLE IF NOT EXISTS ai_facts (
    content_hash TEXT PRIMARY KEY,
    model        TEXT NOT NULL,
    facts        TEXT NOT NULL,              -- JSON
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE INDEX IF NOT EXISTS postings_open ON postings (closed_at, score);
CREATE INDEX IF NOT EXISTS postings_role ON postings (role_id);

-- Full-text search over open postings.
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5 (title, company, location, description);

-- The table almost every question starts from: one row per open job, however many times and places
-- the company listed it.
DROP VIEW IF EXISTS open_roles;
CREATE VIEW open_roles AS
SELECT *
FROM (
    SELECT
        p.*,
        b.company,
        b.platform,
        COUNT(*) OVER (PARTITION BY p.role_id) AS listings,
        ROW_NUMBER() OVER (
            PARTITION BY p.role_id
            ORDER BY p.score DESC, p.posted_at DESC, p.posting_id
        ) AS pick
    FROM postings AS p
    JOIN boards AS b USING (board_id)
    WHERE p.closed_at IS NULL
)
WHERE pick = 1;
