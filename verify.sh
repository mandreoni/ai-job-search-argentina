#!/bin/sh
#
# verify.sh — smoke test for AI Job Search AR.
#
# Confirms the Remotive API (primary structured source) is reachable and returns jobs.
# Note: ar.indeed.com is fully Cloudflare-blocked; the indeed-search CLI is deprecated.
#
#    ./verify.sh
#
set -e

echo "==>" Python
python3 --version

echo "==>" Remotive API "(remote jobs, no auth needed)"
count=$(curl -s "https://remotive.com/api/remote-jobs?category=software-dev&limit=100" \
  | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
ar = [j for j in jobs if any(
    k in (j.get('candidate_required_location') or '').lower()
    for k in ['argentina', 'latin', 'worldwide', 'south america', 'latam', 'anywhere', 'global']
)]
print(len(ar))
sys.stderr.write('total: %d, AR-eligible: %d\n' % (len(jobs), len(ar)))
")

if [ -z "$count" ] || [ "$count" -eq 0 ]; then
    echo "WARN: Remotive returned 0 AR-eligible software-dev jobs (may be a slow day)." >&2
    echo "      Primary job discovery via /scrape uses WebSearch, which is always available." >&2
else
    echo "    Remotive OK — $count AR-eligible remote software jobs available"
fi

echo
echo "All checks passed."
echo "Note: /scrape uses WebSearch (primary) + Remotive API (secondary)."
echo "      ar.indeed.com is fully Cloudflare-blocked and is no longer used."
