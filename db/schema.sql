-- =====================================================================
-- Dual Double Diamond platform - Supabase / PostgreSQL schema
-- =====================================================================
-- Design goals:
--   * Framework stored as DATA, not code  -> add a criterion = INSERT a row
--   * Every observation carries provenance -> research-grade traceability
--   * Scores are versioned by "run"        -> reproducible across vintages
-- Run this in the Supabase SQL editor (or via migration).
-- =====================================================================

-- ---------- enums -----------------------------------------------------
create type factor_kind   as enum ('physical', 'human');
create type context_kind  as enum ('domestic', 'international');
create type polarity_kind as enum ('+', '-');                 -- '-' = lower is better
create type norm_method   as enum ('ratio_max', 'minmax');    -- ratio_max = paper's method
create type coverage_flag as enum ('good', 'patchy', 'thin'); -- emerging-economy data availability
create type track_kind    as enum ('A', 'B');                 -- A = automated API, B = manual/curated

-- ---------- framework (the 8 determinants x 2 contexts = 16 cells) -----
create table factor (
    id    smallserial primary key,
    name  factor_kind not null unique
);

create table determinant (
    id        smallserial primary key,
    factor_id smallint not null references factor(id),
    name      text     not null,
    position  smallint not null,                 -- axis order on the diamond (1..4)
    unique (factor_id, name),
    unique (factor_id, position)
);

create table indicator (
    id            bigserial primary key,
    determinant_id smallint     not null references determinant(id),
    context       context_kind  not null,        -- cell = (determinant_id, context)
    name          text          not null,
    source        text          not null,        -- 'WDI', 'UNCTAD', 'ILOSTAT', ...
    source_code   text,                           -- e.g. 'NY.GDP.MKTP.CD'
    polarity      polarity_kind not null default '+',
    method        norm_method   not null default 'ratio_max',
    coverage      coverage_flag not null default 'good',
    track         track_kind    not null default 'A',
    active        boolean       not null default true,
    notes         text,
    unique (determinant_id, context, name)
);

-- ---------- reference: countries -------------------------------------
create table country (
    iso3        char(3) primary key,
    name        text not null,
    region      text,
    is_emerging boolean not null default false
);

-- ---------- raw data with provenance ---------------------------------
create table observation (
    id             bigserial primary key,
    indicator_id   bigint  not null references indicator(id),
    country_iso3   char(3) not null references country(iso3),
    year           smallint not null,
    raw_value      double precision,             -- null allowed = genuine gap
    source_vintage text,                          -- e.g. 'WDI 2025-03'
    loaded_at      timestamptz not null default now(),
    unique (indicator_id, country_iso3, year)
);
create index obs_lookup on observation (indicator_id, year);
create index obs_country on observation (country_iso3, year);

-- ---------- methodology runs (reproducibility) -----------------------
-- A run pins WHICH countries, WHICH indicators, and WHICH vintage produced
-- a set of scores. Scores are only comparable within the same run.
create table run (
    id           bigserial primary key,
    label        text not null,
    country_set  text[] not null,                -- iso3 codes included
    indicator_set bigint[] not null,             -- indicator ids included
    data_vintage text,
    created_at   timestamptz not null default now()
);

-- ---------- computed scores ------------------------------------------
create table score (
    run_id        bigint  not null references run(id) on delete cascade,
    country_iso3  char(3) not null references country(iso3),
    year          smallint not null,
    determinant_id smallint not null references determinant(id),
    context       context_kind not null,
    index         double precision not null,     -- 0..100
    n_indicators  smallint not null,             -- how many fed this score
    primary key (run_id, country_iso3, year, determinant_id, context)
);

