from sqlalchemy.orm import Session

from app.analysis.features import extract_features
from app.analysis.statistics import build_report
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.player_repository import PlayerRepository
from app.schemas.analysis import AnalysisFilters, AnalysisReport, FeatureDataset
from app.services.match_service import StoredPlayerNotFound


class AnalysisService:
    def __init__(self, session: Session):
        self.repository = AnalysisRepository(session)
        self.players = PlayerRepository(session)

    def features(
        self, game_name: str, tag_line: str, limit: int = 200,
        position: str | None = None, patch: str | None = None,
    ) -> FeatureDataset:
        player = self.players.get_by_riot_id(game_name, tag_line)
        if player is None:
            raise StoredPlayerNotFound("Player not stored. Sync matches before requesting analysis.")
        total, rows = self.repository.select_matches(player.puuid, limit, position, patch)
        items = [extract_features(match, participant) for match, participant in rows]
        return FeatureDataset(
            puuid=player.puuid,
            filters=AnalysisFilters(limit=limit, position=position, patch=patch),
            matched_total=total, selected_matches=len(items),
            eligible_matches=sum(row.eligible for row in items),
            truncated=total > len(items), items=items,
        )

    def report(
        self, game_name: str, tag_line: str, limit: int = 200,
        position: str | None = None, patch: str | None = None,
    ) -> AnalysisReport:
        return build_report(self.features(game_name, tag_line, limit, position, patch))
