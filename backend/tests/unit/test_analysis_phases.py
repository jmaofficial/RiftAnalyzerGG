from copy import deepcopy

import pytest

from app.analysis.features import extract_features
from app.analysis.progression_summary import summarize_progression
from app.analysis.spatial import classify_position
from tests.unit.test_analysis_features import analysis_case


def phase(row, name):
    return next(item for item in row.phases if item.name == name)


def add_positions(match):
    for minute, frame in enumerate(match.timeline_data["info"]["frames"]):
        own = frame["participantFrames"]["1"]
        own["position"] = {"x": 1800, "y": 8000} if 15 <= minute <= 20 else {"x": 7500, "y": 7500}
        own["currentGold"] = 1200


def test_phases_measure_growth_instead_of_end_totals(analysis_case):
    match, player = analysis_case
    add_positions(match)
    row = extract_features(match, player)
    laning = phase(row, "laning")
    assert laning.status == "complete"
    assert laning.gold_gained == 4500
    assert laning.lane_cs_gained == 90
    assert laning.jungle_cs_gained == 0
    assert laning.cs_per_minute == 6
    assert laning.gold_per_minute == 300
    assert laning.xp_gained == 6000
    assert laning.gold_diff_at_start == laning.gold_diff_at_end == -500
    assert laning.gold_diff_change == 0
    assert laning.team_gold_diff_at_start == -2500
    assert (laning.kills, laning.deaths, laning.assists) == (1, 2, 1)
    midgame = phase(row, "midgame")
    assert midgame.gold_gained == 3000
    assert midgame.unspent_gold_at_end == 1200
    assert midgame.kills == 1
    assert midgame.deaths == 0


def test_event_on_window_boundary_is_counted_once(analysis_case):
    match, player = analysis_case
    match.timeline_data["info"]["frames"][5]["events"].append({
        "type": "CHAMPION_KILL", "timestamp": 300000, "killerId": 6, "victimId": 1,
    })
    row = extract_features(match, player)
    assert row.windows[0].deaths == 1
    assert row.windows[1].deaths == 0
    followup = next(item for item in row.event_followups if item.timestamp_ms == 300000)
    assert followup.followup.deaths == 0


def test_short_game_has_partial_midgame_and_no_late_game(analysis_case):
    match, player = analysis_case
    match.duration_seconds = 1000
    row = extract_features(match, player)
    midgame = phase(row, "midgame")
    assert midgame.status == "partial"
    assert midgame.duration_seconds == 100
    assert midgame.observed_start_ms == 900000
    assert midgame.observed_end_ms == 960000
    assert midgame.gold_gained == 300
    assert phase(row, "late_game").status == "not_reached"
    assert phase(row, "late_game").gold_gained is None


def test_sidelane_proxy_requires_same_lane_at_both_endpoints(analysis_case):
    match, player = analysis_case
    add_positions(match)
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.applicable
    assert side.status == "available"
    assert side.observed_seconds == 600
    assert side.sidelane_seconds == side.top_seconds == 300
    assert side.bottom_seconds == 0
    assert side.transition_seconds == 60
    assert side.coverage_fraction == 1
    assert side.sidelane_share_of_observed_time == .5
    assert side.gold_gained_during_sidelane_intervals == 1500
    assert side.lane_cs_gained_during_sidelane_intervals == 30
    assert side.jungle_cs_gained_during_sidelane_intervals == 0
    assert side.gold_per_observed_sidelane_minute == 300
    assert side.lane_cs_per_observed_sidelane_minute == 6
    assert side.attribution == "spatial_proxy_not_gold_source"


def test_sidelane_long_gaps_are_unobserved_not_interpolated(analysis_case):
    match, player = analysis_case
    add_positions(match)
    match.timeline_data["info"]["frames"].pop(17)
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.observed_seconds == 480
    assert side.coverage_fraction == .8
    assert side.sidelane_seconds == 180
    assert side.gold_gained_during_sidelane_intervals == 900


