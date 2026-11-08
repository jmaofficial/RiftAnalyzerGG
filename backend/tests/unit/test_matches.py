import csv
import io
from copy import deepcopy
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import func, select

from app.clients.riot_client import RiotClient
from app.db.models import Match, MatchParticipant, Player
from app.repositories.match_repository import MatchRepository
from app.services.match_service import MatchService


SYNC = "/api/players/jonnybravo/1998/matches/sync"
STORED = "/api/players/jonnybravo/1998/matches/stored"


def test_sync_persists_all_participants_and_raw_payloads(client, session, payload, timeline):
    response = client.post(SYNC)
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["completed"] is True
    match = MatchRepository(session).get_by_id("EUW1_1")
    assert len(match.participants) == 10
    assert match.raw_data == payload
    assert match.timeline_data == timeline
    assert match.duration_seconds == 1800
    player = session.get(Player, "my-puuid")
    assert player.game_name == "JonnyBravo"
    assert session.scalar(select(func.count()).select_from(Player)) == 1
    assert match.participants[0].items == [1001, 0, 0, 0, 0, 0, 0]
    assert match.participants[0].raw_data["perks"] == payload["info"]["participants"][0]["perks"]


def test_repeat_sync_is_idempotent_and_does_not_refetch(client, configured_riot, session):
    client.post(SYNC)
    response = client.post(SYNC)
    assert response.json()["already_stored"] == 1
    configured_riot.get_match_details_by_match_id.assert_called_once_with("EUW1_1")
    configured_riot.get_match_timeline.assert_called_once_with("EUW1_1")
    assert session.scalar(select(func.count()).select_from(MatchParticipant)) == 10


def test_timeline_can_be_added_later(client, configured_riot):
    first = client.post(SYNC, params={"include_timeline": False})
    assert first.json()["imported"] == 1
    assert client.get(STORED).json()["items"][0]["timeline_available"] is False
    assert client.get("/api/matches/EUW1_1/timeline").status_code == 404
    second = client.post(SYNC)
    assert second.json()["timelines_added"] == 1
    configured_riot.get_match_details_by_match_id.assert_called_once()
    assert client.get(STORED).json()["items"][0]["timeline_available"] is True


