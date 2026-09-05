const NUMERIC_FIELDS = new Set(["birth_year", "designer_id", "release_year", "piece_count"]);

function isBlank(value) {
  return value === undefined || value === null || (typeof value === "string" && value.trim() === "");
}

function coerceNumber(value, label) {
  const cleaned = typeof value === "string" ? value.trim() : value;
  const numeric = Number(cleaned);
  if (!Number.isFinite(numeric)) {
    throw new Error(`Enter a valid number for ${label}.`);
  }
  return numeric;
}

export function buildProposedData({ fields, fieldActions, submissionType, fieldLabels = {} }) {
  const labelFor = (key) => fieldLabels[key] || key;
  const coerceValue = (key, value) => (
    NUMERIC_FIELDS.has(key) ? coerceNumber(value, labelFor(key)) : value
  );

  if (submissionType !== "correction") {
    return Object.fromEntries(
      Object.entries(fields)
        .filter(([, value]) => !isBlank(value))
        .map(([key, value]) => [key, coerceValue(key, value)]),
    );
  }

  return Object.fromEntries(
    Object.entries(fieldActions).flatMap(([key, action]) => {
      if (action === "unchanged") return [];
      if (action === "clear") return [[key, null]];
      const value = fields[key];
      if (isBlank(value)) {
        throw new Error(
          `Enter a replacement value for ${labelFor(key)} or choose another change action.`,
        );
      }
      return [[key, coerceValue(key, value)]];
    }),
  );
}
