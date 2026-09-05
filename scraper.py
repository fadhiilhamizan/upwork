"""Playwright scraping of Upwork job search results."""

import random
import re
import time
from typing import List, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

import browser
import config
import parsing
from models import Job


class SessionExpiredError(RuntimeError):
    """Raised when Upwork no longer accepts the saved storage_state.json."""


class ScrapeError(RuntimeError):
    """Raised when a page could not be loaded or read at all."""


# URLs that mean Upwork bounced us back to authentication.
LOGIN_URL_MARKERS = (
    "/ab/account-security/login",
    "/nx/signup",
    "/ab/account-security/twostep",
    "upwork.com/login",
)

# Text Cloudflare shows on its interstitial while it checks the browser.
CHALLENGE_MARKERS = (
    "just a moment",
    "verifying you are human",
    "checking your browser",
    "please wait while we",
    "needs to review the security of your connection",
    "enable javascript and cookies to continue",
)

# Selector fallbacks, most specific first. Upwork's data-test attributes are
# more stable than its generated class names but still change without notice,
# so every field tries several before giving up.
JS_EXTRACT = r"""
() => {
  const TILE_SELECTORS = [
    'article[data-test~="JobTile"]',
    'section[data-test~="JobTile"]',
    'div[data-test~="JobTile"]',
    'article.job-tile',
    '[data-test="job-tile-list"] > *',
    '[data-ev-label="search_results_impression"]'
  ];
  const F = {
    title: ['a[data-test~="job-tile-title-link"]',
            'h2.job-tile-title a', 'h3.job-tile-title a',
            '[data-test~="job-tile-title"] a', 'h2 a[href*="/jobs/"]',
            'a[href*="/jobs/"]'],
    description: ['[data-test~="JobDescription"]',
                  '[data-test="job-description-text"]',
                  'div[data-test~="UpCLineClamp"]',
                  '.job-description', 'p'],
    posted: ['[data-test~="job-pubilshed-date"]', '[data-test~="job-published-date"]',
             '[data-test="posted-on"]', 'small[data-test*="pubilshed"]',
             'small[data-test*="published"]'],
    proposals: ['[data-test~="proposals-tier"]', '[data-test~="proposals"]',
                'li[data-test~="proposals"]', 'strong[data-test~="proposals"]'],
    verified: ['[data-test~="payment-verified"]', '[data-test~="payment-verification-status"]',
               '[data-test="payment-verified"]'],
    location: ['[data-test~="location"]', '[data-test="client-country"]',
               'small[data-test~="location"]'],
    jobType: ['[data-test~="job-type-label"]', '[data-test~="job-type"]',
              'li[data-test~="job-type"]'],
    budget: ['[data-test~="is-fixed-price"]', '[data-test~="budget"]',
             'li[data-test~="budget"]'],
    experience: ['[data-test~="experience-level"]', '[data-test~="contractor-tier"]']
  };
  const SKILL_SELECTORS = ['[data-test~="token"]', '[data-test~="attr-item"]',
                           '.air3-token', '[data-test="skills-list"] a'];

  const pickAll = (root, sels) => {
    for (const s of sels) {
      let found = [];
      try { found = root.querySelectorAll(s); } catch (e) { continue; }
      if (found.length) return Array.from(found);
    }
    return [];
  };
  // Upwork splits labels across sibling inline elements ("Posted" + "2 hours
  // ago"). Joining the element children with a space keeps those readable.
  const nodeText = (el) => {
    if (!el) return '';
    const kids = Array.from(el.children);
    if (kids.length) {
      const joined = kids
        .map(k => (k.innerText || k.textContent || '').trim())
        .filter(Boolean).join(' ');
      if (joined) return joined;
    }
    return (el.innerText || el.textContent || '').trim();
  };
  const txt = (root, sels) => nodeText(pickAll(root, sels)[0]);

  let tiles = [];
  for (const s of TILE_SELECTORS) {
    let found = [];
    try { found = document.querySelectorAll(s); } catch (e) { continue; }
    // A real results list has tiles that contain a job link.
    found = Array.from(found).filter(el => el.querySelector('a[href*="/jobs/"]'));
    if (found.length) { tiles = found; break; }
  }

  return tiles.map(tile => {
    const link = pickAll(tile, F.title)[0];
    const skills = pickAll(tile, SKILL_SELECTORS)
      .map(el => (el.innerText || el.textContent || '').trim());
    return {
      title: link ? (link.innerText || link.textContent || '').trim() : '',
      href: link ? link.getAttribute('href') : '',
      description: txt(tile, F.description),
      posted: txt(tile, F.posted),
      proposals: txt(tile, F.proposals),
      verified: txt(tile, F.verified),
      location: txt(tile, F.location),
      jobType: txt(tile, F.jobType),
      budget: txt(tile, F.budget),
      experience: txt(tile, F.experience),
      skills: skills,
      rawText: (tile.innerText || '').trim()
    };
  });
}
"""

