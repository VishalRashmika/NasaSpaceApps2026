import { test } from "node:test";
import assert from "node:assert/strict";
import { formatValue, formatTime } from "../js/core/format.js";

test("formatValue formats numbers with units and sensible digits", () => {
  assert.equal(formatValue(24.5, "°C"), "24.5 °C");
  assert.equal(formatValue(0, "m/s"), "0 m/s");
  assert.equal(formatValue(150.0, "K"), "150 K");
  assert.equal(formatValue(-3.14159, "ppm"), "-3.14 ppm");
  assert.equal(formatValue(12.34, null), "12.34");
  assert.equal(formatValue(12.34, ""), "12.34");
});

test("formatValue returns 'No data' for null or NaN values", () => {
  assert.equal(formatValue(null, "°C"), "No data");
  assert.equal(formatValue(undefined, "°C"), "No data");
  assert.equal(formatValue(NaN, "°C"), "No data");
  assert.equal(formatValue("invalid", "°C"), "No data");
});

test("formatTime formats seconds into mm:ss", () => {
  assert.equal(formatTime(0), "00:00");
  assert.equal(formatTime(5), "00:05");
  assert.equal(formatTime(65), "01:05");
  assert.equal(formatTime(3599), "59:59");
  assert.equal(formatTime(-10), "00:00");
  assert.equal(formatTime(null), "00:00");
});
