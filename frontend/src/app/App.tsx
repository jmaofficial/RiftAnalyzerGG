import {
  ArrowRight,
  CircleAlert,
  Crosshair,
  Layers3,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Shell } from "../components/Shell";
import { PlayerSearch } from "../features/player/PlayerSearch";
import { ReportFilters } from "../features/analysis/components/ReportFilters";
import { ReportOverview } from "../features/analysis/components/ReportOverview";
import { PhaseBreakdown } from "../features/analysis/components/PhaseBreakdown";
import { PatternFindings } from "../features/analysis/components/PatternFindings";
import { usePlayerReport } from "../features/analysis/usePlayerReport";
import { championName, laneName } from "../lib/format";

export default function App() {
  const state = usePlayerReport();
  const selectedChampion = state.options?.champions.find(
    (champion) => String(champion.champion_id) === state.filters.championId,
  );
  const report = state.report;
  return (
    <Shell>
      <div className="page-body">
        <header className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="eyebrow-line" /> YOUR NEXT LEVEL STARTS WITH
              UNDERSTANDING
            </div>
            <h1>
              Your games.
              <br />
              <span>A clearer game plan.</span>
            </h1>
            <p>
              Look beyond wins and losses. Find the patterns in your play,
              <br className="desktop-break" /> one champion, lane and game phase
              at a time.
            </p>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="rift-orbit orbit-one" />
            <div className="rift-orbit orbit-two" />
            <div className="rift-core">
              <Crosshair size={75} strokeWidth={0.8} />
            </div>
            <span className="art-coordinate coordinate-one">ANALYZE</span>
            <span className="art-coordinate coordinate-two">ADAPT</span>
            <span className="art-coordinate coordinate-three">IMPROVE</span>
          </div>
        </header>
        <section className="search-section" aria-label="Find a player">
          <PlayerSearch
            onSearch={state.search}
            searching={state.searching}
            disabled={state.syncing || state.refreshing}
          />
          <div className="search-hint">
            <span className="region-dot" /> Europe <span>·</span> Ranked Solo /
            Duo <span>·</span> Search with your Riot ID
          </div>
        </section>
        {state.error && (
          <div className="notice error-notice" role="alert">
            <CircleAlert size={18} />
            <div>
              <strong>We couldn’t finish that request.</strong>
              <p>{state.error}</p>
            </div>
            {state.player && (
              <button className="text-button" onClick={state.retry}>
                Retry report
              </button>
            )}
          </div>
        )}
        {state.player && state.options && (
          <>
            <div className="player-heading">
              <div className="player-identity">
                <div className="player-avatar">
                  {state.player.gameName.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h2>
                    {state.player.gameName}
                    <span>#{state.player.tagLine}</span>
                  </h2>
                  <p>
                    {state.options.stored_matches} stored ranked matches ·{" "}
                    {selectedChampion
                      ? championName(selectedChampion.champion_name)
                      : "All champions"}{" "}
                    ·{" "}
                    {state.filters.lane
                      ? laneName(state.filters.lane)
                      : "All lanes"}
                  </p>
                </div>
              </div>
              <div className="player-actions">
                <button
                  className="button button-quiet"
                  onClick={() => void state.refresh()}
                  disabled={state.syncing || state.refreshing || state.loading}
                >
                  <RefreshCw
                    className={state.refreshing || state.loading ? "spin" : ""}
                    size={15}
                  />
                  {state.refreshing || state.loading
                    ? "Refreshing…"
                    : "Refresh report"}
                </button>
                <button
                  className="button button-primary"
                  onClick={() => void state.sync()}
                  disabled={
                    state.syncing || state.refreshing || state.cooldown > 0
                  }
                >
                  {state.syncing ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <RefreshCw size={15} />
                  )}
                  {state.syncing
                    ? "Importing matches…"
                    : state.cooldown > 0
                      ? `Continue in ${state.cooldown}s`
                      : state.paused
                        ? "Try update again"
                        : "Update matches"}
                </button>
              </div>
            </div>
            <p className="update-hint">
              Your report uses stored matches. Update matches checks Riot for up
              to 50 recent ranked games; Refresh report reloads the saved data.
              Champion and lane filters still apply.
            </p>
            {state.notice && (
              <div className="notice" role="status">
                <RefreshCw className={state.syncing ? "spin" : ""} size={17} />
                <p>{state.notice}</p>
                {state.canSkip && (
                  <button className="text-button" onClick={state.skip}>
                    Skip unavailable match
                  </button>
                )}
              </div>
            )}
            <ReportFilters
              options={state.options}
              filters={state.filters}
              onChange={state.setFilters}
              disabled={state.syncing || state.searching}
            />
          </>
        )}
        {(state.searching || (state.loading && state.player)) && (
          <div className="loading-panel" role="status">
            <LoaderCircle size={26} className="spin" />
            <h3>
              {state.searching
                ? "Finding your player…"
                : "Looking closer at your matches…"}
            </h3>
            <p>Building your report from stored match timelines.</p>
          </div>
        )}
        {!state.searching && !state.loading && report && (
          <>
            {report.selected_matches > 0 ? (
              <>
                <ReportOverview report={report} />
                <PhaseBreakdown
                  key={`${state.player?.gameName}:${state.filters.championId}:${state.filters.lane}:${state.filters.limit}:${report.generated_at}`}
                  report={report}
                />
                <PatternFindings report={report} />
              </>
            ) : (
              <div className="panel empty-report">
                <Layers3 size={32} />
                <h2>
                  {state.options?.stored_matches
                    ? "No matches for this combination."
                    : "Your first report starts here."}
                </h2>
                <p>
                  {state.options?.stored_matches
                    ? "Try another champion or lane, or sync more matches to expand your history."
                    : "Import your recent ranked matches and timelines. Then explore your game phase by phase."}
                </p>
                <button
                  className="button button-primary"
                  onClick={() => void state.sync()}
                  disabled={state.syncing || state.cooldown > 0}
                >
                  {state.syncing
                    ? "Importing…"
                    : state.cooldown > 0
                      ? `Available in ${state.cooldown}s`
                      : "Import latest 50 matches"}
                  <ArrowRight size={16} />
                </button>
              </div>
            )}
          </>
        )}
        {!state.player && !state.searching && (
          <section className="welcome-section" id="overview">
            <div className="welcome-heading">
              <span>SMALL DETAILS. A BIGGER PICTURE.</span>
              <span>No generic scores. Just your data.</span>
            </div>
            <div className="welcome-grid">
              <article>
                <span className="welcome-icon">
                  <Crosshair size={23} />
                </span>
                <h3>Focus on your game.</h3>
                <p>
                  Choose a champion and lane to see a report that reflects how
                  you actually play.
                </p>
                <span className="card-index">01 / PERSONAL</span>
              </article>
              <article>
                <span className="welcome-icon">
                  <Layers3 size={23} />
                </span>
                <h3>Find the turning points.</h3>
                <p>
                  Compare laning, midgame and late game. See how your leads grow
                  or slip away.
                </p>
                <span className="card-index">02 / CONTEXTUAL</span>
              </article>
              <article>
                <span className="welcome-icon">
                  <ShieldCheck size={23} />
                </span>
                <h3>Trust the evidence.</h3>
                <p>
                  Clear sample sizes and honest uncertainty. If the data isn’t
                  ready, we’ll tell you.
                </p>
                <span className="card-index">03 / TRANSPARENT</span>
              </article>
            </div>
            <div className="welcome-note" id="methodology">
              <Sparkles size={16} />
              <span>
                A better understanding of your game. No promises, no invented
                explanations.
              </span>
            </div>
          </section>
        )}
      </div>
    </Shell>
  );
}
