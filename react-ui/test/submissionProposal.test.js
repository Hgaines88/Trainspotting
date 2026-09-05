import assert from "node:assert/strict";
import test from "node:test";
import { buildProposedData } from "../src/submissionProposal.js";

test("corrections preserve unchanged, clear, and replacement intent", () => {
  assert.deepEqual(buildProposedData({
    submissionType: "correction",
    fields: { full_name: "Updated name", biography: "", nationality: "Ignored" },
    fieldActions: { full_name: "replace", biography: "clear", nationality: "unchanged" },
  }), {
    full_name: "Updated name",
    biography: null,
  });
});

test("numeric replacements are serialized as numbers", () => {
  assert.deepEqual(buildProposedData({
    submissionType: "correction",
    fields: { birth_year: "1988" },
    fieldActions: { birth_year: "replace" },
  }), { birth_year: 1988 });
});

test("invalid numeric values cannot become accidental null clears", () => {
  assert.throws(() => buildProposedData({
    submissionType: "correction",
    fields: { birth_year: "not-a-number" },
    fieldActions: { birth_year: "replace" },
    fieldLabels: { birth_year: "Birth year" },
  }), /valid number for Birth year/);

  assert.throws(() => buildProposedData({
    submissionType: "addition",
    fields: { piece_count: Number.POSITIVE_INFINITY },
    fieldActions: {},
    fieldLabels: { piece_count: "Piece count" },
  }), /valid number for Piece count/);
});

test("an incomplete replacement reports the human field label", () => {
  assert.throws(() => buildProposedData({
    submissionType: "correction",
    fields: { biography: "" },
    fieldActions: { biography: "replace" },
    fieldLabels: { biography: "Biography" },
  }), /replacement value for Biography/);
});
