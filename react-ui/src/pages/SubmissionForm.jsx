import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "../components/StatusMessage";

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
  const navigate = useNavigate();
  const { authorizedRequest } = useApplicationUser();
  const [recordType, setRecordType] = useState("designer");
  const [submissionType, setSubmissionType] = useState("addition");
  const [targetId, setTargetId] = useState("");
  const [fields, setFields] = useState({});
  const [explanation, setExplanation] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const required = submissionType === "addition";

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

  async function submit(event) {
    event.preventDefault();
    setStatus("Submitting proposal…");
    setError("");
    const numericFields = new Set(["birth_year", "designer_id", "release_year", "piece_count"]);
    const proposedData = Object.fromEntries(
      Object.entries(fields)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, numericFields.has(key) ? Number(value) : value]),
    );
    if (recordType === "collection" && submissionType === "addition" && !proposedData.status) {
      proposedData.status = "released";
    }
    try {
      await authorizedRequest("/submissions", {
        method: "POST",
        body: JSON.stringify({
          record_type: recordType,
          submission_type: submissionType,
          target_id: submissionType === "correction" ? Number(targetId) : null,
          proposed_data: proposedData,
          explanation,
          sources: [{ url: sourceUrl, title: sourceTitle || null }],
        }),
      });
      navigate("/submissions/mine");
    } catch (requestError) {
      setError(requestError.message);
      setStatus("");
    }
  }

  const fieldDefinitions = recordType === "designer" ? designerFields : collectionFields;
  const requiredAdditionFields = new Set(
    recordType === "designer"
      ? ["full_name"]
      : ["designer_id", "label", "season", "release_year", "status"],
  );

  return <>
    <p className="eyebrow">Community research</p><h1>Propose an archive update</h1>
    <p>Your proposal enters moderation and never changes the public archive directly.</p>
    <form className="record-form" onSubmit={submit}>
      <label>Record type<select value={recordType} onChange={changeRecordType}><option value="designer">Designer</option><option value="collection">Collection</option></select></label>
      <label>Proposal type<select value={submissionType} onChange={changeSubmissionType}><option value="addition">Addition</option><option value="correction">Correction</option></select></label>
      {submissionType === "correction" && <label>Existing record ID<input type="number" min="1" value={targetId} onChange={(event) => setTargetId(event.target.value)} required /></label>}
      {fieldDefinitions.map(([name, label, type = "text"]) => {
        if (name === "status") return null;
        const isRequired = required && requiredAdditionFields.has(name);
        return <label key={name}>{label}{type === "textarea" ? <textarea name={name} rows="5" value={fields[name] || ""} onChange={updateField} required={isRequired} /> : <input name={name} type={type} value={fields[name] || ""} onChange={updateField} required={isRequired} />}</label>;
      })}
      {recordType === "collection" && <label>Status<select name="status" value={fields.status ?? (required ? "released" : "")} onChange={updateField} required={required}>{!required && <option value="">Keep unchanged</option>}<option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>}
      <label>Why should the archive change?<textarea rows="5" value={explanation} onChange={(event) => setExplanation(event.target.value)} required /></label>
      <fieldset><legend>Supporting source</legend><label>Source URL<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} required /></label><label>Source title<input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} /></label></fieldset>
      <button className="button" type="submit">Submit for review</button>
      <StatusMessage>{status}</StatusMessage><StatusMessage error>{error}</StatusMessage>
    </form>
  </>;
}
