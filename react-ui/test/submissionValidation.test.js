import assert from "node:assert/strict";
import test from "node:test";
import { startedSources, validateForReview } from "../src/submissionValidation.js";

const labels = { full_name: "Full name", designer_id: "Designer", label: "Label", season: "Season", release_year: "Release year", status: "Status" };

test("source preparation removes blank rows and trims retained values", () => {
  assert.deepEqual(startedSources([
    { url: "", title: "", notes: "" },
    { url: " https://example.com/source ", title: " Archive ", notes: " " },
  ]), [{ url: "https://example.com/source", title: "Archive", notes: null }]);
});

test("review validation reports missing correction intent and evidence", () => {
  assert.deepEqual(validateForReview({
    recordType: "designer",
    submissionType: "correction",
    targetId: "",
    proposedData: {},
    explanation: "",
    sources: [],
    fieldLabels: labels,
  }), [
    "Choose the existing record this correction applies to.",
    "Choose at least one field to replace or clear.",
    "Explain why the archive should change.",
    "Add at least one supporting source.",
  ]);
});

test("review validation rejects incomplete, invalid, and duplicate sources", () => {
  const errors = validateForReview({
    recordType: "designer",
    submissionType: "addition",
    proposedData: { full_name: "Example Designer" },
    explanation: "Documented addition.",
    sources: [
      { url: "", title: "Started", notes: null },
      { url: "not-a-url", title: null, notes: null },
      { url: "https://example.com", title: null, notes: null },
      { url: "https://example.com", title: null, notes: null },
    ],
    fieldLabels: labels,
  });
  assert.deepEqual(errors, [
    "Source 1 needs a URL or must be removed.",
    "Source 2 must use a valid http:// or https:// URL.",
    "Remove duplicate supporting source URLs.",
  ]);
});
