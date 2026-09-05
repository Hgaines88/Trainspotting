import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";
import { useApplicationUser } from "../auth/ApplicationUserContext";

function labelMonogram(label) {
  return label.split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
}

export default function CollectionDetail() {
  const { collectionId } = useParams();
  const navigate = useNavigate();
  const { authorizedRequest, isAdmin } = useApplicationUser();
  const [collection, setCollection] = useState(null);
  const [related, setRelated] = useState(null);
  const [relatedError, setRelatedError] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setCollection(null);
    setError("");
    apiRequest(`/collections/${collectionId}`)
      .then((result) => { if (active) setCollection(result); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [collectionId]);

  useEffect(() => {
    let active = true;
    setRelated(null);
    setRelatedError("");
    apiRequest(`/collections/${collectionId}/related?limit=4`)
      .then((result) => { if (active) setRelated(result); })
      .catch((requestError) => { if (active) setRelatedError(requestError.message); });
    return () => { active = false; };
  }, [collectionId]);

  if (error && !collection) return <StatusMessage error>{error}</StatusMessage>;
  if (!collection) return <StatusMessage>Loading collection…</StatusMessage>;

  async function deleteCollection() {
    if (!window.confirm(`Delete ${collection.name || collection.label}?`)) return;
    try {
      await authorizedRequest(`/collections/${collectionId}`, { method: "DELETE" });
      navigate(`/designers/${collection.designer_id}`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return (
    <article>
      <div className="collection-heading">
        <span className="label-monogram" aria-hidden="true">{labelMonogram(collection.label)}</span>
        <div><p className="eyebrow">{collection.label}</p><h1>{collection.name || `${collection.season} ${collection.release_year}`}</h1></div>
      </div>
      <p className="meta">{collection.season} {collection.release_year} · {collection.status}</p>
      <dl className="details">
        <div><dt>Credits</dt><dd><ol className="collection-credits">{collection.credits.map((credit) => <li key={credit.designer_id}><Link to={`/designers/${credit.designer_id}`}>{credit.designer_name}</Link><span>{credit.role}</span>{credit.attribution_note && <small>{credit.attribution_note}</small>}</li>)}</ol></dd></div>
        <div><dt>Piece count</dt><dd>{collection.piece_count ?? "Unavailable"}</dd></div>
      </dl>
      <p>{collection.description || "No description is available."}</p>
      {isAdmin && <div className="actions"><Link className="button" to={`/collections/${collectionId}/edit`}>Edit collection</Link><button className="danger" type="button" onClick={deleteCollection}>Delete collection</button></div>}

      {(collection.youtube_video_id || collection.source_url) && (
        <section className="section media-section">
          <h2>Runway media</h2>
          {collection.youtube_video_id && (
            <div className="video-frame">
              <iframe
                src={`https://www.youtube.com/embed/${collection.youtube_video_id}`}
                title={`${collection.label} ${collection.season} ${collection.release_year} runway video`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            </div>
          )}
          {collection.source_url && <p><a href={collection.source_url} target="_blank" rel="noreferrer">View the curated collection source ↗</a></p>}
        </section>
      )}

      <section className="section related-collections" aria-labelledby="related-collections-heading">
        <div className="section-heading">
          <h2 id="related-collections-heading">Related collections</h2>
          <span>Explainable matches</span>
        </div>
        {related === null && !relatedError && <StatusMessage>Finding related collections…</StatusMessage>}
        {relatedError && <StatusMessage error>Related collections are temporarily unavailable.</StatusMessage>}
        {related?.length === 0 && <p className="meta">No strong metadata matches yet.</p>}
        {related?.length > 0 && (
          <ol className="related-list">
            {related.map((item, index) => (
              <li key={item.id}>
                <Link to={`/collections/${item.id}`}>
                  <span className="related-rank">{String(index + 1).padStart(2, "0")}</span>
                  <span className="related-record">
                    <strong>{item.name || `${item.season} ${item.release_year}`}</strong>
                    <small>{item.label} · {item.season} {item.release_year}</small>
                  </span>
                  <span className="related-score">Match {item.score}</span>
                </Link>
                <ul className="related-reasons" aria-label={`Why ${item.name || item.label} is related`}>
                  {item.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </section>

      <StatusMessage error>{error}</StatusMessage>
    </article>
  );
}
