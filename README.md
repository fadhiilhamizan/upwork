# Upwork Daily Job Report

Pulls freelance job listings from Upwork for four service categories, scores and
categorises them, and writes everything into a single Excel workbook that is
overwritten in place on every run.

The four categories:

1. Custom Web Data Scraping
2. Google Sheets Automation
3. Microsoft Excel Solutions
4. Web Management Systems & UI/UX Design

## Setup

Python 3.9 or newer.

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

If Playwright's bundled Chromium will not install or you would rather use a
browser already on the machine, point the tool at it:

```bash
export UPWORK_CHROMIUM_PATH=/path/to/chrome      # macOS / Linux
set UPWORK_CHROMIUM_PATH=C:\path\to\chrome.exe   # Windows
```

## Step 1: get a logged in session

Upwork silently ignores search filters such as "Payment verified" and the
proposal bands for logged out visitors, so a real session is required. There are
two ways to get one. Try the first, fall back to the second.

### Option A: log in through the script

```bash
python login_setup.py
```

This opens a window using the real Chrome or Edge installed on your machine,
with the automation flags stripped out, and waits while you log in by hand. Press
ENTER in the terminal afterwards and the session is saved to
`storage_state.json`, along with your browser's user agent in
`session_meta.json`.

Check it afterwards:

```bash
python login_setup.py --check
```

**"Continue with Google" will not work here.** Google refuses to sign in any
browser driven by an automation tool, real Chrome included, and says so with a
message about network restrictions at your location. Nothing on this side can
change that. Use your Upwork email and password in that window. If your account
has no password because you only ever signed in with Google, either add one at
Upwork's account security settings, or use Option B.

### Option B: import cookies from the browser you already use

This never automates the login, so there is nothing for Upwork, Cloudflare or
Google to detect. Use it when Option A gives you a blank page, stalls on the
Cloudflare check, or when your account only has Google sign in.

1. Log in to Upwork normally in Chrome, Edge or Firefox.
2. Install a cookie export extension, such as "Get cookies.txt LOCALLY" or
   "Cookie-Editor".
3. With the Upwork tab open and logged in, export the cookies for `upwork.com`.
   Leave the downloaded file wherever your browser put it.
4. Run the importer and paste your user agent when it asks. Find it at
   `chrome://version`, on the "User Agent" line.

```bash
python import_cookies.py
python login_setup.py --check
```

With no arguments it searches the project folder, Downloads and Desktop for a
cookie export that actually contains Upwork cookies, and uses the newest one. To
name the file yourself:

```bash
python import_cookies.py "C:\Users\you\Downloads\www.upwork.com_cookies.txt" ^
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
```

Netscape `cookies.txt`, a JSON export from a cookie editor, and an existing
Playwright `storage_state.json` are all accepted. The user agent matters: the
cookies were issued to that browser identity, and the scraper presents the same
one.

Delete the cookie export once it is imported.

### Keep these files private

`storage_state.json`, `session_meta.json` and `browser_profile/` are live
credentials: anyone holding them is logged in as you. They are all in
`.gitignore`. Never commit them, never paste their contents into a chat, an
issue or a support ticket.

## Step 2: run the report

```bash
python pull_jobs.py
```

Options:

| Flag | What it does |
| --- | --- |
| `--demo` | Runs against the bundled sample listings instead of Upwork. No login needed, useful for checking the workbook layout. |
| `--headful` | Shows the browser window while scraping. |
| `--no-seen-tracking` | Skips reading and writing `seen_jobs.json`. |

Console output reports how many cards were scraped, how many survived the
recency filter and dedupe, the count per category, the High/Medium/Low totals,
and the top five picks.

If Upwork rejects the saved session the script says so and exits with code 2
without touching the existing workbook. Run `python login_setup.py` again.

## Output

`Upwork_Daily_Job_Report.xlsx` in the project folder. The path is fixed, so each
run overwrites the same file rather than piling up dated copies.

**Dashboard sheet:** title, generation timestamp, the filter summary, a per
category count table broken down by fit, a bar chart of jobs per category, and a
Top 10 Picks table sorted by score with hyperlinked titles.

**One sheet per category:** that category's jobs sorted by score descending, with
columns Score, Fit, New, Title (hyperlinked), Type, Rate/Budget, Proposals,
Posted, Location, Skills, Description. Fit is colour coded green, yellow, red.

Close the workbook in Excel before running, otherwise Windows blocks the write.
The script says so instead of failing obscurely.

### New listings

`seen_jobs.json` records the job IDs from previous runs. Anything not in it is
flagged `NEW` in the New column and counted on the dashboard. Delete the file to
treat every listing as new again. If the file is missing or unreadable the run
still completes, it just marks everything new.

## How jobs are filtered and scored

Each keyword search uses one URL that encodes the whole filter checklist:
intermediate experience level, hourly $5+/hr or fixed under $100 and $100-500,
every proposal band below 50, payment verified, clients with no hires, sorted by
most recent.

Only jobs posted within the last 5 days are kept. Since results come back sorted
by recency, paging stops at the first listing older than that. Jobs are deduped
across all eight searches on the numeric job ID in the URL (`~0123456789`).

