#!/usr/bin/env python3
"""Build storage_state.json from cookies exported by your normal browser.

Use this when login_setup.py cannot get you in, which is the usual outcome when
your Upwork account signs in through Google. Google refuses to authenticate any
browser driven by an automation tool, so the only way past it is to log in in
your everyday browser and hand the resulting session over.

    1. Log in to Upwork normally, in Chrome, Edge or Firefox.
    2. Export the cookies for upwork.com with a cookie export extension, for
       example "Get cookies.txt LOCALLY" or "Cookie-Editor".
    3. python import_cookies.py cookies.txt --user-agent "<your UA>"

Find your user agent at chrome://version (the "User Agent" line), or by running
navigator.userAgent in the browser console. Passing it matters: the scraper then
presents the same browser identity the cookies were issued to.

Accepted formats: Netscape cookies.txt, a JSON array from a cookie editor
extension, or an existing Playwright storage_state file.

The file this writes is a live credential. Do not commit it, do not paste its
contents anywhere, and delete the cookie export once you are done.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List

import browser
import config

UPWORK_DOMAIN_HINTS = ("upwork.com",)

# If none of these show up the export probably came from a logged out browser.
SESSION_COOKIE_HINTS = (
    "master_access_token",
    "oauth2_global_js_token",
    "console_user",
    "user_uid",
)

SAME_SITE_MAP = {
    "no_restriction": "None",
    "none": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
}


def normalise_same_site(value) -> str:
    if not value:
        return "Lax"
    return SAME_SITE_MAP.get(str(value).strip().lower(), "Lax")


def parse_netscape(text: str) -> List[dict]:
    """Parse the tab separated cookies.txt format."""
    cookies = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        http_only = False
        if raw.startswith("#HttpOnly_"):
            raw = raw[len("#HttpOnly_"):]
            http_only = True
        elif raw.startswith("#"):
            continue

        fields = raw.split("\t")
        if len(fields) < 7:
            continue
        domain, _flag, path, secure, expires, name, value = fields[:7]
        try:
            expires_at = float(expires)
        except ValueError:
            expires_at = -1
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path or "/",
            "expires": expires_at if expires_at > 0 else -1,
            "httpOnly": http_only,
            "secure": secure.strip().upper() == "TRUE",
            "sameSite": "Lax",
        })
    return cookies


def parse_json_cookies(data) -> List[dict]:
    """Parse a cookie editor export or an existing storage_state file."""
    if isinstance(data, dict):
        data = data.get("cookies", [])
    if not isinstance(data, list):
        return []

    cookies = []
    for item in data:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        expires = item.get("expires", item.get("expirationDate", -1))
        try:
            expires = float(expires)
        except (TypeError, ValueError):
            expires = -1
        cookies.append({
            "name": item["name"],
            "value": item.get("value", ""),
            "domain": item.get("domain", ""),
            "path": item.get("path") or "/",
            "expires": expires if expires and expires > 0 else -1,
            "httpOnly": bool(item.get("httpOnly", False)),
            "secure": bool(item.get("secure", False)),
            "sameSite": normalise_same_site(item.get("sameSite")),
        })
    return cookies


def load_cookies(path: Path) -> List[dict]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            return parse_json_cookies(json.loads(text))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"That file looks like JSON but will not parse: {exc}")
    return parse_netscape(text)


def clean(cookies: List[dict]) -> List[dict]:
    """Keep the Upwork cookies and make them acceptable to Playwright."""
    now = time.time()
    kept, expired = [], 0

    for cookie in cookies:
        domain = (cookie.get("domain") or "").lstrip(".")
        if not any(hint in domain for hint in UPWORK_DOMAIN_HINTS):
            continue
        if cookie["expires"] != -1 and cookie["expires"] < now:
            expired += 1
            continue
        # Playwright rejects SameSite=None on a cookie that is not secure.
        if cookie["sameSite"] == "None" and not cookie["secure"]:
            cookie["secure"] = True
        kept.append(cookie)

    if expired:
        print(f"  Skipped {expired} cookie(s) that had already expired.")
    return kept


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Turn a browser cookie export into storage_state.json."
    )
    parser.add_argument("cookie_file",
                        help="cookies.txt or JSON exported from your browser")
    parser.add_argument("--user-agent", default=None,
                        help="the user agent of the browser you exported from, "
                             "from chrome://version")
    args = parser.parse_args(argv)

    source = Path(args.cookie_file).expanduser()
    if not source.exists():
        print(f"No such file: {source}")
        return 1

    print("=" * 72)
    print("Importing an Upwork session from a cookie export")
    print("=" * 72)
    print()

    cookies = clean(load_cookies(source))
    if not cookies:
        print("  No upwork.com cookies were found in that file.")
        print("  Export again with the Upwork tab open and logged in, and make")
        print("  sure the extension is exporting the current site's cookies.")
        return 1

    names = {cookie["name"] for cookie in cookies}
    print(f"  Found {len(cookies)} upwork.com cookie(s).")

    if not any(hint in names for hint in SESSION_COOKIE_HINTS):
        print()
        print("  Warning: none of the usual Upwork session cookies are here")
        print(f"  ({', '.join(SESSION_COOKIE_HINTS)}).")
        print("  The export may have come from a logged out browser. Writing it")
        print("  anyway, but check it with: python login_setup.py --check")

    config.STORAGE_STATE_PATH.write_text(
        json.dumps({"cookies": cookies, "origins": []}, indent=2),
        encoding="utf-8",
    )

    user_agent = args.user_agent
    if user_agent:
        browser.save_session_meta(user_agent, None)
    else:
        print()
        print("  No --user-agent given, so a default one is recorded. If Upwork")
        print("  rejects the session, rerun with the real one from")
        print("  chrome://version, it has to match the browser you exported from.")
        browser.save_session_meta(config.USER_AGENT, None)

    print()
    print(f"  Session written to {config.STORAGE_STATE_PATH}")
    print()
    print("  This file is a live credential. Delete the cookie export you just")
    print("  imported, and never paste either one into a chat or an issue.")
    print()
    print("  Check it worked:  python login_setup.py --check")
    print("  Then run:         python pull_jobs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
