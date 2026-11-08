from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer, selectinload

from app.db.models import Match, MatchParticipant


class MatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, match_id: str) -> Match | None:
        return self.session.scalar(
            select(Match)
            .where(Match.match_id == match_id)
            .options(selectinload(Match.participants))
        )

    def create(self, match: Match) -> None:
        self.session.add(match)
        self.session.flush()

    def list_for_player(
        self, puuid: str, start: int, count: int, queue: int | None = None
    ) -> tuple[int, list[tuple[Match, MatchParticipant, bool]]]:
        filters = [MatchParticipant.puuid == puuid]
        if queue is not None:
            filters.append(Match.queue_id == queue)
        base = (
            select(Match, MatchParticipant, Match.timeline_data.is_not(None))
            .join(MatchParticipant, MatchParticipant.match_id == Match.match_id)
            .where(*filters)
        )
        total = self.session.scalar(select(func.count()).select_from(base.subquery()))
        rows = self.session.execute(
            base.options(
                defer(Match.raw_data), defer(Match.timeline_data),
                defer(MatchParticipant.raw_data),
            ).order_by(Match.game_start.desc(), Match.match_id.desc())
            .offset(start).limit(count)
        ).all()
        return total, rows