# Fallbacks read off the whole card when a labelled element is missing.
RE_POSTED = re.compile(
    r"(?:posted\s+)?("
    r"just now|yesterday|today|last (?:week|month)|"
    r"\d+\s*(?:second|minute|min|hour|hr|day|week|month|year)s?\s*ago"
    r")",
    re.I,
)
RE_PROPOSALS = re.compile(r"proposals?:?\s*([^\n]{1,40})", re.I)
RE_HOURLY = re.compile(r"hourly[^\n]*", re.I)
RE_FIXED = re.compile(r"(?:fixed[- ]price|est(?:imated)?\.? budget)[^\n]*", re.I)


def build_job_from_raw(raw: dict, category: str, keyword: str) -> Optional[Job]:
    """Turn one extracted card into a Job, filling gaps from the card text."""
    url = parsing.absolute_url(raw.get("href"))
    job_id = parsing.extract_job_id(url)
    title = parsing.clean_text(raw.get("title"))
    if not job_id or not title:
        return None

    raw_text = raw.get("rawText") or ""

    posted_text = parsing.clean_text(raw.get("posted"))
    if not posted_text:
        match = RE_POSTED.search(raw_text)
        posted_text = parsing.clean_text(match.group(0)) if match else ""
    # The column already says Posted, so drop Upwork's repeated label.
    posted_text = re.sub(r"^posted\s+", "", posted_text, flags=re.I)

    proposals_text = parsing.clean_text(raw.get("proposals"))
    if not proposals_text:
        match = RE_PROPOSALS.search(raw_text)
        proposals_text = parsing.clean_text(match.group(1)) if match else ""
    proposals_text = re.sub(r"^proposals?\s*:?\s*", "", proposals_text, flags=re.I)

    job_type = parsing.clean_text(raw.get("jobType"))
    if not job_type:
        match = RE_HOURLY.search(raw_text) or RE_FIXED.search(raw_text)
        job_type = parsing.clean_text(match.group(0)) if match else ""
    price_type, rate = parsing.parse_price(job_type, raw.get("budget", ""))

    verified = bool(parsing.clean_text(raw.get("verified"))) or (
        "payment verified" in raw_text.lower()
    )

    return Job(
        job_id=job_id,
        title=title,
        url=url,
        description=parsing.clean_text(raw.get("description"))[:1500],
        posted_text=posted_text,
        age_hours=parsing.parse_posted_age_hours(posted_text),
        proposals_text=proposals_text,
        proposal_count=parsing.parse_proposal_count(proposals_text),
        payment_verified=verified,
        location=parsing.clean_text(raw.get("location")),
        rate=rate,
        price_type=price_type,
        skills=parsing.dedupe_skills(raw.get("skills") or []),
        source_category=category,
        source_keyword=keyword,
    )


