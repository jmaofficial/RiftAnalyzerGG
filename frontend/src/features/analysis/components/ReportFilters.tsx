import { SlidersHorizontal } from "lucide-react";
import { championName, laneName } from "../../../lib/format";
import type { AnalysisOptions, Filters, Lane } from "../types";

export function ReportFilters({
  options,
  filters,
  onChange,
  disabled,
}: {
  options: AnalysisOptions;
  filters: Filters;
  onChange: (filters: Filters) => void;
  disabled: boolean;
}) {
  return (
    <section className="filter-bar" aria-label="Report filters">
      <div className="filter-heading">
        <SlidersHorizontal size={17} />
        <span>Make it personal</span>
      </div>
      <label>
        Champion
        <select
          value={filters.championId}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...filters, championId: event.target.value })
          }
        >
          <option value="">All champions</option>
          {options.champions.map((champion) => (
            <option key={champion.champion_id} value={champion.champion_id}>
              {championName(champion.champion_name)} ({champion.matches})
            </option>
          ))}
        </select>
      </label>
      <label>
        Lane
        <select
          value={filters.lane}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...filters, lane: event.target.value as Lane | "" })
          }
        >
          <option value="">All lanes</option>
          {["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"].map((lane) => (
            <option key={lane} value={lane}>
              {laneName(lane)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Sample
        <select
          value={filters.limit}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...filters, limit: Number(event.target.value) })
          }
        >
          {[50, 100, 200, 500].map((limit) => (
            <option key={limit} value={limit}>
              Latest {limit} matches
            </option>
          ))}
        </select>
      </label>
      <button
        className="text-button"
        disabled={
          disabled ||
          (!filters.championId && !filters.lane && filters.limit === 50)
        }
        onClick={() => onChange({ championId: "", lane: "", limit: 50 })}
      >
        Reset
      </button>
    </section>
  );
}
