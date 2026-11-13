#!/usr/bin/env python3
"""Rebuild the roster from the guild armory, and write news posts about what changed.

Only the regions between the <!--ROSTER_*--> and <!--AUTO_NEWS--> markers in
index.html are touched, so every hand-written joke on the page survives.

Each run compares the armory against the last snapshot (roster-data.json) and,
if anything happened, adds ONE post in the Guild Master's voice covering dings,
new members, leavers and promotions. One post per run, never a flood.

Refuses to write anything if the fetch fails or no members parse, so a bad day
at the armory can neither blank the roster nor invent news.
"""

import hashlib
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
NEWS = ROOT / "news-auto.json"

KEEP_POSTS = 10

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


# --------------------------------------------------------------- fetch/parse

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


# ---------------------------------------------------------------- page bits

def coloured(member: dict) -> str:
    """The member's name in their class colour."""
    slug = CLASS_SLUG.get(member["klass"].lower(), "")
    return '<span class="%s">%s</span>' % (slug, html.escape(member["name"]))


def build_rows(members: list[dict], config: dict) -> str:
    notes = config.get("notes", {})
    ranks = config.get("rank_titles", {})
    fallback = config.get("default_note", "")
    lines = []
    for member in members:
        slug = CLASS_SLUG.get(member["klass"].lower(), "")
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
                rank=html.escape(ranks.get(member["rank"], member["rank"])),
                note=html.escape(notes.get(member["name"], fallback)),
            )
        )
    return "\n".join(lines)


def build_stats(members: list[dict], config: dict) -> str:
    counts = Counter(member["klass"] for member in members)
    paladins = counts.get("Paladin", 0)
    priests = counts.get("Priest", 0)
    text = config.get("stat_lines", {})

    paladin_line = text.get(
        "paladin_high" if paladins >= 3 else "paladin_ok", "Paladins: {n}"
    )
    priest_line = text.get(
        "priest_zero" if priests == 0 else "priest_some", "Priests: {n}"
    )

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


# --------------------------------------------------------------------- news

def pick(options: list[str], seed: str) -> str:
    """Stable choice, so re-runs never reshuffle wording already published."""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return options[int(digest, 16) % len(options)]


def rank_order(rank: str) -> int:
    if rank.strip().lower().startswith("guild master"):
        return 0
    found = re.search(r"\d+", rank)
    return int(found.group()) if found else 99


def as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


DING = [
    "grats {who} on ding {level}!!!",
    "{who} dinged {level}!!! grats!!",
    "DING!!! {who} is now level {level}. well done",
    "{who} has reached level {level}. productivity is UP",
]

MILESTONE = [
    "{who} HIT LEVEL {level}!!!! HUGE!!! drinks on the guild bank (we have 4g)",
    "LEVEL {level} FOR {who}!!! a big day for the company",
    "{who} is LEVEL {level}!!!! someone tell the shareholders",
]

JOINED = [
    "WELCOME TO THE COMPANY {who}!!! ({race} {klass}) Inboarding starts Monday. "
    "Ur buddy will find u.",
    "NEW HIRE!!! {who} ({race} {klass}) has joined &lt;Group of workers&gt;. "
    "Say hi in guild chat!!",
    "Please welcome {who}, our new {klass}. HR has been notified.",
]

LEFT = [
    "{who} has left the guild. Exit interview pending.",
    "{who} has /gquit. We wish them well. (they still owe the guild bank 2g)",
    "{who} has moved on to another opportunity. The campfire is colder today.",
]

PROMOTED = [
    "{who} has been promoted to {rank}!!! More responsibility, same pay (0g).",
    "CONGRATULATIONS {who}, now {rank}!!! A new chair has been requested.",
    "{who} is now {rank}. Please update ur org chart.",
]


def detect_events(old: list[dict], new: list[dict]) -> dict:
    before = {member["name"]: member for member in old}
    after = {member["name"]: member for member in new}

    events = {"dinged": [], "joined": [], "left": [], "promoted": []}

    for name, member in after.items():
        previous = before.get(name)
        if previous is None:
            events["joined"].append(member)
            continue
        if as_int(member["level"]) > as_int(previous["level"]):
            events["dinged"].append(member)
        if rank_order(member["rank"]) < rank_order(previous["rank"]):
            events["promoted"].append(member)

    for name, member in before.items():
        if name not in after:
            events["left"].append(member)

    return events


