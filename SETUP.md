# SETUP — Deploy to GitHub + Supabase + Streamlit

Follow in order. Steps 1–4 get you a live app; step 5 automates refreshes.
Time: ~30–45 min. Where a UI label might differ slightly, the *location* is given.

---

## 0. Accounts & local tools
- GitHub account · Supabase account (supabase.com) · Streamlit Community Cloud account (share.streamlit.io, sign in with GitHub).
- Local: `git`, Python 3.11+. Check: `python --version`.
- Unzip the project so you have `app.py`, `db/schema.sql`, `ddd/`, `requirements.txt`, etc.

---

## 1. GitHub repository

**CLI route:**
```bash
cd ddd-platform
git init
git add .
git commit -m "DDD platform: schema, engine, connectors, scoring job, app"
# create an empty repo named ddd-platform on github.com first, then:
git remote add origin https://github.com/<you>/ddd-platform.git
git branch -M main
git push -u origin main
```
**No-CLI route:** on github.com click **New repository** → name it → **uploading an existing file** → drag the whole unzipped folder → Commit.

> A **public** repo deploys a public Streamlit app (free, unlimited). A **private** repo gives you one private app on the free tier. The `.gitignore` already excludes `.env` and `.streamlit/secrets.toml` so secrets never get committed.

---

## 2. Supabase

### 2a. Create the project
supabase.com → **New project** → name it, set a **database password** (save it), pick a region near your users → wait ~2 min.

### 2b. Create the schema
Left sidebar → **SQL Editor** → **New query** → paste the entire contents of `db/schema.sql` → **Run**. You should see the tables under **Table Editor** (factor, determinant, indicator, observation, run, score) plus the `diamond_coords` view.

### 2c. Seed the countries you'll analyze
New query → adjust the list → **Run**:
```sql
insert into country (iso3, name, region, is_emerging) values
  ('KOR','Korea, Rep.','East Asia', false),
  ('SGP','Singapore','East Asia', false),
  ('BRA','Brazil','LatAm', true),
  ('IND','India','South Asia', true),
  ('IDN','Indonesia','SE Asia', true),
  ('MEX','Mexico','LatAm', true),
  ('ZAF','South Africa','Africa', true),
  ('TUR','Türkiye','MENA', true),
  ('VNM','Viet Nam','SE Asia', true),
  ('POL','Poland','Europe', true)
on conflict (iso3) do nothing;
```
(`ingest.py` pulls data for exactly the countries in this table.)

### 2d. Let the app read (Row Level Security)
The app uses the low-privilege **publishable** key, so allow public reads on the
tables it touches. New query → **Run**:
```sql
alter table run         enable row level security;
alter table score       enable row level security;
alter table determinant enable row level security;
alter table factor      enable row level security;
create policy "public read" on run         for select using (true);
create policy "public read" on score       for select using (true);
create policy "public read" on determinant for select using (true);
create policy "public read" on factor      for select using (true);
```
(Writes still require the secret key, which bypasses RLS — see step 3.)

### 2e. Get your keys
**Settings → API Keys** (the **Publishable and secret API keys** tab). Copy:
- **Project URL** → `https://xxxx.supabase.co`
- **Publishable key** → `sb_publishable_...`  (for the app; safe to expose)
- **Secret key** → `sb_secret_...`  (for ingest/scoring; **never commit**)

> New Supabase projects no longer ship anon/service_role keys — publishable/secret are the replacements. Supabase auto-revokes any secret key it detects in a public GitHub repo, so keep it only in the secret stores below.

---

## 3. Load data + create the first scoring run

You can do this **locally** (below) or skip to step 5 and let GitHub Actions do it.

```bash
pip install -r requirements.txt
export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_SECRET_KEY="sb_secret_..."

# pull WDI/WGI for your seeded countries
python -m ddd.ingest --start 2010

# preview scoring + coverage WITHOUT writing
python -m ddd.score_run --label "EM 2010-2023 pooled" --normalization pooled --dry-run

# happy with coverage? write the run:
python -m ddd.score_run --label "EM 2010-2023 pooled" --normalization pooled --vintage "WDI 2025-03"
```
Check **Table Editor → score** in Supabase — it should now have rows.

---

## 4. Deploy the Streamlit app

1. Go to **share.streamlit.io** → **Create app** → "Yup, I have an app."
2. Repository `=<you>/ddd-platform`, Branch `main`, Main file path `app.py`.
3. (Optional) pick a subdomain → app lives at `https://<subdomain>.streamlit.app`.
4. **Advanced settings → Secrets** → paste (TOML):
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
   ```
5. **Deploy.** First build takes a few minutes. The app reads the run you created and draws the diamonds.

> Only the **publishable** key goes here. Streamlit runs server-side, so even the
> publishable key isn't exposed in the browser — and being low-privilege, it's
> safe regardless. Never put the secret key in the app.

---

## 5. Automate refreshes (GitHub Actions)

The workflow `.github/workflows/refresh.yml` re-pulls data and rescores weekly.

1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**. Add two:
   - `SUPABASE_URL` = `https://xxxx.supabase.co`
   - `SUPABASE_SECRET_KEY` = `sb_secret_...`
2. Test it now: **Actions** tab → **Refresh data and rescore** → **Run workflow** (pick `pooled`). Watch the logs.
3. After it succeeds, a new run appears in the app's run selector. The schedule (`cron: 0 6 * * 1`) then runs it every Monday.

---

## Security checklist
- [ ] Secret key only in **GitHub Actions secrets** and your local shell — never in code, never committed.
- [ ] Publishable key only in **Streamlit secrets** (and `.streamlit/secrets.toml` locally, which is git-ignored).
- [ ] `.env` and `.streamlit/secrets.toml` confirmed in `.gitignore`.
- [ ] RLS enabled with public-read policies (step 2d) — app reads work, writes don't.

## Troubleshooting
- **App shows "No scoring runs found"** → you haven't run `score_run` yet (step 3 or 5).
- **App connects but tables look empty** → RLS policies (step 2d) not applied, or applied before data existed (re-run the policy SQL; it's idempotent except the `create policy`, which errors if it already exists — safe to ignore).
- **Ingest says "No countries"** → seed the `country` table (step 2c).
- **Actions fails on auth** → check the two repo secrets are named exactly `SUPABASE_URL` / `SUPABASE_SECRET_KEY`.
