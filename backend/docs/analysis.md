# Personal match analysis, version 2

The first analysis stage computes reproducible match features and exploratory
associations. It reads your existing PostgreSQL data only. It makes no Riot or
LLM calls, writes no database rows, and requires no new migration.

Install the updated dependencies from `backend` with the virtual environment
active, then restart Uvicorn (or let `--reload` reload it):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Usage

First collect ranked solo/duo matches **with timelines** using the existing sync:

```bash
curl -X POST 'http://127.0.0.1:8000/api/players/jonnybravo/1998/matches/sync?queue=420&count=10&include_timeline=true'
```

Check `completed` and `next_start` and continue through older pages as described
in [match collection](match_data.md). Repeating the sync fills missing timelines.
An account lookup or a list of match IDs alone is not enough for analysis.

Inspect the computed features:

```bash
curl 'http://127.0.0.1:8000/api/players/jonnybravo/1998/analysis/features'
```

Request the structured report:

```bash
curl 'http://127.0.0.1:8000/api/players/jonnybravo/1998/analysis?position=MIDDLE&patch=16.22&limit=200'
```

Both endpoints also appear under **Analysis** in `/docs`. Optional parameters:

| Parameter | Meaning |
| --- | --- |
| `limit` | Most recent matching stored games; default 200, maximum 500. |
| `position` | TOP, JUNGLE, MIDDLE, BOTTOM or UTILITY. |
| `patch` | Major/minor version, such as `16.22`. |

Only queue 420 on Summoner's Rift (map 11) is considered. Matches are ordered by
game start and match ID, newest first. Filters apply **before** the limit.
`matched_total`, `selected_matches` and `truncated` expose the sample window;
the backend never silently claims to have analyzed your entire history.

A known player with no usable matches returns HTTP 200 with an insufficient-data
report. An unknown stored account returns 404; sync that account first.

## Feature definitions

`feature_version=timeline-v2` returns one row per selected match. Each row has
checkpoint objects at minutes 10, 15 and 20, plus match ID, UTC start, champion,
role, patch and outcome. Features are computed on demand from stored source data,
so existing matches do not need to be reimported unless their timelines are absent.

For each checkpoint:

- Kills, deaths and assists count CHAMPION_KILL events whose event timestamp is
  **at or before** the cutoff, including events found in a later timeline frame.
  A death to a non-player killer (`killerId=0`) still counts as a death.
- `gold` is cumulative `totalGold`, not unspent gold. `cs` is lane minions plus
  jungle minions. `xp` is cumulative experience.
- Snapshot values use the latest participant frame **at or before** the cutoff.
  We never interpolate from later frames or use end-of-match totals. The source
  timestamp and lag are returned. Snapshots more than 90 seconds old are unknown.
- `gold_diff`, `cs_diff` and `xp_diff` subtract the opposing participant assigned
  the same Riot `teamPosition`. Ambiguous or absent roles yield null differences.
  This is a role comparison, not proof that the two players actually laned together.
- `team_gold_diff` compares total team gold when all participant values are present.
  It is exposed for future contextual analysis but is not yet an adjustment variable.

There are separate `snapshot_status` and `combat_status` fields: valid combat
events can still be available when a snapshot is stale, and vice versa. Fields
with incomplete coverage remain null, not zero. A match that ends before a
checkpoint has null values there, even if a malformed source contains later frames.

The extractor validates timeline match ID, participant-to-PUUID mapping, unique
frame timestamps and coverage from timestamp 0. Event counts require timeline
coverage through the checkpoint. Invalid combat records invalidate the combat
counts rather than silently inventing zeroes.

Remakes/early-surrender games (flagged as such or lasting under five minutes),
unknown roles, unparseable patches and missing/invalid timelines are excluded
from statistical evidence. Exclusions remain visible in the feature dataset and
are counted in the report. `eligible_matches` counts basic eligible rows;
individual comparisons can still lack checkpoint data. Exclusion-reason counts
can overlap because one match can have several reasons.

## Progression, phases and sidelanes

Each feature row now also includes:

