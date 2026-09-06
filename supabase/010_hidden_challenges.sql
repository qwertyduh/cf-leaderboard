-- 010_hidden_challenges: the "lights up as people solve them" circle grid
-- Run this after 006_engagement.sql.
--
-- Powers the hidden-challenge board on the site (§7 side quests). One row per
-- hidden challenge; organizers flip `lit` to true (and optionally set
-- `solved_by`) the moment someone cracks it. Purely manual - there is no
-- automated solver detection, by design.

CREATE TABLE hidden_challenges (
    id         uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
    label      text     NOT NULL,          -- short name, shown on hover
    hint       text,                        -- optional teaser
    lit        boolean  NOT NULL DEFAULT false,  -- true = solved, circle glows
    solved_by  text,                        -- optional: handle of first solver
    lit_at     timestamptz,                 -- when it was lit
    sort_order smallint NOT NULL DEFAULT 0
);

-- ── RLS: public read-only, same pattern as 002_rls.sql ─────────────────────
ALTER TABLE hidden_challenges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon can select hidden_challenges"
    ON hidden_challenges FOR SELECT TO anon USING (true);

CREATE POLICY "authenticated can select hidden_challenges"
    ON hidden_challenges FOR SELECT TO authenticated USING (true);

-- Organizers seed and light these via the service_role (SQL editor), e.g.:
--   insert into hidden_challenges (label, hint, sort_order) values
--     ('Inspect Element', 'the source hides a door', 1),
--     ('Assembled URL',   'outputs are fragments',   2);
--   update hidden_challenges set lit = true, solved_by = 'qwertyduh',
--     lit_at = now() where label = 'Inspect Element';
