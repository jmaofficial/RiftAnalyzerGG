"""Shared validated timeline access and numeric helpers."""
from app.db.models import Match


MAX_SNAPSHOT_LAG_MS = 90_000


def nonnegative_int(value) -> int | None:
    return value if type(value) is int and value >= 0 else None


def cs(frame: dict) -> int | None:
    lane = nonnegative_int(frame.get("minionsKilled"))
    jungle = nonnegative_int(frame.get("jungleMinionsKilled"))
    return lane + jungle if lane is not None and jungle is not None else None


def difference(left: int | None, right: int | None) -> int | None:
    return left - right if left is not None and right is not None else None


def timeline_frames(match: Match) -> tuple[list[dict], str]:
    timeline = match.timeline_data
    if timeline is None:
        return [], "missing_timeline"
    try:
        if timeline["metadata"]["matchId"] != match.match_id:
            return [], "invalid_timeline"
        frames = timeline["info"]["frames"]
        if not isinstance(frames, list) or not frames:
            return [], "invalid_timeline"
        timestamps = [nonnegative_int(frame["timestamp"]) for frame in frames]
        if None in timestamps or len(timestamps) != len(set(timestamps)):
            return [], "invalid_timeline"
        # The first frame establishes coverage from game start for combat events.
        ordered = sorted(frames, key=lambda frame: frame["timestamp"])
        if ordered[0]["timestamp"] != 0:
            return [], "invalid_timeline"
        mapping = timeline["info"]["participants"]
        expected = {p.participant_id: p.puuid for p in match.participants}
        actual = {p["participantId"]: p["puuid"] for p in mapping}
        if actual != expected or len(mapping) != len(actual):
            return [], "invalid_timeline"
        return ordered, "available"
    except (KeyError, TypeError, AttributeError):
        return [], "invalid_timeline"


def combat_events(frames: list[dict], participant_ids: set[int]) -> list[dict] | None:
    events = []
    for frame in frames:
        frame_events = frame.get("events")
        if not isinstance(frame_events, list):
            return None
        for event in frame_events:
            if not isinstance(event, dict):
                return None
            if event.get("type") != "CHAMPION_KILL":
                continue
            timestamp = nonnegative_int(event.get("timestamp"))
            killer = nonnegative_int(event.get("killerId"))
            victim = nonnegative_int(event.get("victimId"))
            assists = event.get("assistingParticipantIds", [])
            if (
                timestamp is None or timestamp > frames[-1]["timestamp"]
                or victim not in participant_ids
                or killer not in participant_ids | {0}
                or not isinstance(assists, list)
                or any(type(pid) is not int or pid not in participant_ids for pid in assists)
            ):
                return None
            events.append(event)
    return events


