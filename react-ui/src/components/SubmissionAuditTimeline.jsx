const EVENT_LABELS = {
  approved: "Approved",
  changes_requested: "Changes requested",
  created: "Draft created",
  draft_updated: "Draft updated",
  rejected: "Rejected",
  rolled_back: "Approval rolled back",
  submitted: "Submitted",
};

function readableDate(value) {
  if (!value) return "Time unavailable";
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

export default function SubmissionAuditTimeline({ events, submissionId }) {
  return <section className="audit-history" aria-label={`Audit history for submission ${submissionId}`}>
    <h3>Audit history</h3>
    <ol>{events.map((event) => <li key={event.id}>
      <div><strong>{EVENT_LABELS[event.event_type] || event.event_type.replaceAll("_", " ")}</strong><span>{event.actor_display_name || "Trainspotting member"}</span></div>
      <time dateTime={event.created_at}>{readableDate(event.created_at)}</time>
      {event.event_data?.notes && <p>{event.event_data.notes}</p>}
      {event.event_data?.reason && <p>{event.event_data.reason}</p>}
    </li>)}</ol>
  </section>;
}
