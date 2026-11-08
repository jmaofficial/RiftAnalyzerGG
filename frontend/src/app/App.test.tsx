import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { PatternFindings } from "../features/analysis/components/PatternFindings";
import { makeReport, options } from "../test/fixtures";
import type { Lane } from "../features/analysis/types";

const json = (body: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );

function mockApi() {
  return vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname.endsWith("/options")) return json(options);
      return json(
        makeReport(
          Number(url.searchParams.get("champion_id")) || null,
          url.searchParams.get("position") as Lane | null,
        ),
      );
    }),
  );
}

async function search() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/game name/i), "TestPlayer");
  await user.type(screen.getByLabelText(/tagline/i), "EUW");
  await user.click(screen.getByRole("button", { name: "View report" }));
  return user;
}

afterEach(() => vi.unstubAllGlobals());

describe("player report workflow", () => {
  it("shows both comparison groups and preserves tiny p-values in supported findings", () => {
    const report = makeReport();
    report.status = "findings_available";
    report.findings = [
      {
        finding_id: "deaths-15",
        rule_id: "deaths_15",
        patch: "16.22",
        position: "MIDDLE",
        minute: 15,
        group_a: {
          label: "At most 2 deaths by 15:00",
          matches: 30,
          wins: 24,
          win_rate: 0.8,
          win_rate_ci95: null,
          match_ids: [],
        },
        group_b: {
          label: "More than 2 deaths by 15:00",
          matches: 30,
          wins: 6,
          win_rate: 0.2,
          win_rate_ci95: null,
          match_ids: [],
        },
        win_rate_difference_pp: 60,
        adjusted_p_value: 0.00001,
        summary: null,
      },
    ];
    render(<PatternFindings report={report} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
    expect(
      screen.getByText(/Comparison: More than 2 deaths/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Adjusted p-value <0.0001/)).toBeInTheDocument();
  });
  it("starts with an English search and no fabricated match data", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "View report" })).toBeDisabled();
    expect(screen.getByText("A clearer game plan.")).toBeInTheDocument();
    expect(screen.queryByText("MATCHES ANALYZED")).not.toBeInTheDocument();
  });

  it("searches a stored player and sends both champion and lane filters to the backend", async () => {
    mockApi();
    render(<App />);
    const user = await search();
    await screen.findByText("Your report, at a glance.");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Champion" }),
      "1",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Lane" }),
      "MIDDLE",
    );
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([url]) =>
              String(url).includes("position=MIDDLE") &&
              String(url).includes("champion_id=1"),
          ),
      ).toBe(true),
    );
    await screen.findByText("Your report, at a glance.");
    expect(screen.getByText(/Annie · Mid/)).toBeInTheDocument();
    expect(
      screen.getByText("Good analysis knows when to wait."),
    ).toBeInTheDocument();
  });

  it("shows a useful empty result instead of a stale report for an empty filter combination", async () => {
    mockApi();
    render(<App />);
    const user = await search();
    await screen.findByText("Your report, at a glance.");
    vi.mocked(fetch).mockImplementation((input) => {
      if (String(input).includes("/options")) return json(options);
      return json({
        ...makeReport(2, "TOP"),
        selected_matches: 0,
        matched_total: 0,
        eligible_matches: 0,
        cohorts: [],
        phase_summaries: [],
      });
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Champion" }),
      "2",
    );
    await screen.findByText("No matches for this combination.");
    expect(
      screen.queryByText("Your report, at a glance."),
    ).not.toBeInTheDocument();
  });

  it("looks up an unknown local account but requires an explicit match import", async () => {
    let registered = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string) => {
        if (input.includes("/options"))
          return registered
            ? json({ ...options, stored_matches: 0, champions: [], lanes: [] })
            : json({ detail: "Player not stored" }, 404);
        if (!input.includes("/analysis")) {
          registered = true;
          return json({ puuid: "test" });
        }
        return json({
          ...makeReport(),
          selected_matches: 0,
          matched_total: 0,
          eligible_matches: 0,
          cohorts: [],
          phase_summaries: [],
        });
      }),
    );
    render(<App />);
    await search();
    await screen.findByText("Your first report starts here.");
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(([url]) => String(url).includes("/sync")),
    ).toBe(false);
    expect(
      screen.getByRole("button", { name: "Import latest 50 matches" }),
    ).toBeEnabled();
  });

  it("does not claim success on a partial sync and resumes from the returned offset", async () => {
    let syncCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string) => {
        if (input.includes("/sync")) {
          syncCount++;
          return json(
            syncCount === 1
              ? {
                  completed: false,
                  next_start: 5,
                  found: 50,
                  imported: 5,
                  retry_after: null,
                  failures: [{ upstream_status: 429, detail: "Rate limited" }],
                }
              : {
                  completed: true,
                  next_start: 50,
                  found: 45,
                  imported: 45,
                  retry_after: null,
                  failures: [],
                },
          );
        }
        return input.includes("/options") ? json(options) : json(makeReport());
      }),
    );
    render(<App />);
    const user = await search();
    await screen.findByText("Your report, at a glance.");
    await user.click(screen.getByRole("button", { name: "Sync latest 50" }));
    await screen.findByText(/Riot paused the import/);
    expect(screen.queryByText(/Import complete\./)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue import" }));
    await screen.findByText(
      /Import complete\. 50 recent ranked matches checked/,
    );
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          ([url]) =>
            String(url).includes("start=5") && String(url).includes("count=45"),
        ),
    ).toBe(true);
  });

  it("shows lookup errors without leaving an endless loading screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => json({ detail: "Player or match not found" }, 404)),
    );
    render(<App />);
    await search();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Player or match not found",
    );
    expect(screen.queryByText("Finding your player…")).not.toBeInTheDocument();
  });

  it("does not show a late response for filters that are no longer selected", async () => {
    let finishFirst: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string) => {
        if (input.includes("/options")) return json(options);
        if (!input.includes("champion_id"))
          return new Promise<Response>((resolve) => {
            finishFirst = resolve;
          });
        return json({ ...makeReport(1), selected_matches: 17 });
      }),
    );
    render(<App />);
    await search();
    const champion = await screen.findByRole("combobox", { name: "Champion" });
    fireEvent.change(champion, { target: { value: "1" } });
    await screen.findByText("Your report, at a glance.");
    finishFirst!(
      new Response(JSON.stringify({ ...makeReport(), selected_matches: 99 })),
    );
    await waitFor(() =>
      expect(screen.queryByText("99")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("17")).toBeInTheDocument();
  });
});
