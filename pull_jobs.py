#!/usr/bin/env python3
"""Pull Upwork job listings, score them, and rewrite the report workbook.

    python pull_jobs.py            normal run against your saved Upwork session
    python pull_jobs.py --demo     offline run against the bundled sample page
    python pull_jobs.py --headful  same as a normal run, with a visible browser

The workbook path is fixed, so every run overwrites the same file.
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List

import config
import report
import scoring
from models import Job
from scraper import ScrapeError, SessionExpiredError, scrape_all

LINE = "=" * 72

RERUN_LOGIN_MESSAGE = f"""
{LINE}
Upwork did not accept the saved session.
{LINE}

Upwork either has no session on file, or the saved one expired or was
invalidated (password change, new device check, logout elsewhere).

Fix it by logging in again:

    python login_setup.py

Then run this script again. Nothing was written, your previous
{config.OUTPUT_PATH.name} is untouched.
"""


# ---------------------------------------------------------------------------
# New-since-last-run tracking
# ---------------------------------------------------------------------------

def load_seen_jobs() -> Dict[str, str]:
    """Read job ids recorded on earlier runs. A missing or broken file is fine."""
    if not config.SEEN_JOBS_PATH.exists():
        return {}
    try:
        data = json.loads(config.SEEN_JOBS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"  Note: {config.SEEN_JOBS_PATH.name} was unreadable, "
              "treating every job as new.")
        return {}
    if isinstance(data, dict) and isinstance(data.get("jobs"), dict):
        return data["jobs"]
    return data if isinstance(data, dict) else {}


def save_seen_jobs(seen: Dict[str, str], jobs: List[Job], now: datetime) -> None:
    """Record this run's job ids. Never let a write failure kill the run."""
    stamp = now.isoformat(timespec="seconds")
    merged = dict(seen)
    for job in jobs:
        merged.setdefault(job.job_id, stamp)

    # Keep the file from growing without bound.
    if len(merged) > 5000:
        merged = dict(sorted(merged.items(), key=lambda kv: kv[1])[-5000:])

    try:
        config.SEEN_JOBS_PATH.write_text(
            json.dumps({"last_run": stamp, "jobs": merged}, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"  Note: could not update {config.SEEN_JOBS_PATH.name} ({exc}).")


def mark_new(jobs: List[Job], seen: Dict[str, str]) -> None:
    for job in jobs:
        job.is_new = job.job_id not in seen


# ---------------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------------

def print_summary(jobs: List[Job], raw_count: int, recent_count: int) -> None:
    print()
    print(LINE)
    print("Results")
    print(LINE)
    print(f"  Raw cards scraped        : {raw_count}")
    print(f"  Within {config.MAX_JOB_AGE_DAYS} days            : {recent_count}")
    print(f"  Unique jobs after dedupe : {len(jobs)}")
    print()
    print("  Jobs per category:")
    for category in config.CATEGORY_ORDER:
        in_category = [j for j in jobs if j.category == category]
        counts = {fit: sum(1 for j in in_category if j.fit == fit)
                  for fit in ("High", "Medium", "Low")}
        label = config.CATEGORY_DISPLAY.get(category, category)
        print(f"    {label:<40} {len(in_category):>3}"
              f"   (High {counts['High']} / Medium {counts['Medium']}"
              f" / Low {counts['Low']})")

    print()
    totals = {fit: sum(1 for j in jobs if j.fit == fit)
              for fit in ("High", "Medium", "Low")}
    print(f"  Fit totals   : High {totals['High']}, "
          f"Medium {totals['Medium']}, Low {totals['Low']}")
    print(f"  New this run : {sum(1 for j in jobs if j.is_new)}")

    top = sorted(jobs, key=lambda j: j.score, reverse=True)[:5]
    if top:
        print()
        print("  Top picks:")
        for index, job in enumerate(top, start=1):
            title = job.title if len(job.title) <= 58 else job.title[:55] + "..."
            print(f"    {index}. [{job.score:>5.1f} {job.fit:<6}] {title}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_jobs(args) -> List[Job]:
    if args.demo:
        from demo_source import scrape_demo
        return scrape_demo(verbose=True)
    return scrape_all(headless=not args.headful, verbose=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull, score and report Upwork jobs into a single workbook."
    )
    parser.add_argument("--demo", action="store_true",
                        help="run against the bundled sample results page "
                             "instead of Upwork, no login needed")
    parser.add_argument("--headful", action="store_true",
                        help="show the browser window while scraping")
    parser.add_argument("--no-seen-tracking", action="store_true",
                        help="do not read or write seen_jobs.json")
    args = parser.parse_args(argv)

    started = datetime.now()
    print(LINE)
    print("Upwork Daily Job Report")
    print(LINE)
    print(f"  Filters : {config.FILTER_SUMMARY}")
    print(f"  Output  : {config.OUTPUT_PATH}")
    if args.demo:
        print("  Mode    : DEMO, using the bundled sample page, not live Upwork")
    print()
    print("Searching...")

    try:
        raw_jobs = collect_jobs(args)
    except SessionExpiredError:
        print(RERUN_LOGIN_MESSAGE)
        return 2
    except ScrapeError as exc:
        print(f"\nScraping failed: {exc}")
        print("Check your connection and try again. The existing workbook was "
              "left untouched.")
        return 1

    recent = scoring.filter_recent(raw_jobs)
    unique = scoring.dedupe(recent)
    scored = scoring.score_all(unique)
    scored.sort(key=lambda j: j.score, reverse=True)

    seen = {} if args.no_seen_tracking else load_seen_jobs()
    mark_new(scored, seen)

    print_summary(scored, len(raw_jobs), len(recent))

    try:
        path = report.build_workbook(scored, generated_at=started)
    except PermissionError as exc:
        print(f"\n{exc}")
        return 1

    if not args.no_seen_tracking:
        save_seen_jobs(seen, scored, started)

    print()
    print(LINE)
    print(f"Report written to {path}")
    print(f"Run took {(datetime.now() - started).total_seconds():.0f}s")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
