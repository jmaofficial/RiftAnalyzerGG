from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Player(Base):
    __tablename__ = "players"

    puuid: Mapped[str] = mapped_column(
        String(100),
        primary_key=True
    )

    game_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    tag_line: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


# JSON on SQLite for isolated tests; JSONB on PostgreSQL for querying raw data.
json_type = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    queue_id: Mapped[int] = mapped_column(Integer)
    map_id: Mapped[int] = mapped_column(Integer)
    game_mode: Mapped[str] = mapped_column(String(50))
    game_version: Mapped[str] = mapped_column(String(100))
    game_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    raw_data: Mapped[dict] = mapped_column(json_type)
    timeline_data: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    participants: Mapped[list["MatchParticipant"]] = relationship(
        back_populates="match", cascade="all, delete-orphan",
        order_by="MatchParticipant.participant_id",
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (Index("ix_match_participants_puuid", "puuid"),)

    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    participant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Participants do not need to have been searched for in the players table.
    puuid: Mapped[str] = mapped_column(String(100))
    game_name: Mapped[str | None] = mapped_column(String(100))
    tag_line: Mapped[str | None] = mapped_column(String(10))
    team_id: Mapped[int] = mapped_column(Integer)
    champion_id: Mapped[int] = mapped_column(Integer)
    champion_name: Mapped[str] = mapped_column(String(100))
    team_position: Mapped[str | None] = mapped_column(String(50))
    win: Mapped[bool] = mapped_column(Boolean)
    kills: Mapped[int] = mapped_column(Integer)
    deaths: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    champion_level: Mapped[int] = mapped_column(Integer)
    gold_earned: Mapped[int] = mapped_column(Integer)
    gold_spent: Mapped[int] = mapped_column(Integer)
    total_minions_killed: Mapped[int] = mapped_column(Integer)
    neutral_minions_killed: Mapped[int] = mapped_column(Integer)
    damage_to_champions: Mapped[int] = mapped_column(Integer)
    damage_taken: Mapped[int] = mapped_column(Integer)
    vision_score: Mapped[int] = mapped_column(Integer)
    wards_placed: Mapped[int] = mapped_column(Integer)
    wards_killed: Mapped[int] = mapped_column(Integer)
    time_played_seconds: Mapped[int | None] = mapped_column(Integer)
    game_ended_in_early_surrender: Mapped[bool | None] = mapped_column(Boolean)
    items: Mapped[list[int]] = mapped_column(json_type)
    summoner_spells: Mapped[list[int]] = mapped_column(json_type)
    raw_data: Mapped[dict] = mapped_column(json_type)
    match: Mapped[Match] = relationship(back_populates="participants")
