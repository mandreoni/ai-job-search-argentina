#!/usr/bin/env python3
"""
job-scraper — Argentina job search CLI.

Sources:
  • Remotive API   — remote tech jobs, filter by LATAM/Worldwide eligibility
  • Jobicy API     — LATAM-focused remote jobs

All Argentine job boards (Indeed AR, Bumeran, Zonajobs, Computrabajo) are behind
Cloudflare or React SPAs — plain HTTP scraping cannot get through them. Use the
Claude Code /scrape skill for AI-powered discovery across those boards.

Usage:
  python3 job_scraper.py --keywords "Python Developer"
  python3 job_scraper.py --keywords "Data Scientist" --region latam
  python3 job_scraper.py --keywords "ML Engineer" --region worldwide --table
  python3 job_scraper.py --keywords "Backend" --category software-development --pages 2

Regions:
  latam       — LATAM, Latin America, South America, Argentina
  worldwide   — Worldwide, Anywhere, Global (broadest net)
  any         — all of the above (default)

Output: JSON array on stdout (default), or human table with --table.
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from html import unescape
from urllib.error import HTTPError, URLError

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4.1 Safari/605.1.15"
)

# Region keyword sets used to filter candidate_required_location fields
REGION_KEYWORDS = {
    "latam": ["latam", "latin america", "latin", "south america", "argentina", "latinoamérica"],
    "worldwide": ["worldwide", "anywhere", "global", "any country", "all countries"],
}
REGION_KEYWORDS["any"] = REGION_KEYWORDS["latam"] + REGION_KEYWORDS["worldwide"]

# Remotive category slugs (from /api/remote-jobs/categories)
REMOTIVE_CATEGORIES = [
    "software-development",
    "artificial-intelligence",
    "data",
    "devops",
    "engineering",
    "information-technology",
    "qa",
    "product",
    "design",
]


def _get(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _matches_region(location_str, region):
    """Return True if the location string is eligible for the given region."""
    if not location_str:
        return region == "any"
    loc = location_str.lower()
    keywords = REGION_KEYWORDS.get(region, REGION_KEYWORDS["any"])
    return any(k in loc for k in keywords)


def _keyword_match(job_text, keywords):
    """Return True if any keyword appears in the job text (case-insensitive)."""
    if not keywords:
        return True
    text = job_text.lower()
    return any(kw.lower() in text for kw in keywords)


# ---------------------------------------------------------------------------
# Remotive
# ---------------------------------------------------------------------------

def fetch_remotive(keywords_list, region, categories=None, limit=100):
    """Fetch jobs from Remotive API, filter by region and keywords."""
    if categories is None:
        categories = ["software-development", "artificial-intelligence", "data", "devops"]

    seen_ids = set()
    results = []

    for cat in categories:
        url = f"https://remotive.com/api/remote-jobs?category={cat}&limit={limit}"
        try:
            data = _get(url)
        except (HTTPError, URLError, json.JSONDecodeError) as e:
            print(f"[remotive] {cat}: {e}", file=sys.stderr)
            continue

        for j in data.get("jobs", []):
            jid = str(j.get("id", ""))
            if jid in seen_ids:
                continue

            location = j.get("candidate_required_location") or ""
            if not _matches_region(location, region):
                continue

            combined = f"{j.get('title','')} {' '.join(j.get('tags') or [])} {j.get('jobExcerpt','')}"
            if not _keyword_match(combined, keywords_list):
                continue

            seen_ids.add(jid)
            desc = j.get("description") or ""
            results.append({
                "id": f"remotive-{jid}",
                "title": (j.get("title") or "").strip(),
                "company": (j.get("company_name") or "").strip(),
                "location": location,
                "salary": (j.get("salary") or "").strip(),
                "work_arrangement": "remote",
                "listing_date": (j.get("publication_date") or "")[:10],
                "teaser": re.sub(r"<[^>]+>", " ", desc).strip()[:300],
                "url": j.get("url") or "",
                "source": "remotive",
            })

        time.sleep(0.3)

    return results


# ---------------------------------------------------------------------------
# Jobicy
# ---------------------------------------------------------------------------

def fetch_jobicy(keywords_list, region, count=50):
    """Fetch jobs from Jobicy API, filter by region and keywords."""
    # Jobicy supports geo=latam natively; for worldwide we query without geo
    geo_param = ""
    if region == "latam":
        geo_param = "&geo=latam"

    url = f"https://jobicy.com/api/v2/remote-jobs?count={count}{geo_param}"
    try:
        data = _get(url)
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        print(f"[jobicy] {e}", file=sys.stderr)
        return []

    results = []
    for j in data.get("jobs", []):
        location = j.get("jobGeo") or ""
        if not _matches_region(location, region):
            continue

        combined = f"{j.get('jobTitle','')} {j.get('jobExcerpt','')} {' '.join(j.get('jobIndustry') or [])}"
        if not _keyword_match(combined, keywords_list):
            continue

        desc = j.get("jobDescription") or j.get("jobExcerpt") or ""
        job_type = j.get("jobType") or []
        if isinstance(job_type, list):
            job_type = ", ".join(job_type) if job_type else "remote"
        results.append({
            "id": f"jobicy-{j.get('id','')}",
            "title": (j.get("jobTitle") or "").strip(),
            "company": (j.get("companyName") or "").strip(),
            "location": location,
            "salary": "",
            "work_arrangement": job_type,
            "listing_date": (j.get("pubDate") or "")[:10],
            "teaser": re.sub(r"<[^>]+>", " ", desc).strip()[:300],
            "url": j.get("url") or "",
            "source": "jobicy",
        })

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def deduplicate(jobs):
    """Remove duplicates by company+title key."""
    seen = set()
    out = []
    for j in jobs:
        key = f"{j['company'].lower()}::{j['title'].lower()}"
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def print_table(jobs):
    if not jobs:
        print("No jobs found.")
        return
    print(f"\nFound {len(jobs)} job(s):\n")
    for i, j in enumerate(jobs, 1):
        print(f"{i}. [{j['source']}] {j['title']}   —   {j['company']}")
        meta_parts = [j["location"], j["work_arrangement"], j["salary"], j["listing_date"]]
        meta = "   ".join(p for p in meta_parts if p)
        if meta:
            print(f"   {meta}")
        print(f"   {j['url']}")
        if j.get("teaser"):
            print(f"   {j['teaser'][:180]}")
        print()


def main():
    ap = argparse.ArgumentParser(
        description="Search remote jobs for Argentina (Remotive + Jobicy APIs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python3 job_scraper.py --keywords "Python Developer"\n'
            '  python3 job_scraper.py --keywords "Data Scientist" --region latam\n'
            '  python3 job_scraper.py --keywords "ML Engineer" --region worldwide --table\n'
            '  python3 job_scraper.py --keywords "Backend Engineer" --category software-development data\n'
            "\nRegions:\n"
            "  latam      — LATAM, Latin America, South America, Argentina\n"
            "  worldwide  — Worldwide, Anywhere, Global\n"
            "  any        — all of the above (default)\n"
            "\nNote: Argentine local job boards (Bumeran, Zonajobs, Indeed AR) require a\n"
            "real browser to scrape. Use the Claude Code /scrape skill for those."
        ),
    )
    ap.add_argument(
        "--keywords", nargs="+", required=True,
        help='One or more search terms, e.g. --keywords "Python" "Machine Learning"',
    )
    ap.add_argument(
        "--region",
        choices=["latam", "worldwide", "any"],
        default="any",
        help="Region filter (default: any — LATAM + Worldwide)",
    )
    ap.add_argument(
        "--category", nargs="+",
        default=["software-development", "artificial-intelligence", "data", "devops"],
        metavar="CAT",
        help=(
            "Remotive category slug(s) to query. Default: software-development "
            "artificial-intelligence data devops. "
            "Full list: software-development artificial-intelligence data devops "
            "engineering information-technology qa product design"
        ),
    )
    ap.add_argument(
        "--pages", type=int, default=1,
        help="Number of pages to fetch per source (Remotive returns up to 100/page). Default: 1.",
    )
    ap.add_argument(
        "--table", action="store_true",
        help="Human-readable output instead of JSON.",
    )
    args = ap.parse_args()

    limit = min(100, args.pages * 100)

    jobs = []

    # Remotive
    remotive_jobs = fetch_remotive(
        keywords_list=args.keywords,
        region=args.region,
        categories=args.category,
        limit=limit,
    )
    jobs.extend(remotive_jobs)
    if remotive_jobs:
        print(f"[remotive] {len(remotive_jobs)} match(es)", file=sys.stderr)

    # Jobicy
    jobicy_jobs = fetch_jobicy(
        keywords_list=args.keywords,
        region=args.region,
        count=50,
    )
    jobs.extend(jobicy_jobs)
    if jobicy_jobs:
        print(f"[jobicy]   {len(jobicy_jobs)} match(es)", file=sys.stderr)

    jobs = deduplicate(jobs)

    if not jobs:
        print(
            f"[job-scraper] No jobs found for {args.keywords!r} (region={args.region}).\n"
            f"  Try: --region any  or  broader keywords.\n"
            f"  For Argentine local boards, use the Claude Code /scrape skill.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.table:
        print_table(jobs)
    else:
        json.dump(jobs, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
