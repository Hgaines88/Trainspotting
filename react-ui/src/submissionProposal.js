const NUMERIC_FIELDS = new Set(["birth_year", "designer_id", "release_year", "piece_count"]);

export function buildProposedData({ fields, fieldActions, submissionType, fieldLabels = {} }) {
  if (submissionType !== "correction") {
    return Object.fromEntries(
      Object.entries(fields)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, NUMERIC_FIELDS.has(key) ? Number(value) : value]),
    );
  }

  return Object.fromEntries(Object.entries(fieldActions).flatMap(([key, action]) => {
    if (action === "unchanged") return [];
    if (action === "clear") return [[key, null]];
    const value = fields[key];
    if (value === "" || value === undefined) {
      throw new Error(
        `Enter a replacement value for ${fieldLabels[key] || key} or choose another change action.`,
      );
    }
    return [[key, NUMERIC_FIELDS.has(key) ? Number(value) : value]];
  }));
}
