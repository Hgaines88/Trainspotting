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


test("public archive discovery preserves filters and pagination in the URL", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("article.card")).toHaveCount(12);
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page).toHaveURL(/\?page=2$/);
  await expect(page.locator("article.card").first().locator(".card-index")).toHaveText("013");

  await page.getByLabel("Search the archive").fill("Afro-Atlantic");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/\?search=Afro-Atlantic$/);
  await expect(page.getByRole("link", { name: /Grace Wales Bonner/ })).toBeVisible();
  await expect(page.locator("article.card")).toHaveCount(1);

  await page.getByLabel("Search the archive").fill("No such archive record");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("heading", { name: "No profiles match these filters." })).toBeVisible();
  await page.getByRole("link", { name: "Clear filters" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("article.card")).toHaveCount(12);
});


test("homepage offers a self-guided path into collection discovery", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Start exploring" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Archive discovery shortcuts" }).getByRole("link")).toHaveCount(4);
  await expect(page.getByText("Recent archive arrivals")).toBeVisible();

  const recentCollection = page.locator(".recent-collections .collection-list a").first();
  const destination = await recentCollection.getAttribute("href");
  expect(destination).toMatch(/^\/collections\/\d+$/);
  await recentCollection.click();
  await expect(page).toHaveURL(new RegExp(`${destination}$`));
  await expect(page.getByRole("heading", { name: "Related collections" })).toBeVisible();

  await page.goto("/");
  await page.getByRole("link", { name: /Most documented/ }).click();
  await expect(page).toHaveURL(/\?sort=collections&direction=desc$/);
  await expect(page.getByRole("heading", { name: "Start exploring" })).toHaveCount(0);
  await expect(page.locator("article.card").first()).toBeVisible();
});


test("public collection explorer preserves discovery filters in a shareable URL", async ({ page }) => {
  await page.goto("/collections");

  await expect(page.getByRole("heading", { name: /What arrived/i })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Public archive" }).getByRole("link", { name: "Collections" })).toBeVisible();
  await expect(page.locator(".collection-explorer-results > li").first()).toBeVisible();

  await page.getByLabel("Search collections").fill("Prada");
  await page.getByLabel("Season").fill("Spring/Summer");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/\/collections\?search=Prada&season=Spring%2FSummer$/);
  await expect(page.getByText("Miuccia Prada + Raf Simons")).toBeVisible();

  const collection = page.locator(".collection-explorer-results a").first();
  await expect(collection).toHaveAttribute("href", /^\/collections\/\d+$/);
  const destination = await collection.getAttribute("href");
  if (!destination) throw new Error("Collection result is missing its destination");
  const expectedUrl = new URL(destination, page.url()).toString();
  await collection.click();
  await expect(page).toHaveURL(expectedUrl);
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Related collections" })).toBeVisible();
});


