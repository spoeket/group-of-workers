#!/usr/bin/env python3
"""Build the Discord server described in discord/server.json.

Needs a bot that is already in the server, with Manage Roles and Manage
Channels, and whose own role sits above the roles it is asked to create.

    export DISCORD_BOT_TOKEN=...      # bash. fish: set -x DISCORD_BOT_TOKEN ...
    export DISCORD_GUILD_ID=...
    python3 discord/setup_server.py --dry-run
    python3 discord/setup_server.py

It only ever creates. Roles and channels that already exist by name are left
exactly as they are, so a second run is a no-op and nothing anyone edited by
hand in Discord gets overwritten. It never deletes.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://discord.com/api/v10"
HERE = Path(__file__).resolve().parent
PLAN = HERE / "server.json"

# Permission bits, from the Discord docs.
ADMINISTRATOR = 1 << 3
KICK_MEMBERS = 1 << 1
MANAGE_CHANNELS = 1 << 4
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
MANAGE_MESSAGES = 1 << 13
ADD_REACTIONS = 1 << 6
MUTE_MEMBERS = 1 << 22
MOVE_MEMBERS = 1 << 24
CREATE_PUBLIC_THREADS = 1 << 35
SEND_MESSAGES_IN_THREADS = 1 << 38

MODERATOR = (
    KICK_MEMBERS | MANAGE_CHANNELS | MANAGE_MESSAGES | MUTE_MEMBERS | MOVE_MEMBERS
)
READONLY_DENY = SEND_MESSAGES | CREATE_PUBLIC_THREADS | SEND_MESSAGES_IN_THREADS

CHANNEL_TYPE = {"text": 0, "voice": 2, "category": 4, "forum": 15}

dry_run = "--dry-run" in sys.argv


def request(
    method: str, path: str, body: dict | None = None, soft: bool = False
) -> dict | list | None:
    """One API call, with a single retry when Discord asks us to slow down.

    With soft=True a "missing permissions" refusal returns None instead of
    stopping the run, so the caller can try something less ambitious.
    """
    token = os.environ["DISCORD_BOT_TOKEN"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bot " + token,
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (group-of-workers, 1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        if error.code == 403 and soft:
            return None
        if error.code == 429:
            detail = json.loads(error.read() or b"{}")
            wait = float(detail.get("retry_after", 2)) + 0.5
            print("  rate limited, waiting %.1fs" % wait)
            time.sleep(wait)
            return request(method, path, body, soft)
        raise SystemExit(
            "%s %s failed: %s %s" % (method, path, error.code, error.read().decode())
        )


def colour(value: str | None) -> int:
    return int(value.lstrip("#"), 16) if value else 0


def main() -> int:
    for name in ("DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID"):
        if not dry_run and not os.environ.get(name):
            raise SystemExit("%s is not set. See discord/README.md." % name)

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    guild = os.environ.get("DISCORD_GUILD_ID", "0")

    if dry_run:
        existing_roles, existing_channels = {}, {}
        print("DRY RUN - nothing will be created\n")
    else:
        existing_roles = {r["name"]: r["id"] for r in request("GET", f"/guilds/{guild}/roles")}
        existing_channels = {
            c["name"].lower(): c["id"] for c in request("GET", f"/guilds/{guild}/channels")
        }

    # ------------------------------------------------------------- roles
    roles: dict[str, str] = dict(existing_roles)
    for spec in plan["roles"]:
        name = spec["name"]
        if name in roles:
            print("role exists, left alone:", name)
            continue
        permissions = 0
        if spec.get("admin"):
            permissions = ADMINISTRATOR
        elif spec.get("moderator"):
            permissions = MODERATOR
        body = {
            "name": name,
            "color": colour(spec.get("color")),
            "hoist": bool(spec.get("hoist")),
            "mentionable": bool(spec.get("mentionable", spec.get("self_assign", False))),
            "permissions": str(permissions),
        }
        if dry_run:
            print("would create role:", name)
            continue
        created = request("POST", f"/guilds/{guild}/roles", body, soft=permissions != 0)
        if created is None:
            # A bot can only grant permissions it holds itself. Rather than
            # stopping, make the role without them and say so - the colour and
            # the name are the point, and you can tick the boxes by hand.
            body["permissions"] = "0"
            created = request("POST", f"/guilds/{guild}/roles", body)
            print("created role (without permissions - set them by hand):", name)
        else:
            print("created role:", name)
        roles[name] = created["id"]

    # ---------------------------------------------------------- channels
    for category in plan["categories"]:
        parent_name = category["name"]
        parent_id = existing_channels.get(parent_name.lower())
        if parent_id:
            print("category exists, left alone:", parent_name)
        elif dry_run:
            print("would create category:", parent_name)
            parent_id = None
        else:
            parent_id = request(
                "POST",
                f"/guilds/{guild}/channels",
                {"name": parent_name, "type": CHANNEL_TYPE["category"]},
            )["id"]
            existing_channels[parent_name.lower()] = parent_id
            print("created category:", parent_name)

        for channel in category["channels"]:
            name = channel["name"]
            # Discord lowercases and hyphenates text channel names itself.
            key = name.lower() if channel["type"] == "voice" else name.lower().replace(" ", "-")
            if key in existing_channels:
                print("  channel exists, left alone:", name)
                continue
            body: dict = {"name": name, "type": CHANNEL_TYPE[channel["type"]]}
            if parent_id:
                body["parent_id"] = parent_id
            if channel.get("topic") and channel["type"] != "voice":
                body["topic"] = channel["topic"]
            if channel.get("readonly"):
                # @everyone can read and react, but not post. The guild id is
                # also the id of the @everyone role.
                body["permission_overwrites"] = [
                    {
                        "id": guild,
                        "type": 0,
                        "allow": str(VIEW_CHANNEL | ADD_REACTIONS),
                        "deny": str(READONLY_DENY),
                    }
                ]
            if dry_run:
                print("  would create %s channel: %s%s" % (
                    channel["type"], name, " (read-only)" if channel.get("readonly") else ""))
                continue
            created = request("POST", f"/guilds/{guild}/channels", body)
            existing_channels[key] = created["id"]
            print("  created %s channel: %s" % (channel["type"], name))

    print("\nDone.")
    print("Still to do by hand, because the API cannot or should not:")
    print("  - drag the rank roles into order (Guild Master at the top)")
    print("  - upload the emoji in emoji_wishlist")
    print("  - paste the posts from discord/copy.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
