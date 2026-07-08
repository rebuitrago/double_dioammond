-- =====================================================================
-- Migration: add the sub-factor layer (IPS two-level hierarchy)
-- =====================================================================
-- Hierarchy becomes:  factor -> determinant -> sub_factor -> indicator
-- Safe to run on a live database: existing data, runs, and scores are
-- untouched. Existing indicators are parked under a "General" sub-factor,
-- so re-scoring reproduces today's results until you add real sub-factors.
-- Run once in the Supabase SQL editor.
-- =====================================================================

-- 1) the new table
create table if not exists sub_factor (
    id             smallserial primary key,
    determinant_id smallint not null references determinant(id),
    name           text     not null,
    position       smallint not null default 1,
    unique (determinant_id, name)
);

-- 2) app read access (consistent with the other read tables)
alter table sub_factor enable row level security;
do $$ begin
    create policy "public read" on sub_factor for select using (true);
exception when duplicate_object then null; end $$;

-- 3) link indicators to sub-factors (nullable first so existing rows survive)
alter table indicator add column if not exists sub_factor_id smallint references sub_factor(id);

-- 4) backfill: one "General" sub-factor per determinant, assign existing indicators
insert into sub_factor (determinant_id, name, position)
select id, 'General', 1 from determinant
on conflict (determinant_id, name) do nothing;

update indicator i
set sub_factor_id = sf.id
from sub_factor sf
where sf.determinant_id = i.determinant_id
  and sf.name = 'General'
  and i.sub_factor_id is null;

-- 5) from now on every indicator must belong to a sub-factor
alter table indicator alter column sub_factor_id set not null;

-- quick check (optional): every indicator now has a sub-factor
-- select count(*) filter (where sub_factor_id is null) as orphans from indicator;  -- expect 0