def test_sidelane_uses_actual_timestamps_not_frame_count(analysis_case):
    match, player = analysis_case
    add_positions(match)
    match.timeline_data["info"]["frames"][16]["timestamp"] = 940000
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.top_seconds == 300
    assert side.observed_seconds == 600


def test_lane_transition_does_not_attribute_gold_to_either_lane(analysis_case):
    match, player = analysis_case
    add_positions(match)
    match.timeline_data["info"]["frames"][20]["participantFrames"]["1"]["position"] = {"x": 8000, "y": 1800}
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.top_seconds == 240
    assert side.bottom_seconds == 0
    assert side.transition_seconds == 120
    assert side.gold_gained_during_sidelane_intervals == 1200


def test_missing_positions_are_unknown_rather_than_no_sidelaning(analysis_case):
    match, player = analysis_case
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.status == "insufficient_position_data"
    assert side.sidelane_seconds is None
    assert side.gold_gained_during_sidelane_intervals is None
    assert side.coverage_fraction is None


def test_valid_non_sidelane_observations_can_be_zero(analysis_case):
    match, player = analysis_case
    for frame in match.timeline_data["info"]["frames"]:
        frame["participantFrames"]["1"]["position"] = {"x": 7500, "y": 7500}
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.status == "available"
    assert side.sidelane_seconds == side.gold_gained_during_sidelane_intervals == 0
    assert side.gold_per_observed_sidelane_minute is None


def test_sidelane_proxy_is_only_for_mid_players(analysis_case):
    match, player = analysis_case
    player.team_position = "JUNGLE"
    add_positions(match)
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.status == "not_applicable"
    assert not side.applicable
    assert side.gold_gained_during_sidelane_intervals is None


def test_invalid_gold_delta_is_unknown_without_discarding_cs(analysis_case):
    match, player = analysis_case
    add_positions(match)
    match.timeline_data["info"]["frames"][17]["participantFrames"]["1"]["totalGold"] = 1
    side = phase(extract_features(match, player), "midgame").sidelane
    assert side.gold_gained_during_sidelane_intervals is None
    assert side.lane_cs_gained_during_sidelane_intervals == 30


def test_missing_timeline_propagates_to_windows(analysis_case):
    match, player = analysis_case
    match.timeline_data = None
    row = extract_features(match, player)
    assert phase(row, "midgame").snapshot_status == "missing_timeline"
    assert phase(row, "midgame").gold_gained is None
    assert phase(row, "midgame").sidelane.status == "missing_timeline"
    assert row.event_followups == []


def test_stale_start_snapshot_does_not_become_growth(analysis_case):
    match, player = analysis_case
    frames = match.timeline_data["info"]["frames"]
    match.timeline_data["info"]["frames"] = [f for f in frames if f["timestamp"] not in (240000, 300000)]
    window = extract_features(match, player).windows[1]
    assert window.snapshot_status == "stale_frame"
    assert window.gold_gained is None
    assert window.kills == 1


def test_activity_events_are_participations_not_gold_sources(analysis_case):
    match, player = analysis_case
    match.timeline_data["info"]["frames"][20]["events"] += [
        {"type": "TURRET_PLATE_DESTROYED", "timestamp": 1020000, "killerId": 1},
        {"type": "BUILDING_KILL", "timestamp": 1080000, "killerId": 2, "buildingType": "TOWER_BUILDING", "assistingParticipantIds": [1], "bounty": 123},
        {"type": "ELITE_MONSTER_KILL", "timestamp": 1140000, "killerId": 2, "assistingParticipantIds": [1]},
        {"type": "ITEM_PURCHASED", "timestamp": 1150000, "participantId": 1, "itemId": 1001},
        {"type": "ITEM_UNDO", "timestamp": 1160000, "participantId": 1, "goldGain": 300},
    ]
    midgame = phase(extract_features(match, player), "midgame")
    assert midgame.tower_kill_participations == 1
    assert midgame.plate_last_hits == 1
    assert midgame.elite_monster_kill_participations == 1
    assert midgame.item_purchase_events == 1
    assert midgame.gold_gained == 3000


