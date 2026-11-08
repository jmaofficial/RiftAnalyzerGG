from copy import deepcopy

import pytest

from tests.unit.test_analysis_features import analysis_case


BASE = "/api/players/jonnybravo/1998/analysis"


@pytest.fixture
def imported_analysis(client, configured_riot, analysis_case):
    match, _ = analysis_case
    configured_riot.get_match_details_by_match_id.return_value = deepcopy(match.raw_data)
    configured_riot.get_match_timeline.return_value = deepcopy(match.timeline_data)
    assert client.post("/api/players/jonnybravo/1998/matches/sync").json()["completed"]
    configured_riot.reset_mock()
    return client


def test_analysis_endpoints_only_read_stored_data(imported_analysis, configured_riot):
    response = imported_analysis.get(BASE + "/features")
    assert response.status_code == 200
    features = response.json()
    assert features["feature_version"] == "timeline-v2"
    assert features["eligible_matches"] == 1
    assert features["items"][0]["checkpoints"]["15"]["deaths"] == 2
    assert len(features["items"][0]["windows"]) == 7
    assert [phase["name"] for phase in features["items"][0]["phases"]] == ["laning", "midgame", "late_game"]
    assert features["items"][0]["phases"][0]["gold_gained"] == 4500
    report = imported_analysis.get(BASE)
    assert report.status_code == 200
    assert report.json()["status"] == "insufficient_data"
    assert report.json()["findings"] == []
    assert report.json()["analysis_version"] == "associations-v2"
    assert report.json()["phase_summaries"]
    assert all(phase["pooling"] == "descriptive_across_patches" for phase in report.json()["phase_summaries"])
    assert configured_riot.mock_calls == []


def test_analysis_filters(imported_analysis):
    assert imported_analysis.get(BASE + "/features?position=MIDDLE&patch=16.22").json()["selected_matches"] == 1
    assert imported_analysis.get(BASE + "/features?position=TOP").json()["selected_matches"] == 0
    assert imported_analysis.get(BASE + "/features?patch=16.2").json()["selected_matches"] == 0


def test_analysis_limit_is_explicit_about_truncation(imported_analysis, configured_riot, analysis_case):
    match, _ = analysis_case
    payload = deepcopy(match.raw_data)
    payload["metadata"]["matchId"] = "EUW1_2"
    payload["info"]["gameStartTimestamp"] += 3600000
    timeline = deepcopy(match.timeline_data)
    timeline["metadata"]["matchId"] = "EUW1_2"
    configured_riot.get_match_details_by_match_id.return_value = payload
    configured_riot.get_match_timeline.return_value = timeline
    assert imported_analysis.post("/api/matches/EUW1_2/sync").status_code == 200
    response = imported_analysis.get(BASE + "/features?limit=1").json()
    assert response["matched_total"] == 2
    assert response["selected_matches"] == 1
    assert response["truncated"] is True
    assert response["items"][0]["match_id"] == "EUW1_2"


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "position=SUPPORT", "patch=16.22.1", "patch=x"])
def test_invalid_analysis_filters(client, query):
    assert client.get(BASE + "?" + query).status_code == 422


def test_analysis_for_unknown_player_returns_404(client):
    assert client.get(BASE).status_code == 404
    assert client.get(BASE + "/features").status_code == 404


def test_other_queues_are_not_included(imported_analysis, session):
    from app.db.models import Match

    session.get(Match, "EUW1_1").queue_id = 450
    session.commit()
    assert imported_analysis.get(BASE + "/features").json()["selected_matches"] == 0


def test_missing_timeline_is_visible_in_report(imported_analysis, session):
    from app.db.models import Match

    session.get(Match, "EUW1_1").timeline_data = None
    session.commit()
    report = imported_analysis.get(BASE).json()
    assert report["selected_matches"] == 1
    assert report["eligible_matches"] == 0
    assert report["excluded_matches_by_reason"] == {"missing_timeline": 1}


def test_report_with_supported_finding_across_streamed_batches(client, session, analysis_case):
    from app.db.models import Player
    from app.services.match_service import MatchService

    template, _ = analysis_case
    session.add(Player(puuid="my-puuid", game_name="JonnyBravo", tag_line="1998"))
    for index in range(60):
        match_id = f"EUW1_{index + 1}"
        payload = deepcopy(template.raw_data)
        payload["metadata"]["matchId"] = match_id
        payload["info"]["gameStartTimestamp"] += index * 3600000
        payload["info"]["participants"][0]["win"] = index < 24 if index < 30 else index < 36
        match = MatchService._build_match(match_id, payload)
        match.timeline_data = deepcopy(template.timeline_data)
        match.timeline_data["metadata"]["matchId"] = match_id
        for frame in match.timeline_data["info"]["frames"]:
            frame["events"] = []
        match.timeline_data["info"]["frames"][15]["events"] = [
            {"type": "CHAMPION_KILL", "timestamp": 720_000 + i * 10000, "killerId": 6, "victimId": 1}
            for i in range(1 if index < 30 else 4)
        ]
        session.add(match)
    session.commit()
    response = client.get(BASE)
    assert response.status_code == 200
    report = response.json()
    assert report["eligible_matches"] == 60
    assert report["status"] == "findings_available"
    finding = next(f for f in report["findings"] if f["rule_id"] == "deaths_15")
    assert finding["group_a"]["wins"] == 24
    assert finding["group_b"]["wins"] == 6
    assert finding["win_rate_difference_pp"] == pytest.approx(60)
