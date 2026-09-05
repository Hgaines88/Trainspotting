const REQUIRED_ADDITION_FIELDS = {
  designer: ["full_name"],
  collection: ["designer_id", "label", "season", "release_year", "status"],
};

function isHttpUrl(value) {
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol) && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

const FIELD_LIMITS = {
  full_name: 120,
  nationality: 120,
  website: 500,
  biography: 10_000,
  label: 120,
  name: 120,
  season: 40,
  description: 10_000,
  source_url: 500,
  youtube_video_id: 200,
};

export function startedSources(sources) {
  return sources
    .filter((source) => source.url.trim() || source.title.trim() || source.notes.trim())
    .map((source) => ({
      url: source.url.trim(),
      title: source.title.trim() || null,
      notes: source.notes.trim() || null,
    }));
}

export function validateForReview({
  recordType,
  submissionType,
  targetId,
  proposedData,
  explanation,
  sources,
  fieldLabels,
}) {
  const errors = [];
  if (submissionType === "correction" && !targetId) {
    errors.push("Choose the existing record this correction applies to.");
  }
  if (submissionType === "correction" && Object.keys(proposedData).length === 0) {
    errors.push("Choose at least one field to replace or clear.");
  }
  if (submissionType === "addition") {
    for (const field of REQUIRED_ADDITION_FIELDS[recordType]) {
      const value = proposedData[field];
      if (value === undefined || value === null || (typeof value === "string" && !value.trim())) {
        errors.push(`${fieldLabels[field]} is required for this addition.`);
      }
    }
  }
  for (const [field, limit] of Object.entries(FIELD_LIMITS)) {
    if (typeof proposedData[field] === "string" && proposedData[field].length > limit) {
      errors.push(`${fieldLabels[field]} must be ${limit.toLocaleString()} characters or fewer.`);
    }
  }
  if (proposedData.birth_year !== undefined && (proposedData.birth_year < 1800 || proposedData.birth_year > 2100)) {
    errors.push("Birth year must be between 1800 and 2100.");
  }
  if (proposedData.release_year !== undefined && (proposedData.release_year < 1900 || proposedData.release_year > 2100)) {
    errors.push("Release year must be between 1900 and 2100.");
  }
  if (proposedData.piece_count !== undefined && proposedData.piece_count < 0) {
    errors.push("Piece count cannot be negative.");
  }
  for (const [field, label] of [["website", "Website"], ["source_url", "Curated source URL"]]) {
    const value = proposedData[field];
    if (value !== undefined && value !== null && !isHttpUrl(value)) {
      errors.push(`${label} must use a valid http:// or https:// URL.`);
    }
  }
  if (!explanation.trim()) errors.push("Explain why the archive should change.");
  else if (explanation.length > 2000) errors.push("The explanation must be 2,000 characters or fewer.");
  if (sources.length === 0) errors.push("Add at least one supporting source.");
  sources.forEach((source, index) => {
    if (!source.url) errors.push(`Source ${index + 1} needs a URL or must be removed.`);
    else if (!isHttpUrl(source.url)) errors.push(`Source ${index + 1} must use a valid http:// or https:// URL.`);
    else if (source.url.length > 500) errors.push(`Source ${index + 1} URL must be 500 characters or fewer.`);
    if (source.title?.length > 200) errors.push(`Source ${index + 1} title must be 200 characters or fewer.`);
    if (source.notes?.length > 1000) errors.push(`Source ${index + 1} notes must be 1,000 characters or fewer.`);
  });
  const normalizedUrls = sources.map((source) => source.url).filter(Boolean);
  if (new Set(normalizedUrls).size !== normalizedUrls.length) {
    errors.push("Remove duplicate supporting source URLs.");
  }
  return errors;
}
