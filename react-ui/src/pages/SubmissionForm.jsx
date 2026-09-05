import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";
import { SUPPORTED_NATIONALITIES } from "../nationalityFlags";

const designerFields = [
  ["full_name", "Full name"], ["nationality", "Nationality"],
  ["birth_year", "Birth year", "number"], ["website", "Website", "url"],
  ["biography", "Biography", "textarea"],
];
const collectionFields = [
  ["designer_id", "Designer ID", "number"], ["label", "Label or fashion house"],
  ["name", "Collection name"], ["season", "Season"],
  ["release_year", "Release year", "number"],
  ["piece_count", "Piece count", "number"], ["description", "Description", "textarea"],
  ["source_url", "Curated source URL", "url"], ["youtube_video_id", "YouTube URL or video ID"],
];

export default function SubmissionForm() {
  const location = useLocation();
  const navigate = useNavigate();
  const { submissionId } = useParams();
  const editing = Boolean(submissionId);
  const { authorizedRequest } = useApplicationUser();
  const [recordType, setRecordType] = useState("designer");
  const [submissionType, setSubmissionType] = useState("addition");
  const [targetId, setTargetId] = useState("");
  const [fields, setFields] = useState({});
  const [explanation, setExplanation] = useState("");
  const [sources, setSources] = useState([{ url: "", title: "", notes: "" }]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const required = submissionType === "addition";

  useEffect(() => {
    if (!editing) return;
    setStatus("Loading proposal…");
    authorizedRequest(`/submissions/${submissionId}`)
      .then((submission) => {
        if (!submission || !["draft", "changes_requested"].includes(submission.status)) {
          throw new Error("This submission is not available for editing.");
        }
        setRecordType(submission.record_type);
        setSubmissionType(submission.submission_type);
        setTargetId(submission.target_id ? String(submission.target_id) : "");
        setFields(Object.fromEntries(
          Object.entries(submission.proposed_data).map(([key, value]) => [key, value ?? ""]),
        ));
        setExplanation(submission.explanation || "");
        setSources(submission.sources.length
          ? submission.sources.map((source) => ({ url: source.url, title: source.title || "", notes: source.notes || "" }))
          : [{ url: "", title: "", notes: "" }]);
        setStatus(location.state?.notice || "");
      })
      .catch((requestError) => {
        setError(requestError.message);
        setStatus("");
      });
  }, [authorizedRequest, editing, location.state?.notice, submissionId]);

  function changeRecordType(event) {
    const nextRecordType = event.target.value;
    setRecordType(nextRecordType);
    setFields(nextRecordType === "collection" && submissionType === "addition" ? { status: "released" } : {});
  }

  function changeSubmissionType(event) {
    const nextSubmissionType = event.target.value;
    setSubmissionType(nextSubmissionType);
    setFields({ ...fields, status: recordType === "collection" && nextSubmissionType === "addition" ? "released" : "" });
  }

  function updateField(event) {
    setFields({ ...fields, [event.target.name]: event.target.value });
  }

  function updateSource(index, field, value) {
    setSources(sources.map((source, sourceIndex) => (
      sourceIndex === index ? { ...source, [field]: value } : source
    )));
  }

  function requestBody() {
    const numericFields = new Set(["birth_year", "designer_id", "release_year", "piece_count"]);
    const proposedData = Object.fromEntries(
      Object.entries(fields)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, numericFields.has(key) ? Number(value) : value]),
    );
    if (recordType === "collection" && submissionType === "addition" && !proposedData.status) {
      proposedData.status = "released";
    }
    const startedSources = sources.filter((source) => (
      source.url.trim() || source.title.trim() || source.notes.trim()
    ));
    if (startedSources.some((source) => !source.url.trim())) {
      throw new Error("Add a URL for each started source or remove the unfinished source row.");
    }
    return JSON.stringify({
      record_type: recordType,
      submission_type: submissionType,
      target_id: submissionType === "correction" && targetId ? Number(targetId) : null,
      proposed_data: proposedData,
      explanation,
      sources: startedSources.map((source) => ({
        url: source.url,
        title: source.title || null,
        notes: source.notes || null,
      })),
    });
  }

  async function saveDraft() {
    setBusy(true);
    setStatus("Saving draft…");
    setError("");
    try {
      const saved = await authorizedRequest(
        editing ? `/submission-drafts/${submissionId}` : "/submission-drafts",
        { method: editing ? "PUT" : "POST", body: requestBody() },
      );
      if (editing) setStatus("Draft saved.");
      else navigate(`/submissions/${saved.id}/edit`, {
        replace: true,
        state: { notice: "Draft saved." },
      });
    } catch (requestError) {
      setError(requestError.message);
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setStatus("Submitting proposal…");
    setError("");
    try {
      const body = requestBody();
      if (editing) {
        await authorizedRequest(`/submission-drafts/${submissionId}`, {
          method: "PUT",
          body,
        });
        await authorizedRequest(`/submissions/${submissionId}/submit`, {
          method: "POST",
        });
      } else await authorizedRequest("/submissions", {
        method: "POST",
        body,
      });
      navigate("/submissions/mine");
    } catch (requestError) {
      setError(requestError.message);
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  const fieldDefinitions = recordType === "designer" ? designerFields : collectionFields;
  const requiredAdditionFields = new Set(
    recordType === "designer"
      ? ["full_name"]
      : ["designer_id", "label", "season", "release_year", "status"],
  );

  return <>
    <p className="eyebrow">Community research</p><h1>{editing ? "Revise your proposal" : "Propose an archive update"}</h1>
    <p>Your proposal enters moderation and never changes the public archive directly.</p>
    <form className="record-form" onSubmit={submit}>
      <label>Record type<select value={recordType} onChange={changeRecordType} disabled={editing}><option value="designer">Designer</option><option value="collection">Collection</option></select></label>
      <label>Proposal type<select value={submissionType} onChange={changeSubmissionType} disabled={editing}><option value="addition">Addition</option><option value="correction">Correction</option></select></label>
      {submissionType === "correction" && <label>Existing record ID<input type="number" min="1" value={targetId} onChange={(event) => setTargetId(event.target.value)} required /></label>}
      {fieldDefinitions.map(([name, label, type = "text"]) => {
        if (name === "status") return null;
        const isRequired = required && requiredAdditionFields.has(name);
        return <label key={name}>{label}{type === "textarea" ? <textarea name={name} rows="5" value={fields[name] || ""} onChange={updateField} required={isRequired} /> : <input name={name} type={type} list={name === "nationality" ? "supported-nationalities" : undefined} value={fields[name] || ""} onChange={updateField} required={isRequired} />}{name === "nationality" && <datalist id="supported-nationalities">{SUPPORTED_NATIONALITIES.map((nationality) => <option key={nationality} value={nationality} />)}</datalist>}</label>;
      })}
      {recordType === "collection" && <label>Status<select name="status" value={fields.status ?? (required ? "released" : "")} onChange={updateField} required={required}>{!required && <option value="">Keep unchanged</option>}<option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>}
      <label>Why should the archive change?<textarea rows="5" value={explanation} onChange={(event) => setExplanation(event.target.value)} required /></label>
      <fieldset><legend>Supporting sources</legend><small>Sources are required for review, but a draft may be saved before sources are added.</small>{sources.map((source, index) => <div className="source-fields" key={index}><label>Source URL<input type="url" value={source.url} onChange={(event) => updateSource(index, "url", event.target.value)} required /></label><label>Source title<input value={source.title} onChange={(event) => updateSource(index, "title", event.target.value)} /></label><label>Source notes<textarea rows="3" value={source.notes} onChange={(event) => updateSource(index, "notes", event.target.value)} /></label>{sources.length > 1 && <button className="danger" type="button" onClick={() => setSources(sources.filter((_, sourceIndex) => sourceIndex !== index))}>Remove source</button>}</div>)}<button className="button secondary" type="button" onClick={() => setSources([...sources, { url: "", title: "", notes: "" }])}>Add another source</button></fieldset>
      <div className="actions"><button className="button secondary" type="button" disabled={busy} onClick={saveDraft}>Save draft</button><button className="button" type="submit" disabled={busy}>{editing ? "Save and resubmit" : "Submit for review"}</button></div>
      <StatusMessage>{status}</StatusMessage><StatusMessage error>{error}</StatusMessage>
    </form>
  </>;
}
