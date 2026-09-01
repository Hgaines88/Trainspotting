import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../api";
import StatusMessage from "../components/StatusMessage";

function labelMonogram(label) {
  return label.split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
}

export default function CollectionDetail() {
  const { collectionId } = useParams();
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest(`/collections/${collectionId}`)
      .then(setCollection)
      .catch((requestError) => setError(requestError.message));
  }, [collectionId]);

  if (error && !collection) return <StatusMessage error>{error}</StatusMessage>;
  if (!collection) return <StatusMessage>Loading collection…</StatusMessage>;

  return (
    <article>
      <div className="collection-heading">
        <span className="label-monogram" aria-hidden="true">{labelMonogram(collection.label)}</span>
        <div><p className="eyebrow">{collection.label}</p><h1>{collection.name || `${collection.season} ${collection.release_year}`}</h1></div>
      </div>
      <p className="meta">{collection.season} {collection.release_year} · {collection.status}</p>
      <dl className="details">
        <div><dt>Lead designer</dt><dd><Link to={`/designers/${collection.designer_id}`}>{collection.lead_designer}</Link></dd></div>
        <div><dt>Piece count</dt><dd>{collection.piece_count ?? "Unavailable"}</dd></div>
      </dl>
      <p>{collection.description || "No description is available."}</p>

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

      <StatusMessage error>{error}</StatusMessage>
    </article>
  );
}
