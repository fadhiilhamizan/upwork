"""Central configuration for the Upwork job report.

Everything a user is likely to tweak (categories, keywords, filters, scoring
weights, output paths) lives here so the other modules stay generic.
"""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

# Authenticated Playwright session produced by login_setup.py.
STORAGE_STATE_PATH = PROJECT_DIR / "storage_state.json"

# The one workbook that every run overwrites in place.
OUTPUT_PATH = PROJECT_DIR / "Upwork_Daily_Job_Report.xlsx"

# Job IDs seen on previous runs, used to flag listings as new.
SEEN_JOBS_PATH = PROJECT_DIR / "seen_jobs.json"

# Browser profile used for the login window, and reused by the scraper when
# USE_PERSISTENT_PROFILE is on. Keeping a profile makes the browser look like an
# ordinary one rather than a fresh automated session every time.
PROFILE_DIR = PROJECT_DIR / "browser_profile"

# The browser identity captured during login, so the scraper can present the
# same one the cookies were issued to.
SESSION_META_PATH = PROJECT_DIR / "session_meta.json"

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

# Filter checklist encoded in the URL:
#   amount=0-99,100-499      fixed price under $100 and $100-500
#   client_hires=0           clients with no hires yet
#   contractor_tier=2        experience level: intermediate
#   hourly_rate=5-           hourly $5/hr and up
#   payment_verified=1       payment verified clients only
#   proposals=0-4,...,20-49  every proposal band below 50
#   sort=recency             most recent first (recency filter depends on this)
#   t=0,1                    both hourly and fixed price contracts
SEARCH_URL_TEMPLATE = (
    "https://www.upwork.com/nx/search/jobs/"
    "?amount=0-99,100-499"
    "&client_hires=0"
    "&contractor_tier=2"
    "&hourly_rate=5-"
    "&nbs=1"
    "&payment_verified=1"
    "&proposals=0-4,5-9,10-14,15-19,20-49"
    "&q={keyword}"
    "&sort=recency"
    "&t=0,1"
    "&per_page=50"
)

FILTER_SUMMARY = (
    "Intermediate level | Hourly $5+/hr or Fixed <$100 and $100-500 | "
    "Proposals under 50 | Payment verified | Client with no hires | "
    "Posted within last 5 days | Sorted by most recent"
)

# Only keep jobs posted within this window.
MAX_JOB_AGE_DAYS = 5

# Safety cap on paging per keyword. Paging normally stops earlier, as soon as a
# job older than MAX_JOB_AGE_DAYS shows up in the recency-sorted results.
MAX_PAGES_PER_KEYWORD = 3

# Category keys are used as sheet names, so keep them under 31 characters.
CAT_SCRAPING = "Custom Web Data Scraping"
CAT_SHEETS = "Google Sheets Automation"
CAT_EXCEL = "Microsoft Excel Solutions"
CAT_WEB = "Web Systems & UI UX Design"

CATEGORY_ORDER = [CAT_SCRAPING, CAT_SHEETS, CAT_EXCEL, CAT_WEB]

# Long display names, for places where the 31 character sheet limit is not a
# constraint (dashboard tables, console output).
CATEGORY_DISPLAY = {
    CAT_SCRAPING: "Custom Web Data Scraping",
    CAT_SHEETS: "Google Sheets Automation",
    CAT_EXCEL: "Microsoft Excel Solutions",
    CAT_WEB: "Web Management Systems & UI/UX Design",
}

