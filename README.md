# &lt;Group of workers&gt;

The guild homepage, as it would have looked in 2004.

Live at **https://spoeket.github.io/group-of-workers/**

## How the roster stays current

`.github/workflows/roster.yml` runs once a day, fetches the guild's armory page
and rewrites only the regions of `index.html` marked with `<!--ROSTER_*-->`
comments. Everything else on the page is left alone.

It refuses to write anything if the armory can't be reached or if no members
can be parsed, so a bad day at the armory can't blank the roster.

Run it by hand from the Actions tab ("Update roster" -> "Run workflow"), or
locally:

```
python3 scripts/update_roster.py
```

## Editing

| What | Where |
| --- | --- |
| Everything on the page | `index.html` |
| The joke note after each member's name | `roster-notes.json` |
| Rank names (Middle Mgmt, Worker, Intern) | `roster-notes.json` |
| Levels, classes, who's in the guild | nothing — the armory decides |

New members get the `default_note` from `roster-notes.json` until you write
them one. The script prints the names it has no note for.

`roster-data.json` is the last armory snapshot, written by the job.
