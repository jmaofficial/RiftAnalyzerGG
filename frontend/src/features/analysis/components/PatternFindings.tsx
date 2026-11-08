import {
  ChartNoAxesCombined,
  Check,
  CircleHelp,
  FlaskConical,
} from "lucide-react";
import { laneName, number, percent } from "../../../lib/format";
import type { AnalysisReport } from "../types";

export function PatternFindings({ report }: { report: AnalysisReport }) {
  const largest = Math.max(
    0,
    ...report.cohorts.map((cohort) => cohort.matches),
  );
  return (
    <section id="patterns">
      <div className="section-heading">
        <div>
          <span className="eyebrow">EVIDENCE, NOT GUESSWORK</span>
          <h2>Patterns worth paying attention to.</h2>
        </div>
        <span className="subtle-badge">
          <FlaskConical size={14} /> Exploratory analysis
        </span>
      </div>
      {report.findings.length ? (
        <div className="findings-grid">
          {report.findings.map((finding) => (
            <article className="panel finding-card" key={finding.finding_id}>
              <span className="finding-meta">
                <Check size={15} /> {laneName(finding.position)} · Patch{" "}
                {finding.patch}
              </span>
              <h3>{finding.group_a.label}</h3>
              <div className="finding-numbers">
                <strong
                  className={
                    (finding.group_a.win_rate ?? 0) >=
                    (finding.group_b.win_rate ?? 0)
                      ? "win-text"
                      : undefined
                  }
                >
                  {percent(finding.group_a.win_rate)}
                </strong>
                <span>vs</span>
                <strong
                  className={
                    (finding.group_b.win_rate ?? 0) >
                    (finding.group_a.win_rate ?? 0)
                      ? "win-text"
                      : undefined
                  }
                >
                  {percent(finding.group_b.win_rate)}
                </strong>
              </div>
              <p>
                {finding.group_a.wins}/{finding.group_a.matches} wins compared
                with {finding.group_b.wins}/{finding.group_b.matches} wins.
              </p>
              <p>Comparison: {finding.group_b.label}.</p>
              <p className="proxy-note">
                Adjusted p-value{" "}
                {finding.adjusted_p_value != null &&
                finding.adjusted_p_value < 0.0001
                  ? "<0.0001"
                  : number(finding.adjusted_p_value, 4)}
                . An association, not a causal effect.
              </p>
            </article>
          ))}
        </div>
      ) : (
        <article className="panel evidence-empty">
          <div className="evidence-icon">
            <ChartNoAxesCombined size={25} />
          </div>
          <div>
            <h3>
              {report.status === "insufficient_data"
                ? "Good analysis knows when to wait."
                : "No clear pattern passed the checks."}
            </h3>
            <p>
              {report.status === "insufficient_data"
                ? `Your largest lane-and-patch group has ${largest} matches. A comparison needs at least ${report.minimum_cohort_matches} applicable games and ${report.minimum_group_matches} in each group. You can still explore the phase breakdown above.`
                : "There is enough data to run some comparisons, but none passed all uncertainty and effect-size checks. That does not mean no pattern exists."}
            </p>
          </div>
        </article>
      )}
      <details id="methodology" className="methodology">
        <summary>
          <CircleHelp size={16} /> How to read this report{" "}
          <span>Methods & data coverage</span>
        </summary>
        <div>
          <p>
            Win rates use eligible matches. Phase averages pool patches within
            each lane and exclude partial phases. Each metric shows its own
            contributing sample size.
          </p>
          <p>
            Statistical comparisons keep lanes and patches separate, use
            Fisher’s exact test and Holm correction, and require at least a 10
            percentage-point difference. They describe associations, not causes.
            Sidelane averages require at least 80% position coverage.
          </p>
          {Object.keys(report.excluded_matches_by_reason).length > 0 && (
            <p>
              Excluded-match reasons:{" "}
              {Object.entries(report.excluded_matches_by_reason)
                .map(
                  ([reason, count]) =>
                    `${reason.replaceAll("_", " ")} (${count})`,
                )
                .join("; ")}
              . Reasons may overlap.
            </p>
          )}
          <p className="muted">
            Feature version {report.feature_version} · Report version{" "}
            {report.analysis_version} · {report.tested_hypotheses} comparisons
            tested.
          </p>
        </div>
      </details>
    </section>
  );
}