class UpworkScraper:
    """Drives one Chromium context against Upwork job search."""

    def __init__(self, playwright, headless: bool = True, verbose: bool = True):
        self.verbose = verbose
        self.browser = None

        if config.USE_PERSISTENT_PROFILE:
            # Reuse the profile the login window created. Slower to start but
            # far less likely to be challenged.
            self.context = browser.launch_persistent(
                playwright, browser.session_channel(), headless=headless
            )
        else:
            if not config.STORAGE_STATE_PATH.exists():
                raise SessionExpiredError(
                    f"No saved session at {config.STORAGE_STATE_PATH}."
                )
            self.browser = self._launch(playwright, headless)
            self.context = self.browser.new_context(
                storage_state=str(config.STORAGE_STATE_PATH),
                # The identity the cookies were issued to, captured at login.
                user_agent=browser.session_user_agent(),
                viewport=config.VIEWPORT,
                locale=config.LOCALE,
            )
            browser.apply_stealth(self.context)

        self.context.set_default_timeout(config.NAV_TIMEOUT_MS)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self._consent_dismissed = False

    @staticmethod
    def _launch(playwright, headless: bool):
        """Launch the browser the login used, falling back to the bundled one."""
        channel = browser.session_channel()
        try:
            return playwright.chromium.launch(
                **browser.launch_kwargs(headless, channel)
            )
        except Exception:
            if not channel:
                raise
            # The browser used at login is gone, carry on with the bundled one.
            return playwright.chromium.launch(**browser.launch_kwargs(headless))

    def close(self) -> None:
        closers = [self.context.close]
        if self.browser is not None:
            closers.append(self.browser.close)
        for closer in closers:
            try:
                closer()
            except Exception:
                pass

    # -- page hygiene -------------------------------------------------------

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def _wait_out_challenge(self) -> None:
        """Sit through the Cloudflare interstitial until the real page shows.

        The check normally clears itself in a few seconds. We poll for either
        the job list appearing or the challenge text going away.
        """
        deadline = time.time() + config.CLOUDFLARE_TIMEOUT_MS / 1000
        announced = False
        while time.time() < deadline:
            try:
                body = (self.page.inner_text("body", timeout=5_000) or "").lower()
            except Exception:
                body = ""

            challenged = any(m in body[:2000] for m in CHALLENGE_MARKERS)
            if not challenged:
                return
            if not announced:
                self._log("      Cloudflare check in progress, waiting for it to clear...")
                announced = True
            self.page.wait_for_timeout(1_500)

        self._log("      Cloudflare check did not clear in time, reading the page anyway.")

    def _dismiss_consent(self) -> None:
        """Close the cookie banner using its close control, never 'accept'."""
        if self._consent_dismissed:
            return
        close_selectors = [
            'button[data-test="close-consent"]',
            '#onetrust-close-btn-container button',
            'button.onetrust-close-btn-handler',
            '#onetrust-banner-sdk button[aria-label="Close"]',
            'div[data-test="cookie-consent"] button[aria-label="Close"]',
            'button[aria-label="Close cookie banner"]',
            'button[data-cy="close-consent"]',
        ]
        for selector in close_selectors:
            try:
                button = self.page.locator(selector).first
                if button.count() and button.is_visible(timeout=1_000):
                    button.click(timeout=3_000)
                    self._consent_dismissed = True
                    self._log("      Cookie banner closed.")
                    return
            except Exception:
                continue
        # Nothing to close is the normal case once the choice is remembered.
        self._consent_dismissed = True

    def _assert_session_alive(self) -> None:
        url = (self.page.url or "").lower()
        if any(marker in url for marker in LOGIN_URL_MARKERS):
            raise SessionExpiredError(f"Upwork redirected to login: {self.page.url}")
        try:
            if self.page.locator(
                'input[name="login[username]"], #login_password, '
                'form[name="loginForm"]'
            ).count():
                raise SessionExpiredError("Upwork rendered its login form.")
        except SessionExpiredError:
            raise
        except Exception:
            pass

    def _open(self, url: str) -> None:
        try:
            self.page.goto(url, wait_until="domcontentloaded",
                           timeout=config.NAV_TIMEOUT_MS)
        except PlaywrightTimeout as exc:
            raise ScrapeError(f"Timed out loading {url}") from exc

        self._wait_out_challenge()
        self._assert_session_alive()
        self._dismiss_consent()

        # Give the client rendered results a chance to mount.
        try:
            self.page.wait_for_selector(
                '[data-test="job-tile-list"], article[data-test~="JobTile"], '
                'article.job-tile, [data-test="empty-state"]',
                timeout=20_000,
            )
        except PlaywrightTimeout:
            pass
        self.page.wait_for_timeout(1_200)

    def _pause(self) -> None:
        low, high = config.DELAY_BETWEEN_PAGES_MS
        self.page.wait_for_timeout(random.randint(low, high))

    # -- extraction ---------------------------------------------------------

    def _dump_debug(self, tag: str) -> None:
        html_path = config.PROJECT_DIR / f"debug_{tag}.html"
        png_path = config.PROJECT_DIR / f"debug_{tag}.png"
        try:
            html_path.write_text(self.page.content(), encoding="utf-8")
            self.page.screenshot(path=str(png_path), full_page=False)
            self._log(f"      Saved {html_path.name} and {png_path.name} for selector debugging.")
        except Exception:
            pass

    def _build_job(self, raw: dict, category: str, keyword: str) -> Optional[Job]:
        return build_job_from_raw(raw, category, keyword)

    # -- public API ---------------------------------------------------------

    def search(self, keyword: str, category: str) -> List[Job]:
        """Run one keyword search, paging until results fall outside the window."""
        collected: List[Job] = []
        max_age_hours = config.MAX_JOB_AGE_DAYS * 24
        base_url = config.SEARCH_URL_TEMPLATE.format(
            keyword=keyword.replace(" ", "%20")
        )

        for page_number in range(1, config.MAX_PAGES_PER_KEYWORD + 1):
            url = base_url if page_number == 1 else f"{base_url}&page={page_number}"
            self._open(url)

            try:
                rows = self.page.evaluate(JS_EXTRACT)
            except Exception as exc:
                self._log(f"      Could not read page {page_number}: {exc}")
                break

            if not rows:
                if page_number == 1:
                    self._log("      No job cards found on the first page.")
                    self._dump_debug(re.sub(r"\W+", "_", keyword))
                break

            stop_paging = False
            kept_on_page = 0
            for raw in rows:
                job = self._build_job(raw, category, keyword)
                if job is None:
                    continue
                # Results are sorted by recency, so the first job past the
                # window means everything after it is older too.
                if job.age_hours is not None and job.age_hours > max_age_hours:
                    stop_paging = True
                    break
                collected.append(job)
                kept_on_page += 1

            self._log(
                f"      page {page_number}: {len(rows)} cards, "
                f"{kept_on_page} within {config.MAX_JOB_AGE_DAYS} days"
            )

            if stop_paging or len(rows) < 10:
                break
            self._pause()

        return collected


