import { collectionCoverStyle } from "../collectionCover.js";

function labelMark(label = "Archive") {
  return label.split(/\s+/).filter(Boolean).slice(0, 2)
    .map((word) => word[0]).join("").toUpperCase() || "AR";
}

export default function CollectionCover({ collection, index, compact = false }) {
  const title = collection.name || `${collection.season || "Undated"} ${collection.release_year || ""}`.trim();
  return (
    <span
      className={`collection-cover${compact ? " collection-cover-compact" : ""}`}
      style={collectionCoverStyle(collection)}
      aria-hidden="true"
    >
      <span className="collection-cover-topline">
        <span>{index ? String(index).padStart(3, "0") : "TS"}</span>
        <span>{collection.status || "archive"}</span>
      </span>
      <span className="collection-cover-mark">{labelMark(collection.label)}</span>
      <span className="collection-cover-copy">
        <strong>{title}</strong>
        <small>{collection.label || "Independent"}</small>
      </span>
      <span className="collection-cover-season">
        {collection.season || "Season pending"} / {collection.release_year || "—"}
      </span>
    </span>
  );
}
