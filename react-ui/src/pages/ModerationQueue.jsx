import { useCallback, useEffect, useState } from "react";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import ModerationActionDialog from "../components/ModerationActionDialog";
import StatusMessage from "../components/StatusMessage";

export default function ModerationQueue() {
  const { appUser, authorizedRequest } = useApplicationUser();
  const [submissions, setSubmissions] = useState([]);
  const [queueStatus, setQueueStatus] = useState("submitted");
  const [error, setError] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const loadQueue = useCallback(() => {
    setError("");
    return authorizedRequest(`/moderation/submissions?queue_status=${queueStatus}`).then(setSubmissions).catch((requestError) => setError(requestError.message));
  }, [authorizedRequest, queueStatus]);
  useEffect(() => { loadQueue(); }, [loadQueue]);

  async function confirmAction(notes) {
    if (!pendingAction || submitting) return;
    const { id, action } = pendingAction;
    setSubmitting(true);
    setError("");
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
    } catch (requestError) { setError(requestError.message); }
    finally { setSubmitting(false); }
  }

  return <>
    <p className="eyebrow">Moderator workspace</p><h1>Review queue</h1>
    <div className="queue-filters" aria-label="Submission status">{["submitted", "changes_requested", "approved", "rejected", "rolled_back"].map((itemStatus) => <button className={queueStatus === itemStatus ? "active" : "secondary"} type="button" key={itemStatus} onClick={() => setQueueStatus(itemStatus)}>{itemStatus.replace("_", " ")}</button>)}</div>
    <StatusMessage error>{error}</StatusMessage>
    {!error && submissions.length === 0 && <StatusMessage>The queue is clear.</StatusMessage>}
    <div className="moderation-list">{submissions.map((item) => <article className="moderation-card" key={item.id}>
      <p className="eyebrow">Submission #{item.id} · {item.submitter_clerk_user_id === appUser?.clerk_user_id ? "your proposal" : (item.submitter_display_name || "Trainspotting member")}</p>
      <h2>{item.record_type} {item.submission_type}</h2><p>{item.explanation}</p>
      <pre>{JSON.stringify(item.proposed_data, null, 2)}</pre>
      <ul>{item.sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url} ↗</a></li>)}</ul>
      {item.status === "submitted" && (item.submitter_clerk_user_id === appUser?.clerk_user_id ? <StatusMessage>You cannot review your own submission.</StatusMessage> : <div className="actions"><button type="button" onClick={() => setPendingAction({ id: item.id, action: "approve" })}>Approve</button><button className="secondary" type="button" onClick={() => setPendingAction({ id: item.id, action: "request_changes" })}>Request changes</button><button className="danger" type="button" onClick={() => setPendingAction({ id: item.id, action: "reject" })}>Reject</button></div>)}
      {item.status === "approved" && appUser?.role === "admin" && !item.promotion?.rolled_back_at && <div className="actions"><button className="danger" type="button" onClick={() => setPendingAction({ id: item.id, action: "rollback" })}>Roll back approval</button></div>}
    </article>)}</div>
    <ModerationActionDialog action={pendingAction?.action} busy={submitting} onCancel={() => setPendingAction(null)} onConfirm={confirmAction} />
  </>;
}
