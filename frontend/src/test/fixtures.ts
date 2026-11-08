import type {
  AnalysisOptions,
  AnalysisReport,
  Lane,
  Metric,
} from "../features/analysis/types";

const metric = (win: number, loss: number): Metric => ({
  available_matches: 30,
  mean: (win + loss) / 2,
  win_matches: 15,
  win_mean: win,
  loss_matches: 15,
  loss_mean: loss,
});

export const options: AnalysisOptions = {
  game_name: "TestPlayer",
  tag_line: "EUW",
  stored_matches: 50,
  champions: [
    { champion_id: 1, champion_name: "Annie", matches: 30 },
    { champion_id: 2, champion_name: "Olaf", matches: 20 },
  ],
  lanes: [
    { position: "MIDDLE", matches: 40 },
    { position: "JUNGLE", matches: 10 },
  ],
};

export function makeReport(
  championId: number | null = null,
  lane: Lane | null = null,
): AnalysisReport {
  const position = lane || "MIDDLE";
  return {
    puuid: "synthetic-test-puuid",
    generated_at: "2026-11-08T12:00:00Z",
    feature_version: "timeline-v2",
    analysis_version: "associations-v2",
    status: "insufficient_data",
    filters: {
      limit: 50,
      champion_id: championId,
      position: lane,
      patch: null,
    },
    matched_total: 50,
    selected_matches: 50,
    eligible_matches: 46,
    truncated: false,
    excluded_matches_by_reason: { remake_or_early_surrender: 4 },
    cohorts: [
      { patch: "16.22", position, matches: 24, wins: 13 },
      { patch: "16.21", position, matches: 22, wins: 12 },
    ],
    tested_hypotheses: 0,
    minimum_cohort_matches: 30,
    minimum_group_matches: 10,
    multiple_testing_method: "holm",
    findings: [],
    phase_summaries: ["laning", "midgame", "late_game"].map((phase) => ({
      position,
      phase: phase as "laning" | "midgame" | "late_game",
      patches: ["16.21", "16.22"],
      pooling: "descriptive_across_patches",
      complete_matches: 30,
      partial_matches: 2,
      not_reached_matches: 14,
      metrics: {
        gold_per_minute: metric(443, 383),
        lane_cs_gained: metric(60, 67),
        kills: metric(3.4, 2.2),
        deaths: metric(2.2, 2.2),
        assists: metric(4, 2.5),
        "sidelane.sidelane_share_of_observed_time": metric(0.05, 0.04),
        "sidelane.gold_gained_during_sidelane_intervals": metric(145, 185),
        "sidelane.coverage_fraction": metric(0.92, 0.91),
      },
    })),
    limitations: ["Exploratory associations, not causal effects."],
  };
}
