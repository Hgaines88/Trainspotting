import { useCallback, useEffect, useState } from "react";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";

export default function ModerationQueue() {
  const { appUser, authorizedRequest } = useApplicationUser();
  const [submissions, setSubmissions] = useState([]);
  const [error, setError] = useState("");
  const loadQueue = useCallback(() => authorizedRequest("/moderation/submissions").then(setSubmissions).catch((requestError) => setError(requestError.message)), [authorizedRequest]);
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

  return <>
    <p className="eyebrow">Moderator workspace</p><h1>Review queue</h1>
    <StatusMessage error>{error}</StatusMessage>
    {!error && submissions.length === 0 && <StatusMessage>The queue is clear.</StatusMessage>}
    <div className="moderation-list">{submissions.map((item) => <article className="moderation-card" key={item.id}>
      <p className="eyebrow">Submission #{item.id} · {item.submitter_clerk_user_id === appUser?.clerk_user_id ? "your proposal" : item.submitter_clerk_user_id}</p>
      <h2>{item.record_type} {item.submission_type}</h2><p>{item.explanation}</p>
      <pre>{JSON.stringify(item.proposed_data, null, 2)}</pre>
      <ul>{item.sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url} ↗</a></li>)}</ul>
      {item.submitter_clerk_user_id === appUser?.clerk_user_id ? <StatusMessage>You cannot review your own submission.</StatusMessage> : <div className="actions"><button type="button" onClick={() => decide(item.id, "approve")}>Approve</button><button className="secondary" type="button" onClick={() => decide(item.id, "request_changes")}>Request changes</button><button className="danger" type="button" onClick={() => decide(item.id, "reject")}>Reject</button></div>}
    </article>)}</div>
  </>;
}
