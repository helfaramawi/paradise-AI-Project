import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, who = "commercial") {
  await page.goto("/");
  await page.getByTestId("email").fill(`${who}@haqq.demo`);
  await page.getByTestId("password").fill("HaqqDemo!2026");
  await page.getByTestId("login").click();
  await expect(page.getByTestId("lang-toggle")).toBeVisible();
}

test("dashboard renders RTL Arabic by default and switches to English LTR", async ({ page }) => {
  await login(page);
  await expect(page.locator('[data-kpi="potential_entitlements"]')).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByText("الذكاء التنفيذي")).toBeVisible();
  await page.getByTestId("lang-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByText("Executive intelligence")).toBeVisible();
  await page.locator('[data-kpi="revenue_at_risk"]').click();
  await expect(page.getByRole("dialog")).toContainText("ENT-");
});

test("explainable entitlement: clause citation, missing notice, deadline and claim preparation", async ({ page }) => {
  await login(page);
  await page.goto("/projects");
  await page.getByText("NAC-01").first().click();
  await page.getByRole("button", { name: /Entitlements|المستحقات/ }).click();
  await page.getByRole("link", { name: "ENT-001" }).click();
  await expect(page.getByTestId("fin-impact")).toContainText(/2[,٬]000[,٬]000|٢٬٠٠٠٬٠٠٠/);
  await expect(page.getByText(/13\.1/).first()).toBeVisible();
  await expect(page.getByTestId("notice-due")).toBeVisible();
  if (await page.getByTestId("create-claim").count()) await page.getByTestId("create-claim").click();
  else await page.getByRole("button", { name: /^CLM-/ }).click();
  await expect(page).toHaveURL(/\/claims\//);
  await page.getByTestId("generate").click();
  await expect(page.getByText(/_package_/)).toBeVisible();
});

test("site engineer only sees assigned projects and no executive dashboard", async ({ page }) => {
  await login(page, "site");
  await expect(page).toHaveURL(/\/projects/);
  await expect(page.getByText("NAC-01")).toBeVisible();
  await expect(page.getByText("WH-02")).toHaveCount(0);
});
