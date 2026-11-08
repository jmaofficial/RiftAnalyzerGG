"""Deterministic timeline extraction. No network calls or database writes."""
import re

from app.db.models import Match, MatchParticipant
from app.schemas.analysis import Checkpoint, MatchFeatures
from app.analysis.timeline import (
    MAX_SNAPSHOT_LAG_MS, combat_events, cs, difference, nonnegative_int, timeline_frames,
)
from app.analysis.phases import ProgressionExtractor


CHECKPOINT_MINUTES = (10, 15, 20)
POSITIONS = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}


def extract_features(match: Match, player: MatchParticipant) -> MatchFeatures:
    version = re.match(r"^(\d+\.\d+)\.", match.game_version)
    patch = version.group(1) if version else None
    reasons = []
    if match.queue_id != 420 or match.map_id != 11:
        reasons.append("unsupported_queue_or_map")
    if match.duration_seconds < 300 or player.game_ended_in_early_surrender:
        reasons.append("remake_or_early_surrender")
    if player.team_position not in POSITIONS:
        reasons.append("unknown_position")
    if patch is None:
        reasons.append("unknown_patch")

    opponents = [p for p in match.participants if (
        player.team_position in POSITIONS and p.team_id != player.team_id
        and p.team_position == player.team_position
    )]
    teammates_same_role = [p for p in match.participants if (
        p.team_id == player.team_id and p.team_position == player.team_position
    )]
    opponent = opponents[0] if len(opponents) == 1 and len(teammates_same_role) == 1 else None
    opponent_status = "matched" if opponent else (
        "ambiguous" if len(opponents) > 1 or len(teammates_same_role) > 1 else "unavailable"
    )
    frames, timeline_status = timeline_frames(match)
    if timeline_status != "available":
        reasons.append(timeline_status)
    events = combat_events(frames, {p.participant_id for p in match.participants}) if frames else None
    checkpoints = {}
    for minute in CHECKPOINT_MINUTES:
        cutoff = minute * 60_000
        status = "match_too_short" if match.duration_seconds * 1000 < cutoff else timeline_status
        checkpoint = Checkpoint(minute=minute, snapshot_status=status, combat_status=status)
        checkpoints[minute] = checkpoint
        if status != "available":
            continue

        # Count by event time, including events stored in the frame AFTER the cutoff.
        if frames[-1]["timestamp"] < cutoff:
            checkpoint.combat_status = "missing_frame"
        elif events is None:
            checkpoint.combat_status = "invalid_timeline"
        else:
            checkpoint.kills = checkpoint.deaths = checkpoint.assists = 0
            for event in events:
                if event["timestamp"] > cutoff:
                    continue
                checkpoint.kills += int(event["killerId"] == player.participant_id)
                checkpoint.deaths += int(event["victimId"] == player.participant_id)
                checkpoint.assists += int(player.participant_id in event.get("assistingParticipantIds", []))

        previous = [frame for frame in frames if frame["timestamp"] <= cutoff]
        if not previous:
            checkpoint.snapshot_status = "missing_frame"
            continue
        frame = previous[-1]
        checkpoint.snapshot_timestamp_ms = frame["timestamp"]
        checkpoint.snapshot_lag_ms = cutoff - frame["timestamp"]
        if checkpoint.snapshot_lag_ms > MAX_SNAPSHOT_LAG_MS:
            checkpoint.snapshot_status = "stale_frame"
            continue
        participant_frames = frame.get("participantFrames")
        own = participant_frames.get(str(player.participant_id)) if isinstance(participant_frames, dict) else None
        if not isinstance(own, dict) or own.get("participantId") != player.participant_id:
            checkpoint.snapshot_status = "missing_player_frame"
            continue
        checkpoint.gold = nonnegative_int(own.get("totalGold"))
        checkpoint.cs = cs(own)
        checkpoint.xp = nonnegative_int(own.get("xp"))
        other = participant_frames.get(str(opponent.participant_id), {}) if opponent else {}
        if (
            opponent is None or not isinstance(other, dict)
            or other.get("participantId") != opponent.participant_id
        ):
            other = {}
        checkpoint.gold_diff = difference(checkpoint.gold, nonnegative_int(other.get("totalGold")))
        checkpoint.cs_diff = difference(checkpoint.cs, cs(other))
        checkpoint.xp_diff = difference(checkpoint.xp, nonnegative_int(other.get("xp")))

        team_gold = {True: [], False: []}
        for participant in match.participants:
            data = participant_frames.get(str(participant.participant_id), {})
            gold = nonnegative_int(data.get("totalGold")) if (
                isinstance(data, dict) and data.get("participantId") == participant.participant_id
            ) else None
            team_gold[participant.team_id == player.team_id].append(gold)
        if all(team_gold.values()) and all(g is not None for values in team_gold.values() for g in values):
            checkpoint.team_gold_diff = sum(team_gold[True]) - sum(team_gold[False])

    windows, phases, followups = ProgressionExtractor(
        match, player, opponent, frames, timeline_status, events
    ).extract()
    return MatchFeatures(
        match_id=match.match_id, game_start=match.game_start, patch=patch,
        position=player.team_position, champion_name=player.champion_name,
        win=player.win, duration_seconds=match.duration_seconds,
        eligible=not reasons, exclusion_reasons=reasons,
        opponent_participant_id=opponent.participant_id if opponent else None,
        opponent_status=opponent_status, checkpoints=checkpoints,
        windows=windows, phases=phases, event_followups=followups,
    )
