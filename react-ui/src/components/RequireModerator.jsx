import { Navigate } from "react-router-dom";
import { useApplicationUser } from "../auth/ApplicationUserContext";
import StatusMessage from "./StatusMessage";

export default function RequireModerator({ children }) {
  const { appUser, error, isLoading } = useApplicationUser();
  if (isLoading) return <StatusMessage>Checking moderator access…</StatusMessage>;
  if (error) return <StatusMessage error>{error}</StatusMessage>;
  if (!["moderator", "admin"].includes(appUser?.role)) return <Navigate to="/" replace />;
  return children;
}
