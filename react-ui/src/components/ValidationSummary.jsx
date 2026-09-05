import { useEffect, useRef } from "react";

export default function ValidationSummary({ errors }) {
  const summaryRef = useRef(null);
  useEffect(() => {
    if (errors.length) summaryRef.current?.focus();
  }, [errors]);
  if (!errors.length) return null;
  return <section className="validation-summary" role="alert" tabIndex="-1" ref={summaryRef}>
    <h2>Review this proposal before submitting</h2>
    <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
  </section>;
}