test("collection pages show ranked recommendations with visible reasons", async ({ page }) => {
  await page.goto("/collections/1");

  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.locator(".source-list a").first()).toHaveAttribute("href", /^https:\/\//);
  await expect(page.getByRole("heading", { name: "Related collections" })).toBeVisible();
  const recommendations = page.locator(".related-list > li");
  await expect(recommendations.first()).toBeVisible();
  const recommendationCount = await recommendations.count();
  expect(recommendationCount).toBeLessThanOrEqual(4);
  await expect(recommendations.first().locator(".related-score")).toContainText(/^Match \d+$/);
  await expect(recommendations.first().locator(".related-reasons li").first()).toBeVisible();

  const destination = await recommendations.first().getByRole("link").getAttribute("href");
  await recommendations.first().getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`${destination}$`));
  await expect(page.getByRole("heading", { name: "Related collections" })).toBeVisible();
});


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
  await page.getByRole("button", { name: "Submit for review" }).click();
  const validationSummary = page.getByRole("alert");
  await expect(validationSummary).toBeFocused();
  await expect(validationSummary).toContainText("Full name is required");
  await expect(validationSummary).toContainText("Add at least one supporting source");
  await page.getByRole("button", { name: "Remove source" }).click();
  await expect(page.getByText("No sources added yet.")).toBeVisible();
  await page.getByRole("button", { name: "Add another source" }).click();
  await page.getByLabel("Proposal type").selectOption("correction");
  await page.getByLabel("Search Existing designer").fill("Sarah Burton");
  const existingDesigner = page.getByLabel("Existing designer", { exact: true });
  const sarahId = await existingDesigner.locator("option").filter({ hasText: "Sarah Burton" }).getAttribute("value");
  await existingDesigner.selectOption(sarahId);
  await expect(existingDesigner).not.toHaveValue("");
  await expect(page.getByLabel("Existing record ID")).toHaveCount(0);
  await page.getByLabel("Change action for Biography").selectOption("clear");
  await expect(page.getByText("This field will be cleared if the proposal is approved.")).toBeVisible();
  await expect(page.getByLabel("Change action for Full name").locator("option[value=clear]")).toHaveCount(0);
  await page.getByLabel("Change action for Full name").selectOption("replace");
  await expect(page.getByLabel("Full name", { exact: true })).toBeVisible();

  await page.getByLabel("Record type").selectOption("collection");
  const existingCollection = page.getByLabel("Existing collection", { exact: true });
  await expect(existingCollection).toHaveValue("");
  await page.getByLabel("Search Existing collection").fill("No. 13");
  const collectionId = await existingCollection.locator("option").filter({ hasText: "No. 13" }).getAttribute("value");
  await existingCollection.selectOption(collectionId);
  await expect(existingCollection).not.toHaveValue("");

  await page.getByLabel("Proposal type").selectOption("addition");
  await page.getByLabel("Search Designer or creative lead").fill("Grace Wales Bonner");
  const collectionDesigner = page.getByLabel("Designer or creative lead", { exact: true });
  const graceId = await collectionDesigner.locator("option").filter({ hasText: "Grace Wales Bonner" }).getAttribute("value");
  await collectionDesigner.selectOption(graceId);
  await expect(collectionDesigner).not.toHaveValue("");

  await page.getByLabel("Record type").selectOption("designer");
  await expect(page.getByLabel("Designer or creative lead", { exact: true })).toHaveCount(0);
  await page.getByLabel("Biography").fill("Notes preserved from an incomplete draft.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page).toHaveURL(/\/submissions\/\d+\/edit$/);
  await expect(page.getByText("Draft saved.")).toBeVisible();
  const submissionId = Number(page.url().match(/\/submissions\/(\d+)\/edit$/)[1]);
  await expect(page.getByLabel("Biography")).toHaveValue("Notes preserved from an incomplete draft.");
  await page.getByLabel("Full name").fill(DESIGNER_NAME);
  await page.getByLabel("Nationality").fill("American");
  await page.getByLabel("Why should the archive change?").fill(
    "Exercise the complete isolated browser moderation workflow.",
  );
  await page.getByLabel("Source URL").fill("https://example.test/primary-source");
  await page.getByLabel("Source title").fill("Primary documented source");
  await page.getByRole("button", { name: "Save and resubmit" }).click();
  await expect(page).toHaveURL(/\/submissions\/mine$/);
  const submissionLabel = page.getByText(/#\d+ · designer addition/).first();
  await expect(submissionLabel).toBeVisible();
  await expect(submissionLabel).toContainText(`#${submissionId}`);

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
  await page.route("**/api/moderation/submissions?queue_status=approved*", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Temporary queue failure." }),
    });
  });
  await page.getByRole("button", { name: /^approved /i }).click();
  await expect(page.getByText("Temporary queue failure.")).toBeVisible();
  await expect(page.locator(".moderation-card")).toHaveCount(0);
  await page.unroute("**/api/moderation/submissions?queue_status=approved*");
  await page.getByRole("button", { name: /^submitted /i }).click();
  await expect(page.getByText(new RegExp(`^Submission #${submissionId} · E2E Member$`))).toBeVisible();
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
  await page.route(`**/api/moderation/submissions/${submissionId}/decisions`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Temporary decision failure." }),
    });
  });
  await changesDialog.getByRole("button", { name: "Send change request" }).click();
  await expect(changesDialog.getByRole("alert")).toHaveText("Temporary decision failure.");
  await expect(page.locator(".moderation-card")).toHaveCount(1);
  await page.unroute(`**/api/moderation/submissions/${submissionId}/decisions`);
  await changesDialog.getByRole("button", { name: "Send change request" }).click();
  await expect(page.getByText("The queue is clear.")).toBeVisible();

  await useIdentity(page, "member");
  await page.goto("/submissions/mine");
  const memberSubmission = page
    .getByText(new RegExp(`^#${submissionId} · designer addition$`))
    .locator("..");
  await expect(memberSubmission.getByText("changes requested · version 2")).toBeVisible();
  await memberSubmission.getByRole("link", { name: "View details" }).click();
  await expect(page.getByRole("heading", { name: "Changes requested", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Reviewer feedback" })).toBeVisible();
  await expect(page.locator(".review-decisions").getByText("Please add a second independent source.")).toBeVisible();
  await expect(page.getByLabel(new RegExp(`Audit history for submission ${submissionId}`))).toContainText("Changes requested");
  await page.getByRole("link", { name: "Revise and resubmit" }).click();
  await expect(page.getByLabel("Source URL")).toHaveValue(
    "https://example.test/primary-source",
  );
  await page.getByRole("button", { name: "Add another source" }).click();
  const sourceUrls = page.getByLabel("Source URL");
  await expect(sourceUrls).toHaveCount(2);
  await sourceUrls.nth(1).fill("https://example.test/independent-source");
  const sourceTitles = page.getByLabel("Source title");
  await sourceTitles.nth(1).fill("Independent documented source");
  await page.locator(".source-fields").nth(1).getByRole("button", { name: "Move up" }).click();
  await expect(sourceUrls.nth(0)).toHaveValue("https://example.test/independent-source");
  await expect(sourceUrls.nth(1)).toHaveValue("https://example.test/primary-source");
  await page.getByRole("button", { name: "Save and resubmit" }).click();
  await expect(page.getByText("submitted · version 3")).toBeVisible();

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

  const approvedDesigners = await apiRequest(
    page,
    `/designers?search=${encodeURIComponent(DESIGNER_NAME)}`,
  );
  expect(
    approvedDesigners.body.items.filter(
      (item) => item.full_name === DESIGNER_NAME,
    ),
  ).toHaveLength(1);
  const publishedDesigner = approvedDesigners.body.items.find(
    (item) => item.full_name === DESIGNER_NAME,
  );
  const publishedDetail = await apiRequest(page, `/designers/${publishedDesigner.id}`);
  expect(publishedDetail.body.provenance.sources).toEqual([
    expect.objectContaining({
      url: "https://example.test/independent-source",
      origin: "approved_submission",
    }),
    expect.objectContaining({
      url: "https://example.test/primary-source",
      origin: "approved_submission",
    }),
  ]);

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
  expect(
    restoredDesigners.body.items.some(
      (item) => item.full_name === DESIGNER_NAME,
    ),
  ).toBe(false);
  const audit = await apiRequest(page, `/submissions/${submissionId}/audit`, {
    identity: "admin",
  });
  expect(audit.status).toBe(200);
  expect(audit.body.map((event) => event.event_type)).toEqual([
    "created",
    "draft_updated",
    "submitted",
    "changes_requested",
    "draft_updated",
    "submitted",
    "approved",
    "rolled_back",
  ]);
});
