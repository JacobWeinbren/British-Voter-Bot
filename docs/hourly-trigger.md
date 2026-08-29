# The hourly trigger

The bot posts at 10:00, 13:00, 17:00 and 21:00 UK time. Nothing inside GitHub decides when to
check any more: a Cloudflare Worker in [trigger/](../trigger) runs on the hour and asks GitHub to
run `.github/workflows/post.yml`, which then makes its own mind up with `python -m voterbot due`.

## Why the clock moved off GitHub

GitHub's cron delivered this workflow perfectly for three days and then stopped.

| Day | Ticks asked for | Runs delivered | Cards posted |
|---|---|---|---|
| 23-25 Aug | 8 a day | 8, 8, 8 | 4, 4, 4 |
| 26 Aug | 8 | 7, the last two hours late | 3 |
| 27 Aug | 8 | 0 | 1, by hand |
| 28 Aug | 48 | 2 | 3, two by hand |
| 29 Aug | 48, then 16 | 1 | 2, both by hand |

Nothing in the repository accounted for it. The cron was valid and GitHub had accepted it; the
workflow's state was `active`; the `post-card` concurrency group had been in place since 22 August,
through the days that worked; `main` is the default branch; the repository is public, so Actions
minutes are unmetered; and githubstatus.com reported no incident.

What the numbers do show is that asking for more ticks delivered fewer runs. A scheduled run that
is still pending when the next tick comes due is dropped, and GitHub's delay here had grown from 20
minutes to over two hours. Once the delay is longer than the gap between ticks, nearly every tick is
superseded before it runs - so moving from 8 a day to 48 a day made it worse, and the hourly cron
that replaced it went 0 for 4.

Cloudflare's cron triggers are not best effort in the same way, so the schedule lives there.

## How it fits together

    Cloudflare cron (hourly, 08:00-23:00 UTC)
      -> POST /repos/:owner/:repo/actions/workflows/post.yml/dispatches
        -> the `slot` job runs `python -m voterbot due`
          -> not due  : exit 3, nothing happens, a few seconds of runner time
          -> due      : the `post` job renders the next card and posts it

The Worker deliberately knows nothing about slots or posting times. Deciding stays in one place -
`voterbot/schedule.py` - so a trigger that fires twice, fires late, or fires when the slot is
already filled cannot put a second card on the feed. That is also why the trigger can be blunt: one
call an hour, every hour of the window, whether or not a card is expected.

`due` weighs two things. The ledger (`outputs/last_post.txt`, committed after each post) says when
the last card went out; the Bluesky feed says what is actually up. When they disagree - the card
posted but the queue position never pushed - the feed wins, the card is not posted twice, and the
ledger is repaired and committed on the spot.

## Running it

Deploy or redeploy the trigger:

    cd trigger && npx wrangler deploy

Set the GitHub token it authenticates with (interactive; the value is never passed on a command
line). It needs one permission: **Actions: Read and write**, on this repository only.

    cd trigger && npx wrangler secret put GITHUB_TOKEN

Watch it fire:

    cd trigger && npx wrangler tail

Post a card out of turn, ignoring the slot: run the workflow from the Actions tab with **force**
ticked. Left unticked, a manual run behaves exactly like an hourly one.
