import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.SHOT_DIR || "../docs/screenshots";
const shot = (page: Page, name: string) => page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false });

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', "FutureMirror!2026");
  await page.click('button[type="submit"]');
  await expect(page.getByTestId("platform-chips")).toBeVisible();
}

test("guided demo: question → agents → court → futures → time machine → governance → approval", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/login");
  await shot(page, "00-login");
  await login(page, "analyst@futuremirror.demo");
  await expect(page.getByTestId("platform-chips")).toContainText("Synthetic data");
  await expect(page.getByTestId("platform-chips")).toContainText("no LLM");

  // Scene 1 — the executive question
  await page.goto("/decisions/new");
  await page.getByTestId("use-demo").click();
  await expect(page.getByTestId("question-input")).toHaveValue(/20%/);
  await shot(page, "03-intake-question");
  await page.getByTestId("parse-btn").click();
  await expect(page.getByText("no terminations")).toBeVisible();
  await page.getByTestId("next-2").click();
  await page.getByTestId("next-3").click();
  await page.getByTestId("launch-btn").click();

  // Scene 2 — the agents awaken (real SSE events)
  await expect(page).toHaveURL(/\/execution\//);
  await expect(page.getByTestId("event-feed")).toContainText("Independent analysis", { timeout: 30_000 });
  await page.waitForTimeout(1500);
  await shot(page, "04-execution-live");
  await expect(page.getByTestId("to-court")).toBeVisible({ timeout: 90_000 });
  await shot(page, "04b-execution-done");

  // Scene 3/4 — Agent Court & Future Collision
  await page.getByTestId("to-court").click();
  await expect(page.getByTestId("court-mode")).toContainText("Rule-based");
  await expect(page.getByTestId("verdict-headline")).toBeVisible();
  await page.waitForTimeout(6000);
  await shot(page, "05-agent-court");
  await page.getByRole("tab", { name: /Future Collision Detector/ }).click();
  await expect(page.getByTestId("collision-card").first()).toBeVisible();
  await shot(page, "05b-collision-detector");

  // Scene 5 — Three futures with live recalculation
  await page.goto("/futures");
  await expect(page.getByTestId("future-C")).toBeVisible();
  await page.waitForTimeout(1200);
  await shot(page, "06-three-futures");
  await page.getByTestId("future-A").scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await shot(page, "06a-three-futures-cards");
  const slider = page.locator('input[type="range"]').first();
  await slider.fill("12");
  await expect(page.getByText("What-if mode")).toBeVisible({ timeout: 15_000 });
  await shot(page, "06b-three-futures-whatif");

  // Scene 6 — Time machine
  await page.goto("/time-machine");
  await page.getByTestId("tm-stops").getByText("Month 6").click();
  await expect(page.getByTestId("tm-tiles")).toBeVisible();
  await shot(page, "07-time-machine");

  for (const [path, name] of [["/financial", "08-financial"], ["/risk", "09-risk"], ["/lab", "10-lab"], ["/history", "11-history"],
    ["/data", "13-data"], ["/automation", "14-automation"], ["/governance", "15-governance"], ["/", "01-command-center"], ["/decisions", "02-workspace"]] as const) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    await shot(page, name);
  }
  await page.goto("/lab");
  await page.getByTestId("lab-run").click();
  await expect(page.getByText("Sensitivity (tornado)")).toBeVisible();
  await page.waitForTimeout(800);
  await shot(page, "10-lab");

  // Scene 7 — governance gate: Future A blocked; Future B submitted
  await page.goto("/approvals");
  await page.getByTestId("pick-A").click();
  await expect(page.getByText("GOV-009")).toBeVisible();
  await page.getByTestId("pick-B").click();
  await page.getByTestId("ack").check();
  await page.getByTestId("submit-approval").click();
  await expect(page.getByTestId("approval-card").first()).toContainText(/Pending/);
  await shot(page, "12-approval-center");

  // Scene 8 — executive decision: CFO approves (separation of duties: analyst requested)
  await page.getByRole("button", { name: "Sign out" }).click();
  await login(page, "cfo@futuremirror.demo");
  await page.goto("/approvals");
  await page.getByTestId("approve-btn").first().click();
  await expect(page.getByText(/CFO · Karim Mansour/).first()).toBeVisible();

  // Reality feedback loop
  await page.goto("/outcomes");
  await page.getByTestId("demo-actuals").click();
  await expect(page.getByText("Why the forecast differed")).toBeVisible();
  await page.waitForTimeout(800);
  await shot(page, "16-actual-vs-predicted");

  // Arabic RTL
  await page.getByTestId("lang-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.goto("/court");
  await page.waitForTimeout(5000);
  await shot(page, "20-agent-court-ar");
  await page.goto("/futures");
  await page.waitForTimeout(1200);
  await shot(page, "21-three-futures-ar");
  await page.goto("/time-machine");
  await page.waitForTimeout(800);
  await shot(page, "22-time-machine-ar");
  await page.getByTestId("lang-toggle").click();

  // Light theme + admin
  await page.getByRole("button", { name: "Sign out" }).click();
  await login(page, "admin@futuremirror.demo");
  await page.goto("/admin");
  await page.waitForTimeout(800);
  await shot(page, "17-admin");
  await page.getByTestId("theme-toggle").click();
  await page.goto("/");
  await page.waitForTimeout(800);
  await shot(page, "23-command-center-light");
  await page.getByTestId("theme-toggle").click();
  expect(errors, errors.join("\n")).toEqual([]);
});

test("tablet layout renders core screens", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 820, height: 1180 } });
  const page = await ctx.newPage();
  await login(page, "ceo@futuremirror.demo");
  await page.goto("/futures");
  await expect(page.getByTestId("future-B")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: `${SHOTS}/30-tablet-futures.png` });
  await ctx.close();
});
