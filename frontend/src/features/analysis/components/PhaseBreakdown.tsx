import { ArrowUpRight, GitCompareArrows, MapPin, Route } from "lucide-react";
import { useState } from "react";
import { laneName, number, percent } from "../../../lib/format";
import type { AnalysisReport, Lane, Metric, Phase } from "../types";

const phases: { id: Phase; name: string; time: string }[] = [
  { id: "laning", name: "Laning", time: "0–15 min" },
  { id: "midgame", name: "Midgame", time: "15–25 min" },
  { id: "late_game", name: "Late game", time: "25 min–end" },
];
const metrics = [
  {
    key: "gold_per_minute",
    name: "Gold per minute",
    unit: "gold / min",
    digits: 0,
  },
  {
    key: "lane_cs_gained",
    name: "Lane minions collected",
    unit: "CS during phase",
    digits: 1,
  },
  { key: "kills", name: "Kills", unit: "during phase", digits: 1 },
  { key: "assists", name: "Assists", unit: "during phase", digits: 1 },
  { key: "deaths", name: "Deaths", unit: "during phase", digits: 1 },
];

function ComparisonRow({
  label,
  unit,
  digits,
  metric,
}: {
  label: string;
  unit: string;
  digits: number;
  metric?: Metric;
}) {
  const maximum = Math.max(metric?.win_mean || 0, metric?.loss_mean || 0, 1);
  return (
    <div className="comparison-row">
      <div className="metric-label">
        {label}
        <small>{unit}</small>
      </div>
      {(["win", "loss"] as const).map((outcome) => {
        const value = metric?.[`${outcome}_mean`];
        const count = metric?.[`${outcome}_matches`] || 0;
        return (
          <div className={`metric-cell ${outcome}`} key={outcome}>
            <div>
              <strong>{number(value, digits)}</strong>
              <small>{count} matches</small>
            </div>
            <div className="metric-track">
              <span
                style={{
                  width: `${value == null || value <= 0 ? 0 : Math.max(2, (value / maximum) * 100)}%`,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PhaseBreakdown({ report }: { report: AnalysisReport }) {
  const roles = Array.from(
    new Set(report.phase_summaries.map((summary) => summary.position)),
  );
  const defaultRole =
    report.filters.position ||
    [...report.phase_summaries].sort(
      (a, b) => b.complete_matches - a.complete_matches,
    )[0]?.position ||
    "MIDDLE";
  const [role, setRole] = useState<Lane>(defaultRole);
  const [active, setActive] = useState<Phase>("midgame");
  const current = report.phase_summaries.find(
    (summary) => summary.position === role && summary.phase === active,
  );
  const side = current?.metrics;
  const sideShare = side?.["sidelane.sidelane_share_of_observed_time"];
  const sideGold = side?.["sidelane.gold_gained_during_sidelane_intervals"];
  const phaseLabel = phases.find((phase) => phase.id === active)!;
  return (
    <section id="phases" className="phase-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">BEYOND THE SCORELINE</span>
          <h2>Where your games take shape.</h2>
        </div>
        {roles.length > 1 && (
          <label className="compact-select">
            Compare role
            <select
              aria-label="Phase comparison role"
              value={role}
              onChange={(event) => setRole(event.target.value as Lane)}
            >
              {roles.map((lane) => (
                <option key={lane} value={lane}>
                  {laneName(lane)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="phase-layout">
        <article className="panel phase-panel">
          <div className="phase-tabs" role="tablist" aria-label="Game phase">
            {phases.map((phase) => (
              <button
                key={phase.id}
                id={`tab-${phase.id}`}
                role="tab"
                aria-selected={phase.id === active}
                aria-controls="phase-content"
                onClick={() => setActive(phase.id)}
              >
                <span>{phase.name}</span>
                <small>{phase.time}</small>
              </button>
            ))}
          </div>
          <div
            id="phase-content"
            role="tabpanel"
            aria-labelledby={`tab-${active}`}
            tabIndex={0}
          >
            <div className="comparison-header">
              <span>
                <GitCompareArrows size={16} /> {laneName(role)} ·{" "}
                {phaseLabel.name}
              </span>
              <span className="outcome-label win-text">IN WINS</span>
              <span className="outcome-label loss-text">IN LOSSES</span>
            </div>
            {current && current.complete_matches > 0 ? (
              <>
                {metrics.map((metric) => (
                  <ComparisonRow
                    key={metric.key}
                    label={metric.name}
                    unit={metric.unit}
                    digits={metric.digits}
                    metric={current.metrics[metric.key]}
                  />
                ))}
                <p className="panel-footnote">
                  {current.complete_matches} complete phases ·{" "}
                  {current.patches.length}{" "}
                  {current.patches.length === 1 ? "patch" : "patches"}.
                  Descriptive averages, not proof of what caused a win.{" "}
                  {current.partial_matches > 0 &&
                    `${current.partial_matches} partial phases omitted.`}
                  {active === "late_game" &&
                    " Late-game duration varies between matches."}
                </p>
              </>
            ) : (
              <div className="inline-empty">
                <Route size={25} />
                <h3>No complete {phaseLabel.name.toLowerCase()} phases yet.</h3>
                <p>
                  Try another phase, lane or champion, or import more matches.
                </p>
              </div>
            )}
          </div>
        </article>
        <aside className="panel sidelane-panel">
          <div className="panel-kicker">
            <MapPin size={17} /> SIDELANE ACTIVITY
          </div>
          {role === "MIDDLE" && sideShare?.mean != null ? (
            <>
              <h3>
                What happens
                <br />
                away from mid?
              </h3>
              <div className="side-stat">
                {percent(sideShare.mean, 1)}
                <ArrowUpRight size={25} />
              </div>
              <p>of observed phase time in stable top or bot lane intervals</p>
              <div className="side-details">
                <div>
                  <span>Gold gained in those intervals</span>
                  <strong>
                    {number(sideGold?.mean)}
                    <small> / match</small>
                  </strong>
                </div>
                <div>
                  <span>Position coverage</span>
                  <strong>
                    {percent(side?.["sidelane.coverage_fraction"]?.mean)}
                  </strong>
                </div>
                <div>
                  <span>Matches contributing gold data</span>
                  <strong>{number(sideGold?.available_matches)}</strong>
                </div>
              </div>
              <p className="proxy-note">
                A position-based estimate, including passive and other gold.
                This is not exact gold earned from sidelane minions.
              </p>
            </>
          ) : (
            <>
              <h3>
                A different angle
                <br />
                on your map play.
              </h3>
              <div className="mini-rift" aria-hidden="true">
                <span />
                <i />
                <b />
              </div>
              <p>
                {role !== "MIDDLE"
                  ? "Sidelane observations are available for Mid. Choose Mid in the lane filter to explore them."
                  : "More position coverage is needed for this phase. Missing observations are never counted as zero sidelane time."}
              </p>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
