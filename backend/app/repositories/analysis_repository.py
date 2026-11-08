from collections.abc import Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer, selectinload

from app.db.models import Match, MatchParticipant


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def select_matches(
        self, puuid: str, limit: int, position: str | None = None, patch: str | None = None,
        champion_id: int | None = None,
    ) -> tuple[int, Iterator[tuple[Match, MatchParticipant]]]:
        filters = [MatchParticipant.puuid == puuid, Match.queue_id == 420, Match.map_id == 11]
        if position is not None:
            filters.append(MatchParticipant.team_position == position)
        if patch is not None:
            filters.append(Match.game_version.startswith(patch + "."))
        if champion_id is not None:
            filters.append(MatchParticipant.champion_id == champion_id)
        query = (
            select(Match, MatchParticipant)
            .join(MatchParticipant, MatchParticipant.match_id == Match.match_id)
            .where(*filters)
        )
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        # Retain only feature rows in memory; load large timelines in small batches.
        rows = self.session.execute(
            query.options(
                defer(Match.raw_data), defer(MatchParticipant.raw_data),
                selectinload(Match.participants).defer(MatchParticipant.raw_data),
            ).order_by(Match.game_start.desc(), Match.match_id.desc()).limit(limit)
            .execution_options(yield_per=10)
        )
        return total, rows

    def filter_options(self, puuid: str):
        base = (
            select(MatchParticipant.champion_id, MatchParticipant.champion_name,
                   MatchParticipant.team_position)
            .join(Match, Match.match_id == MatchParticipant.match_id)
            .where(MatchParticipant.puuid == puuid, Match.queue_id == 420, Match.map_id == 11)
            .subquery()
        )
        # A champion ID is stable even if the payload's display name changes.
        champions = self.session.execute(
            select(base.c.champion_id, func.max(base.c.champion_name), func.count())
            .group_by(base.c.champion_id).order_by(func.max(base.c.champion_name))
        ).all()
        lanes = self.session.execute(
            select(base.c.team_position, func.count())
            .where(base.c.team_position.in_(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]))
            .group_by(base.c.team_position)
        ).all()
        return champions, lanes
