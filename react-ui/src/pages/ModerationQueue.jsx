import { useCallback, useEffect, useState } from "react";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import ModerationActionDialog from "../components/ModerationActionDialog";
import StatusMessage from "../components/StatusMessage";
import SubmissionAuditTimeline from "../components/SubmissionAuditTimeline";
import SubmissionComparison from "../components/SubmissionComparison";

export default function ModerationQueue() {
  const { appUser, authorizedRequest } = useApplicationUser();
  const [submissions, setSubmissions] = useState([]);
  const [queueStatus, setQueueStatus] = useState("submitted");
  const [counts, setCounts] = useState({});
  const [pagination, setPagination] = useState({ page: 1, page_size: 10, total: 0, total_pages: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const loadQueue = useCallback(() => {
    setQueueError("");
    setActionError("");
    setLoading(true);
    return authorizedRequest(`/moderation/submissions?queue_status=${queueStatus}&page=${page}&page_size=10`)
      .then((response) => {
        setSubmissions(response.items);
        setCounts(response.counts);
        setPagination(response.pagination);
        if (response.pagination.total_pages > 0 && page > response.pagination.total_pages) {
          setPage(response.pagination.total_pages);
        }
      })
      .catch((requestError) => setQueueError(requestError.message))
      .finally(() => setLoading(false));
  }, [authorizedRequest, page, queueStatus]);
  useEffect(() => { loadQueue(); }, [loadQueue]);

  async function confirmAction(notes) {
    if (!pendingAction || submitting) return;
    const { id, action } = pendingAction;
    setSubmitting(true);
    setActionError("");
    try {
      if (action === "rollback") {
        await authorizedRequest(`/moderation/submissions/${id}/rollback`, {
          method: "POST",
          body: JSON.stringify({ reason: notes }),
        });
      } else {
        await authorizedRequest(`/moderation/submissions/${id}/decisions`, {
          method: "POST",
          body: JSON.stringify({ decision: action, notes }),
        });
      }
      setPendingAction(null);
      await loadQueue();
    } catch (requestError) { setActionError(requestError.message); }
    finally { setSubmitting(false); }
  }

  return <>
    <p className="eyebrow">Moderator workspace</p><h1>Review queue</h1>
    <div className="queue-filters" aria-label="Submission status">{["submitted", "changes_requested", "approved", "rejected", "rolled_back"].map((itemStatus) => <button aria-pressed={queueStatus === itemStatus} className={queueStatus === itemStatus ? "active" : "secondary"} type="button" key={itemStatus} onClick={() => { setPage(1); setQueueStatus(itemStatus); }}>{itemStatus.replaceAll("_", " ")} <span aria-label={`${counts[itemStatus] || 0} ${(counts[itemStatus] || 0) === 1 ? "submission" : "submissions"}`}>{counts[itemStatus] || 0}</span></button>)}</div>
    <StatusMessage error>{queueError}</StatusMessage>
    {loading && <StatusMessage>Loading review queue…</StatusMessage>}
    {!loading && !queueError && submissions.length === 0 && <StatusMessage>The queue is clear.</StatusMessage>}
    {!loading && !queueError && <div className="moderation-list">{submissions.map((item) => <article className="moderation-card" key={item.id}>
      <p className="eyebrow">Submission #{item.id} · {item.submitter_clerk_user_id === appUser?.clerk_user_id ? "your proposal" : (item.submitter_display_name || "Trainspotting member")}</p>
      <h2>{item.record_type} {item.submission_type}</h2><p>{item.explanation}</p>
      <SubmissionComparison submission={item} />
      <ul>{item.sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url} ↗</a></li>)}</ul>
      <SubmissionAuditTimeline events={item.audit} submissionId={item.id} />
      {item.status === "submitted" && (item.submitter_clerk_user_id === appUser?.clerk_user_id ? <StatusMessage>You cannot review your own submission.</StatusMessage> : <div className="actions"><button type="button" onClick={() => setPendingAction({ id: item.id, action: "approve" })}>Approve</button><button className="secondary" type="button" onClick={() => setPendingAction({ id: item.id, action: "request_changes" })}>Request changes</button><button className="danger" type="button" onClick={() => setPendingAction({ id: item.id, action: "reject" })}>Reject</button></div>)}
      {item.status === "approved" && appUser?.role === "admin" && !item.promotion?.rolled_back_at && <div className="actions"><button className="danger" type="button" onClick={() => setPendingAction({ id: item.id, action: "rollback" })}>Roll back approval</button></div>}
    </article>)}</div>}
    {!loading && !queueError && pagination.total_pages > 1 && <nav className="pagination" aria-label="Review queue pages">
      <button className="secondary" type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
      <span>Page {pagination.page} of {pagination.total_pages} · {pagination.total} submissions</span>
      <button className="secondary" type="button" disabled={page === pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
    </nav>}
    <ModerationActionDialog action={pendingAction?.action} busy={submitting} error={actionError} onCancel={() => { setActionError(""); setPendingAction(null); }} onConfirm={confirmAction} />
  </>;
}
