"""Predefined exploratory associations, with no data-driven threshold search."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from statistics import NormalDist

from scipy.stats import fisher_exact
from app.analysis.progression_summary import summarize_progression

from app.schemas.analysis import (
    AnalysisReport, CohortSummary, Comparison, FeatureDataset,
    Interval, MatchFeatures, OutcomeGroup,
)


MIN_COHORT_MATCHES = 30
MIN_GROUP_MATCHES = 10
MIN_DIFFERENCE_PP = 10
ALPHA = 0.05


@dataclass(frozen=True)
class Rule:
    rule_id: str
    minute: int
    metric: str
    threshold: int
    comparison: str
    label_a: str
    label_b: str
    minimum_kills: int | None = None

    def group(self, row: MatchFeatures) -> bool | None:
        checkpoint = row.checkpoints[self.minute]
        value = getattr(checkpoint, self.metric)
        if value is None:
            return None
        if self.minimum_kills is not None and (
            checkpoint.kills is None or checkpoint.kills < self.minimum_kills
        ):
            return None
        return value <= self.threshold if self.comparison == "le" else value >= self.threshold


# These thresholds are versioned product hypotheses, not fitted to the player's wins.
RULES = (
    Rule("deaths_10", 10, "deaths", 1, "le", "Högst 1 death vid 10:00", "Fler än 1 death vid 10:00"),
    Rule("deaths_15", 15, "deaths", 2, "le", "Högst 2 deaths vid 15:00", "Fler än 2 deaths vid 15:00"),
    Rule("gold_diff_15", 15, "gold_diff", 0, "ge", "Minst lika mycket guld som rollmotståndaren vid 15:00", "Mindre guld än rollmotståndaren vid 15:00"),
    Rule("cs_diff_10", 10, "cs_diff", 0, "ge", "Minst lika mycket CS som rollmotståndaren vid 10:00", "Mindre CS än rollmotståndaren vid 10:00"),
    Rule("xp_diff_15", 15, "xp_diff", 0, "ge", "Minst lika mycket XP som rollmotståndaren vid 15:00", "Mindre XP än rollmotståndaren vid 15:00"),
    Rule("high_kill_deaths_20", 20, "deaths", 7, "le", "Minst 10 kills och färre än 8 deaths vid 20:00", "Minst 10 kills och minst 8 deaths vid 20:00", minimum_kills=10),
)


def wilson_interval(wins: int, matches: int) -> Interval | None:
    """95% Wilson score interval for a binomial proportion."""
    if matches == 0:
        return None
    z = NormalDist().inv_cdf(0.975)
    rate = wins / matches
    denominator = 1 + z * z / matches
    centre = (rate + z * z / (2 * matches)) / denominator
    radius = z * sqrt(rate * (1 - rate) / matches + z * z / (4 * matches**2)) / denominator
    return Interval(lower=max(0, centre - radius), upper=min(1, centre + radius))


def outcome_group(label: str, rows: list[MatchFeatures]) -> OutcomeGroup:
    wins = sum(row.win for row in rows)
    return OutcomeGroup(
        label=label, matches=len(rows), wins=wins,
        win_rate=wins / len(rows) if rows else None,
        win_rate_ci95=wilson_interval(wins, len(rows)),
        match_ids=[row.match_id for row in rows],
    )


def newcombe_difference(a: OutcomeGroup, b: OutcomeGroup) -> Interval:
    """Newcombe's unpooled Wilson interval for difference in independent proportions."""
    difference = a.win_rate - b.win_rate
    lower = difference - sqrt(
        (a.win_rate - a.win_rate_ci95.lower)**2
        + (b.win_rate_ci95.upper - b.win_rate)**2
    )
    upper = difference + sqrt(
        (a.win_rate_ci95.upper - a.win_rate)**2
        + (b.win_rate - b.win_rate_ci95.lower)**2
    )
    return Interval(lower=max(-1, lower) * 100, upper=min(1, upper) * 100)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm step-down family-wise correction; output retains original order."""
    adjusted = [1.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)), key=p_values.__getitem__)):
        previous = min(1.0, max(previous, p_values[index] * (len(p_values) - rank)))
        adjusted[index] = previous
    return adjusted


def compare(rule: Rule, rows: list[MatchFeatures], patch: str, position: str) -> Comparison:
    a, b = [], []
    for row in rows:
        assignment = rule.group(row)
        if assignment is not None:
            (a if assignment else b).append(row)
    group_a = outcome_group(rule.label_a, a)
    group_b = outcome_group(rule.label_b, b)
    comparison = Comparison(
        finding_id=f"{patch}:{position}:{rule.rule_id}", rule_id=rule.rule_id,
        patch=patch, position=position, minute=rule.minute, metric=rule.metric,
        group_a=group_a, group_b=group_b,
        missing_or_inapplicable_matches=len(rows) - len(a) - len(b),
        status="insufficient_data",
    )
    if a and b:
        comparison.win_rate_difference_pp = (group_a.win_rate - group_b.win_rate) * 100
        comparison.difference_ci95_pp = newcombe_difference(group_a, group_b)
    if len(a) + len(b) >= MIN_COHORT_MATCHES and min(len(a), len(b)) >= MIN_GROUP_MATCHES:
        comparison.p_value = float(fisher_exact([
            [group_a.wins, group_a.matches - group_a.wins],
            [group_b.wins, group_b.matches - group_b.wins],
        ], alternative="two-sided").pvalue)
        comparison.status = "not_supported"
    return comparison


def build_report(dataset: FeatureDataset) -> AnalysisReport:
    cohorts = defaultdict(list)
    excluded = Counter()
    for row in dataset.items:
        if row.eligible:
            cohorts[(row.patch, row.position)].append(row)
        else:
            excluded.update(row.exclusion_reasons)
    comparisons = [
        compare(rule, rows, patch, position)
        for (patch, position), rows in sorted(cohorts.items()) for rule in RULES
    ]
    tested = [comparison for comparison in comparisons if comparison.p_value is not None]
    adjusted = holm_adjust([comparison.p_value for comparison in tested])
    for comparison, p_value in zip(tested, adjusted):
        comparison.adjusted_p_value = p_value
        interval = comparison.difference_ci95_pp
        if (
            p_value <= ALPHA
            and abs(comparison.win_rate_difference_pp) >= MIN_DIFFERENCE_PP
            and (interval.lower > 0 or interval.upper < 0)
        ):
            comparison.status = "supported_association"
            comparison.direction = "higher_in_group_a" if comparison.win_rate_difference_pp > 0 else "higher_in_group_b"
            comparison.summary = (
                f"{comparison.group_a.label}: {comparison.group_a.wins}/{comparison.group_a.matches} "
                f"vinster ({comparison.group_a.win_rate:.0%}). "
                f"{comparison.group_b.label}: {comparison.group_b.wins}/{comparison.group_b.matches} "
                f"vinster ({comparison.group_b.win_rate:.0%}). "
                "Detta är ett samband i dina sparade matcher, inte ett bevis på orsak."
            )
    findings = sorted(
        [comparison for comparison in comparisons if comparison.status == "supported_association"],
        key=lambda comparison: (comparison.adjusted_p_value, -abs(comparison.win_rate_difference_pp), comparison.finding_id),
    )
    status = "findings_available" if findings else (
        "no_supported_findings" if tested else "insufficient_data"
    )
    return AnalysisReport(
        puuid=dataset.puuid, generated_at=datetime.now(timezone.utc), status=status,
        filters=dataset.filters, matched_total=dataset.matched_total,
        selected_matches=dataset.selected_matches, eligible_matches=dataset.eligible_matches,
        truncated=dataset.truncated, excluded_matches_by_reason=dict(excluded),
        cohorts=[CohortSummary(patch=patch, position=position, matches=len(rows), wins=sum(row.win for row in rows))
                 for (patch, position), rows in sorted(cohorts.items())],
        tested_hypotheses=len(tested), comparisons=comparisons, findings=findings,
        phase_summaries=summarize_progression(dataset.items),
        limitations=[
            "Exploratory associations, not causal effects or validated predictions.",
            "Champion, rank, team state and opponent strength are not statistically adjusted for.",
            "Consecutive matches may be dependent; uncertainty calculations assume independent match outcomes.",
            "Only stored matches are analyzed; missing timelines and matches shorter than a checkpoint can bias coverage.",
            "No threshold search is performed, but repeatedly changing filters or collecting data until significant can still create false positives.",
            "Snapshot values use the latest frame at or before the checkpoint, at most 90 seconds old; combat counts use event timestamps.",
            "Role opponents follow Riot teamPosition and may not be the actual lane opponent.",
            "Phase summaries pool patches descriptively within each role, omit partial phases from means, and are not statistical findings.",
            "Sidelane metrics use sparse position samples and include all gold gained during observed intervals, not exact gold earned from that lane.",
            "Fixed phase boundaries are analysis conventions, not detected lane swaps or actual phase transitions.",
            "Post-event windows describe subsequent observations, may overlap, and do not measure causal gold lost or gained because of an event.",
        ],
    )
