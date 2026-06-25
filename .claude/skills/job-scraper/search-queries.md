# Search Queries for Job Scraper

<!-- PRIMARY discovery = WebSearch (Google/Bing) + Remotive API. Indeed AR is fully blocked. -->
<!-- Re-run /setup --section search to update as priorities evolve. -->

## How /scrape uses this file

For each priority category below, the `job-scraper` skill runs 2–3 WebSearch queries per
role-title keyword across LinkedIn, company career pages, and startup/ATS boards, then calls
the Remotive API for remote/worldwide roles:

```
"[ROLE TITLE]" remote (worldwide OR LATAM OR "Latin America" OR Argentina) site:linkedin.com/jobs
"[ROLE TITLE]" remote site:greenhouse.io OR site:lever.co OR site:ashbyhq.com
"[ROLE TITLE]" remote Argentina -site:indeed.com
```

It also runs a few `WebSearch` + `WebFetch` queries over startup ATS boards (Section: Startup boards).

## Search profile

- **Candidate:** Martin Andreoni, Ph.D. — senior AI/ML & security research-leadership profile.
- **Arrangement:** Remote-first, based in Argentina. Targets international / LATAM-eligible remote
  roles paid in USD. No relocation.
- **Seniority:** Senior / Lead / Principal / Director level (11+ years, leads teams of 6–13+).

## Locations

Remote is the primary filter. Location strings to recognise as eligible:

- `Remote` / `Remote - Worldwide` / `Remote - Americas` / `Remote - LATAM` / `Remote - Argentina`
- `Buenos Aires` (for occasional hybrid; home base in Argentina)
- Other Argentina cities for hybrid: `Cordoba`, `Rosario`, `Mendoza`, `San Juan`, `La Plata`

## Priority Categories (role-title keywords)

### Priority 1: AI / ML Research & Engineering Leadership   *(strongest direction)*
```
Director of AI
Head of AI Research
Principal Research Scientist
Machine Learning Research Lead
Applied Research Lead (ML)
```

### Priority 2: Security / Cybersecurity (leadership & research)
```
Security Research Lead
Principal Security Engineer
Head of Security Research
AI Security Engineer
ML Security Researcher
```

### Priority 3: Hands-on AI / ML Engineering   *(roles leaning on PyTorch/TensorFlow + research)*
```
Machine Learning Engineer
Applied Scientist
Senior ML Engineer
Research Engineer (ML)
```

### Priority 4: Engineering Leadership (broad)   *(wider net)*
```
Engineering Manager
Director of Engineering
VP Engineering
Founding Engineer
Head of Engineering
```

## Startup boards (secondary — WebSearch, not Indeed)

For founding-engineer / AI-startup roles, run a few of these and verify remote-eligibility:
```
site:wellfound.com (AI OR ML OR security) remote LATAM
site:workatastartup.com (machine learning OR security) engineer remote
"founding engineer" OR "head of AI" remote (LATAM OR worldwide) startup
site:jobs.ashbyhq.com (machine learning OR security) remote
```

## Fit filters

- **Location:** keep fully-remote roles eligible for Argentina / LATAM / worldwide / Americas. Drop
  on-site or relocation-required roles. Hybrid only if the office is in Argentina.
- **Salary:** target **USD 8,000–10,000 / month** (remote). Flag roles showing pay in or above that
  band; don't auto-reject roles that hide salary. Note ARS vs USD where shown.
- **Seniority:** prefer senior / lead / principal / director; de-prioritise junior/mid roles.
- **Recency:** prefer `listing_date` within the last ~21 days; flag older ones.

## Adapting on focus

- `/scrape ai` → Priority 1 + 3 keywords.
- `/scrape security` → Priority 2 keywords.
- `/scrape remote` → all categories, hard-filtered to remote.
- `/scrape linkedin` → also query LinkedIn guest endpoints (at-your-own-risk).
