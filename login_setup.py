"""One time Upwork login.

Opens a real, visible Chromium window, waits while you log in by hand, then
saves the authenticated session to storage_state.json so pull_jobs.py can reuse
it headlessly.

Why this is needed: Upwork silently drops search filters such as "Payment
verified" and the proposal bands for logged out visitors. The filters only
apply to a logged in session.

    python login_setup.py
"""

import sys

from playwright.sync_api import sync_playwright

import config

LOGIN_URL = "https://www.upwork.com/ab/account-security/login"

# Any of these means we are past the login flow and inside the product.
LOGGED_IN_MARKERS = [
    "upwork.com/nx/find-work",
    "upwork.com/nx/search/jobs",
    "upwork.com/freelancers/",
    "upwork.com/nx/plans",
    "upwork.com/ab/find-work",
]


def looks_logged_in(page) -> bool:
    url = page.url
    if any(marker in url for marker in LOGGED_IN_MARKERS):
        return True
    # Fallback: the freelancer header avatar only renders for a live session.
    try:
        if page.locator('[data-test="nav-user-avatar"], '
                        '[data-test="UpCAvatar"], '
                        'button[data-test="user-menu"]').count() > 0:
            return True
    except Exception:
        pass
    return False


def main() -> int:
    print("=" * 70)
    print("Upwork login setup")
    print("=" * 70)
    print()
    print("A Chromium window will open on the Upwork login page.")
    print("Log in there by hand, including any 2FA or device verification.")
    print("Solve the Cloudflare check if it appears.")
    print()
    print("When you can see your logged in Upwork home or job feed, come back")
    print("to this terminal and press ENTER to save the session.")
    print()

    with sync_playwright() as p:
        launch_kwargs = {"headless": False, "args": ["--start-maximized"]}
        if config.CHROMIUM_EXECUTABLE_PATH:
            launch_kwargs["executable_path"] = config.CHROMIUM_EXECUTABLE_PATH
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=config.USER_AGENT,
            viewport=config.VIEWPORT,
            locale=config.LOCALE,
        )
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, timeout=config.NAV_TIMEOUT_MS)
        except Exception as exc:
            print(f"Could not open the login page: {exc}")
            print("Check your internet connection and try again.")
            browser.close()
            return 1

        try:
            input("Press ENTER once you are logged in... ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled, nothing was saved.")
            browser.close()
            return 1

        if not looks_logged_in(page):
            print()
            print("Warning: this still does not look like a logged in page.")
            print(f"Current URL: {page.url}")
            answer = input("Save the session anyway? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Nothing was saved. Run this script again when ready.")
                browser.close()
                return 1

        context.storage_state(path=str(config.STORAGE_STATE_PATH))
        browser.close()

    print()
    print(f"Session saved to {config.STORAGE_STATE_PATH}")
    print("This file is a live credential. It is already in .gitignore, keep it")
    print("out of version control and off shared machines.")
    print()
    print("Next step:  python pull_jobs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
