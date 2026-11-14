import { test } from "node:test";
import assert from "node:assert/strict";
import { describeHealth } from "../js/core/version.js";

test("describeHealth reports ok", () => {
  assert.match(describeHealth({ status: "ok", version: "1", mapping_version: "1.0.0" }), /Backend ok/);
});
test("describeHealth handles failure", () => {
  assert.equal(describeHealth(null), "Backend unavailable.");
});
