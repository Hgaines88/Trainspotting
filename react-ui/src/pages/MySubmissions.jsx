import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";

export default function MySubmissions() {
  const { authorizedRequest } = useApplicationUser();
  const [submissions, setSubmissions] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    authorizedRequest("/submissions/mine").then(setSubmissions).catch((requestError) => setError(requestError.message));
  }, [authorizedRequest]);
  return <>
    <div className="page-heading"><div><p className="eyebrow">Community research</p><h1>My submissions</h1></div><Link className="button" to="/submissions/new">New proposal</Link></div>
    <StatusMessage error>{error}</StatusMessage>
    {!error && submissions.length === 0 && <StatusMessage>No submissions yet.</StatusMessage>}
    <ul className="collection-list">{submissions.map((item) => <li key={item.id}><div className="submission-row"><strong>#{item.id} · {item.record_type} {item.submission_type}</strong><span>{item.status.replace("_", " ")} · version {item.version}</span><small>{item.explanation || "Draft explanation not provided"}</small>{item.decisions.at(-1)?.notes && <small>Reviewer: {item.decisions.at(-1).notes}</small>}</div></li>)}</ul>
  </>;
}
