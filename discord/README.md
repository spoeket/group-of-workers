# The Discord server

Everything needed to stand up **\<Group of workers\>** on Discord, in the order
you'd actually do it. Twenty minutes, most of it pasting.

| File | What it is |
| --- | --- |
| `server.json` | The whole server as data — roles, categories, channels, topics |
| `setup_server.py` | Builds what's in `server.json`. Creates only, never deletes |
| `copy.md` | The three posts to paste, plus the two settings screens |
| `new_raid.py` | Creates a Raid-Helper signup event, by hand or from the Monday cron |
| `raid.json` | Channel ids and defaults for `new_raid.py` |
| `last-posted.json` | Written by the news job. Don't edit |

## 1. Make the server

Discord → **+** → *Create My Own* → *For me and my friends*.

- **Name:** `<Group of workers>` — angle brackets included, they survive.
- **Icon:** the guild crest from the homepage, or anything with a tabard on it.
- Server Settings → Overview → **Description:** `Ingen guild, bara en grupp. Horde, PvP. Mondays 19:30.`

## 2. Build the channels and roles

Either by hand from the table below, or let the script do it.

**By script.** Make a bot at <https://discord.com/developers/applications> →
*New Application* → *Bot* → *Reset Token*. Invite it by opening this, with the
application's Client ID pasted in:

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=8
```

`permissions=8` is Administrator. Manage Roles and Manage Channels are enough to
create everything, with one catch: a bot can never grant a permission it doesn't
hold itself, so a less privileged bot can't give the Guild Master role its admin
rights or Middle Management its moderator rights. The script handles that — it
makes those roles without permissions and tells you to tick the boxes yourself —
but giving the bot Administrator for one run is simpler. Kick it afterwards; the
roles and channels stay.

Then, in fish:

```fish
set -x DISCORD_BOT_TOKEN "your-bot-token"
set -x DISCORD_GUILD_ID "your-server-id"
python3 discord/setup_server.py --dry-run
```

```fish
python3 discord/setup_server.py
```

Server id: Settings → Advanced → Developer Mode on, then right-click the server
→ *Copy Server ID*. The run is safe to repeat — anything already there by name
is left alone, so you can edit `server.json` and run it again to add what's new.

Two things the script leaves to you: dragging the rank roles into order (Guild
Master at the top, Rank 5 at the bottom, Rank 4 wherever), and pasting the posts.

**The structure it builds — eight channels, on purpose:**

| Channel | What goes in it |
| --- | --- |
| **HQ** | |
| `#onboarding` | One pinned post: welcome, the rules, how the week works. Read-only |
| `#water-cooler` | Guild chat. Memes, alts, dings, screenshots, loot opinions — all of it |
| `#all-hands` | Announcements, and the homepage's news. Read-only |
| **OPERATIONS** | |
| `#monday-standup` | 19:30 Mondays. One post a week, react if you're coming |
| `#offsites` | Dungeon runs that aren't Monday. Instance, time, who's short of what |
| `#internal-tools` | Addons, macros, keybinds. The channel you search six weeks later |
| **MEETING ROOMS** | |
| `Open Office` | Voice. Join when you log in, leave it running |
| `Meeting Room 2` | Voice. For when a group splits, or someone takes a call |

Eight is the point. A channel nobody can describe the purpose of is a channel
that stays empty and makes the server look dead, so everything that doesn't have
an obvious job lives in `#water-cooler` until there's genuinely too much of it to
fit. *Then* split it out — that's the signal to add a channel, not a hunch.

Ranks mirror the armory so Discord and the homepage agree: Guild Master, Rank 1
(Middle Mgmt), Rank 2 (Senior Worker), Rank 3 (Worker), Rank 4 (does not exist,
assign to nobody), Rank 5 (Intern). Plus Tank/Healer/DPS, which are pingable and
earn their keep every Monday, one role per class because coloured names in the
member list are the cheapest good thing on a WoW server, and an opt-in
`@Gaming Monday`.

