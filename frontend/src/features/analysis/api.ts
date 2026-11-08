import { request } from "../../lib/http";
import type {
  AnalysisOptions,
  AnalysisReport,
  Filters,
  PlayerIdentity,
  SyncResult,
} from "./types";

const playerPath = (player: PlayerIdentity) =>
  `/api/players/${encodeURIComponent(player.gameName)}/${encodeURIComponent(player.tagLine)}`;

export const analysisApi = {
  options: (player: PlayerIdentity, signal?: AbortSignal) =>
    request<AnalysisOptions>(`${playerPath(player)}/analysis/options`, {
      signal,
    }),
  lookup: (player: PlayerIdentity, signal?: AbortSignal) =>
    request(`${playerPath(player)}`, { signal }),
  report: (player: PlayerIdentity, filters: Filters, signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: String(filters.limit) });
    if (filters.lane) params.set("position", filters.lane);
    if (filters.championId) params.set("champion_id", filters.championId);
    return request<AnalysisReport>(`${playerPath(player)}/analysis?${params}`, {
      signal,
    });
  },
  sync: (player: PlayerIdentity, start: number) => {
    const params = new URLSearchParams({
      queue: "420",
      count: String(50 - start),
      start: String(start),
      include_timeline: "true",
    });
    return request<SyncResult>(`${playerPath(player)}/matches/sync?${params}`, {
      method: "POST",
    });
  },
};