def scrape_all(searches=None, headless: bool = None, verbose: bool = True):
    """Run every configured keyword search and return the raw job list."""
    searches = searches or config.SEARCHES
    headless = config.HEADLESS if headless is None else headless

    # Checked before the browser starts, so a missing session fails fast.
    if not config.USE_PERSISTENT_PROFILE and not config.STORAGE_STATE_PATH.exists():
        raise SessionExpiredError(
            f"No saved session at {config.STORAGE_STATE_PATH}."
        )

    jobs: List[Job] = []
    failure = None

    with sync_playwright() as playwright:
        scraper = None
        try:
            scraper = UpworkScraper(playwright, headless=headless, verbose=verbose)
            for category, keywords in searches.items():
                if verbose:
                    print(f"\n  {config.CATEGORY_DISPLAY.get(category, category)}")
                for keyword in keywords:
                    if verbose:
                        print(f"    searching: {keyword!r}")
                    found = scraper.search(keyword, category)
                    if verbose:
                        print(f"      kept {len(found)} jobs")
                    jobs.extend(found)
                    scraper._pause()
        except (SessionExpiredError, ScrapeError) as exc:
            # Held and re-raised outside, so Playwright shuts down cleanly and
            # the console shows the guidance rather than a teardown traceback.
            failure = exc
        finally:
            if scraper is not None:
                scraper.close()

    if failure is not None:
        raise failure
    return jobs