*Open Office* is the one that matters. A voice channel somebody is always sitting
in does more for a server than any number of text channels.

## 3. Emoji

Server Settings → Emoji. Only `:tank:` `:healer:` `:dps:` actually matter — they
carry the Monday post. `:ding:` and `:forthehorde:` are nice to have.

## 4. Paste the posts

Open `copy.md` and work down it. It's three posts: `#onboarding`,
`#monday-standup`, `#offsites`. Pin each one.

Then the two settings screens, also in `copy.md`:

- Server Settings → **Onboarding** — three questions that assign class, dungeon
  role and the Monday ping, so nobody has to hunt for a reaction post.
- Server Settings → **Safety Setup** → *Rules Screening* — five lines.

## 5. Raid-Helper, and the Monday signup

**Raid-Helper** (<https://raid-helper.dev>) is the one bot worth having: proper
signup slots with tank/healer/dps counts, and a reminder before the time.

Invite it, then run `/apikey` in your server. That gives you a key for *that
server* — it's a secret, so it goes in the environment and in GitHub secrets,
never in a file in this repo.

Its own recurring events are a premium feature, so the weekly one is a cron here
instead. `.github/workflows/monday-standup.yml` runs every Monday morning and
puts up a signup for that evening.

To turn it on:

1. Fill in the channel ids in `discord/raid.json` — Developer Mode on,
   right-click `#monday-standup` and `#offsites`, *Copy Channel ID*. Commit them;
   channel ids aren't secret.
2. Add two repository secrets on GitHub (Settings → Secrets and variables →
   Actions): `RAID_HELPER_API_KEY` and `DISCORD_GUILD_ID`.
3. Actions tab → *Monday standup* → *Run workflow*, to see one go up now.

Without those secrets the job runs and skips, so nothing breaks in the meantime.

### Making one any time

Same script, from your own machine:

```fish
set -x RAID_HELPER_API_KEY (string trim < ~/.raid-helper-key)
set -x DISCORD_GUILD_ID "your-server-id"
```

```bash
python3 discord/new_raid.py --title SFK --date 2026-11-19 --time 19:30
```

Other ways to say when: `--monday` for the next Monday at the usual time,
`--in 2` for two days from now, nothing at all for tonight (or tomorrow, if
tonight's time has already gone past). `--channel monday` or `--channel offsites`
picks where it lands, defaulting to `#offsites`; a raw channel id works too.
`--dry-run` prints the request without sending it, and needs no key.

Times are Europe/Stockholm and handle summer time by themselves. The event is
sent as a unix timestamp, so Raid-Helper's own date-format setting can't
misread it.

Defaults — the time, the Monday title and description, and optionally a
`templateId` and `leaderId` — live in `discord/raid.json`. The description uses
Raid-Helper's `{Gaming Monday}` shortcode, which turns a role name into a real
mention when the event posts.

Skip levelling bots, economy bots and anything that keeps a leaderboard.

## 6. The homepage feeds itself in

The daily job that rebuilds the guild homepage drops the same news in
`#all-hands`. Dings, new members, promotions, leavers — one message a day, in the
Guild Master's name, only when something actually happened.

1. In Discord: `#all-hands` → Edit Channel → Integrations → **Create Webhook**.
   Name it `Business Manadin`, copy the URL.
2. On GitHub: repo → Settings → Secrets and variables → Actions → **New repository
   secret**, named `DISCORD_WEBHOOK_URL`, pasted in.

That's it — `.github/workflows/roster.yml` already calls
`scripts/post_news_to_discord.py`, which does nothing at all until that secret
exists, and never fails the job if Discord is down. Test it from the Actions tab:
*Update site* → *Run workflow*.

To try it locally first:

```fish
set -x DISCORD_WEBHOOK_URL "https://discord.com/api/webhooks/..."
python3 scripts/post_news_to_discord.py
```

## 7. Invite everyone

Make an invite that doesn't expire: right-click the server → *Invite People* →
*Edit invite link* → **Never**, max uses unlimited. The blurb for the Slack group
is at the bottom of `copy.md`.
