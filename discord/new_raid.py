#!/usr/bin/env python3
"""Create a Raid-Helper signup event.

Raid-Helper's own recurring events are a premium feature, so the Monday one is
made by a GitHub Actions cron calling this script - see .github/workflows/
monday-standup.yml. The same script makes a one-off event any time you want one.

    # next Monday at the usual time, in #monday-standup
    python3 discord/new_raid.py --monday

    # anything else
    python3 discord/new_raid.py --title SFK --date 2026-11-19 --time 19:30
    python3 discord/new_raid.py --title BFD --in 2 --channel offsites

Needs two things in the environment:

    RAID_HELPER_API_KEY   run /apikey in your Discord server to get it
    DISCORD_GUILD_ID      the server id

Everything else lives in discord/raid.json. --dry-run prints the request
without sending it and needs no key.

API: https://raid-helper.xyz/documentation/api
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://raid-helper.xyz/api/v4"
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "raid.json"


def ssl_context() -> ssl.SSLContext:
    """Verified context. Falls back to certifi where the platform has no bundle."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def env_value(name: str) -> str:
    """One environment variable, trimmed - a pasted key often brings a newline."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            "%s is not set. See the Raid-Helper section of discord/README.md." % name
        )
    if any(character.isspace() for character in value):
        raise SystemExit("%s has a space or a line break inside it." % name)
    return value


def next_weekday(now: datetime, weekday: int, hour: int, minute: int) -> datetime:
    """The next date that falls on `weekday`, at the given time.

    Today counts only if the time has not passed yet, so a Monday-morning cron
    makes that same evening's event rather than one eight days out.
    """
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    ahead = (weekday - now.weekday()) % 7
    if ahead == 0 and candidate <= now:
        ahead = 7
    return candidate + timedelta(days=ahead)


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    zone = ZoneInfo(config.get("timezone", "Europe/Stockholm"))

    parser = argparse.ArgumentParser(description="Create a Raid-Helper event.")
    parser.add_argument("--title", help="Event title, e.g. SFK")
    parser.add_argument("--date", help="YYYY-MM-DD. Defaults to today")
    parser.add_argument("--time", help="HH:MM. Defaults to raid.json defaultTime")
    parser.add_argument(
        "--in", dest="days", type=int, metavar="N", help="N days from today"
    )
    parser.add_argument("--monday", action="store_true", help="The next Monday")
    parser.add_argument("--channel", help="A key from raid.json channels, or a raw id")
    parser.add_argument("--description", help="Overrides the default description")
    parser.add_argument("--dry-run", action="store_true", help="Print, do not send")
    args = parser.parse_args()

    hour, minute = (int(part) for part in config.get("defaultTime", "19:30").split(":"))
    if args.time:
        hour, minute = (int(part) for part in args.time.split(":"))

    now = datetime.now(zone)
    if args.monday:
        start = next_weekday(now, 0, hour, minute)
    elif args.date:
        day = datetime.strptime(args.date, "%Y-%m-%d")
        start = day.replace(hour=hour, minute=minute, tzinfo=zone)
    elif args.days is not None:
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        start += timedelta(days=args.days)
    else:
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start <= now:
            start += timedelta(days=1)

    channel_key = args.channel or (
        "monday" if args.monday else config.get("defaultChannel", "offsites")
    )
    channel = config.get("channels", {}).get(channel_key, channel_key)
    if not channel or not channel.isdigit():
        raise SystemExit(
            "No channel id for '%s'. Fill in discord/raid.json channels, or pass "
            "--channel with a raw channel id." % channel_key
        )

    defaults = config.get("monday", {}) if args.monday else {}
    title = args.title or defaults.get("title") or "Dungeon"
    description = args.description or defaults.get("description", "")

    # A unix timestamp sidesteps the server's date-format setting entirely.
    stamp = str(int(start.timestamp()))
    body = {"title": title, "date": stamp, "time": stamp}
    if description:
        body["description"] = description
    for key in ("templateId", "leaderId"):
        if config.get(key):
            body[key] = config[key]

    when = start.strftime("%a %d %b %Y at %H:%M")
    if args.dry_run:
        print("Would create in channel %s:\n  %s - %s" % (channel, title, when))
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 0

    guild = env_value("DISCORD_GUILD_ID")
    request = urllib.request.Request(
        "%s/servers/%s/channels/%s/event" % (API, guild, channel),
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": env_value("RAID_HELPER_API_KEY"),
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as r:
            answer = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as error:
        print(
            "Raid-Helper said %s: %s" % (error.code, error.read().decode()),
            file=sys.stderr,
        )
        return 1

    print("Created '%s' for %s." % (title, when))
    if isinstance(answer, dict) and answer.get("eventId"):
        print("Event id:", answer["eventId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
