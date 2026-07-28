-- Schema for the Postgres backend. Safe to run more than once.
--
-- Two things run this file:
--   1. Postgres itself, on first boot, via the /docker-entrypoint-initdb.d mount in
--      docker-compose.yml (only ever runs when the volume is empty).
--   2. The app at startup, so a database that already has a volume but no table
--      still ends up with one.
-- Both paths use this same file, so the schema is defined in exactly one place.

CREATE TABLE IF NOT EXISTS tasks (
    id    SERIAL  PRIMARY KEY,
    title TEXT    NOT NULL,
    done  BOOLEAN NOT NULL DEFAULT false
);

-- Seed the three example tasks, but only while the table is still empty.
INSERT INTO tasks (title, done)
SELECT seed.title, seed.done
FROM (VALUES
    ('Buy milk',     false),
    ('Walk dog',     true),
    ('Write README', false)
) AS seed(title, done)
WHERE NOT EXISTS (SELECT 1 FROM tasks);