-- ---------- convenience view: diamond coordinates --------------------
-- international coord = domestic + international (the paper's construction)
create view diamond_coords as
select s.run_id, s.country_iso3, s.year,
       d.factor_id, d.id as determinant_id, d.name as determinant, d.position,
       max(case when s.context='domestic'      then s.index end) as domestic,
       max(case when s.context='international'  then s.index end) as international,
       coalesce(max(case when s.context='domestic' then s.index end),0)
     + coalesce(max(case when s.context='international' then s.index end),0)
       as international_coord
from score s
join determinant d on d.id = s.determinant_id
group by s.run_id, s.country_iso3, s.year, d.factor_id, d.id, d.name, d.position;

-- =====================================================================
-- SEED: the framework skeleton (4 physical + 4 human determinants)
-- =====================================================================
insert into factor (name) values ('physical'), ('human');

insert into determinant (factor_id, name, position)
select f.id, x.name, x.position from factor f
join (values
    ('physical','Factor Conditions',1),
    ('physical','Demand Conditions',2),
    ('physical','Related & Supporting Industries',3),
    ('physical','Firm Strategy, Structure & Rivalry',4),
    ('human','Workers',1),
    ('human','Politicians & Bureaucrats',2),
    ('human','Entrepreneurs',3),
    ('human','Professionals',4)
) as x(factor_name, name, position) on x.factor_name = f.name::text;

-- SEED: a starter slice of the indicator catalog (extend freely).
-- Cell is (determinant, context). Add a criterion later = one INSERT here.
insert into indicator (determinant_id, context, name, source, source_code, polarity, method, coverage, track)
select d.id, v.context::context_kind, v.name, v.source, v.code,
       v.polarity::polarity_kind, v.method::norm_method,
       v.coverage::coverage_flag, v.track::track_kind
from determinant d
join (values
  -- Domestic Physical
  ('Factor Conditions','domestic','Total natural resources rents (% GDP)','WDI','NY.GDP.TOTL.RT.ZS','+','ratio_max','good','A'),
  ('Factor Conditions','domestic','R&D expenditure (% GDP)','WDI','GB.XPD.RSDV.GD.ZS','+','ratio_max','patchy','A'),
  ('Demand Conditions','domestic','GDP (current US$)','WDI','NY.GDP.MKTP.CD','+','ratio_max','good','A'),
  ('Demand Conditions','domestic','GDP growth (annual %)','WDI','NY.GDP.MKTP.KD.ZG','+','ratio_max','good','A'),
  ('Related & Supporting Industries','domestic','Mobile subscriptions (per 100)','WDI','IT.CEL.SETS.P2','+','ratio_max','good','A'),
  ('Firm Strategy, Structure & Rivalry','domestic','New business density (per 1,000)','WDI','IC.BUS.NDNS.ZS','+','ratio_max','patchy','A'),
  -- International Physical
  ('Factor Conditions','international','FDI net inflows (% GDP)','WDI','BX.KLT.DINV.WD.GD.ZS','+','ratio_max','good','A'),
  ('Factor Conditions','international','FDI net outflows (% GDP)','WDI','BM.KLT.DINV.WD.GD.ZS','+','ratio_max','good','A'),
  ('Demand Conditions','international','Exports of goods & services (% GDP)','WDI','NE.EXP.GNFS.ZS','+','ratio_max','good','A'),
  ('Firm Strategy, Structure & Rivalry','international','Applied tariff rate, weighted mean','WDI','TM.TAX.MRCH.WM.AR.ZS','-','ratio_max','good','A'),
  ('Firm Strategy, Structure & Rivalry','international','Trade (% GDP)','WDI','NE.TRD.GNFS.ZS','+','ratio_max','good','A'),
  -- Domestic Human  (note: WGI uses minmax because estimates can be negative)
  ('Workers','domestic','Labor force participation rate (%)','WDI','SL.TLF.CACT.ZS','+','ratio_max','good','A'),
  ('Politicians & Bureaucrats','domestic','Government Effectiveness (estimate)','WGI','GE.EST','+','minmax','good','A'),
  ('Politicians & Bureaucrats','domestic','Control of Corruption (estimate)','WGI','CC.EST','+','minmax','good','A'),
  ('Professionals','domestic','Researchers in R&D (per million)','WDI','SP.POP.SCIE.RD.P6','+','ratio_max','patchy','A'),
  -- International Human
  ('Workers','international','International migrant stock (% pop)','WDI','SM.POP.TOTL.ZS','+','ratio_max','good','A'),
  ('Entrepreneurs','international','High-technology exports (% mfg exports)','WDI','TX.VAL.TECH.MF.ZS','+','ratio_max','patchy','A'),
  ('Professionals','international','International students inbound (% tertiary)','UNESCO',null,'+','ratio_max','patchy','B')
) as v(det, context, name, source, code, polarity, method, coverage, track)
  on v.det = d.name;
