#!/usr/bin/env python3
"""Post the newest guild news item to Discord, once.

Run after scripts/update_site.py. Reads the post that script just wrote to
news-auto.json and sends it to a Discord webhook, in the Guild Master's name.

Does nothing at all when DISCORD_WEBHOOK_URL is unset, so the daily job keeps
working exactly as before until someone adds the secret.

It remembers the last post it sent in discord/last-posted.json, so re-running
the job on a day with no armory changes does not repost yesterday's news.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "news-auto.json"
MARKER = ROOT / "discord" / "last-posted.json"
HOMEPAGE = "https://spoeket.github.io/group-of-workers/"
LIMIT = 1900  # Discord's cap is 2000; leave room for the footer.


def ssl_context() -> ssl.SSLContext:
    """Verified context. Falls back to certifi where the platform has no bundle."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", '"'), ("&middot;", "-"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    return text.strip()


def main() -> int:
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        print("DISCORD_WEBHOOK_URL not set - skipping Discord.")
        return 0

    if not NEWS.exists():
        print("no news-auto.json yet - nothing to post.")
        return 0

    posts = json.loads(NEWS.read_text(encoding="utf-8")).get("posts", [])
    if not posts:
        print("no posts - nothing to say.")
        return 0

    newest = posts[0]
    lines = [strip_html(line) for line in newest["lines"]]
    fingerprint = hashlib.sha256(
        (newest["date"] + "\n".join(lines)).encode("utf-8")
    ).hexdigest()

    if MARKER.exists():
        if json.loads(MARKER.read_text(encoding="utf-8")).get("fingerprint") == fingerprint:
            print("newest post already went to Discord - nothing to do.")
            return 0

    body = "\n".join("- " + line for line in lines)
    content = "**GUILD NEWS - %s**\n%s\n\n<%s>" % (newest["date"], body, HOMEPAGE)
    if len(content) > LIMIT:
        content = content[: LIMIT - 3] + "..."

    payload = json.dumps({"username": "Business Manadin", "content": content}).encode()
    request = urllib.request.Request(
        webhook,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "group-of-workers/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as response:
            response.read()
    except urllib.error.HTTPError as error:
        # A broken webhook must never fail the daily job - the site is the
        # thing that matters, Discord is a bonus.
        print("Discord said %s: %s" % (error.code, error.read().decode()), file=sys.stderr)
        return 0
    except urllib.error.URLError as error:
        print("could not reach Discord: %s" % error.reason, file=sys.stderr)
        return 0

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        json.dumps({"fingerprint": fingerprint, "date": newest["date"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    print("posted %d line(s) to Discord." % len(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
