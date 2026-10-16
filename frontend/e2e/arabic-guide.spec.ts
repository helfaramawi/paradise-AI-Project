import { expect, test, type Page } from "@playwright/test";

// Captures the Arabic (RTL) screenshots used by the Arabic user guide.
const DIR = process.env.AR_SHOT_DIR || "../docs/screenshots/ar";
const shot = (page: Page, name: string) => page.screenshot({ path: `${DIR}/${name}.png` });

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', "FutureMirror!2026");
  await page.click('button[type="submit"]');
  await expect(page.getByTestId("platform-chips")).toBeVisible();
}

test("arabic user-guide screenshots", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fm_lang", "ar"));
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.waitForTimeout(600);
  await shot(page, "00-login");
  await login(page, "analyst@futuremirror.demo");

  await page.goto("/decisions/new");
  await page.getByTestId("use-demo").click();
  await page.waitForTimeout(400);
  await shot(page, "03-intake");
  await page.getByTestId("parse-btn").click();
  await page.getByTestId("next-2").click();
  await page.getByTestId("next-3").click();
  await page.getByTestId("launch-btn").click();
  await expect(page).toHaveURL(/\/execution\//);
  await expect(page.getByTestId("to-court")).toBeVisible({ timeout: 90_000 });
  await page.waitForTimeout(1500);
  await shot(page, "04-execution");

  await page.getByTestId("to-court").click();
  await expect(page.getByTestId("verdict-headline")).toBeVisible();
  await page.waitForTimeout(6000);
  await shot(page, "05-court");
  await page.getByRole("tab", { name: /كاشف تصادم المستقبل/ }).click();
  await page.getByTestId("collision-card").first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(900);
  await shot(page, "05b-collision");

  await page.goto("/futures");
  await expect(page.getByTestId("future-C")).toBeVisible();
  await page.waitForTimeout(1200);
  await page.getByTestId("future-A").scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await shot(page, "06-futures");
  await page.locator('input[type="range"]').first().fill("12");
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  await shot(page, "06b-whatif");

  await page.goto("/time-machine");
  await page.getByTestId("tm-stops").locator("button").nth(3).click();
  await page.waitForTimeout(1200);
  await shot(page, "07-time-machine");

  for (const [path, name] of [["/financial", "08-financial"], ["/risk", "09-risk"], ["/history", "11-history"],
    ["/data", "13-data"], ["/automation", "14-automation"], ["/governance", "15-governance"],
    ["/", "01-command-center"], ["/decisions", "02-workspace"]] as const) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    await shot(page, name);
  }
  await page.goto("/lab");
  await page.getByTestId("lab-run").click();
  await page.waitForTimeout(2500);
  await shot(page, "10-lab");

  await page.goto("/approvals");
  await page.getByTestId("pick-B").click();
  await page.getByTestId("ack").check();
  await page.getByTestId("submit-approval").click();
  await expect(page.getByTestId("approval-card").first()).toBeVisible();
  await page.waitForTimeout(800);
  await shot(page, "12-approvals");

  await page.goto("/outcomes");
  await page.getByTestId("demo-actuals").click();
  await page.waitForTimeout(2000);
  await shot(page, "16-outcomes");

  await page.getByTestId("theme-toggle").click();
  await page.goto("/");
  await page.waitForTimeout(1200);
  await shot(page, "23-command-center-light");
  await page.getByTestId("theme-toggle").click();

  await page.goto("/login");
  await page.evaluate(() => localStorage.removeItem("fm_token"));
  await login(page, "admin@futuremirror.demo");
  await page.goto("/admin");
  await page.waitForTimeout(1200);
  await shot(page, "17-admin");
});