def compose_post(events: dict, config: dict) -> list[str]:
    """One post's paragraphs, or [] when nothing happened."""
    ranks = config.get("rank_titles", {})
    lines = []

    for member in sorted(events["dinged"], key=lambda m: -as_int(m["level"])):
        level = as_int(member["level"])
        pool = MILESTONE if (level % 10 == 0 or level == 60) else DING
        lines.append(
            pick(pool, member["name"] + str(level)).format(
                who=coloured(member), level=level
            )
        )

    for member in events["joined"]:
        lines.append(
            pick(JOINED, member["name"]).format(
                who=coloured(member),
                race=html.escape(member["race"]),
                klass=html.escape(member["klass"]),
            )
        )

    for member in events["promoted"]:
        rank = ranks.get(member["rank"], member["rank"])
        lines.append(
            pick(PROMOTED, member["name"] + member["rank"]).format(
                who=coloured(member), rank=html.escape(rank)
            )
        )

    for member in events["left"]:
        lines.append(pick(LEFT, member["name"]).format(who=coloured(member)))

    return lines


def render_news(posts: list[dict]) -> str:
    chunks = []
    for index, post in enumerate(posts):
        badge = ' <span class="new">NEW!</span>' if index == 0 else ""
        body = "\n".join("          <p>%s</p>" % line for line in post["lines"])
        chunks.append(
            '        <article class="post">\n'
            '          <p class="meta">%s &middot; posted by <b>Business Manadin</b>%s</p>\n'
            "%s\n"
            "        </article>" % (post["date"], badge, body)
        )
    return "\n".join(chunks)


# -------------------------------------------------------------------- render

def replace_region(page: str, marker: str, body: str, block: bool) -> str:
    opening, closing = "<!--%s-->" % marker, "<!--/%s-->" % marker
    pattern = re.compile(re.escape(opening) + ".*?" + re.escape(closing), re.S)
    if not pattern.search(page):
        raise SystemExit("marker %s missing from %s" % (marker, PAGE.name))
    filling = ("\n%s\n" % body) if (block and body) else body
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

    # Diff against the previous run before the snapshot is overwritten.
    previous = []
    if SNAPSHOT.exists():
        previous = json.loads(SNAPSHOT.read_text(encoding="utf-8")).get("members", [])

    posts = []
    if NEWS.exists():
        posts = json.loads(NEWS.read_text(encoding="utf-8")).get("posts", [])

    if previous:
        events = detect_events(previous, members)
        lines = compose_post(events, config)
        if lines:
            posts.insert(
                0,
                {
                    "date": datetime.now(timezone.utc).strftime("%m/%d/%Y"),
                    "lines": lines,
                },
            )
            posts = posts[:KEEP_POSTS]
            NEWS.write_text(
                json.dumps({"posts": posts}, indent=2) + "\n", encoding="utf-8"
            )
            print("wrote a news post with %d item(s)" % len(lines))
    else:
        print("no previous snapshot - skipping news this run")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = replace_region(page, "ROSTER_ROWS", build_rows(members, config), True)
    page = replace_region(page, "ROSTER_STATS", build_stats(members, config), True)
    page = replace_region(page, "ROSTER_COUNT", str(len(members)), False)
    page = replace_region(page, "ROSTER_SYNC", html.escape(stamp), False)
    page = replace_region(page, "AUTO_NEWS", render_news(posts), True)

    SNAPSHOT.write_text(
        json.dumps({"fetched": stamp, "members": members}, indent=2) + "\n",
        encoding="utf-8",
    )

    unknown = sorted({m["name"] for m in members} - set(config.get("notes", {})))
    if unknown:
        print("no note yet for: %s" % ", ".join(unknown))

    if page == before:
        print("nothing changed (%d members)" % len(members))
        return 0

    PAGE.write_text(page, encoding="utf-8")
    print("page updated (%d members)" % len(members))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
