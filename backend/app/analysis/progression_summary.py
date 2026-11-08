"""Descriptive phase summaries, deliberately separate from inferential findings."""
from collections import defaultdict
from statistics import mean

from app.schemas.analysis import DescriptiveMetric, PhaseSummary


METRICS = (
    "duration_seconds", "observed_duration_seconds", "gold_gained", "gold_per_minute",
    "lane_cs_gained", "jungle_cs_gained", "xp_gained", "cs_per_minute",
    "gold_diff_at_start", "gold_diff_at_end", "gold_diff_change",
    "cs_diff_change", "xp_diff_change", "team_gold_diff_at_start",
    "unspent_gold_at_end", "kills", "deaths", "assists",
    "tower_kill_participations", "plate_last_hits",
    "elite_monster_kill_participations",
)
SIDE_METRICS = (
    "coverage_fraction", "sidelane_share_of_observed_time",
    "gold_gained_during_sidelane_intervals", "lane_cs_gained_during_sidelane_intervals",
    "gold_per_observed_sidelane_minute",
    "lane_cs_per_observed_sidelane_minute", "sidelane_seconds",
)


def summarize_progression(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.eligible:
            for phase in row.phases:
                groups[(row.position, phase.name)].append((row, phase))
    result = []
    for (position, name), entries in sorted(groups.items()):
        complete = [(row, phase) for row, phase in entries if phase.status == "complete"]
        metrics = {}
        for metric in METRICS + tuple("sidelane." + metric for metric in SIDE_METRICS):
            values = []
            for row, phase in complete:
                # Keep low-coverage samples visible individually, but out of pooled lane claims.
                if metric.startswith("sidelane.") and metric != "sidelane.coverage_fraction":
                    coverage = phase.sidelane.coverage_fraction
                    if coverage is None or coverage < 0.8:
                        continue
                value = getattr(phase.sidelane, metric.split(".")[1]) if metric.startswith("sidelane.") else getattr(phase, metric)
                if value is not None:
                    values.append((row.win, value))
            wins = [value for won, value in values if won]
            losses = [value for won, value in values if not won]
            metrics[metric] = DescriptiveMetric(
                available_matches=len(values), mean=mean(value for _, value in values) if values else None,
                win_matches=len(wins), win_mean=mean(wins) if wins else None,
                loss_matches=len(losses), loss_mean=mean(losses) if losses else None,
            )
        result.append(PhaseSummary(
            position=position, phase=name, patches=sorted({row.patch for row, _ in entries}),
            complete_matches=len(complete),
            partial_matches=sum(phase.status == "partial" for _, phase in entries),
            not_reached_matches=sum(phase.status == "not_reached" for _, phase in entries),
            metrics=metrics,
        ))
    return result
