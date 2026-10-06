-- Brain OS schema. Every table below (except the plumbing ones) is audited by
-- triggers that db.py generates: nothing changes without a row in `changes`.

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- One row. Who is writing and why; the audit triggers read it. `purge` lets
-- `demo clear` and `restore` bypass the append-only rules, and nothing else.
CREATE TABLE IF NOT EXISTS ctx (
  id     INTEGER PRIMARY KEY CHECK (id = 1),
  actor  TEXT NOT NULL DEFAULT 'user',
  reason TEXT,
  purge  INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO ctx (id) VALUES (1);

CREATE TABLE IF NOT EXISTS changes (
  id        INTEGER PRIMARY KEY,
  ts        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
  actor     TEXT NOT NULL,
  reason    TEXT,
  entity    TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  action    TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
  before    TEXT,
  after     TEXT
);
CREATE INDEX IF NOT EXISTS changes_entity ON changes (entity, entity_id);
CREATE INDEX IF NOT EXISTS changes_ts ON changes (ts);

-- Which rows the demo seed created, so `demo clear` removes them and nothing else.
CREATE TABLE IF NOT EXISTS demo_rows (
  tbl    TEXT NOT NULL,
  row_id INTEGER NOT NULL,
  PRIMARY KEY (tbl, row_id)
);

CREATE TABLE IF NOT EXISTS automation_runs (
  id         INTEGER PRIMARY KEY,
  automation TEXT NOT NULL,
  job_key    TEXT NOT NULL,
  label      TEXT NOT NULL,
  kind       TEXT NOT NULL,
  status     TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at   TEXT,
  output     TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------- the business

-- Company facts as key/value: name, tagline, stage, hours_per_week, runway, kill_condition, ...
CREATE TABLE IF NOT EXISTS profile (
  id         INTEGER PRIMARY KEY,
  key        TEXT NOT NULL UNIQUE,
  value      TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
  id         INTEGER PRIMARY KEY,
  slug       TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  owner      TEXT NOT NULL DEFAULT '',
  hours      TEXT NOT NULL DEFAULT '',
  owns       TEXT NOT NULL DEFAULT '',
  intro      TEXT NOT NULL DEFAULT '',
  brief      TEXT NOT NULL DEFAULT '',
  briefed_at TEXT,
  position   INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- All prose lives here: notes, source material, playbooks, and the sections of a
-- department's page (kind 'section', slug '<dept>/<section>').
CREATE TABLE IF NOT EXISTS documents (
  id            INTEGER PRIMARY KEY,
  slug          TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  kind          TEXT NOT NULL CHECK (kind IN ('note', 'source', 'playbook', 'section')),
  department_id INTEGER REFERENCES departments (id) ON DELETE SET NULL,
  tags          TEXT NOT NULL DEFAULT '',
  body          TEXT NOT NULL DEFAULT '',
  position      INTEGER NOT NULL DEFAULT 0,
  ingested      INTEGER NOT NULL DEFAULT 0,
  source_ref    TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_kind ON documents (kind);
CREATE INDEX IF NOT EXISTS documents_dept ON documents (department_id);

-- ---------------------------------------------------------------- direction

CREATE TABLE IF NOT EXISTS goals (
  id         INTEGER PRIMARY KEY,
  level      TEXT NOT NULL CHECK (level IN ('north_star', 'year')),
  text       TEXT NOT NULL,
  detail     TEXT NOT NULL DEFAULT '',
  position   INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bets (
  id            INTEGER PRIMARY KEY,
  n             INTEGER NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  department_id INTEGER REFERENCES departments (id) ON DELETE SET NULL,
  why           TEXT NOT NULL DEFAULT '',
  success       TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'not started',
  status_note   TEXT NOT NULL DEFAULT '',
  next_steps    TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- Weekly goals and daily priorities. `bet` is the bet's number; NULL = serves none.
CREATE TABLE IF NOT EXISTS items (
  id         INTEGER PRIMARY KEY,
  kind       TEXT NOT NULL CHECK (kind IN ('goal', 'priority')),
  text       TEXT NOT NULL,
  bet        INTEGER,
  week       TEXT NOT NULL,
  day        TEXT,
  done_at    TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_kind_week ON items (kind, week);

CREATE TABLE IF NOT EXISTS open_calls (
  id          INTEGER PRIMARY KEY,
  question    TEXT NOT NULL,
  context     TEXT NOT NULL DEFAULT '',
  resolution  TEXT NOT NULL DEFAULT '',
  resolved_at TEXT,
  created_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------- memory

CREATE TABLE IF NOT EXISTS decisions (
  id            INTEGER PRIMARY KEY,
  title         TEXT NOT NULL,
  decided       TEXT NOT NULL,
  why           TEXT NOT NULL DEFAULT '',
  expect        TEXT NOT NULL CHECK (length(trim(expect)) > 0),
  review_on     TEXT NOT NULL CHECK (review_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  outcome       TEXT NOT NULL DEFAULT '',
  outcome_at    TEXT,
  department_id INTEGER REFERENCES departments (id) ON DELETE SET NULL,
  supersedes    INTEGER REFERENCES decisions (id),
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS log_entries (
  id            INTEGER PRIMARY KEY,
  date          TEXT NOT NULL,
  type          TEXT NOT NULL,
  title         TEXT NOT NULL,
  body          TEXT NOT NULL DEFAULT '',
  department_id INTEGER REFERENCES departments (id) ON DELETE SET NULL,
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS log_date ON log_entries (date);

CREATE TABLE IF NOT EXISTS inbox (
  id         INTEGER PRIMARY KEY,
  text       TEXT NOT NULL,
  filed_at   TEXT,
  filed_to   TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

-- ---------------------------------------------------------------- numbers

CREATE TABLE IF NOT EXISTS metrics (
  id            INTEGER PRIMARY KEY,
  key           TEXT NOT NULL UNIQUE CHECK (key NOT GLOB '*[^a-z0-9_]*'),
  name          TEXT NOT NULL,
  department_id INTEGER REFERENCES departments (id) ON DELETE SET NULL,
  definition    TEXT NOT NULL DEFAULT '',
  unit          TEXT NOT NULL DEFAULT '',
  source        TEXT NOT NULL DEFAULT 'manual',
  healthy       TEXT NOT NULL DEFAULT '',
  watch         TEXT NOT NULL DEFAULT '',
  bad           TEXT NOT NULL DEFAULT '',
  position      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- One value per metric per day. A point deleted by hand is tombstoned so a
-- later pull can't bring it back.
CREATE TABLE IF NOT EXISTS metric_points (
  id          INTEGER PRIMARY KEY,
  metric_id   INTEGER NOT NULL REFERENCES metrics (id) ON DELETE CASCADE,
  as_of       TEXT NOT NULL,
  value       REAL NOT NULL,
  origin      TEXT NOT NULL DEFAULT 'manual',
  note        TEXT NOT NULL DEFAULT '',
  recorded_at TEXT NOT NULL,
  deleted_at  TEXT,
  UNIQUE (metric_id, as_of)
);

-- ---------------------------------------------------------------- append-only rules

CREATE TRIGGER IF NOT EXISTS changes_no_update BEFORE UPDATE ON changes
WHEN (SELECT purge FROM ctx) = 0
BEGIN SELECT RAISE(ABORT, 'the change history is append-only'); END;

CREATE TRIGGER IF NOT EXISTS changes_no_delete BEFORE DELETE ON changes
WHEN (SELECT purge FROM ctx) = 0
BEGIN SELECT RAISE(ABORT, 'the change history is append-only'); END;

CREATE TRIGGER IF NOT EXISTS log_entries_no_update BEFORE UPDATE ON log_entries
WHEN (SELECT purge FROM ctx) = 0
BEGIN SELECT RAISE(ABORT, 'log entries are append-only: add a new entry that supersedes it'); END;

CREATE TRIGGER IF NOT EXISTS log_entries_no_delete BEFORE DELETE ON log_entries
WHEN (SELECT purge FROM ctx) = 0 AND substr(OLD.created_at, 1, 10) < date('now', 'localtime')
BEGIN SELECT RAISE(ABORT, 'log entries are append-only (only today''s can be deleted): add a new entry that supersedes it'); END;

CREATE TRIGGER IF NOT EXISTS decisions_locked BEFORE UPDATE ON decisions
WHEN (SELECT purge FROM ctx) = 0 AND substr(OLD.created_at, 1, 10) < date('now', 'localtime')
  AND (NEW.title IS NOT OLD.title OR NEW.decided IS NOT OLD.decided OR NEW.why IS NOT OLD.why
       OR NEW.expect IS NOT OLD.expect OR NEW.review_on IS NOT OLD.review_on
       OR NEW.department_id IS NOT OLD.department_id OR NEW.supersedes IS NOT OLD.supersedes
       OR NEW.created_at IS NOT OLD.created_at)
BEGIN SELECT RAISE(ABORT, 'past decisions are append-only: only the outcome can be filled in. Log a new decision that supersedes it'); END;

CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
WHEN (SELECT purge FROM ctx) = 0 AND substr(OLD.created_at, 1, 10) < date('now', 'localtime')
BEGIN SELECT RAISE(ABORT, 'past decisions are append-only (only today''s can be deleted)'); END;