The score is:

```
  base score for the category      52 to 58
+ topic relevance                  up to +24
+ recency bonus                    up to +8   (posted today beats posted 5 days ago)
+ payment verified                 +2
- competition penalty              0 to -30   (grows with proposal count)
- off topic penalty                0 to -30   (blockchain, NFT, web3, game dev,
                                               mobile only apps, cold calling, ...)
```

A job is moved to a different category when its title and description clearly fit
another one better, so a "scraping" search result that is really a blockchain or
game development job gets demoted instead of counting as on topic.

Fit bands are anchored at 80 (High) and 66 (Medium). Because competition on
Upwork swings day to day, a run with enough jobs recalculates the bands from its
own score tertiles, clamped so a weak job can never be labelled High and a strong
one never Low. That keeps a day's results spread across the three bands instead
of piling into one. All of this lives in `config.py`.

## Scheduling it to run every morning

The script has no built in scheduler. Use your OS's.

### macOS / Linux (cron)

```bash
crontab -e
```

Add a line to run it at 08:00 daily. Use absolute paths, cron does not inherit
your shell environment:

```cron
0 8 * * * cd /home/you/upwork && /usr/bin/python3 pull_jobs.py >> run.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler and choose "Create Basic Task".
2. Name it, then set the trigger to Daily at 08:00.
3. Action: "Start a program".
   - Program/script: `python` (or the full path to `python.exe`)
   - Add arguments: `pull_jobs.py`
   - Start in: the full path to this project folder
4. Under Properties, tick "Run whether user is logged on or not" if you want it
   to run on a locked machine.

Either way, expect to rerun `login_setup.py` every so often. Upwork sessions do
not last forever, and the script tells you when the saved one stops working.

## Troubleshooting login

**"Continue with Google is not available due to network restrictions and/or
traffic blocking at your location."** Google's own block on automated browsers.
Use email and password, or Option B above.

**The login page is blank white.** Upwork's login app refused to render for the
browser it was given. In order: make sure Chrome or Edge is installed so
`login_setup.py` does not fall back to Playwright's bundled test build (the
script prints which browser it used); try reloading in the window; then use
Option B.

**Upwork rejects the session on the next run.** Sessions expire. Rerun
`login_setup.py`, or re-export cookies. `python login_setup.py --check` tells you
whether the saved session is still good without running a full scrape.

**The Cloudflare check appears and then the page goes blank.** Same detection as
the blank login page: the check passes, then Upwork's app refuses to render for
an automated browser. Use Option B.

**Cloudflare keeps stopping the scrape itself.** Set `USE_PERSISTENT_PROFILE =
True` in `config.py` and run `python pull_jobs.py --headful`. The scrape then
reuses a real browser profile instead of a clean context, which is much less
likely to be challenged. Cookies from `storage_state.json` are loaded into that
profile automatically, so this works with an imported session too. It starts more
slowly and needs a visible desktop, so it is not suited to a scheduled run.

**No installed browser is found.** Set `UPWORK_CHROMIUM_PATH` to a Chrome, Edge
or Chromium binary, or set `BROWSER_CHANNEL` in `config.py` to `"chrome"` or
`"msedge"`.

## Maintenance

Upwork's `data-test` attributes are more stable than its generated class names,
but they still change without notice. Every field is read through a list of
fallback selectors, so one rename usually will not break the run.

```bash
python selftest.py
```

34 offline checks over the parsers, the scoring rules, cookie import, the
automation flag removal, the Cloudflare
interstitial handling, expired session detection, cookie banner dismissal, and
card extraction against Upwork shaped markup. No network access needed. Run it
after changing any selector.

If a live run finds no job cards, it writes `debug_<keyword>.html` and
`debug_<keyword>.png` for the failing search. Open those, find the current
attributes, and add them to the selector lists at the top of `scraper.py`.

## Files

| File | Purpose |
| --- | --- |
| `login_setup.py` | Manual login in a real browser, and `--check` to test a saved session |
| `import_cookies.py` | Builds `storage_state.json` from a cookie export, for when login is blocked |
| `browser.py` | Browser launching, automation flag removal, saved browser identity |
| `pull_jobs.py` | Main entry point: scrape, score, write the workbook |
| `config.py` | Categories, keywords, search URL, scoring weights, paths |
| `scraper.py` | Playwright scraping, Cloudflare and session handling, card extraction |
| `parsing.py` | Text parsing for dates, proposals, prices, job IDs |
| `scoring.py` | Scoring, categorisation, dedupe, recency filter, fit bands |
| `report.py` | Excel workbook generation |
| `models.py` | The `Job` record |
| `demo_source.py` | Renders sample listings for `--demo` and the self test |
| `sample_jobs.py` | Sample listing data |
| `selftest.py` | Offline checks |

## Notes and limits

- This drives a real browser against your own logged in account and reads only
  public search results. Keep the run to once or twice a day. The script already
  pauses a few seconds between page loads.
- Cloudflare occasionally serves a challenge that does not clear on its own. The
  run continues and reports what it could read. Rerunning usually clears it.
- Upwork's proposal counts are bands, not exact numbers. The lower bound of the
  band is used for the competition penalty.
