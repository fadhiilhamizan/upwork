#!/usr/bin/env python3
"""Offline checks for the parts that are hard to observe during a live run.

    python selftest.py

Covers the text parsers, the scoring rules, and the three browser behaviours
that only show up against Upwork: the Cloudflare interstitial, an expired
session, and the cookie banner. Run this after changing any selector.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import config
import demo_source
import parsing
import scoring
from models import Job
import browser
import import_cookies
from scraper import (JS_EXTRACT, SessionExpiredError, UpworkScraper,
                     build_job_from_raw)

PASSED = []
FAILED = []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"  {detail}" if detail and not condition else ""))


def make_scraper(page):
    """An UpworkScraper wired to a page, without launching a real session."""
    scraper = object.__new__(UpworkScraper)
    scraper.page = page
    scraper.verbose = False
    scraper._consent_dismissed = False
    return scraper


def test_parsers():
    print("\nParsers")
    check("relative posted times",
          parsing.parse_posted_age_hours("Posted 3 days ago") == 72
          and parsing.parse_posted_age_hours("yesterday") == 24
          and parsing.parse_posted_age_hours("2 weeks ago") == 336
          and parsing.parse_posted_age_hours("30 minutes ago") == 0.5)
    check("unparsable posted text returns None",
          parsing.parse_posted_age_hours("who knows") is None)
    check("job id from url",
          parsing.extract_job_id(
              "https://www.upwork.com/jobs/Foo_~021968676050348026869/?a=1"
          ) == "021968676050348026869")
    check("tracking params stripped from url",
          parsing.absolute_url("/jobs/Foo_~012345678/?referrer=x")
          == "https://www.upwork.com/jobs/Foo_~012345678/")
    check("proposal bands to lower bound",
          parsing.parse_proposal_count("Less than 5") == 0
          and parsing.parse_proposal_count("20 to 50") == 20
          and parsing.parse_proposal_count("50+") == 50)
    check("hourly and fixed prices",
          parsing.parse_price("Hourly: $15.00 - $30.00") == ("Hourly", "$15.00 - $30.00")
          and parsing.parse_price("Fixed price", "Est. Budget: $250.00")
          == ("Fixed", "$250.00"))


def test_scoring():
    print("\nScoring")

    def job(title, description="", proposals=0, hours=2, category="Custom Web Data Scraping"):
        return scoring.score_job(Job(
            job_id="1", title=title, url="u", description=description,
            proposal_count=proposals, age_hours=hours, payment_verified=True,
            source_category=category,
        ))

    fresh = job("Build a web scraping tool in Python", "scrape product data")
    stale = job("Build a web scraping tool in Python", "scrape product data", hours=110)
    check("recent posts outscore older ones", fresh.score > stale.score,
          f"{fresh.score} vs {stale.score}")

    low_comp = job("Web scraping tool", "scrape data", proposals=0)
    high_comp = job("Web scraping tool", "scrape data", proposals=20)
    check("competition penalty grows with proposals", low_comp.score > high_comp.score,
          f"{low_comp.score} vs {high_comp.score}")

    on_topic = job("Web scraping tool for product data", "python scraper")
    off_topic = job("Scrape NFT prices for our blockchain web3 dashboard",
                    "solidity smart contract work")
    check("off topic listings are demoted", off_topic.score < on_topic.score - 20,
          f"{off_topic.score} vs {on_topic.score}")

    sales = job("Cold calling agents wanted", "telemarketing and appointment setter")
    check("cold calling work scores Low", sales.score < config.FIT_HARD_LOW_MAX,
          f"{sales.score}")

    misfiled = job("Excel dashboard with pivot tables and VBA macros",
                   "clean our spreadsheet data", category="Custom Web Data Scraping")
    check("poorly matched job is recategorised",
          misfiled.category == "Microsoft Excel Solutions", misfiled.category)

    duplicated = scoring.dedupe([
        Job(job_id="42", title="A", url="u", description="short"),
        Job(job_id="42", title="A", url="u", description="a much longer description"),
        Job(job_id="43", title="B", url="u"),
    ])
    check("dedupe keys on job id and keeps the fuller record",
          len(duplicated) == 2
          and any(j.description == "a much longer description" for j in duplicated))

    old = Job(job_id="9", title="old", url="u", age_hours=24 * 9)
    recent = Job(job_id="8", title="new", url="u", age_hours=10)
    unknown = Job(job_id="7", title="unknown", url="u", age_hours=None)
    kept = scoring.filter_recent([old, recent, unknown])
    check("recency filter drops jobs past the window, keeps unknown ages",
          len(kept) == 2 and old not in kept)

    batch = scoring.score_all([
        job("Web scraping tool", "scrape", proposals=p, hours=h)
        for p, h in [(0, 1), (0, 20), (5, 30), (10, 40), (15, 60),
                     (20, 80), (20, 100), (5, 5), (10, 12), (0, 50), (50, 100)]
    ])
    bands = {fit: sum(1 for j in batch if j.fit == fit)
             for fit in ("High", "Medium", "Low")}
    check("fit bands stay spread across a run", all(bands.values()), str(bands))


def test_cookie_import():
    print("\nCookie import")
    future = int(time.time()) + 86_400 * 30
    past = int(time.time()) - 86_400

    with tempfile.TemporaryDirectory() as tmp:
        netscape = Path(tmp) / "cookies.txt"
        netscape.write_text(
            "# Netscape HTTP Cookie File\n"
            f"#HttpOnly_.upwork.com\tTRUE\t/\tTRUE\t{future}\tmaster_access_token\tabc\n"
            f".upwork.com\tTRUE\t/\tTRUE\t{past}\tstale\told\n"
            f".google.com\tTRUE\t/\tTRUE\t{future}\tSID\tother\n",
            encoding="utf-8",
        )
        parsed = import_cookies.clean(import_cookies.load_cookies(netscape))
        check("netscape export keeps live Upwork cookies only",
              [c["name"] for c in parsed] == ["master_access_token"],
              str([c["name"] for c in parsed]))
        check("httpOnly prefix is read from the netscape format",
              parsed and parsed[0]["httpOnly"] is True)

        editor = Path(tmp) / "cookies.json"
        editor.write_text(json.dumps([
            {"domain": ".upwork.com", "expirationDate": future, "httpOnly": True,
             "name": "master_access_token", "path": "/",
             "sameSite": "no_restriction", "secure": False, "value": "abc"},
            {"domain": ".facebook.com", "name": "xs", "value": "no", "path": "/"},
        ]), encoding="utf-8")
        parsed = import_cookies.clean(import_cookies.load_cookies(editor))
        check("cookie editor export is filtered to Upwork",
              [c["name"] for c in parsed] == ["master_access_token"])
        check("sameSite None is upgraded to secure, as Playwright requires",
              parsed and parsed[0]["sameSite"] == "None" and parsed[0]["secure"] is True)

        state = Path(tmp) / "state.json"
        state.write_text(json.dumps({"cookies": [
            {"name": "oauth2_global_js_token", "value": "v", "domain": ".upwork.com",
             "path": "/", "expires": -1, "httpOnly": False, "secure": True,
             "sameSite": "Lax"}], "origins": []}), encoding="utf-8")
        parsed = import_cookies.clean(import_cookies.load_cookies(state))
        check("an existing storage_state file is accepted",
              [c["name"] for c in parsed] == ["oauth2_global_js_token"])

        empty = Path(tmp) / "none.txt"
        empty.write_text("# nothing here\n", encoding="utf-8")
        check("an export with no Upwork cookies yields nothing",
              import_cookies.clean(import_cookies.load_cookies(empty)) == [])


def test_browser_behaviour():
    print("\nBrowser behaviour")
    with sync_playwright() as playwright:
        chrome = playwright.chromium.launch(**browser.launch_kwargs(True))
        context = chrome.new_context()
        browser.apply_stealth(context)
        page = context.new_page()
        page.set_content("<h1>probe</h1>")
        check("navigator.webdriver is not exposed",
              page.evaluate("() => navigator.webdriver") in (None, False))
        check("window.chrome is present",
              page.evaluate("() => !!window.chrome"))
        check("automation switch is not passed to the browser",
              "--enable-automation" not in browser.launch_kwargs(True)["args"]
              and "--enable-automation"
              in browser.launch_kwargs(True)["ignore_default_args"])

        scraper = make_scraper(page)

        # Cloudflare interstitial that resolves itself, like the real one.
        page.set_content("""
            <body><h1>Just a moment...</h1>
            <p>Verifying you are human. This may take a few seconds.</p>
            <script>setTimeout(() => {
              document.body.innerHTML = '<div data-test="job-tile-list">ready</div>';
            }, 2500);</script></body>""")
        started = time.time()
        scraper._wait_out_challenge()
        elapsed = time.time() - started
        body = page.inner_text("body").lower()
        check("waits out the Cloudflare interstitial",
              elapsed >= 1.0 and "just a moment" not in body,
              f"elapsed {elapsed:.1f}s, body {body[:40]!r}")

        # An expired session: Upwork serves its login form.
        page.set_content('<form name="loginForm">'
                         '<input name="login[username]"></form>')
        raised = False
        try:
            scraper._assert_session_alive()
        except SessionExpiredError:
            raised = True
        check("expired session is detected from the login form", raised)

        # An expired session: Upwork redirects to the login URL.
        class FakePage:
            url = "https://www.upwork.com/ab/account-security/login"

            def locator(self, _selector):
                raise AssertionError("should not reach the DOM check")

        scraper.page = FakePage()
        raised = False
        try:
            scraper._assert_session_alive()
        except SessionExpiredError:
            raised = True
        check("expired session is detected from the redirect URL", raised)
        scraper.page = page

        # A healthy results page must not trip the session check.
        page.set_content('<div data-test="job-tile-list">jobs</div>')
        ok = True
        try:
            scraper._assert_session_alive()
        except SessionExpiredError:
            ok = False
        check("a live session is not flagged as expired", ok)

        # The cookie banner is closed, never accepted.
        page.set_content(demo_source.render_page(
            [j for j in demo_source.sample_jobs.SAMPLE_JOBS[:2]]))
        scraper._consent_dismissed = False
        scraper._dismiss_consent()
        accepted = page.evaluate("() => window.__consentAccepted === true")
        closed = page.evaluate("() => window.__consentClosed === true")
        check("cookie banner is closed and not accepted", closed and not accepted,
              f"closed={closed} accepted={accepted}")

        chrome.close()


def test_extraction():
    print("\nExtraction")
    jobs = demo_source.scrape_demo(verbose=False)
    check("job cards are extracted from Upwork shaped markup", len(jobs) > 0,
          f"got {len(jobs)}")

    if not jobs:
        return

    complete = [j for j in jobs if j.title and j.url and j.job_id
                and j.posted_text and j.proposals_text and j.rate
                and j.location and j.skills and j.description]
    check("every field is populated on each card", len(complete) == len(jobs),
          f"{len(complete)} of {len(jobs)} complete")
    check("payment verified flag is read", all(j.payment_verified for j in jobs))
    check("both hourly and fixed prices are handled",
          {j.price_type for j in jobs} == {"Hourly", "Fixed"})
    check("labels are stripped from posted and proposals text",
          not any(j.posted_text.lower().startswith("posted") for j in jobs)
          and not any(j.proposals_text.lower().startswith("proposal") for j in jobs))
    check("paging stops at the first job outside the recency window",
          not any("should be filtered out" in j.title for j in jobs))


def main():
    print("=" * 60)
    print("Upwork job report self test (no network access needed)")
    print("=" * 60)
    test_parsers()
    test_scoring()
    test_cookie_import()
    test_browser_behaviour()
    test_extraction()

    print()
    print("=" * 60)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        for name in FAILED:
            print(f"  failed: {name}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
