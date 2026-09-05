"""Offline demo source.

Renders Upwork shaped search result markup from sample_jobs.py into a real
Chromium page and runs the exact same extraction code the live scraper uses.
It exercises the selectors, the consent banner handling and the recency cutoff
without touching upwork.com, which makes it a useful smoke test after any
selector change.
"""

import html
from typing import List

from playwright.sync_api import sync_playwright

import config
import sample_jobs
from models import Job
import browser
from scraper import JS_EXTRACT, build_job_from_raw

# Mirrors the parts of Upwork's markup the scraper depends on: the data-test
# attributes, the multi value attributes such as "UpCLineClamp JobDescription",
# and Upwork's own misspelling of "published".
TILE_TEMPLATE = """
<article class="job-tile" data-test="JobTile">
  <h2 class="job-tile-title">
    <a data-test="job-tile-title-link UpLink" href="/jobs/{slug}_~{job_id}/?referrer_url_path=%2Fnx%2Fsearch">{title}</a>
  </h2>
  <small data-test="job-pubilshed-date"><span>Posted</span><span>{posted}</span></small>
  <ul class="job-tile-info-list">
    <li data-test="job-type-label"><strong>{job_type}</strong></li>
    <li data-test="experience-level"><strong>Intermediate</strong></li>
    {budget_li}
  </ul>
  <div data-test="UpCLineClamp JobDescription"><p>{description}</p></div>
  <ul class="job-tile-footer">
    <li data-test="payment-verified"><small>Payment verified</small></li>
    <li data-test="proposals-tier"><strong>Proposals: </strong><span>{proposals}</span></li>
    <li data-test="location"><small>{location}</small></li>
  </ul>
  <div class="skills-list">{skills}</div>
</article>
"""

# A consent banner shaped like the real one. Clicking "Accept" flips a flag, so
# the self test can prove the scraper closed the banner instead of accepting it.
PAGE_TEMPLATE = """
<html><head><meta charset="utf-8"><title>Jobs | Upwork</title></head>
<body>
<div id="onetrust-banner-sdk" style="position:fixed;bottom:0;width:100%;background:#eee;padding:12px;z-index:9999">
  <span>We use cookies.</span>
  <button id="onetrust-accept-btn-handler" onclick="window.__consentAccepted=true">Accept All</button>
  <div id="onetrust-close-btn-container">
    <button class="onetrust-close-btn-handler" aria-label="Close"
            onclick="window.__consentClosed=true;this.closest('#onetrust-banner-sdk').remove()">Close</button>
  </div>
</div>
<main>
  <h1>Jobs</h1>
  <div data-test="job-tile-list">{tiles}</div>
</main>
</body></html>
"""


def _slug(title: str) -> str:
    keep = [c if c.isalnum() else "-" for c in title]
    return "".join(keep).strip("-")[:60]


def render_page(jobs: List[dict]) -> str:
    """Build a search results page for the given sample listings."""
    tiles = []
    for job in jobs:
        budget_li = ""
        if job.get("budget"):
            budget_li = (
                '<li data-test="is-fixed-price"><strong>Est. Budget: </strong>'
                f'<span>{html.escape(job["budget"].split(":")[-1].strip())}</span></li>'
            )
        skills = "".join(
            f'<button data-test="token"><span>{html.escape(skill)}</span></button>'
            for skill in job["skills"]
        )
        tiles.append(TILE_TEMPLATE.format(
            slug=_slug(job["title"]),
            job_id=job["id"],
            title=html.escape(job["title"]),
            posted=html.escape(job["posted"]),
            job_type=html.escape(job["type"]),
            budget_li=budget_li,
            description=html.escape(job["description"]),
            proposals=html.escape(job["proposals"]),
            location=html.escape(job["location"]),
            skills=skills,
        ))
    return PAGE_TEMPLATE.format(tiles="\n".join(tiles))


def _dismiss_consent(page) -> None:
    """Close the banner through its close control, never through accept."""
    for selector in ('#onetrust-close-btn-container button',
                     'button.onetrust-close-btn-handler',
                     'button[data-test="close-consent"]'):
        button = page.locator(selector).first
        if button.count():
            button.click()
            return


def scrape_demo(verbose: bool = True) -> List[Job]:
    """Run every configured search against the sample data."""
    collected: List[Job] = []
    max_age_hours = config.MAX_JOB_AGE_DAYS * 24

    with sync_playwright() as playwright:
        chrome = playwright.chromium.launch(**browser.launch_kwargs(True))
        page = chrome.new_page(user_agent=config.USER_AGENT,
                                viewport=config.VIEWPORT)
        try:
            for category, keywords in config.SEARCHES.items():
                if verbose:
                    print(f"\n  {config.CATEGORY_DISPLAY.get(category, category)}")
                for keyword in keywords:
                    rows = sample_jobs.jobs_for_keyword(keyword)
                    page.set_content(render_page(rows))
                    _dismiss_consent(page)
                    extracted = page.evaluate(JS_EXTRACT)

                    kept = 0
                    for raw in extracted:
                        job = build_job_from_raw(raw, category, keyword)
                        if job is None:
                            continue
                        # Same cutoff the live scraper uses on recency sorted
                        # results: the first job past the window ends the page.
                        if job.age_hours is not None and job.age_hours > max_age_hours:
                            break
                        collected.append(job)
                        kept += 1

                    if verbose:
                        print(f"    searching: {keyword!r}")
                        print(f"      page 1: {len(extracted)} cards, "
                              f"{kept} within {config.MAX_JOB_AGE_DAYS} days")
        finally:
            chrome.close()

    return collected
