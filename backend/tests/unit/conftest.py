import os
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Never use backend/.env or a real Riot key in automated tests.
os.environ["RIOT_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite://"

from app.api.dependencies import get_riot_client, get_session
from app.db.database import Base
from app.main import app


@pytest.fixture
def session():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    if url != "sqlite://" and not url.rsplit("/", 1)[-1].startswith("riftanalyzer_test_"):
        raise RuntimeError("TEST_DATABASE_URL must point to a riftanalyzer_test_* database")
    kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url == "sqlite://" else {}
    engine = create_engine(url, **kwargs)
    if url == "sqlite://":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def riot():
    client = MagicMock()
    client.get_account_by_riot_id.return_value = {
        "puuid": "my-puuid", "gameName": "JonnyBravo", "tagLine": "1998",
    }
    client.get_match_history_by_puuid.return_value = ["EUW1_1"]
    return client


@pytest.fixture
def payload():
    participants = []
    for index in range(1, 11):
        participants.append({
            "participantId": index, "puuid": "my-puuid" if index == 1 else f"opponent-{index}",
            "riotIdGameName": "JonnyBravo" if index == 1 else f"Player{index}",
            "riotIdTagline": "1998", "teamId": 100 if index <= 5 else 200,
            "championId": 1, "championName": "Annie", "teamPosition": "MIDDLE",
            "win": index <= 5, "kills": index, "deaths": 0, "assists": 4,
            "champLevel": 18, "goldEarned": 15000, "goldSpent": 14000,
            "totalMinionsKilled": 200, "neutralMinionsKilled": 5,
            "totalDamageDealtToChampions": 25000, "totalDamageTaken": 18000,
            "visionScore": 30, "wardsPlaced": 10, "wardsKilled": 2,
            "timePlayed": 1800, "gameEndedInEarlySurrender": False,
            "item0": 1001, "summoner1Id": 4, "summoner2Id": 14,
            "perks": {"styles": [{"style": 8100}]}, "challenges": {"kda": 5},
        })
    return {
        "metadata": {"matchId": "EUW1_1", "participants": [p["puuid"] for p in participants]},
        "info": {
            "gameVersion": "16.22.1", "gameDuration": 1800,
            "gameStartTimestamp": 1794168000000, "queueId": 420,
            "mapId": 11, "gameMode": "CLASSIC", "participants": participants,
            "teams": [{"teamId": 100, "objectives": {"dragon": {"kills": 3}}}],
        },
    }


@pytest.fixture
def timeline():
    return {
        "metadata": {"matchId": "EUW1_1"},
        "info": {"frames": [{"timestamp": 60000, "participantFrames": {}, "events": []}]},
    }


@pytest.fixture
def configured_riot(riot, payload, timeline):
    riot.get_match_details_by_match_id.return_value = deepcopy(payload)
    riot.get_match_timeline.return_value = deepcopy(timeline)
    return riot


@pytest.fixture
def client(session, configured_riot):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_riot_client] = lambda: configured_riot
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
