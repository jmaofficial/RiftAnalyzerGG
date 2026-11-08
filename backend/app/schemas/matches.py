from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    participant_id: int
    puuid: str
    game_name: str | None
    tag_line: str | None
    team_id: int
    champion_id: int
    champion_name: str
    team_position: str | None
    win: bool
    kills: int
    deaths: int
    assists: int
    champion_level: int
    gold_earned: int
    gold_spent: int
    total_minions_killed: int
    neutral_minions_killed: int
    damage_to_champions: int
    damage_taken: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    time_played_seconds: int | None
    game_ended_in_early_surrender: bool | None
    items: list[int]
    summoner_spells: list[int]


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: str
    queue_id: int
    map_id: int
    game_mode: str
    game_version: str
    game_start: datetime
    duration_seconds: int
    fetched_at: datetime
    participants: list[ParticipantRead]


class MatchSample(ParticipantRead):
    """One flat row per match for the requested player, ready for pandas/CSV."""

    match_id: str
    queue_id: int
    map_id: int
    game_mode: str
    game_version: str
    game_start: datetime
    duration_seconds: int
    timeline_available: bool


class MatchPage(BaseModel):
    total: int
    start: int
    count: int
    items: list[MatchSample]


class SyncFailure(BaseModel):
    match_id: str
    detail: str
    upstream_status: int | None = None


class SyncResult(BaseModel):
    puuid: str
    requested: int
    found: int
    imported: int = 0
    already_stored: int = 0
    timelines_added: int = 0
    completed: bool = True
    next_start: int
    retry_after: str | None = None
    failures: list[SyncFailure] = Field(default_factory=list)


class MatchImportResult(BaseModel):
    match_id: str
    status: Literal["imported", "already_stored", "timeline_added"]
    timeline_available: bool
