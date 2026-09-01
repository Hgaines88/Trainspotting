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
  const [status, setStatus] = useState(editing ? "Loading collection…" : "");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing) return;
    apiRequest(`/collections/${params.collectionId}`).then((collection) => {
      setDesignerId(String(collection.designer_id));
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
  }, [editing, params.collectionId]);

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
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
