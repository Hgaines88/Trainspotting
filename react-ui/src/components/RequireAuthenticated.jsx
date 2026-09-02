import { Navigate } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "./StatusMessage";

export default function RequireAuthenticated({ children }) {
  const { error, isLoading, isSignedIn } = useApplicationUser();
  if (isLoading) return <StatusMessage>Checking account…</StatusMessage>;
  if (error) return <StatusMessage error>{error}</StatusMessage>;
  if (!isSignedIn) return <Navigate to="/" replace />;
  return children;
}
