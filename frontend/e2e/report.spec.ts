import { expect, test } from "@playwright/test";
import { makeReport, options } from "../src/test/fixtures";
import type { Lane } from "../src/features/analysis/types";

test("a three-match report has a visible update action and refreshes after importing", async ({
  page,
}) => {
  let count = 3;
  await page.route("**/api/players/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/sync")) {
      count = 50;
      return route.fulfill({
        json: {
          completed: true,
          next_start: 50,
          found: 50,
          imported: 47,
          retry_after: null,
          failures: [],
        },
      });
    }
    return route.fulfill({
      json: url.pathname.endsWith("/options")
        ? { ...options, stored_matches: count }
        : { ...makeReport(), selected_matches: count, matched_total: count },
    });
  });
  await page.goto("/");
  await page.getByLabel("GAME NAME").fill("TestPlayer");
  await page.getByLabel("TAGLINE").fill("EUW");
  await page.getByRole("button", { name: "View report" }).click();
  await expect(
    page.getByText("3 stored ranked matches · All champions · All lanes"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Update matches" }).click();
  await expect(
    page.getByText(/Import complete\. 50 recent ranked matches checked/),
  ).toBeVisible();
  await expect(
    page.getByText("50 stored ranked matches · All champions · All lanes"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Refresh report" }),
  ).toBeEnabled();
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.evaluate(() => innerWidth),
  );
});

test("search, filter and explore a report in English", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/players/**", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      json: url.pathname.endsWith("/options")
        ? options
        : makeReport(
            Number(url.searchParams.get("champion_id")) || null,
            url.searchParams.get("position") as Lane | null,
          ),
    });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Your games/ })).toBeVisible();
  await page.getByLabel("GAME NAME").fill("TestPlayer");
  await page.getByLabel("TAGLINE").fill("EUW");
  await page.getByRole("button", { name: "View report" }).click();
  await expect(
    page.getByRole("heading", { name: "Your report, at a glance." }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Champion", exact: true })
    .selectOption("1");
  const filtered = page.waitForResponse(
    (response) =>
      response.url().includes("champion_id=1") &&
      response.url().includes("position=MIDDLE"),
  );
  await page
    .getByRole("combobox", { name: "Lane", exact: true })
    .selectOption("MIDDLE");
  await filtered;
  await expect(
    page.getByText("50 stored ranked matches · Annie · Mid"),
  ).toBeVisible();
  await page.getByRole("tab", { name: /Laning/ }).click();
  await expect(page.getByRole("tab", { name: /Laning/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByText("Good analysis knows when to wait."),
  ).toBeVisible();
  await page.locator("#methodology summary").click();
  await expect(
    page.getByText(/Statistical comparisons keep lanes and patches separate/),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.evaluate(() => innerWidth),
  );
  expect(errors).toEqual([]);
});

test("an API failure is visible and does not display sample data", async ({
  page,
}) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Riot is temporarily unavailable. Please try later." },
    }),
  );
  await page.goto("/");
  await page.getByLabel("GAME NAME").fill("MissingPlayer");
  await page.getByLabel("TAGLINE").fill("EUW");
  await page.getByRole("button", { name: "View report" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Riot is temporarily unavailable",
  );
  await expect(page.getByText("MATCHES ANALYZED")).toHaveCount(0);
});
