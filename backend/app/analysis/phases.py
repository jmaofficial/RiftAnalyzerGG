"""Phase/window progression and conservative spatial proxies from stored timelines."""
from app.analysis.spatial import classify_position
from app.analysis.timeline import MAX_SNAPSHOT_LAG_MS, cs, difference, nonnegative_int
from app.schemas.analysis import EventFollowup, SidelaneObservation, WindowFeatures


ACTIVITY_TYPES = {"BUILDING_KILL", "TURRET_PLATE_DESTROYED", "ELITE_MONSTER_KILL", "ITEM_PURCHASED"}


def participant_frame(frame, participant_id):
    frames = frame.get("participantFrames", {})
    own = frames.get(str(participant_id)) if isinstance(frames, dict) else None
    return own if isinstance(own, dict) and own.get("participantId") == participant_id else None


def increase(start, end, field):
    left = nonnegative_int(start.get(field))
    right = nonnegative_int(end.get(field))
    return right - left if left is not None and right is not None and right >= left else None


class ProgressionExtractor:
    def __init__(self, match, player, opponent, frames, timeline_status, combat_events):
        self.match = match
        self.player = player
        self.opponent = opponent
        self.frames = frames
        self.timeline_status = timeline_status
        self.combat_events = combat_events
        self.duration_ms = match.duration_seconds * 1000
        self.activity_events = self._activity_events()
        self.samples = {}

    def _activity_events(self):
        events = []
        ids = {p.participant_id for p in self.match.participants}
        for frame in self.frames:
            frame_events = frame.get("events")
            if not isinstance(frame_events, list):
                return None
            for event in frame_events:
                if not isinstance(event, dict):
                    return None
                if event.get("type") not in ACTIVITY_TYPES:
                    continue
                timestamp = nonnegative_int(event.get("timestamp"))
                if timestamp is None or timestamp > self.frames[-1]["timestamp"]:
                    return None
                if event["type"] == "ITEM_PURCHASED":
                    if nonnegative_int(event.get("participantId")) not in ids:
                        return None
                elif (
                    nonnegative_int(event.get("killerId")) not in ids | {0}
                    or not isinstance(event.get("assistingParticipantIds", []), list)
                    or any(type(pid) is not int or pid not in ids for pid in event.get("assistingParticipantIds", []))
                ):
                    return None
                if event["type"] == "BUILDING_KILL" and not isinstance(event.get("buildingType"), str):
                    return None
                events.append(event)
        return events

    def _sample(self, timestamp):
        if timestamp not in self.samples:
            previous = [frame for frame in self.frames if frame["timestamp"] <= timestamp]
            if not previous:
                sample = (None, None, "missing_frame")
            else:
                frame = previous[-1]
                if timestamp - frame["timestamp"] > MAX_SNAPSHOT_LAG_MS:
                    sample = (frame, None, "stale_frame")
                else:
                    own = participant_frame(frame, self.player.participant_id)
                    sample = (frame, own, "available" if own is not None else "missing_player_frame")
            self.samples[timestamp] = sample
        return self.samples[timestamp]

    def _role_difference(self, frame, own, metric):
        other = participant_frame(frame, self.opponent.participant_id) if self.opponent else None
        if other is None:
            return None
        if metric == "cs":
            return difference(cs(own), cs(other))
        return difference(nonnegative_int(own.get(metric)), nonnegative_int(other.get(metric)))

    def _team_gold_difference(self, frame):
        teams = {True: [], False: []}
        for participant in self.match.participants:
            data = participant_frame(frame, participant.participant_id)
            gold = nonnegative_int(data.get("totalGold")) if data is not None else None
            teams[participant.team_id == self.player.team_id].append(gold)
        if all(teams.values()) and all(value is not None for values in teams.values() for value in values):
            return sum(teams[True]) - sum(teams[False])
        return None

    def _sidelane(self, start, end):
        applicable = self.player.team_position == "MIDDLE" and self.match.map_id == 11
        result = SidelaneObservation(applicable=applicable, status="not_applicable")
        if not applicable:
            return result
        if self.timeline_status != "available":
            result.status = self.timeline_status
            return result
        result.status = "insufficient_position_data"
        if end <= start:
            return result
        seconds = {"top": 0.0, "bottom": 0.0, "observed": 0.0, "transition": 0.0}
        changes = {"totalGold": [], "minionsKilled": [], "jungleMinionsKilled": []}
        for before, after in zip(self.frames, self.frames[1:]):
            t0, t1 = before["timestamp"], after["timestamp"]
            # No proportional splitting of gold across window boundaries or long gaps.
            if t0 < start or t1 > end or not 0 < t1 - t0 <= MAX_SNAPSHOT_LAG_MS:
                continue
            own_before = participant_frame(before, self.player.participant_id)
            own_after = participant_frame(after, self.player.participant_id)
            if own_before is None or own_after is None:
                continue
            zone_before = classify_position(own_before.get("position"))
            zone_after = classify_position(own_after.get("position"))
            if zone_before is None or zone_after is None:
                continue
            elapsed = (t1 - t0) / 1000
            seconds["observed"] += elapsed
            if zone_before != zone_after:
                seconds["transition"] += elapsed
                continue
            if zone_before not in ("top", "bottom"):
                continue
            seconds[zone_before] += elapsed
            for metric in changes:
                changes[metric].append(increase(own_before, own_after, metric))
        if seconds["observed"] == 0:
            return result
        result.status = "available"
        result.observed_seconds = seconds["observed"]
        result.coverage_fraction = seconds["observed"] / ((end - start) / 1000)
        result.top_seconds = seconds["top"]
        result.bottom_seconds = seconds["bottom"]
        result.transition_seconds = seconds["transition"]
        result.sidelane_seconds = seconds["top"] + seconds["bottom"]
        result.sidelane_share_of_observed_time = result.sidelane_seconds / result.observed_seconds
        for metric, output in (
            ("totalGold", "gold_gained_during_sidelane_intervals"),
            ("minionsKilled", "lane_cs_gained_during_sidelane_intervals"),
            ("jungleMinionsKilled", "jungle_cs_gained_during_sidelane_intervals"),
        ):
            values = changes[metric]
            setattr(result, output, sum(values) if all(value is not None for value in values) else None)
        if result.sidelane_seconds and result.gold_gained_during_sidelane_intervals is not None:
            result.gold_per_observed_sidelane_minute = result.gold_gained_during_sidelane_intervals / (result.sidelane_seconds / 60)
        if result.sidelane_seconds and result.lane_cs_gained_during_sidelane_intervals is not None:
            result.lane_cs_per_observed_sidelane_minute = result.lane_cs_gained_during_sidelane_intervals / (result.sidelane_seconds / 60)
        return result

    def window(self, name, start, requested_end):
        end = min(requested_end, self.duration_ms)
        status = "not_reached" if end <= start else ("partial" if end < requested_end else "complete")
        data_status = "match_too_short" if status == "not_reached" else self.timeline_status
        result = WindowFeatures(
            name=name, requested_start_ms=start, requested_end_ms=requested_end,
            end_ms=end, duration_seconds=max(0, end - start) / 1000, status=status,
            snapshot_status=data_status, combat_status=data_status, activity_status=data_status,
            sidelane=self._sidelane(start, end),
        )
        if status == "not_reached" or self.timeline_status != "available":
            return result
        in_window = lambda event: (start < event["timestamp"] <= end or start == event["timestamp"] == 0)
        if self.frames[-1]["timestamp"] < end:
            result.combat_status = result.activity_status = "missing_frame"
        else:
            if self.combat_events is None:
                result.combat_status = "invalid_timeline"
            else:
                events = [event for event in self.combat_events if in_window(event)]
                pid = self.player.participant_id
                result.kills = sum(event["killerId"] == pid for event in events)
                result.deaths = sum(event["victimId"] == pid for event in events)
                result.assists = sum(pid in event.get("assistingParticipantIds", []) for event in events)
            if self.activity_events is None:
                result.activity_status = "invalid_timeline"
            else:
                events = [event for event in self.activity_events if in_window(event)]
                involved = lambda event: self.player.participant_id == event.get("killerId") or self.player.participant_id in event.get("assistingParticipantIds", [])
                result.tower_kill_participations = sum(event["type"] == "BUILDING_KILL" and event.get("buildingType") == "TOWER_BUILDING" and involved(event) for event in events)
                result.plate_last_hits = sum(event["type"] == "TURRET_PLATE_DESTROYED" and event.get("killerId") == self.player.participant_id for event in events)
                result.elite_monster_kill_participations = sum(event["type"] == "ELITE_MONSTER_KILL" and involved(event) for event in events)
                result.item_purchase_events = sum(event["type"] == "ITEM_PURCHASED" and event["participantId"] == self.player.participant_id for event in events)

        before, own_before, start_status = self._sample(start)
        after, own_after, end_status = self._sample(end)
        result.snapshot_status = start_status if start_status != "available" else end_status
        result.observed_start_ms = before["timestamp"] if before is not None else None
        result.observed_end_ms = after["timestamp"] if after is not None else None
        if end_status == "available":
            result.unspent_gold_at_end = nonnegative_int(own_after.get("currentGold"))
        if result.snapshot_status != "available":
            return result
        elapsed = (after["timestamp"] - before["timestamp"]) / 1000
        if elapsed <= 0:
            result.snapshot_status = "missing_frame"
            return result
        result.observed_duration_seconds = elapsed
        for field, output in (
            ("totalGold", "gold_gained"), ("minionsKilled", "lane_cs_gained"),
            ("jungleMinionsKilled", "jungle_cs_gained"), ("xp", "xp_gained"),
        ):
            setattr(result, output, increase(own_before, own_after, field))
        if result.lane_cs_gained is not None and result.jungle_cs_gained is not None:
            result.cs_gained = result.lane_cs_gained + result.jungle_cs_gained
            result.cs_per_minute = result.cs_gained / (elapsed / 60)
        if result.gold_gained is not None:
            result.gold_per_minute = result.gold_gained / (elapsed / 60)
        result.gold_diff_at_start = self._role_difference(before, own_before, "totalGold")
        result.gold_diff_at_end = self._role_difference(after, own_after, "totalGold")
        result.gold_diff_change = difference(result.gold_diff_at_end, result.gold_diff_at_start)
        result.cs_diff_change = difference(self._role_difference(after, own_after, "cs"), self._role_difference(before, own_before, "cs"))
        result.xp_diff_change = difference(self._role_difference(after, own_after, "xp"), self._role_difference(before, own_before, "xp"))
        result.team_gold_diff_at_start = self._team_gold_difference(before)
        return result

    def extract(self):
        windows = [self.window(f"{minute}_{minute + 5}", minute * 60000, (minute + 5) * 60000) for minute in range(0, 30, 5)]
        windows.append(self.window("30_end", 1800000, max(1800000, self.duration_ms)))
        phases = [
            self.window("laning", 0, 900000),
            self.window("midgame", 900000, 1500000),
            self.window("late_game", 1500000, max(1500000, self.duration_ms)),
        ]
        followups = []
        for event in sorted(self.combat_events or [], key=lambda event: event["timestamp"]):
            timestamp = event["timestamp"]
            if timestamp >= self.duration_ms:
                continue
            if event["killerId"] == self.player.participant_id:
                event_type = "after_kill"
            elif event["victimId"] == self.player.participant_id:
                event_type = "after_death"
            else:
                continue
            followups.append(EventFollowup(
                event_type=event_type, timestamp_ms=timestamp,
                event_zone=classify_position(event.get("position")),
                followup=self.window(event_type, timestamp, timestamp + 120000),
            ))
        return windows, phases, followups
