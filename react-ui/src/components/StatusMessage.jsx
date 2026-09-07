export default function StatusMessage({ children, error = false }) {
  if (!children) return null;
  return (
    <p
      aria-live={error ? "assertive" : "polite"}
      className={error ? "status error" : "status"}
      role={error ? "alert" : "status"}
    >
      {children}
    </p>
  );
}
