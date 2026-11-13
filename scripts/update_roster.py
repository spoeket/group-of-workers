#!/usr/bin/env python3
"""Rebuild the roster table in index.html from the guild armory page.

Only the regions between the <!--ROSTER_*--> markers are touched, so every
joke on the page survives. Per-member notes live in roster-notes.json.

Refuses to write anything if the fetch fails or returns no members, so a bad
day at the armory can never blank the roster.
"""

import html
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ARMORY_URL = os.environ.get(
    "ARMORY_URL",
    "https://armorywowforever.com/g/forever/eu/pvp/group-of-workers",
)
USER_AGENT = "group-of-workers-roster/1.0 (static site roster sync)"

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
NOTES = ROOT / "roster-notes.json"
SNAPSHOT = ROOT / "roster-data.json"

# Class name on the armory -> the CSS class the page uses for its colour.
CLASS_SLUG = {
    "warrior": "warrior",
    "mage": "mage",
    "priest": "priest",
    "rogue": "rogue",
    "hunter": "hunter",
    "warlock": "warlock",
    "shaman": "shaman",
    "druid": "druid",
    "paladin": "paladin",
}

MEMBER_BLOCK = re.compile(r'<a\s+class="member".*?</a>', re.S)
TAGS = re.compile(r"<[^>]+>")


def ssl_context() -> ssl.SSLContext:
    """Verified context. Falls back to certifi where the platform has no bundle."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def cell(block: str, name: str) -> str:
    match = re.search(r'<span class="c-%s"[^>]*>(.*?)</span>' % name, block, re.S)
    if not match:
        return ""
    return html.unescape(TAGS.sub("", match.group(1))).strip()


def parse_members(document: str) -> list[dict]:
    members = []
    for block in MEMBER_BLOCK.findall(document):
        name = cell(block, "name")
        if not name:
            continue
        members.append(
            {
                "name": name,
                "level": cell(block, "level"),
                "race": cell(block, "race"),
                "klass": cell(block, "class"),
                "rank": cell(block, "rank"),
            }
        )
    return members


def build_rows(members: list[dict], config: dict) -> str:
    notes = config.get("notes", {})
    ranks = config.get("rank_titles", {})
    fallback = config.get("default_note", "")
    lines = []
    for member in members:
        slug = CLASS_SLUG.get(member["klass"].lower(), "")
        note = notes.get(member["name"], fallback)
        rank = ranks.get(member["rank"], member["rank"])
        lines.append(
            '              <tr>'
            '<td class="cname {slug}">{name}</td>'
            '<td class="num">{level}</td>'
            '<td>{race} <span class="{slug}">{klass}</span></td>'
            '<td>{rank}</td>'
            '<td>{note}</td>'
            '</tr>'.format(
                slug=slug,
                name=html.escape(member["name"]),
                level=html.escape(member["level"]),
                race=html.escape(member["race"]),
                klass=html.escape(member["klass"]),
                rank=html.escape(rank),
                note=html.escape(note),
            )
        )
    return "\n".join(lines)


def build_stats(members: list[dict], config: dict) -> str:
    counts = Counter(member["klass"] for member in members)
    paladins = counts.get("Paladin", 0)
    priests = counts.get("Priest", 0)
    text = config.get("stat_lines", {})

    if paladins >= 3:
        paladin_line = text.get("paladin_high", "Paladins: {n} (too many)")
    else:
        paladin_line = text.get("paladin_ok", "Paladins: {n}")
    if priests == 0:
        priest_line = text.get("priest_zero", "Priests: 0 (HELP)")
    else:
        priest_line = text.get("priest_some", "Priests: {n} (THANK U)")

    return "\n".join(
        [
            "          <li>Members: <b>%d</b></li>" % len(members),
            "          <li>Leveling: at ur own pace</li>",
            '          <li class="paladin">%s</li>'
            % html.escape(paladin_line.format(n=paladins)),
            '          <li class="priest">%s</li>'
            % html.escape(priest_line.format(n=priests)),
            "          <li>Cooks: 0 (RIP Biff)</li>",
        ]
    )


def replace_region(page: str, marker: str, body: str, block: bool) -> str:
    opening, closing = "<!--%s-->" % marker, "<!--/%s-->" % marker
    pattern = re.compile(
        re.escape(opening) + ".*?" + re.escape(closing), re.S
    )
    if not pattern.search(page):
        raise SystemExit("marker %s missing from %s" % (marker, PAGE.name))
    filling = "\n%s\n" % body if block else body
    return pattern.sub(lambda _: opening + filling + closing, page, count=1)


def main() -> int:
    try:
        document = fetch(ARMORY_URL)
    except (urllib.error.URLError, TimeoutError) as error:
        print("armory fetch failed: %s" % error, file=sys.stderr)
        return 1

    members = parse_members(document)
    if not members:
        print("no members parsed - markup probably changed", file=sys.stderr)
        return 1

    config = json.loads(NOTES.read_text(encoding="utf-8"))
    page = PAGE.read_text(encoding="utf-8")
    before = page

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = replace_region(page, "ROSTER_ROWS", build_rows(members, config), True)
    page = replace_region(page, "ROSTER_STATS", build_stats(members, config), True)
    page = replace_region(page, "ROSTER_COUNT", str(len(members)), False)
    page = replace_region(page, "ROSTER_SYNC", html.escape(stamp), False)

    SNAPSHOT.write_text(
        json.dumps({"fetched": stamp, "members": members}, indent=2) + "\n",
        encoding="utf-8",
    )

    unknown = sorted(
        {m["name"] for m in members} - set(config.get("notes", {}))
    )
    if unknown:
        print("no note yet for: %s" % ", ".join(unknown))

    if page == before:
        print("roster unchanged (%d members)" % len(members))
        return 0

    PAGE.write_text(page, encoding="utf-8")
    print("roster updated (%d members)" % len(members))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
