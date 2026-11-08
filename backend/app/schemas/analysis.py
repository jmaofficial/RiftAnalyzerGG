from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Position = Literal["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
DataStatus = Literal[
    "available", "match_too_short", "missing_timeline", "invalid_timeline",
    "missing_frame", "stale_frame", "missing_player_frame",
]


class Checkpoint(BaseModel):
    minute: int
    snapshot_status: DataStatus
    combat_status: DataStatus
    snapshot_timestamp_ms: int | None = None
    snapshot_lag_ms: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    gold: int | None = None
    cs: int | None = None
    xp: int | None = None
    gold_diff: int | None = None
    cs_diff: int | None = None
    xp_diff: int | None = None
    team_gold_diff: int | None = None


class SidelaneObservation(BaseModel):
    applicable: bool
    status: Literal["available", "not_applicable", "insufficient_position_data", "missing_timeline", "invalid_timeline"]
    method: str = "same_zone_endpoints_v1"
    observed_seconds: float = 0
    coverage_fraction: float | None = None
    sidelane_seconds: float | None = None
    top_seconds: float | None = None
    bottom_seconds: float | None = None
    transition_seconds: float | None = None
    sidelane_share_of_observed_time: float | None = None
    gold_gained_during_sidelane_intervals: int | None = None
    lane_cs_gained_during_sidelane_intervals: int | None = None
    jungle_cs_gained_during_sidelane_intervals: int | None = None
    gold_per_observed_sidelane_minute: float | None = None
    lane_cs_per_observed_sidelane_minute: float | None = None
    attribution: Literal["spatial_proxy_not_gold_source"] = "spatial_proxy_not_gold_source"


class WindowFeatures(BaseModel):
    name: str
    requested_start_ms: int
    requested_end_ms: int
    end_ms: int
    duration_seconds: float
    status: Literal["complete", "partial", "not_reached"]
    snapshot_status: DataStatus
    combat_status: DataStatus
    activity_status: DataStatus
    observed_start_ms: int | None = None
    observed_end_ms: int | None = None
    observed_duration_seconds: float | None = None
    gold_gained: int | None = None
    lane_cs_gained: int | None = None
    jungle_cs_gained: int | None = None
    cs_gained: int | None = None
    xp_gained: int | None = None
    gold_per_minute: float | None = None
    cs_per_minute: float | None = None
    unspent_gold_at_end: int | None = None
    gold_diff_at_start: int | None = None
    gold_diff_at_end: int | None = None
    gold_diff_change: int | None = None
    cs_diff_change: int | None = None
    xp_diff_change: int | None = None
    team_gold_diff_at_start: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    tower_kill_participations: int | None = None
    plate_last_hits: int | None = None
    elite_monster_kill_participations: int | None = None
    item_purchase_events: int | None = None
    sidelane: SidelaneObservation


class EventFollowup(BaseModel):
    event_type: Literal["after_kill", "after_death"]
    timestamp_ms: int
    event_zone: str | None
    followup: WindowFeatures


class MatchFeatures(BaseModel):
    match_id: str
    game_start: datetime
    patch: str | None
    position: str | None
    champion_name: str
    win: bool
    duration_seconds: int
    eligible: bool
    exclusion_reasons: list[str] = Field(default_factory=list)
    opponent_participant_id: int | None = None
    opponent_status: Literal["matched", "unavailable", "ambiguous"]
    checkpoints: dict[int, Checkpoint]
    windows: list[WindowFeatures] = Field(default_factory=list)
    phases: list[WindowFeatures] = Field(default_factory=list)
    event_followups: list[EventFollowup] = Field(default_factory=list)


class AnalysisFilters(BaseModel):
    queue_id: int = 420
    map_id: int = 11
    limit: int
    position: Position | None = None
    patch: str | None = None


class FeatureDataset(BaseModel):
    puuid: str
    feature_version: str = "timeline-v2"
    filters: AnalysisFilters
    matched_total: int
    selected_matches: int
    eligible_matches: int
    truncated: bool
    items: list[MatchFeatures]


class Interval(BaseModel):
    lower: float
    upper: float


class OutcomeGroup(BaseModel):
    label: str
    matches: int
    wins: int
    win_rate: float | None
    win_rate_ci95: Interval | None
    match_ids: list[str]


class Comparison(BaseModel):
    finding_id: str
    rule_id: str
    patch: str
    position: str
    minute: int
    metric: str
    group_a: OutcomeGroup
    group_b: OutcomeGroup
    missing_or_inapplicable_matches: int
    win_rate_difference_pp: float | None = None
    difference_ci95_pp: Interval | None = None
    p_value: float | None = None
    adjusted_p_value: float | None = None
    status: Literal["insufficient_data", "not_supported", "supported_association"]
    direction: Literal["higher_in_group_a", "higher_in_group_b"] | None = None
    interpretation: Literal["association_only"] = "association_only"
    summary: str | None = None


class CohortSummary(BaseModel):
    patch: str
    position: str
    matches: int
    wins: int


class DescriptiveMetric(BaseModel):
    available_matches: int
    mean: float | None
    win_matches: int
    win_mean: float | None
    loss_matches: int
    loss_mean: float | None


class PhaseSummary(BaseModel):
    position: str
    phase: str
    patches: list[str]
    pooling: Literal["descriptive_across_patches"] = "descriptive_across_patches"
    complete_matches: int
    partial_matches: int
    not_reached_matches: int
    metrics: dict[str, DescriptiveMetric]


class AnalysisReport(BaseModel):
    puuid: str
    generated_at: datetime
    feature_version: str = "timeline-v2"
    analysis_version: str = "associations-v2"
    status: Literal["insufficient_data", "no_supported_findings", "findings_available"]
    filters: AnalysisFilters
    matched_total: int
    selected_matches: int
    eligible_matches: int
    truncated: bool
    excluded_matches_by_reason: dict[str, int]
    cohorts: list[CohortSummary]
    tested_hypotheses: int
    minimum_cohort_matches: int = 30
    minimum_group_matches: int = 10
    minimum_difference_pp: float = 10
    significance_level: float = 0.05
    multiple_testing_method: str = "holm"
    confidence_interval_note: str = "95% pointwise intervals; not simultaneous or multiplicity-adjusted"
    comparisons: list[Comparison]
    findings: list[Comparison]
    phase_summaries: list[PhaseSummary] = Field(default_factory=list)
    limitations: list[str]
