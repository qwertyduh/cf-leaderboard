-- 004_fetch_log_source: add source column to fetch_log
-- Run this after 001_tables.sql.  (No dependency on 002 or 003.)

ALTER TABLE fetch_log ADD COLUMN source TEXT;
