import { useCallback, useEffect, useState } from "react";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";

export default function ModerationQueue() {
  const { appUser, authorizedRequest } = useApplicationUser();
  const [submissions, setSubmissions] = useState([]);
  const [queueStatus, setQueueStatus] = useState("submitted");
  const [error, setError] = useState("");
  const loadQueue = useCallback(() => {
    setError("");
    return authorizedRequest(`/moderation/submissions?queue_status=${queueStatus}`).then(setSubmissions).catch((requestError) => setError(requestError.message));
  }, [authorizedRequest, queueStatus]);
  useEffect(() => { loadQueue(); }, [loadQueue]);

  async function decide(id, decision) {
    let notes = null;
    if (decision !== "approve") {
      notes = window.prompt(decision === "reject" ? "Why is this rejected?" : "What changes are required?");
      if (!notes) return;
    } else if (!window.confirm("Approve and promote this proposal into the public archive?")) return;
    try {
      await authorizedRequest(`/moderation/submissions/${id}/decisions`, { method: "POST", body: JSON.stringify({ decision, notes }) });
      await loadQueue();
    } catch (requestError) { setError(requestError.message); }
  }

  async function rollback(id) {
    const reason = window.prompt("Why should this approved change be rolled back?");
    if (!reason) return;
    if (!window.confirm("Restore the pre-approval archive state? This action is audited.")) return;
    try {
      await authorizedRequest(`/moderation/submissions/${id}/rollback`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      await loadQueue();
    } catch (requestError) { setError(requestError.message); }
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
      {item.status === "submitted" && (item.submitter_clerk_user_id === appUser?.clerk_user_id ? <StatusMessage>You cannot review your own submission.</StatusMessage> : <div className="actions"><button type="button" onClick={() => decide(item.id, "approve")}>Approve</button><button className="secondary" type="button" onClick={() => decide(item.id, "request_changes")}>Request changes</button><button className="danger" type="button" onClick={() => decide(item.id, "reject")}>Reject</button></div>)}
      {item.status === "approved" && appUser?.role === "admin" && !item.promotion?.rolled_back_at && <div className="actions"><button className="danger" type="button" onClick={() => rollback(item.id)}>Roll back approval</button></div>}
    </article>)}</div>
  </>;
}
