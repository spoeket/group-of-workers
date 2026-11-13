# The Discord server

Everything needed to stand up **\<Group of workers\>** on Discord, in the order
you'd actually do it. Budget about 30 minutes, most of it pasting.

| File | What it is |
| --- | --- |
| `server.json` | The whole server as data — roles, categories, channels, topics |
| `setup_server.py` | Builds what's in `server.json`. Creates only, never deletes |
| `copy.md` | Every post to paste in: handbook, welcome, org chart, templates |
| `last-posted.json` | Written by the news job. Don't edit |

## 1. Make the server

Discord → **+** → *Create My Own* → *For me and my friends*.

- **Name:** `<Group of workers>` — angle brackets included, they survive.
- **Icon:** the guild crest from the homepage, or anything with a tabard on it.
- Server Settings → Overview → **Description:** `Ingen guild, bara en grupp.`

## 2. Build the channels and roles

Either by hand from the table below, or let the script do it.

**By script.** Make a bot at <https://discord.com/developers/applications> →
*New Application* → *Bot* → *Reset Token*. Invite it with the OAuth2 URL
generator, scope `bot`, permissions **Manage Roles** and **Manage Channels**.
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

Three things the script deliberately leaves to you: dragging the rank roles into
order (Guild Master at the top, Rank 5 at the bottom, Rank 4 wherever), uploading
the emoji, and pasting the posts.

**The structure it builds:**

| Category | Channels |
| --- | --- |
| ONBOARDING | welcome-aboard · employee-handbook · org-chart · new-hires |
| THE OFFICE | guild-chat · water-cooler · fika · hr · payroll · it-support *(forum)* |
| OPERATIONS | announcements · gaming-mondays · dungeon-bookings · looking-for-group · level-checkpoints · alt-department · overtime |
| SUPPLY CLOSET | guild-homepage · addons-and-macros · performance-reviews · corpse-runs · alliance-sightings |
| VOICE | Open Office · Meeting Room 1 · Meeting Room 2 · The Fireplace · Board Meeting · Quiet Room |

Ranks mirror the armory, so the Discord and the homepage agree: Guild Master,
Rank 1 (Middle Mgmt), Rank 2 (Senior Worker), Rank 3 (Worker), Rank 4 (does not
exist, assign to nobody), Rank 5 (Intern). On top of those: one role per class,
one per dungeon role, and a few opt-in ping roles.

*Open Office* is the one that matters. A voice channel somebody is always sitting
in does more for a server than any number of text channels.

`#overtime` is a joke about the five hours, not a log anybody has to keep, and
`#alt-department` is where the levelling actually goes on now. Neither needs
maintaining.

## 3. Emoji

Server Settings → Emoji. The reaction posts in `copy.md` assume these exist:

`:tank:` `:healer:` `:dps:` — the three that get used daily, for dungeon signups.
`:ding:` `:ninja:` `:forthehorde:` `:nopaladins:` `:priestpls:` `:fivehours:` — the rest.

Class icons come free: Discord's own `:warrior:`-style emoji don't exist, so grab
the class crests from wowpedia, or skip them and use letters.

## 4. Paste the posts

Open `copy.md` and work down it. Pin each one after posting.

1. `#welcome-aboard` — the welcome post
2. `#employee-handbook` — the rules
3. `#org-chart` — the reaction-role post
4. `#new-hires` — the template, pinned
5. `#gaming-mondays` — the weekly post, pinned as an example

## 5. Bots

Two, and no more. Every bot is a thing that can break on a Monday.

- **Raid-Helper** (<https://raid-helper.dev>) — dungeon signups with tank/healer/dps
  slots and a reminder before the time. Set the default to 19:30, Europe/Stockholm.
  `/quickcreate` in `#gaming-mondays` once a week and that's the whole job.
- **Carl-bot** (<https://carl.gg>) — reaction roles for `#org-chart`, and a welcome
  message in `#new-hires`. Set its welcome to:
  > {user} has been onboarded. No interview was conducted.

Skip levelling bots, economy bots and anything that keeps a leaderboard.

## 6. Onboarding

Server Settings → **Onboarding**. The questions are in `copy.md` and assign the
same class and role tags as `#org-chart`, so new people arrive already sorted.

Also turn on Server Settings → **Safety Setup** → *Rules Screening* and paste the
five-line version from `copy.md`. It's the only thing anyone reads.

## 7. The homepage feeds itself in

The daily job that rebuilds the guild homepage can drop the same news in
`#guild-homepage`. Dings, new members, promotions, leavers — one message a day,
in the Guild Master's name, only when something actually happened.

1. In Discord: `#guild-homepage` → Edit Channel → Integrations → **Create Webhook**.
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

## 8. Invite everyone

Make an invite that doesn't expire: right-click the server → *Invite People* →
*Edit invite link* → **Never**, max uses unlimited. The blurb for the Slack group
is at the bottom of `copy.md`.

---

**Keep it small.** The channel list above is already more than eight people need.
If a channel has been quiet for a month, delete it — nothing on this list is load
bearing except `#guild-chat`, `#gaming-mondays` and Open Office.
