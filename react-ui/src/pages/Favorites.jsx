import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import { collectionCreditLine } from "../collectionAttribution";
import StatusMessage from "../components/StatusMessage";

export default function Favorites() {
  const { authorizedRequest } = useApplicationUser();
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    authorizedRequest("/favorites")
      .then((result) => { if (active) setFavorites(result); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [authorizedRequest]);

  return <>
    <div className="page-heading"><div><p className="eyebrow">Personal archive / {String(favorites.length).padStart(3, "0")} saved</p><h1>Favorites</h1></div><Link className="button secondary" to="/collections">Browse collections</Link></div>
    <StatusMessage>{loading ? "Loading favorites…" : ""}</StatusMessage>
    <StatusMessage error>{error}</StatusMessage>
    {!loading && !error && favorites.length === 0 && <section className="empty-results"><p className="eyebrow">Nothing saved yet</p><h2>Build your personal archive.</h2><p>Save collections from their detail pages, then return here to revisit them.</p><Link className="button" to="/collections">Explore collections</Link></section>}
    {!loading && !error && favorites.length > 0 && <ol className="collection-explorer-results">{favorites.map((collection, index) => <li key={collection.id}><Link to={`/collections/${collection.id}`}><span className="collection-result-index">{String(index + 1).padStart(3, "0")}</span><span className="collection-result-title"><strong>{collection.name || `${collection.season} ${collection.release_year}`}</strong><small>{collection.label}</small></span><span className="collection-result-credit">{collectionCreditLine(collection)}</span><span className="collection-result-meta">{collection.season} {collection.release_year}<small>{collection.status}</small></span><span aria-hidden="true">↗</span></Link></li>)}</ol>}
  </>;
}
