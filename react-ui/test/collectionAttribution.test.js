import assert from "node:assert/strict";
import test from "node:test";
import { collectionCreditLine, collectionCreditNames } from "../src/collectionAttribution.js";


test("ordered credits are authoritative for collection attribution", () => {
  const collection = {
    lead_designer: "Legacy primary",
    credits: [
      { designer_name: "Miuccia Prada", position: 1 },
      { designer_name: "Raf Simons", position: 2 },
    ],
  };

  assert.deepEqual(collectionCreditNames(collection), ["Miuccia Prada", "Raf Simons"]);
  assert.equal(collectionCreditLine(collection), "Miuccia Prada + Raf Simons");
});


test("legacy lead remains a compatibility fallback when credits are unavailable", () => {
  assert.equal(collectionCreditLine({ lead_designer: "Archive Designer" }), "Archive Designer");
  assert.equal(collectionCreditLine({ credits: [] }), "");
});
