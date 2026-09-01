import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";
import { useApplicationUser } from "../auth/ApplicationUserContext";

const emptyDesigner = {
  full_name: "",
  nationality: "",
  birth_year: "",
  website: "",
  biography: "",
};
export default function DesignerForm() {
  const { designerId } = useParams();
  const editing = Boolean(designerId);
  const navigate = useNavigate();
  const { authorizedRequest } = useApplicationUser();
  const [form, setForm] = useState(emptyDesigner);
  const [status, setStatus] = useState(editing ? "Loading designer…" : "");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!editing) return;
    apiRequest(`/designers/${designerId}`)
      .then((designer) => {
        setForm({
          full_name: designer.full_name,
          nationality: designer.nationality || "",
          birth_year: designer.birth_year ?? "",
          website: designer.website || "",
          biography: designer.biography || "",
        });
        setStatus("");
      })
      .catch((error) => {
        setError(error.message);
        setStatus("");
      });
  }, [designerId, editing]);
  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  async function submit(event) {
    event.preventDefault();
    setStatus("Saving designer…");
    setError("");
    let website = form.website.trim();
    if (website && !/^https?:\/\//i.test(website))
      website = `https://${website}`;
    const payload = {
      full_name: form.full_name,
      nationality: form.nationality || null,
      birth_year: form.birth_year ? Number(form.birth_year) : null,
      website: website || null,
      biography: form.biography || null,
    };
    try {
      const result = await authorizedRequest(
        editing ? `/designers/${designerId}` : "/designers",
        { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) },
      );
      navigate(`/designers/${result.id}`);
    } catch (error) {
      setError(error.message);
      setStatus("");
    }
  }
  return (
    <>
      <p className="eyebrow">Archive editor</p>
      <h1>{editing ? "Edit Designer" : "Add a Designer"}</h1>
      <StatusMessage>{status}</StatusMessage>
      <StatusMessage error>{error}</StatusMessage>
      <form className="record-form" onSubmit={submit}>
        <label>
          Full name
          <input
            name="full_name"
            value={form.full_name}
            onChange={updateField}
            required
          />
        </label>
        <label>
          Nationality
          <input
            name="nationality"
            value={form.nationality}
            onChange={updateField}
          />
        </label>
        <label>
          Birth year
          <input
            name="birth_year"
            type="number"
            min="1800"
            max="2100"
            value={form.birth_year}
            onChange={updateField}
          />
        </label>
        <label>
          Website
          <input
            name="website"
            inputMode="url"
            placeholder="www.example.com"
            value={form.website}
            onChange={updateField}
          />
        </label>
        <label>
          Biography
          <textarea
            name="biography"
            rows="6"
            value={form.biography}
            onChange={updateField}
          />
        </label>
        <button className="button" type="submit">
          {editing ? "Save changes" : "Save designer"}
        </button>
        <StatusMessage error>{error}</StatusMessage>
      </form>
    </>
  );
}
