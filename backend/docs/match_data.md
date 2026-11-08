# Collect your matches

This backend collects the data needed to start analyzing your own matches. It does
not calculate scores, trends, recommendations or predictions yet. Routing remains
`europe`, matching the existing Riot client (including EUW and EUNE).

## Start the backend

From the project root:

```bash
docker compose up -d db
cd backend
source .venv/bin/activate
```

If setting up a fresh checkout, create the virtual environment first with
`python3 -m venv .venv`, activate it, and run `pip install -r requirements.txt`.
Create `backend/.env` from `backend/.env.example` if it does not already exist,
then enter your Riot key. Keep your existing `.env` when upgrading.

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs>. The migration adds `matches` and
`match_participants`; existing players are preserved.

## Import a first batch

Use **POST** `/api/players/{game_name}/{tag_line}/matches/sync` in Swagger, or:

```bash
curl -X POST 'http://127.0.0.1:8000/api/players/jonnybravo/1998/matches/sync?count=10'
```

This refreshes the player's account, fetches a page of match IDs, and saves each
match with all participants and its timeline. Default: 10 matches, `start=0`,
all queues, `include_timeline=true`. Match IDs alone are not a stored dataset.
The older **GET** `/api/players/{game_name}/{tag_line}/matches` still returns
only the latest 10 IDs from Riot for backwards compatibility.

Sync options:

| Parameter | Meaning |
| --- | --- |
| `count` | Matches per Riot page, 1–100. Start with 10. |
| `start` | Offset into Riot history, starting at 0. |
| `queue` | Optional queue ID; for example 420 for ranked solo/duo. |
| `include_timeline` | Store event/frame data too; defaults to true. |

The result includes `imported`, `already_stored`, `timelines_added`, `found`,
`completed`, `next_start`, `failures`, and `retry_after`.

- If `completed=true`, use `next_start` for the next page with the same filters.
  Stop when `found=0` (or fewer than `count` matches were found).
- If `completed=false`, earlier matches have already been committed. Inspect
  `failures`. For a rate limit, wait for `retry_after` seconds, then retry at
  `next_start`. There is no automatic background retry or long-running job.
- A batch response can be HTTP 200 with `completed=false`: always inspect the body.
  Failure fetching the account/history page instead uses the global HTTP error
  handler (503 for rate limiting, with Retry-After when Riot provides it).
- A permanently unavailable match (for example HTTP 404) requires explicitly
  skipping that history offset by increasing `start` by one. Do not silently
  treat a failed page as a complete dataset.
- A match and all its participants are committed together. If its requested
  timeline cannot be fetched, that match is not partially imported. You can
  retry with `include_timeline=false`, then add the timeline later.
- Repeating a sync does not duplicate matches or participants. Already stored
  details/timelines are reused. A later sync with `include_timeline=true` fills
  missing timelines without downloading the details again.

New matches shift Riot's offset-based history. Start at 0 when refreshing your
newest matches; stored match IDs make repeated imports safe. Riot history is
not guaranteed to contain every match you have ever played. Sync periodically
to build your own persistent dataset.

For one known match:

```bash
curl -X POST 'http://127.0.0.1:8000/api/matches/EUW1_1234567890/sync'
```

Replace that example ID with a real ID. The local match endpoints expect the
format `EUW1_1234567890` (a platform prefix, underscore, numeric game ID).

## Read or export the dataset

These GET endpoints read PostgreSQL only and do not contact Riot:

| Endpoint | Result |
| --- | --- |
| `/api/players/{name}/{tag}/matches/stored` | Flat rows for that player with match metadata and participant stats. |
| `/api/players/{name}/{tag}/matches/export` | The same rows as a CSV download. |
| `/api/matches/{match_id}` | Match metadata and all participants' normalized stats. |
| `/api/matches/{match_id}/raw` | Original full match JSON from Riot. |
| `/api/matches/{match_id}/timeline` | Original full timeline JSON from Riot. |

