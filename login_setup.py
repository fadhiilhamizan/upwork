#!/usr/bin/env python3
"""One time Upwork login.

    python login_setup.py           open a browser and log in by hand
    python login_setup.py --check   test the session that is already saved

Opens a window using the real Chrome or Edge installed on this machine, with
the automation flags removed, because Upwork's login page will not render in
Playwright's own "Chrome for Testing" build. Log in by hand, press ENTER here,
and the session is saved to storage_state.json.

Upwork silently drops search filters such as "Payment verified" and the
proposal bands for logged out visitors, which is why a real session is needed.

If this still will not let you in, use import_cookies.py instead. That takes
the session from the browser you use every day and never automates the login
at all.
"""

import argparse
import sys

from playwright.sync_api import sync_playwright

import browser
import config

HOME_URL = "https://www.upwork.com/"
LOGIN_URL = "https://www.upwork.com/ab/account-security/login"
CHECK_URL = "https://www.upwork.com/nx/find-work/"

# Any of these means we are past the login flow and inside the product.
LOGGED_IN_MARKERS = [
    "upwork.com/nx/find-work",
    "upwork.com/nx/search/jobs",
    "upwork.com/freelancers/",
    "upwork.com/nx/plans",
    "upwork.com/ab/find-work",
    "upwork.com/nx/wm/",
]

GOOGLE_NOTE = """
  Note on "Continue with Google"
  ------------------------------
  Google blocks sign in from any browser started by an automation tool, real
  Chrome included, with the message about network restrictions at your
  location. There is no way around it from this side.

  Use your Upwork email and password in this window instead. If your account
  only has Google sign in, set a password first at
  https://www.upwork.com/ab/account-security/settings, or use import_cookies.py.
"""


def looks_logged_in(page) -> bool:
    url = page.url or ""
    if any(marker in url for marker in LOGGED_IN_MARKERS):
        return True
    try:
        if page.locator('[data-test="nav-user-avatar"], '
                        '[data-test="UpCAvatar"], '
                        'button[data-test="user-menu"]').count() > 0:
            return True
    except Exception:
        pass
    return False


def looks_blank(page) -> bool:
    """True when the page rendered essentially nothing."""
    try:
        return len((page.inner_text("body", timeout=5_000) or "").strip()) < 40
    except Exception:
        return True


def do_login() -> int:
    print("=" * 72)
    print("Upwork login setup")
    print("=" * 72)

    with sync_playwright() as playwright:
        try:
            context, channel = browser.open_login_browser(
                playwright, config.BROWSER_CHANNEL
            )
        except RuntimeError as exc:
            print(f"\n{exc}")
            print("\nInstall Google Chrome or Microsoft Edge, or set "
                  "UPWORK_CHROMIUM_PATH to a browser binary.")
            return 1

        label = channel or "Playwright's bundled Chromium"
        print(f"\n  Browser : {label}")
        print(f"  Profile : {config.PROFILE_DIR}")
        if channel is None:
            print("\n  Warning: no installed Chrome or Edge was found, so this is")
            print("  the bundled test build. Upwork's login page often refuses to")
            print("  render in it. If you get a blank page, install Chrome or use")
            print("  import_cookies.py.")
        print(GOOGLE_NOTE)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Landing on the home page first and then the login page is closer
            # to how a person arrives, and avoids some blank page cases.
            page.goto(HOME_URL, wait_until="domcontentloaded",
                      timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(1_500)
            page.goto(LOGIN_URL, wait_until="domcontentloaded",
                      timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(3_000)
        except Exception as exc:
            print(f"  Could not open the login page: {exc}")
            context.close()
            return 1

        if looks_blank(page):
            print("  The login page came back blank. Try reloading it in the")
            print("  window, or click Log In from the Upwork home page. If it")
            print("  stays blank, use import_cookies.py.")

        print("  Log in in the browser window, including any 2FA or device check.")
        print("  Solve the Cloudflare check if one appears.")
        print()

        try:
            input("  Press ENTER once you are logged in and can see your feed... ")
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled, nothing was saved.")
            context.close()
            return 1

        if not looks_logged_in(page):
            print()
            print("  Warning: this still does not look like a logged in page.")
            print(f"  Current URL: {page.url}")
            answer = input("  Save the session anyway? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("  Nothing was saved. Run this script again when ready.")
                context.close()
                return 1

        try:
            user_agent = page.evaluate("() => navigator.userAgent")
        except Exception:
            user_agent = config.USER_AGENT

        context.storage_state(path=str(config.STORAGE_STATE_PATH))
        browser.save_session_meta(user_agent, channel)
        context.close()

    print()
    print(f"  Session saved to {config.STORAGE_STATE_PATH}")
    print(f"  Browser identity saved to {config.SESSION_META_PATH}")
    print()
    print("  These are live credentials. They are already in .gitignore, keep")
    print("  them out of version control and off shared machines.")
    print()
    print("  Check it worked:  python login_setup.py --check")
    print("  Then run:         python pull_jobs.py")
    return 0


def do_check() -> int:
    """Load the saved session and see whether Upwork still accepts it."""
    print("=" * 72)
    print("Checking the saved Upwork session")
    print("=" * 72)

    if not config.STORAGE_STATE_PATH.exists():
        print(f"\n  No session file at {config.STORAGE_STATE_PATH}")
        print("  Run: python login_setup.py")
        return 2

    # Imported here so --check still works if the scraper is being edited.
    from scraper import SessionExpiredError, UpworkScraper

    with sync_playwright() as playwright:
        scraper = None
        alive, detail = False, ""
        try:
            scraper = UpworkScraper(playwright, headless=True, verbose=True)
            scraper._open(CHECK_URL)
            alive = True
        except SessionExpiredError as exc:
            detail = str(exc)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        finally:
            if scraper is not None:
                scraper.close()

    print()
    if alive:
        meta = browser.load_session_meta()
        print("  The session works. Upwork served a logged in page.")
        if meta.get("saved_at"):
            print(f"  Saved at: {meta['saved_at']}")
        print("\n  Run: python pull_jobs.py")
        return 0

    print(f"  The session was rejected: {detail}")
    print("\n  Run: python login_setup.py")
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Log in to Upwork once and save the session."
    )
    parser.add_argument("--check", action="store_true",
                        help="test the saved session instead of logging in")
    args = parser.parse_args(argv)
    return do_check() if args.check else do_login()


if __name__ == "__main__":
    sys.exit(main())