SEARCHES = {
    CAT_SCRAPING: ["web scraping", "data scraper"],
    CAT_SHEETS: ["google sheets automation", "google apps script"],
    CAT_EXCEL: ["excel dashboard", "excel automation"],
    CAT_WEB: ["web application", "web design UI UX"],
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Starting point per category, before relevance, competition and recency.
BASE_SCORES = {
    CAT_SCRAPING: 58,
    CAT_SHEETS: 57,
    CAT_EXCEL: 56,
    CAT_WEB: 52,
}

# Signals that a job really belongs to a category. "strong" terms are the core
# of the service, "weak" terms are supporting context.
CATEGORY_SIGNALS = {
    CAT_SCRAPING: {
        "strong": [
            "web scraping", "scraper", "scrape", "crawler", "crawling",
            "data extraction", "data scraping", "web crawler", "beautifulsoup",
            "scrapy", "selenium", "playwright", "puppeteer", "data mining",
        ],
        "weak": [
            "python", "automation", "bot", "api", "extract", "parse",
            "lead generation", "data collection", "csv", "proxy", "captcha",
        ],
    },
    CAT_SHEETS: {
        "strong": [
            "google sheets", "google apps script", "apps script",
            "google spreadsheet", "sheets automation", "google form",
            "app script", "google workspace",
        ],
        "weak": [
            "automation", "script", "formula", "dashboard", "google drive",
            "zapier", "make.com", "integration", "custom function", "gmail",
        ],
    },
    CAT_EXCEL: {
        "strong": [
            "excel", "vba", "macro", "power query", "pivot table",
            "spreadsheet", "xlsx", "power pivot", "excel dashboard",
        ],
        "weak": [
            "formula", "data cleaning", "data cleanup", "dashboard", "report",
            "template", "csv", "data entry automation", "financial model",
        ],
    },
    CAT_WEB: {
        "strong": [
            "web application", "web app", "management system", "admin panel",
            "dashboard design", "ui/ux", "ui ux", "ux design", "ui design",
            "web design", "landing page", "figma", "crm system", "web portal",
            "inventory system",
        ],
        "weak": [
            "react", "next.js", "laravel", "django", "php", "javascript",
            "frontend", "front-end", "website", "responsive", "tailwind",
            "bootstrap", "wordpress", "database", "user interface",
        ],
    },
}

# Work outside the four service lines. Hits here cost points and can demote a
# job that was only matched because a keyword happened to appear.
OFF_TOPIC_TERMS = [
    "blockchain", "nft", "web3", "crypto", "cryptocurrency", "solidity",
    "smart contract", "defi", "token sale", "metaverse",
    "game development", "unity 3d", "unreal engine", "game developer",
    "cold calling", "cold call", "telemarketing", "appointment setter",
    "sales representative", "sales agent", "commission only", "closer",
    "virtual assistant", "data entry only", "typing job",
    "ios app", "android app", "flutter", "react native", "mobile app developer",
    "swift developer", "kotlin developer",
    "seo backlink", "article writing", "content writer", "ghostwriter",
    "video editing", "3d modeling", "logo design contest",
    "machine learning model training", "deep learning research",
]

# Terms that are off-topic on their own but fine when the job is genuinely a
# web build, so they are not penalised inside the web category.
OFF_TOPIC_EXEMPT = {
    CAT_WEB: {"ios app", "android app", "flutter", "react native",
              "mobile app developer"},
}

RELEVANCE_MAX = 24          # ceiling for the relevance component
STRONG_TITLE_POINTS = 8     # strong signal found in the title
STRONG_BODY_POINTS = 4      # strong signal found in description or skills
WEAK_TITLE_POINTS = 3
WEAK_BODY_POINTS = 1.5

OFF_TOPIC_PENALTY = 12      # per distinct off-topic term
OFF_TOPIC_PENALTY_MAX = 30

# Competition penalty by proposal count. Upwork reports bands, so the parser
# turns "20 to 50" into its lower bound and this table is read by lower bound.
PROPOSAL_PENALTY = [
    (0, 0),      # fewer than 5 proposals
    (5, 4),
    (10, 9),
    (15, 14),
    (20, 20),
    (50, 30),
]

# Freshness bonus by age in hours.
RECENCY_BONUS = [
    (24, 8),     # under a day old
    (48, 6),
    (72, 4),
    (96, 2),
    (120, 1),
]

PAYMENT_VERIFIED_BONUS = 2

# A job is moved out of the category that found it when that category scores
# poorly on relevance and another category beats it by this margin.
REASSIGN_MARGIN = 6
# Below this relevance the job is considered a poor fit for every category and
# is demoted rather than treated as on topic.
POOR_FIT_RELEVANCE = 4

# Fit bands.
#
# The fixed anchors below suit a typical day: an on-topic job with average
# competition and a day or two of age lands in the low 70s.
#
# Competition on Upwork swings a lot day to day, so fixed cut offs alone tend
# to dump a whole run into one bucket. When a run has enough jobs, the bands
# are recalculated from that run's own score tertiles, then clamped by the
# floors and ceilings below so a genuinely weak job can never be called High
# and a strong one can never be called Low.
FIT_HIGH_MIN = 80
FIT_MEDIUM_MIN = 66

FIT_ADAPTIVE = True
FIT_ADAPTIVE_MIN_JOBS = 9
FIT_HIGH_FLOOR, FIT_HIGH_CEIL = 68, 86
FIT_MEDIUM_FLOOR, FIT_MEDIUM_CEIL = 52, 72
# No matter what the distribution looks like, a job under this score is Low.
FIT_HARD_LOW_MAX = 55

# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

HEADLESS = True

# Scrape using the saved browser profile rather than a clean context built from
# storage_state.json. Slower to start but much less likely to be challenged,
# which helps if Cloudflare keeps stopping the run.
USE_PERSISTENT_PROFILE = False

# Force a browser channel ("chrome", "msedge") instead of letting login_setup
# pick one. Leave as None to autodetect.
BROWSER_CHANNEL = None
NAV_TIMEOUT_MS = 60_000
CLOUDFLARE_TIMEOUT_MS = 45_000
# Pause between page loads so the run does not hammer Upwork.
DELAY_BETWEEN_PAGES_MS = (2_500, 5_000)

# Set UPWORK_CHROMIUM_PATH when Playwright's bundled Chromium is missing or you
# would rather drive a Chromium/Chrome already installed on the machine.
CHROMIUM_EXECUTABLE_PATH = os.environ.get("UPWORK_CHROMIUM_PATH") or None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}
LOCALE = "en-US"