Stored/export endpoints accept `start`, `count` (1–1000), and optional `queue`.
Rows are ordered by game start, newest first, then match ID for stable ordering.
The JSON page includes `total` so you can iterate through the complete local
dataset. CSV exports **one page**, default 1000 rows; use `start=1000`, etc. if
you have more. CSV files include a header even when there are no rows.
Lists such as `items` are JSON strings inside CSV cells. Strings that could be
interpreted as spreadsheet formulas are prefixed with an apostrophe in CSV.

```bash
curl 'http://127.0.0.1:8000/api/players/jonnybravo/1998/matches/stored?queue=420&count=100'
curl --fail 'http://127.0.0.1:8000/api/players/jonnybravo/1998/matches/export?count=1000' -o matches.csv
```

The flat dataset includes match ID, queue, map, patch/version, UTC start time,
duration in seconds, champion, position, team, outcome, K/D/A, level, gold,
lane/jungle CS separately, damage, vision, wards, items, spells, time played,
early-surrender flag and timeline availability. Unknown optional fields are
`null`, rather than invented zeroes. Zero deaths remains zero; no KDA ratio is
calculated. Duration from pre-11.20 matches is normalized to seconds.

An unknown stored player/match returns 404. Players are looked up locally by
case-insensitive Riot ID. If your Riot ID changes, sync with the new ID first;
your PUUID links the existing match history. Reading historical matches never
overwrites the current account name with an old name from a match.

## Database layout

- `players`: searched accounts, identified by PUUID. `last_updated` is refreshed
  when the account is fetched from Riot, not when its matches are merely read.
- `matches`: one row per Riot match ID, metadata, `raw_data` JSONB and optional
  `timeline_data` JSONB. `fetched_at` records when details were first stored.
- `match_participants`: one row per `(match_id, participant_id)` with statistics
  and the original participant JSONB. An index on PUUID supports player history.
  Participants do not require an account row in `players`; opponents are stored
  without making extra account requests.

All source fields are preserved: perks, challenges, objectives, team bans and
other match fields are accessible through raw JSON even when they do not have
dedicated SQL columns. Timeline frames/events retain Riot's timestamps. Use those
timestamps when analyzing events; do not assume frames are exactly a minute apart.
Rank/LP history is not part of match-v5 and is not collected in this step.

From the project root, open SQL:

```bash
docker compose exec db psql -U riftanalyzer -d riftanalyzer
```

```sql
\pset pager off
SELECT count(*) FROM matches;
SELECT count(*) FROM match_participants;

SELECT m.match_id, m.game_start, m.game_version, m.queue_id,
       m.duration_seconds, p.champion_name, p.team_position,
       p.win, p.kills, p.deaths, p.assists, p.total_minions_killed,
       p.neutral_minions_killed, p.gold_earned, p.vision_score
FROM matches AS m
JOIN match_participants AS p USING (match_id)
JOIN players AS account ON account.puuid = p.puuid
WHERE lower(account.game_name) = lower('jonnybravo')
  AND lower(account.tag_line) = lower('1998')
ORDER BY m.game_start DESC;
```

## Tests

From `backend`, with the virtual environment active:

```bash
python -m pytest -q
```

Automated tests use an isolated SQLite database and a simulated Riot client, so
they do not consume your API quota or write to your development database.
`pytest.ini` selects `tests/unit`; the older `tests/test_client.py`,
`test_db.py` and `test_player_repository.py` are manual smoke scripts that make
real external calls and are deliberately not collected by the default command.

To exercise the same tests on PostgreSQL, set `TEST_DATABASE_URL` to a **dedicated,
disposable** database whose name begins with `riftanalyzer_test_`. The fixture
creates and drops its application tables for each test. Never use your development
database for that setting. Alembic should also be verified against a disposable
PostgreSQL database before changing an existing deployment.

API reference: <https://developer.riotgames.com/apis#match-v5>.
