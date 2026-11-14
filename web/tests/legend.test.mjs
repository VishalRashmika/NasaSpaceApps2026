import { test } from "node:test";
import assert from "node:assert/strict";
import { validateLegendForm } from "../js/core/legend.js";

test("validateLegendForm succeeds for valid sequential legend", () => {
  const values = {
    label: "Sea Surface Temperature",
    units: "°C",
    vmin: "0",
    vmax: "32",
    kind: "sequential",
    category: "temperature",
    scale: "linear",
    orientation: "horizontal",
  };
  const res = validateLegendForm(values);
  assert.equal(res.ok, true);
  assert.deepEqual(res.errors, {});
});

test("validateLegendForm succeeds for valid diverging legend", () => {
  const values = {
    label: "Temperature Anomaly",
    units: "°C",
    vmin: -4,
    vmax: 4,
    center: 0,
    kind: "diverging",
    category: "temperature",
  };
  const res = validateLegendForm(values);
  assert.equal(res.ok, true);
});

test("validateLegendForm rejects missing or invalid fields", () => {
  const res = validateLegendForm({});
  assert.equal(res.ok, false);
  assert.ok(res.errors.label);
  assert.ok(res.errors.units);
  assert.ok(res.errors.vmin);
  assert.ok(res.errors.vmax);
});

test("validateLegendForm enforces vmin < vmax", () => {
  const res = validateLegendForm({
    label: "Test",
    units: "m",
    vmin: "100",
    vmax: "50",
  });
  assert.equal(res.ok, false);
  assert.ok(res.errors.vmax);
});

test("validateLegendForm enforces log scale vmin > 0", () => {
  const res = validateLegendForm({
    label: "Chlorophyll",
    units: "mg/m^3",
    vmin: "-0.5",
    vmax: "10",
    scale: "log",
  });
  assert.equal(res.ok, false);
  assert.ok(res.errors.vmin);
});

test("validateLegendForm enforces diverging center within (vmin, vmax)", () => {
  const res = validateLegendForm({
    label: "Anomaly",
    units: "°C",
    vmin: "0",
    vmax: "10",
    center: "15",
    kind: "diverging",
  });
  assert.equal(res.ok, false);
  assert.ok(res.errors.center);
});
