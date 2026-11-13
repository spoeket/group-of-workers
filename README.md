# &lt;Group of workers&gt;

The guild homepage, as it would have looked in 2004.

Live at **https://spoeket.github.io/group-of-workers/**

## How the site keeps itself current

`.github/workflows/roster.yml` runs once a day, fetches the guild's armory page
and rewrites only the regions of `index.html` marked with `<!--ROSTER_*-->` and
`<!--AUTO_NEWS-->` comments. Everything else on the page is left alone.

**The roster** — table, member count, and the Paladins/Priests lines in the
sidebar — is rebuilt from the armory every run.

**The news** — each run compares the armory against the last snapshot and, if
anything happened, adds one post in the Guild Master's voice covering dings,
new members, promotions and leavers. One post per run, so a busy week can't
flood the page. The last 10 posts are kept, in `news-auto.json`.

It refuses to write anything if the armory can't be reached or if no members
can be parsed, so a bad day at the armory can neither blank the roster nor
invent news.

Run it by hand from the Actions tab ("Update site" -> "Run workflow"), or
locally:

```
python3 scripts/update_site.py
```

## Discord

`discord/` holds the server: the structure as data, a script that builds it, and
every post to paste in. Start at [discord/README.md](discord/README.md).

Once `DISCORD_WEBHOOK_URL` is set as a repository secret, the daily job also
posts each news item to Discord. Without the secret it skips that step silently.

A second workflow, `.github/workflows/monday-standup.yml`, puts up the weekly
Raid-Helper signup every Monday morning. It needs `RAID_HELPER_API_KEY` and
`DISCORD_GUILD_ID` as secrets, and skips without them.

## Editing

| What | Where |
| --- | --- |
| Everything hand-written on the page | `index.html` |
| The joke note after each member's name | `roster-notes.json` |
| Rank names (Middle Mgmt, Worker, Intern) | `roster-notes.json` |
| How dings, welcomes and goodbyes are phrased | the word pools in `scripts/update_site.py` |
| Levels, classes, who's in the guild | nothing — the armory decides |

New members get the `default_note` from `roster-notes.json` until you write
them one. The script prints the names it has no note for.

Each phrasing is picked by a hash of the member and level, not at random, so
re-running never reshuffles wording that has already been published.

`roster-data.json` is the last armory snapshot and `news-auto.json` the stored
posts. Both are written by the job — edit them only to undo something.
