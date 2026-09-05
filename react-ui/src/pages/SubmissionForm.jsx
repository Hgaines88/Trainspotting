import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import { apiRequest } from "../api";
import ArchiveRecordSelector from "../components/ArchiveRecordSelector";
import CorrectionField from "../components/CorrectionField";
import StatusMessage from "../components/StatusMessage";
import ValidationSummary from "../components/ValidationSummary";
import { SUPPORTED_NATIONALITIES } from "../nationalityFlags";
import { buildProposedData } from "../submissionProposal";
import { startedSources, validateForReview } from "../submissionValidation";

const designerFields = [
  ["full_name", "Full name"], ["nationality", "Nationality"],
  ["birth_year", "Birth year", "number"], ["website", "Website", "url"],
  ["biography", "Biography", "textarea"],
];
const collectionFields = [
  ["designer_id", "Designer or creative lead"], ["label", "Label or fashion house"],
  ["name", "Collection name"], ["season", "Season"],
  ["release_year", "Release year", "number"],
  ["piece_count", "Piece count", "number"], ["description", "Description", "textarea"],
  ["source_url", "Curated source URL", "url"], ["youtube_video_id", "YouTube URL or video ID"],
];
const requiredCanonicalFields = {
  designer: new Set(["full_name"]),
  collection: new Set(["designer_id", "label", "season", "release_year", "status"]),
};
const fieldLabels = Object.fromEntries([
  ...designerFields, ...collectionFields, ["status", "Status"],
].map(([name, label]) => [name, label]));

const designerLabel = (designer) => [designer.full_name, designer.nationality]
  .filter(Boolean)
  .join(" — ");