- `windows`: 0–5, 5–10, 10–15, 15–20, 20–25, 25–30 minutes and 30–end.
- `phases`: `laning` (0–15), `midgame` (15–25), `late_game` (25–end).
- `event_followups`: the next two minutes after each of the player's kills and
  deaths, with the event timestamp, approximate event zone and source snapshots.

These are fixed, versioned comparison conventions, not detected real-world phase
transitions. Different champions, lane swaps or early towers can change how a
match is actually played. Windows can be `complete`, `partial` (the game ended
during the requested window), or `not_reached`. A partial window is not padded
with zeroes. Events belong to `(start, end]`, except timestamp 0 is included in
the first window. A boundary event is not counted in both adjacent windows.

Window/phase metrics include cumulative gold, lane CS, jungle CS and XP increases;
gold and CS per observed minute; changes in gold/CS/XP difference against the role
opponent; unspent gold at the end; K/D/A; tower and elite-monster kill
participations; plate last hits; and item purchase event counts. Purchase counts
are **not net purchases**: undo/sell events do not turn them into spending totals.
Plate last hits are **not** all recipients of shared plate gold. Objective counts
only identify participation through the killer/assist IDs in the event.

Snapshot differences use the latest valid frames at/before both boundaries, with
a maximum 90-second lag. `observed_start_ms`, `observed_end_ms` and
`observed_duration_seconds` expose the actual measured interval. Rates use that
interval, not an assumed frame frequency. A negative change in a cumulative
counter is unknown rather than silently clamped to zero. Relative advantages can
legitimately increase or decrease.

Post-kill/death windows use the same sparse-snapshot rules: the baseline can be
before the event, and the endpoint can be before the requested end. They do not
measure exact gold caused by a kill or lost due to a death. Followups can overlap
and are not independent samples; do not sum them as a gold accounting ledger.
Future prediction models must only use windows completed by their prediction
cutoff, never future followups or final-match information.

### Mid-player sidelane proxy

For `MIDDLE` players on map 11, a versioned geometric heuristic labels sampled
positions as top, bottom, middle, base, jungle/river, or unknown. It uses a band
around lane paths, excludes base areas, and treats ambiguous/invalid positions
as unknown. It is a heuristic, not an official Riot lane classifier.

Only adjacent observations wholly inside the window, at most 90 seconds apart,
are considered. Both endpoints must have valid positions. An interval contributes
to a sidelane only when **both endpoints lie in the same sidelane**. Lane
transitions are reported separately, not assigned to either side. Gold is not
proportionally split over long gaps or window boundaries.

The `sidelane` object returns observed time/coverage, top and bottom interval time,
the sidelane share of observed time, gold and lane-CS per observed sidelane minute,
and gold/lane-CS/jungle-CS increases during
those intervals. Missing positions are unknown, not "zero sidelaning". A player
observed exclusively elsewhere can have a genuine zero for observed sidelane
intervals. A gold-per-sidelane-minute rate is null if no side interval exists.

**This is not exact gold earned from sidelane minions.** Gold changes include
passive income, kills, objectives, sales or other sources reflected by Riot's
counter. Both endpoints being in a lane also cannot prove the player stayed
there throughout the interval. The API explicitly labels this as
`spatial_proxy_not_gold_source`; it makes no assumed minion-gold or patch-specific
reward calculations. Lane-CS and event counts provide source proxies alongside
gold, not an exact additive breakdown of its sources.

### Descriptive phase summaries

The report's `phase_summaries` compares phase metrics for wins and losses within
each position. These summaries **pool patches descriptively**, list those patches,
and do not contribute statistical findings or p-values. Each metric has its own
available-match count and win/loss counts. Partial and unreached phases are
counted but excluded from the means. Games reaching late game have variable phase
lengths; use the exposed duration and rates when comparing them.

Individual low-coverage sidelane measurements remain visible, but sidelane metrics
other than coverage itself require at least 80% position coverage to enter pooled
means. Reported means are means of per-match values, not time-weighted pooled
rates. A match with missing gold/CS may still contribute position coverage but
not that missing metric. There is no minimum sample-size claim for descriptive
means; a single-match mean is still only a single match.

## Statistical comparisons

