from copy import deepcopy

import pytest

from app.analysis.features import extract_features
from app.services.match_service import MatchService


@pytest.fixture
def analysis_case(payload):
    roles = ["MIDDLE", "TOP", "JUNGLE", "BOTTOM", "UTILITY"] * 2
    for participant, role in zip(payload["info"]["participants"], roles):
        participant["teamPosition"] = role
    match = MatchService._build_match("EUW1_1", payload)
    frames = []
    for minute in range(31):
        frames.append({
            "timestamp": minute * 60_000, "events": [],
            "participantFrames": {
                str(pid): {
                    "participantId": pid, "totalGold": 500 + minute * 300 + pid * 100,
                    "minionsKilled": minute * 6, "jungleMinionsKilled": pid,
                    "xp": minute * 400 + pid * 100,
                } for pid in range(1, 11)
            },
        })
    # Events may be stored in a frame after the event's actual timestamp.
    frames[11]["events"] = [
        {"type": "CHAMPION_KILL", "timestamp": 599_999, "killerId": 1, "victimId": 6},
        {"type": "CHAMPION_KILL", "timestamp": 600_000, "killerId": 2, "victimId": 7, "assistingParticipantIds": [1]},
        {"type": "CHAMPION_KILL", "timestamp": 600_001, "killerId": 6, "victimId": 1},
    ]
    frames[16]["events"] = [
        {"type": "CHAMPION_KILL", "timestamp": 900_000, "killerId": 0, "victimId": 1},
        {"type": "CHAMPION_KILL", "timestamp": 900_001, "killerId": 1, "victimId": 6},
    ]
    match.timeline_data = {
        "metadata": {"matchId": match.match_id},
        "info": {
            "participants": [{"participantId": p.participant_id, "puuid": p.puuid} for p in match.participants],
            "frames": frames,
        },
    }
    return match, match.participants[0]


def test_cutoff_is_inclusive_and_events_use_event_time(analysis_case):
    match, participant = analysis_case
    row = extract_features(match, participant)
    assert row.eligible
    assert row.patch == "16.22"
    assert row.opponent_participant_id == 6
    at10, at15 = row.checkpoints[10], row.checkpoints[15]
    assert (at10.kills, at10.deaths, at10.assists) == (1, 0, 1)
    assert (at15.kills, at15.deaths, at15.assists) == (1, 2, 1)
    assert row.checkpoints[20].kills == 2
    assert at10.gold == 3600
    assert at10.cs == 61
    assert at10.xp == 4100
    assert at10.gold_diff == -500
    assert at10.cs_diff == -5
    assert at10.xp_diff == -500
    assert at10.team_gold_diff == -2500


def test_never_uses_a_future_snapshot(analysis_case):
    match, participant = analysis_case
    match.timeline_data["info"]["frames"] = [
        f for f in match.timeline_data["info"]["frames"] if f["timestamp"] != 900_000
    ]
    row = extract_features(match, participant).checkpoints[15]
    assert row.snapshot_timestamp_ms == 840_000
    assert row.snapshot_lag_ms == 60_000
    assert row.gold == 4800
    assert row.deaths == 2


def test_stale_snapshot_does_not_invalidate_combat(analysis_case):
    match, participant = analysis_case
    match.timeline_data["info"]["frames"] = [
        f for f in match.timeline_data["info"]["frames"] if f["timestamp"] not in (540_000, 600_000)
    ]
    row = extract_features(match, participant).checkpoints[10]
    assert row.snapshot_status == "stale_frame"
    assert row.gold is None
    assert row.gold_diff is None
    assert row.combat_status == "available"
    assert row.kills == 1


def test_short_matches_have_unknown_later_values(analysis_case):
    match, participant = analysis_case
    match.duration_seconds = 700
    row = extract_features(match, participant)
    assert row.eligible
    assert row.checkpoints[10].gold is not None
    for minute in (15, 20):
        assert row.checkpoints[minute].snapshot_status == "match_too_short"
        assert row.checkpoints[minute].deaths is None
        assert row.checkpoints[minute].gold is None


