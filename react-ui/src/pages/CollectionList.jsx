import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiRequest } from "../api";
import { collectionCreditLine } from "../collectionAttribution";
import StatusMessage from "../components/StatusMessage";
import CollectionCover from "../components/CollectionCover";

const EMPTY_PAGINATION = { page: 1, page_size: 12, total: 0, total_pages: 0 };
const FILTER_NAMES = ["search", "nationality", "label", "season", "year", "status"];
const QUERY_NAMES = [...FILTER_NAMES, "sort", "direction", "page"];

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export default function CollectionList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [collections, setCollections] = useState([]);
  const [pagination, setPagination] = useState(EMPTY_PAGINATION);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const queryString = searchParams.toString();
  const page = positiveInteger(searchParams.get("page"), 1);
  const hasQuery = QUERY_NAMES.some((name) => searchParams.get(name));
  const currentSort = searchParams.get("sort") || "newest";
  const defaultDirection = currentSort === "newest" ? "desc" : "asc";
  const sortValue = `${currentSort}:${searchParams.get("direction") || defaultDirection}`;
  const requestParameters = new URLSearchParams(queryString);
  requestParameters.set("page", String(page));
  requestParameters.set("page_size", "12");
  const requestPath = `/collections?${requestParameters.toString()}`;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest(requestPath)
      .then((payload) => {
        if (!active) return;
        setCollections(payload.items);
        setPagination(payload.pagination);
        if (payload.pagination.total_pages > 0 && page > payload.pagination.total_pages) {
          const corrected = new URLSearchParams(queryString);
          corrected.set("page", String(payload.pagination.total_pages));
          setSearchParams(corrected, { replace: true });
        }
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, queryString, requestPath, setSearchParams]);

  function applyFilters(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    for (const name of FILTER_NAMES) {
      const value = String(form.get(name) || "").trim();
      if (value) next.set(name, value);
    }
    const [sort, direction] = String(form.get("sort_order") || "newest:desc").split(":");
    if (sort !== "newest") next.set("sort", sort);
    if (direction !== (sort === "newest" ? "desc" : "asc")) next.set("direction", direction);
    setSearchParams(next);
  }

  function movePage(nextPage) {
    const next = new URLSearchParams(searchParams);
    if (nextPage === 1) next.delete("page");
    else next.set("page", String(nextPage));
    setSearchParams(next);
  }

  return (
    <>
      <div className="page-heading collection-explorer-heading">
        <div><p className="eyebrow">Collections / {String(pagination.total).padStart(3, "0")} documented collections</p><h1>What<br />arrived?</h1></div>
        <Link className="button secondary" to="/">Browse designers</Link>
      </div>
      <form className="archive-filters" key={queryString} onSubmit={applyFilters}>
        <label className="search-field">Search collections<input name="search" type="search" maxLength="120" defaultValue={searchParams.get("search") || ""} placeholder="Collection, designer, label, season…" /></label>
        <label>Nationality<input name="nationality" maxLength="120" defaultValue={searchParams.get("nationality") || ""} /></label>
        <label>Label<input name="label" maxLength="120" defaultValue={searchParams.get("label") || ""} /></label>
        <label>Season<input name="season" maxLength="100" defaultValue={searchParams.get("season") || ""} /></label>
        <label>Year<input name="year" type="number" min="1900" max="2100" defaultValue={searchParams.get("year") || ""} /></label>
        <label>Status<select name="status" defaultValue={searchParams.get("status") || ""}><option value="">Any status</option><option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>
        <label>Sort<select name="sort_order" defaultValue={sortValue}><option value="newest:desc">Newest first</option><option value="oldest:asc">Oldest first</option><option value="label:asc">Label A–Z</option><option value="label:desc">Label Z–A</option><option value="designer:asc">Designer A–Z</option><option value="designer:desc">Designer Z–A</option></select></label>
        <div className="filter-actions"><button type="submit">Apply filters</button>{hasQuery && <Link className="button secondary" to="/collections">Clear all</Link>}</div>
      </form>
      <StatusMessage>{loading ? "Searching collections…" : ""}</StatusMessage>
      <StatusMessage error>{error}</StatusMessage>
      {!loading && !error && collections.length === 0 && <section className="empty-results"><p className="eyebrow">No arrivals</p><h2>No collections match these filters.</h2><p>Try fewer filters, check the spelling, or return to the complete collection archive.</p><Link className="button" to="/collections">Clear filters</Link></section>}
      {!loading && !error && collections.length > 0 && <ol className="collection-explorer-results">
        {collections.map((collection, index) => {
          const resultNumber = (pagination.page - 1) * pagination.page_size + index + 1;
          return <li key={collection.id}><Link to={`/collections/${collection.id}`}><CollectionCover collection={collection} index={resultNumber} /><span className="collection-result-title"><strong>{collection.name || `${collection.season} ${collection.release_year}`}</strong><small>{collection.label}</small></span><span className="collection-result-credit">{collectionCreditLine(collection)}</span><span className="collection-result-meta">{collection.season} {collection.release_year}<small>{collection.status}</small></span><span aria-hidden="true">↗</span></Link></li>;
        })}
      </ol>}
      {!loading && !error && pagination.total_pages > 1 && <nav className="pagination" aria-label="Collection result pages"><button className="secondary" type="button" disabled={pagination.page === 1} onClick={() => movePage(pagination.page - 1)}>Previous</button><span>Page {pagination.page} of {pagination.total_pages} · {pagination.total} collections</span><button className="secondary" type="button" disabled={pagination.page === pagination.total_pages} onClick={() => movePage(pagination.page + 1)}>Next</button></nav>}
    </>
  );
}
