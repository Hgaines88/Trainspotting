import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";
import { useApplicationUser } from "../auth/ApplicationUserContext";

const emptyCollection = {
  label: "", name: "", season: "", release_year: "", status: "concept",
  piece_count: "", description: "", source_url: "", youtube_video_id: "",
};

export default function CollectionForm() {
  const params = useParams();
  const editing = Boolean(params.collectionId);
  const navigate = useNavigate();
  const { authorizedRequest } = useApplicationUser();
  const [designerId, setDesignerId] = useState(params.designerId || "");
  const [form, setForm] = useState(emptyCollection);
  const [credits, setCredits] = useState([]);
  const [designerOptions, setDesignerOptions] = useState([]);
  const [designerSearch, setDesignerSearch] = useState("");
  const [status, setStatus] = useState(editing ? "Loading collection…" : "");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing) {
      if (!params.designerId) return;
      apiRequest(`/designers/${params.designerId}`).then((designer) => {
        setDesignerOptions([designer]);
        setCredits([{
          designer_id: designer.id,
          designer_name: designer.full_name,
          role: "lead",
          attribution_note: "",
        }]);
      }).catch((requestError) => setError(requestError.message));
      return;
    }
    apiRequest(`/collections/${params.collectionId}`).then((collection) => {
      setDesignerId(String(collection.designer_id));
      setCredits(collection.credits.map((credit) => ({
        ...credit,
        attribution_note: credit.attribution_note || "",
      })));
      setDesignerOptions(collection.credits.map((credit) => ({
        id: credit.designer_id,
        full_name: credit.designer_name,
      })));
      setForm({
        label: collection.label,
        name: collection.name || "",
        season: collection.season,
        release_year: collection.release_year,
        status: collection.status,
        piece_count: collection.piece_count ?? "",
        description: collection.description || "",
        source_url: collection.source_url || "",
        youtube_video_id: collection.youtube_video_id || "",
      });
      setStatus("");
    }).catch((requestError) => { setError(requestError.message); setStatus(""); });
  }, [editing, params.collectionId, params.designerId]);

  useEffect(() => {
    let active = true;
    apiRequest(`/archive-options/designers?search=${encodeURIComponent(designerSearch)}&limit=50`)
      .then((records) => {
        if (!active) return;
        setDesignerOptions((current) => {
          const recordsById = new Map(current.map((record) => [record.id, record]));
          records.forEach((record) => recordsById.set(record.id, record));
          return [...recordsById.values()];
        });
      })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [designerSearch]);

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  function updateCredit(index, field, value) {
    setCredits((current) => current.map((credit, creditIndex) => (
      creditIndex === index ? { ...credit, [field]: value } : credit
    )));
    if (index === 0 && field === "designer_id") setDesignerId(String(value));
  }

  function addCredit() {
    setCredits((current) => [...current, {
      designer_id: "",
      designer_name: "",
      role: "collaborator",
      attribution_note: "",
    }]);
  }

  function removeCredit(index) {
    setCredits((current) => current.filter((_, creditIndex) => creditIndex !== index));
  }

  async function submit(event) {
    event.preventDefault();
    setStatus("Saving collection…");
    setError("");
    const payload = {
      designer_id: Number(designerId),
      label: form.label,
      name: form.name || null,
      season: form.season,
      release_year: Number(form.release_year),
      status: form.status,
      piece_count: form.piece_count === "" ? null : Number(form.piece_count),
      description: form.description || null,
      source_url: form.source_url || null,
      youtube_video_id: form.youtube_video_id || null,
      credits: credits.map((credit, index) => ({
        designer_id: Number(credit.designer_id),
        role: index === 0 ? "lead" : credit.role,
        position: index + 1,
        attribution_note: credit.attribution_note || null,
      })),
    };
    try {
      const result = await authorizedRequest(editing ? `/collections/${params.collectionId}` : "/collections", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      navigate(`/collections/${result.id}`);
    } catch (requestError) {
      setError(requestError.message);
      setStatus("");
    }
  }

  return (
    <>
      <p className="eyebrow">Archive editor</p><h1>{editing ? "Edit Collection" : "Add a Collection"}</h1>
      <StatusMessage>{status}</StatusMessage><StatusMessage error>{error}</StatusMessage>
      <form className="record-form" onSubmit={submit}>
        <label>Label or fashion house<input name="label" value={form.label} onChange={updateField} required /></label>
        <label>Collection name<input name="name" value={form.name} onChange={updateField} /></label>
        <label>Season<input name="season" value={form.season} onChange={updateField} required /></label>
        <label>Release year<input name="release_year" type="number" min="1900" max="2100" value={form.release_year} onChange={updateField} required /></label>
        <label>Status<select name="status" value={form.status} onChange={updateField}><option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>
        <label>Piece count<input name="piece_count" type="number" min="0" value={form.piece_count} onChange={updateField} /></label>
        <label>Description<textarea name="description" rows="6" value={form.description} onChange={updateField} /></label>
        <fieldset className="credit-editor">
          <legend>Collection credits</legend>
          <label>Find a designer<input type="search" value={designerSearch} onChange={(event) => setDesignerSearch(event.target.value)} placeholder="Search designer names" /></label>
          {credits.map((credit, index) => (
            <div className="credit-editor-row" key={`${index}-${credit.designer_id}`}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <label>Designer<select value={credit.designer_id} onChange={(event) => updateCredit(index, "designer_id", event.target.value)} required>
                <option value="">Choose designer</option>
                {designerOptions.map((designer) => <option key={designer.id} value={designer.id}>{designer.full_name}</option>)}
              </select></label>
              <label>Role<select value={index === 0 ? "lead" : credit.role} onChange={(event) => updateCredit(index, "role", event.target.value)} disabled={index === 0}>
                {index === 0 && <option value="lead">Lead</option>}
                {index > 0 && <><option value="co-designer">Co-designer</option><option value="guest">Guest</option><option value="collaborator">Collaborator</option><option value="attribution-note">Attribution note</option></>}
              </select></label>
              <label>Attribution note<input value={credit.attribution_note} onChange={(event) => updateCredit(index, "attribution_note", event.target.value)} maxLength="500" /></label>
              {index > 0 && <button className="danger" type="button" onClick={() => removeCredit(index)}>Remove</button>}
            </div>
          ))}
          <button className="button secondary" type="button" onClick={addCredit}>Add contributor</button>
          <small>The first credit is always the lead designer. Drag ordering is intentionally deferred; rows save in the order shown.</small>
        </fieldset>
        <fieldset>
          <legend>Curated media</legend>
          <label>Collection source URL<input name="source_url" type="url" placeholder="https://www.vogue.com/..." value={form.source_url} onChange={updateField} /></label>
          <label>YouTube URL or video ID<input name="youtube_video_id" placeholder="https://www.youtube.com/watch?v=..." value={form.youtube_video_id} onChange={updateField} /></label>
          <small>Use a source you trust and an official brand or publisher video.</small>
        </fieldset>
        <button className="button" type="submit">{editing ? "Save changes" : "Save collection"}</button>
        <StatusMessage error>{error}</StatusMessage>
      </form>
    </>
  );
}