@pytest.mark.parametrize("flag,duration", [(True, 1800), (False, 180)])
def test_remakes_excluded(analysis_case, flag, duration):
    match, participant = analysis_case
    participant.game_ended_in_early_surrender = flag
    match.duration_seconds = duration
    row = extract_features(match, participant)
    assert not row.eligible
    assert "remake_or_early_surrender" in row.exclusion_reasons


def test_missing_timeline_is_not_zero(analysis_case):
    match, participant = analysis_case
    match.timeline_data = None
    row = extract_features(match, participant)
    assert not row.eligible
    assert row.exclusion_reasons == ["missing_timeline"]
    assert row.checkpoints[15].combat_status == "missing_timeline"
    assert row.checkpoints[15].deaths is None


def test_no_opponent_is_not_a_zero_difference(analysis_case):
    match, participant = analysis_case
    match.participants[5].team_position = None
    row = extract_features(match, participant)
    assert row.opponent_status == "unavailable"
    assert row.checkpoints[10].gold == 3600
    assert row.checkpoints[10].gold_diff is None


def test_ambiguous_role_match_does_not_choose_arbitrarily(analysis_case):
    match, participant = analysis_case
    match.participants[6].team_position = "MIDDLE"
    row = extract_features(match, participant)
    assert row.opponent_status == "ambiguous"
    assert row.opponent_participant_id is None
    assert row.checkpoints[15].cs_diff is None


def test_missing_player_frame_preserves_event_counts(analysis_case):
    match, participant = analysis_case
    del match.timeline_data["info"]["frames"][10]["participantFrames"]["1"]
    checkpoint = extract_features(match, participant).checkpoints[10]
    assert checkpoint.snapshot_status == "missing_player_frame"
    assert checkpoint.gold is None
    assert checkpoint.kills == 1


@pytest.mark.parametrize("field,value", [("totalGold", None), ("xp", -1), ("minionsKilled", True)])
def test_missing_invalid_fields_remain_unknown(analysis_case, field, value):
    match, participant = analysis_case
    match.timeline_data["info"]["frames"][10]["participantFrames"]["1"][field] = value
    row = extract_features(match, participant).checkpoints[10]
    metric = {"totalGold": "gold", "xp": "xp", "minionsKilled": "cs"}[field]
    assert getattr(row, metric) is None


def test_incomplete_event_coverage_is_not_zero(analysis_case):
    match, participant = analysis_case
    match.timeline_data["info"]["frames"] = match.timeline_data["info"]["frames"][:15]
    checkpoint = extract_features(match, participant).checkpoints[15]
    assert checkpoint.combat_status == "missing_frame"
    assert checkpoint.deaths is None
    assert checkpoint.gold is not None


@pytest.mark.parametrize("problem", ["wrong_match", "wrong_participant", "duplicate_frame", "missing_start", "malformed_frame"])
def test_invalid_timelines_are_excluded(analysis_case, problem):
    match, participant = analysis_case
    timeline = match.timeline_data
    if problem == "wrong_match":
        timeline["metadata"]["matchId"] = "EUW1_999"
    elif problem == "wrong_participant":
        timeline["info"]["participants"][0]["puuid"] = "someone-else"
    elif problem == "duplicate_frame":
        timeline["info"]["frames"].append(deepcopy(timeline["info"]["frames"][0]))
    elif problem == "missing_start":
        timeline["info"]["frames"].pop(0)
    else:
        timeline["info"]["frames"][0] = None
    row = extract_features(match, participant)
    assert not row.eligible
    assert "invalid_timeline" in row.exclusion_reasons


def test_invalid_combat_does_not_invent_zero_deaths(analysis_case):
    match, participant = analysis_case
    match.timeline_data["info"]["frames"][11]["events"][0]["victimId"] = 999
    row = extract_features(match, participant).checkpoints[10]
    assert row.combat_status == "invalid_timeline"
    assert row.kills is None
    assert row.gold is not None