def test_stored_reads_and_exports_do_not_call_riot(client, configured_riot, payload, timeline):
    client.post(SYNC)
    configured_riot.reset_mock()
    page = client.get(STORED).json()
    assert page["total"] == 1
    row = page["items"][0]
    assert row["puuid"] == "my-puuid"
    assert row["kills"] == 1
    assert row["deaths"] == 0
    assert row["queue_id"] == 420
    assert "raw_data" not in row
    detail = client.get("/api/matches/EUW1_1")
    assert detail.status_code == 200
    assert len(detail.json()["participants"]) == 10
    assert client.get("/api/matches/EUW1_1/raw").json() == payload
    assert client.get("/api/matches/EUW1_1/timeline").json() == timeline
    export = client.get("/api/players/jonnybravo/1998/matches/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert list(csv.DictReader(io.StringIO(export.text)))[0]["match_id"] == "EUW1_1"
    assert configured_riot.mock_calls == []


def test_queue_filter_pagination_and_empty_page(client, configured_riot, payload, timeline):
    client.post(SYNC)
    newer = deepcopy(payload)
    newer["metadata"]["matchId"] = "EUW1_2"
    newer["info"]["queueId"] = 450
    newer["info"]["gameStartTimestamp"] += 3600000
    configured_riot.get_match_details_by_match_id.return_value = newer
    configured_riot.get_match_timeline.return_value = {
        **timeline, "metadata": {"matchId": "EUW1_2"},
    }
    assert client.post("/api/matches/EUW1_2/sync").status_code == 200
    page = client.get(STORED, params={"count": 1}).json()
    assert page["total"] == 2
    assert page["items"][0]["match_id"] == "EUW1_2"
    assert client.get(STORED, params={"start": 1}).json()["items"][0]["match_id"] == "EUW1_1"
    filtered = client.get(STORED, params={"queue": 420}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["match_id"] == "EUW1_1"
    assert client.get(STORED, params={"start": 20}).json()["items"] == []


def test_rate_limit_keeps_previous_matches_and_reports_resume_position(client, configured_riot, payload):
    configured_riot.get_match_history_by_puuid.return_value = ["EUW1_1", "EUW1_2"]
    request = httpx.Request("GET", "https://europe.api.riotgames.com/test")
    error = httpx.HTTPStatusError("limited", request=request, response=httpx.Response(
        429, request=request, headers={"Retry-After": "60"}
    ))
    configured_riot.get_match_details_by_match_id.side_effect = [payload, error]
    response = client.post(SYNC, params={"start": 10, "queue": 420})
    result = response.json()
    assert result["completed"] is False
    assert result["imported"] == 1
    assert result["next_start"] == 11
    assert result["retry_after"] == "60"
    assert result["failures"][0]["upstream_status"] == 429
    assert client.get(STORED).json()["total"] == 1
    configured_riot.get_match_history_by_puuid.assert_called_once_with(
        "my-puuid", start=10, count=10, queue=420
    )


def test_timeline_failure_does_not_save_partial_match(client, configured_riot, session):
    configured_riot.get_match_timeline.side_effect = httpx.ReadTimeout("timeout")
    result = client.post(SYNC).json()
    assert result["completed"] is False
    assert result["next_start"] == 0
    assert result["imported"] == 0
    assert session.scalar(select(func.count()).select_from(Match)) == 0
    assert session.scalar(select(func.count()).select_from(MatchParticipant)) == 0


def test_bad_payload_is_rejected_without_writes(client, configured_riot, session):
    configured_riot.get_match_details_by_match_id.return_value = {"metadata": {"matchId": "OTHER_1"}}
    assert client.post("/api/matches/EUW1_1/sync").status_code == 502
    assert session.scalar(select(func.count()).select_from(Match)) == 0


def test_unknown_local_resources_return_404(client):
    assert client.get(STORED).status_code == 404
    assert client.get("/api/matches/EUW1_999").status_code == 404


@pytest.mark.parametrize("params", [{"count": 0}, {"count": 101}, {"start": -1}, {"queue": -1}])
def test_invalid_sync_parameters(client, configured_riot, params):
    assert client.post(SYNC, params=params).status_code == 422
    configured_riot.get_account_by_riot_id.assert_not_called()


def test_empty_riot_history(client, configured_riot):
    configured_riot.get_match_history_by_puuid.return_value = []
    result = client.post(SYNC).json()
    assert result["completed"] is True
    assert result["found"] == 0
    assert result["next_start"] == 0
    assert client.get(STORED).json()["total"] == 0


def test_legacy_duration_units(payload):
    payload["info"]["gameVersion"] = "11.19.1"
    payload["info"]["gameDuration"] = 1800000
    assert MatchService._build_match("EUW1_1", payload).duration_seconds == 1800


def test_missing_optional_fields_are_preserved_as_unknown(payload):
    for participant in payload["info"]["participants"]:
        for key in ("riotIdGameName", "riotIdTagline", "teamPosition", "timePlayed", "gameEndedInEarlySurrender"):
            participant.pop(key)
    participant = MatchService._build_match("EUW1_1", payload).participants[0]
    assert participant.game_name is None
    assert participant.time_played_seconds is None
    assert participant.game_ended_in_early_surrender is None


def test_riot_match_list_filters_and_timeline_path():
    with RiotClient("test") as riot, patch.object(riot.client, "get") as get:
        get.return_value = httpx.Response(200, request=httpx.Request("GET", "https://example.test"), json=[])
        riot.get_match_history_by_puuid("my-puuid", start=20, count=30, queue=420)
        assert get.call_args.kwargs["params"] == {"start": 20, "count": 30, "queue": 420}
        riot.get_match_timeline("EUW1_1")
        assert get.call_args.args[0] == "/lol/match/v5/matches/EUW1_1/timeline"


def test_original_player_endpoints_still_work(client):
    player = client.get("/api/players/jonnybravo/1998")
    assert player.status_code == 200
    assert player.json() == {"puuid": "my-puuid", "game_name": "JonnyBravo", "tag_line": "1998"}
    ids = client.get("/api/players/jonnybravo/1998/matches")
    assert ids.status_code == 200
    assert ids.json() == ["EUW1_1"]


def test_account_refresh_updates_name_and_timestamp_without_duplicate(client, configured_riot, session):
    client.post(SYNC)
    player = session.get(Player, "my-puuid")
    previous_update = player.last_updated
    configured_riot.get_account_by_riot_id.return_value = {
        "puuid": "my-puuid", "gameName": "NewName", "tagLine": "NEW",
    }
    assert client.post("/api/players/NewName/NEW/matches/sync").status_code == 200
    session.refresh(player)
    assert player.last_updated > previous_update
    assert session.scalar(select(func.count()).select_from(Player)) == 1
    assert client.get("/api/players/newname/new/matches/stored").json()["total"] == 1
    assert client.get(STORED).status_code == 404


def test_upstream_history_rate_limit_preserves_retry_after(client, configured_riot):
    request = httpx.Request("GET", "https://europe.api.riotgames.com/test")
    configured_riot.get_match_history_by_puuid.side_effect = httpx.HTTPStatusError(
        "limited", request=request,
        response=httpx.Response(429, request=request, headers={"Retry-After": "120"}),
    )
    response = client.post(SYNC)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "120"


def test_invalid_timeline_does_not_commit_details(client, configured_riot, session):
    configured_riot.get_match_timeline.return_value = {
        "metadata": {"matchId": "EUW1_999"}, "info": {"frames": []},
    }
    response = client.post("/api/matches/EUW1_1/sync")
    assert response.status_code == 502
    assert session.scalar(select(func.count()).select_from(Match)) == 0


@pytest.mark.parametrize("suffix", ["stored", "export"])
def test_invalid_local_page_size(client, suffix):
    response = client.get(f"/api/players/jonnybravo/1998/matches/{suffix}?count=1001")
    assert response.status_code == 422


def test_csv_has_headers_for_empty_dataset(client, configured_riot):
    configured_riot.get_match_history_by_puuid.return_value = []
    client.post(SYNC)
    response = client.get("/api/players/jonnybravo/1998/matches/export")
    reader = csv.DictReader(io.StringIO(response.text))
    assert "match_id" in reader.fieldnames
    assert list(reader) == []