const collectionLabel = (collection) => {
  const title = collection.name ? `${collection.label}: ${collection.name}` : collection.label;
  const date = [collection.season, collection.release_year].filter(Boolean).join(" ");
  return [collection.lead_designer, title, date].filter(Boolean).join(" — ");
};

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
  const [fieldActions, setFieldActions] = useState({});
  const [explanation, setExplanation] = useState("");
  const [sources, setSources] = useState([{ url: "", title: "", notes: "" }]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState([]);
  const [busy, setBusy] = useState(false);
  const [designers, setDesigners] = useState([]);
  const [collections, setCollections] = useState([]);
  const [designerSearch, setDesignerSearch] = useState("");
  const [collectionSearch, setCollectionSearch] = useState("");
  const [designersLoading, setDesignersLoading] = useState(false);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [designersError, setDesignersError] = useState("");
  const [collectionsError, setCollectionsError] = useState("");
  const required = submissionType === "addition";
  const needsDesignerOptions = (
    (recordType === "designer" && submissionType === "correction")
    || (recordType === "collection" && (
      submissionType === "addition" || fieldActions.designer_id === "replace"
    ))
  );
  const needsCollectionOptions = recordType === "collection" && submissionType === "correction";

  useEffect(() => {
    if (!needsDesignerOptions) {
      setDesigners([]);
      setDesignersLoading(false);
      setDesignersError("");
      return undefined;
    }
    let active = true;
    setDesignersLoading(true);
    const timeout = window.setTimeout(async () => {
      try {
        const records = await apiRequest(`/archive-options/designers?search=${encodeURIComponent(designerSearch)}&limit=20`);
        const selectedId = recordType === "designer" ? targetId : fields.designer_id;
        if (selectedId && !records.some((record) => String(record.id) === String(selectedId))) {
          records.push(await apiRequest(`/designers/${selectedId}`));
        }
        if (active) {
          setDesigners(records);
          setDesignersError("");
        }
      } catch (requestError) {
        if (active) setDesignersError(requestError.message);
      } finally {
        if (active) setDesignersLoading(false);
      }
    }, 250);
    return () => { active = false; window.clearTimeout(timeout); };
  }, [designerSearch, fields.designer_id, needsDesignerOptions, recordType, targetId]);

  useEffect(() => {
    if (!needsCollectionOptions) {
      setCollections([]);
      setCollectionsLoading(false);
      setCollectionsError("");
      return undefined;
    }
    let active = true;
    setCollectionsLoading(true);
    const timeout = window.setTimeout(async () => {
      try {
        const records = await apiRequest(`/archive-options/collections?search=${encodeURIComponent(collectionSearch)}&limit=20`);
        if (targetId && !records.some((record) => String(record.id) === String(targetId))) {
          records.push(await apiRequest(`/collections/${targetId}`));
        }
        if (active) {
          setCollections(records);
          setCollectionsError("");
        }
      } catch (requestError) {
        if (active) setCollectionsError(requestError.message);
      } finally {
        if (active) setCollectionsLoading(false);
      }
    }, 250);
    return () => { active = false; window.clearTimeout(timeout); };
  }, [collectionSearch, needsCollectionOptions, targetId]);

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
        setFieldActions(Object.fromEntries(
          Object.entries(submission.proposed_data).map(([key, value]) => [key, value === null ? "clear" : "replace"]),
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
    setTargetId("");
    setDesignerSearch("");
    setCollectionSearch("");
    setFieldActions({});
    setFields(nextRecordType === "collection" && submissionType === "addition" ? { status: "released" } : {});
  }

  function changeSubmissionType(event) {
    const nextSubmissionType = event.target.value;
    setSubmissionType(nextSubmissionType);
    setTargetId("");
    setDesignerSearch("");
    setCollectionSearch("");
    setFieldActions({});
    setFields((current) => ({
      ...current,
      status: recordType === "collection" && nextSubmissionType === "addition" ? "released" : "",
    }));
  }

  function updateField(event) {
    setFields((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function updateFieldAction(name, action) {
    setFieldActions((current) => ({ ...current, [name]: action }));
    if (action !== "replace") setFields((current) => ({ ...current, [name]: "" }));
  }

  function updateSource(index, field, value) {
    setSources((current) => current.map((source, sourceIndex) => (
      sourceIndex === index ? { ...source, [field]: value } : source
    )));
  }

  function moveSource(index, direction) {
    setSources((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.length) return current;
      const nextSources = [...current];
      [nextSources[index], nextSources[nextIndex]] = [nextSources[nextIndex], nextSources[index]];
      return nextSources;
    });
  }

  function requestPayload() {
    const proposedData = buildProposedData({
      fields, fieldActions, submissionType, fieldLabels,
    });
    if (recordType === "collection" && submissionType === "addition" && !proposedData.status) {
      proposedData.status = "released";
    }
    const preparedSources = startedSources(sources);
    if (preparedSources.some((source) => !source.url)) {
      throw new Error("Add a URL for each started source or remove the unfinished source row.");
    }
    return {
      record_type: recordType,
      submission_type: submissionType,
      target_id: submissionType === "correction" && targetId ? Number(targetId) : null,
      proposed_data: proposedData,
      explanation,
      sources: preparedSources,
    };
  }

  function requestBody() {
    return JSON.stringify(requestPayload());
  }

  async function saveDraft() {
    setBusy(true);
    setStatus("Saving draft…");
    setError("");
    setValidationErrors([]);
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
    setValidationErrors([]);
    try {
      const payload = requestPayload();
      const reviewErrors = validateForReview({
        recordType: payload.record_type,
        submissionType: payload.submission_type,
        targetId: payload.target_id,
        proposedData: payload.proposed_data,
        explanation: payload.explanation,
        sources: payload.sources,
        fieldLabels,
      });
      if (reviewErrors.length) {
        setValidationErrors(reviewErrors);
        setStatus("");
        return;
      }
      const body = JSON.stringify(payload);
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

  function renderValueInput(name, label, type = "text", isRequired = false) {
    if (name === "designer_id") return <ArchiveRecordSelector
      id="collection-designer"
      label="Designer or creative lead"
      records={designers}
      value={fields.designer_id || ""}
      onChange={(designerId) => setFields((current) => ({ ...current, designer_id: designerId }))}
      onSearchChange={setDesignerSearch}
      getLabel={designerLabel}
      loading={designersLoading}
      error={designersError}
      required={isRequired}
    />;
    if (name === "status") return <label>Status<select name="status" value={fields.status ?? (isRequired ? "released" : "")} onChange={updateField} required={isRequired}><option value="">Choose status</option><option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>;
    return <label>{label}{type === "textarea" ? <textarea name={name} rows="5" value={fields[name] || ""} onChange={updateField} required={isRequired} /> : <input name={name} type={type} list={name === "nationality" ? "supported-nationalities" : undefined} value={fields[name] || ""} onChange={updateField} required={isRequired} />}{name === "nationality" && <datalist id="supported-nationalities">{SUPPORTED_NATIONALITIES.map((nationality) => <option key={nationality} value={nationality} />)}</datalist>}</label>;
  }

  return <>
    <p className="eyebrow">Community research</p><h1>{editing ? "Revise your proposal" : "Propose an archive update"}</h1>
    <p>Your proposal enters moderation and never changes the public archive directly.</p>
    <form className="record-form" onSubmit={submit} noValidate>
      <ValidationSummary errors={validationErrors} />
      <label>Record type<select value={recordType} onChange={changeRecordType} disabled={editing}><option value="designer">Designer</option><option value="collection">Collection</option></select></label>
      <label>Proposal type<select value={submissionType} onChange={changeSubmissionType} disabled={editing}><option value="addition">Addition</option><option value="correction">Correction</option></select></label>
      {submissionType === "correction" && <ArchiveRecordSelector
        id="correction-target"
        label={recordType === "designer" ? "Existing designer" : "Existing collection"}
        records={recordType === "designer" ? designers : collections}
        value={targetId}
        onChange={setTargetId}
        onSearchChange={recordType === "designer" ? setDesignerSearch : setCollectionSearch}
        getLabel={recordType === "designer" ? designerLabel : collectionLabel}
        loading={recordType === "designer" ? designersLoading : collectionsLoading}
        error={recordType === "designer" ? designersError : collectionsError}
        required
      />}
      {fieldDefinitions.map(([name, label, type = "text"]) => {
        const isRequired = required && requiredAdditionFields.has(name);
        const input = renderValueInput(name, label, type, isRequired);
        if (submissionType === "addition") return <div key={name}>{input}</div>;
        return <CorrectionField
          key={name}
          label={label}
          action={fieldActions[name] || "unchanged"}
          onActionChange={(action) => updateFieldAction(name, action)}
          canClear={!requiredCanonicalFields[recordType].has(name)}
        >{input}</CorrectionField>;
      })}
      {recordType === "collection" && submissionType === "correction" && <CorrectionField
        label="Status"
        action={fieldActions.status || "unchanged"}
        onActionChange={(action) => updateFieldAction("status", action)}
        canClear={false}
      >{renderValueInput("status", "Status")}</CorrectionField>}
      {recordType === "collection" && submissionType === "addition" && renderValueInput("status", "Status", "text", true)}
      <label>Why should the archive change?<textarea rows="5" value={explanation} onChange={(event) => setExplanation(event.target.value)} required /></label>
      <fieldset><legend>Supporting sources</legend><small>At least one source is required for review, but drafts may be saved without one.</small>{sources.length === 0 && <StatusMessage>No sources added yet.</StatusMessage>}{sources.map((source, index) => <div className="source-fields" key={index}><h3>Source {index + 1}</h3><label>Source URL<input type="url" value={source.url} onChange={(event) => updateSource(index, "url", event.target.value)} /></label><label>Source title<input value={source.title} onChange={(event) => updateSource(index, "title", event.target.value)} /></label><label>Source notes<textarea rows="3" value={source.notes} onChange={(event) => updateSource(index, "notes", event.target.value)} /></label><div className="source-actions"><button className="secondary" type="button" disabled={index === 0} onClick={() => moveSource(index, -1)}>Move up</button><button className="secondary" type="button" disabled={index === sources.length - 1} onClick={() => moveSource(index, 1)}>Move down</button><button className="danger" type="button" onClick={() => setSources((current) => current.filter((_, sourceIndex) => sourceIndex !== index))}>Remove source</button></div></div>)}<button className="button secondary" type="button" disabled={sources.length >= 20} onClick={() => setSources((current) => [...current, { url: "", title: "", notes: "" }])}>Add another source</button><small>{sources.length} of 20 sources added</small></fieldset>
      <div className="actions"><button className="button secondary" type="button" disabled={busy} onClick={saveDraft}>Save draft</button><button className="button" type="submit" disabled={busy}>{editing ? "Save and resubmit" : "Submit for review"}</button></div>
      <StatusMessage>{status}</StatusMessage><StatusMessage error>{error}</StatusMessage>
    </form>
  </>;
}
