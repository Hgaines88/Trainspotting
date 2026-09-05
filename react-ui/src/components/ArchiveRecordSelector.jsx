import { useMemo, useState } from "react";

export default function ArchiveRecordSelector({
  id,
  label,
  records,
  value,
  onChange,
  getLabel,
  loading = false,
  error = "",
  required = false,
}) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const selected = records.find((record) => String(record.id) === String(value));
  const matches = useMemo(() => records.filter((record) => (
    getLabel(record).toLocaleLowerCase().includes(normalizedQuery)
  )), [getLabel, normalizedQuery, records]);
  const options = selected && !matches.some((record) => record.id === selected.id)
    ? [selected, ...matches]
    : matches;

  return <div className="archive-record-selector">
    <label htmlFor={`${id}-search`}>Search {label}</label>
    <input
      id={`${id}-search`}
      type="search"
      value={query}
      onChange={(event) => setQuery(event.target.value)}
      placeholder={`Search ${label.toLocaleLowerCase()}`}
      disabled={loading || Boolean(error)}
    />
    <label htmlFor={id}>{label}</label>
    <select
      id={id}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={required}
      disabled={loading || Boolean(error)}
    >
      <option value="">Choose {label.toLocaleLowerCase()}</option>
      {options.map((record) => <option key={record.id} value={record.id}>{getLabel(record)}</option>)}
    </select>
    <small aria-live="polite">
      {loading
        ? `Loading ${label.toLocaleLowerCase()}…`
        : error || `${matches.length} matching ${matches.length === 1 ? "record" : "records"}`}
    </small>
  </div>;
}
