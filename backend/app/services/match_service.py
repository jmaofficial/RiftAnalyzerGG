from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.riot_client import RiotClient
from app.db.models import Match, MatchParticipant
from app.repositories.match_repository import MatchRepository
from app.repositories.player_repository import PlayerRepository
from app.schemas.matches import MatchPage, MatchSample, ParticipantRead, SyncFailure, SyncResult
from app.services.player_service import PlayerService


class InvalidMatchData(ValueError):
    """Riot returned a payload that cannot safely be stored."""


class StoredPlayerNotFound(LookupError):
    pass


class MatchService:
    def __init__(self, session: Session, riot_client: RiotClient | None = None):
        self.riot_client = riot_client
        self.session = session
        self.repository = MatchRepository(session)

    def get_stored_match(self, match_id: str) -> Match | None:
        return self.repository.get_by_id(match_id)

    def get_stored_matches(
        self, game_name: str, tag_line: str, start: int = 0,
        count: int = 100, queue: int | None = None,
    ) -> MatchPage:
        player = PlayerRepository(self.session).get_by_riot_id(game_name, tag_line)
        if player is None:
            raise StoredPlayerNotFound("Player not stored. Sync the player first.")
        total, rows = self.repository.list_for_player(player.puuid, start, count, queue)
        items = []
        for match, participant, timeline_available in rows:
            items.append(MatchSample(
                **ParticipantRead.model_validate(participant).model_dump(),
                match_id=match.match_id, queue_id=match.queue_id, map_id=match.map_id,
                game_mode=match.game_mode, game_version=match.game_version,
                game_start=match.game_start, duration_seconds=match.duration_seconds,
                timeline_available=timeline_available,
            ))
        return MatchPage(total=total, start=start, count=count, items=items)

    def import_match(
        self, match_id: str, include_timeline: bool = True
    ) -> tuple[Match, str]:
        if self.riot_client is None:
            raise RuntimeError("A Riot client is required for importing matches")
        existing = self.repository.get_by_id(match_id)
        if existing is not None and (
            not include_timeline or existing.timeline_data is not None
        ):
            return existing, "already_stored"

        try:
            match = existing or self._build_match(
                match_id, self.riot_client.get_match_details_by_match_id(match_id)
            )
            if include_timeline:
                timeline = self.riot_client.get_match_timeline(match_id)
                if (
                    timeline.get("metadata", {}).get("matchId") != match_id
                    or not isinstance(timeline.get("info", {}).get("frames"), list)
                ):
                    raise InvalidMatchData("Riot returned an invalid match timeline")
                match.timeline_data = timeline
            if existing is None:
                self.repository.create(match)
            self.session.commit()
        except IntegrityError:
            # Another request may have imported this match after our initial SELECT.
            self.session.rollback()
            concurrent = self.repository.get_by_id(match_id)
            if concurrent is None:
                raise
            if include_timeline and concurrent.timeline_data is None:
                return self.import_match(match_id, include_timeline=True)
            return concurrent, "already_stored"
        except Exception:
            self.session.rollback()
            raise
        return match, "imported" if existing is None else "timeline_added"

    def sync_player_matches(
        self, game_name: str, tag_line: str, start: int = 0, count: int = 10,
        queue: int | None = None, include_timeline: bool = True,
    ) -> SyncResult:
        if self.riot_client is None:
            raise RuntimeError("A Riot client is required for syncing matches")
        player = PlayerService(self.riot_client, self.session).get_or_create_player(
            game_name, tag_line
        )
        puuid = player.puuid
        match_ids = self.riot_client.get_match_history_by_puuid(
            puuid, start=start, count=count, queue=queue
        )
        result = SyncResult(
            puuid=puuid, requested=count, found=len(match_ids),
            next_start=start + len(match_ids),
        )
        for offset, match_id in enumerate(match_ids):
            try:
                _, import_status = self.import_match(match_id, include_timeline)
            except (httpx.HTTPError, InvalidMatchData) as exc:
                # Commit per match: earlier successes survive a rate limit or timeout.
                self.session.rollback()
                result.completed = False
                result.next_start = start + offset
                status = None
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    result.retry_after = exc.response.headers.get("Retry-After")
                    detail = f"Riot returned HTTP {status}"
                elif isinstance(exc, InvalidMatchData):
                    detail = str(exc)
                else:
                    detail = "Unable to reach Riot API; retry this page"
                result.failures.append(SyncFailure(
                    match_id=match_id, detail=detail, upstream_status=status
                ))
                break
            if import_status == "imported":
                result.imported += 1
            elif import_status == "timeline_added":
                result.timelines_added += 1
            else:
                result.already_stored += 1
        return result

    @staticmethod
    def _build_match(match_id: str, payload: dict) -> Match:
        try:
            if payload["metadata"]["matchId"] != match_id:
                raise ValueError("Unexpected match ID")
            info = payload["info"]
            # Before patch 11.20 Riot reported gameDuration in milliseconds.
            version = tuple(int(part) for part in info["gameVersion"].split(".")[:2])
            duration = info["gameDuration"]
            if version < (11, 20):
                duration //= 1000
            match = Match(
                match_id=match_id, queue_id=info["queueId"], map_id=info["mapId"],
                game_mode=info["gameMode"], game_version=info["gameVersion"],
                game_start=datetime.fromtimestamp(info["gameStartTimestamp"] / 1000, timezone.utc),
                duration_seconds=duration, raw_data=payload,
            )
            participants = info["participants"]
            if not participants:
                raise ValueError("Missing participants")
            ids = [p["participantId"] for p in participants]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate participant IDs")
            for p in participants:
                match.participants.append(MatchParticipant(
                    participant_id=p["participantId"], puuid=p["puuid"],
                    game_name=p.get("riotIdGameName"), tag_line=p.get("riotIdTagline"),
                    team_id=p["teamId"], champion_id=p["championId"],
                    champion_name=p["championName"], team_position=p.get("teamPosition") or None,
                    win=p["win"], kills=p["kills"], deaths=p["deaths"], assists=p["assists"],
                    champion_level=p["champLevel"], gold_earned=p["goldEarned"],
                    gold_spent=p["goldSpent"], total_minions_killed=p["totalMinionsKilled"],
                    neutral_minions_killed=p["neutralMinionsKilled"],
                    damage_to_champions=p["totalDamageDealtToChampions"],
                    damage_taken=p["totalDamageTaken"], vision_score=p["visionScore"],
                    wards_placed=p["wardsPlaced"], wards_killed=p["wardsKilled"],
                    time_played_seconds=p.get("timePlayed"),
                    game_ended_in_early_surrender=p.get("gameEndedInEarlySurrender"),
                    items=[p.get(f"item{i}", 0) for i in range(7)],
                    summoner_spells=[p["summoner1Id"], p["summoner2Id"]], raw_data=p,
                ))
            return match
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise InvalidMatchData("Riot returned incomplete or invalid match data") from exc
