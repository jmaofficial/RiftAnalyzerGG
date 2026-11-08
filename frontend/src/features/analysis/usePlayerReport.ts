import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/http";
import { analysisApi } from "./api";
import type {
  AnalysisOptions,
  AnalysisReport,
  Filters,
  PlayerIdentity,
} from "./types";

const defaults: Filters = { championId: "", lane: "", limit: 50 };
const aborted = (error: unknown) =>
  error instanceof Error && error.name === "AbortError";
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Unable to load this report.";

export function usePlayerReport() {
  const [player, setPlayer] = useState<PlayerIdentity | null>(null);
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [filters, setFilters] = useState<Filters>(defaults);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resumeStart, setResumeStart] = useState(0);
  const [canSkip, setCanSkip] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [revision, setRevision] = useState(0);
  const searchRequest = useRef<AbortController | null>(null);

  useEffect(() => () => searchRequest.current?.abort(), []);
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(
      () => setCooldown((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const search = useCallback(async (identity: PlayerIdentity) => {
    searchRequest.current?.abort();
    const controller = new AbortController();
    searchRequest.current = controller;
    setSearching(true);
    setLoading(false);
    setPlayer(null);
    setOptions(null);
    setReport(null);
    setError(null);
    setNotice(null);
    setResumeStart(0);
    setPaused(false);
    setCooldown(0);
    setCanSkip(false);
    try {
      let data: AnalysisOptions;
      try {
        data = await analysisApi.options(identity, controller.signal);
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error;
        await analysisApi.lookup(identity, controller.signal);
        data = await analysisApi.options(identity, controller.signal);
      }
      if (controller.signal.aborted) return;
      setOptions(data);
      setFilters(defaults);
      setPlayer({ gameName: data.game_name, tagLine: data.tag_line });
    } catch (error) {
      if (!aborted(error)) setError(message(error));
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }, []);

  useEffect(() => {
    if (!player) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setReport(null);
    setError(null);
    analysisApi
      .report(player, filters, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setReport(data);
      })
      .catch((error) => {
        if (!aborted(error)) setError(message(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [player, filters, revision]);

  const refresh = async () => {
    if (!player) return;
    setRefreshing(true);
    try {
      setOptions(await analysisApi.options(player));
    } catch {
      setNotice(
        (current) =>
          `${current ? `${current} ` : ""}Some player details could not be refreshed. Try Refresh report again.`,
      );
    } finally {
      // Retry the report even if refreshing filter choices failed.
      setRevision((value) => value + 1);
      setRefreshing(false);
    }
  };

  const sync = async () => {
    if (!player || syncing || cooldown > 0) return;
    setSyncing(true);
    setError(null);
    setNotice(
      "Importing up to 50 ranked matches and timelines. This can take a few minutes.",
    );
    setCanSkip(false);
    try {
      const result = await analysisApi.sync(player, resumeStart);
      if (!result.completed) {
        setPaused(true);
        setResumeStart(result.next_start);
        const retry = Number(result.retry_after);
        setCooldown(Number.isFinite(retry) && retry > 0 ? Math.ceil(retry) : 0);
        const failed = result.failures[0];
        setCanSkip(failed?.upstream_status === 404);
        setNotice(
          failed?.upstream_status === 429
            ? `Riot paused the import. ${result.next_start} of the latest 50 matches have been checked. Your saved matches are safe; continue when the timer ends.`
            : `Import paused at match ${result.next_start + 1}. Earlier matches are saved. ${failed?.detail || "Please try continuing."}`,
        );
      } else {
        setPaused(false);
        const checked = resumeStart + result.found;
        setResumeStart(0);
        setNotice(
          `Import complete. ${checked} recent ranked matches checked. Your report uses the current filters.`,
        );
      }
    } catch (error) {
      setPaused(true);
      if (error instanceof ApiError && error.retryAfter)
        setCooldown(Math.ceil(error.retryAfter));
      setError(message(error));
      setNotice(
        `The update did not finish. ${message(error)} Matches already saved remain available. Try updating again.`,
      );
    } finally {
      // A failed response can still follow committed matches. Always re-read them.
      await refresh();
      setSyncing(false);
    }
  };

  return {
    player,
    options,
    report,
    filters,
    setFilters,
    searching,
    loading,
    syncing,
    refreshing,
    paused,
    error,
    notice,
    resumeStart,
    cooldown,
    canSkip,
    search,
    sync,
    refresh,
    retry: refresh,
    skip: () => {
      if (resumeStart >= 49) {
        setResumeStart(0);
        setPaused(false);
        setNotice(
          "Import finished with the final unavailable match skipped. All other saved matches remain in your report.",
        );
      } else {
        setResumeStart((value) => value + 1);
        setNotice(
          "Unavailable match skipped. Continue the import to fetch the remaining matches.",
        );
      }
      setCanSkip(false);
    },
  };
}