def test_post_kill_followup_keeps_snapshot_provenance(analysis_case):
    match, player = analysis_case
    kill = match.timeline_data["info"]["frames"][11]["events"][0]
    kill["position"] = {"x": 8000, "y": 1800}
    row = extract_features(match, player)
    followup = next(item for item in row.event_followups if item.timestamp_ms == 599999)
    assert followup.event_type == "after_kill"
    assert followup.event_zone == "bottom"
    assert followup.followup.kills == 0
    assert followup.followup.deaths == 1
    assert followup.followup.observed_start_ms == 540000
    assert followup.followup.observed_end_ms == 660000


def test_descriptive_summaries_pool_patches_but_do_not_mix_roles_or_partial_phases(analysis_case):
    match, player = analysis_case
    add_positions(match)
    won = extract_features(match, player)
    won.win = True
    lost = won.model_copy(deep=True)
    lost.patch = "16.21"
    lost.win = False
    phase(lost, "midgame").gold_gained = 2000
    partial = won.model_copy(deep=True)
    phase(partial, "midgame").status = "partial"
    phase(partial, "midgame").gold_gained = 1
    jungle = won.model_copy(deep=True)
    jungle.position = "JUNGLE"
    summary = next(s for s in summarize_progression([won, lost, partial, jungle]) if s.position == "MIDDLE" and s.phase == "midgame")
    assert summary.pooling == "descriptive_across_patches"
    assert summary.patches == ["16.21", "16.22"]
    assert summary.complete_matches == 2
    assert summary.partial_matches == 1
    metric = summary.metrics["gold_gained"]
    assert metric.available_matches == 2
    assert metric.mean == 2500
    assert metric.win_mean == 3000
    assert metric.loss_mean == 2000


def test_low_spatial_coverage_is_not_used_in_pooled_side_lane_metrics(analysis_case):
    match, player = analysis_case
    add_positions(match)
    row = extract_features(match, player)
    phase(row, "midgame").sidelane.coverage_fraction = .2
    summary = next(s for s in summarize_progression([row]) if s.phase == "midgame")
    assert summary.metrics["sidelane.coverage_fraction"].available_matches == 1
    assert summary.metrics["sidelane.gold_gained_during_sidelane_intervals"].available_matches == 0


def test_malformed_activity_does_not_erase_valid_combat_or_gold(analysis_case):
    match, player = analysis_case
    match.timeline_data["info"]["frames"][20]["events"].append({
        "type": "BUILDING_KILL", "timestamp": 1080000, "killerId": 1,
    })
    midgame = phase(extract_features(match, player), "midgame")
    assert midgame.activity_status == "invalid_timeline"
    assert midgame.tower_kill_participations is None
    assert midgame.gold_gained == 3000
    assert midgame.kills == 1


@pytest.mark.parametrize("point,expected", [
    ({"x": 1800, "y": 8000}, "top"),
    ({"x": 8000, "y": 13000}, "top"),
    ({"x": 8000, "y": 1800}, "bottom"),
    ({"x": 13000, "y": 8000}, "bottom"),
    ({"x": 7500, "y": 7500}, "middle"),
    ({"x": 5000, "y": 8500}, "jungle_or_river"),
    ({"x": 1200, "y": 1200}, "base"),
    ({"x": 13800, "y": 13800}, "base"),
    ({"x": 0, "y": 0}, None),
    ({"x": -1, "y": 8000}, None),
    ({"x": float("nan"), "y": 8000}, None),
    ({"x": True, "y": 8000}, None),
    (None, None),
])
def test_spatial_classifier(point, expected):
    assert classify_position(point) == expected
