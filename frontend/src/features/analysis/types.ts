export type Lane = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";
export interface PlayerIdentity {
  gameName: string;
  tagLine: string;
}
export interface Filters {
  championId: string;
  lane: Lane | "";
  limit: number;
}
export interface AnalysisOptions {
  game_name: string;
  tag_line: string;
  stored_matches: number;
  champions: { champion_id: number; champion_name: string; matches: number }[];
  lanes: { position: Lane; matches: number }[];
}
export interface Metric {
  available_matches: number;
  mean: number | null;
  win_matches: number;
  win_mean: number | null;
  loss_matches: number;
  loss_mean: number | null;
}
export type Phase = "laning" | "midgame" | "late_game";
export interface PhaseSummary {
  position: Lane;
  phase: Phase;
  patches: string[];
  pooling: string;
  complete_matches: number;
  partial_matches: number;
  not_reached_matches: number;
  metrics: Record<string, Metric>;
}
export interface OutcomeGroup {
  label: string;
  matches: number;
  wins: number;
  win_rate: number | null;
  win_rate_ci95: { lower: number; upper: number } | null;
  match_ids: string[];
}
export interface Finding {
  finding_id: string;
  rule_id: string;
  patch: string;
  position: Lane;
  minute: number;
  group_a: OutcomeGroup;
  group_b: OutcomeGroup;
  win_rate_difference_pp: number | null;
  adjusted_p_value: number | null;
  summary: string | null;
}
export interface AnalysisReport {
  puuid: string;
  generated_at: string;
  feature_version: string;
  analysis_version: string;
  status: "insufficient_data" | "no_supported_findings" | "findings_available";
  filters: {
    limit: number;
    position: Lane | null;
    champion_id: number | null;
    patch: string | null;
  };
  matched_total: number;
  selected_matches: number;
  eligible_matches: number;
  truncated: boolean;
  excluded_matches_by_reason: Record<string, number>;
  cohorts: { patch: string; position: Lane; matches: number; wins: number }[];
  tested_hypotheses: number;
  minimum_cohort_matches: number;
  minimum_group_matches: number;
  multiple_testing_method: string;
  findings: Finding[];
  phase_summaries: PhaseSummary[];
  limitations: string[];
}
export interface SyncResult {
  imported: number;
  already_stored: number;
  timelines_added: number;
  completed: boolean;
  found: number;
  next_start: number;
  retry_after: string | null;
  failures: {
    match_id: string;
    detail: string;
    upstream_status: number | null;
  }[];
}
