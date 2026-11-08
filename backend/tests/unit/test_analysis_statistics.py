from datetime import datetime, timezone

import pytest

from app.analysis.statistics import build_report, holm_adjust, wilson_interval
from app.schemas.analysis import AnalysisFilters, Checkpoint, FeatureDataset, MatchFeatures


def feature(index, win, deaths, patch="16.22", position="MIDDLE"):
    checkpoints = {
        minute: Checkpoint(minute=minute, snapshot_status="available", combat_status="available")
        for minute in (10, 15, 20)
    }
    checkpoints[15].deaths = deaths
    return MatchFeatures(
        match_id=f"EUW1_{index}", game_start=datetime(2026, 11, 1, tzinfo=timezone.utc),
        patch=patch, position=position, champion_name="Annie", win=win,
        duration_seconds=1800, eligible=True, opponent_status="unavailable",
        checkpoints=checkpoints,
    )


def strong_rows(offset=0, patch="16.22"):
    return [
        feature(offset + i, i < 24 if i < 30 else i < 36, 1 if i < 30 else 4, patch=patch)
        for i in range(60)
    ]


def dataset(rows):
    return FeatureDataset(
        puuid="my-puuid", filters=AnalysisFilters(limit=200),
        matched_total=len(rows), selected_matches=len(rows),
        eligible_matches=sum(row.eligible for row in rows), truncated=False, items=rows,
    )


def test_wilson_known_reference_values_and_extreme_outcomes():
    balanced = wilson_interval(5, 10)
    assert balanced.lower == pytest.approx(0.2365930905)
    assert balanced.upper == pytest.approx(0.7634069095)
    assert wilson_interval(0, 10).upper == pytest.approx(0.2775327999)
    assert wilson_interval(10, 10).lower == pytest.approx(0.7224672001)
    assert wilson_interval(0, 0) is None


@pytest.mark.parametrize("values,expected", [
    ([.01, .04, .03], [.03, .06, .06]),
    ([.5, .001, .02, .1], [.5, .004, .06, .2]),
    ([0, 1, .025, .025], [0, 1, .075, .075]),
    ([], []),
])
def test_holm_adjustment_matches_reference_examples(values, expected):
    assert holm_adjust(values) == pytest.approx(expected)


def test_strong_association_has_evidence_and_is_not_a_causal_claim():
    report = build_report(dataset(strong_rows()))
    assert report.status == "findings_available"
    assert report.tested_hypotheses == 1
    finding = report.findings[0]
    assert finding.rule_id == "deaths_15"
    assert (finding.group_a.matches, finding.group_a.wins) == (30, 24)
    assert (finding.group_b.matches, finding.group_b.wins) == (30, 6)
    assert finding.win_rate_difference_pp == pytest.approx(60)
    assert finding.difference_ci95_pp.lower > 0
    assert finding.adjusted_p_value < .0001
    assert finding.interpretation == "association_only"
    assert "inte ett bevis på orsak" in finding.summary
    assert len(finding.group_a.match_ids) == 30
    assert finding.direction == "higher_in_group_a"


def test_reverse_association_is_reported_without_assuming_expected_direction():
    rows = strong_rows()
    for row in rows:
        row.win = not row.win
    finding = build_report(dataset(rows)).findings[0]
    assert finding.direction == "higher_in_group_b"
    assert finding.win_rate_difference_pp == pytest.approx(-60)
    assert finding.difference_ci95_pp.upper < 0


def test_balanced_results_do_not_generate_feedback():
    rows = [feature(i, i % 2 == 0, 1 if i < 30 else 4) for i in range(60)]
    report = build_report(dataset(rows))
    assert report.status == "no_supported_findings"
    assert report.findings == []
    tested = [c for c in report.comparisons if c.p_value is not None]
    assert tested[0].p_value == pytest.approx(1)
    assert tested[0].win_rate_difference_pp == 0


@pytest.mark.parametrize("size_a,size_b", [(9, 51), (10, 10), (30, 0)])
def test_minimum_sample_sizes_prevent_overconfident_findings(size_a, size_b):
    rows = [feature(i, True, 1) for i in range(size_a)]
    rows += [feature(i + size_a, False, 4) for i in range(size_b)]
    report = build_report(dataset(rows))
    assert report.status == "insufficient_data"
    assert report.tested_hypotheses == 0
    assert report.findings == []


def test_positions_and_patches_are_never_pooled():
    rows = strong_rows()
    for i, row in enumerate(rows):
        row.patch = "16.22" if i % 2 else "16.21"
        row.position = "MIDDLE" if (i // 2) % 2 else "TOP"
    report = build_report(dataset(rows))
    assert len(report.cohorts) == 4
    assert all(cohort.matches == 15 for cohort in report.cohorts)
    assert report.status == "insufficient_data"


def test_multiple_testing_correction_covers_all_cohorts():
    report = build_report(dataset(strong_rows() + strong_rows(offset=100, patch="16.21")))
    assert report.tested_hypotheses == 2
    assert len(report.findings) == 2
    for finding in report.findings:
        assert finding.adjusted_p_value == pytest.approx(2 * finding.p_value)


def test_high_kill_rule_only_compares_high_kill_matches():
    rows = strong_rows()
    for i, row in enumerate(rows):
        row.checkpoints[20].kills = 10
        row.checkpoints[20].deaths = 7 if i < 30 else 8
    low_kill_rows = [feature(100 + i, False, 1) for i in range(30)]
    for row in low_kill_rows:
        row.checkpoints[20].kills = 9
        row.checkpoints[20].deaths = 0
    report = build_report(dataset(rows + low_kill_rows))
    comparison = next(c for c in report.comparisons if c.rule_id == "high_kill_deaths_20")
    assert comparison.group_a.matches == comparison.group_b.matches == 30
    assert comparison.missing_or_inapplicable_matches == 30
    assert comparison.status == "supported_association"


def test_exclusions_are_counted_and_never_used_as_evidence():
    rows = strong_rows()
    for row in rows:
        row.eligible = False
        row.exclusion_reasons = ["missing_timeline"]
    report = build_report(dataset(rows))
    assert report.excluded_matches_by_reason == {"missing_timeline": 60}
    assert report.eligible_matches == 0
    assert report.comparisons == report.findings == []
    assert report.status == "insufficient_data"
