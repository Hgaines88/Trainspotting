import { useApplicationUser } from "../auth/ApplicationUserContext";

export default function UserSync() {
  const { error } = useApplicationUser();

  if (!error) return null;

  return (
    <span className="auth-sync-error" role="status" title={error}>
      Account sync unavailable
    </span>
  );
}
