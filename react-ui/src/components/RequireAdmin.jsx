import { Navigate } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "./StatusMessage";

export default function RequireAdmin({ children }) {
  const { error, isAdmin, isLoading, isSignedIn } = useApplicationUser();

  if (isLoading) return <StatusMessage>Checking administrator access…</StatusMessage>;
  if (error) return <StatusMessage error>{error}</StatusMessage>;
  if (!isSignedIn || !isAdmin) return <Navigate to="/" replace />;

  return children;
}
