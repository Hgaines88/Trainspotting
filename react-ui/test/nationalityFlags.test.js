import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import { nationalityFlags as reactFlags } from "../src/nationalityFlags.js";

const require = createRequire(import.meta.url);
const { nationalityFlags: vanillaFlags } = require("../../web/flags.js");

const expectedFlags = {
  American: "🇺🇸",
  Belgian: "🇧🇪",
  British: "🇬🇧",
  "British-Jamaican": "🇬🇧 🇯🇲",
  Canadian: "🇨🇦",
  "Dominican-American": "🇩🇴 🇺🇸",
  French: "🇫🇷",
  "French-American": "🇫🇷 🇺🇸",
  "French-Belgian": "🇫🇷 🇧🇪",
  "French-Colombian": "🇫🇷 🇨🇴",
  Georgian: "🇬🇪",
  German: "🇩🇪",
  Italian: "🇮🇹",
  Japanese: "🇯🇵",
  "Liberian-American": "🇱🇷 🇺🇸",
  "Northern Irish": "🇬🇧",
  Russian: "🇷🇺",
};

test("React and Vanilla expose the same nationality flags", () => {
  for (const [nationality, flags] of Object.entries(expectedFlags)) {
    assert.equal(reactFlags(nationality), flags);
    assert.equal(vanillaFlags(nationality), flags);
  }
});

test("unknown or missing nationalities do not render a flag", () => {
  for (const nationality of ["Unknown", "", null, undefined]) {
    assert.equal(reactFlags(nationality), "");
    assert.equal(vanillaFlags(nationality), "");
  }
});

test("nationalities are normalized and supported compounds are composed", () => {
  for (const value of ["american", " American "]) {
    assert.equal(reactFlags(value), "🇺🇸");
    assert.equal(vanillaFlags(value), "🇺🇸");
  }
  assert.equal(reactFlags("Nigerian-British"), "🇳🇬 🇬🇧");
  assert.equal(vanillaFlags("Nigerian-British"), "🇳🇬 🇬🇧");
  assert.equal(reactFlags("South Korean"), "🇰🇷");
  assert.equal(vanillaFlags("South Korean"), "🇰🇷");
});
