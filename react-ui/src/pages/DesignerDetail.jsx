import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";
import { nationalityFlags } from "../nationalityFlags";
import { useApplicationUser } from "../auth/ApplicationUserContext";

export default function DesignerDetail() {
  const { designerId } = useParams();
  const navigate = useNavigate();
  const { authorizedRequest, isAdmin } = useApplicationUser();
  const [designer, setDesigner] = useState(null);
  const [collections, setCollections] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      apiRequest(`/designers/${designerId}`),
      apiRequest(`/designers/${designerId}/collections`),
    ]).then(([designerData, collectionData]) => {
      setDesigner(designerData);
      setCollections(collectionData);
    }).catch((requestError) => setError(requestError.message));
  }, [designerId]);

  if (error && !designer) return <StatusMessage error>{error}</StatusMessage>;
  if (!designer) return <StatusMessage>Loading designer…</StatusMessage>;

  const flags = nationalityFlags(designer.nationality);
  const details = [designer.nationality, designer.birth_year ? `Born ${designer.birth_year}` : null].filter(Boolean);
  async function deleteDesigner() {
    if (!window.confirm(`Delete ${designer.full_name} and all associated collections?`)) return;
    try {
      await authorizedRequest(`/designers/${designerId}`, { method: "DELETE" });
      navigate("/");
    } catch (requestError) {
      setError(requestError.message);
    }
  }
  return (
    <>
      <p className="eyebrow">Designer profile / ID {String(designer.id).padStart(3, "0")}</p>
      <h1 className="profile-title">{flags && <span className="profile-flag" aria-label={`${designer.nationality} flag`}>{flags}</span>}{designer.full_name}</h1>
      <div className="profile-intro"><p className="meta">{details.join(" · ") || "Additional details unavailable"}</p><p className="biography">{designer.biography || "No biography is available."}</p></div>
      <p className="external-link">{designer.website ? <a href={designer.website} target="_blank" rel="noreferrer">Official transmission ↗</a> : "No website is available."}</p>
      {isAdmin && <div className="actions"><Link className="button" to={`/designers/${designerId}/edit`}>Edit designer</Link><Link className="button secondary" to={`/designers/${designerId}/collections/new`}>Add a collection</Link><button className="danger" type="button" onClick={deleteDesigner}>Delete designer</button></div>}
      <StatusMessage error>{error}</StatusMessage>
      <section className="section provenance" aria-labelledby="provenance-heading">
        <div className="section-heading"><h2 id="provenance-heading">Evidence</h2><span>Public provenance</span></div>
        {designer.provenance.sources.length > 0 ? <ul className="source-list">{designer.provenance.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a><span>Approved community evidence{source.reviewed_at ? ` · reviewed ${new Date(String(source.reviewed_at).replace(" ", "T")).toLocaleDateString()}` : ""}</span></li>)}</ul> : <p className="meta">No public source is available for this profile yet.</p>}
      </section>
      <section className="section">
        <div className="section-heading"><h2>Collections</h2><span>{String(collections.length).padStart(2, "0")} records</span></div>
        {collections.length === 0 ? <p>No collections have been added.</p> : (
          <ul className="collection-list">
            {collections.map((collection, index) => (
              <li key={collection.id}><Link to={`/collections/${collection.id}`}><i>{String(index + 1).padStart(2, "0")}</i><strong>{collection.name || collection.label}</strong><span>{collection.name ? `${collection.label} · ${collection.season} ${collection.release_year}` : `${collection.season} ${collection.release_year}`}</span></Link></li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
