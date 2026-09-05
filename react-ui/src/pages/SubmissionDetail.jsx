import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";
import SubmissionAuditTimeline from "../components/SubmissionAuditTimeline";
import SubmissionComparison from "../components/SubmissionComparison";

const STATUS_DETAILS = {
  draft: ["Draft in progress", "Finish the proposal and submit it when the evidence is ready."],
  submitted: ["Awaiting review", "A moderator can now evaluate the proposal and its supporting sources."],
  changes_requested: ["Changes requested", "Review the moderator’s feedback, revise the proposal, and resubmit it."],
  approved: ["Approved and published", "The approved proposal has been promoted into the public archive."],
  rejected: ["Rejected", "This proposal is closed. The reviewer’s decision remains in the audit history."],
  rolled_back: ["Publication rolled back", "The canonical change was reversed while preserving its complete history."],
};

function canonicalPath(submission) {
  const recordId = submission.promotion?.canonical_record_id;
  if (!recordId || !["approved", "rolled_back"].includes(submission.status)) return null;
  return submission.record_type === "designer" ? `/designers/${recordId}` : `/collections/${recordId}`;
}

export default function SubmissionDetail() {
  const { submissionId } = useParams();
  const { appUser, authorizedRequest } = useApplicationUser();
  const [submission, setSubmission] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    authorizedRequest(`/submissions/${submissionId}`)
      .then(setSubmission)
      .catch((requestError) => setError(requestError.message));
  }, [authorizedRequest, submissionId]);

  if (error) return <StatusMessage error>{error}</StatusMessage>;
  if (!submission) return <StatusMessage>Loading submission…</StatusMessage>;

  const [statusLabel, statusDescription] = STATUS_DETAILS[submission.status] || [submission.status, ""];
  const editable = ["draft", "changes_requested"].includes(submission.status)
    && submission.submitter_clerk_user_id === appUser?.clerk_user_id;
  const archivePath = canonicalPath(submission);

  return <>
    <div className="page-heading"><div><p className="eyebrow">Submission #{submission.id} · version {submission.version}</p><h1>{statusLabel}</h1></div><Link className="button secondary" to="/submissions/mine">All submissions</Link></div>
    <section className={`submission-status status-${submission.status}`} aria-labelledby="submission-status-heading">
      <h2 id="submission-status-heading">{statusLabel}</h2>
      <p>{statusDescription}</p>
      <dl><div><dt>Record</dt><dd>{submission.record_type} {submission.submission_type}</dd></div><div><dt>Current status</dt><dd>{submission.status.replaceAll("_", " ")}</dd></div></dl>
    </section>
    <div className="actions">
      {editable && <Link className="button" to={`/submissions/${submission.id}/edit`}>{submission.status === "changes_requested" ? "Revise and resubmit" : "Continue draft"}</Link>}
      {archivePath && submission.status === "approved" && <Link className="button" to={archivePath}>View published record</Link>}
    </div>
    <section className="section"><h2>Proposal</h2><p>{submission.explanation || "An explanation has not been added to this draft."}</p><SubmissionComparison submission={submission} /></section>
    <section className="section"><h2>Supporting sources</h2>{submission.sources.length === 0 ? <StatusMessage>No supporting sources have been added.</StatusMessage> : <ol className="submission-sources">{submission.sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url} ↗</a>{source.notes && <p>{source.notes}</p>}</li>)}</ol>}</section>
    <section className="section"><h2>Reviewer feedback</h2>{submission.decisions.length === 0 ? <StatusMessage>No reviewer decision has been recorded yet.</StatusMessage> : <ol className="review-decisions">{submission.decisions.map((decision) => <li key={decision.id}><strong>{decision.decision.replaceAll("_", " ")}</strong><span>{decision.reviewer_display_name || "Trainspotting reviewer"}</span>{decision.notes && <p>{decision.notes}</p>}</li>)}</ol>}</section>
    <SubmissionAuditTimeline events={submission.audit} submissionId={submission.id} />
  </>;
}
