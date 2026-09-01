import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";
import { nationalityFlags } from "../nationalityFlags";

export default function DesignerList() {
  const [designers, setDesigners] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest("/designers")
      .then(setDesigners)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="page-heading hero-heading">
        <div><p className="eyebrow">Index / {String(designers.length).padStart(3, "0")} active profiles</p><h1>Who<br />made it?</h1></div>
      </div>
      <StatusMessage>{loading ? "Loading designers…" : ""}</StatusMessage>
      <StatusMessage error>{error}</StatusMessage>
      <div className="card-grid">
        {designers.map((designer, index) => {
          const details = [
            nationalityFlags(designer.nationality),
            designer.nationality,
            designer.birth_year ? `Born ${designer.birth_year}` : null,
            designer.collection_count !== undefined
              ? `${designer.collection_count} collections`
              : null,
          ].filter(Boolean);
          return (
            <article className="card" key={designer.id}>
              <span className="card-index">{String(index + 1).padStart(3, "0")}</span>
              <h2><Link to={`/designers/${designer.id}`}>{designer.full_name}<span className="arrow">↗</span></Link></h2>
              <p>{details.join(" · ") || "Additional details unavailable"}</p>
            </article>
          );
        })}
      </div>
    </>
  );
}
