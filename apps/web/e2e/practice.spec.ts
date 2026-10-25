import { expect, test } from "@playwright/test";

const ANSWER =
  "I would start by reproducing the problem and checking the logs and metrics around the time " +
  "it started. Then I would form a hypothesis, test it with a small experiment, and once I " +
  "find the cause I would fix it, add a regression test, and watch the error rate after the " +
  "deploy. I would also write down what happened and explain the trade-offs to the team.";

test("a candidate completes a practice interview and reads the report", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(`waitlist-${Date.now()}@example.com`);
  await page.getByLabel("Role interest").selectOption("devops_sre");
  await page.getByRole("button", { name: "Join waitlist" }).click();
  await expect(page.getByRole("status")).toContainText("You're on the waitlist");
  await page.getByRole("link", { name: "Start a practice interview" }).click();

  await page.getByText("DevOps and SRE engineer (junior to mid)").click();
  await page.getByText("Mid level").click();
  await page.getByLabel("Your email").fill(`e2e-${Date.now()}@example.com`);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Start interview" }).click();

  await expect(page).toHaveURL(/\/interview\/\?id=/);
  await expect(page.getByTestId("progress")).toContainText("Section 1 of 5");

  // A short answer gets a follow-up question.
  await page.getByLabel("Your answer").fill("I ran some servers.");
  await page.getByRole("button", { name: "Send answer" }).click();
  await expect(page.locator('[data-speaker="interviewer"]').last()).toContainText(
    "go a bit deeper",
  );

  // Detailed answers move through every question until the interview ends.
  let usedTerminal = false;
  for (let i = 0; i < 12 && (await page.getByLabel("Your answer").count()) > 0; i++) {
    const before = await page.locator("li[data-speaker]").count();
    // Scenario questions have a practice terminal; use it once, then answer as usual.
    if ((await page.getByTestId("terminal").count()) > 0 && !usedTerminal) {
      await page.getByLabel(/^ops@.*\$$/).fill("ss -tlnp | grep 443");
      await page.getByLabel(/^ops@.*\$$/).press("Enter");
      await expect(page.getByTestId("terminal")).toContainText("0.0.0.0:443");
      usedTerminal = true;
    }
    await page.getByLabel("Your answer").fill(ANSWER);
    await page.getByRole("button", { name: "Send answer" }).click();
    // Offline grading can redirect before the final transcript update renders.
    await expect.poll(async () =>
      new URL(page.url()).pathname === "/report/" ||
      (await page.locator("li[data-speaker]").count()) === before + 2,
    ).toBe(true);
  }

  expect(usedTerminal).toBe(true);
  await expect(page).toHaveURL(/\/report\/\?id=/, { timeout: 30_000 });
  await expect(page.getByTestId("verdict")).toBeVisible();
  await expect(page.getByTestId("skill")).toHaveCount(6);
  await expect(page.getByText("Graded by dev/dev-grader")).toBeVisible();

  await page.getByRole("link", { name: "My interviews" }).click();
  await expect(page.getByText("DevOps and SRE practice interview (mid)")).toBeVisible();
  await page.getByRole("link", { name: "My consents" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Withdraw" }).first().click();
  await expect(page.getByText(/Withdrawn/)).toBeVisible();
});
