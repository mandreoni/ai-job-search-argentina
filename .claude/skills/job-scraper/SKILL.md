---
name: job-scraper
description: >
  Searches the Argentina job market (Remotive API for remote roles + WebSearch across Bumeran,
  Zonajobs, LinkedIn, and startup boards) for new positions matching your profile.
  Deduplicates across runs. Triggers on: job scrape, find jobs, search jobs, new jobs, job search,
  scrape jobs, /scrape
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch, WebSearch, Agent, AskUserQuestion
---

# Job Scraper (Argentina market)

---

## How It Works

This skill discovers Argentina job postings using two channels:

1. **WebSearch — primary.** Claude searches Google/Bing for fresh postings on Bumeran,
   Zonajobs, LinkedIn, and company career pages. All Argentine job boards are either
   Cloudflare-blocked or JavaScript-rendered SPAs, making direct HTTP scraping impossible.
   WebSearch bypasses this by using search engine indexes.
2. **Remotive API — secondary (remote/worldwide roles).** A free public JSON API
   (`remotive.com/api/remote-jobs`) returns structured remote jobs with salary, location
   eligibility, and description. No key or auth required. Good for finding LATAM/worldwide
   remote roles that Argentine boards under-index.
3. **Startup / ATS boards — secondary.** `WebSearch` + `WebFetch` over Wellfound,
   Y Combinator, Greenhouse/Lever/Ashby, and Argentina-specific boards for founding-engineer
   and AI-startup roles.

> **Note on Indeed Argentina:** `ar.indeed.com` is fully behind Cloudflare and its mobile
> endpoint was removed. The `tools/indeed-search/` CLI no longer works. Do not invoke it.

It then deduplicates against previously seen jobs and the application tracker, and presents
new matches with a quick fit assessment.

---

## Invocation

Triggered by: "Find new jobs", "Scrape for jobs", "Any new positions?", "/scrape".

Optional arguments:
- A focus area, e.g. "/scrape ai" or "/scrape full stack"
- "broad" to run all priority categories
- "remote" to hard-filter to remote/hybrid roles
- "linkedin" to include LinkedIn in the WebSearch queries

---

## Execution Steps

### Step 0: Load State

1. Read `job_scraper/seen_jobs.json` (create if missing — start with `{"seen": {}}`)
2. Read `job_search_tracker.csv` to extract already-applied companies+roles
3. Read `search-queries.md` (this directory) for the priority categories, role keywords, and location strings
4. Read the candidate profile (`.claude/skills/job-application-assistant/01-candidate-profile.md` and `04-job-evaluation.md`) to ground the fit assessment in Step 4

### Step 1: WebSearch (primary)

For each priority category in `search-queries.md`, run 2–3 WebSearch queries. By default
use the **top 3 priority categories**; if the user said "broad", run all; if a focus area
was given, prioritise that category.

Use a mix of these search patterns per category (substituting the role title):

```
site:bumeran.com.ar "[ROLE TITLE]" Buenos Aires
site:zonajobs.com.ar "[ROLE TITLE]" Argentina remoto
"[ROLE TITLE]" Argentina remoto OR híbrido site:linkedin.com/jobs
"[ROLE TITLE]" Argentina (remoto OR híbrido) -site:indeed.com
```

For each search result:
- Extract job title, company, location, URL, and any visible teaser from the snippet.
- Only `WebFetch` a result if it's a strong candidate AND the URL is not Cloudflare-blocked.
  Company career pages (Greenhouse, Lever, Ashby, Workable) are usually safe to fetch.
  Bumeran and Zonajobs URLs will 403 — extract what you can from the search snippet only.
- Normalize extracted fields to the standard job record format (see Step 5).

### Step 2: Remotive API (secondary — remote roles)

Call the Remotive API for each top-priority role keyword. Parse the JSON array directly — no
web scraping needed:

