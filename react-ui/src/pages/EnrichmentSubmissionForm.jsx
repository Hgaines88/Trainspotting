import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";

export default function EnrichmentSubmissionForm() {
  const { collectionId, submissionId } = useParams();
  const editing = Boolean(submissionId);
  const navigate = useNavigate();
  const { authorizedRequest } = useApplicationUser();
  const [collection, setCollection] = useState(null);
  const [vocabulary, setVocabulary] = useState({});
  const [category, setCategory] = useState("");
  const [canonicalValue, setCanonicalValue] = useState("");
  const [strength, setStrength] = useState("supporting");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [explanation, setExplanation] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceNotes, setSourceNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const submissionRequest = editing
      ? authorizedRequest(`/submissions/${submissionId}`)
      : Promise.resolve(null);
    Promise.all([authorizedRequest("/editorial-vocabulary"), submissionRequest])
      .then(async ([vocabularyResult, submission]) => {
      if (submission && (
        submission.proposal_kind !== "enrichment"
        || !["draft", "changes_requested"].includes(submission.status)
      )) throw new Error("This enrichment submission is not available for editing.");
      const targetCollectionId = submission?.target_id || collectionId;
      const collectionResult = await apiRequest(`/collections/${targetCollectionId}`);
      setCollection(collectionResult);
      setVocabulary(vocabularyResult);
      const firstCategory = submission?.proposed_data.category || Object.keys(vocabularyResult)[0] || "";
      setCategory(firstCategory);
      setCanonicalValue(submission?.proposed_data.canonical_value || vocabularyResult[firstCategory]?.[0] || "");
      if (submission) {
        setStrength(submission.proposed_data.strength);
        setEvidenceNote(submission.proposed_data.evidence_note);
        setExplanation(submission.explanation || "");
        const source = submission.sources[0] || {};
        setSourceUrl(source.url || "");
        setSourceTitle(source.title || "");
        setSourceNotes(source.notes || "");
      }
    }).catch((requestError) => setError(requestError.message));
  }, [authorizedRequest, collectionId, editing, submissionId]);

  const values = useMemo(() => vocabulary[category] || [], [category, vocabulary]);

  function changeCategory(event) {
    const nextCategory = event.target.value;
    setCategory(nextCategory);
    setCanonicalValue(vocabulary[nextCategory]?.[0] || "");
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
          record_type: "collection",
          proposal_kind: "enrichment",
          submission_type: "correction",
          target_id: collection.id,
          proposed_data: {
            category,
            canonical_value: canonicalValue,
            strength,
            evidence_note: evidenceNote,
          },
          explanation,
          sources: [{
            url: sourceUrl,
            title: sourceTitle || null,
            notes: sourceNotes || null,
          }],
        };
      if (editing) {
        await authorizedRequest(`/submission-drafts/${submissionId}`, {
          method: "PUT", body: JSON.stringify(payload),
        });
        await authorizedRequest(`/submissions/${submissionId}/submit`, { method: "POST" });
        navigate(`/submissions/${submissionId}`);
      } else {
        const submission = await authorizedRequest("/submissions", {
          method: "POST", body: JSON.stringify(payload),
        });
        navigate(`/submissions/${submission.id}`);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!collection && !error) return <StatusMessage>Loading enrichment form…</StatusMessage>;
  if (!collection) return <StatusMessage error>{error}</StatusMessage>;

  return <>
    <p className="eyebrow">Community research · controlled vocabulary</p>
    <h1>{editing ? "Revise editorial enrichment" : "Suggest editorial enrichment"}</h1>
    <p>{collection.label} · {collection.name || `${collection.season} ${collection.release_year}`}</p>
    <p>Your evidence-backed suggestion enters the existing moderation and audit workflow. It cannot publish itself.</p>
    <form className="record-form" onSubmit={submit}>
      <label>Descriptor category<select value={category} onChange={changeCategory} required>{Object.keys(vocabulary).map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>Canonical descriptor<select value={canonicalValue} onChange={(event) => setCanonicalValue(event.target.value)} required>{values.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>Strength<select value={strength} onChange={(event) => setStrength(event.target.value)} required><option value="dominant">Dominant</option><option value="supporting">Supporting</option></select></label>
      <label>Evidence note<textarea rows="4" value={evidenceNote} onChange={(event) => setEvidenceNote(event.target.value)} required /></label>
      <label>Why does this improve discovery?<textarea rows="4" value={explanation} onChange={(event) => setExplanation(event.target.value)} required /></label>
      <fieldset><legend>Supporting source</legend><label>Source URL<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} required /></label><label>Source title<input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} /></label><label>Source notes<textarea rows="3" value={sourceNotes} onChange={(event) => setSourceNotes(event.target.value)} /></label></fieldset>
      <div className="actions"><button type="submit" disabled={busy}>{busy ? "Submitting…" : "Submit for review"}</button></div>
      <StatusMessage error>{error}</StatusMessage>
    </form>
  </>;
}
