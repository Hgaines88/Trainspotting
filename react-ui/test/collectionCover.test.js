import assert from "node:assert/strict";
import test from "node:test";
import { collectionCoverIdentity, collectionCoverStyle } from "../src/collectionCover.js";

const collection = {
  id: 42,
  label: "Wales Bonner",
  season: "Spring/Summer",
  release_year: 2025,
};

test("collection cover identity and style are stable", () => {
  assert.equal(collectionCoverIdentity(collection), "42|Wales Bonner|Spring/Summer|2025");
  assert.deepEqual(collectionCoverStyle(collection), collectionCoverStyle({ ...collection }));
});

test("collection cover styling supports sparse records", () => {
  assert.equal(collectionCoverIdentity({}), "");
  assert.deepEqual(collectionCoverStyle({}), collectionCoverStyle({}));
  assert.ok(collectionCoverStyle({})["--cover-accent"]);
});

test("collection cover identity changes with a canonical key", () => {
  assert.notEqual(collectionCoverIdentity({ ...collection, id: 43 }), collectionCoverIdentity(collection));
});