```bash
# software-dev category (most relevant), filtered to LATAM/worldwide:
curl -s "https://remotive.com/api/remote-jobs?category=software-dev&limit=100" \
  | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
ar_eligible = [j for j in jobs if any(
    k in (j.get('candidate_required_location') or '').lower()
    for k in ['argentina', 'latin', 'worldwide', 'south america', 'latam', 'anywhere', 'global']
)]
print(json.dumps(ar_eligible, ensure_ascii=False))
"
```

Other useful Remotive categories: `devops-sysadmin`, `data`, `product`, `design`.

Remotive job fields: `id`, `url`, `title`, `company_name`, `tags`, `job_type`,
`publication_date`, `candidate_required_location`, `salary`, `description`.

Map to standard fields: `id` → id, `title` → title, `company_name` → company,
`candidate_required_location` → location, `salary` → salary, `url` → url,
`publication_date` → listing_date, first 300 chars of `description` → teaser.

### Step 3: Startup boards (secondary)

For founding-engineer / AI-startup coverage, run a few WebSearch queries using the
`Startup boards` section of `search-queries.md`. Only fetch a posting with `WebFetch` if it
looks like a strong match AND the URL is a direct ATS link (Greenhouse, Lever, Ashby).
Verify Argentina-eligibility before presenting — many results are US-only.

### Step 4: Deduplicate

For every job from Steps 1–3:
- Skip if its `id`/URL or `company+title` key already exists in `seen_jobs.json`.
- Skip if the `company+role` already appears in `job_search_tracker.csv`.

### Step 5: Quick Fit Assessment

For each NEW job, do a rapid fit check against the candidate profile:

- **High** — role directly hits the candidate's core skills AND location/remote works AND
   (if salary shown) it meets the candidate's salary expectation.
- **Medium** — adjacent role, or location/salary needs checking.
- **Low** — significant skill gap, or on-site outside the candidate's city with no remote.

Apply the location filter from `search-queries.md`.

### Step 6: Store

Add ALL surfaced jobs (new and skipped) to `seen_jobs.json`:
```json
{
  "seen": {
    "<url_or_company_title_key>": {
      "title": "...", "company": "...", "location": "...", "url": "...",
      "salary": "...", "work_arrangement": "...",
      "first_seen": "YYYY-MM-DD", "fit": "high/medium/low", "status": "new/skipped/evaluated",
      "source": "websearch|remotive|startup-board"
    }
  }
}
```

### Step 7: Present Results

Present new jobs in a table sorted by fit (high first):

```
## New Job Matches — YYYY-MM-DD

Found X new positions (Y high, Z medium, W low match).

| # | Fit | Title | Company | Location | Arrangement | Salary | URL |
|---|-----|-------|---------|----------|-------------|--------|-----|
| 1 | High | ... | ... | Buenos Aires | Remote/Hybrid | ... | [Link](...) |

### High-Match Highlights
For each high-match job, add 2-3 bullets: why it matches, key requirements to check, any red flags.
```

After presenting, ask:
> "Want me to evaluate any of these in detail, or apply to one? Give me the number(s)."

To get the full job description for a result:
- **Remotive jobs**: the `description` field is already in the API response — use it directly.
- **WebSearch results**: try `WebFetch` on the company's ATS URL. If the job board URL is
  Cloudflare-blocked, ask the user to paste the description, or use the snippet + any visible
  detail from search results.

Then run the **job-application-assistant** workflow (or `/apply`) on the full description.

### Step 8: Update Tracker (Optional)

If the user decides to apply, add a row to `job_search_tracker.csv`.

---

## Important Rules

1. **Never fabricate job postings.** Only present jobs from actual search results or API data.
2. **Respect deduplication.** Always check `seen_jobs.json` AND `job_search_tracker.csv` first.
3. **Location filter.** Honour the candidate's configured location strings; skip on-site-only
   roles outside their city unless the user opts in.
4. **Only open positions.** Skip anything clearly stale (>60 days old where date is visible).
5. **Do not call the indeed-search CLI.** `ar.indeed.com` is fully blocked — it will return
   empty results and waste time. Use WebSearch instead.
6. **Efficiency.** Run WebSearch queries in parallel where possible; pre-filter on
   title/teaser/salary before fetching full descriptions.
