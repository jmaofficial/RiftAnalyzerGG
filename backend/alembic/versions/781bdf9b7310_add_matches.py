"""Store match details, participants and timelines.

Revision ID: 781bdf9b7310
Revises: 2eef2dcd059b
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "781bdf9b7310"
down_revision = "2eef2dcd059b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("match_id", sa.String(100), primary_key=True),
        sa.Column("queue_id", sa.Integer(), nullable=False),
        sa.Column("map_id", sa.Integer(), nullable=False),
        sa.Column("game_mode", sa.String(50), nullable=False),
        sa.Column("game_version", sa.String(100), nullable=False),
        sa.Column("game_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("timeline_data", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_matches_game_start", "matches", ["game_start"])
    op.create_table(
        "match_participants",
        sa.Column("match_id", sa.String(100), sa.ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("participant_id", sa.Integer(), primary_key=True),
        sa.Column("puuid", sa.String(100), nullable=False),
        sa.Column("game_name", sa.String(100), nullable=True),
        sa.Column("tag_line", sa.String(10), nullable=True),
        sa.Column("champion_name", sa.String(100), nullable=False),
        sa.Column("team_position", sa.String(50), nullable=True),
        sa.Column("win", sa.Boolean(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in (
            "team_id", "champion_id", "kills", "deaths", "assists", "champion_level",
            "gold_earned", "gold_spent", "total_minions_killed", "neutral_minions_killed",
            "damage_to_champions", "damage_taken", "vision_score", "wards_placed", "wards_killed",
        )],
        sa.Column("time_played_seconds", sa.Integer(), nullable=True),
        sa.Column("game_ended_in_early_surrender", sa.Boolean(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("summoner_spells", postgresql.JSONB(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_match_participants_puuid", "match_participants", ["puuid"])


def downgrade() -> None:
    op.drop_table("match_participants")
    op.drop_table("matches")
