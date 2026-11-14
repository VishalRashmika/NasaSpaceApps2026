/**
 * Pure legend form validation (F-072, docs/09 §3).
 */

export const ALLOWED_CATEGORIES = [
  "temperature",
  "ocean",
  "precipitation",
  "aerosol",
  "vegetation",
  "ice",
  "generic",
  "sea_surface_height",
  "wind_speed",
  "aerosol_optical_depth",
  "carbon_dioxide",
  "chlorophyll",
  "other",
];

export const ALLOWED_KINDS = ["sequential", "diverging"];

export const ALLOWED_SCALES = ["linear", "log"];

export const ALLOWED_ORIENTATIONS = ["horizontal", "vertical"];

/**
 * Validates legend metadata form inputs.
 *
 * @param {object} values Form values object
 * @returns {{ ok: boolean, errors: Record<string, string> }} Validation result
 */
export function validateLegendForm(values) {
  const errors = {};

  if (!values || typeof values !== "object") {
    return { ok: false, errors: { form: "Form values required" } };
  }

  // Label validation
  if (!values.label || typeof values.label !== "string" || !values.label.trim()) {
    errors.label = "Label is required";
  }

  // Units validation
  if (!values.units || typeof values.units !== "string" || !values.units.trim()) {
    errors.units = "Units are required";
  }

  // Numeric bounds
  const vminRaw = values.vmin;
  const vmaxRaw = values.vmax;

  const vminNum = vminRaw !== "" && vminRaw !== null && vminRaw !== undefined ? Number(vminRaw) : NaN;
  const vmaxNum = vmaxRaw !== "" && vmaxRaw !== null && vmaxRaw !== undefined ? Number(vmaxRaw) : NaN;

  if (Number.isNaN(vminNum) || !Number.isFinite(vminNum)) {
    errors.vmin = "Valid minimum value is required";
  }
  if (Number.isNaN(vmaxNum) || !Number.isFinite(vmaxNum)) {
    errors.vmax = "Valid maximum value is required";
  }

  if (Number.isFinite(vminNum) && Number.isFinite(vmaxNum)) {
    if (vminNum >= vmaxNum) {
      errors.vmax = "Maximum value must be strictly greater than minimum value";
    }

    if (values.scale === "log" && vminNum <= 0) {
      errors.vmin = "Minimum value must be greater than zero for logarithmic scale";
    }

    if (values.kind === "diverging") {
      const centerRaw = values.center;
      const centerNum = centerRaw !== "" && centerRaw !== null && centerRaw !== undefined ? Number(centerRaw) : NaN;
      if (Number.isNaN(centerNum) || !Number.isFinite(centerNum)) {
        errors.center = "Diverging colormap requires a numeric center value";
      } else if (centerNum <= vminNum || centerNum >= vmaxNum) {
        errors.center = "Center must lie strictly between minimum and maximum value";
      }
    }
  }

  if (values.category && !ALLOWED_CATEGORIES.includes(values.category)) {
    errors.category = `Invalid category: ${values.category}`;
  }

  if (values.kind && !ALLOWED_KINDS.includes(values.kind)) {
    errors.kind = `Invalid kind: ${values.kind}`;
  }

  if (values.scale && !ALLOWED_SCALES.includes(values.scale)) {
    errors.scale = `Invalid scale: ${values.scale}`;
  }

  if (values.orientation && !ALLOWED_ORIENTATIONS.includes(values.orientation)) {
    errors.orientation = `Invalid orientation: ${values.orientation}`;
  }

  return {
    ok: Object.keys(errors).length === 0,
    errors,
  };
}
