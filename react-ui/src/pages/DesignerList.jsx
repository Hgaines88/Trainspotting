import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiRequest } from "../api";
import { collectionCreditLine } from "../collectionAttribution";
import StatusMessage from "../components/StatusMessage";
import { nationalityFlags } from "../nationalityFlags";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import CollectionCover from "../components/CollectionCover";

const EMPTY_PAGINATION = { page: 1, page_size: 12, total: 0, total_pages: 0 };
const FILTER_NAMES = ["search", "nationality", "label", "season", "year", "status"];
const DISCOVERY_NAMES = [...FILTER_NAMES, "sort", "direction", "page"];

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export default function DesignerList() {
  const { isAdmin } = useApplicationUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const [designers, setDesigners] = useState([]);
  const [recentCollections, setRecentCollections] = useState([]);
  const [pagination, setPagination] = useState(EMPTY_PAGINATION);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const queryString = searchParams.toString();
  const page = positiveInteger(searchParams.get("page"), 1);
  const hasFilters = DISCOVERY_NAMES.some((name) => searchParams.get(name));
  const currentSort = searchParams.get("sort") || "name";
  const defaultDirection = ["newest", "collections"].includes(currentSort) ? "desc" : "asc";
  const sortValue = `${currentSort}:${searchParams.get("direction") || defaultDirection}`;

  const requestParameters = new URLSearchParams(queryString);
  requestParameters.set("page", String(page));
  requestParameters.set("page_size", "12");
  const requestPath = `/designers?${requestParameters.toString()}`;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest(requestPath)
      .then((payload) => {
        if (!active) return;
        setDesigners(payload.items);
        setPagination(payload.pagination);
        if (payload.pagination.total_pages > 0 && page > payload.pagination.total_pages) {
          const corrected = new URLSearchParams(queryString);
          corrected.set("page", String(payload.pagination.total_pages));
          setSearchParams(corrected, { replace: true });
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [page, queryString, requestPath, setSearchParams]);

  useEffect(() => {
    if (hasFilters) {
      setRecentCollections([]);
      return undefined;
    }
    let active = true;
    apiRequest("/collections?sort=newest&direction=desc&page=1&page_size=4")
      .then((payload) => { if (active) setRecentCollections(payload.items); })
      .catch(() => { if (active) setRecentCollections([]); });
    return () => { active = false; };
  }, [hasFilters]);

  function applyFilters(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    for (const name of FILTER_NAMES) {
      const value = String(form.get(name) || "").trim();
      if (value) next.set(name, value);
    }
    const [sort, direction] = String(form.get("sort_order") || "name:asc").split(":");
    if (sort !== "name") next.set("sort", sort);
    if (direction !== "asc") next.set("direction", direction);
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
      <div className="page-heading hero-heading">
        <div><p className="eyebrow">Index / {String(pagination.total).padStart(3, "0")} active profiles</p><h1>Who<br />made it?</h1></div>
        {isAdmin && <Link className="button" to="/designers/new">Add a designer</Link>}
      </div>
      {!hasFilters && <section className="discovery-entry" aria-labelledby="discovery-heading">
        <div className="section-heading"><h2 id="discovery-heading">Start exploring</h2><span>Four ways into the archive</span></div>
        <nav className="discovery-links" aria-label="Archive discovery shortcuts">
          <Link to="/collections?sort=newest&direction=desc"><strong>Latest collections</strong><span>Follow the timeline from newest to oldest</span></Link>
          <Link to="/collections?label=Wales+Bonner"><strong>Browse a label</strong><span>See collections connected through a fashion house</span></Link>
          <Link to="/collections?season=Spring%2FSummer"><strong>Explore a season</strong><span>Compare work from the same calendar moment</span></Link>
          <Link to="/?sort=collections&direction=desc"><strong>Most documented</strong><span>Begin with the archive's richest profiles</span></Link>
        </nav>
        {recentCollections.length > 0 && <div className="recent-collections">
          <p className="eyebrow">Recent archive arrivals</p>
          <ol className="collection-list">
            {recentCollections.map((collection, index) => <li key={collection.id}><Link to={`/collections/${collection.id}`}><CollectionCover collection={collection} index={index + 1} compact /><span className="collection-list-copy"><strong>{collection.name || collection.label}</strong><span>{collectionCreditLine(collection)} · {collection.season} {collection.release_year}</span></span></Link></li>)}
          </ol>
          <p className="discovery-hint">Open a collection to follow its explainable related-collection trail.</p>
        </div>}
      </section>}
      <form className="archive-filters" key={queryString} onSubmit={applyFilters}>
        <label className="search-field">Search the archive<input name="search" type="search" maxLength="120" defaultValue={searchParams.get("search") || ""} placeholder="Designer, label, collection, season…" /></label>
        <label>Nationality<input name="nationality" maxLength="120" defaultValue={searchParams.get("nationality") || ""} /></label>
        <label>Label<input name="label" maxLength="120" defaultValue={searchParams.get("label") || ""} /></label>
        <label>Season<input name="season" maxLength="100" defaultValue={searchParams.get("season") || ""} /></label>
        <label>Year<input name="year" type="number" min="1900" max="2100" defaultValue={searchParams.get("year") || ""} /></label>
        <label>Status<select name="status" defaultValue={searchParams.get("status") || ""}><option value="">Any status</option><option value="concept">Concept</option><option value="in-production">In production</option><option value="released">Released</option><option value="archived">Archived</option></select></label>
        <label>Sort<select name="sort_order" defaultValue={sortValue}><option value="name:asc">Name A–Z</option><option value="name:desc">Name Z–A</option><option value="newest:desc">Newest collection</option><option value="oldest:asc">Oldest collection</option><option value="collections:desc">Most collections</option></select></label>
        <div className="filter-actions"><button type="submit">Apply filters</button>{hasFilters && <Link className="button secondary" to="/">Clear all</Link>}</div>
      </form>
      <StatusMessage>{loading ? "Searching the archive…" : ""}</StatusMessage>
      <StatusMessage error>{error}</StatusMessage>
      {!loading && !error && designers.length === 0 && <section className="empty-results"><p className="eyebrow">No arrivals</p><h2>No profiles match these filters.</h2><p>Try fewer filters, check the spelling, search a broader term, or clear the current search.</p><Link className="button" to="/">Clear filters</Link></section>}
      {!loading && !error && designers.length > 0 && <div className="card-grid">
        {designers.map((designer, index) => {
          const details = [
            nationalityFlags(designer.nationality),
            designer.nationality,
            designer.birth_year ? `Born ${designer.birth_year}` : null,
            `${designer.collection_count} ${designer.collection_count === 1 ? "collection" : "collections"}`,
          ].filter(Boolean);
          const resultNumber = (pagination.page - 1) * pagination.page_size + index + 1;
          return (
            <article className="card" key={designer.id}>
              <span className="card-index">{String(resultNumber).padStart(3, "0")}</span>
              <h2><Link to={`/designers/${designer.id}`}>{designer.full_name}<span className="arrow">↗</span></Link></h2>
              <p>{details.join(" · ") || "Additional details unavailable"}</p>
            </article>
          );
        })}
      </div>}
      {!loading && !error && pagination.total_pages > 1 && <nav className="pagination" aria-label="Designer result pages">
        <button className="secondary" type="button" disabled={pagination.page === 1} onClick={() => movePage(pagination.page - 1)}>Previous</button>
        <span>Page {pagination.page} of {pagination.total_pages} · {pagination.total} profiles</span>
        <button className="secondary" type="button" disabled={pagination.page === pagination.total_pages} onClick={() => movePage(pagination.page + 1)}>Next</button>
      </nav>}
    </>
  );
}
