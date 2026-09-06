const FIELD_LABELS = {
  biography: "Biography",
  birth_year: "Birth year",
  description: "Description",
  designer_id: "Designer ID",
  full_name: "Full name",
  label: "Label",
  name: "Collection name",
  nationality: "Nationality",
  piece_count: "Piece count",
  release_year: "Release year",
  season: "Season",
  source_url: "Source URL",
  status: "Status",
  website: "Website",
  youtube_video_id: "YouTube video ID",
  category: "Descriptor category",
  canonical_value: "Canonical descriptor",
  strength: "Descriptor strength",
  evidence_note: "Evidence note",
};

function displayValue(value, emptyLabel) {
  if (value === null || value === undefined || value === "") return <span className="empty-value">{emptyLabel}</span>;
  return String(value);
}

export default function SubmissionComparison({ submission }) {
  const proposed = submission.proposed_data;
  const historicalBefore = submission.promotion?.before_snapshot;
  const current = historicalBefore ?? submission.current_data;
  const enrichment = submission.proposal_kind === "enrichment";
  const addition = submission.submission_type === "addition" || enrichment;

  return <div className="comparison-wrap">
    <table className="comparison-table">
      <caption>{enrichment ? "Proposed editorial enrichment" : (addition ? "Proposed archive record" : "Proposed field changes")}</caption>
      <thead><tr><th scope="col">Field</th>{!addition && <th scope="col">Current</th>}<th scope="col">Proposed</th></tr></thead>
      <tbody>{Object.entries(proposed).map(([field, value]) => <tr key={field}>
        <th scope="row">{FIELD_LABELS[field] || field.replaceAll("_", " ")}</th>
        {!addition && <td>{displayValue(current?.[field], "Not recorded")}</td>}
        <td className="proposed-value">{displayValue(value, "Clear field")}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}