`analysis_version=associations-v2` retains six fixed hypotheses **separately
for each patch and position**. There is no optimization of cutoffs against the
player's outcomes, and no pooling of different roles or patches to increase N.

| Rule | Group A | Group B |
| --- | --- | --- |
| deaths_10 | At most 1 death by 10:00 | More than 1 death |
| deaths_15 | At most 2 deaths by 15:00 | More than 2 deaths |
| gold_diff_15 | Gold difference >= 0 at 15:00 | Gold difference < 0 |
| cs_diff_10 | CS difference >= 0 at 10:00 | CS difference < 0 |
| xp_diff_15 | XP difference >= 0 at 15:00 | XP difference < 0 |
| high_kill_deaths_20 | At least 10 kills and fewer than 8 deaths by 20:00 | At least 10 kills and at least 8 deaths |

The last comparison excludes all games with fewer than 10 kills at minute 20.
Each comparison returns group labels, match IDs, match/win counts, win rates and
missing/inapplicable counts. Win rates are fractions from 0 to 1; differences
and their intervals use **percentage points**, not relative percentage changes.

Methods:

1. 95% Wilson score intervals for each group's win rate.
2. A 95% Newcombe/Wilson interval for the difference between two proportions.
3. Two-sided Fisher exact test, using SciPy, when at least 30 applicable games
   are available and each comparison group contains at least 10 games.
4. Holm correction across **all tested rules in all cohorts in the response**.
5. A finding is emitted only if the adjusted p-value is at most 0.05, the absolute
   difference is at least 10 percentage points, and the difference interval
   excludes zero. The minimum sample/effect cutoffs are conservative product
   gates, not a guarantee of reliability or statistical power.

Confidence intervals are **pointwise** 95% intervals and are not adjusted for
multiple comparisons. The p-values are multiplicity-adjusted; the two should
not be described as if they had the same simultaneous coverage guarantee.

Report statuses:

- `insufficient_data`: no comparison meets the sample-size requirements.
- `no_supported_findings`: tests were possible, but no comparison passed all gates.
- `findings_available`: at least one exploratory association passed the gates.

`comparisons` includes every evaluated rule, including withheld results.
`findings` contains only results that passed the gates, ranked by adjusted
p-value, then absolute difference, then stable finding ID. A supported finding
may have either direction; the code does not assume fewer deaths must correlate
with more wins in every sample. Its short Swedish summary is a deterministic
template generated from the counts, not LLM text.

## What the findings mean

These are exploratory associations in your stored sample, not causal claims,
validated predictions, or estimates of how many more games you would win after
changing a behavior. Champion, rank, team state and opponent strength are not
adjusted for. Consecutive matches may be dependent, whereas these statistical
calculations assume independent match outcomes. Missing timelines and exclusion
of games that end before a checkpoint can also affect the observed sample.

Repeatedly changing filters or checking results until they become significant
can create false positives beyond the correction within one report. Validate
interesting patterns on subsequently collected matches before turning them into
strong coaching recommendations. A negative finding does not prove absence of
an effect; splitting by position and patch often leaves limited statistical power.

The next stages are contextual/multivariable analysis and an LLM report renderer.
The renderer should receive these structured findings and limitations, preserve
the evidence IDs and numbers, and avoid inventing causal claims or recommendations
unsupported by the evidence. No LLM API key is needed for this first stage.

## Verification and method references

Run `python -m pytest -q` from `backend`. Tests include cutoff boundaries, events
stored after the cutoff, stale and missing frames, remakes, role ambiguity,
known numerical interval/correction examples, cohort separation, small samples,
reverse associations, end-to-end supported findings, phases, event boundaries,
irregular spatial samples, lane transitions, partial games and local-only API access.
The same suite can run on a disposable PostgreSQL database using the existing
`TEST_DATABASE_URL` mechanism documented in [match collection](match_data.md).

- [Riot Match-v5](https://developer.riotgames.com/apis#match-v5)
- [SciPy Fisher exact test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)
- [Wilson proportion intervals](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html)
- [Two-proportion intervals](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html)
- [Holm multiple-testing correction](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)
