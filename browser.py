"""Browser launching shared by the login helper and the scraper.

Upwork and Google both refuse to serve their login pages to an obviously
automated browser. Two things cause that:

  1. Playwright's bundled Chromium is a "Chrome for Testing" build, which
     identifies itself as such.
  2. Chrome started by an automation tool carries the --enable-automation
     switch and sets navigator.webdriver, which the login pages look for.

So the login window is launched from the real Chrome or Edge installed on the
machine, with those two tells removed and a persistent profile directory, which
makes it behave like an ordinary browser window.

None of this defeats Google's own check on "Continue with Google". Google
blocks sign in from any browser driven over the DevTools protocol, real Chrome
included. Use an email and password in that window, or the import_cookies.py
route instead.
"""

import json
from datetime import datetime
from typing import Optional

import config

# Removes the automation tells the login pages check for.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--disable-features=Translate,OptimizationHints",
]

# Chrome adds this itself and it shows up in the page as an automation flag.
IGNORED_DEFAULT_ARGS = ["--enable-automation"]

# Patches the leftover JavaScript level tells before any page script runs.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5],
});
try {
  const query = window.navigator.permissions.query;
  window.navigator.permissions.query = (parameters) =>
    parameters && parameters.name === 'notifications' && window.Notification
      ? Promise.resolve({ state: window.Notification.permission })
      : query(parameters);
} catch (e) { /* permissions API missing, nothing to patch */ }
"""

# Tried in order when no channel is configured. None means Playwright's own
# bundled Chromium, which works for scraping but not for logging in.
CHANNEL_CANDIDATES = ["chrome", "msedge", "chrome-beta", None]


def launch_kwargs(headless: bool, channel: Optional[str] = None) -> dict:
    """Arguments shared by every browser this project starts."""
    kwargs = {
        "headless": headless,
        "args": list(STEALTH_ARGS),
        "ignore_default_args": list(IGNORED_DEFAULT_ARGS),
    }
    # A pinned binary and a named channel are mutually exclusive.
    if config.CHROMIUM_EXECUTABLE_PATH:
        kwargs["executable_path"] = config.CHROMIUM_EXECUTABLE_PATH
    elif channel:
        kwargs["channel"] = channel
    return kwargs


def apply_stealth(context) -> None:
    """Run the fingerprint patches in every page this context opens."""
    try:
        context.add_init_script(STEALTH_JS)
    except Exception:
        pass


def launch_persistent(playwright, channel: Optional[str], headless: bool = False):
    """Start a browser on its own profile directory.

    A persistent profile keeps cookies, local storage and the device
    fingerprint between runs, which is what an ordinary browser looks like.
    """
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = launch_kwargs(headless, channel)
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(config.PROFILE_DIR),
        locale=config.LOCALE,
        no_viewport=True,
        **kwargs,
    )
    apply_stealth(context)
    return context


def open_login_browser(playwright, preferred: Optional[str] = None):
    """Open a real browser window for logging in, trying the best channel first.

    Returns (context, channel_used). Raises RuntimeError when nothing starts.
    """
    candidates = [preferred] if preferred else list(CHANNEL_CANDIDATES)
    if config.CHROMIUM_EXECUTABLE_PATH:
        candidates = [None]

    errors = []
    for channel in candidates:
        try:
            context = launch_persistent(playwright, channel, headless=False)
            return context, channel
        except Exception as exc:
            errors.append(f"{channel or 'bundled chromium'}: "
                          f"{str(exc).splitlines()[0][:120]}")
    raise RuntimeError(
        "Could not start a browser. Tried:\n  " + "\n  ".join(errors)
    )


def seed_cookies_from_storage_state(context) -> int:
    """Copy the saved cookies into a persistent context.

    A profile created by login_setup.py already carries the session. One being
    used alongside a session that came from import_cookies.py does not, so the
    cookies have to be injected or the profile browses logged out.
    """
    if not config.STORAGE_STATE_PATH.exists():
        return 0
    try:
        data = json.loads(config.STORAGE_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    cookies = [c for c in data.get("cookies", []) if c.get("name")]
    if not cookies:
        return 0
    try:
        context.add_cookies(cookies)
        return len(cookies)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Session metadata
#
# The user agent and browser channel from the login are recorded so the scraper
# presents the same browser identity the cookies were issued to. A mismatch
# there is another thing Upwork can notice.
# ---------------------------------------------------------------------------

def save_session_meta(user_agent: str, channel: Optional[str]) -> None:
    payload = {
        "user_agent": user_agent,
        "channel": channel,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        config.SESSION_META_PATH.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def load_session_meta() -> dict:
    if not config.SESSION_META_PATH.exists():
        return {}
    try:
        data = json.loads(config.SESSION_META_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def session_user_agent() -> str:
    """The user agent captured at login, falling back to the configured one."""
    return load_session_meta().get("user_agent") or config.USER_AGENT


def session_channel() -> Optional[str]:
    return load_session_meta().get("channel")
