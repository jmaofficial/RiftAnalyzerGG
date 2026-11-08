import { Activity, ArrowDownToLine, CheckCheck, Trophy } from "lucide-react";
import { number, percent } from "../../../lib/format";
import type { AnalysisReport } from "../types";

export function ReportOverview({ report }: { report: AnalysisReport }) {
  const wins = report.cohorts.reduce((total, cohort) => total + cohort.wins, 0);
  const losses = report.eligible_matches - wins;
  const winRate = report.eligible_matches
    ? wins / report.eligible_matches
    : null;
  const excluded = report.selected_matches - report.eligible_matches;
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "riftanalyzer-report.json";
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section id="overview" className="report-overview">
      <div className="section-heading">
        <div>
          <span className="eyebrow">THE BIG PICTURE</span>
          <h2>Your report, at a glance.</h2>
        </div>
        <button className="button button-quiet" onClick={download}>
          <ArrowDownToLine size={15} /> Download report
        </button>
      </div>
      <div className="stat-grid">
        <article className="stat-card">
          <div className="stat-label">
            MATCHES ANALYZED <Activity size={17} />
          </div>
          <strong>{number(report.selected_matches)}</strong>
          <span>
            of {number(report.matched_total)} stored matches matching your
            filters
          </span>
        </article>
        <article className="stat-card">
          <div className="stat-label">
            ELIGIBLE MATCHES <CheckCheck size={17} />
          </div>
          <strong>{number(report.eligible_matches)}</strong>
          <span>
            {excluded
              ? `${excluded} excluded · remakes or incomplete data`
              : "Ready for a closer look"}
          </span>
        </article>
        <article className="stat-card win-card">
          <div className="stat-label">
            WIN RATE <Trophy size={17} />
          </div>
          <div className="win-card-content">
            <div>
              <strong>{percent(winRate, 1)}</strong>
              <span>
                <b className="win-text">{wins}W</b>
                <span className="stat-divider">/</span>
                <b className="loss-text">{losses}L</b> · eligible matches
              </span>
            </div>
            <div
              className="win-ring"
              role="img"
              aria-label={`${wins} wins and ${losses} losses`}
              style={{
                background: `conic-gradient(var(--win) ${(winRate || 0) * 360}deg, var(--surface-high) 0)`,
              }}
            >
              <span>{number(report.eligible_matches)}</span>
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
