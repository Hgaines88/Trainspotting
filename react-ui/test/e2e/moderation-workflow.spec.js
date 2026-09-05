import { expect, test } from "@playwright/test";


const DESIGNER_NAME = "Isolated Browser Test Designer";


async function useIdentity(page, identity) {
  await page.goto("/");
  await page.evaluate(({ key, value }) => {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  }, { key: "trainspotting-e2e-identity", value: identity });
  await page.reload();
}


async function apiRequest(page, path, { identity, method = "GET", body } = {}) {
  return page.evaluate(async ({ requestPath, requestIdentity, requestMethod, requestBody }) => {
    const response = await fetch(`/api${requestPath}`, {
      method: requestMethod,
      headers: {
        ...(requestIdentity ? { Authorization: `Bearer e2e-${requestIdentity}` } : {}),
        ...(requestBody ? { "Content-Type": "application/json" } : {}),
      },
      ...(requestBody ? { body: JSON.stringify(requestBody) } : {}),
    });
    return { status: response.status, body: await response.json() };
  }, {
    requestPath: path,
    requestIdentity: identity,
    requestMethod: method,
    requestBody: body,
  });
}


test("critical moderation workflow is isolated, authorized, idempotent, and reversible", async ({ page }) => {
  await useIdentity(page, null);
  await expect(page.getByRole("heading", { name: /Who made it/i })).toBeVisible();
  const anonymousMutation = await apiRequest(page, "/submissions", {
    method: "POST",
    body: {
      record_type: "designer",
      submission_type: "addition",
      proposed_data: { full_name: DESIGNER_NAME },
      explanation: "Anonymous requests must be rejected.",
      sources: [{ url: "https://example.test/anonymous" }],
    },
  });
  expect(anonymousMutation.status).toBe(401);

  await useIdentity(page, "member");
  await page.goto("/submissions/new");
  await page.getByLabel("Full name").fill(DESIGNER_NAME);
  await page.getByLabel("Nationality").fill("American");
  await page.getByLabel("Why should the archive change?").fill(
    "Exercise the complete isolated browser moderation workflow.",
  );
  await page.getByLabel("Source URL").fill("https://example.test/primary-source");
  await page.getByLabel("Source title").fill("Primary documented source");
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page).toHaveURL(/\/submissions\/mine$/);
  const submissionLabel = page.getByText(/#\d+ · designer addition/).first();
  await expect(submissionLabel).toBeVisible();
  const submissionId = Number((await submissionLabel.textContent()).match(/#(\d+)/)[1]);

  await page.goto("/moderation");
  await expect(page).toHaveURL(/\/$/);
  const forbiddenMemberDecision = await apiRequest(
    page,
    `/moderation/submissions/${submissionId}/decisions`,
    {
      identity: "member",
      method: "POST",
      body: { decision: "approve", notes: "Members cannot approve." },
    },
  );
  expect(forbiddenMemberDecision.status).toBe(403);

  await useIdentity(page, "moderator");
  await page.goto("/moderation");
  await expect(page.getByText(new RegExp(`^Submission #${submissionId} · E2E Member$`))).toBeVisible();
  await expect(page.getByRole("button", { name: /submitted 1 submission/i })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("table", { name: "Proposed archive record" })).toContainText(DESIGNER_NAME);
  await expect(page.getByLabel(new RegExp(`Audit history for submission ${submissionId}`))).toContainText("Submitted");
  await page.getByRole("button", { name: "Request changes" }).click();
  const changesDialog = page.getByRole("dialog", { name: "Request changes" });
  await expect(changesDialog).toBeVisible();
  const requiredChanges = changesDialog.getByLabel("Required changes");
  await expect(requiredChanges).toBeFocused();
  await changesDialog.getByRole("button", { name: "Send change request" }).click();
  await expect(changesDialog).toBeVisible();
  await changesDialog.getByRole("button", { name: "Cancel" }).click();
  await expect(changesDialog).toBeHidden();
  await page.getByRole("button", { name: "Request changes" }).click();
  await requiredChanges.fill("Please add a second independent source.");
  await changesDialog.getByRole("button", { name: "Send change request" }).click();
  await expect(page.getByText("The queue is clear.")).toBeVisible();

  await useIdentity(page, "member");
  await page.goto("/submissions/mine");
  const memberSubmission = page
    .getByText(new RegExp(`^#${submissionId} · designer addition$`))
    .locator("..");
  await expect(memberSubmission.getByText("changes requested · version 1")).toBeVisible();
  await memberSubmission.getByRole("link", { name: "Edit and resubmit" }).click();
  await expect(page.getByLabel("Source URL")).toHaveValue(
    "https://example.test/primary-source",
  );
  await page.getByRole("button", { name: "Add another source" }).click();
  const sourceUrls = page.getByLabel("Source URL");
  await expect(sourceUrls).toHaveCount(2);
  await sourceUrls.nth(1).fill("https://example.test/independent-source");
  const sourceTitles = page.getByLabel("Source title");
  await sourceTitles.nth(1).fill("Independent documented source");
  await page.getByRole("button", { name: "Save and resubmit" }).click();
  await expect(page.getByText("submitted · version 2")).toBeVisible();

  await useIdentity(page, "moderator");
  await page.goto("/moderation");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const approvalDialog = page.getByRole("dialog", { name: "Approve proposal" });
  await expect(approvalDialog).toContainText("promote this proposal into the public archive");
  await approvalDialog.getByRole("button", { name: "Approve and publish" }).click();
  await expect(page.getByText("The queue is clear.")).toBeVisible();

  const duplicateApproval = await apiRequest(
    page,
    `/moderation/submissions/${submissionId}/decisions`,
    {
      identity: "moderator",
      method: "POST",
      body: { decision: "approve", notes: "Idempotent retry." },
    },
  );
  expect(duplicateApproval.status).toBe(200);
  expect(duplicateApproval.body.status).toBe("approved");

  const approvedDesigners = await apiRequest(page, "/designers");
  expect(approvedDesigners.body.filter((item) => item.full_name === DESIGNER_NAME)).toHaveLength(1);

  await useIdentity(page, "admin");
  await page.goto("/moderation");
  await page.getByRole("button", { name: /^approved /i }).click();
  await expect(page.getByText(DESIGNER_NAME)).toBeVisible();
  await page.getByRole("button", { name: "Roll back approval" }).click();
  const rollbackDialog = page.getByRole("dialog", { name: "Roll back approval" });
  await rollbackDialog.getByLabel("Rollback reason").fill("Rollback the isolated browser test record.");
  await rollbackDialog.getByRole("button", { name: "Restore previous state" }).click();
  await expect(page.getByText("The queue is clear.")).toBeVisible();

  const restoredDesigners = await apiRequest(page, "/designers");
  expect(restoredDesigners.body.some((item) => item.full_name === DESIGNER_NAME)).toBe(false);
  const audit = await apiRequest(page, `/submissions/${submissionId}/audit`, {
    identity: "admin",
  });
  expect(audit.status).toBe(200);
  expect(audit.body.map((event) => event.event_type)).toEqual([
    "submitted",
    "changes_requested",
    "draft_updated",
    "submitted",
    "approved",
    "rolled_back",
  ]);
});
